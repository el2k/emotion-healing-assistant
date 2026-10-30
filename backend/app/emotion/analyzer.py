# -*- coding: utf-8 -*-
"""情绪分析组合器：本地规则必跑（保证离线可用），LLM 可选增强。"""
from . import llm, rule_engine


async def analyze(text: str, use_llm: bool = True) -> dict:
    """先跑本地规则，再尝试 LLM 增强（未配置则返回规则结果）。

    设计：LLM 结果作为"增强层"，若解析失败自动回落规则结果，保证永不失败。
    """
    rule_result = rule_engine.analyze(text)

    if not use_llm:
        return rule_result

    llm_result = await llm.analyze(text)
    if llm_result is None:
        return rule_result

    # 合并：保留规则的 high_risk（更保守），采用 LLM 的情绪类别与建议
    merged = rule_result.copy()
    merged["emotion_type"] = llm_result.get("emotion_type", rule_result["emotion_type"])
    merged["polarity"] = llm_result.get("polarity", rule_result["polarity"])
    merged["score"] = llm_result.get("score", rule_result["score"])
    merged["heal_score"] = llm_result.get("heal_score", rule_result["heal_score"])
    merged["high_risk"] = rule_result["high_risk"] or llm_result.get("high_risk", [])
    merged["suggestion"] = llm_result.get("suggestion", "")
    merged["source"] = "llm"
    return merged