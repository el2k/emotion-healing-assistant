# -*- coding: utf-8 -*-
"""管理后台路由：概览、用户、情绪、角色运营、社区审核、系统信息。"""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..config import BASE_DIR, settings
from ..database import get_db
from ..deps import get_current_user, require_admin
from ..models import (ChatSession, EmotionCalibration, EmotionRecord,
                      ForumComment, ForumLike, ForumPost, LLMModel, LLMUsageLog,
                      Message, User)
from .. import personas
from ..schemas import UserUpdateIn
from ..security import hash_password
from ..services import emotion_service
from ..observability import metrics, llm_breaker
from ..observability.drift import drift_report

APP_VERSION = "2.0.0"

router = APIRouter(prefix="/api/admin", tags=["admin"],
                   dependencies=[Depends(require_admin)])


# ============================================================
# 可观测性端点：指标、漂移检测、断路器
# ============================================================
@router.get("/observability/overview")
def observability_overview(db: Session = Depends(get_db)):
    """可观测性总览：请求指标 + LLM 指标 + 断路器 + 数据漂移 + 系统摘要。"""
    req_5m = metrics.request_summary(minutes=5)
    req_1h = metrics.request_summary(minutes=60)
    req_24h = metrics.request_summary(minutes=1440)
    llm_1h = metrics.llm_summary(minutes=60)
    lifetime = metrics.lifetime_summary()
    breaker = llm_breaker.status()

    # 深度健康（内联，避免循环导入）
    health_checks = {}
    try:
        from sqlalchemy import text as _text
        db.execute(_text("SELECT 1"))
        health_checks["database"] = {"status": "ok"}
    except Exception as e:
        health_checks["database"] = {"status": "fail", "message": str(e)[:80]}
    try:
        import shutil as _shutil
        _total, _used, _free = _shutil.disk_usage(Path(__file__).parent)
        _free_pct = _free / _total * 100
        health_checks["disk"] = {
            "status": "ok" if _free_pct > 10 else "warn",
            "message": f"剩余 {_free_pct:.0f}%",
        }
    except Exception:
        health_checks["disk"] = {"status": "unknown"}
    breaker_state = breaker.get("state", "closed")
    health_checks["llm_circuit"] = {
        "status": ("ok" if breaker_state == "closed" else
                    "degraded" if breaker_state == "half_open" else "fail"),
    }
    health = {"status": "ok" if all(c["status"] == "ok" for c in health_checks.values()) else "degraded",
              "checks": health_checks}

    # 漂移检测（可能耗时，放在最后）
    drift = drift_report(db)

    return {
        "request_metrics": {
            "last_5m": req_5m,
            "last_1h": req_1h,
            "last_24h": req_24h,
        },
        "llm_metrics": llm_1h,
        "llm_breaker": breaker,
        "drift": drift,
        "health": health,
        "lifetime": lifetime,
        "app_version": APP_VERSION,
    }


@router.get("/observability/metrics")
def observability_metrics(minutes: int = Query(60, ge=1, le=1440)):
    """按时间窗口查询请求指标。"""
    return {
        "window_minutes": minutes,
        "requests": metrics.request_summary(minutes),
        "llm": metrics.llm_summary(minutes),
        "lifetime": metrics.lifetime_summary(),
    }


@router.get("/observability/drift")
def observability_drift(db: Session = Depends(get_db)):
    """数据漂移检测报告。"""
    return drift_report(db)


@router.get("/observability/breaker")
def observability_breaker():
    """LLM 断路器状态。"""
    return llm_breaker.status()


@router.get("/observability/ratelimits")
def observability_ratelimits():
    """限流器状态（登录/注册/API 全局限流）。"""
    from ..security.rate_limit import login_limiter, register_limiter, api_limiter
    return {
        "login": login_limiter.status(),
        "register": register_limiter.status(),
        "api": api_limiter.status(),
    }


@router.post("/observability/breaker/reset")
def observability_breaker_reset():
    """手动重置 LLM 断路器（故障排除后恢复）。"""
    llm_breaker.reset()
    return {"ok": True, "message": "断路器已重置为 CLOSED"}


def _media_of(post: ForumPost) -> str:
    """取帖子首图（image_urls 或 blocks 里的第一张图/视频封面）。"""
    try:
        urls = json.loads(post.image_urls or "[]")
        if urls:
            return urls[0] if isinstance(urls[0], str) else ""
    except Exception:
        pass
    try:
        blocks = json.loads(post.blocks or "[]")
        for b in blocks:
            if isinstance(b, dict) and b.get("url"):
                return b["url"]
    except Exception:
        pass
    return ""


# ---------- 疗愈室数据 ----------
def _heal_personas() -> dict:
    """疗愈室专家：id -> 人设信息。"""
    return {p["id"]: p for p in personas.list_personas()
            if p["category"] == "心理疗愈室"}


