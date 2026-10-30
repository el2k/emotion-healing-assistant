# -*- coding: utf-8 -*-
"""聊天路由：会话、消息、图片上传。"""
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import ChatSession, User
from ..schemas import MessageIn, SessionCreateIn, SessionRenameIn
from ..services import chat_service
from .. import personas

router = APIRouter(prefix="/api/chat", tags=["chat"])

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
_ALLOWED = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def _own_session(db: Session, user: User, session_id: int) -> ChatSession:
    s = db.query(ChatSession).filter(
        ChatSession.id == session_id, ChatSession.user_id == user.id).first()
    if not s:
        raise HTTPException(status_code=404, detail="会话不存在")
    return s


def _persona_counts(db: Session) -> dict:
    rows = (db.query(ChatSession.persona_id, func.count(ChatSession.id))
            .group_by(ChatSession.persona_id).all())
    return {pid or "nuan": c for pid, c in rows}


@router.get("/personas")
def personas_list(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    counts = _persona_counts(db)
    data = personas.list_personas()
    for p in data:
        p["chat_count"] = counts.get(p["id"], 0)
    return data


@router.get("/personas/popular")
def personas_popular(limit: int = Query(8, ge=1, le=20),
                     user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    counts = _persona_counts(db)
    data = personas.list_personas()
    for p in data:
        p["chat_count"] = counts.get(p["id"], 0)
    data.sort(key=lambda x: (-x["chat_count"], x["name"]))
    return data[:limit]


@router.post("/sessions")
def create_session(data: SessionCreateIn, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    s = chat_service.create_session(db, user.id, data.title, data.persona_id)
    return {"id": s.id, "title": s.title, "persona_id": s.persona_id}


@router.get("/sessions")
def sessions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return chat_service.list_sessions(db, user.id)


@router.get("/sessions/{session_id}/messages")
def messages(session_id: int, user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    _own_session(db, user, session_id)
    return chat_service.list_messages(db, session_id)


@router.delete("/sessions/{session_id}")
def delete(session_id: int, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    _own_session(db, user, session_id)
    chat_service.delete_session(db, session_id)
    return {"ok": True}


@router.put("/sessions/{session_id}")
def rename_session(session_id: int, data: SessionRenameIn,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = _own_session(db, user, session_id)
    s.title = data.title.strip()
    db.commit()
    return {"id": s.id, "title": s.title}


@router.post("/upload")
async def upload(file: UploadFile = File(...), user: User = Depends(get_current_user)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _ALLOWED:
        raise HTTPException(400, "仅支持 png/jpg/jpeg/webp/gif 图片")
    data = await file.read()
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(400, "图片不能超过 8MB")
    name = f"{uuid.uuid4().hex}{ext}"
    (UPLOAD_DIR / name).write_bytes(data)
    return {"url": f"/uploads/{name}"}


@router.post("/sessions/{session_id}/messages")
async def send(session_id: int, data: MessageIn,
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _own_session(db, user, session_id)
    if not data.content.strip() and not data.image_url:
        raise HTTPException(400, "消息内容不能为空")
    return await chat_service.send_user_message(
        db, user.id, session_id, data.content, data.msg_type, data.image_url)