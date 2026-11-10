# -*- coding: utf-8 -*-
"""聊天路由：会话、消息、图片上传。"""
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import ChatSession, LLMModel, User
from ..schemas import MessageIn, SessionCreateIn, SessionRenameIn
from ..services import chat_service, llm_models
from ..config import settings
from .. import personas

router = APIRouter(prefix="/api/chat", tags=["chat"])


# ============================================================
# 模型选择：用户可选的 AI 模型列表与偏好保存
# ============================================================
@router.get("/models")
def models_list(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """可选模型列表 + 当前选中（请求偏好 → 用户偏好 → 默认）。"""
    rows = llm_models.list_enabled(db)
    current = llm_models.resolve_model(db, None, user.llm_model)
    return {
        "enabled": bool(settings.LLM_ENABLED and settings.LLM_API_KEY),
        "current": current,
        "models": [
            {"id": m.model_id, "name": m.display_name or m.model_id,
             "description": m.description or "",
             "is_default": bool(m.is_default)}
            for m in rows
        ],
    }


class SelectModelIn(BaseModel):
    model: str = Field(..., min_length=1, max_length=64)


@router.post("/model")
def select_model(data: SelectModelIn, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    """保存用户偏好的模型（仅限启用中的模型）。"""
    if not llm_models.get_enabled(db, data.model):
        raise HTTPException(400, "该模型不存在或未启用")
    user.llm_model = data.model
    db.commit()
    return {"current": data.model}

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
    # 积分消耗：每条消息 2 积分（余额不足时提示领取每日积分）
    from .points import try_consume, CHAT_COST
    if not try_consume(db, user, CHAT_COST, "chat", note=f"会话 {session_id}"):
        raise HTTPException(402, f"积分不足（当前 {user.points or 0}），"
                                 "请在「个人信息」页领取每日 100 免费积分后再聊～")
    model = llm_models.resolve_model(db, data.model, user.llm_model)
    return await chat_service.send_user_message(
        db, user.id, session_id, data.content, data.msg_type, data.image_url,
        model=model)


# ============================================================
# 流式端点（SSE）：逐字返回回复，降低首字延迟
# ============================================================
from fastapi.responses import StreamingResponse
import json as _json


@router.post("/sessions/{session_id}/messages/stream")
async def send_stream(session_id: int, data: MessageIn,
                     user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    """流式发送消息。返回 SSE（Server-Sent Events）。

    事件流：
      data: {"type":"meta", "emotion":{...}, "user_message":{...}, "flow":{...}}\n\n
      data: {"type":"chunk", "content":"..."}\n\n  （多个）
      data: {"type":"done", "reply_id":123, "reply_source":"llm", "degraded":false}\n\n
    """
    _own_session(db, user, session_id)
    if not data.content.strip() and not data.image_url:
        raise HTTPException(400, "消息内容不能为空")
    from .points import try_consume, CHAT_COST
    if not try_consume(db, user, CHAT_COST, "chat", note=f"会话 {session_id}"):
        raise HTTPException(402, f"积分不足（当前 {user.points or 0}）")

    # 生成器执行时 FastAPI 已关闭注入的 db、且 user ORM 懒加载会 Detached——
    # 在这里（请求处理阶段）先提取所有需要的标量值，再传给生成器闭包
    uid = user.id
    stream_model = llm_models.resolve_model(db, data.model, user.llm_model)

    async def event_stream():
        """SSE 生成器：先发 meta，再逐字流式返回。"""
        from ..database import SessionLocal
        stream_db = SessionLocal()
        try:
            from ..emotion import analyzer, intent as intent_mod
            from ..services import emotion_service, dialog_flow, profile_service, wiki_service, llm_reply as _lr
            from ..services import llm_usage as _lu
            from ..models import Message, EmotionRecord
            from ..services import wiki_service as _ws

            db = stream_db  # 长会话替代注入的已关闭会话
            content = data.content
            emotion = await analyzer.analyze(content, model=stream_model)
            if emotion.get("source") == "llm" and emotion.get("llm_model"):
                try:
                    _lu.record(db, uid, emotion["llm_model"], "analyze",
                               emotion.get("llm_usage"), estimate_text=content)
                except Exception:
                    db.rollback()
            emotion, calibration = emotion_service.apply_personal_calibration(
                db, uid, content, emotion)
            intent = intent_mod.detect(content, bool(emotion.get("high_risk")))

            history, _ = emotion_service.build_memory_context(db, uid, session_id)
            profile_text = profile_service.build_prompt_card(db, uid)
            wiki_text = wiki_service.build_wiki_prompt(db, uid)
            if wiki_text:
                profile_text = (profile_text + "\n" + wiki_text) if profile_text else wiki_text

            trajectory = dialog_flow.compute_trajectory(db, session_id, current_emotion=emotion)
            action = dialog_flow.pick_action(trajectory, emotion)
            strategy_text = dialog_flow.strategy_prompt_text(trajectory, emotion)
            length_text = dialog_flow.length_hint(intent)

            session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
            persona_id = session.persona_id if session else "nuan"

            # ---- 2. 发送 meta 事件 ----
            meta = {
                "type": "meta",
                "emotion": {
                    "emotion_type": emotion["emotion_type"],
                    "polarity": emotion["polarity"],
                    "heal_score": emotion["heal_score"],
                    "high_risk": emotion.get("high_risk", []),
                    "source": emotion.get("source", "rule"),
                    "intent": intent,
                },
                "user_message": {
                    "role": "user", "content": content,
                    "msg_type": data.msg_type, "image_url": data.image_url or "",
                    "emotion_type": emotion["emotion_type"],
                    "emotion_score": emotion["heal_score"],
                },
                "flow": {"level": trajectory["level"], "label": trajectory["label"],
                         "consecutive_neg": trajectory["consecutive_neg"]},
                "action": action,
            }
            yield f"data: {_json.dumps(meta, ensure_ascii=False)}\n\n"

            # ---- 3. 流式生成回复 ----
            recent_replies = trajectory["recent_replies"]
            full_reply = ""
            reply_source = "template"
            reply_usage: dict = {}

            async for event in _lr.generate_stream(
                    emotion, content, history=history, profile_text=profile_text,
                    intent=intent, persona_id=persona_id,
                    recent_replies=recent_replies,
                    strategy_text=strategy_text, length_text=length_text,
                    model=stream_model):
                if event["type"] == "chunk":
                    full_reply += event["content"]
                    yield f'data: {_json.dumps({"type":"chunk","content":event["content"]}, ensure_ascii=False)}\n\n'
                elif event["type"] == "done":
                    full_reply = event["content"]
                    reply_source = event["source"]
                    if event.get("model"):
                        reply_usage = {"model": event["model"], "usage": event.get("usage") or {}}

            # ---- 3.1 记录回复生成的 token 消耗 ----
            if reply_usage.get("model"):
                try:
                    _lu.record(db, uid, reply_usage["model"], "reply_stream",
                               reply_usage.get("usage"), estimate_text=full_reply)
                except Exception:
                    db.rollback()

            # ---- 4. 落库 ----
            trigger = (content[:60] + "…") if len(content) > 60 else content
            user_msg = Message(session_id=session_id, role="user", content=content,
                               msg_type=data.msg_type, image_url=data.image_url,
                               emotion_type=emotion["emotion_type"],
                               emotion_score=emotion["heal_score"],
                               emotion_source=emotion.get("source", "rule"))
            user_msg.detail = _json.dumps(
                {"hits": emotion.get("hits", []), "high_risk": emotion.get("high_risk", []),
                 "suggestion": emotion.get("suggestion", ""), "intent": intent}, ensure_ascii=False)
            assistant_msg = Message(session_id=session_id, role="assistant", content=full_reply)
            record = EmotionRecord(
                user_id=uid, session_id=session_id,
                emotion_type=emotion["emotion_type"],
                score=emotion.get("heal_score", 0.0),
                polarity=1 if emotion["polarity"] == "positive" else (
                    -1 if emotion["polarity"] == "negative" else 0),
                source=emotion.get("source", "rule"), intent=intent, trigger=trigger)
            db.add_all([user_msg, assistant_msg, record])
            if session and session.title == "新的对话":
                base = content if content else "新的对话"
                session.title = (base[:20] + "…") if len(base) > 20 else base
            db.commit()
            db.refresh(user_msg)
            db.refresh(assistant_msg)

        # ---- 5. 触发维基编译 ----
            try:
                total = db.query(Message).join(ChatSession, ChatSession.id == Message.session_id) \
                    .filter(ChatSession.user_id == uid, Message.role == "user").count()
                _ws.maybe_compile_async(SessionLocal, uid, total)
            except Exception:
                pass

            # ---- 6. 发送 done 事件 ----
            done = {
                "type": "done",
                "reply_id": assistant_msg.id,
                "reply": {"id": assistant_msg.id, "role": "assistant", "content": full_reply},
                "reply_source": reply_source,
                "degraded": reply_source == "template_degraded",
            }
            yield f"data: {_json.dumps(done, ensure_ascii=False)}\n\n"
        finally:
            stream_db.close()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )