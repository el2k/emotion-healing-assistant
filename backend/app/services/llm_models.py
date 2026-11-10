# -*- coding: utf-8 -*-
"""LLM 模型池：可用模型的配置、默认模型解析、用户选择校验。

设计：
- llm_models 表由管理后台维护（增删改、额度、启停、默认）；
- 首次启动自动种子一批主流文本对话模型（阿里云百炼 OpenAI 兼容接口，
  含通义千问、DeepSeek、GLM、Kimi、MiniMax、阶跃等），额度为预填值，可后台修改；
- 每次启动按 model_id 增量补齐缺失的种子模型，已有记录（含后台改过的）不会被覆盖；
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

    # --- 通义千问新旗舰 ---
    {"model_id": "qwen3.8-max", "display_name": "通义千问 3.8 Max",
     "description": "最新旗舰：复杂情绪理解与长文推理最强",
     "free_quota_tokens": 1_000_000, "is_default": False, "sort_order": 10},
    {"model_id": "qwen3.7-max", "display_name": "通义千问 3.7 Max",
     "description": "上代旗舰：稳定性价比高",
     "free_quota_tokens": 1_000_000, "is_default": False, "sort_order": 11},
    {"model_id": "qwen-max", "display_name": "通义千问 Max",
     "description": "经典旗舰：中文表达与人设扮演稳定",
     "free_quota_tokens": 1_000_000, "is_default": False, "sort_order": 12},
    {"model_id": "qwen3.7-plus", "display_name": "通义千问 3.7 Plus",
     "description": "均衡稳定：日常陪伴的主力选择",
     "free_quota_tokens": 1_000_000, "is_default": False, "sort_order": 13},
    {"model_id": "qwen3.6-plus", "display_name": "通义千问 3.6 Plus",
     "description": "均衡稳定：速度与质量的平衡点",
     "free_quota_tokens": 1_000_000, "is_default": False, "sort_order": 14},
    {"model_id": "qwen3.8-flash", "display_name": "通义千问 3.8 Flash",
     "description": "极速响应：高并发闲聊首选",
     "free_quota_tokens": 10_000_000, "is_default": False, "sort_order": 15},
    {"model_id": "qwen3.7-flash", "display_name": "通义千问 3.7 Flash",
     "description": "轻量快速：成本低、延迟低",
     "free_quota_tokens": 10_000_000, "is_default": False, "sort_order": 16},
    {"model_id": "qwen3.6-flash", "display_name": "通义千问 3.6 Flash",
     "description": "轻量之选：长对话也不卡",
     "free_quota_tokens": 10_000_000, "is_default": False, "sort_order": 17},
    {"model_id": "qwen-long", "display_name": "通义千问 Long",
     "description": "长文本专家：适合长对话回顾与档案分析",
     "free_quota_tokens": 1_000_000, "is_default": False, "sort_order": 18},
    {"model_id": "qwen3.8-27b", "display_name": "通义千问 3.8 27B",
     "description": "开源尺寸：风格自然，成本友好",
     "free_quota_tokens": 1_000_000, "is_default": False, "sort_order": 19},

    # --- 第三方模型（同接口可调） ---
    {"model_id": "deepseek-v4-pro", "display_name": "DeepSeek V4 Pro",
     "description": "深度推理：适合复杂情绪与逻辑分析",
     "free_quota_tokens": 1_000_000, "is_default": False, "sort_order": 20},
    {"model_id": "deepseek-v4.1-flash", "display_name": "DeepSeek V4.1 Flash",
     "description": "高性价比推理：快且稳",
     "free_quota_tokens": 10_000_000, "is_default": False, "sort_order": 21},
    {"model_id": "glm-5.3", "display_name": "智谱 GLM-5.3",
     "description": "中文自然、语气温和，适合共情表达",
     "free_quota_tokens": 1_000_000, "is_default": False, "sort_order": 30},
    {"model_id": "kimi-k3.1-pro", "display_name": "Kimi K3.1 Pro",
     "description": "超长上下文：记忆力强，表达细腻",
     "free_quota_tokens": 1_000_000, "is_default": False, "sort_order": 40},
    {"model_id": "kimi-k3", "display_name": "Kimi K3",
     "description": "长文本与对话均衡之选",
     "free_quota_tokens": 1_000_000, "is_default": False, "sort_order": 41},
    {"model_id": "MiniMax-M2.5", "display_name": "MiniMax M2.5",
     "description": "轻快活泼：适合轻松闲聊",
     "free_quota_tokens": 10_000_000, "is_default": False, "sort_order": 50},
]


def ensure_seed(db: Session) -> None:
    """按 model_id 增量补齐种子模型。

    只插入缺失项，已有记录（包括管理后台改过的额度、启停、默认标记）一律不动，
    因此可以安全地在每次启动时执行，用于给老数据库补充新增模型。
    """
    existing = {m.model_id for m in db.query(LLMModel).all()}
    added = False
    for item in DEFAULT_MODELS:
        if item["model_id"] in existing:
            continue
        db.add(LLMModel(**item))
        added = True
    if added:
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