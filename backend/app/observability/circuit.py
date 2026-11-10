# -*- coding: utf-8 -*-
"""断路器：防止 LLM 故障时反复重试导致级联失败。

模式：
  CLOSED  → 正常调用（记录失败次数）
  OPEN    → 超过阈值后跳过调用，直接走降级路径
  HALF_OPEN → 冷却期后放一个探测请求验证是否恢复
"""
from __future__ import annotations

import threading
import time
from enum import Enum


class BreakerState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """单个依赖的断路器。线程安全。"""

    def __init__(self, name: str, failure_threshold: int = 3,
                 recovery_timeout_s: float = 30.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout_s = recovery_timeout_s
        self._lock = threading.Lock()
        self._state = BreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_at: float = 0
        self._last_error = ""
        self._total_calls = 0
        self._total_rejects = 0

    @property
    def state(self) -> BreakerState:
        return self._state

    def can_call(self) -> bool:
        """判断是否允许调用。OPEN 时返回 False，冷却期过自动进入 HALF_OPEN。"""
        with self._lock:
            if self._state == BreakerState.OPEN:
                if time.time() - self._last_failure_at >= self.recovery_timeout_s:
                    self._state = BreakerState.HALF_OPEN
                    return True  # 放一个探测请求
                return False
            return True

    def record_success(self):
        with self._lock:
            self._total_calls += 1
            if self._state == BreakerState.HALF_OPEN:
                self._state = BreakerState.CLOSED
            self._failure_count = 0
            self._last_error = ""

    def record_failure(self, error: str = ""):
        with self._lock:
            self._failure_count += 1
            self._last_failure_at = time.time()
            self._last_error = error
            if self._failure_count >= self.failure_threshold:
                self._state = BreakerState.OPEN

    def record_reject(self):
        """OPEN 状态下拒绝了调用。"""
        with self._lock:
            self._total_rejects += 1

    def status(self) -> dict:
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "last_error": self._last_error,
            "total_calls": self._total_calls,
            "total_rejects": self._total_rejects,
            "recovery_timeout_s": self.recovery_timeout_s,
        }

    def reset(self):
        with self._lock:
            self._state = BreakerState.CLOSED
            self._failure_count = 0
            self._last_error = ""


# 全局 LLM 断路器
llm_breaker = CircuitBreaker("llm", failure_threshold=3, recovery_timeout_s=30)
