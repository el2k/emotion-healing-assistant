# -*- coding: utf-8 -*-
"""回复生成：优先用大模型(带多轮记忆+长期画像+角色人设+会话轨迹策略)，
否则按角色风格降级到本地模板（带去重，避免连续重复同一句安慰）。

含断路器保护：LLM 连续失败超过阈值后自动 OPEN（跳过调用直接降级），
冷却期后 HALF_OPEN 放探测请求验证是否恢复。降级会记录到指标中。
"""
import json
import time

import httpx

from ..config import settings
from .. import personas
from ..observability import metrics, llm_breaker


def _build_messages(emotion: dict, user_message: str, history: list[dict],
                    profile_text: str, intent: str, persona_id: str,
                    strategy_text: str = "", length_text: str = "",
                    knowledge_text: str = "") -> list[dict]:
    msgs = [{"role": "system", "content": personas.system_prompt(persona_id)}]
    if profile_text:
        msgs.append({"role": "system", "content": "【用户长期画像】" + profile_text})
    if knowledge_text:
        msgs.append({"role": "system", "content": knowledge_text})
    for h in history or []:
        if h.get("role") in ("user", "assistant") and h.get("content"):
            msgs.append({"role": h["role"], "content": h["content"]})
    high_risk = bool(emotion.get("high_risk"))
    meta = (f"【当前情绪】{emotion['emotion_type']}；【意图】{intent or '倾诉'}；"
            f"【危机风险】{'是' if high_risk else '否'}")
    msgs.append({"role": "system", "content": meta})
    if strategy_text:
        msgs.append({"role": "system", "content": strategy_text})
    if length_text:
        msgs.append({"role": "system", "content": "【长度要求】" + length_text})
    msgs.append({"role": "user", "content": user_message})
    return msgs


async def generate(emotion: dict, user_message: str = "",
                   history: list[dict] | None = None,
                   profile_text: str = "",
                   intent: str = "",
                   persona_id: str = "nuan",
                   recent_replies: list[str] | None = None,
                   strategy_text: str = "",
                   length_text: str = "",
                   model: str | None = None,
                   include_messages: bool = False,
                   knowledge_text: str = "") -> tuple[str, str, dict]:
    """返回 (回复文本, 来源, 用量信息)。source 为 llm / template / template_degraded。

    用量信息：{"model": 实际模型, "usage": {prompt/completion/total_tokens}}，
    非 LLM 来源时为空 dict。include_messages=True 时附 "messages"（发给 LLM 的
    完整消息数组，仅供链路追踪展示；llm_usage.record 只读 token 字段，不会落库）。
    """
    # 断路器检查：OPEN 时不调用 LLM，直接降级
    if llm_breaker.can_call() and settings.LLM_ENABLED and settings.LLM_API_KEY:
        used_model = model or settings.LLM_MODEL
        start = time.time()
        reply, usage = await _call_llm(emotion, user_message, history, profile_text,
                                       intent, persona_id, strategy_text, length_text,
                                       model=used_model, knowledge_text=knowledge_text)
        latency = (time.time() - start) * 1000
        if reply:
            llm_breaker.record_success()
            metrics.record_llm("reply", latency, success=True)
            extra = {"messages": _build_messages(
                emotion, user_message, history, profile_text,
                intent, persona_id, strategy_text, length_text,
                knowledge_text)} if include_messages else {}
            return reply, "llm", {"model": used_model, "usage": usage or {}, **extra}
        # LLM 调用失败
        llm_breaker.record_failure("LLM returned empty")
        metrics.record_llm("reply", latency, success=False, fallback=True)
        return (personas.fallback_reply(persona_id, emotion,
                                        recent_replies=recent_replies or []),
                "template_degraded", {})
    else:
        if settings.LLM_ENABLED and settings.LLM_API_KEY:
            llm_breaker.record_reject()
        return (personas.fallback_reply(persona_id, emotion,
                                        recent_replies=recent_replies or []),
                "template", {})


