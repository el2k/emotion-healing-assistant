# -*- coding: utf-8 -*-
"""用户画像：把散落在消息与情绪记录里的线索，汇总成一张「角色可用的画像卡」。

组成：
  基础信息（陪伴天数 / 活跃天数 / 连续记录 / 关系阶段）
  情绪特征（主导情绪 / 基线心情 / 负向占比 / 波动性 / 高峰时段 / 风险次数 / 趋势）
  话题偏好（工作 / 学习 / 家庭 / 关系 / 健康 / 经济 / 自我 / 未来）
  校准偏好（用户亲手纠正过的识别结果）
  摘要与事实卡（facts 注入角色提示词，让角色「记得你」）
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from statistics import mean, pstdev

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import ChatSession, EmotionCalibration, EmotionRecord, Message, User
from . import emotion_service

# 话题词典：命中即计数（用于画像的「最近反复提到」）
TOPIC_WORDS = {
    "工作": ["加班", "上班", "工作", "职场", "老板", "领导", "同事", "开会", "项目",
             "业绩", "裁员", "面试", "跳槽", "KPI", "汇报"],
    "学习": ["学习", "考试", "上课", "作业", "论文", "导师", "毕设", "毕业", "成绩",
             "复习", "考研", "学校", "挂科"],
    "家庭": ["妈妈", "爸爸", "父母", "家里", "家人", "奶奶", "爷爷", "弟弟", "妹妹",
             "姐姐", "哥哥", "亲戚"],
    "关系": ["朋友", "室友", "同学", "恋爱", "男朋友", "女朋友", "分手", "吵架",
             "约会", "喜欢的人", "失恋"],
    "健康": ["失眠", "睡不着", "睡眠", "身体", "生病", "医院", "头疼", "胃疼", "疲惫", "好累"],
    "经济": ["钱", "房租", "房贷", "工资", "存款", "穷", "兼职", "账单", "花呗"],
    "自我": ["自卑", "没用", "失败", "不够好", "讨厌自己", "内耗", "迷茫", "没意义"],
    "未来": ["未来", "找工作", "方向", "前途", "意义", "目标"],
}

_SLOT_LABEL = {"凌晨": "凌晨", "上午": "上午", "下午": "下午", "傍晚": "傍晚", "晚上": "晚上", "深夜": "深夜"}


def _joined_days(user: User) -> int:
    if not user.created_at:
        return 1
    dt = user.created_at
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(1, (datetime.now(timezone.utc) - dt).days + 1)


def _topics(db: Session, user_id: int, limit: int = 5) -> list[dict]:
    """从最近消息与情绪触发词中提取高频话题。"""
    texts = []
    rows = (db.query(Message.content)
            .join(ChatSession, ChatSession.id == Message.session_id)
            .filter(ChatSession.user_id == user_id, Message.role == "user")
            .order_by(Message.created_at.desc()).limit(200).all())
    texts.extend([r[0] or "" for r in rows])
    trig = (db.query(EmotionRecord.trigger)
            .filter(EmotionRecord.user_id == user_id)
            .order_by(EmotionRecord.created_at.desc()).limit(100).all())
    texts.extend([r[0] or "" for r in trig])
    blob = "\n".join(texts)
    counts = []
    for label, words in TOPIC_WORDS.items():
        n = sum(blob.count(w) for w in words)
        if n:
            counts.append({"name": label, "count": n})
    counts.sort(key=lambda x: -x["count"])
    return counts[:limit]


def _trend(timeline: list[dict]) -> tuple[str, float]:
    """近 7 天 vs 前 7 天的平均心情变化。返回 (描述, 差值)。"""
    days = [d for d in timeline if d.get("count")]
    if len(days) < 4:
        return "", 0.0
    recent = [d["mood"] for d in days[-7:]]
    prev = [d["mood"] for d in days[-14:-7]] or recent[:-1]
    if not prev or not recent:
        return "", 0.0
    diff = mean(recent) - mean(prev)
    if diff >= 0.08:
        return "近期心情在回升", round(diff, 3)
    if diff <= -0.08:
        return "近期心情走低，需要多留意", round(diff, 3)
    return "近期整体平稳", round(diff, 3)


def build_portrait(db: Session, user_id: int, days: int = 90) -> dict:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {}

    lp = emotion_service.long_term_profile(db, user_id, days)
    total = lp.get("total_records", 0)

    active_days = (db.query(func.count(func.distinct(func.date(EmotionRecord.created_at))))
                   .filter(EmotionRecord.user_id == user_id).scalar() or 0)
    risk_count = (db.query(func.count(EmotionRecord.id))
                  .filter(EmotionRecord.user_id == user_id,
                          EmotionRecord.polarity < 0,
                          EmotionRecord.score >= 0.7).scalar() or 0)

    moods = [d["mood"] for d in lp.get("timeline", []) if d.get("count")]
    volatility = pstdev(moods) if len(moods) >= 3 else 0.0

    peak = ""
    tod = lp.get("time_of_day") or []
    if tod:
        top = max(tod, key=lambda x: x["count"])
        slot = str(top.get("slot", ""))
        peak = _SLOT_LABEL.get(slot, slot)

    trend_text, trend_diff = _trend(lp.get("timeline", []))

    calib_rows = (db.query(EmotionCalibration)
                  .filter(EmotionCalibration.user_id == user_id)
                  .order_by(EmotionCalibration.created_at.desc()).limit(5).all())
    calib_total = (db.query(func.count(EmotionCalibration.id))
                   .filter(EmotionCalibration.user_id == user_id).scalar() or 0)

    topics = _topics(db, user_id)

    joined = _joined_days(user)
    if joined <= 3 or total < 5:
        stage = "新朋友"
    elif joined <= 30:
        stage = "熟悉的朋友"
    else:
        stage = "老朋友"

    dominant = lp.get("dominant_emotion") or "中性"
    neg_ratio = lp.get("negative_ratio", 0.0)
    mood = lp.get("avg_mood", 0.5)

    # ---- 摘要 ----
    parts = [f"认识第 {joined} 天，累计 {total} 条情绪记录，活跃 {active_days} 天"]
    if total:
        parts.append(f"主导情绪是「{dominant}」")
        if neg_ratio >= 0.5:
            parts.append(f"负向占比 {round(neg_ratio * 100)}%")
        if volatility >= 0.18:
            parts.append("情绪波动较大")
        if peak:
            parts.append(f"常在{peak}倾诉")
        if topics:
            parts.append("最近反复提到：" + "、".join(t["name"] for t in topics[:3]))
        if trend_text:
            parts.append(trend_text)
    summary = "；".join(parts) + "。"

    # ---- 事实卡（给角色用） ----
    facts = []
    if total:
        facts.append(f"陪伴第 {joined} 天，累计 {total} 条情绪记录")
        facts.append(f"主导情绪是{dominant}，负向占比 {round(neg_ratio * 100)}%")
        if volatility >= 0.18:
            facts.append("情绪起伏比一般人明显，低落时需要更稳的陪伴")
        if peak:
            facts.append(f"通常在{peak}来倾诉")
        if topics:
            facts.append("最近反复提到：" + "、".join(t["name"] for t in topics[:3]))
        if trend_text:
            facts.append(trend_text)
    if calib_total:
        pairs = "；".join(f"「{c.text[:12]}」由{c.original_emotion}纠正为{c.corrected_emotion}"
                         for c in calib_rows[:3])
        facts.append(f"用户校准过 {calib_total} 次情绪识别：{pairs}")
    if risk_count:
        facts.append(f"近 {days} 天有 {risk_count} 次高强度负向记录，需温和提醒专业支持")

    return {
        "basic": {
            "nickname": user.nickname or "",
            "joined_days": joined,
            "active_days": active_days,
            "streak_days": lp.get("streak_days", 0),
            "stage": stage,
        },
        "emotion": {
            "total_records": total,
            "dominant": dominant,
            "baseline_mood": round(mood, 3),
            "negative_ratio": round(neg_ratio, 3),
            "volatile": volatility >= 0.18,
            "volatility": round(volatility, 3),
            "peak_slot": peak,
            "risk_count": risk_count,
            "trend": trend_text,
            "trend_diff": trend_diff,
            "distribution": lp.get("distribution", []),
        },
        "topics": topics,
        "calibration": {
            "count": calib_total,
            "recent": [{
                "original": c.original_emotion, "corrected": c.corrected_emotion,
                "text": c.text,
            } for c in calib_rows[:3]],
        },
        "summary": summary,
        "facts": facts,
    }


def build_prompt_card(db: Session, user_id: int, days: int = 90) -> str:
    """生成注入角色提示词的「用户画像卡」；无数据时返回空串。"""
    p = build_portrait(db, user_id, days)
    if not p or not p.get("basic"):
        return ""
    e = p["emotion"]
    lines = ["【用户画像卡（长期，帮助你记得 TA）】"]
    lines.append(f"- {p['basic']['stage']}：认识第 {p['basic']['joined_days']} 天，"
                 f"累计 {e['total_records']} 条情绪记录，连续记录 {p['basic']['streak_days']} 天")
    if e["total_records"]:
        lines.append(f"- 主导情绪：{e['dominant']}；负向占比 {round(e['negative_ratio'] * 100)}%；"
                     f"基线心情 {e['baseline_mood']}（0 低 - 1 高）")
        if e["volatile"]:
            lines.append("- 情绪起伏较大，安慰时语气要更稳、更慢")
        if e["peak_slot"]:
            lines.append(f"- 常在{e['peak_slot']}倾诉，可自然关心作息与睡眠")
        if e["trend"]:
            lines.append(f"- {e['trend']}")
    if p["topics"]:
        lines.append("- 最近反复提到：" + "、".join(f"{t['name']}（{t['count']}次）"
                                                  for t in p["topics"][:4]))
    if p["calibration"]["count"]:
        pairs = "；".join(f"「{c['text'][:10]}」原判{c['original']}→用户纠正为{c['corrected']}"
                         for c in p["calibration"]["recent"][:3])
        lines.append(f"- 校准偏好：{pairs}（说明用户的真实感受可能比字面更强烈/更平静，别照字面下判断）")
    if e["risk_count"]:
        lines.append(f"- 近 {days} 天有 {e['risk_count']} 次高强度负向记录：保持敏感，"
                     "必要时温和建议专业帮助（12356 / 就医），不说教不施压")
    lines.append("使用方式：像朋友一样在合适时机自然提及这些细节（如「你之前说加班很多」），"
                 "不要机械罗列，不要说「根据你的画像」这类话。")
    return "\n".join(lines)