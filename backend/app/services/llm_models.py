# -*- coding: utf-8 -*-
"""LLM 模型池：可用模型的配置、默认模型解析、用户选择校验。

设计：
- llm_models 表由管理后台维护（增删改、额度、启停、默认）；
- 首次启动自动种子 4 个通义千问模型（额度为常见免费额度预填值，可后台修改）；
- 解析优先级：请求显式指定 → 用户偏好 → 全局默认 → 任一启用模型 → 环境变量兜底；
- 未配置任何模型时回落到 settings.LLM_MODEL，保证单模型部署方式仍然可用。
"""
from sqlalchemy.orm import Session

from ..config import settings
from ..models import LLMModel

# 种子模型（阿里云百炼；额度为常见新用户免费额度，实际以控制台为准，管理后台可改）
DEFAULT_MODELS = [
    {"model_id": "qwen-plus", "display_name": "通义千问 Plus",
     "description": "均衡之选：情商与文采兼备，适合深度陪伴",
     "free_quota_tokens": 1_000_000, "is_default": True, "sort_order": 1},
    {"model_id": "qwen-flash", "display_name": "通义千问 Flash",
     "description": "轻快之选：响应最快，适合日常闲聊",
     "free_quota_tokens": 10_000_000, "is_default": False, "sort_order": 2},
    {"model_id": "qwen3.5-plus", "display_name": "通义千问 3.5 Plus",
     "description": "新一代旗舰：理解力与细腻度更强",
     "free_quota_tokens": 1_000_000, "is_default": False, "sort_order": 3},
    {"model_id": "qwen3.5-flash", "display_name": "通义千问 3.5 Flash",
     "description": "新一代轻量：又快又稳",
     "free_quota_tokens": 1_000_000, "is_default": False, "sort_order": 4},
]


def ensure_seed(db: Session) -> None:
    """首次启动时插入种子模型（表为空才插入，不覆盖管理后台的修改）。"""
    if db.query(LLMModel).count() > 0:
        return
    for item in DEFAULT_MODELS:
        db.add(LLMModel(**item))
    db.commit()


def list_enabled(db: Session) -> list[LLMModel]:
    return (db.query(LLMModel)
            .filter(LLMModel.enabled.is_(True))
            .order_by(LLMModel.sort_order, LLMModel.id)
            .all())


def default_model(db: Session) -> LLMModel | None:
    m = (db.query(LLMModel)
         .filter(LLMModel.enabled.is_(True), LLMModel.is_default.is_(True))
         .first())
    if m:
        return m
    return (db.query(LLMModel)
            .filter(LLMModel.enabled.is_(True))
            .order_by(LLMModel.sort_order, LLMModel.id)
            .first())


def resolve_model(db: Session, requested: str | None = None,
                  user_pref: str | None = None) -> str:
    """解析本次调用实际使用的模型 id。"""
    enabled = {m.model_id for m in list_enabled(db)}
    for cand in (requested, user_pref):
        cand = (cand or "").strip()
        if cand and cand in enabled:
            return cand
    d = default_model(db)
    if d:
        return d.model_id
    return settings.LLM_MODEL


def get_enabled(db: Session, model_id: str) -> LLMModel | None:
    return (db.query(LLMModel)
            .filter(LLMModel.model_id == model_id, LLMModel.enabled.is_(True))
            .first())