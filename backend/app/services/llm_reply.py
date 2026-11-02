# -*- coding: utf-8 -*-
"""回复生成：优先用大模型(带多轮记忆+长期画像+角色人设+会话轨迹策略)，
否则按角色风格降级到本地模板（带去重，避免连续重复同一句安慰）。"""
import httpx

from ..config import settings
from .. import personas


def _build_messages(emotion: dict, user_message: str, history: list[dict],
                    profile_text: str, intent: str, persona_id: str,
                    strategy_text: str = "", length_text: str = "") -> list[dict]:
    msgs = [{"role": "system", "content": personas.system_prompt(persona_id)}]
    if profile_text:
        msgs.append({"role": "system", "content": "【用户长期画像】" + profile_text})
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
                   length_text: str = "") -> tuple[str, str]:
    """返回 (回复文本, 来源)。source 为 llm 或 template。"""
    if settings.LLM_ENABLED and settings.LLM_API_KEY:
        reply = await _call_llm(emotion, user_message, history, profile_text,
                                intent, persona_id, strategy_text, length_text)
        if reply:
            return reply, "llm"
    return (personas.fallback_reply(persona_id, emotion,
                                    recent_replies=recent_replies or []),
            "template")


async def _call_llm(emotion, user_message, history, profile_text, intent,
                    persona_id, strategy_text="", length_text="") -> str | None:
    url = f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {settings.LLM_API_KEY}"}
    payload = {
        "model": settings.LLM_MODEL,
        "messages": _build_messages(emotion, user_message, history, profile_text,
                                    intent, persona_id, strategy_text, length_text),
        "temperature": 0.75,
    }
    try:
        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
        content = content.strip().strip('"').strip()
        return content if content else None
    except Exception:
        return None