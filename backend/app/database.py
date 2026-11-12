# -*- coding: utf-8 -*-
"""数据库引擎与会话管理：双驱动（PostgreSQL 优先 / SQLite 回落）。

- DATABASE_URL 配置了 PostgreSQL 时走 psycopg 驱动：
  连接池 5 常驻 + 5 溢出（服务端总上限 100、多项目共享，本项目不超过 10），
  pool_pre_ping 防止共享实例上空闲连接被回收导致的第一请求失败；
- 否则回落本地 SQLite（开发/测试模式，行为与历史版本一致）。
- 时间约定：库内一律存 UTC（timestamptz）；展示时区（Asia/Shanghai）由应用层转换。
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import BASE_DIR, settings

# 确保数据目录存在（SQLite 模式需要）
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

IS_POSTGRES = bool(settings.DATABASE_URL)


def _build_engine():
    if IS_POSTGRES:
        url = settings.DATABASE_URL
        # 统一使用 psycopg3 驱动标识（兼容 postgresql:// / postgres:// 前缀）
        for prefix in ("postgresql://", "postgres://"):
            if url.startswith(prefix):
                url = "postgresql+psycopg://" + url[len(prefix):]
                break
        return create_engine(
            url,
            echo=False,
            pool_size=5,          # 常驻连接
            max_overflow=5,       # 峰值溢出（合计 ≤10，多项目共享 100 上限内）
            pool_pre_ping=True,   # 取连接前探活，规避共享实例断连
            pool_recycle=1800,    # 30 分钟回收，避免长连接被服务端掐断
        )
    db_path = settings.DB_PATH
    url = db_path if db_path.startswith("sqlite:///") else f"sqlite:///{db_path}"
    return create_engine(
        url,
        connect_args={"check_same_thread": False},
        echo=False,
    )


DATABASE_URL = settings.DATABASE_URL  # 向后兼容引用（SQLite 模式下为空串）
engine = _build_engine()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db():
    """FastAPI 依赖：请求级数据库会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from . import models  # noqa: F401  确保模型已注册
    Base.metadata.create_all(bind=engine)
    _ensure_columns()
    _seed_llm_models()


def _seed_llm_models() -> None:
    """首次启动时种子 LLM 模型池（表为空才插，不覆盖后台修改）。"""
    from .services.llm_models import ensure_seed
    db = SessionLocal()
    try:
        ensure_seed(db)
    except Exception:
        db.rollback()
    finally:
        db.close()


# 轻量自动迁移：为已存在的表补齐新增列（避免删库丢数据）
_COLUMNS = {
    "users": {
        "avatar": "VARCHAR(255) DEFAULT ''",
        "points": "INTEGER DEFAULT 999999",
        "llm_model": "VARCHAR(64) DEFAULT ''",
    },
    "messages": {
        "trace_id": "VARCHAR(36) DEFAULT ''",
    },
}


def _ensure_columns() -> None:
    # SQLite 专属的轻量补列迁移；PG 模式下表结构由迁移工具/建表统一管理，跳过
    if IS_POSTGRES:
        return
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    with engine.begin() as conn:
        for table, cols in _COLUMNS.items():
            if not insp.has_table(table):
                continue
            existing = {c["name"] for c in insp.get_columns(table)}
            for name, ddl in cols.items():
                if name not in existing:
                    conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {ddl}'))
        # 旧数据回填：无积分的用户直接拉满
        if insp.has_table("users") and "points" in {c["name"] for c in insp.get_columns("users")}:
            conn.execute(text("UPDATE users SET points = 999999 WHERE points IS NULL"))