# -*- coding: utf-8 -*-
"""数据模型：用户、会话、消息、情绪档案。"""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from .database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(20), unique=True, index=True, nullable=False)
    nickname = Column(String(50), default="")
    avatar = Column(String(255), default="")             # 头像 URL 或 emoji
    password_hash = Column(String(256), nullable=False)
    role = Column(String(16), default="user")          # user / admin
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow)

    sessions = relationship("ChatSession", back_populates="user",
                            cascade="all, delete-orphan")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title = Column(String(100), default="新的对话")
    persona_id = Column(String(32), default="nuan")     # 多智能体角色
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    user = relationship("User", back_populates="sessions")
    messages = relationship("Message", back_populates="session",
                            cascade="all, delete-orphan", order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"),
                        index=True)
    role = Column(String(16), nullable=False)          # user / assistant
    content = Column(Text, nullable=False)
    msg_type = Column(String(16), default="text")       # text / image / voice
    image_url = Column(String(255), default="")         # 图片消息的地址

    # 情绪相关（仅记录在用户消息上）
    emotion_type = Column(String(32), default="中性")   # 见 emotion/analyzer.py 类别
    emotion_score = Column(Float, default=0.0)          # 0~1，负向强度（越大越需安抚）
    emotion_source = Column(String(16), default="rule") # rule / llm
    detail = Column(Text, default="")                   # JSON 明细

    created_at = Column(DateTime, default=_utcnow)

    session = relationship("ChatSession", back_populates="messages")


class EmotionRecord(Base):
    """情绪档案：按(用户,时间)记录的情绪快照，用于管理后台趋势分析。"""
    __tablename__ = "emotion_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_id = Column(Integer, index=True, nullable=True)
    emotion_type = Column(String(32), nullable=False)
    score = Column(Float, default=0.0)                  # 0~1 情绪强度
    polarity = Column(Integer, default=0)               # -1 负 / 0 中 / 1 正
    source = Column(String(16), default="rule")
    intent = Column(String(16), default="")             # 倾诉/求助/分享/闲聊/危机
    trigger = Column(String(120), default="")           # 触发情绪的原话片段（事件）
    detail = Column(Text, default="")
    created_at = Column(DateTime, default=_utcnow, index=True)


class EmotionCalibration(Base):
    """用户个人情绪校准：记录用户对识别结果的纠正，用于个性化回馈。"""
    __tablename__ = "emotion_calibrations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    message_id = Column(Integer, index=True, nullable=True)
    record_id = Column(Integer, index=True, nullable=True)
    original_emotion = Column(String(32), default="")   # 系统原判
    corrected_emotion = Column(String(32), nullable=False)  # 用户校准结果
    text = Column(String(200), default="")              # 原话片段
    created_at = Column(DateTime, default=_utcnow, index=True)


class ForumPost(Base):
    """正能量社区帖子。"""
    __tablename__ = "forum_posts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title = Column(String(120), default="")
    content = Column(Text, default="")
    tags = Column(String(200), default="")              # 逗号分隔
    image_urls = Column(Text, default="")               # JSON 数组字符串
    blocks = Column(Text, default="")                   # JSON：图文混排块（text/image/video）
    created_at = Column(DateTime, default=_utcnow, index=True)


class ForumLike(Base):
    __tablename__ = "forum_likes"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("forum_posts.id", ondelete="CASCADE"), index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at = Column(DateTime, default=_utcnow)


class ForumComment(Base):
    __tablename__ = "forum_comments"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("forum_posts.id", ondelete="CASCADE"), index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    content = Column(Text, default="")
    created_at = Column(DateTime, default=_utcnow, index=True)