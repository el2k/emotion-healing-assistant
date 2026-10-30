# -*- coding: utf-8 -*-
"""情绪档案服务：长周期画像、情绪波动、每日小结、AI 洞察、对话记忆上下文。"""
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

import httpx
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..models import ChatSession, EmotionCalibration, EmotionRecord, Message
from .. import personas

POSITIVE = {"喜悦", "平静", "感恩", "期待"}
NEGATIVE = {"悲伤", "焦虑", "愤怒", "恐惧", "孤独", "委屈", "低落"}
EMOTION_TYPES = ["喜悦", "平静", "感恩", "期待",
                 "悲伤", "焦虑", "愤怒", "恐惧", "孤独", "委屈", "低落", "中性"]


def polarity_of(emotion_type: str) -> int:
    if emotion_type in POSITIVE:
        return 1
    if emotion_type in NEGATIVE:
        return -1
    return 0


def apply_personal_calibration(db: Session, user_id: int, text: str,
                               emotion: dict) -> tuple[dict, dict | None]:
    """在模型/规则识别之后，用用户历史校准结果做个性化纠正。

    两条策略（都不完全依赖模型）：
      1) 相似原话：新消息与某条已校准的原话高度相似 → 采用用户当时校准的情绪。
      2) 纠正偏好：用户多次把「A」纠正成「B」→ 系统再判为 A 时，倾向采纳 B。
    返回 (调整后的情绪, 校准信息或None)。
    """
    cals = (db.query(EmotionCalibration)
            .filter(EmotionCalibration.user_id == user_id)
            .order_by(EmotionCalibration.created_at.desc())
            .limit(200).all())
    if not cals:
        return emotion, None

    pred = emotion.get("emotion_type", "中性")
    norm = (text or "").strip()

    # 1) 相似原话匹配
    best, best_ratio = None, 0.0
    if norm:
        for c in cals:
            if not c.text or not c.corrected_emotion:
                continue
            ratio = SequenceMatcher(None, norm, c.text).ratio()
            if ratio > best_ratio:
                best_ratio, best = ratio, c
    if best and best_ratio >= 0.82 and best.corrected_emotion != pred:
        return _override(emotion, best.corrected_emotion,
                         reason="similar", detail=f"与已校准原话相似度{int(best_ratio*100)}%",
                         ), {"reason": "similar", "to": best.corrected_emotion,
                             "original": pred}

    # 2) 纠正偏好
    pair = Counter(c.corrected_emotion for c in cals if c.original_emotion == pred)
    if pair:
        target, cnt = pair.most_common(1)[0]
        total = sum(pair.values())
        if target != pred and cnt >= 2 and cnt / total >= 0.6:
            return _override(emotion, target, reason="preference",
                             detail=f"你曾{cnt}次把「{pred}」校准为「{target}」",
                             ), {"reason": "preference", "to": target, "original": pred}

    return emotion, None


def _override(emotion: dict, new_type: str, reason: str, detail: str) -> dict:
    out = dict(emotion)
    out["emotion_type"] = new_type
    pol = polarity_of(new_type)
    out["polarity"] = "positive" if pol > 0 else ("negative" if pol < 0 else "neutral")
    out["source"] = "calibrated"
    # 校准后负向情绪保留一定安抚强度
    if pol < 0:
        out["heal_score"] = max(out.get("heal_score", 0.0), 0.45)
    else:
        out["heal_score"] = 0.0
    out["calibration"] = {"applied": True, "reason": reason,
                          "detail": detail, "original": emotion.get("emotion_type")}
    return out


def persona_breakdown(db: Session, user_id: int) -> dict:
    """角色陪伴与情绪的联动统计：和哪些角色聊得最多、各自记录了多少情绪。"""
    rows = (db.query(ChatSession.persona_id, func.count(ChatSession.id))
            .filter(ChatSession.user_id == user_id)
            .group_by(ChatSession.persona_id).all())
    total = sum(c for _, c in rows) or 0
    items = []
    for pid, cnt in sorted(rows, key=lambda x: -x[1]):
        p = personas.get(pid)
        if not p:
            continue
        emo = (db.query(func.count(EmotionRecord.id))
               .join(ChatSession, ChatSession.id == EmotionRecord.session_id)
               .filter(EmotionRecord.user_id == user_id, ChatSession.persona_id == pid)
               .scalar() or 0)
        items.append({
            "persona_id": pid, "name": p["name"], "emoji": p["emoji"],
            "sessions": cnt, "emotions": emo,
        })
    return {"total_sessions": total, "items": items[:10]}


