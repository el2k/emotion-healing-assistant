# -*- coding: utf-8 -*-
"""情绪引擎单元测试：python -m tests.test_analyzer"""
import asyncio

from app.emotion import analyzer
from app.emotion.rule_engine import analyze


def test_positive_joy():
    r = analyze("我今天特别开心，老板夸我了，哈哈")
    assert r["polarity"] == "positive"
    assert r["emotion_type"] == "喜悦"


def test_negative_sad():
    r = analyze("最近很难过，心里很压抑，想哭")
    assert r["polarity"] == "negative"
    assert r["emotion_type"] in ("悲伤", "低落")


def test_anxiety():
    r = analyze("我好焦虑，睡不着，压力很大，担心失败")
    assert r["polarity"] == "negative"
    assert r["emotion_type"] in ("焦虑", "低落")


def test_loneliness():
    r = analyze("一个人待着好孤独，没人理解我")
    assert r["polarity"] == "negative"
    assert r["emotion_type"] in ("孤独", "悲伤", "低落")


def test_negation_flip():
    r = analyze("我并不生气，只是有点平静")
    # "不生气" 应被否定
    assert r["polarity"] != "negative" or r["emotion_type"] != "愤怒"


def test_neutral():
    r = analyze("今天吃了面条")
    assert r["polarity"] == "neutral"
    assert r["emotion_type"] == "中性"


def test_high_risk():
    r = analyze("我撑不下去了，不想活了")
    assert r["high_risk"]
    assert r["heal_score"] == 1.0


async def test_combined_fallback():
    # 未配置 LLM 时应返回 rule 结果，不抛异常
    r = await analyzer.analyze("我今天很难过")
    assert r["source"] == "rule"


def main():
    import sys
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            if asyncio.iscoroutinefunction(t):
                asyncio.run(t())
            else:
                t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {t.__name__}: {e}")
    print(f"\n{passed}/{len(tests)} 通过")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(main())