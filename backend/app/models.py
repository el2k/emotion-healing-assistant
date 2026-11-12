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
    points = Column(Integer, default=999999)            # 积分（聊天消耗，每日可领）
    llm_model = Column(String(64), default="")          # 用户偏好的模型（空=用默认）
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    sessions = relationship("ChatSession", back_populates="user",
                            cascade="all, delete-orphan")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title = Column(String(100), default="新的对话")
    persona_id = Column(String(32), default="nuan")     # 多智能体角色
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

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
    trace_id = Column(String(36), default="", index=True)  # Agent 链路 ID（assistant 消息；持久化供随时回看）

    # 情绪相关（仅记录在用户消息上）
    emotion_type = Column(String(32), default="中性")   # 见 emotion/analyzer.py 类别
    emotion_score = Column(Float, default=0.0)          # 0~1，负向强度（越大越需安抚）
    emotion_source = Column(String(16), default="rule") # rule / llm
    detail = Column(Text, default="")                   # JSON 明细

    created_at = Column(DateTime(timezone=True), default=_utcnow)

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
    created_at = Column(DateTime(timezone=True), default=_utcnow, index=True)


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
    created_at = Column(DateTime(timezone=True), default=_utcnow, index=True)


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
    created_at = Column(DateTime(timezone=True), default=_utcnow, index=True)


class ForumLike(Base):
    __tablename__ = "forum_likes"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("forum_posts.id", ondelete="CASCADE"), index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)


class ForumComment(Base):
    __tablename__ = "forum_comments"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("forum_posts.id", ondelete="CASCADE"), index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    content = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), default=_utcnow, index=True)


class PointsLedger(Base):
    """积分流水：每日领取 / 聊天消耗 / 管理员调整。"""
    __tablename__ = "points_ledger"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    delta = Column(Integer, nullable=False)             # 正数增加 / 负数消耗
    balance = Column(Integer, default=0)                # 变动后余额（冗余，便于审计）
    reason = Column(String(32), default="")             # daily_claim / chat / admin_adjust
    note = Column(String(200), default="")
    created_at = Column(DateTime(timezone=True), default=_utcnow, index=True)


class UserWikiEntry(Base):
    """用户记忆维基（LLM Wiki 范式）：从对话中持续抽取、可与用户共建的事实条目。

    与统计画像（profile_service 动态计算）互补：
      统计画像回答「情绪模式如何」；
      记忆维基回答「用户是谁、具体在意哪些人与事」——这些只能靠积累，无法实时统计。
    """
    __tablename__ = "user_wiki_entries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category = Column(String(32), index=True)            # 基本情况/学业职业/重要他人/喜好偏好/目标计划/健康情况/情绪背景
    key = Column(String(120), default="")                # 简短标签，如「养的宠物」「备考方向」
    value = Column(Text, default="")                     # 事实描述（一句自然语言）
    evidence = Column(String(200), default="")           # 抽取依据（原话片段，便于用户核实）
    source = Column(String(16), default="rule")          # rule / llm / user
    confidence = Column(Float, default=0.6)              # 0~1
    pinned = Column(Boolean, default=False)              # 用户置顶/确认的事实
    hits = Column(Integer, default=1)                    # 同类事实被提及次数（用于置信度成长）
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class PaymentOrder(Base):
    """积分充值订单。支持微信/支付宝（Demo 模式模拟确认，生产模式对接真实网关）。"""
    __tablename__ = "payment_orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    amount_cents = Column(Integer, nullable=False)       # 支付金额（分）
    points = Column(Integer, nullable=False)             # 到账积分
    method = Column(String(16), default="wechat")         # wechat / alipay
    plan_id = Column(String(16), default="")             # 套餐 ID
    status = Column(String(16), default="pending", index=True)  # pending / paid / cancelled
    trade_no = Column(String(64), default="")            # 第三方支付流水号
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    paid_at = Column(DateTime(timezone=True))


class KnowledgeArticle(Base):
    """情绪知识库文章。"""
    __tablename__ = "knowledge_articles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(120), nullable=False)
    category = Column(String(32), index=True)           # 情绪认知 / 减压练习 / 焦虑应对 / 抑郁陪伴 / 睡眠作息 / 危机求助
    tags = Column(String(200), default="")              # 逗号分隔
    summary = Column(String(300), default="")
    content = Column(Text, default="")                  # markdown-lite 正文
    source = Column(String(200), default="")            # 参考来源
    read_minutes = Column(Integer, default=3)
    views = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=_utcnow, index=True)


class LLMModel(Base):
    """可用的 LLM 模型配置（管理后台维护，用户端可选）。

    free_quota_tokens 为人工填入的免费额度（阿里百炼控制台可查），
    剩余额度 = free_quota_tokens - 该模型累计 total_tokens。
    """
    __tablename__ = "llm_models"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(String(64), unique=True, index=True, nullable=False)  # 如 qwen-plus
    display_name = Column(String(64), default="")       # 展示名，如 通义千问 Plus
    description = Column(String(200), default="")       # 一句话说明（用户可见）
    enabled = Column(Boolean, default=True)             # 是否对用户开放
    is_default = Column(Boolean, default=False)         # 默认模型（全局唯一）
    free_quota_tokens = Column(Integer, default=0)      # 免费额度（token，0=未配置）
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class LLMUsageLog(Base):
    """每次 LLM 调用的 token 用量记录（按模型/场景/用户统计）。"""
    __tablename__ = "llm_usage_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    model = Column(String(64), index=True, nullable=False)   # 实际调用的模型
    scene = Column(String(24), default="reply")             # analyze / reply / reply_stream
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)               # 消耗的 token（花费）
    success = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, index=True)


class AgentTraceLog(Base):
    """Agent 链路追踪节点（参考 dsAgent 的 llm-trace-log 设计，Python 版）。

    一条用户消息（一个 trace_id）→ 多个节点（execution_order 递增）：
    规则情绪 → LLM 情绪 → 意图 → 记忆画像 → 会话策略 → LLM 回复 → 落库。
    每个节点记录进入/离开时间、耗时、成败、入参/出参 JSON、异常，
    让 LLM 管线不再是黑盒。
    """
    __tablename__ = "agent_trace_logs"

    id = Column(Integer, primary_key=True, index=True)
    trace_id = Column(String(36), index=True, nullable=False)   # 一次消息处理链路 ID
    session_id = Column(Integer, index=True, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    message_id = Column(Integer, index=True, nullable=True)     # 关联的 AI 回复消息 ID

    node_key = Column(String(48), nullable=False)               # RULE_EMOTION / LLM_REPLY ...
    node_type = Column(String(24), default="General")           # Emotion / LLM / Intent / Memory ...
    node_name = Column(String(64), default="")                  # 人类可读名称
    execution_order = Column(Integer, default=0)                # 同链路内顺序

    enter_time = Column(DateTime(timezone=True), default=_utcnow)
    leave_time = Column(DateTime(timezone=True))
    duration_ms = Column(Integer, default=0)                    # 节点耗时（毫秒）
    result = Column(Integer, default=1)                         # 1 成功 / 0 失败

    input_str = Column(Text, default="")                        # 入参 JSON
    output_str = Column(Text, default="")                       # 出参 JSON
    error_msg = Column(Text, default="")                        # 异常信息
    detail = Column(Text, default="")                           # 额外信息（模型/tokens 等）

    created_at = Column(DateTime(timezone=True), default=_utcnow, index=True)