@router.get("/heal")
def heal_overview(days: int = Query(90, ge=1, le=3650),
                  db: Session = Depends(get_db)):
    """疗愈室运营数据：总量、疾病方向分布、专家使用、高风险用户与最近会话。"""
    hp = _heal_personas()
    heal_ids = list(hp.keys())
    since = datetime.now(timezone.utc) - timedelta(days=days)

    if not heal_ids:
        return {"totals": {}, "by_target": [], "experts": [],
                "risk_users": [], "recent_risk": [], "recent_sessions": []}

    # 会话与消息
    sess = (db.query(ChatSession, User.nickname)
            .join(User, User.id == ChatSession.user_id)
            .filter(ChatSession.persona_id.in_(heal_ids))
            .order_by(ChatSession.updated_at.desc()))
    all_rows = sess.all()
    heal_session_ids = [s.id for s, _ in all_rows]
    msg_counts = {}
    if heal_session_ids:
        msg_counts = dict(db.query(Message.session_id, func.count(Message.id))
                          .filter(Message.session_id.in_(heal_session_ids))
                          .group_by(Message.session_id).all())

    # 各专家（疾病方向）统计
    by_persona_sess = dict(db.query(ChatSession.persona_id, func.count(ChatSession.id))
                           .filter(ChatSession.persona_id.in_(heal_ids))
                           .group_by(ChatSession.persona_id).all())
    by_persona_users = dict(
        db.query(ChatSession.persona_id, func.count(func.distinct(ChatSession.user_id)))
        .filter(ChatSession.persona_id.in_(heal_ids))
        .group_by(ChatSession.persona_id).all())
    by_persona_msgs = dict(
        db.query(ChatSession.persona_id, func.count(Message.id))
        .join(Message, Message.session_id == ChatSession.id)
        .filter(ChatSession.persona_id.in_(heal_ids))
        .group_by(ChatSession.persona_id).all())

    # 高风险情绪（疗愈室会话内，负向且强度≥0.7）
    risk_base = (db.query(EmotionRecord, ChatSession.persona_id)
                 .join(ChatSession, ChatSession.id == EmotionRecord.session_id)
                 .filter(ChatSession.persona_id.in_(heal_ids),
                         EmotionRecord.polarity < 0,
                         EmotionRecord.score >= 0.7))
    risk_rows = (risk_base.filter(EmotionRecord.created_at >= since)
                 .order_by(EmotionRecord.created_at.desc()).limit(30).all())
    risk_by_user = (risk_base.filter(EmotionRecord.created_at >= since)
                    .order_by(EmotionRecord.created_at.desc()).all())
    risk_by_persona = {}
    user_risk = {}
    for r, pid in risk_by_user:
        risk_by_persona[pid] = risk_by_persona.get(pid, 0) + 1
        u = user_risk.setdefault(r.user_id, {"user_id": r.user_id, "count": 0,
                                              "last": r.created_at, "targets": set()})
        u["count"] += 1
        u["targets"].add(pid)
        if r.created_at > u["last"]:
            u["last"] = r.created_at

    user_names = {}
    if user_risk:
        rows = (db.query(User.id, User.nickname, User.phone)
                .filter(User.id.in_(list(user_risk.keys()))).all())
        user_names = {r[0]: (r[1], r[2]) for r in rows}

    total_sessions = len(all_rows)
    total_messages = sum(msg_counts.get(sid, 0) for sid in heal_session_ids)
    total_users = len({s.user_id for s, _ in all_rows})
    heal_emotions = (db.query(func.count(EmotionRecord.id))
                     .join(ChatSession, ChatSession.id == EmotionRecord.session_id)
                     .filter(ChatSession.persona_id.in_(heal_ids),
                             EmotionRecord.created_at >= since).scalar() or 0)

    by_target = {}
    for pid, p in hp.items():
        t = p.get("heal_target") or p["name"]
        d = by_target.setdefault(t, {"target": t, "sessions": 0, "users": 0,
                                     "messages": 0, "high_risk": 0})
        d["sessions"] += by_persona_sess.get(pid, 0)
        d["users"] += by_persona_users.get(pid, 0)
        d["messages"] += by_persona_msgs.get(pid, 0)
        d["high_risk"] += risk_by_persona.get(pid, 0)
    by_target = sorted(by_target.values(), key=lambda x: -x["sessions"])

    experts = [{
        "persona_id": pid, "name": p["name"], "avatar": p.get("avatar", ""),
        "emoji": p["emoji"], "work": p["work"], "target": p.get("heal_target", ""),
        "sessions": by_persona_sess.get(pid, 0),
        "users": by_persona_users.get(pid, 0),
        "messages": by_persona_msgs.get(pid, 0),
        "high_risk": risk_by_persona.get(pid, 0),
    } for pid, p in hp.items()]
    experts.sort(key=lambda x: -x["sessions"])

    recent_risk = [{
        "user_id": r.user_id, "user": user_names.get(r.user_id, ("", ""))[0],
        "phone": user_names.get(r.user_id, ("", ""))[1],
        "target": hp.get(pid, {}).get("heal_target", ""),
        "expert": hp.get(pid, {}).get("name", ""),
        "emotion": r.emotion_type, "score": round(r.score, 2),
        "trigger": r.trigger or "", "intent": r.intent or "",
        "time": r.created_at.isoformat() if r.created_at else None,
    } for r, pid in risk_rows]

    recent_sessions = [{
        "id": s.id, "title": s.title, "user_id": s.user_id, "nickname": nickname,
        "persona_id": s.persona_id,
        "expert": hp.get(s.persona_id, {}).get("name", ""),
        "avatar": hp.get(s.persona_id, {}).get("avatar", ""),
        "target": hp.get(s.persona_id, {}).get("heal_target", ""),
        "messages": msg_counts.get(s.id, 0),
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    } for s, nickname in all_rows[:15]]

    return {
        "totals": {
            "sessions": total_sessions,
            "users": total_users,
            "messages": total_messages,
            "emotions": heal_emotions,
            "high_risk": len(risk_by_user),
        },
        "by_target": by_target,
        "experts": experts,
        "risk_users": [{
            "user_id": uid, "nickname": user_names.get(uid, ("", ""))[0],
            "phone": user_names.get(uid, ("", ""))[1],
            "count": u["count"],
            "targets": "/".join(hp.get(t, {}).get("heal_target", t) for t in u["targets"]),
            "last": u["last"].isoformat() if u["last"] else None,
        } for uid, u in sorted(user_risk.items(), key=lambda kv: -kv[1]["count"])[:10]],
        "recent_risk": recent_risk,
        "recent_sessions": recent_sessions,
    }


