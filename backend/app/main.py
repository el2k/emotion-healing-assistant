# -*- coding: utf-8 -*-
"""FastAPI 应用入口：注册路由、CORS、初始化管理员、托管前端静态文件。"""
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import SessionLocal, init_db
from .models import User
from .routers import admin, auth, chat, emotion, forum
from .security import hash_password

FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


def _seed_admin() -> None:
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.phone == settings.ADMIN_PHONE).first():
            db.add(User(
                phone=settings.ADMIN_PHONE,
                nickname="管理员",
                password_hash=hash_password(settings.ADMIN_PASSWORD),
                role="admin",
            ))
            db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from .database import init_db
    init_db()
    _seed_admin()
    yield


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(emotion.router)
app.include_router(forum.router)
app.include_router(admin.router)

# 图片上传目录（与 routers/chat.py 保持一致：backend/uploads）
UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME, "llm": settings.LLM_ENABLED}


# 生产环境可托管前端构建产物（若 dist 存在）
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"),
              name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        target = FRONTEND_DIST / full_path
        if full_path and target.is_file():
            return FileResponse(target)
        index = FRONTEND_DIST / "index.html"
        if index.exists():
            return FileResponse(index)
        return {"detail": "前端未构建，请运行 npm run build"}