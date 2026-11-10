# -*- coding: utf-8 -*-
"""用户画像与记忆维基路由。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import User, UserWikiEntry
from ..services import profile_service, wiki_service

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("/me/portrait")
def my_portrait(days: int = Query(90, ge=7, le=3650),
                db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    """我的长期画像：基础信息 / 情绪特征 / 话题偏好 / 校准偏好 / 摘要 / 事实卡。"""
    return profile_service.build_portrait(db, user.id, days)


# ---------------- 记忆维基（LLM Wiki） ----------------
@router.get("/me/wiki")
def my_wiki(db: Session = Depends(get_db),
            user: User = Depends(get_current_user)):
    """我的记忆维基：结构化条目 + markdown 渲染。用户可核实、可纠错。"""
    entries = wiki_service.get_wiki(db, user.id)
    return {
        "entries": entries,
        "markdown": wiki_service.render_wiki_markdown(db, user.id),
        "stats": {
            "total": len(entries),
            "by_source": {
                "llm": sum(1 for e in entries if e["source"] == "llm"),
                "rule": sum(1 for e in entries if e["source"] == "rule"),
                "user": sum(1 for e in entries if e["source"] == "user"),
            },
        },
    }


class WikiEntryIn(BaseModel):
    key: str
    value: str
    category: str = "基本情况"
    evidence: str = ""


@router.post("/me/wiki")
def add_wiki_entry(data: WikiEntryIn, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    """用户自行补充事实（source=user，最高置信、置顶）。"""
    if not data.key.strip() or not data.value.strip():
        raise HTTPException(400, "标签和内容都不能为空")
    entry = UserWikiEntry(
        user_id=user.id,
        category=data.category if data.category in wiki_service.CATEGORIES else "基本情况",
        key=data.key.strip()[:120], value=data.value.strip()[:300],
        evidence="用户自行补充", source="user", confidence=0.95, pinned=True,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {"ok": True, "id": entry.id}


@router.delete("/me/wiki/{entry_id}")
def delete_wiki_entry(entry_id: int, db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    """用户删除错误事实（纠错权在自己手里）。"""
    entry = (db.query(UserWikiEntry)
             .filter(UserWikiEntry.id == entry_id, UserWikiEntry.user_id == user.id)
             .first())
    if not entry:
        raise HTTPException(404, "条目不存在")
    db.delete(entry)
    db.commit()
    return {"ok": True}