def calibration_stats(db: Session, user_id: int) -> dict:
    """用户校准统计：总次数、纠正对、最近记录、个性化是否生效。"""
    cals = (db.query(EmotionCalibration)
            .filter(EmotionCalibration.user_id == user_id)
            .order_by(EmotionCalibration.created_at.desc())
            .all())
    total = len(cals)
    pairs = Counter((c.original_emotion, c.corrected_emotion) for c in cals)
    pair_list = [
        {"from": k[0], "to": k[1], "count": v}
        for k, v in pairs.most_common()
    ]
    recent = [
        {
            "time": _aware(c.created_at).strftime("%m-%d %H:%M"),
            "original": c.original_emotion,
            "corrected": c.corrected_emotion,
            "text": c.text,
        }
        for c in cals[:20]
    ]
    # 达到阈值即视为会个性化生效
    effective = any(1 for k, v in pairs.items() if k[0] != k[1] and v >= 2)
    note = ("你的个性化校准已生效，之后相似的表达会优先按你的习惯识别。"
            if effective else
            "继续校准同一类情绪 2 次以上，个性化识别就会开始生效。")
    return {
        "total": total,
        "pairs": pair_list,
        "recent": recent,
        "effective": effective,
        "note": note,
        "emotion_types": EMOTION_TYPES,
    }


def _now():
    return datetime.now(timezone.utc)


