# -*- coding: utf-8 -*-
"""正能量社区论坛：发帖、列表/搜索、详情、点赞、评论、媒体上传。"""
import json
import os
import uuid
from collections import Counter
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import ForumComment, ForumLike, ForumPost, User
from ..schemas import CommentIn, PostIn

router = APIRouter(prefix="/api/forum", tags=["forum"])

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
_IMG_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
_VID_EXT = {".mp4", ".webm", ".mov"}


@router.post("/upload")
async def upload_media(file: UploadFile = File(...),
                       user: User = Depends(get_current_user)):
    """上传论坛媒体：图片或短视频。"""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext in _IMG_EXT:
        media_type, limit = "image", 8 * 1024 * 1024
    elif ext in _VID_EXT:
        media_type, limit = "video", 50 * 1024 * 1024
    else:
        raise HTTPException(400, "仅支持 png/jpg/jpeg/webp/gif 图片或 mp4/webm/mov 视频")
    data = await file.read()
    if len(data) > limit:
        raise HTTPException(400, f"文件过大（{'图片上限8MB' if media_type == 'image' else '视频上限50MB'}）")
    name = f"{uuid.uuid4().hex}{ext}"
    (UPLOAD_DIR / name).write_bytes(data)
    return {"url": f"/uploads/{name}", "type": media_type}


def _tags_list(s: str) -> list[str]:
    return [t for t in (s or "").split(",") if t]


def _imgs(s: str) -> list[str]:
    try:
        return json.loads(s) if s else []
    except Exception:
        return []


def _is_video(url: str) -> bool:
    return url.lower().endswith((".mp4", ".webm", ".mov"))


def _blocks_of(post: ForumPost) -> list[dict]:
    """返回图文混排块；兼容旧数据（仅有 content + image_urls）。"""
    if post.blocks:
        try:
            parsed = json.loads(post.blocks)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
    blocks = []
    if post.content:
        blocks.append({"type": "text", "text": post.content})
    for u in _imgs(post.image_urls):
        blocks.append({"type": "video" if _is_video(u) else "image", "url": u})
    return blocks


def _serialize(post: ForumPost, nickname: str, like_count: int,
               comment_count: int, liked: bool) -> dict:
    return {
        "id": post.id,
        "title": post.title,
        "content": post.content,
        "excerpt": (post.content[:70] + "…") if len(post.content) > 70 else post.content,
        "tags": _tags_list(post.tags),
        "images": _imgs(post.image_urls),
        "blocks": _blocks_of(post),
        "author": nickname,
        "user_id": post.user_id,
        "like_count": like_count,
        "comment_count": comment_count,
        "liked": liked,
        "created_at": post.created_at.isoformat() if post.created_at else None,
    }


