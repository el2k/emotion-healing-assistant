# -*- coding: utf-8 -*-
"""意图识别：判断用户这句是在倾诉、求助、分享、闲聊还是危机求助。

借鉴 emotional_chat 等项目的"混合式意图识别"思路，这里用关键词规则实现，
轻量、离线可用；接入大模型后可由 LLM 结果覆盖。
"""

# 意图 -> 关键词
INTENT_KEYWORDS = {
    "危机": ["不想活", "想死", "轻生", "活不下去", "自杀", "结束生命", "绝望",
             "想消失", "想解脱", "伤害自己", "自残", "没有我会更好"],
    "求助": ["怎么办", "帮我", "我该", "如何", "怎么才能", "有没有办法",
             "建议", "教我", "求助", "能不能帮"],
    "分享": ["今天", "刚刚", "你知道吗", "告诉你", "跟你分享", "发生",
             "哈哈", "太好了", "居然"],
    "倾诉": ["难过", "累", "委屈", "孤独", "压力", "烦", "好难受", "撑不住",
             "想哭", "睡不着", "焦虑", "害怕", "好累"],
    "闲聊": ["你好", "在吗", "你是谁", "随便聊聊", "聊聊", "嗯", "在不在"],
}


def detect(text: str, high_risk: bool = False) -> str:
    """返回意图标签。优先级：危机 > 求助 > 倾诉 > 分享 > 闲聊。"""
    if high_risk:
        return "危机"
    text = text or ""
    # 危机优先
    for kw in INTENT_KEYWORDS["危机"]:
        if kw in text:
            return "危机"
    order = ["求助", "倾诉", "分享", "闲聊"]
    for intent in order:
        for kw in INTENT_KEYWORDS[intent]:
            if kw in text:
                return intent
    return "倾诉"  # 默认按倾诉处理（治愈助手场景）


# 意图优先级（供解释输出）
_PRIORITY = ["危机", "求助", "倾诉", "分享", "闲聊"]


def explain(text: str, high_risk: bool = False) -> dict:
    """意图判定过程解释（供 Agent 链路追踪展示，不影响 detect 主逻辑）。

    返回：{intent, path, hits} — path 为判定路径，hits 为命中的关键词及所属意图。
    """
    if high_risk:
        return {"intent": "危机", "path": "情绪引擎高风险 → 直接判定危机",
                "hits": [{"keyword": "(high_risk)", "intent": "危机"}]}
    text = text or ""
    all_hits = [{"keyword": kw, "intent": label}
                for label in _PRIORITY for kw in INTENT_KEYWORDS.get(label, [])
                if kw in text]
    # 全部命中按优先级排序展示
    order_idx = {label: i for i, label in enumerate(_PRIORITY)}
    all_hits.sort(key=lambda h: order_idx.get(h["intent"], 99))
    if all_hits:
        # 与 detect 一致：最高优先级意图的第一个命中关键词触发判定
        top = all_hits[0]
        return {"intent": top["intent"],
                "path": f"关键词命中「{top['keyword']}」→ {top['intent']}",
                "hits": all_hits[:8]}
    return {"intent": "倾诉", "path": "无关键词命中 → 默认倾诉（治愈场景兜底）",
            "hits": []}