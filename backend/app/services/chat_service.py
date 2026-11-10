# -*- coding: utf-8 -*-
"""对话服务：创建会话、收发消息、记录情绪档案与多轮记忆。"""
import json

from sqlalchemy.orm import Session

from ..emotion import analyzer
from ..emotion import intent as intent_mod
from ..models import ChatSession, EmotionRecord, Message
from .. import personas
from . import dialog_flow, emotion_service, llm_reply, llm_usage, profile_service, wiki_service


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
                            image_url: str = "", model: str | None = None) -> dict:
    """处理用户消息：情绪分析 -> 意图识别 -> 生成回复(带记忆) -> 入库 -> 写情绪档案。

    model：本次使用的 LLM 模型（已由路由层解析好）；None 时用全局默认。
    """
    # 1) 情绪分析（model 使分析/回复使用同一模型，token 统计归属清晰）
    emotion = await analyzer.analyze(content, model=model)
    # 1.1) 记录情绪分析的 token 消耗（LLM 来源时）
    if emotion.get("source") == "llm" and emotion.get("llm_model"):
        try:
            llm_usage.record(db, user_id, emotion["llm_model"], "analyze",
                             emotion.get("llm_usage"), success=True, estimate_text=content)
        except Exception:
            db.rollback()
    # 1.1) 个人情绪校准（用用户历史纠正结果做个性化修正，不完全依赖模型）
    emotion, calibration = emotion_service.apply_personal_calibration(
        db, user_id, content, emotion)
    high_risk = bool(emotion.get("high_risk"))

    # 2) 意图识别
    intent = intent_mod.detect(content, high_risk)

    # 3) 多轮记忆上下文 + 长期画像（画像卡 + 记忆维基：让角色「记得你」）
    history, _ = emotion_service.build_memory_context(db, user_id, session_id)
    profile_text = profile_service.build_prompt_card(db, user_id)
    wiki_text = wiki_service.build_wiki_prompt(db, user_id)
    if wiki_text:
        profile_text = (profile_text + "\n" + wiki_text) if profile_text else wiki_text

    # 3.1) 会话级情绪轨迹与陪伴策略（连续低落 → 升级深度陪伴 + 去重）
    trajectory = dialog_flow.compute_trajectory(db, session_id,
                                                current_emotion=emotion)
    action = dialog_flow.pick_action(trajectory, emotion)
    if action and action.get("article"):
        article = dialog_flow.find_article(db, action["article"])
        if article:
            action["article_ref"] = article
    strategy_text = dialog_flow.strategy_prompt_text(trajectory, emotion)
    length_text = dialog_flow.length_hint(intent)

    # 3.2) 会话所属角色
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    persona_id = session.persona_id if session else "nuan"

    # 4) 生成回复
    reply_usage: dict = {}
    if msg_type == "image" and not content.strip():
        reply = "我看到你分享的图片啦，谢谢你愿意和我分享这一刻～如果它让你想到什么、或有什么感受，都可以说给我听。"
        reply_source = "template"
    else:
        reply, reply_source, reply_usage = await llm_reply.generate(
            emotion, content, history=history, profile_text=profile_text,
            intent=intent, persona_id=persona_id,
            recent_replies=trajectory["recent_replies"],
            strategy_text=strategy_text, length_text=length_text,
            model=model)
        # 记录回复生成的 token 消耗
        if reply_usage.get("model"):
            try:
                llm_usage.record(db, user_id, reply_usage["model"], "reply",
                                 reply_usage.get("usage"), success=True, estimate_text=reply)
            except Exception:
                db.rollback()

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

    # 9) 记忆维基编译（每 EXTRACT_EVERY 条用户消息触发一次，后台执行，不阻塞回复）
    try:
        total = db.query(Message).join(ChatSession, ChatSession.id == Message.session_id) \
            .filter(ChatSession.user_id == user_id, Message.role == "user").count()
        from ..database import SessionLocal
        wiki_service.maybe_compile_async(SessionLocal, user_id, total)
    except Exception:
        pass

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
        "degraded": reply_source == "template_degraded",  # True = LLM 故障走了降级
        "flow": {
            "level": trajectory["level"],
            "label": trajectory["label"],
            "consecutive_neg": trajectory["consecutive_neg"],
            "dominant_emotion": trajectory["dominant_emotion"],
        },
        "action": action,
    }