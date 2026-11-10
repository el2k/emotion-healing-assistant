# -*- coding: utf-8 -*-
"""安全加固：登录限流（IP+账号维度滑动窗口 + 自动封禁）。"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    """滑动窗口限流器。线程安全，内存实现，零外部依赖。

    用途：防止单 IP / 单账号暴力破解密码、刷接口 DoS。
    行为：窗口内超限 → 自动封禁 block_s 秒 → 解封后可重试。
    """

    def __init__(self, max_requests: int, window_s: float, block_s: float):
        self.max_requests = max_requests      # 窗口内最大请求数
        self.window_s = window_s              # 窗口长度（秒）
        self.block_s = block_s                # 超限后的封禁时长（秒）
        self._hits: dict[str, deque] = defaultdict(deque)
        self._blocked: dict[str, float] = {}  # key -> 解封时间戳
        self._lock = threading.Lock()

    def check(self, key: str) -> bool:
        """True=放行，False=限流（已进入封禁期）。"""
        now = time.time()
        with self._lock:
            # 封禁检查
            if key in self._blocked:
                if now < self._blocked[key]:
                    return False
                del self._blocked[key]  # 封禁期满，解封

            # 滑动窗口计数
            q = self._hits[key]
            while q and now - q[0] > self.window_s:
                q.popleft()
            if len(q) >= self.max_requests:
                self._blocked[key] = now + self.block_s
                self._hits.pop(key, None)
                return False
            q.append(now)
            return True

    def reset(self, key: str) -> None:
        """登录成功后重置计数（不误伤正常用户自己的账号）。"""
        with self._lock:
            self._hits.pop(key, None)
            self._blocked.pop(key, None)

    def status(self) -> dict:
        with self._lock:
            return {
                "tracking_keys": len(self._hits),
                "blocked_keys": len(self._blocked),
                "max_requests": self.max_requests,
                "window_s": self.window_s,
                "block_s": self.block_s,
                "blocked": {k: int(t - time.time()) for k, t in self._blocked.items()
                            if t > time.time()},
            }


# ============================================================
# 全局限流器实例
# ============================================================
# 登录：每 IP 60秒内最多 10 次尝试，超限封禁 5 分钟
login_limiter = RateLimiter(max_requests=10, window_s=60, block_s=300)
# 注册：每 IP 60秒内最多 5 次，超限封禁 10 分钟
register_limiter = RateLimiter(max_requests=5, window_s=60, block_s=600)
# 通用 API：每 IP 60秒内最多 200 次，超限封禁 60 秒
api_limiter = RateLimiter(max_requests=200, window_s=60, block_s=60)
