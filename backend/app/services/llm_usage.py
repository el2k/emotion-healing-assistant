# -*- coding: utf-8 -*-
"""LLM 用量记录：把每次调用的 token 消耗写入 llm_usage_logs。

数据来源：
- 非流式/流式响应里的 usage 字段（OpenAI 兼容协议，DashScope 兼容模式返回）；
- 流式拿不到 usage 时按回复文本粗略估算（中文约 0.75 token/字），保证统计不断链。
"""
from sqlalchemy.orm import Session

from ..models import LLMUsageLog


def estimate_tokens(text: str) -> int:
    """粗略估算 token（中英混合：约 0.75 token/字符）。"""
    if not text:
        return 0
    return max(1, int(len(text) * 0.75))


def record(db: Session, user_id: int, model: str, scene: str,
           usage: dict | None = None, success: bool = True,
           estimate_text: str = "") -> None:
    """记录一次 LLM 调用。usage 缺失时按 estimate_text 估算。"""
    if not model:
        return
    usage = usage or {}
    try:
        p = int(usage.get("prompt_tokens") or 0)
        c = int(usage.get("completion_tokens") or 0)
        t = int(usage.get("total_tokens") or 0)
    except (TypeError, ValueError):
        p = c = t = 0
    if t <= 0:
        t = (p + c) if (p + c) > 0 else estimate_tokens(estimate_text)
        if p == 0 and c == 0:
            p = max(t - estimate_tokens(estimate_text), 0)
            c = max(t - p, 0)
    log = LLMUsageLog(user_id=user_id, model=model, scene=scene,
                      prompt_tokens=p, completion_tokens=c, total_tokens=t,
                      success=bool(success))
    db.add(log)
    db.commit()