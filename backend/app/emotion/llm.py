# -*- coding: utf-8 -*-
"""大模型情绪深度分析（可选）。未配置时自动降级，不影响主流程。"""
import json

import httpx

from ..config import settings

_SYSTEM_PROMPT = (
    "你是一个温柔的中文情绪分析师。分析用户说的话，只输出 JSON，不要任何解释。"
    "JSON 结构：{\"emotion_type\":\"情绪类别\",\"polarity\":\"positive|negative|neutral\","
    "\"score\":0到1的强度,\"heal_score\":0到1的安抚需要度,\"high_risk\":bool,"
    "\"needs_care\":bool,\"suggestion\":\"简短疗愈建议\"}。"
    "情绪类别从以下选：喜悦、平静、感恩、期待、悲伤、焦虑、愤怒、恐惧、孤独、委屈、低落、中性。"
    "若用户出现轻生/自伤/绝望倾向，high_risk 必须为 true。"
)


def _is_configured() -> bool:
    return bool(settings.LLM_ENABLED and settings.LLM_API_KEY)


def _parse(text: str) -> dict | None:
    """从模型回复中容错提取 JSON。"""
    if not text:
        return None
    cleaned = text.strip()
    # 去掉可能的 markdown 代码围栏
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    try:
        data = json.loads(cleaned)
    except Exception:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end < start:
            return None
        try:
            data = json.loads(cleaned[start:end + 1])
        except Exception:
            return None
    if not isinstance(data, dict) or "emotion_type" not in data:
        return None
    return data


async def analyze(user_message: str) -> dict | None:
    """调用大模型深度分析；失败/未配置返回 None。"""
    if not _is_configured():
        return None
    url = f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {settings.LLM_API_KEY}"}
    payload = {
        "model": settings.LLM_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.2,
    }
    try:
        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT) as client:
            resp = await client.post(settings.LLM_BASE_URL.rstrip("/") + "/chat/completions",
                                     headers=headers, json=payload)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
        data = _parse(content)
        if not data:
            return None
        return {
            "emotion_type": data.get("emotion_type", "中性"),
            "polarity": data.get("polarity", "neutral"),
            "score": float(data.get("confidence", 0.5)),
            "heal_score": float(data.get("heal_score", 0.4)),
            "high_risk": [data.get("high_risk", "")] if data.get("high_risk") else [],
            "suggestion": data.get("suggestion", ""),
            "source": "llm",
        }
    except Exception:
        return None