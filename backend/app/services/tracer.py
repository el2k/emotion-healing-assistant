# -*- coding: utf-8 -*-
"""Agent 链路追踪（参考 dsAgent 的 @AgentTrace + AOP 设计，改用 Python 上下文管理器）。

设计对照（Java → Python）：
  AgentTraceDocument（ES 文档）  → AgentTraceLog（SQLite 行）
  @AgentTrace 注解 + AgentTraceAspect（环绕） → TraceRecorder.span()（contextmanager）
  TraceRecordedEvent + 异步监听器 → ThreadPoolExecutor 异步写库（失败仅告警绝不阻断业务）
  TraceNodeEnum（节点枚举）      → NODE 常量表

用法：
    tracer = TraceRecorder(user_id=uid, session_id=sid)
    with tracer.span(NODE_RULE_EMOTION, input_data={"text": content}) as span:
        ...
        span.output = {...}            # 成功出参
    with tracer.span(NODE_LLM_REPLY, input_data=... ) as span:   # 异常自动记 result=0
        ...
    tracer.flush(message_id=assistant_msg.id)   # 用户消息落库后关联消息 ID 并异步写库

隐私原则：入参/出参仅本人（或管理员审计）可查；文本截断防爆库。
"""
import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone

from ..models import AgentTraceLog

# ---- 节点定义（对照 dsAgent TraceNodeEnum）----
NODE_RULE_EMOTION = ("RULE_EMOTION", "规则情绪分析", "Emotion")
NODE_LLM_EMOTION = ("LLM_EMOTION", "LLM 深度情绪分析", "LLM")
NODE_INTENT = ("INTENT", "意图识别", "Intent")
NODE_MEMORY = ("MEMORY", "记忆与画像上下文", "Memory")
NODE_FLOW = ("DIALOG_FLOW", "会话轨迹策略", "Flow")
NODE_KNOWLEDGE = ("KNOWLEDGE_RETRIEVAL", "知识库检索（RAG）", "Tool")
NODE_LLM_REPLY = ("LLM_REPLY", "LLM 回复生成", "LLM")
NODE_FALLBACK = ("FALLBACK_REPLY", "本地模板降级", "Fallback")
NODE_PERSIST = ("PERSIST", "消息与档案落库", "Persist")

_MAX_TEXT = 6000          # 入参/出参 JSON 截断长度
_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="trace")


def _json_compact(data, limit: int = _MAX_TEXT) -> str:
    """序列化为紧凑 JSON 并截断。"""
    if data is None:
        return ""
    try:
        s = json.dumps(data, ensure_ascii=False, default=str)
    except Exception:
        return str(data)[:limit]
    return s if len(s) <= limit else s[:limit] + "…(截断)"


def _utcnow():
    return datetime.now(timezone.utc)


class _Span:
    __slots__ = ("node", "input", "output", "detail", "error", "result",
                 "enter_ns", "leave_ns")

    def __init__(self, node):
        self.node = node
        self.input = None
        self.output = None
        self.detail = None
        self.error = ""
        self.result = 1
        self.enter_ns = 0.0
        self.leave_ns = 0.0


class TraceRecorder:
    """一次用户消息处理链路的追踪器：收集各节点 span，flush 时整链路异步落库。"""

    def __init__(self, user_id: int, session_id: int | None = None,
                 node_filter: set[str] | None = None):
        self.trace_id = uuid.uuid4().hex
        self.user_id = user_id
        self.session_id = session_id
        self._spans: list[_Span] = []
        self._order = 0
        self._lock = threading.Lock()
        self._flushed = False

    @contextmanager
    def span(self, node: tuple[str, str, str], input_data=None):
        """记录一个处理节点。异常会标记失败并原样抛出（不打断业务语义）。"""
        sp = _Span(node)
        sp.input = input_data
        with self._lock:
            self._order += 1
            order = self._order
        sp.enter_ns = _perf_ms()
        try:
            yield sp
        except Exception as e:                       # noqa: BLE001
            sp.result = 0
            sp.error = f"{type(e).__name__}: {e}"[:1000]
            raise
        finally:
            sp.leave_ns = _perf_ms()
            with self._lock:
                self._spans.append((order, sp))

    @property
    def total_ms(self) -> float:
        if not self._spans:
            return 0.0
        first = min(sp.enter_ns for _, sp in self._spans)
        last = max(sp.leave_ns for _, sp in self._spans)
        return round(last - first, 1)

    def flush(self, message_id: int | None = None) -> None:
        """异步整链路写库（幂等；失败仅打印，绝不影响聊天主流程）。"""
        if self._flushed:
            return
        self._flushed = True
        _EXECUTOR.submit(self._write, message_id)

    # ---- 内部 ----
    def _write(self, message_id: int | None) -> None:
        try:
            from ..database import SessionLocal
            db = SessionLocal()
            try:
                rows = []
                for order, sp in sorted(self._spans, key=lambda x: x[0]):
                    key, name, ntype = sp.node
                    rows.append(AgentTraceLog(
                        trace_id=self.trace_id,
                        session_id=self.session_id,
                        user_id=self.user_id,
                        message_id=message_id,
                        node_key=key, node_name=name, node_type=ntype,
                        execution_order=order,
                        enter_time=datetime.fromtimestamp(sp.enter_ns / 1000.0, tz=timezone.utc),
                        leave_time=datetime.fromtimestamp(sp.leave_ns / 1000.0, tz=timezone.utc),
                        duration_ms=max(0, int(round(sp.leave_ns - sp.enter_ns))),
                        result=sp.result,
                        input_str=_json_compact(sp.input),
                        output_str=_json_compact(sp.output),
                        error_msg=sp.error or "",
                        detail=_json_compact(sp.detail),
                    ))
                if rows:
                    db.add_all(rows)
                    db.commit()
            finally:
                db.close()
        except Exception as e:                       # noqa: BLE001
            print(f"[trace] 写入链路追踪失败（不影响业务）: {e}")


def _perf_ms() -> float:
    import time
    return time.perf_counter() * 1000.0


def get_trace(trace_id: str):
    """查询某条链路的全部节点（按执行顺序）。"""
    from ..database import SessionLocal
    db = SessionLocal()
    try:
        return (db.query(AgentTraceLog)
                .filter(AgentTraceLog.trace_id == trace_id)
                .order_by(AgentTraceLog.execution_order.asc())
                .all())
    finally:
        db.close()


def trace_to_dict(trace_id: str) -> dict | None:
    """链路 → 前端结构：总耗时 + 节点列表（入参/出参解析回对象）。"""
    rows = get_trace(trace_id)
    if not rows:
        return None
    nodes = []
    total = 0
    for r in rows:
        total += r.duration_ms or 0
        nodes.append({
            "order": r.execution_order,
            "node_key": r.node_key,
            "node_name": r.node_name,
            "node_type": r.node_type,
            "duration_ms": r.duration_ms or 0,
            "result": bool(r.result),
            "error": r.error_msg or "",
            "input": _try_json(r.input_str),
            "output": _try_json(r.output_str),
            "detail": _try_json(r.detail),
        })
    return {
        "trace_id": trace_id,
        "session_id": rows[0].session_id,
        "message_id": rows[0].message_id,
        "node_count": len(nodes),
        "total_ms": int(total),
        "nodes": nodes,
    }


def _try_json(s: str):
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        return s
