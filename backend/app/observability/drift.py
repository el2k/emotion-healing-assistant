# -*- coding: utf-8 -*-
"""数据漂移检测：监控情绪识别的输入分布是否发生显著变化。

检测维度：
  1. 情绪标签分布漂移——某类情绪突然激增/骤降
  2. 高风险率漂移——危机识别率突变
  3. 输入长度漂移——用户消息变短/变长（可能意味着使用方式变化）
  4. LLM 降级率漂移——更多请求走规则兜底而非 LLM

方法：将最近 N 小时的分布与前 N 小时的基线做逐维比较，
偏差超过阈值即标记为漂移警报。
"""
from __future__ import annotations

import math
from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import EmotionRecord, Message, ChatSession

# 告警阈值（超过此比例的变化视为漂移）
DRIFT_THRESHOLD = 0.25  # 25%
MIN_SAMPLE = 5  # 至少 N 条记录才做比较

EMOTION_LABELS = ["喜悦", "平静", "感恩", "期待",
                  "悲伤", "焦虑", "愤怒", "恐惧", "孤独", "委屈", "低落", "中性"]


def _distribution(records: list) -> dict[str, float]:
    """计算情绪分布。"""
    if not records:
        return {}
    counter = Counter(r.emotion_type for r in records)
    total = len(records)
    return {label: counter.get(label, 0) / total for label in EMOTION_LABELS}


def _js_divergence(p: dict[str, float], q: dict[str, float]) -> float:
    """Jensen-Shannon 散度（0~1，越大越不同）。"""
    eps = 1e-10
    js = 0
    for key in set(list(p.keys()) + list(q.keys())):
        pk = p.get(key, 0)
        qk = q.get(key, 0)
        mk = (pk + qk) / 2
        if pk > eps:
            js += 0.5 * pk * math.log2(pk / mk)
        if qk > eps:
            js += 0.5 * qk * math.log2(qk / mk)
    return js


def detect_emotion_drift(db: Session, window_hours: int = 24) -> dict:
    """检测情绪分布是否发生漂移。"""
    now = datetime.now(timezone.utc)
    recent_cutoff = now - timedelta(hours=window_hours)
    baseline_cutoff = now - timedelta(hours=window_hours * 2)

    recent = (db.query(EmotionRecord)
              .filter(EmotionRecord.created_at >= recent_cutoff).all())
    baseline = (db.query(EmotionRecord)
                .filter(EmotionRecord.created_at >= baseline_cutoff,
                        EmotionRecord.created_at < recent_cutoff).all())

    if len(recent) < MIN_SAMPLE or len(baseline) < MIN_SAMPLE:
        return {
            "status": "insufficient_data",
            "message": f"样本不足（近期 {len(recent)} / 基线 {len(baseline)}，至少需 {MIN_SAMPLE}）",
            "recent_count": len(recent), "baseline_count": len(baseline),
        }

    recent_dist = _distribution(recent)
    baseline_dist = _distribution(baseline)
    js = _js_divergence(recent_dist, baseline_dist)

    # 逐标签比较涨跌
    label_changes = {}
    for label in EMOTION_LABELS:
        rc = recent_dist.get(label, 0)
        bc = baseline_dist.get(label, 0)
        if bc > 0.01 or rc > 0.01:
            change = rc - bc
            label_changes[label] = {
                "recent_pct": round(rc * 100, 1),
                "baseline_pct": round(bc * 100, 1),
                "change": round(change * 100, 1),
            }

    drifted = js > DRIFT_THRESHOLD
    return {
        "status": "drift" if drifted else "stable",
        "js_divergence": round(js, 3),
        "threshold": DRIFT_THRESHOLD,
        "recent_count": len(recent),
        "baseline_count": len(baseline),
        "recent_distribution": {k: round(v * 100, 1) for k, v in recent_dist.items() if v > 0},
        "baseline_distribution": {k: round(v * 100, 1) for k, v in baseline_dist.items() if v > 0},
        "label_changes": label_changes,
        "message": (
            f"情绪分布漂移警报：JSD={js:.3f} > {DRIFT_THRESHOLD}，"
            f"近期与基线的行为模式出现显著差异，建议检查情绪引擎是否正常"
            if drifted else
            f"情绪分布稳定：JSD={js:.3f} < {DRIFT_THRESHOLD}"
        ),
    }


