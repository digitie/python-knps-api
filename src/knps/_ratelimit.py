"""작은 async 고정 속도 제한기."""

from __future__ import annotations

import asyncio
import time


class AsyncRateLimiter:
    """단일 프로세스용 간단한 초당 요청 제한기 (burst 없이 최소 간격만 강제)."""

    def __init__(self, *, max_rps: float) -> None:
        if max_rps <= 0:
            raise ValueError("max_rps must be greater than 0")
        self._interval = 1.0 / max_rps
        self._lock = asyncio.Lock()
        self._next_at = 0.0

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            wait_for = self._next_at - now
            if wait_for > 0:
                await asyncio.sleep(wait_for)
                now = time.monotonic()
            self._next_at = max(now, self._next_at) + self._interval