async def _call_llm(emotion, user_message, history, profile_text, intent,
                    persona_id, strategy_text="", length_text="",
                    model: str | None = None,
                    knowledge_text: str = "") -> tuple[str | None, dict]:
    """调用 LLM，返回 (内容, usage)。失败返回 (None, {})。"""
    url = f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {settings.LLM_API_KEY}"}
    payload = {
        "model": model or settings.LLM_MODEL,
        "messages": _build_messages(emotion, user_message, history, profile_text,
                                    intent, persona_id, strategy_text, length_text,
                                    knowledge_text),
        "temperature": 0.75,
    }
    try:
        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            body = resp.json()
            content = body["choices"][0]["message"]["content"]
        content = content.strip().strip('"').strip()
        return (content if content else None), (body.get("usage") or {})
    except Exception:
        return None, {}


# ============================================================
# 流式回复生成（SSE）：逐字返回，降低首字延迟
# ============================================================
async def generate_stream(emotion: dict, user_message: str = "",
                          history: list[dict] | None = None,
                          profile_text: str = "",
                          intent: str = "",
                          persona_id: str = "nuan",
                          recent_replies: list[str] | None = None,
                          strategy_text: str = "",
                          length_text: str = "",
                          model: str | None = None,
                          include_messages: bool = False,
                          knowledge_text: str = ""):
    """流式生成回复。yield 事件 dict：
    {"type": "chunk", "content": "..."}   逐段文本
    {"type": "done", "content": "...", "source": "...", "model": "...", "usage": {...}}  完整回复+来源+用量

    断路器 OPEN 或 LLM 未配置时直接 yield 模板回复（一次性）。
    """
    # 断路器检查
    if not (llm_breaker.can_call() and settings.LLM_ENABLED and settings.LLM_API_KEY):
        if settings.LLM_ENABLED and settings.LLM_API_KEY:
            llm_breaker.record_reject()
        # 一次性返回模板
        reply = personas.fallback_reply(persona_id, emotion,
                                        recent_replies=recent_replies or [])
        yield {"type": "chunk", "content": reply}
        yield {"type": "done", "content": reply, "source": "template"}
        return

    used_model = model or settings.LLM_MODEL
    start = time.time()
    url = f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {settings.LLM_API_KEY}"}
    payload = {
        "model": used_model,
        "messages": _build_messages(emotion, user_message, history, profile_text,
                                    intent, persona_id, strategy_text, length_text,
                                    knowledge_text),
        "temperature": 0.75,
        "stream": True,
        "stream_options": {"include_usage": True},   # 末尾 chunk 返回 token 用量
    }

    full_content = ""
    usage: dict = {}
    try:
        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]  # 去掉 "data: " 前缀
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        if chunk.get("usage"):
                            usage = chunk["usage"]
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        text = delta.get("content", "")
                        if text:
                            full_content += text
                            yield {"type": "chunk", "content": text}
                    except (json.JSONDecodeError, IndexError):
                        continue

        latency = (time.time() - start) * 1000
        if full_content.strip():
            llm_breaker.record_success()
            metrics.record_llm("reply_stream", latency, success=True)
            extra = {"messages": payload["messages"]} if include_messages else {}
            yield {"type": "done", "content": full_content.strip(), "source": "llm",
                   "model": used_model, "usage": usage, **extra}
        else:
            # LLM 流式返回为空
            llm_breaker.record_failure("stream returned empty")
            metrics.record_llm("reply_stream", latency, success=False, fallback=True)
            reply = personas.fallback_reply(persona_id, emotion,
                                            recent_replies=recent_replies or [])
            yield {"type": "chunk", "content": reply}
            yield {"type": "done", "content": reply, "source": "template_degraded"}
    except Exception as exc:
        # 流式调用失败：断路器记失败 + 降级
        latency = (time.time() - start) * 1000
        llm_breaker.record_failure(str(exc)[:100])
        metrics.record_llm("reply_stream", latency, success=False, fallback=True)
        reply = personas.fallback_reply(persona_id, emotion,
                                        recent_replies=recent_replies or [])
        yield {"type": "chunk", "content": reply}
        yield {"type": "done", "content": reply, "source": "template_degraded"}