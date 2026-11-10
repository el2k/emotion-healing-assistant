# -*- coding: utf-8 -*-
"""认证路由：注册、登录、个人信息、退出（含限流防护）。"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import ChatSession, EmotionRecord, Message, User
from ..schemas import LoginIn, ProfileUpdateIn, RegisterIn, TokenOut
from ..security import create_token, hash_password, verify_password
from ..security.rate_limit import login_limiter, register_limiter

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    """取真实客户端 IP（支持代理头）。"""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/register", response_model=TokenOut)
def register(data: RegisterIn, request: Request, db: Session = Depends(get_db)):
    # 限流：单 IP 60秒/5次，超限封禁 10 分钟（防批量注册）
    ip = _client_ip(request)
    if not register_limiter.check(f"reg:{ip}"):
        raise HTTPException(status_code=429, detail="注册请求过于频繁，请稍后再试")
    if db.query(User).filter(User.phone == data.phone).first():
        raise HTTPException(status_code=409, detail="该手机号已注册")
    user = User(
        phone=data.phone,
        nickname=data.nickname or f"用户_{data.phone[-4:]}",
        password_hash=hash_password(data.password),
        role="user",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_token(user.id, user.role)
    return TokenOut(token=token, user_id=user.id,
                    nickname=user.nickname, role=user.role)


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, request: Request, db: Session = Depends(get_db)):
    # 双维度限流：IP（防扫描）+ 账号（防定向爆破）
    # 60秒内每 IP 最多10次、每账号最多10次；超限封禁5分钟
    ip = _client_ip(request)
    if not login_limiter.check(f"ip:{ip}"):
        raise HTTPException(status_code=429, detail="尝试过于频繁，请5分钟后重试")
    if not login_limiter.check(f"acct:{data.phone}"):
        raise HTTPException(status_code=429, detail="该账号尝试过于频繁，请5分钟后重试")

    user = db.query(User).filter(User.phone == data.phone).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="手机号或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已被禁用")
    # 登录成功：重置该账号与 IP 的计数（不误伤正常用户）
    login_limiter.reset(f"acct:{data.phone}")
    login_limiter.reset(f"ip:{ip}")
    token = create_token(user.id, user.role)
    return TokenOut(token=token, user_id=user.id,
                    nickname=user.nickname, role=user.role)


@router.get("/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """当前登录用户的个人信息 + 使用统计。"""
    session_count = (db.query(func.count(ChatSession.id))
                     .filter(ChatSession.user_id == user.id).scalar() or 0)
    message_count = (db.query(func.count(Message.id))
                     .join(ChatSession, ChatSession.id == Message.session_id)
                     .filter(ChatSession.user_id == user.id).scalar() or 0)
    emotion_count = (db.query(func.count(EmotionRecord.id))
                     .filter(EmotionRecord.user_id == user.id).scalar() or 0)
    days_active = (db.query(func.count(func.distinct(func.date(EmotionRecord.created_at))))
                   .filter(EmotionRecord.user_id == user.id).scalar() or 0)

    return {
        "id": user.id,
        "phone": user.phone,
        "nickname": user.nickname,
        "avatar": user.avatar or "",
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "stats": {
            "sessions": session_count,
            "messages": message_count,
            "emotions": emotion_count,
            "days_active": days_active,
        },
    }


@router.put("/me")
def update_me(data: ProfileUpdateIn, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    """修改昵称 / 头像 / 手机号 / 密码（改手机号与密码需校验原密码）。"""
    msg = []

    if data.nickname is not None and data.nickname.strip():
        user.nickname = data.nickname.strip()
        msg.append("昵称已更新")

    if data.avatar is not None:
        user.avatar = data.avatar.strip()
        msg.append("头像已更新")

    # 修改手机号
    if data.phone and data.phone.strip() and data.phone.strip() != user.phone:
        new_phone = data.phone.strip()
        if not data.old_password or not verify_password(data.old_password, user.password_hash):
            raise HTTPException(400, "修改手机号需填写正确的原密码")
        if db.query(User).filter(User.phone == new_phone, User.id != user.id).first():
            raise HTTPException(409, "该手机号已被占用")
        user.phone = new_phone
        msg.append("手机号已更新")

    # 修改密码
    if data.new_password:
        if not data.old_password:
            raise HTTPException(400, "请填写原密码")
        if not verify_password(data.old_password, user.password_hash):
            raise HTTPException(400, "原密码不正确")
        user.password_hash = hash_password(data.new_password)
        msg.append("密码已更新")

    if not msg:
        raise HTTPException(400, "没有需要修改的内容")
    db.commit()
    return {"ok": True, "message": "、".join(msg), "nickname": user.nickname,
            "phone": user.phone, "avatar": user.avatar or ""}


@router.post("/logout")
def logout(user: User = Depends(get_current_user)):
    """退出当前用户（JWT 无状态，服务端仅作确认，前端清理凭证即可）。"""
    return {"ok": True, "message": "已退出登录"}