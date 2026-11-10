# -*- coding: utf-8 -*-
"""请求级指标采集：延迟、状态码、路径、错误——内存存储，零外部依赖。

设计原则：
  - 不阻塞主流程（所有记录用 try/except 包裹）
  - 有限内存（rolling window，只保留最近 N 条）
  - 可通过 /api/admin/observability/metrics 查询
  - 结构化存储，方便后续对接 Prometheus / Grafana
"""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field

# 全局单例（线程安全）
_lock = threading.Lock()


@dataclass
class RequestMetric:
    path: str
    method: str
    status: int
    latency_ms: float
    error: str = ""      # 非空表示有错误详情
    ts: float = field(default_factory=time.time)


@dataclass
class LLMCallMetric:
    action: str           # analyze / reply / wiki_compile
    latency_ms: float
    success: bool
    fallback: bool        # True = 降级到本地规则
    error: str = ""
    tokens_estimated: int = 0
    ts: float = field(default_factory=time.time)


class MetricsStore:
    """有限内存的指标存储。"""

    def __init__(self, max_requests=5000, max_llm_calls=500):
        self.requests: deque[RequestMetric] = deque(maxlen=max_requests)
        self.llm_calls: deque[LLMCallMetric] = deque(maxlen=max_llm_calls)
        self.start_time = time.time()

        # 聚合计数器（不受 deque 上限影响）
        self.total_requests = 0
        self.total_errors = 0
        self.total_llm_calls = 0
        self.total_llm_failures = 0
        self.total_llm_fallbacks = 0

    def record_request(self, path: str, method: str, status: int,
                      latency_ms: float, error: str = ""):
        with _lock:
            self.requests.append(RequestMetric(path, method, status, latency_ms, error))
            self.total_requests += 1
            if status >= 500 or error:
                self.total_errors += 1

    def record_llm(self, action: str, latency_ms: float, success: bool,
                   fallback: bool = False, error: str = "", tokens: int = 0):
        with _lock:
            self.llm_calls.append(
                LLMCallMetric(action, latency_ms, success, fallback, error, tokens))
            self.total_llm_calls += 1
            if not success:
                self.total_llm_failures += 1
                if fallback:
                    self.total_llm_fallbacks += 1

    def request_summary(self, minutes: int = 60) -> dict:
        """最近 N 分钟的请求摘要。"""
        cutoff = time.time() - minutes * 60
        with _lock:
            recent = [r for r in self.requests if r.ts >= cutoff]
        if not recent:
            return {"count": 0, "avg_ms": 0, "p95_ms": 0, "p99_ms": 0, "error_rate": 0, "per_path": {}}

        latencies = sorted(r.latency_ms for r in recent)
        n = len(latencies)
        errors = sum(1 for r in recent if r.status >= 500 or r.error)

        per_path: dict[str, dict] = {}
        for r in recent:
            key = r.path
            pd = per_path.setdefault(key, {"count": 0, "errors": 0, "total_ms": 0})
            pd["count"] += 1
            pd["total_ms"] += r.latency_ms
            if r.status >= 500 or r.error:
                pd["errors"] += 1

        for pd in per_path.values():
            pd["avg_ms"] = round(pd.pop("total_ms") / pd["count"], 1)
            pd["error_rate"] = round(pd["errors"] / pd["count"] * 100, 1)
            pd.pop("errors")

        return {
            "count": n,
            "avg_ms": round(sum(latencies) / n, 1),
            "p50_ms": round(latencies[n // 2], 1),
            "p95_ms": round(latencies[int(n * 0.95)] if n > 1 else latencies[0], 1),
            "p99_ms": round(latencies[int(n * 0.99)] if n > 1 else latencies[0], 1),
            "error_rate": round(errors / n * 100, 2),
            "per_path": per_path,
        }

    def llm_summary(self, minutes: int = 60) -> dict:
        cutoff = time.time() - minutes * 60
        with _lock:
            recent = [r for r in self.llm_calls if r.ts >= cutoff]
        if not recent:
            return {"count": 0, "success": 0, "failures": 0, "fallbacks": 0, "avg_ms": 0}

        latencies = [r.latency_ms for r in recent]
        return {
            "count": len(recent),
            "success": sum(1 for r in recent if r.success),
            "failures": sum(1 for r in recent if not r.success),
            "fallbacks": sum(1 for r in recent if r.fallback),
            "avg_ms": round(sum(latencies) / len(latencies), 1),
            "total_tokens_est": sum(r.tokens_estimated for r in recent),
        }

    def lifetime_summary(self) -> dict:
        uptime_s = time.time() - self.start_time
        return {
            "uptime_seconds": round(uptime_s),
            "uptime_human": _fmt_duration(uptime_s),
            "total_requests": self.total_requests,
            "total_errors": self.total_errors,
            "total_llm_calls": self.total_llm_calls,
            "total_llm_failures": self.total_llm_failures,
            "total_llm_fallbacks": self.total_llm_fallbacks,
            "error_rate": round(self.total_errors / max(1, self.total_requests) * 100, 2),
            "llm_failure_rate": round(
                self.total_llm_failures / max(1, self.total_llm_calls) * 100, 2),
        }


def _fmt_duration(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {int(seconds % 60)}s"
    return f"{int(seconds)}s"


# 全局实例
metrics = MetricsStore()
