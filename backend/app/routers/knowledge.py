# -*- coding: utf-8 -*-
"""知识库路由：文章列表、分类统计、详情阅读。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import KnowledgeArticle, User
from ..knowledge_data import ARTICLES

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


def _seed_if_empty(db: Session) -> None:
    """首次启动时把内置文章入库（幂等）。"""
    if db.query(func.count(KnowledgeArticle.id)).scalar():
        return
    for a in ARTICLES:
        db.add(KnowledgeArticle(
            title=a["title"], category=a["category"], tags=a["tags"],
            summary=a["summary"], content=a["content"], source=a["source"],
            read_minutes=a["read_minutes"],
        ))
    db.commit()


@router.get("/categories")
def categories(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _seed_if_empty(db)
    rows = (db.query(KnowledgeArticle.category, func.count(KnowledgeArticle.id))
            .group_by(KnowledgeArticle.category).all())
    order = [c for c in ["情绪认知", "减压练习", "焦虑应对", "抑郁陪伴", "睡眠作息", "危机求助"]]
    items = [{"name": k, "count": v} for k, v in rows]
    items.sort(key=lambda x: order.index(x["name"]) if x["name"] in order else 99)
    return items


@router.get("/articles")
def articles(category: str = "", q: str = "",
             page: int = Query(1, ge=1), page_size: int = Query(12, ge=1, le=50),
             db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _seed_if_empty(db)
    query = db.query(KnowledgeArticle)
    if category:
        query = query.filter(KnowledgeArticle.category == category)
    if q.strip():
        kw = f"%{q.strip()}%"
        query = query.filter(
            KnowledgeArticle.title.like(kw) | KnowledgeArticle.summary.like(kw)
            | KnowledgeArticle.content.like(kw) | KnowledgeArticle.tags.like(kw))
    total = query.count()
    rows = (query.order_by(KnowledgeArticle.id)
            .offset((page - 1) * page_size).limit(page_size).all())
    return {
        "total": total,
        "items": [{
            "id": r.id, "title": r.title, "category": r.category,
            "tags": [t for t in (r.tags or "").split(",") if t],
            "summary": r.summary, "read_minutes": r.read_minutes,
            "views": r.views,
        } for r in rows],
    }


@router.get("/articles/{article_id}")
def article_detail(article_id: int, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    _seed_if_empty(db)
    r = db.query(KnowledgeArticle).filter(KnowledgeArticle.id == article_id).first()
    if not r:
        raise HTTPException(404, "文章不存在")
    r.views = (r.views or 0) + 1
    db.commit()
    return {
        "id": r.id, "title": r.title, "category": r.category,
        "tags": [t for t in (r.tags or "").split(",") if t],
        "summary": r.summary, "content": r.content, "source": r.source,
        "read_minutes": r.read_minutes, "views": r.views,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }