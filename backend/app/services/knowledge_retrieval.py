# -*- coding: utf-8 -*-
"""知识库检索（轻量 RAG）：按情绪/意图从知识库文章中检索相关段落注入提示词。

设计原则：
- 触发条件收窄：仅在「用户求助」或「连续负向（level≥2）」时检索，闲聊/分享不查，
  控制提示词长度与 token 成本；
- 检索策略：情绪/意图 → 候选关键词组；关键词按 词缀匹配 title/tags，再模糊兜底 content；
- 注入形态：截取文章最相关的 1~2 个小节（markdown ## 分段），以
  「参考资料（可自然借鉴，不要照读、不要提及来源）」注入，角色仍按人设说话；
- 全程可解释：检索词、命中文章、注入段落全部返回（供 Agent 轨迹 KNOWLEDGE_RETRIEVAL 节点展示）。
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import KnowledgeArticle

# 情绪 → 检索关键词（与知识库 title/tags 对齐）
_EMOTION_QUERIES = {
    "焦虑": ["呼吸", "着陆", "焦虑"],
    "恐惧": ["着陆", "惊恐"],
    "愤怒": ["着陆", "情绪不是敌人"],
    "悲伤": ["抑郁", "陪伴"],
    "低落": ["行为激活", "抑郁"],
    "孤独": ["陪伴", "情绪日记"],
    "委屈": ["情绪日记", "情绪粒度"],
    # 正向情绪不检索
}

# 意图 → 附加关键词
_INTENT_QUERIES = {
    "求助": ["专业帮助"],       # 主动求助时补一篇「何时需要专业帮助」
    "危机": ["热线"],
}

_MAX_ARTICLES = 2                    # 最多注入文章数
_MAX_SECTION_CHARS = 420             # 每篇文章截取的最大字符数


def _split_sections(content: str) -> list[tuple[str, str]]:
    """markdown 内容按 ## 分段：[(段标题, 段文本), ...]。"""
    sections: list[tuple[str, str]] = []
    cur_title, buf = "", []
    for line in (content or "").splitlines():
        if line.startswith("## "):
            if buf:
                sections.append((cur_title, "\n".join(buf).strip()))
            cur_title, buf = line[3:].strip(), []
        else:
            buf.append(line)
    if buf:
        sections.append((cur_title, "\n".join(buf).strip()))
    return sections


def _pick_sections(content: str, keyword: str) -> str:
    """选取与关键词最相关的段落：优先段标题/正文含关键词，否则取「步骤/方法」类段落。"""
    sections = _split_sections(content)
    if not sections:
        return (content or "")[:_MAX_SECTION_CHARS]
    scored = []
    for i, (title, text) in enumerate(sections):
        score = 0
        if keyword and keyword in title:
            score += 3
        if keyword and keyword in text:
            score += 2
        if any(k in title for k in ("步骤", "方法", "怎么做", "怎么用", "练习")):
            score += 2
        scored.append((score, i, title, text))
    scored.sort(key=lambda x: (-x[0], x[1]))
    out = []
    used = 0
    for score, i, title, text in scored[:2]:
        if score <= 0 and used > 0:
            break
        piece = (f"{title}：" if title else "") + text
        if used + len(piece) > _MAX_SECTION_CHARS:
            piece = piece[:_MAX_SECTION_CHARS - used] + "…"
        out.append(piece)
        used += len(piece)
        if used >= _MAX_SECTION_CHARS:
            break
    return "\n".join(out) if out else sections[0][1][:_MAX_SECTION_CHARS]


def retrieve(db: Session, emotion_type: str | None, intent: str | None,
             trajectory_level: int = 0) -> dict:
    """检索入口：返回 {hit(bool), queries, articles, prompt}。

    未触发（轻共情/闲聊/正向）返回 hit=False，prompt 为空——不注入、不耗 token。
    """
    queries: list[str] = []
    for q in _EMOTION_QUERIES.get(emotion_type or "", []):
        if q not in queries:
            queries.append(q)
    for q in _INTENT_QUERIES.get(intent or "", []):
        if q not in queries:
            queries.append(q)
    should = bool(queries) and (intent in ("求助", "危机") or trajectory_level >= 2)
    if not should:
        return {"hit": False, "queries": queries, "articles": [], "prompt": "",
                "reason": "未触发检索（非求助且连续负向不足 2 轮）"}

    articles_out = []
    seen_ids: set[int] = set()
    for kw in queries:
        if len(articles_out) >= _MAX_ARTICLES:
            break
        a = (db.query(KnowledgeArticle)
              .filter(KnowledgeArticle.title.like(f"%{kw}%")
                      | KnowledgeArticle.tags.like(f"%{kw}%"))
              .order_by(KnowledgeArticle.id).first())
        if not a:
            a = (db.query(KnowledgeArticle)
                 .filter(KnowledgeArticle.content.like(f"%{kw}%"))
                 .order_by(KnowledgeArticle.id).first())
        if a and a.id not in seen_ids:
            seen_ids.add(a.id)
            articles_out.append({
                "id": a.id, "title": a.title, "category": a.category,
                "keyword": kw,
                "section": _pick_sections(a.content or "", kw),
            })

    if not articles_out:
        return {"hit": False, "queries": queries, "articles": [], "prompt": "",
                "reason": f"关键词 {queries} 未命中任何文章"}

    parts = ["【参考资料（来自情绪知识库，可自然借鉴其中的方法与视角，"
             "不要照读原文、不要提及资料来源）】"]
    for i, art in enumerate(articles_out, 1):
        parts.append(f"{i}. 《{art['title']}》（{art['category']}）\n{art['section']}")
    return {"hit": True, "queries": queries, "articles": articles_out,
            "prompt": "\n".join(parts)}