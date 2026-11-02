# -*- coding: utf-8 -*-
"""情绪分析组合器：本地规则必跑（保证离线可用与危机底线），LLM 可选增强。

双引擎交叉校验原则：
- 危机（high_risk）：规则与 LLM 任一命中即视为命中（宁可误报不可漏报）；
- 情绪类别/极性：LLM 给出的值必须合法，非法或缺失回落规则结果；
- 强度：约束到 [0,1]，LLM 缺失沿用规则打分。
"""
from . import llm, rule_engine

EMOTION_TYPES = {"喜悦", "平静", "感恩", "期待",
                 "悲伤", "焦虑", "愤怒", "恐惧", "孤独", "委屈", "低落", "中性"}
_POLARITY_BY_TYPE = {}
for t in ("喜悦", "平静", "感恩", "期待"):
    _POLARITY_BY_TYPE[t] = "positive"
for t in ("悲伤", "焦虑", "愤怒", "恐惧", "孤独", "委屈", "低落"):
    _POLARITY_BY_TYPE[t] = "negative"
_POLARITY_BY_TYPE["中性"] = "neutral"
_VALID_POLARITY = {"positive", "negative", "neutral"}


def _clamp(v, default):
    try:
        return max(0.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        return default


async def analyze(text: str, use_llm: bool = True) -> dict:
    """先跑本地规则，再尝试 LLM 增强（未配置则返回规则结果）。

    设计：LLM 结果作为"增强层"，经合法性校验后合并；解析失败自动回落规则结果，保证永不失败。
    """
    rule_result = rule_engine.analyze(text)

    if not use_llm:
        return rule_result

    llm_result = await llm.analyze(text)
    if llm_result is None:
        return rule_result

    merged = rule_result.copy()

    # 情绪类别：LLM 值必须合法，否则保留规则结果
    llm_type = llm_result.get("emotion_type")
    if llm_type in EMOTION_TYPES:
        merged["emotion_type"] = llm_type

    # 极性：LLM 值合法则用；否则按最终类别推导（保持自洽）
    llm_polarity = llm_result.get("polarity")
    if llm_polarity in _VALID_POLARITY:
        merged["polarity"] = llm_polarity
    else:
        merged["polarity"] = _POLARITY_BY_TYPE.get(merged["emotion_type"],
                                                   rule_result["polarity"])

    # 强度：LLM 提供则用（约束到 0~1），否则沿用规则
    if "score" in llm_result:
        merged["score"] = _clamp(llm_result["score"], rule_result["score"])
    if "heal_score" in llm_result:
        merged["heal_score"] = _clamp(llm_result["heal_score"], rule_result["heal_score"])

    # 危机底线：任一引擎命中即命中（规则引擎更保守，永远保留）
    merged["high_risk"] = rule_result["high_risk"] or llm_result.get("high_risk", [])
    merged["suggestion"] = llm_result.get("suggestion", "")
    merged["source"] = "llm"
    return merged