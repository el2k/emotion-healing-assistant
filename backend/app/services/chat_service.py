# -*- coding: utf-8 -*-
"""对话服务：创建会话、收发消息、记录情绪档案与多轮记忆。"""
import json

from sqlalchemy.orm import Session

from ..emotion import analyzer
from ..emotion import intent as intent_mod
from ..models import ChatSession, EmotionRecord, Message
from .. import personas
from . import emotion_service, llm_reply


def create_session(db: Session, user_id: int, title: str = "新的对话",
                   persona_id: str = "nuan") -> ChatSession:
    session = ChatSession(user_id=user_id, title=title or "新的对话",
                          persona_id=persona_id or "nuan")
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def list_sessions(db: Session, user_id: int) -> list[dict]:
    rows = (db.query(ChatSession)
            .filter(ChatSession.user_id == user_id)
            .order_by(ChatSession.updated_at.desc())
            .all())
    result = []
    for s in rows:
        msg_count = db.query(Message).filter(Message.session_id == s.id).count()
        result.append({
            "id": s.id, "title": s.title,
            "persona_id": s.persona_id or "nuan",
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            "message_count": msg_count,
        })
    return result


def list_messages(db: Session, session_id: int) -> list[dict]:
    msgs = (db.query(Message)
            .filter(Message.session_id == session_id)
            .order_by(Message.created_at.asc())
            .all())
    return [
        {
            "id": m.id, "role": m.role, "content": m.content,
            "msg_type": m.msg_type or "text", "image_url": m.image_url or "",
            "emotion_type": m.emotion_type, "emotion_score": m.emotion_score,
            "emotion_source": m.emotion_source,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in msgs
    ]


def delete_session(db: Session, session_id: int) -> bool:
    s = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not s:
        return False
    db.query(Message).filter(Message.session_id == session_id).delete()
    db.delete(s)
    db.commit()
    return True


async def send_user_message(db: Session, user_id: int, session_id: int,
                            content: str, msg_type: str = "text",
                            image_url: str = "") -> dict:
    """处理用户消息：情绪分析 -> 意图识别 -> 生成回复(带记忆) -> 入库 -> 写情绪档案。"""
    # 1) 情绪分析
    emotion = await analyzer.analyze(content)
    # 1.1) 个人情绪校准（用用户历史纠正结果做个性化修正，不完全依赖模型）
    emotion, calibration = emotion_service.apply_personal_calibration(
        db, user_id, content, emotion)
    high_risk = bool(emotion.get("high_risk"))

    # 2) 意图识别
    intent = intent_mod.detect(content, high_risk)

    # 3) 多轮记忆上下文 + 长期画像
    history, profile_text = emotion_service.build_memory_context(db, user_id, session_id)

    # 3.1) 会话所属角色
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    persona_id = session.persona_id if session else "nuan"

    # 4) 生成回复
    if msg_type == "image" and not content.strip():
        reply = "我看到你分享的图片啦，谢谢你愿意和我分享这一刻～如果它让你想到什么、或有什么感受，都可以说给我听。"
        reply_source = "template"
    else:
        reply, reply_source = await llm_reply.generate(
            emotion, content, history=history, profile_text=profile_text,
            intent=intent, persona_id=persona_id)

    trigger = (content[:60] + "…") if len(content) > 60 else content

    # 5) 落库：用户消息
    user_msg = Message(
        session_id=session_id, role="user", content=content,
        msg_type=msg_type, image_url=image_url,
        emotion_type=emotion["emotion_type"], emotion_score=emotion["heal_score"],
        emotion_source=emotion.get("source", "rule"),
    )
    user_msg.detail = json.dumps(
        {"hits": emotion.get("hits", []), "high_risk": emotion.get("high_risk", []),
         "suggestion": emotion.get("suggestion", ""), "intent": intent}, ensure_ascii=False)

    # 6) 落库：助手回复
    assistant_msg = Message(session_id=session_id, role="assistant", content=reply)

    # 7) 情绪档案（含意图与触发事件）
    record = EmotionRecord(
        user_id=user_id, session_id=session_id,
        emotion_type=emotion["emotion_type"],
        score=emotion.get("heal_score", 0.0),
        polarity=1 if emotion["polarity"] == "positive" else (
            -1 if emotion["polarity"] == "negative" else 0),
        source=emotion.get("source", "rule"),
        intent=intent, trigger=trigger,
        detail=json.dumps({"high_risk": emotion.get("high_risk", []),
                           "hits": emotion.get("hits", [])}, ensure_ascii=False),
    )

    db.add_all([user_msg, assistant_msg, record])

    # 8) 更新会话标题与时间
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if session and session.title == "新的对话":
        base = content if content else ("[图片]" if msg_type == "image" else "新的对话")
        session.title = (base[:20] + "…") if len(base) > 20 else base
    db.commit()
    db.refresh(user_msg)
    db.refresh(assistant_msg)

    return {
        "user_message": {
            "id": user_msg.id, "role": "user", "content": content,
            "msg_type": msg_type, "image_url": image_url,
            "emotion_type": user_msg.emotion_type,
            "emotion_score": user_msg.emotion_score,
            "emotion_source": user_msg.emotion_source,
        },
        "reply": {
            "id": assistant_msg.id, "role": "assistant", "content": reply,
        },
        "emotion": {
            "emotion_type": emotion["emotion_type"],
            "polarity": emotion["polarity"],
            "score": emotion["score"],
            "heal_score": emotion["heal_score"],
            "high_risk": emotion.get("high_risk", []),
            "source": emotion.get("source", "rule"),
            "hits": emotion.get("hits", []),
            "intent": intent,
            "calibration": emotion.get("calibration"),
        },
        "reply_source": reply_source,
    }