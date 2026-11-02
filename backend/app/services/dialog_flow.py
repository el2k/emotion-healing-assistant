# -*- coding: utf-8 -*-
"""会话级对话流：情绪轨迹、陪伴策略升级、安抚去重与行动建议。

目标：让对话从「每条消息独立回应」升级为「有记忆、有递进」的陪伴——
用户连续低落时安慰会升级并给出可执行的小工具，而不是原地重复同一句话。
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import KnowledgeArticle, Message

_POSITIVE = {"喜悦", "平静", "感恩", "期待"}
_NEGATIVE = {"悲伤", "焦虑", "愤怒", "恐惧", "孤独", "委屈", "低落"}

# 策略等级
LEVEL_LABELS = {
    0: "轻共情",
    1: "稳定陪伴",
    2: "深度陪伴",
}

# 情绪 → 具体小工具（深度陪伴时给一个当下可做的事）
_TOOLS = [
    ("焦虑", {"kind": "exercise", "label": "🫁 试试 4-7-8 呼吸法", "detail": "吸气4秒、屏息7秒、缓慢呼气8秒，循环4次", "article": "呼吸"}),
    ("恐惧", {"kind": "exercise", "label": "🖐 试试 5-4-3-2-1 着陆", "detail": "说出看到的5样、摸到的4样、听到的3样…把注意力带回当下", "article": "着陆"}),
    ("愤怒", {"kind": "exercise", "label": "🖐 试试 5-4-3-2-1 着陆", "detail": "先让身体降温：说出周围的5样东西，再决定要不要回应", "article": "着陆"}),
    ("悲伤", {"kind": "heal", "label": "🩺 进入心理疗愈室", "detail": "有对应的专家角色陪你慢慢梳理", "article": "抑郁"}),
    ("低落", {"kind": "exercise", "label": "🌤 试试行为激活小步法", "detail": "只挑一件最小的事：喝一杯水、拉开窗帘晒5分钟太阳", "article": "行为激活"}),
    ("孤独", {"kind": "heal", "label": "🩺 进入心理疗愈室", "detail": "让专业的陪伴者接住你", "article": "陪伴"}),
    ("委屈", {"kind": "exercise", "label": "📝 把委屈写下来", "detail": "写「情境—想法—感受」三栏，写完往往就轻了一半", "article": "情绪日记"}),
]
_TOOL_DEFAULT = {"kind": "exercise", "label": "🫁 一起做几次慢呼吸", "detail": "跟着我：吸4秒，呼6秒", "article": "呼吸"}


def _polarity_of(emotion_type: str | None) -> int:
    if emotion_type in _POSITIVE:
        return 1
    if emotion_type in _NEGATIVE:
        return -1
    return 0


def compute_trajectory(db: Session, session_id: int, window: int = 6,
                       current_emotion: dict | None = None) -> dict:
    """基于本会话最近若干条用户消息，计算情绪轨迹与陪伴策略。

    current_emotion：本轮刚识别出的情绪（尚未落库），计入轨迹，
    使"连续第 N 轮低落"的升级在当轮即生效。
    """
    msgs = (db.query(Message)
            .filter(Message.session_id == session_id)
            .order_by(Message.created_at.desc())
            .limit(window * 2 + 4).all())
    msgs.reverse()

    user_turns = [m for m in msgs if m.role == "user"]
    assistant_turns = [m for m in msgs if m.role == "assistant"]

    class _Turn:
        def __init__(self, emotion_type, score):
            self.emotion_type = emotion_type
            self.emotion_score = score

    if current_emotion:
        user_turns = user_turns + [_Turn(current_emotion.get("emotion_type"),
                                         current_emotion.get("heal_score", 0))]

    recent_user = user_turns[-window:] if len(user_turns) > window else user_turns
    consecutive_neg = 0
    for m in reversed(recent_user):
        if _polarity_of(m.emotion_type) < 0:
            consecutive_neg += 1
        else:
            break

    neg_types = [m.emotion_type for m in recent_user if _polarity_of(m.emotion_type) < 0]
    dominant = ""
    if neg_types:
        dominant = max(set(neg_types), key=neg_types.count)
    neg_count = len(neg_types)
    max_intensity = max((m.emotion_score or 0 for m in recent_user), default=0)

    if consecutive_neg >= 3 or (consecutive_neg >= 2 and max_intensity >= 0.85):
        level = 2
    elif consecutive_neg >= 2:
        level = 1
    else:
        level = 0

    return {
        "level": level,
        "label": LEVEL_LABELS[level],
        "consecutive_neg": consecutive_neg,
        "neg_count": neg_count,
        "max_intensity": round(max_intensity, 2),
        "dominant_emotion": dominant,
        "recent_replies": [m.content for m in assistant_turns[-3:]],
    }


def pick_action(trajectory: dict, emotion: dict) -> dict | None:
    """根据轨迹与情绪选一个行动建议（None 表示本轮不给）。"""
    if bool(emotion.get("high_risk")):
        return {"kind": "crisis", "label": "☎️ 全国心理援助热线 12356",
                "detail": "24 小时，免费匿名。此刻的安全比什么都重要",
                "article": "热线"}
    if trajectory["level"] < 2:
        return None
    tool = dict(_TOOL_DEFAULT)
    for etype, t in _TOOLS:
        if etype == trajectory["dominant_emotion"] or etype == emotion.get("emotion_type"):
            tool = dict(t)
            break
    return tool


def find_article(db: Session, keyword: str) -> dict | None:
    """按关键词在知识库中找最匹配的文章，供行动卡片跳转。"""
    if not keyword:
        return None
    kw = f"%{keyword}%"
    a = (db.query(KnowledgeArticle)
         .filter(KnowledgeArticle.title.like(kw) | KnowledgeArticle.tags.like(kw))
         .first())
    if not a:
        a = (db.query(KnowledgeArticle)
             .filter(KnowledgeArticle.content.like(kw))
             .order_by(KnowledgeArticle.id).first())
    if not a:
        return None
    return {"id": a.id, "title": a.title, "category": a.category}


def strategy_prompt_text(trajectory: dict, emotion: dict) -> str:
    """生成注入 LLM 的「会话轨迹与策略」提示。"""
    if trajectory["level"] == 0:
        return ""
    lines = [f"【会话轨迹】本会话用户已连续 {trajectory['consecutive_neg']} 轮表达负向情绪"
             f"（主导情绪：{trajectory['dominant_emotion'] or '未明'}），请升级为「{trajectory['label']}」："]
    if trajectory["level"] >= 2:
        lines.append("先具体回应 TA 说过的事（引用细节，不用『加油』这类空话），"
                     "再温和给出一个当下就能做的小步骤，语气比平时更稳、更慢。")
    else:
        lines.append("多停留一会儿在共情上，不急着给建议。")
    if trajectory["recent_replies"]:
        quoted = "；".join(f"「{r[:40]}」" for r in trajectory["recent_replies"])
        lines.append(f"你最近的回复是 {quoted}，本轮不要重复相同句式与内容。")
    return "\n".join(lines)


def length_hint(intent: str) -> str:
    """按意图控制回复长度，避免倾诉时说教。"""
    return {
        "倾诉": "回复不超过 40 字：以接住情绪为主，本伦不给建议、不说教。",
        "求助": "回复 60~90 字：先一句共情，再给 1~2 个具体可执行的小步骤。",
        "分享": "回复轻快简短（30 字内），真诚地为 TA 高兴。",
        "闲聊": "回复简短自然，像朋友聊天。",
        "危机": "回复坚定而温暖：表达关心、劝不要伤害自己、引导联系热线 12356。",
    }.get(intent, "回复 30~90 字，温暖不说教。")