def detect_highrisk_drift(db: Session, window_hours: int = 24) -> dict:
    """高风险率是否突变（可能意味着用户群体变化或引擎异常）。"""
    now = datetime.now(timezone.utc)
    recent_cutoff = now - timedelta(hours=window_hours)
    baseline_cutoff = now - timedelta(hours=window_hours * 2)

    def _rate(start, end=None):
        q = (db.query(EmotionRecord)
             .filter(EmotionRecord.created_at >= start))
        if end:
            q = q.filter(EmotionRecord.created_at < end)
        records = q.all()
        if not records:
            return 0, 0
        high = sum(1 for r in records if r.polarity < 0 and (r.score or 0) >= 0.7)
        return high / len(records), len(records)

    recent_rate, recent_n = _rate(recent_cutoff)
    baseline_rate, baseline_n = _rate(baseline_cutoff, recent_cutoff)

    if recent_n < MIN_SAMPLE or baseline_n < MIN_SAMPLE:
        return {"status": "insufficient_data",
                "recent_rate": round(recent_rate * 100, 1),
                "baseline_rate": round(baseline_rate * 100, 1)}

    rate_change = recent_rate - baseline_rate
    drifted = abs(rate_change) > 0.10  # 10 个百分点

    return {
        "status": "drift" if drifted else "stable",
        "recent_rate": round(recent_rate * 100, 1),
        "baseline_rate": round(baseline_rate * 100, 1),
        "change_pct": round(rate_change * 100, 1),
        "message": (
            f"高风险率突变：从 {baseline_rate:.1%} 变为 {recent_rate:.1%}（{rate_change:+.1%}），"
            f"可能意味着用户群体变化或危机识别规则需要更新"
            if drifted else
            f"高风险率稳定：{recent_rate:.1%} vs 基线 {baseline_rate:.1%}"
        ),
    }


def detect_input_drift(db: Session, window_hours: int = 24) -> dict:
    """输入长度分布是否漂移。"""
    now = datetime.now(timezone.utc)
    recent_cutoff = now - timedelta(hours=window_hours)
    baseline_cutoff = now - timedelta(hours=window_hours * 2)

    def _avg_len(start, end=None):
        q = (db.query(func.avg(func.length(Message.content)))
             .join(ChatSession, ChatSession.id == Message.session_id)
             .filter(Message.role == "user", Message.created_at >= start))
        if end:
            q = q.filter(Message.created_at < end)
        result = q.scalar()
        return float(result or 0)

    recent_avg = _avg_len(recent_cutoff)
    baseline_avg = _avg_len(baseline_cutoff, recent_cutoff)

    if baseline_avg == 0 or recent_avg == 0:
        return {"status": "insufficient_data", "recent_avg_len": recent_avg}

    ratio = recent_avg / baseline_avg
    drifted = ratio > 1.5 or ratio < 0.67  # 变化超过 50%

    return {
        "status": "drift" if drifted else "stable",
        "recent_avg_len": round(recent_avg, 1),
        "baseline_avg_len": round(baseline_avg, 1),
        "change_ratio": round(ratio, 2),
        "message": (
            f"输入长度漂移：平均消息长度从 {baseline_avg:.0f} 字变为 {recent_avg:.0f} 字"
            f"（{ratio:.2f}x），用户使用方式可能发生变化"
            if drifted else
            f"输入长度稳定：平均 {recent_avg:.0f} 字"
        ),
    }


def drift_report(db: Session) -> dict:
    """汇总全部漂移检测结果。"""
    emotion = detect_emotion_drift(db)
    highrisk = detect_highrisk_drift(db)
    input_len = detect_input_drift(db)

    any_drift = any(r["status"] == "drift" for r in [emotion, highrisk, input_len])
    return {
        "overall_status": "drift_detected" if any_drift else "stable",
        "emotion_distribution": emotion,
        "highrisk_rate": highrisk,
        "input_length": input_len,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