# ---------- 用户管理 ----------
@router.get("/users")
def list_users(q: str = "", page: int = Query(1, ge=1),
               page_size: int = Query(50, ge=1, le=200),
               db: Session = Depends(get_db)):
    query = db.query(User)
    if q.strip():
        kw = f"%{q.strip()}%"
        query = query.filter(or_(User.phone.like(kw), User.nickname.like(kw)))
    total = query.count()
    users = (query.order_by(User.created_at.desc())
             .offset((page - 1) * page_size).limit(page_size).all())
    ids = [u.id for u in users]
    sess_rows, msg_rows, last_rows = {}, {}, {}
    if ids:
        sess_rows = dict(db.query(ChatSession.user_id, func.count(ChatSession.id))
                         .filter(ChatSession.user_id.in_(ids))
                         .group_by(ChatSession.user_id).all())
        msg_rows = dict(db.query(ChatSession.user_id, func.count(Message.id))
                        .join(Message, Message.session_id == ChatSession.id)
                        .filter(ChatSession.user_id.in_(ids))
                        .group_by(ChatSession.user_id).all())
        last_rows = dict(db.query(EmotionRecord.user_id, func.max(EmotionRecord.created_at))
                         .filter(EmotionRecord.user_id.in_(ids))
                         .group_by(EmotionRecord.user_id).all())
    return {
        "total": total,
        "items": [
            {
                "id": u.id, "phone": u.phone, "nickname": u.nickname, "role": u.role,
                "avatar": u.avatar or "", "is_active": u.is_active,
                "points": u.points or 0,
                "sessions": sess_rows.get(u.id, 0),
                "messages": msg_rows.get(u.id, 0),
                "last_active": (last_rows.get(u.id).isoformat()
                                if last_rows.get(u.id) else None),
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ],
    }


@router.put("/users/{user_id}")
def update_user(user_id: int, data: UserUpdateIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "用户不存在")
    if data.nickname is not None:
        user.nickname = data.nickname
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.password:
        user.password_hash = hash_password(data.password)
    db.commit()
    return {"ok": True}


@router.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "用户不存在")
    if user.role == "admin":
        raise HTTPException(400, "不能删除管理员账号")
    # 会话及其消息
    sess_ids = [r[0] for r in db.query(ChatSession.id)
                .filter(ChatSession.user_id == user_id).all()]
    if sess_ids:
        db.query(Message).filter(Message.session_id.in_(sess_ids)).delete(
            synchronize_session=False)
    db.query(ChatSession).filter(ChatSession.user_id == user_id).delete(
        synchronize_session=False)
    # 情绪与校准
    db.query(EmotionRecord).filter(EmotionRecord.user_id == user_id).delete(
        synchronize_session=False)
    db.query(EmotionCalibration).filter(
        EmotionCalibration.user_id == user_id).delete(synchronize_session=False)
    # 社区内容
    post_ids = [r[0] for r in db.query(ForumPost.id)
                .filter(ForumPost.user_id == user_id).all()]
    if post_ids:
        db.query(ForumLike).filter(ForumLike.post_id.in_(post_ids)).delete(
            synchronize_session=False)
        db.query(ForumComment).filter(ForumComment.post_id.in_(post_ids)).delete(
            synchronize_session=False)
        db.query(ForumPost).filter(ForumPost.id.in_(post_ids)).delete(
            synchronize_session=False)
    db.query(ForumLike).filter(ForumLike.user_id == user_id).delete(
        synchronize_session=False)
    db.query(ForumComment).filter(ForumComment.user_id == user_id).delete(
        synchronize_session=False)
    db.delete(user)
    db.commit()
    return {"ok": True}


@router.get("/users/{user_id}/profile")
def user_profile(user_id: int, days: int = Query(90, ge=1, le=3650),
                 db: Session = Depends(get_db)):
    """管理员查看某用户的长周期情绪画像。"""
    if not db.query(User).filter(User.id == user_id).first():
        raise HTTPException(404, "用户不存在")
    return emotion_service.long_term_profile(db, user_id, days)


class PointsAdjustIn(BaseModel):
    delta: int
    reason: str = "admin_adjust"


