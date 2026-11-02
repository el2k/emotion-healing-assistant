# -*- coding: utf-8 -*-
"""积分路由：余额、每日领取、流水。"""
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import PointsLedger, User

router = APIRouter(prefix="/api/points", tags=["points"])

DAILY_CLAIM = 100          # 每日可领积分
CHAT_COST = 2              # 每条消息消耗


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def add_points(db: Session, user: User, delta: int, reason: str, note: str = "") -> int:
    """统一入口：变更积分并记录流水。"""
    user.points = (user.points or 0) + delta
    db.add(PointsLedger(user_id=user.id, delta=delta, balance=user.points,
                        reason=reason, note=note))
    db.commit()
    return user.points


def try_consume(db: Session, user: User, cost: int, reason: str, note: str = "") -> bool:
    """消耗积分；不足时返回 False（不产生流水）。"""
    if (user.points or 0) < cost:
        return False
    user.points -= cost
    db.add(PointsLedger(user_id=user.id, delta=-cost, balance=user.points,
                        reason=reason, note=note))
    db.commit()
    return True


class ClaimOut(BaseModel):
    balance: int
    delta: int
    message: str


@router.get("/me")
def my_points(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    last = (db.query(PointsLedger)
            .filter(PointsLedger.user_id == user.id, PointsLedger.reason == "daily_claim")
            .order_by(PointsLedger.created_at.desc()).first())
    claimed = bool(last and last.created_at.date().isoformat() == _today())
    rows = (db.query(PointsLedger).filter(PointsLedger.user_id == user.id)
            .order_by(PointsLedger.created_at.desc()).limit(20).all())
    return {
        "balance": user.points or 0,
        "claimed_today": claimed,
        "daily_amount": DAILY_CLAIM,
        "chat_cost": CHAT_COST,
        "history": [{
            "delta": r.delta, "reason": r.reason, "note": r.note,
            "balance": r.balance,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        } for r in rows],
    }


@router.post("/claim", response_model=ClaimOut)
def claim(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    last = (db.query(PointsLedger)
            .filter(PointsLedger.user_id == user.id, PointsLedger.reason == "daily_claim")
            .order_by(PointsLedger.created_at.desc()).first())
    if last and last.created_at.date().isoformat() == _today():
        raise HTTPException(409, "今天已经领取过啦，明天再来～")
    balance = add_points(db, user, DAILY_CLAIM, "daily_claim", "每日签到")
    return {"balance": balance, "delta": DAILY_CLAIM, "message": f"领取成功，+{DAILY_CLAIM} 积分！"}