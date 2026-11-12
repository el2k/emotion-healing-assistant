# -*- coding: utf-8 -*-
"""对话服务：创建会话、收发消息、记录情绪档案与多轮记忆。"""
import json

from sqlalchemy.orm import Session

from ..emotion import analyzer
from ..emotion import intent as intent_mod
from ..models import ChatSession, EmotionRecord, Message
from .. import personas
from . import dialog_flow, emotion_service, llm_reply, llm_usage, profile_service, wiki_service
from . import knowledge_retrieval
from .tracer import (NODE_FALLBACK, NODE_FLOW, NODE_INTENT, NODE_KNOWLEDGE,
                     NODE_LLM_EMOTION, NODE_LLM_REPLY, NODE_MEMORY, NODE_PERSIST,
                     NODE_RULE_EMOTION, TraceRecorder)


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
            "trace_id": m.trace_id or "",   # assistant 消息的链路 ID（刷新后仍可查轨迹）
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
    全链路按节点记录 Agent Trace（异步落库；响应附 trace_id 供前端透明化查看）。
    """
    tracer = TraceRecorder(user_id=user_id, session_id=session_id)

    # 1) 情绪分析（model 使分析/回复使用同一模型，token 统计归属清晰）
    with tracer.span(NODE_RULE_EMOTION, input_data={"text": content}) as span:
        rule_only = await analyzer.analyze(content, use_llm=False)
        span.output = {"emotion": rule_only["emotion_type"],
                       "polarity": rule_only["polarity"],
                       "heal_score": rule_only["heal_score"]}
    emotion = rule_only
    with tracer.span(NODE_LLM_EMOTION, input_data={"text": content, "model": model}) as span:
        emotion = await analyzer.analyze(content, model=model)
        span.output = {"emotion": emotion["emotion_type"],
                       "polarity": emotion["polarity"],
                       "heal_score": emotion.get("heal_score"),
                       "high_risk": bool(emotion.get("high_risk")),
                       "source": emotion.get("source", "rule")}
        span.detail = {"model": emotion.get("llm_model", ""),
                       "tokens": (emotion.get("llm_usage") or {}).get("total_tokens")}
    # 1.1) 记录情绪分析的 token 消耗（LLM 来源时）
    if emotion.get("source") == "llm" and emotion.get("llm_model"):
        try:
            llm_usage.record(db, user_id, emotion["llm_model"], "analyze",
                             emotion.get("llm_usage"), success=True, estimate_text=content)
        except Exception:
            db.rollback()
    # 1.2) 个人情绪校准（用用户历史纠正结果做个性化修正，不完全依赖模型）
    emotion, calibration = emotion_service.apply_personal_calibration(
        db, user_id, content, emotion)
    high_risk = bool(emotion.get("high_risk"))

    # 2) 意图识别（explain 附带判定过程：命中关键词与路径）
    with tracer.span(NODE_INTENT, input_data={"text": content, "high_risk": high_risk}) as span:
        intent = intent_mod.detect(content, high_risk)
        span.output = intent_mod.explain(content, high_risk)

    # 3) 多轮记忆上下文 + 长期画像（画像卡 + 记忆维基：让角色「记得你」）
    #    透出实际注入的内容摘要：历史消息、画像卡、维基条目（黑盒打开）
    with tracer.span(NODE_MEMORY, input_data={"session": session_id,
                                             "history_limit": 12}) as span:
        history, emotion_summary = emotion_service.build_memory_context(db, user_id, session_id)
        prompt_card = profile_service.build_prompt_card(db, user_id)
        wiki_text = wiki_service.build_wiki_prompt(db, user_id)
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

    # 3.1) 会话级情绪轨迹与陪伴策略（连续低落 → 升级深度陪伴 + 去重）
    with tracer.span(NODE_FLOW,
                     input_data={"emotion": emotion["emotion_type"],
                                 "intent": intent}) as span:
        trajectory = dialog_flow.compute_trajectory(db, session_id,
                                                    current_emotion=emotion)
        action = dialog_flow.pick_action(trajectory, emotion)
        if action and action.get("article"):
            article = dialog_flow.find_article(db, action["article"])
            if article:
                action["article_ref"] = article
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
                       # 行动卡片关联的知识库文章（点击「阅读 ›」跳转的那篇）
                       "article_ref": ({"id": action["article_ref"]["id"],
                                        "title": action["article_ref"]["title"],
                                        "category": action["article_ref"]["category"],
                                        "searched_by": action.get("article")}
                                       if action and action.get("article_ref") else None),
                       "strategy_injected": strategy_text,
                       "length_hint": length_text}

    # 3.2) 知识库检索（轻量 RAG）：求助或连续负向时检索段落注入提示词
    with tracer.span(NODE_KNOWLEDGE,
                     input_data={"emotion": emotion["emotion_type"], "intent": intent,
                                 "level": trajectory["level"]}) as span:
        kb = knowledge_retrieval.retrieve(db, emotion["emotion_type"], intent,
                                          trajectory["level"])
        span.output = {"hit": kb["hit"],
                       "queries": kb["queries"],
                       "articles": [{"id": a["id"], "title": a["title"],
                                     "category": a["category"], "keyword": a["keyword"],
                                     "section": a["section"]}
                                    for a in kb["articles"]],
                       "reason": kb.get("reason", "")}
    knowledge_prompt = kb["prompt"]

    # 3.2) 会话所属角色
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    persona_id = session.persona_id if session else "nuan"

    # 4) 生成回复
    reply_usage: dict = {}
    with tracer.span(NODE_LLM_REPLY,
                     input_data={"user_message": content, "persona": persona_id,
                                 "model": model}) as span:
        if msg_type == "image" and not content.strip():
            reply = "我看到你分享的图片啦，谢谢你愿意和我分享这一刻～如果它让你想到什么、或有什么感受，都可以说给我听。"
            reply_source = "template"
        else:
            reply, reply_source, reply_usage = await llm_reply.generate(
                emotion, content, history=history, profile_text=profile_text,
                intent=intent, persona_id=persona_id,
                recent_replies=trajectory["recent_replies"],
                strategy_text=strategy_text, length_text=length_text,
                model=model, include_messages=True,
                knowledge_text=knowledge_prompt)
        span.output = {"reply": (reply or "")[:300], "source": reply_source}
        # 透出发给 LLM 的完整消息数组（含系统提示词/画像/历史）——打开黑盒
        if reply_usage.get("messages"):
            span.input = {"user_message": content, "model": model,
                          "persona": persona_id,
                          "messages": reply_usage["messages"]}
        elif reply_source == "template":
            span.input = {"user_message": content, "model": model,
                          "persona": persona_id, "fallback": True}
        usage = reply_usage.get("usage") or {}
        span.detail = {"model": reply_usage.get("model", ""),
                       "tokens": usage.get("total_tokens"),
                       "source": reply_source}
    # 记录回复生成的 token 消耗
    if reply_usage.get("model"):
        try:
            llm_usage.record(db, user_id, reply_usage["model"], "reply",
                             reply_usage.get("usage"), success=True, estimate_text=reply)
        except Exception:
            db.rollback()

    trigger = (content[:60] + "…") if len(content) > 60 else content

    # 5) 落库：用户消息 + 助手回复 + 情绪档案
    with tracer.span(NODE_PERSIST, input_data={"session": session_id}) as persist_span:
        user_msg = Message(
            session_id=session_id, role="user", content=content,
            msg_type=msg_type, image_url=image_url,
            emotion_type=emotion["emotion_type"], emotion_score=emotion["heal_score"],
            emotion_source=emotion.get("source", "rule"),
        )
        user_msg.detail = json.dumps(
            {"hits": emotion.get("hits", []), "high_risk": emotion.get("high_risk", []),
             "suggestion": emotion.get("suggestion", ""), "intent": intent}, ensure_ascii=False)
        assistant_msg = Message(session_id=session_id, role="assistant", content=reply)
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
        # assistant 消息关联链路 ID（持久化：刷新/重开后仍可查轨迹）
        assistant_msg.trace_id = tracer.trace_id

        # 8) 更新会话标题与时间
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if session and session.title == "新的对话":
            base = content if content else ("[图片]" if msg_type == "image" else "新的对话")
            session.title = (base[:20] + "…") if len(base) > 20 else base
        db.commit()
        db.refresh(user_msg)
        db.refresh(assistant_msg)
        persist_span.output = {"user_msg_id": user_msg.id, "reply_msg_id": assistant_msg.id}

    # 9) 记忆维基编译（每 EXTRACT_EVERY 条用户消息触发一次，后台执行，不阻塞回复）
    try:
        total = db.query(Message).join(ChatSession, ChatSession.id == Message.session_id) \
            .filter(ChatSession.user_id == user_id, Message.role == "user").count()
        from ..database import SessionLocal
        wiki_service.maybe_compile_async(SessionLocal, user_id, total)
    except Exception:
        pass

    # 10) 链路追踪异步落库（关联本次回复消息，不阻塞响应）
    tracer.flush(message_id=assistant_msg.id)

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
            "trace_id": tracer.trace_id,
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
        "trace_id": tracer.trace_id,
    }