def _aware(dt):
    """SQLite 取出的 datetime 可能是 naive，统一补成 UTC aware。"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _empty_profile(days: int) -> dict:
    return {
        "days": days,
        "total_records": 0,
        "dominant_emotion": "中性",
        "positive_ratio": 0.0,
        "negative_ratio": 0.0,
        "avg_mood": 0.5,
        "distribution": [],
        "timeline": [],
        "heatmap": [],
        "events": [],
        "time_of_day": [],
        "streak_days": 0,
        "summary_text": "还没有足够的情绪记录，多和我聊聊，我就能慢慢读懂你啦。",
    }


def long_term_profile(db: Session, user_id: int, days: int = 90) -> dict:
    """长周期情绪画像（默认回溯 90 天，可传更长）。"""
    records = (db.query(EmotionRecord)
               .filter(EmotionRecord.user_id == user_id)
               .filter(EmotionRecord.created_at >= _now() - timedelta(days=days))
               .order_by(EmotionRecord.created_at.asc())
               .all())
    if not records:
        return _empty_profile(days)

    total = len(records)
    dist = Counter(r.emotion_type for r in records)
    pos = sum(1 for r in records if r.polarity > 0)
    neg = sum(1 for r in records if r.polarity < 0)

    # 心情值：正向=高、负向=低，加权平均（0~1）
    mood_vals = []
    for r in records:
        if r.polarity > 0:
            mood_vals.append(0.5 + 0.5 * min(1.0, r.score))
        elif r.polarity < 0:
            mood_vals.append(0.5 - 0.5 * min(1.0, r.score))
        else:
            mood_vals.append(0.5)
    avg_mood = round(sum(mood_vals) / len(mood_vals), 3)

    # 按天聚合：timeline（趋势）与 heatmap（日历热力）
    by_day = defaultdict(list)
    for r in records:
        d = _aware(r.created_at).strftime("%Y-%m-%d")
        by_day[d].append(r)
    timeline, heatmap = [], []
    for d in sorted(by_day):
        rs = by_day[d]
        day_mood = []
        for r in rs:
            if r.polarity > 0:
                day_mood.append(0.5 + 0.5 * min(1.0, r.score))
            elif r.polarity < 0:
                day_mood.append(0.5 - 0.5 * min(1.0, r.score))
            else:
                day_mood.append(0.5)
        avg = round(sum(day_mood) / len(day_mood), 3)
        timeline.append({"date": d, "mood": avg, "count": len(rs)})
        # 当日主导情绪
        top_emotion = Counter(r.emotion_type for r in rs).most_common(1)[0][0]
        heatmap.append({"date": d, "mood": avg, "count": len(rs), "emotion": top_emotion})

    # 情绪波动事件：负向且强度较高的记录，带触发原话
    neg_events = [r for r in records if r.polarity < 0]
    neg_events.sort(key=lambda r: (_aware(r.created_at)), reverse=True)
    events = []
    for r in neg_events[:30]:
        if r.trigger or r.score >= 0.5:
            events.append({
                "time": _aware(r.created_at).strftime("%m-%d %H:%M"),
                "emotion": r.emotion_type,
                "score": round(r.score, 2),
                "intent": r.intent or "",
                "trigger": r.trigger or "",
            })

    # 情绪波动的时段分布（一天中的哪个时段最易低落/开心）
    tod = Counter()
    for r in records:
        h = _aware(r.created_at).hour
        label = ("凌晨" if h < 6 else "早上" if h < 9 else "上午" if h < 12
                 else "中午" if h < 14 else "下午" if h < 18 else "傍晚" if h < 21 else "深夜")
        tod[label] += 1
    _order = ["凌晨", "早上", "上午", "中午", "下午", "傍晚", "深夜"]
    time_of_day = [{"slot": s, "count": tod[s]} for s in _order if tod[s] > 0]

    # 连续记录天数
    streak = _calc_streak(by_day)

    dominant = dist.most_common(1)[0][0]
    summary = _compose_summary(total, dominant, pos, neg, avg_mood, time_of_day)

    return {
        "days": days,
        "total_records": total,
        "dominant_emotion": dominant,
        "positive_ratio": round(pos / total, 3),
        "negative_ratio": round(neg / total, 3),
        "avg_mood": avg_mood,
        "distribution": [{"name": k, "value": v} for k, v in dist.most_common()],
        "timeline": timeline,
        "heatmap": heatmap,
        "events": events,
        "time_of_day": time_of_day,
        "streak_days": streak,
        "summary_text": summary,
    }


def _calc_streak(by_day: dict) -> int:
    """从今天往前，连续有记录的天数。"""
    streak = 0
    day = _now().date()
    keys = set(by_day.keys())
    for _ in range(366):
        if day.strftime("%Y-%m-%d") in keys:
            streak += 1
            day -= timedelta(days=1)
        else:
            break
    return streak


def _compose_summary(total, dominant, pos, neg, avg_mood, time_of_day) -> str:
    mood_desc = "整体挺明媚的" if avg_mood >= 0.6 else (
        "整体比较平稳" if avg_mood >= 0.45 else "最近有些低沉")
    peak = ""
    if time_of_day:
        peak = f"，在「{max(time_of_day, key=lambda x: x['count'])['slot']}」时段情绪记录最多"
    return (f"这段时间你一共记录了 {total} 次情绪，最常见的是「{dominant}」"
            f"，{mood_desc}{peak}。正向 {pos} 次、负向 {neg} 次，"
            f"记得温柔地对待每一个情绪的自己。")


def daily_summary(db: Session, user_id: int) -> dict:
    """今日情绪小结 + 每日推送文案。"""
    today = _now().date()
    start = datetime(today.year, today.month, today.day, tzinfo=timezone.utc)
    records = (db.query(EmotionRecord)
               .filter(EmotionRecord.user_id == user_id,
                       EmotionRecord.created_at >= start)
               .order_by(EmotionRecord.created_at.asc())
               .all())
    count = len(records)
    if count == 0:
        return {
            "date": today.strftime("%Y-%m-%d"),
            "count": 0,
            "dominant_emotion": "中性",
            "mood": 0.5,
            "push_text": "今天还没有记录情绪哦，有什么想说的都可以告诉我，我一直都在～",
            "tip": "试着说说今天最让你在意的一件小事吧。",
        }

    dist = Counter(r.emotion_type for r in records)
    dominant = dist.most_common(1)[0][0]
    mood_vals = []
    for r in records:
        if r.polarity > 0:
            mood_vals.append(0.5 + 0.5 * min(1.0, r.score))
        elif r.polarity < 0:
            mood_vals.append(0.5 - 0.5 * min(1.0, r.score))
        else:
            mood_vals.append(0.5)
    mood = round(sum(mood_vals) / len(mood_vals), 3)

    if mood >= 0.6:
        push = f"今天你整体是「{dominant}」的一天，愿这份好心情一直延续，记得奖励一下自己～"
        tip = "把今天的开心小事写下来，留作以后的小太阳。"
    elif mood >= 0.45:
        push = f"今天你记录了 {count} 次心情，以「{dominant}」为主，起伏中有稳，你已经做得很好啦。"
        tip = "睡前做几次深呼吸，让身体先放松下来。"
    else:
        push = f"今天似乎有些不容易，出现较多「{dominant}」。辛苦了，允许自己慢一点，我一直陪着你。"
        tip = "如果很难受，试着联系信任的人，或拨打心理援助热线 12356。"

    return {
        "date": today.strftime("%Y-%m-%d"),
        "count": count,
        "dominant_emotion": dominant,
        "mood": mood,
        "push_text": push,
        "tip": tip,
    }


async def insight(db: Session, user_id: int, days: int = 30) -> dict:
    """AI 情绪洞察（周报式分析）。配置大模型走 LLM，否则规则生成。"""
    profile = long_term_profile(db, user_id, days)
    if profile["total_records"] == 0:
        return {"text": "还没有足够的记录来生成洞察，我们多聊聊吧。", "source": "rule",
                "highlights": []}

    if settings.LLM_ENABLED and settings.LLM_API_KEY:
        text = await _llm_insight(profile)
        if text:
            return {"text": text, "source": "llm", "highlights": _highlights(profile)}

    return {"text": _rule_insight(profile), "source": "rule",
            "highlights": _highlights(profile)}


def _highlights(profile: dict) -> list[str]:
    hs = []
    hs.append(f"近 {profile['days']} 天共记录 {profile['total_records']} 次情绪")
    hs.append(f"最常见情绪：{profile['dominant_emotion']}")
    hs.append(f"平均心情指数：{profile['avg_mood']}")
    if profile["events"]:
        hs.append(f"最近一次较明显的低落：{profile['events'][0]['emotion']}（{profile['events'][0]['time']}）")
    return hs


def _rule_insight(profile: dict) -> str:
    mood = profile["avg_mood"]
    dom = profile["dominant_emotion"]
    neg = profile["negative_ratio"]
    tod = profile["time_of_day"]
    parts = [f"从近 {profile['days']} 天的记录看，你的情绪以「{dom}」为主。"]
    if mood >= 0.6:
        parts.append("整体心情偏积极，说明你在很好地照顾自己，继续保持这份节奏。")
    elif mood >= 0.45:
        parts.append("整体处于平稳区间，偶有起伏是正常的，不必苛责自己。")
    else:
        parts.append("近期负向情绪偏多，你可能正经历一段辛苦的时期，请记得你不必独自承受。")
    if neg >= 0.5:
        parts.append("负向情绪占比超过一半，建议多和信任的人聊聊，或尝试深呼吸、散步来释放压力。")
    if tod:
        peak = max(tod, key=lambda x: x["count"])["slot"]
        parts.append(f"你在「{peak}」时段记录最多，可以留意这个时间点前后的状态，给自己多留些缓冲。")
    if profile["events"]:
        e = profile["events"][0]
        if e["trigger"]:
            parts.append(f"最近让你比较在意的是「{e['trigger']}」这类事情，可以试着换个角度理解它。")
    parts.append("愿你被这个世界温柔以待，也别忘了先温柔地对待自己。")
    return "".join(parts)


async def _llm_insight(profile: dict) -> str | None:
    prompt = (
        "你是一位温柔的情绪分析师。请根据用户近期的情绪数据，写一段 120~200 字的个性化"
        "情绪洞察（口语化、有温度、给具体可执行的小建议，不说教）。数据如下：\n"
        f"记录天数范围：{profile['days']} 天；记录次数：{profile['total_records']}；"
        f"最常见情绪：{profile['dominant_emotion']}；正向占比：{profile['positive_ratio']}；"
        f"负向占比：{profile['negative_ratio']}；平均心情指数(0-1)：{profile['avg_mood']}；"
        f"时段分布：{profile['time_of_day']}；近期低落事件：{profile['events'][:3]}。"
    )
    url = f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {settings.LLM_API_KEY}"}
    payload = {"model": settings.LLM_MODEL,
               "messages": [{"role": "user", "content": prompt}],
               "temperature": 0.6}
    try:
        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


def build_memory_context(db: Session, user_id: int, session_id: int,
                         limit: int = 12) -> tuple[list[dict], str]:
    """构建多轮对话记忆：返回(最近消息历史, 用户长期画像摘要文本)。"""
    msgs = (db.query(Message)
            .filter(Message.session_id == session_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
            .all())
    msgs.reverse()
    history = [{"role": m.role, "content": m.content}
               for m in msgs if m.content]

    # 长期画像摘要（供 LLM 记得用户）
    recent = (db.query(EmotionRecord)
              .filter(EmotionRecord.user_id == user_id)
              .order_by(EmotionRecord.created_at.desc())
              .limit(40).all())
    profile_text = ""
    if recent:
        dist = Counter(r.emotion_type for r in recent)
        top = "、".join(f"{k}{v}次" for k, v in dist.most_common(3))
        neg = sum(1 for r in recent if r.polarity < 0)
        profile_text = (f"该用户近期情绪记录中，出现较多的是：{top}；"
                        f"近 40 条里负向情绪 {neg} 次。聊天时可自然体现你记得 TA 的状态。")
    return history, profile_text