# -*- coding: utf-8 -*-
"""配置中心：读取环境变量与 .env 文件（零第三方依赖）。"""
import os
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    """极简 .env 解析，仅支持 KEY=VALUE 与 # 注释。"""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


BASE_DIR = Path(__file__).resolve().parent.parent          # backend/
_load_dotenv(BASE_DIR / ".env")
_load_dotenv(BASE_DIR.parent / ".env")


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


class Settings:
    # --- 服务 ---
    APP_NAME = os.getenv("APP_NAME", "情绪感知聊天治愈助手")
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8000"))
    DEBUG = _bool("DEBUG", True)

    # --- 数据库 ---
    DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "data" / "healing.db"))

    # --- 认证 ---
    JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me-9f8a7b6c5d4e3f2a1b0c")
    JWT_ALG = "HS256"
    TOKEN_EXPIRE_MINUTES = int(os.getenv("TOKEN_EXPIRE_MINUTES", "1440"))

    # --- 大模型(可选，配置后开启深度情绪分析) ---
    LLM_ENABLED = _bool("LLM_ENABLED", False)
    LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    LLM_API_KEY = os.getenv("LLM_API_KEY", "")
    LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
    LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "30"))

    # --- 管理平台初始管理员(首次启动自动创建) ---
    ADMIN_PHONE = os.getenv("ADMIN_PHONE", "13800000000")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")


settings = Settings()