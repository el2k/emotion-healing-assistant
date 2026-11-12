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


# ============================================================
# Agent 链路轨迹（透明化：让用户看到 LLM 每一步做了什么）
# ============================================================
@router.get("/trace/{trace_id}")
def get_trace(trace_id: str, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    """查看某条回复的完整处理链路（节点/耗时/入参/出参/模型与 tokens）。

    仅限自己的链路；轨迹落库为异步，刚发完消息可能需稍等片刻。
    """
    from ..services.tracer import trace_to_dict
    from ..models import AgentTraceLog

    row = (db.query(AgentTraceLog)
           .filter(AgentTraceLog.trace_id == trace_id).first())
    if not row or (row.user_id != user.id and user.role != "admin"):
        raise HTTPException(404, "轨迹不存在或已过期（刚发送的消息可能尚未落库，稍候重试）")
    data = trace_to_dict(trace_id)
    if not data:
        raise HTTPException(404, "轨迹不存在")
    # 普通用户隐藏 user_id 维度，仅保留链路内容
    data.pop("user_id", None)
    return data


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
            from ..services.tracer import (NODE_FLOW, NODE_INTENT, NODE_KNOWLEDGE,
                                           NODE_LLM_EMOTION, NODE_LLM_REPLY,
                                           NODE_MEMORY, NODE_PERSIST,
                                           NODE_RULE_EMOTION, TraceRecorder)
            from ..services import knowledge_retrieval as _kb
            tracer = TraceRecorder(user_id=uid, session_id=session_id)
            content = data.content

            with tracer.span(NODE_RULE_EMOTION,
                             input_data={"text": content}) as span:
                rule_only = await analyzer.analyze(content, use_llm=False)
                span.output = {"emotion": rule_only["emotion_type"],
                               "polarity": rule_only["polarity"]}
            emotion = rule_only
            with tracer.span(NODE_LLM_EMOTION,
                             input_data={"text": content, "model": stream_model}) as span:
                emotion = await analyzer.analyze(content, model=stream_model)
                span.output = {"emotion": emotion["emotion_type"],
                               "polarity": emotion["polarity"],
                               "high_risk": bool(emotion.get("high_risk")),
                               "source": emotion.get("source", "rule")}
                span.detail = {"model": emotion.get("llm_model", ""),
                               "tokens": (emotion.get("llm_usage") or {}).get("total_tokens")}
            if emotion.get("source") == "llm" and emotion.get("llm_model"):
                try:
                    _lu.record(db, uid, emotion["llm_model"], "analyze",
                               emotion.get("llm_usage"), estimate_text=content)
                except Exception:
                    db.rollback()
            emotion, calibration = emotion_service.apply_personal_calibration(
                db, uid, content, emotion)
            high_risk = bool(emotion.get("high_risk"))

            with tracer.span(NODE_INTENT,
                             input_data={"text": content, "high_risk": high_risk}) as span:
                intent = intent_mod.detect(content, high_risk)
                span.output = intent_mod.explain(content, high_risk)

            with tracer.span(NODE_MEMORY, input_data={"session": session_id,
                                                     "history_limit": 12}) as span:
                history, emotion_summary = emotion_service.build_memory_context(db, uid, session_id)
                prompt_card = profile_service.build_prompt_card(db, uid)
                wiki_text = wiki_service.build_wiki_prompt(db, uid)
                profile_text = "\n".join(x for x in (prompt_card, wiki_text) if x)
                span.output = {
                    "history": [{"role": m.get("role"),
                                 "content": (m.get("content") or "")[:40]}
                                for m in (history or [])],
                    "emotion_summary_internal": emotion_summary or "",  # 内部摘要，未注入提示词
                    "profile_card_injected": prompt_card or "",          # 实际注入 LLM 的画像卡
                    "memory_wiki_injected": wiki_text or "",              # 实际注入 LLM 的记忆维基
                    "summary": {
                        "history_turns": len(history or []),
                        "profile_len": len(profile_text or ""),
                        "wiki_entries": len([l for l in (wiki_text or "").splitlines()
                                             if l.startswith("-")]) or (1 if wiki_text else 0),
                    },
                }

            with tracer.span(NODE_FLOW, input_data={"emotion": emotion["emotion_type"],
                                                    "intent": intent}) as span:
                trajectory = dialog_flow.compute_trajectory(db, session_id, current_emotion=emotion)
                action = dialog_flow.pick_action(trajectory, emotion)
                strategy_text = dialog_flow.strategy_prompt_text(trajectory, emotion)
                length_text = dialog_flow.length_hint(intent)
                if action and action.get("article"):
                    article = dialog_flow.find_article(db, action["article"])
                    if article:
                        action["article_ref"] = article
                span.output = {"level": trajectory["level"], "label": trajectory["label"],
                               "consecutive_neg": trajectory["consecutive_neg"],
                               "dominant_emotion": trajectory["dominant_emotion"],
                               "action": action.get("title") if action else None,
                               "action_kind": action.get("kind") if action else None,
                               "article_ref": ({"id": action["article_ref"]["id"],
                                                "title": action["article_ref"]["title"],
                                                "category": action["article_ref"]["category"],
                                                "searched_by": action.get("article")}
                                               if action and action.get("article_ref") else None),
                               "strategy_injected": strategy_text,
                               "length_hint": length_text}

            with tracer.span(NODE_KNOWLEDGE,
                             input_data={"emotion": emotion["emotion_type"],
                                         "intent": intent,
                                         "level": trajectory["level"]}) as span:
                kb = _kb.retrieve(db, emotion["emotion_type"], intent,
                                  trajectory["level"])
                span.output = {"hit": kb["hit"],
                               "queries": kb["queries"],
                               "articles": [{"id": a["id"], "title": a["title"],
                                             "category": a["category"],
                                             "keyword": a["keyword"],
                                             "section": a["section"]}
                                            for a in kb["articles"]],
                               "reason": kb.get("reason", "")}
            knowledge_prompt = kb["prompt"]

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

            # ---- 3. 流式生成回复（附轨迹 span，messages 透出但不下发前端） ----
            recent_replies = trajectory["recent_replies"]
            full_reply = ""
            reply_source = "template"
            reply_usage: dict = {}

            with tracer.span(NODE_LLM_REPLY,
                             input_data={"user_message": content, "persona": persona_id,
                                         "model": stream_model}) as span:
                async for event in _lr.generate_stream(
                        emotion, content, history=history, profile_text=profile_text,
                        intent=intent, persona_id=persona_id,
                        recent_replies=recent_replies,
                        strategy_text=strategy_text, length_text=length_text,
                        model=stream_model, include_messages=True,
                        knowledge_text=knowledge_prompt):
                    if event["type"] == "chunk":
                        full_reply += event["content"]
                        yield f'data: {_json.dumps({"type":"chunk","content":event["content"]}, ensure_ascii=False)}\n\n'
                    elif event["type"] == "done":
                        full_reply = event["content"]
                        reply_source = event["source"]
                        if event.get("model"):
                            reply_usage = {"model": event["model"],
                                           "usage": event.get("usage") or {},
                                           "messages": event.get("messages")}
                span.output = {"reply": (full_reply or "")[:300], "source": reply_source}
                if reply_usage.get("messages"):
                    span.input = {"user_message": content, "model": stream_model,
                                  "persona": persona_id,
                                  "messages": reply_usage["messages"]}
                span.detail = {"model": reply_usage.get("model", ""),
                               "tokens": (reply_usage.get("usage") or {}).get("total_tokens"),
                               "stream": True}
            # ---- 3.1 记录回复生成的 token 消耗 ----
            if reply_usage.get("model"):
                try:
                    _lu.record(db, uid, reply_usage["model"], "reply_stream",
                               reply_usage.get("usage"), estimate_text=full_reply)
                except Exception:
                    db.rollback()

            # ---- 4. 落库（轨迹记 PERSIST 节点）----
            with tracer.span(NODE_PERSIST, input_data={"session": session_id}) as persist_span:
                trigger = (content[:60] + "…") if len(content) > 60 else content
                user_msg = Message(session_id=session_id, role="user", content=content,
                                   msg_type=data.msg_type, image_url=data.image_url,
                                   emotion_type=emotion["emotion_type"],
                                   emotion_score=emotion["heal_score"],
                                   emotion_source=emotion.get("source", "rule"))
                user_msg.detail = _json.dumps(
                    {"hits": emotion.get("hits", []), "high_risk": emotion.get("high_risk", []),
                     "suggestion": emotion.get("suggestion", ""), "intent": intent}, ensure_ascii=False)
                assistant_msg = Message(session_id=session_id, role="assistant",
                                        content=full_reply, trace_id=tracer.trace_id)
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
                persist_span.output = {"reply_msg_id": assistant_msg.id}

        # ---- 5. 触发维基编译 ----
            try:
                total = db.query(Message).join(ChatSession, ChatSession.id == Message.session_id) \
                    .filter(ChatSession.user_id == uid, Message.role == "user").count()
                _ws.maybe_compile_async(SessionLocal, uid, total)
            except Exception:
                pass

            # ---- 6. 发送 done 事件：附 trace_id（messages 等内部字段不下发）----
            done = {
                "type": "done",
                "reply_id": assistant_msg.id,
                "reply": {"id": assistant_msg.id, "role": "assistant", "content": full_reply},
                "reply_source": reply_source,
                "degraded": reply_source == "template_degraded",
                "trace_id": tracer.trace_id,
            }
            yield f"data: {_json.dumps(done, ensure_ascii=False)}\n\n"
            # ---- 7. 链路追踪异步落库（关联回复消息 ID）----
            tracer.flush(message_id=assistant_msg.id)
        finally:
            stream_db.close()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )