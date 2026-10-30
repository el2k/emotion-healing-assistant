# -*- coding: utf-8 -*-
"""情绪档案路由（用户端）：长周期画像、每日小结、AI 洞察、个人校准。"""
from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import ChatSession, EmotionCalibration, EmotionRecord, Message, User
from ..schemas import CalibrateIn
from ..services import emotion_service

router = APIRouter(prefix="/api/emotion", tags=["emotion"])


def _aware(dt):
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


@router.get("/profile")
def profile(days: int = Query(90, ge=1, le=3650),
            user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return emotion_service.long_term_profile(db, user.id, days)


@router.get("/daily")
def daily(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return emotion_service.daily_summary(db, user.id)


@router.get("/insight")
async def insight(days: int = Query(30, ge=1, le=3650),
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return await emotion_service.insight(db, user.id, days)


@router.get("/calibration")
def calibration(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return emotion_service.calibration_stats(db, user.id)


@router.get("/persona-stats")
def persona_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """角色陪伴 + 情绪的联动统计。"""
    return emotion_service.persona_breakdown(db, user.id)


@router.post("/calibrate")
def calibrate(data: CalibrateIn, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    """用户手动校准某条消息的情绪；同时回写情绪档案与校准历史。"""
    if data.emotion_type not in emotion_service.EMOTION_TYPES:
        raise HTTPException(400, "无效的情绪类型")

    msg = (db.query(Message)
           .join(ChatSession, ChatSession.id == Message.session_id)
           .filter(Message.id == data.message_id,
                   ChatSession.user_id == user.id,
                   Message.role == "user")
           .first())
    if not msg:
        raise HTTPException(404, "消息不存在")

    original = msg.emotion_type or "中性"
    msg.emotion_type = data.emotion_type
    msg.emotion_source = "user_calibrated"

    # 回写最近的情绪档案记录
    rec = _nearest_record(db, user.id, msg)
    if rec:
        rec.emotion_type = data.emotion_type
        rec.polarity = emotion_service.polarity_of(data.emotion_type)
        rec.source = "user_calibrated"

    db.add(EmotionCalibration(
        user_id=user.id, message_id=msg.id,
        record_id=rec.id if rec else None,
        original_emotion=original,
        corrected_emotion=data.emotion_type,
        text=(msg.content or "")[:200],
    ))
    db.commit()

    return {
        "ok": True,
        "message_id": msg.id,
        "original": original,
        "corrected": data.emotion_type,
        "calibrated": original != data.emotion_type,
        "message": "已按你的感受校准，后续识别会更贴合你。",
    }


def _nearest_record(db: Session, user_id: int, msg: Message):
    """找到与该消息最接近的情绪档案记录（同会话、时间最相近）。"""
    q = db.query(EmotionRecord).filter(EmotionRecord.user_id == user_id)
    if msg.session_id:
        q = q.filter(EmotionRecord.session_id == msg.session_id)
    candidates = q.order_by(EmotionRecord.created_at.desc()).limit(20).all()
    if not candidates:
        return None
    mt = _aware(msg.created_at)
    best, best_diff = None, None
    for r in candidates:
        rt = _aware(r.created_at)
        diff = abs((rt - mt).total_seconds()) if (rt and mt) else 999
        if best_diff is None or diff < best_diff:
            best_diff, best = diff, r
    return best if best_diff is not None and best_diff <= 120 else None