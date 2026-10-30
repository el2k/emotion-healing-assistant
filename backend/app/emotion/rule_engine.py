# -*- coding: utf-8 -*-
"""基于词典+规则的本地情绪识别引擎（零外部依赖，可离线运行）。"""
import re

from .lexicon import (
    ELLIPSIS,
    EMOTION_WORDS,
    EXCLAMATION,
    HIGH_RISK_WORDS,
    INTENSIFIERS,
    NEGATIONS,
    NEGATIVE,
    NEUTRAL,
    POSITIVE,
)

# 类别 -> 极性
_CAT_POLARITY = {}
for _cat in EMOTION_WORDS:
    if _cat in ("喜悦", "平静", "感恩", "期待"):
        _CAT_POLARITY[_cat] = POSITIVE
    elif _cat in ("悲伤", "焦虑", "愤怒", "恐惧", "孤独", "委屈", "低落"):
        _CAT_POLARITY[_cat] = NEGATIVE
    else:
        _CAT_POLARITY[_cat] = NEUTRAL

_POSITIVE_CATS = {"喜悦", "平静", "感恩", "期待"}
_NEGATIVE_CATS = {"悲伤", "焦虑", "愤怒", "恐惧", "孤独", "委屈", "低落"}


def _has_negation(text: str, idx: int) -> bool:
    """检查情感词紧邻前 4 个字符内是否有否定词。"""
    ctx = text[max(0, idx - 4):idx]
    for neg in sorted(NEGATIONS, key=len, reverse=True):
        if ctx.endswith(neg):
            return True
    return False


def _boost(text: str, idx: int) -> float:
    """取情感词紧邻前的强化词，放大情感强度。"""
    ctx = text[max(0, idx - 4):idx]
    mult = 1.0
    for word, factor in INTENSIFIERS.items():
        if ctx.endswith(word):
            mult *= factor
    return mult


def analyze(text: str) -> dict:
    """输入一条用户消息，返回完整情绪画像。"""
    text = (text or "").strip()
    if not text:
        return _neutral_result()

    scores = {cat: 0.0 for cat in EMOTION_WORDS}
    evidence = {cat: 0.0 for cat in EMOTION_WORDS}   # 未被否定的正面证据
    hits = []
    denied_positive = False   # 出现"不/没 + 正向词"（如"不开心"）
    denied_negative = False   # 出现"不 + 负向词"（如"不生气"）

    for cat, words in EMOTION_WORDS.items():
        for word, weight in words.items():
            start = 0
            while True:
                idx = text.find(word, start)
                if idx < 0:
                    break
                neg = _has_negation(text, idx)
                boost = _boost(text, idx)
                score = weight * boost * (-1.0 if neg else 1.0)
                if neg:
                    if cat in _POSITIVE_CATS:
                        denied_positive = True
                    else:
                        denied_negative = True
                else:
                    evidence[cat] += weight * boost
                if abs(score) > 0:
                    scores[cat] += score
                    hits.append({"word": word, "category": cat,
                                 "score": round(score, 2)})
                start = idx + len(word)

    has_ellipsis = any(sym in text for sym in ELLIPSIS)
    has_exclaim = any(sym in text for sym in EXCLAMATION)
    high_risk = [w for w in HIGH_RISK_WORDS if w in text]

    # 主导情绪：优先看未被否定的正面证据
    if high_risk:
        dominant, polarity = "低落", NEGATIVE
    else:
        top = max(evidence, key=lambda k: evidence[k])
        if evidence[top] < 1.0:
            # 证据不足：被否定的正向词（"不开心"）→ 低落；否则中性
            if denied_positive:
                dominant, polarity = "低落", NEGATIVE
            else:
                dominant, polarity = "中性", NEUTRAL
        else:
            dominant = top
            polarity = _CAT_POLARITY[top]

    # 强度 0~1（用未否定的峰值）
    peak = max(evidence.values()) if evidence else 0.0
    raw = min(1.0, peak / 3.0)
    if polarity == NEGATIVE and high_risk:
        raw = 1.0
    if polarity == NEGATIVE and has_ellipsis:
        raw = min(1.0, raw * 1.15)
    if polarity != NEUTRAL and has_exclaim:
        raw = min(1.0, raw * 1.1)

    # 负向安抚强度
    heal_score = 0.0
    if polarity == NEGATIVE:
        heal_score = 1.0 if high_risk else min(1.0, raw * 0.6 + 0.25)

    return {
        "emotion_type": dominant,
        "polarity": polarity,
        "score": round(raw, 3),
        "heal_score": round(heal_score, 3),
        "high_risk": high_risk,
        "hits": hits[:20],
        "source": "rule",
    }


def _neutral_result() -> dict:
    return {
        "emotion_type": "中性",
        "polarity": NEUTRAL,
        "score": 0.0,
        "heal_score": 0.0,
        "high_risk": [],
        "hits": [],
        "source": "rule",
    }