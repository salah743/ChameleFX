from __future__ import annotations
from chamelefx.log import get_logger
import asyncio, time
from typing import Callable, Awaitable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

class Gatekeeper(BaseHTTPMiddleware):
    def __init__(self, app, global_limit: int = 8, per_path_qps: float = 8.0, sequential_paths: tuple[str,...]=()):
        super().__init__(app)
        self.sem = asyncio.Semaphore(max(1, int(global_limit)))
        self.qps = max(0.5, float(per_path_qps))
        self.sequential = set(sequential_paths or ())
        self._last: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._errors = 0

    @property
    def error_count(self) -> int:
        return self._errors

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]):
        path = request.url.path
        # simple per-path QPS
        now = time.time()
        last = self._last.get(path, 0.0)
        min_gap = 1.0 / self.qps
        if (now - last) < min_gap:
            await asyncio.sleep(min_gap - (now - last))
        self._last[path] = time.time()

        # sequentialize selected heavy endpoints
        lock: asyncio.Lock | None = None
        for p in self.sequential:
            if path.startswith(p):
                lock = self._locks.setdefault(p, asyncio.Lock())
                break

        try:
            async with self.sem:
                if lock:
                    async with lock:
                        return await call_next(request)
                else:
                    return await call_next(request)
        except Exception:
            self._errors += 1
            raise
