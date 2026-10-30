# -*- coding: utf-8 -*-
"""管理后台路由：概览、用户、情绪、角色运营、社区审核、系统信息。"""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..config import BASE_DIR, settings
from ..database import get_db
from ..deps import get_current_user, require_admin
from ..models import (ChatSession, EmotionCalibration, EmotionRecord,
                      ForumComment, ForumLike, ForumPost, Message, User)
from .. import personas
from ..schemas import UserUpdateIn
from ..security import hash_password
from ..services import emotion_service

APP_VERSION = "2.0.0"

router = APIRouter(prefix="/api/admin", tags=["admin"],
                   dependencies=[Depends(require_admin)])


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