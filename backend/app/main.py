# -*- coding: utf-8 -*-
"""FastAPI 应用入口：注册路由、CORS、初始化管理员、托管前端静态文件。
含请求指标中间件、断路器、深度健康检查与结构化错误响应。"""
import os
import sys
import time
import traceback
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import SessionLocal, init_db
from .models import User
from .routers import admin, auth, chat, emotion, fortune, forum, knowledge, payments, points, profile
from .security import hash_password
from .observability import metrics, llm_breaker
from .security.rate_limit import api_limiter

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


# 生产环境关闭自动文档（/docs、/redoc、/openapi.json），
# 避免接口结构暴露给攻击者。开发时用环境变量 DEBUG 控制。
app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# API 限流中间件：单 IP 60秒/200次（防接口批量扫描 DoS）
# 登录/注册有更严的专属限流（auth.py 内），不在本层重复限制
# ============================================================
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    path = request.url.path
    _skip = path.startswith(("/assets", "/uploads", "/models", "/api/health")
                            or path in ("/api/auth/login", "/api/auth/register")
                            or not path.startswith(("/api",)))
    if not _skip:
        fwd = request.headers.get("x-forwarded-for")
        ip = fwd.split(",")[0].strip() if fwd else (
            request.client.host if request.client else "unknown")
        if not api_limiter.check(ip):
            return JSONResponse(
                status_code=429,
                content={"detail": "请求过于频繁，请稍后重试"},
                headers={"Retry-After": "60"},
            )
    return await call_next(request)


# ============================================================
# 请求指标中间件：记录每个请求的延迟与状态码
# ============================================================
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.time()
    error_detail = ""
    try:
        response = await call_next(request)
        latency_ms = (time.time() - start) * 1000
        # 记录非静态资源的请求（静态文件性能不重要）
        path = request.url.path
        if not path.startswith(("/assets", "/uploads", "/models")):
            metrics.record_request(path, request.method, response.status_code, latency_ms)
        return response
    except Exception as exc:
        latency_ms = (time.time() - start) * 1000
        error_detail = f"{type(exc).__name__}: {str(exc)[:200]}"
        metrics.record_request(request.url.path, request.method, 500, latency_ms, error_detail)
        # 未处理异常的完整堆栈打到 stderr（docker compose logs 可见），便于定位 500
        print(f"[ERROR] {request.method} {request.url.path} -> {error_detail}", file=sys.stderr)
        traceback.print_exc()
        # 结构化错误：绝不把失败包装成 200
        return JSONResponse(
            status_code=500,
            content={
                "detail": "服务内部错误，请稍后重试",
                "error_type": type(exc).__name__,
                "request_id": f"req_{int(time.time() * 1000)}",
            },
        )


# ============================================================
# LLM 断路器： OPEN 时跳过调用直接走降级（不阻塞请求）
# ============================================================
def llm_available() -> bool:
    """检查 LLM 是否可调用（配置启用 + 断路器未 OPEN）。"""
    return bool(settings.LLM_ENABLED and settings.LLM_API_KEY) and llm_breaker.can_call()


app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(emotion.router)
app.include_router(forum.router)
app.include_router(fortune.router)
app.include_router(knowledge.router)
app.include_router(payments.router)
app.include_router(points.router)
app.include_router(profile.router)
app.include_router(admin.router)

# 图片上传目录（与 routers/chat.py 保持一致：backend/uploads）
UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


# ============================================================
# 健康检查：浅层（liveness）+ 深层（readiness）
# ============================================================
@app.get("/api/health")
def health():
    """浅层健康检查：进程存活。K8s/容器探针用。"""
    return {"status": "ok", "app": settings.APP_NAME,
            "llm": settings.LLM_ENABLED, "timestamp": int(time.time())}


@app.get("/api/health/deep")
def health_deep():
    """深度健康检查：检查依赖可用性。部署就绪探针 / 监控告警用。"""
    checks = {}

    # 1. 数据库连接
    try:
        from sqlalchemy import text as _text
        db = SessionLocal()
        db.execute(_text("SELECT 1"))
        db.close()
        checks["database"] = {"status": "ok", "message": "连接正常"}
    except Exception as e:
        checks["database"] = {"status": "fail", "message": str(e)[:100]}

    # 2. 磁盘空间
    try:
        import shutil
        total, used, free = shutil.disk_usage(Path(__file__).parent)
        free_pct = free / total * 100
        checks["disk"] = {
            "status": "ok" if free_pct > 10 else "warn",
            "message": f"剩余 {free_pct:.0f}%（{free // (1024**3):.1f}GB）",
        }
    except Exception:
        checks["disk"] = {"status": "unknown", "message": "无法检测"}

    # 3. LLM 断路器状态
    breaker = llm_breaker.status()
    checks["llm_circuit"] = {
        "status": ("ok" if breaker["state"] == "closed" else
                   "degraded" if breaker["state"] == "half_open" else "fail"),
        "message": f"断路器 {breaker['state']}，"
                   f"连续失败 {breaker['failure_count']} 次"
                   + (f"，最近错误: {breaker['last_error'][:60]}" if breaker["last_error"] else ""),
    }

    # 4. 最近 5 分钟错误率
    try:
        summary = metrics.request_summary(minutes=5)
        err_rate = summary["error_rate"]
        checks["recent_errors"] = {
            "status": "ok" if err_rate < 5 else "warn" if err_rate < 20 else "fail",
            "message": f"5 分钟 {summary['count']} 次请求，错误率 {err_rate}%"
            if summary["count"] else "5 分钟内无请求",
        }
    except Exception:
        checks["recent_errors"] = {"status": "unknown", "message": "无法检测"}

    # 综合状态
    all_ok = all(c["status"] == "ok" for c in checks.values())
    any_fail = any(c["status"] == "fail" for c in checks.values())
    overall = "ok" if all_ok else "degraded" if not any_fail else "fail"

    return {
        "status": overall,
        "checks": checks,
        "timestamp": int(time.time()),
    }


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
        return JSONResponse(
            status_code=404,
            content={"detail": "页面不存在", "path": full_path},
        )