@router.post("/users/{user_id}/points")
def adjust_points(user_id: int, data: PointsAdjustIn,
                  db: Session = Depends(get_db)):
    """管理员调整用户积分（正数加、负数扣）。"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "用户不存在")
    from .points import add_points
    balance = add_points(db, user, data.delta, "admin_adjust", data.reason)
    return {"ok": True, "balance": balance}


# ---------- 情绪档案 ----------
@router.get("/emotions")
def list_emotions(
    user_id: int | None = Query(None),
    days: int = Query(7, ge=1, le=365),
    db: Session = Depends(get_db),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    q = db.query(EmotionRecord).filter(EmotionRecord.created_at >= since)
    if user_id:
        q = q.filter(EmotionRecord.user_id == user_id)
    rows = q.order_by(EmotionRecord.created_at.desc()).limit(2000).all()
    return [
        {
            "id": r.id, "user_id": r.user_id, "emotion_type": r.emotion_type,
            "score": r.score, "polarity": r.polarity, "source": r.source,
            "intent": r.intent or "", "trigger": r.trigger or "",
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


# ---------- 统计报表 ----------
@router.get("/stats")
def stats(
    days: int = Query(7, ge=1, le=365),
    db: Session = Depends(get_db),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)

    total_users = db.query(func.count(User.id)).scalar()
    active_sessions = db.query(func.count(ChatSession.id)).scalar()
    total_messages = db.query(func.count(Message.id)).scalar()
    risk_count = (db.query(func.count(EmotionRecord.id))
                  .filter(EmotionRecord.created_at >= since,
                          EmotionRecord.polarity < 0,
                          EmotionRecord.score >= 0.7).scalar())

    # 情绪分布（统计周期内）
    dist_rows = (db.query(EmotionRecord.emotion_type, func.count(EmotionRecord.id))
                 .filter(EmotionRecord.created_at >= since)
                 .group_by(EmotionRecord.emotion_type)
                 .all())
    emotion_dist = [{"name": k, "value": v} for k, v in dist_rows]

    # 情绪随时间变化（按天汇总平均 score）
    trend_rows = (db.query(
                     func.date(EmotionRecord.created_at),
                     func.avg(EmotionRecord.score))
                  .filter(EmotionRecord.created_at >= since)
                  .group_by(func.date(EmotionRecord.created_at))
                  .order_by(func.date(EmotionRecord.created_at))
                  .all())
    trend = [{"date": str(d), "avg_score": round(float(a), 3)} for d, a in trend_rows]

    # 高风险用户 TOP
    risk_users = (
        db.query(User.id, User.nickname, User.phone, func.count(EmotionRecord.id))
        .join(EmotionRecord, EmotionRecord.user_id == User.id)
        .filter(EmotionRecord.created_at >= since,
                EmotionRecord.polarity < 0, EmotionRecord.score >= 0.7)
        .group_by(User.id)
        .order_by(func.count(EmotionRecord.id).desc())
        .limit(10)
        .all())
    risk_users = [
        {"user_id": uid, "nickname": nick, "phone": ph, "count": cnt}
        for uid, nick, ph, cnt in risk_users
    ]

    return {
        "totals": {
            "users": total_users,
            "sessions": active_sessions,
            "messages": total_messages,
            "high_risk": risk_count,
            "posts": db.query(func.count(ForumPost.id)).scalar() or 0,
            "likes": db.query(func.count(ForumLike.id)).scalar() or 0,
            "comments": db.query(func.count(ForumComment.id)).scalar() or 0,
            "calibrations": db.query(func.count(EmotionCalibration.id)).scalar() or 0,
        },
        "emotion_distribution": emotion_dist,
        "emotion_trend": trend,
        "risk_users": risk_users,
    }


@router.get("/personas")
def persona_usage(db: Session = Depends(get_db)):
    """角色使用数据：各角色的会话数、消息数、记录的情绪数。"""
    sess_rows = dict(db.query(ChatSession.persona_id, func.count(ChatSession.id))
                     .group_by(ChatSession.persona_id).all())
    msg_rows = dict(db.query(ChatSession.persona_id, func.count(Message.id))
                    .join(Message, Message.session_id == ChatSession.id)
                    .group_by(ChatSession.persona_id).all())
    emo_rows = dict(db.query(ChatSession.persona_id, func.count(EmotionRecord.id))
                    .join(ChatSession, ChatSession.id == EmotionRecord.session_id)
                    .group_by(ChatSession.persona_id).all())
    out = []
    for p in personas.list_personas():
        pid = p["id"]
        out.append({
            "persona_id": pid, "name": p["name"], "emoji": p["emoji"],
            "avatar": p.get("avatar", ""),
            "category": p["category"], "work": p["work"],
            "tagline": p.get("tag", ""), "desc": p.get("desc", ""),
            "heal_target": p.get("heal_target", ""),
            "sessions": sess_rows.get(pid, 0),
            "messages": msg_rows.get(pid, 0),
            "emotions": emo_rows.get(pid, 0),
        })
    out.sort(key=lambda x: (-x["sessions"], -x["messages"]))
    return out


@router.get("/forum")
def forum_stats(db: Session = Depends(get_db)):
    """论坛数据概览：总量、热门标签、热门帖子。"""
    posts = db.query(func.count(ForumPost.id)).scalar() or 0
    likes = db.query(func.count(ForumLike.id)).scalar() or 0
    comments = db.query(func.count(ForumComment.id)).scalar() or 0

    # 热门标签
    from collections import Counter
    tag_counter = Counter()
    for (tags,) in db.query(ForumPost.tags).all():
        for t in (tags or "").split(","):
            if t.strip():
                tag_counter[t.strip()] += 1
    hot_tags = [{"name": k, "count": v} for k, v in tag_counter.most_common(10)]

    # 热门帖子（按点赞数）
    like_counts = dict(db.query(ForumLike.post_id, func.count(ForumLike.id))
                       .group_by(ForumLike.post_id).all())
    top = (db.query(ForumPost, User.nickname)
           .join(User, User.id == ForumPost.user_id)
           .order_by(ForumPost.created_at.desc()).limit(50).all())
    top_posts = [
        {"id": p.id, "title": p.title or "无标题", "author": nick,
         "likes": like_counts.get(p.id, 0)}
        for p, nick in top
    ]
    top_posts.sort(key=lambda x: -x["likes"])
    top_posts = top_posts[:8]

    return {
        "totals": {"posts": posts, "likes": likes, "comments": comments},
        "hot_tags": hot_tags,
        "top_posts": top_posts,
    }


# 后台看到的会话明细（管理员可抽查）
@router.get("/sessions")
def all_sessions(q: str = "", page: int = Query(1, ge=1),
                 page_size: int = Query(50, ge=1, le=200),
                 db: Session = Depends(get_db)):
    query = (db.query(ChatSession, User.nickname)
             .join(User, User.id == ChatSession.user_id))
    if q.strip():
        kw = f"%{q.strip()}%"
        query = query.filter(or_(ChatSession.title.like(kw), User.nickname.like(kw)))
    total = query.count()
    rows = (query.order_by(ChatSession.updated_at.desc())
            .offset((page - 1) * page_size).limit(page_size).all())
    ids = [s.id for s, _ in rows]
    msg_counts = {}
    if ids:
        msg_counts = dict(db.query(Message.session_id, func.count(Message.id))
                          .filter(Message.session_id.in_(ids))
                          .group_by(Message.session_id).all())
    pmap = {p["id"]: p for p in personas.list_personas()}
    return {
        "total": total,
        "items": [
            {
                "id": s.id, "title": s.title, "user_id": s.user_id, "nickname": nickname,
                "persona_id": s.persona_id,
                "persona_name": pmap.get(s.persona_id, {}).get("name", "小窝"),
                "persona_avatar": pmap.get(s.persona_id, {}).get("avatar", ""),
                "messages": msg_counts.get(s.id, 0),
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            }
            for s, nickname in rows
        ],
    }


# ---------- 概览看板 ----------
@router.get("/overview")
def overview(days: int = Query(7, ge=1, le=90), db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days - 1)
    today = now.date().isoformat()

    def _by_day(rows):
        return {str(d): int(v) for d, v in rows if d}

    msg_rows = _by_day(db.query(func.date(Message.created_at), func.count(Message.id))
                       .filter(Message.created_at >= since)
                       .group_by(func.date(Message.created_at)).all())
    user_rows = _by_day(db.query(func.date(Message.created_at),
                                 func.count(func.distinct(ChatSession.user_id)))
                        .join(ChatSession, ChatSession.id == Message.session_id)
                        .filter(Message.created_at >= since)
                        .group_by(func.date(Message.created_at)).all())
    new_user_rows = _by_day(db.query(func.date(User.created_at), func.count(User.id))
                            .filter(User.created_at >= since)
                            .group_by(func.date(User.created_at)).all())
    emotion_rows = _by_day(db.query(func.date(EmotionRecord.created_at),
                                    func.count(EmotionRecord.id))
                           .filter(EmotionRecord.created_at >= since)
                           .group_by(func.date(EmotionRecord.created_at)).all())

    series = []
    for i in range(days):
        d = (since + timedelta(days=i)).date().isoformat()
        series.append({
            "date": d,
            "messages": msg_rows.get(d, 0),
            "active_users": user_rows.get(d, 0),
            "new_users": new_user_rows.get(d, 0),
            "emotions": emotion_rows.get(d, 0),
        })

    dist_rows = (db.query(EmotionRecord.emotion_type, func.count(EmotionRecord.id))
                 .filter(EmotionRecord.created_at >= since)
                 .group_by(EmotionRecord.emotion_type).all())
    dist = sorted([{"name": k, "value": v} for k, v in dist_rows],
                  key=lambda x: -x["value"])

    risk_users = (
        db.query(User.id, User.nickname, User.phone, func.count(EmotionRecord.id))
        .join(EmotionRecord, EmotionRecord.user_id == User.id)
        .filter(EmotionRecord.created_at >= since,
                EmotionRecord.polarity < 0, EmotionRecord.score >= 0.7)
        .group_by(User.id)
        .order_by(func.count(EmotionRecord.id).desc())
        .limit(8).all())

    sess_rows = dict(db.query(ChatSession.persona_id, func.count(ChatSession.id))
                     .group_by(ChatSession.persona_id).all())
    pmap = {p["id"]: p for p in personas.list_personas()}
    personas_top = sorted(
        [{"id": pid, "name": pmap.get(pid, {}).get("name", pid),
          "avatar": pmap.get(pid, {}).get("avatar", ""),
          "emoji": pmap.get(pid, {}).get("emoji", "🎭"),
          "sessions": cnt} for pid, cnt in sess_rows.items()],
        key=lambda x: -x["sessions"])[:6]

    recent_users = (db.query(User).order_by(User.created_at.desc()).limit(6).all())

    return {
        "totals": {
            "users": db.query(func.count(User.id)).scalar() or 0,
            "sessions": db.query(func.count(ChatSession.id)).scalar() or 0,
            "messages": db.query(func.count(Message.id)).scalar() or 0,
            "emotions": db.query(func.count(EmotionRecord.id)).scalar() or 0,
            "posts": db.query(func.count(ForumPost.id)).scalar() or 0,
            "likes": db.query(func.count(ForumLike.id)).scalar() or 0,
            "comments": db.query(func.count(ForumComment.id)).scalar() or 0,
            "calibrations": db.query(func.count(EmotionCalibration.id)).scalar() or 0,
            "high_risk": db.query(func.count(EmotionRecord.id))
            .filter(EmotionRecord.created_at >= since, EmotionRecord.polarity < 0,
                    EmotionRecord.score >= 0.7).scalar() or 0,
        },
        "today": {
            "new_users": new_user_rows.get(today, 0),
            "messages": msg_rows.get(today, 0),
            "active_users": user_rows.get(today, 0),
        },
        "series": series,
        "emotion_distribution": dist,
        "risk_users": [{"user_id": u, "nickname": n, "phone": p, "count": c}
                       for u, n, p, c in risk_users],
        "personas_top": personas_top,
        "recent_users": [
            {"id": u.id, "nickname": u.nickname, "phone": u.phone,
             "avatar": u.avatar or "", "role": u.role,
             "created_at": u.created_at.isoformat() if u.created_at else None}
            for u in recent_users
        ],
        "system": {
            "llm": settings.LLM_ENABLED,
            "model": settings.LLM_MODEL if settings.LLM_ENABLED else "本地规则引擎",
            "version": APP_VERSION,
        },
    }


# ---------- 社区内容审核 ----------
@router.get("/posts")
def admin_posts(q: str = "", page: int = Query(1, ge=1),
                page_size: int = Query(20, ge=1, le=100),
                db: Session = Depends(get_db)):
    query = (db.query(ForumPost, User.nickname, User.avatar)
             .join(User, User.id == ForumPost.user_id))
    if q.strip():
        kw = f"%{q.strip()}%"
        query = query.filter(or_(ForumPost.title.like(kw), ForumPost.content.like(kw)))
    total = query.count()
    rows = (query.order_by(ForumPost.created_at.desc())
            .offset((page - 1) * page_size).limit(page_size).all())
    ids = [p.id for p, _, _ in rows]
    like_counts, comment_counts = {}, {}
    if ids:
        like_counts = dict(db.query(ForumLike.post_id, func.count(ForumLike.id))
                           .filter(ForumLike.post_id.in_(ids))
                           .group_by(ForumLike.post_id).all())
        comment_counts = dict(db.query(ForumComment.post_id, func.count(ForumComment.id))
                              .filter(ForumComment.post_id.in_(ids))
                              .group_by(ForumComment.post_id).all())
    items = []
    for p, nickname, avatar in rows:
        text = (p.content or "").strip().replace("\n", " ")
        items.append({
            "id": p.id, "title": p.title or "无标题", "tags": p.tags or "",
            "excerpt": text[:80] + ("…" if len(text) > 80 else ""),
            "cover": _media_of(p), "author": nickname, "author_avatar": avatar or "",
            "likes": like_counts.get(p.id, 0),
            "comments": comment_counts.get(p.id, 0),
            "created_at": p.created_at.isoformat() if p.created_at else None,
        })
    return {"total": total, "items": items}


@router.delete("/posts/{post_id}")
def admin_delete_post(post_id: int, db: Session = Depends(get_db)):
    post = db.query(ForumPost).filter(ForumPost.id == post_id).first()
    if not post:
        raise HTTPException(404, "帖子不存在")
    db.query(ForumLike).filter(ForumLike.post_id == post_id).delete()
    db.query(ForumComment).filter(ForumComment.post_id == post_id).delete()
    db.delete(post)
    db.commit()
    return {"ok": True}


@router.get("/comments")
def admin_comments(q: str = "", page: int = Query(1, ge=1),
                   page_size: int = Query(20, ge=1, le=100),
                   db: Session = Depends(get_db)):
    query = (db.query(ForumComment, User.nickname, ForumPost.title)
             .join(User, User.id == ForumComment.user_id)
             .join(ForumPost, ForumPost.id == ForumComment.post_id))
    if q.strip():
        query = query.filter(ForumComment.content.like(f"%{q.strip()}%"))
    total = query.count()
    rows = (query.order_by(ForumComment.created_at.desc())
            .offset((page - 1) * page_size).limit(page_size).all())
    return {
        "total": total,
        "items": [
            {"id": c.id, "post_id": c.post_id, "post_title": title or "无标题",
             "author": nickname, "content": c.content,
             "created_at": c.created_at.isoformat() if c.created_at else None}
            for c, nickname, title in rows
        ],
    }


@router.delete("/comments/{comment_id}")
def admin_delete_comment(comment_id: int, db: Session = Depends(get_db)):
    c = db.query(ForumComment).filter(ForumComment.id == comment_id).first()
    if not c:
        raise HTTPException(404, "评论不存在")
    db.delete(c)
    db.commit()
    return {"ok": True}


# ---------- 系统信息 ----------
def _dir_size(path: Path) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    total, files = 0, 0
    for root, _, names in os.walk(path):
        for n in names:
            fp = Path(root) / n
            try:
                total += fp.stat().st_size
                files += 1
            except OSError:
                pass
    return total, files


@router.get("/system")
def system_info(db: Session = Depends(get_db)):
    db_path = settings.DB_PATH
    if db_path.startswith("sqlite:///"):
        db_path = db_path.replace("sqlite:///", "")
    db_file = Path(db_path)
    upload_bytes, upload_files = _dir_size(BASE_DIR / "uploads")
    return {
        "app": settings.APP_NAME,
        "version": APP_VERSION,
        "debug": settings.DEBUG,
        "db": {
            "path": str(db_file),
            "size_mb": round(db_file.stat().st_size / 1024 / 1024, 2)
            if db_file.exists() else 0,
        },
        "uploads": {
            "files": upload_files,
            "size_mb": round(upload_bytes / 1024 / 1024, 2),
        },
        "llm": {
            "enabled": settings.LLM_ENABLED,
            "model": settings.LLM_MODEL,
            "base_url": settings.LLM_BASE_URL,
            "has_key": bool(settings.LLM_API_KEY),
        },
        "counts": {
            "users": db.query(func.count(User.id)).scalar() or 0,
            "sessions": db.query(func.count(ChatSession.id)).scalar() or 0,
            "messages": db.query(func.count(Message.id)).scalar() or 0,
            "emotions": db.query(func.count(EmotionRecord.id)).scalar() or 0,
            "posts": db.query(func.count(ForumPost.id)).scalar() or 0,
            "personas": len(personas.list_personas()),
        },
    }


# ============================================================
# LLM 模型管理与 token 用量统计
# ============================================================
class LLMModelIn(BaseModel):
    model_id: str
    display_name: str = ""
    description: str = ""
    free_quota_tokens: int = 0
    enabled: bool = True
    is_default: bool = False
    sort_order: int = 0


class LLMModelUpdateIn(BaseModel):
    display_name: str | None = None
    description: str | None = None
    free_quota_tokens: int | None = None
    enabled: bool | None = None
    is_default: bool | None = None
    sort_order: int | None = None


def _today_start_utc():
    """UTC 今日零点（与 created_at 的 utcnow 对齐）。"""
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


def _model_stats(db: Session, model_id: str) -> dict:
    used_total = (db.query(func.coalesce(func.sum(LLMUsageLog.total_tokens), 0))
                  .filter(LLMUsageLog.model == model_id).scalar() or 0)
    today = _today_start_utc()
    used_today = (db.query(func.coalesce(func.sum(LLMUsageLog.total_tokens), 0))
                  .filter(LLMUsageLog.model == model_id,
                          LLMUsageLog.created_at >= today).scalar() or 0)
    calls_today = (db.query(func.count(LLMUsageLog.id))
                   .filter(LLMUsageLog.model == model_id,
                           LLMUsageLog.created_at >= today).scalar() or 0)
    calls_total = (db.query(func.count(LLMUsageLog.id))
                   .filter(LLMUsageLog.model == model_id).scalar() or 0)
    last_used = (db.query(func.max(LLMUsageLog.created_at))
                 .filter(LLMUsageLog.model == model_id).scalar())
    return {
        "used_total": int(used_total),
        "used_today": int(used_today),
        "calls_today": int(calls_today),
        "calls_total": int(calls_total),
        "last_used_at": (last_used.replace(tzinfo=timezone.utc).isoformat()
                         if last_used else None),
    }


@router.get("/llm/models")
def llm_models_overview(db: Session = Depends(get_db)):
    """模型配置列表 + 每模型 token 额度/已用/剩余/今日消耗 + 全局汇总。"""
    rows = db.query(LLMModel).order_by(LLMModel.sort_order, LLMModel.id).all()
    out = []
    for m in rows:
        st = _model_stats(db, m.model_id)
        quota = int(m.free_quota_tokens or 0)
        out.append({
            "id": m.id, "model_id": m.model_id,
            "display_name": m.display_name or m.model_id,
            "description": m.description or "",
            "enabled": bool(m.enabled), "is_default": bool(m.is_default),
            "free_quota_tokens": quota,
            "remaining": max(0, quota - st["used_total"]) if quota > 0 else None,
            "sort_order": m.sort_order or 0,
            **st,
        })
    today = _today_start_utc()
    total_tokens_today = (db.query(func.coalesce(func.sum(LLMUsageLog.total_tokens), 0))
                         .filter(LLMUsageLog.created_at >= today).scalar() or 0)
    calls_today = (db.query(func.count(LLMUsageLog.id))
                   .filter(LLMUsageLog.created_at >= today).scalar() or 0)
    total_tokens = (db.query(func.coalesce(func.sum(LLMUsageLog.total_tokens), 0))
                    .scalar() or 0)
    return {
        "models": out,
        "summary": {
            "enabled_models": sum(1 for m in out if m["enabled"]),
            "total_models": len(out),
            "tokens_today": int(total_tokens_today),
            "calls_today": int(calls_today),
            "tokens_total": int(total_tokens),
        },
    }


@router.post("/llm/models")
def create_llm_model(data: LLMModelIn, db: Session = Depends(get_db)):
    """新增可选模型。"""
    mid = data.model_id.strip()
    if not mid:
        raise HTTPException(400, "模型 ID 不能为空")
    if db.query(LLMModel).filter(LLMModel.model_id == mid).first():
        raise HTTPException(400, "该模型已存在")
    m = LLMModel(model_id=mid, display_name=data.display_name or mid,
                 description=data.description,
                 free_quota_tokens=max(0, data.free_quota_tokens),
                 enabled=data.enabled, is_default=False,
                 sort_order=data.sort_order)
    db.add(m)
    db.flush()
    if data.is_default:
        _set_default(db, m)
    db.commit()
    db.refresh(m)
    return {"id": m.id, "model_id": m.model_id}


def _set_default(db: Session, target: LLMModel) -> None:
    db.query(LLMModel).update({LLMModel.is_default: False})
    target.is_default = True
    target.enabled = True


@router.put("/llm/models/{model_pk}")
def update_llm_model(model_pk: int, data: LLMModelUpdateIn,
                     db: Session = Depends(get_db)):
    m = db.query(LLMModel).filter(LLMModel.id == model_pk).first()
    if not m:
        raise HTTPException(404, "模型不存在")
    if data.display_name is not None:
        m.display_name = data.display_name
    if data.description is not None:
        m.description = data.description
    if data.free_quota_tokens is not None:
        m.free_quota_tokens = max(0, data.free_quota_tokens)
    if data.sort_order is not None:
        m.sort_order = data.sort_order
    if data.enabled is not None:
        if not data.enabled and m.is_default:
            raise HTTPException(400, "默认模型不能停用，请先切换默认模型")
        m.enabled = data.enabled
    if data.is_default:
        _set_default(db, m)
    db.commit()
    return {"ok": True}


@router.delete("/llm/models/{model_pk}")
def delete_llm_model(model_pk: int, db: Session = Depends(get_db)):
    m = db.query(LLMModel).filter(LLMModel.id == model_pk).first()
    if not m:
        raise HTTPException(404, "模型不存在")
    if m.is_default:
        raise HTTPException(400, "默认模型不能删除，请先切换默认模型")
    db.delete(m)
    db.commit()
    return {"ok": True}


@router.get("/llm/usage")
def llm_usage_stats(days: int = Query(7, ge=1, le=90),
                    db: Session = Depends(get_db)):
    """token 用量：按天趋势 + 按模型汇总 + 最近记录。"""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    day_rows = (db.query(func.date(LLMUsageLog.created_at).label("d"),
                         func.coalesce(func.sum(LLMUsageLog.total_tokens), 0),
                         func.count(LLMUsageLog.id))
                .filter(LLMUsageLog.created_at >= since)
                .group_by("d").order_by("d").all())
    by_day = [{"date": str(r[0]), "tokens": int(r[1]), "calls": int(r[2])}
              for r in day_rows]
    model_rows = (db.query(LLMUsageLog.model,
                           func.coalesce(func.sum(LLMUsageLog.total_tokens), 0),
                           func.count(LLMUsageLog.id))
                  .filter(LLMUsageLog.created_at >= since)
                  .group_by(LLMUsageLog.model)
                  .order_by(func.sum(LLMUsageLog.total_tokens).desc()).all())
    by_model = [{"model": r[0], "tokens": int(r[1]), "calls": int(r[2])}
                for r in model_rows]
    recent_rows = (db.query(LLMUsageLog)
                   .order_by(LLMUsageLog.id.desc()).limit(50).all())
    recent = [{
        "id": r.id, "user_id": r.user_id, "model": r.model, "scene": r.scene,
        "total_tokens": r.total_tokens, "success": bool(r.success),
        "created_at": (r.created_at.replace(tzinfo=timezone.utc).isoformat()
                       if r.created_at else None),
    } for r in recent_rows]
    return {"days": days, "by_day": by_day, "by_model": by_model, "recent": recent}


# ============================================================
# 提示词管理：角色卡外置 markdown（在线编辑 / 预览 / 备份恢复）
# ============================================================
class PersonaPromptPatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")   # 传入不可编辑字段（如 id）直接 422

    name: str | None = None
    emoji: str | None = None
    tag: str | None = None
    desc: str | None = None
    color: str | None = None
    personality: str | None = None
    speech: str | None = None
    catchphrases: list[str] | None = None
    cares: str | None = None
    voice: dict[str, list[str]] | None = None


class PromptSourceIn(BaseModel):
    text: str = Field(..., min_length=10)


class PromptPreviewIn(BaseModel):
    persona_id: str = "nuan"
    patch: dict = {}


class PromptRestoreIn(BaseModel):
    filename: str


@router.get("/prompts/overview")
def prompts_overview():
    """提示词管理总览：源文件信息 + 安全守则（只读）+ 备份列表 + 角色索引。"""
    src = personas.get_prompt_source()
    return {
        "file": {"path": src["path"], "updated_at": src["updated_at"],
                 "personas": src["personas"], "source_mode": personas._SOURCE_MODE},
        "guards": personas.guards_text(),
        "backups": personas.list_prompt_backups()[:20],
        "personas": [{"id": p["id"], "name": p["name"], "emoji": p.get("emoji", ""),
                      "category": p["category"], "tag": p.get("tag", ""),
                      "heal_target": p.get("heal_target", "")}
                     for p in personas.PERSONAS],
    }


@router.get("/prompts/source")
def prompts_source():
    """Markdown 源文件全文。"""
    src = personas.get_prompt_source()
    return {"text": src["text"], "path": src["path"], "updated_at": src["updated_at"]}


@router.put("/prompts/source")
def prompts_source_save(data: PromptSourceIn):
    """Markdown 全文保存：校验 → 备份 → 写盘 → 热重载（立即生效，无需重启）。"""
    try:
        return personas.save_prompt_source(data.text)
    except ValueError as e:
        raise HTTPException(400, f"保存被拒绝：{e}")


@router.get("/prompts/persona/{pid}/markdown")
def persona_markdown(pid: str):
    """单个角色的 Markdown 源码块（供「左编辑 / 右实时渲染」的单角色编辑器）。"""
    try:
        return personas.get_persona_markdown(pid)
    except KeyError:
        raise HTTPException(404, "角色不存在")


class PersonaMarkdownIn(BaseModel):
    markdown: str = Field(..., min_length=10)


@router.put("/prompts/persona/{pid}/markdown")
def persona_markdown_save(pid: str, data: PersonaMarkdownIn):
    """保存单个角色的 Markdown 块：校验 → 备份 → 写盘 → 热重载（id/技术字段不可变）。"""
    try:
        r = personas.update_persona_markdown(pid, data.markdown)
        return {**r, "system_prompt": personas.system_prompt(pid)}
    except KeyError:
        raise HTTPException(404, "角色不存在")
    except ValueError as e:
        raise HTTPException(400, f"保存被拒绝：{e}")


@router.get("/prompts/persona/{pid}")
def persona_prompt(pid: str):
    """单个角色的可编辑字段 + 组装后的完整系统提示词。"""
    p = personas.get(pid)
    if not p:
        raise HTTPException(404, "角色不存在")
    return {
        "persona": {k: p.get(k) for k in personas.EDITABLE_FIELDS},
        "readonly": {"id": p["id"], "category": p["category"], "work": p["work"],
                     "heal_target": p.get("heal_target", ""),
                     "model_3d": bool(p.get("model_3d"))},
        "system_prompt": personas.system_prompt(pid),
    }


@router.put("/prompts/persona/{pid}")
def persona_prompt_save(pid: str, data: PersonaPromptPatchIn):
    """表单更新单个角色：校验 → 备份 → 写盘 → 热重载。"""
    try:
        r = personas.update_persona(pid, data.model_dump(exclude_none=True))
        return {**r, "system_prompt": personas.system_prompt(pid)}
    except KeyError:
        raise HTTPException(404, "角色不存在")
    except ValueError as e:
        raise HTTPException(400, f"保存被拒绝：{e}")


@router.post("/prompts/preview")
def persona_prompt_preview(data: PromptPreviewIn):
    """不落盘：预览表单补丁应用后的完整系统提示词。"""
    try:
        return {"system_prompt": personas.preview_prompt(data.persona_id, data.patch)}
    except ValueError as e:
        raise HTTPException(400, f"预览失败：{e}")


@router.post("/prompts/restore")
def prompts_restore(data: PromptRestoreIn):
    """恢复某个历史备份（恢复前会先备份当前版本）。"""
    try:
        return personas.restore_prompt_backup(data.filename)
    except ValueError as e:
        raise HTTPException(400, f"恢复被拒绝：{e}")
    except FileNotFoundError:
        raise HTTPException(404, "备份不存在")