@router.get("/posts")
def list_posts(q: str = Query("", max_length=100),
               tag: str = Query("", max_length=40),
               page: int = Query(1, ge=1),
               page_size: int = Query(12, ge=1, le=50),
               user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    query = db.query(ForumPost, User.nickname).join(User, User.id == ForumPost.user_id)
    if q:
        like = f"%{q}%"
        query = query.filter(ForumPost.title.like(like) | ForumPost.content.like(like)
                             | ForumPost.tags.like(like))
    if tag:
        query = query.filter(ForumPost.tags.like(f"%{tag}%"))
    total = query.count()
    rows = (query.order_by(ForumPost.created_at.desc())
            .offset((page - 1) * page_size).limit(page_size).all())
    post_ids = [p.id for p, _ in rows]

    like_counts = dict(db.query(ForumLike.post_id, func.count(ForumLike.id))
                       .filter(ForumLike.post_id.in_(post_ids))
                       .group_by(ForumLike.post_id).all()) if post_ids else {}
    comment_counts = dict(db.query(ForumComment.post_id, func.count(ForumComment.id))
                          .filter(ForumComment.post_id.in_(post_ids))
                          .group_by(ForumComment.post_id).all()) if post_ids else {}
    my_likes = set(x[0] for x in db.query(ForumLike.post_id)
                   .filter(ForumLike.user_id == user.id,
                           ForumLike.post_id.in_(post_ids)).all()) if post_ids else set()

    items = [_serialize(p, nick, like_counts.get(p.id, 0),
                        comment_counts.get(p.id, 0), p.id in my_likes)
             for p, nick in rows]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/posts")
def create_post(data: PostIn, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    # 优先使用图文混排 blocks；兼容仅 content + image_urls 的旧调用
    blocks = data.blocks or []
    if not blocks:
        if data.content.strip():
            blocks.append({"type": "text", "text": data.content.strip()})
        for u in data.image_urls:
            blocks.append({"type": "video" if _is_video(u) else "image", "url": u})

    clean = []
    for b in blocks:
        t = b.get("type")
        if t == "text" and str(b.get("text", "")).strip():
            clean.append({"type": "text", "text": str(b["text"]).strip()})
        elif t in ("image", "video") and b.get("url"):
            clean.append({"type": t, "url": str(b["url"])})
    if not clean:
        raise HTTPException(400, "帖子内容不能为空")

    content = "\n".join(b["text"] for b in clean if b["type"] == "text")
    media = [b["url"] for b in clean if b["type"] in ("image", "video")]

    post = ForumPost(
        user_id=user.id,
        title=data.title.strip(),
        content=content,
        tags=",".join(t.strip() for t in data.tags if t.strip()),
        image_urls=json.dumps(media, ensure_ascii=False),
        blocks=json.dumps(clean, ensure_ascii=False),
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return {"id": post.id, "ok": True}


@router.get("/posts/{post_id}")
def post_detail(post_id: int, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    row = (db.query(ForumPost, User.nickname).join(User, User.id == ForumPost.user_id)
           .filter(ForumPost.id == post_id).first())
    if not row:
        raise HTTPException(404, "帖子不存在")
    post, nickname = row
    like_count = db.query(func.count(ForumLike.id)).filter(
        ForumLike.post_id == post_id).scalar() or 0
    liked = db.query(ForumLike).filter(
        ForumLike.post_id == post_id, ForumLike.user_id == user.id).first() is not None
    comments = (db.query(ForumComment, User.nickname)
                .join(User, User.id == ForumComment.user_id)
                .filter(ForumComment.post_id == post_id)
                .order_by(ForumComment.created_at.asc()).all())
    data = _serialize(post, nickname, like_count, len(comments), liked)
    data["comments"] = [
        {"id": c.id, "content": c.content, "author": nick,
         "user_id": c.user_id, "mine": c.user_id == user.id,
         "created_at": c.created_at.isoformat() if c.created_at else None}
        for c, nick in comments
    ]
    return data


@router.delete("/posts/{post_id}")
def delete_post(post_id: int, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    post = db.query(ForumPost).filter(ForumPost.id == post_id).first()
    if not post:
        raise HTTPException(404, "帖子不存在")
    if post.user_id != user.id and user.role != "admin":
        raise HTTPException(403, "无权删除")
    db.query(ForumComment).filter(ForumComment.post_id == post_id).delete()
    db.query(ForumLike).filter(ForumLike.post_id == post_id).delete()
    db.delete(post)
    db.commit()
    return {"ok": True}


@router.post("/posts/{post_id}/like")
def toggle_like(post_id: int, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    if not db.query(ForumPost).filter(ForumPost.id == post_id).first():
        raise HTTPException(404, "帖子不存在")
    existing = db.query(ForumLike).filter(
        ForumLike.post_id == post_id, ForumLike.user_id == user.id).first()
    if existing:
        db.delete(existing)
        liked = False
    else:
        db.add(ForumLike(post_id=post_id, user_id=user.id))
        liked = True
    db.commit()
    count = db.query(func.count(ForumLike.id)).filter(
        ForumLike.post_id == post_id).scalar() or 0
    return {"liked": liked, "like_count": count}


@router.post("/posts/{post_id}/comments")
def add_comment(post_id: int, data: CommentIn, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    if not db.query(ForumPost).filter(ForumPost.id == post_id).first():
        raise HTTPException(404, "帖子不存在")
    c = ForumComment(post_id=post_id, user_id=user.id, content=data.content.strip())
    db.add(c)
    db.commit()
    db.refresh(c)
    return {"id": c.id, "content": c.content, "author": user.nickname,
            "created_at": c.created_at.isoformat() if c.created_at else None}


@router.delete("/comments/{comment_id}")
def delete_comment(comment_id: int, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    c = db.query(ForumComment).filter(ForumComment.id == comment_id).first()
    if not c:
        raise HTTPException(404, "评论不存在")
    if c.user_id != user.id and user.role != "admin":
        raise HTTPException(403, "无权删除")
    db.delete(c)
    db.commit()
    return {"ok": True}


@router.get("/tags")
def hot_tags(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(ForumPost.tags).all()
    counter = Counter()
    for (tags,) in rows:
        for t in _tags_list(tags):
            counter[t] += 1
    return [{"name": k, "count": v} for k, v in counter.most_common(20)]