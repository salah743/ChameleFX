from __future__ import annotations
from chamelefx.log import get_logger
from typing import Callable, Awaitable
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import time

from chamelefx.utils.validator import validate_and_fix_config, ensure_runtime_layout

# in-memory token bucket per (path) with simple quotas
_BUCKETS = {}  # path -> {tokens, last_ts}
_RATE   = {     # per 2 seconds
  "/stats/summary_fast": 8,
  "/alpha/features/compute": 6,
  "/alpha/weight_from_signal": 10,
}
_WINDOW = 2.0

class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        path = request.url.path
        quota = _RATE.get(path)
        if quota:
            now = time.time()
            b = _BUCKETS.get(path, {"tokens": quota, "last": now})
            # refill
            elapsed = now - b["last"]
            if elapsed > _WINDOW:
                b["tokens"] = quota
                b["last"] = now
            if b["tokens"] <= 0:
                return JSONResponse({"ok": False, "error": "rate_limited"}, status_code=429)
            b["tokens"] -= 1
            _BUCKETS[path] = b
        return await call_next(request)

def wire(app) -> None:
    # 1) ensure config + runtime layout
    try:
        from pathlib import Path
        root = Path(__file__).resolve().parents[2] / "chamelefx"
        validate_and_fix_config(root / "config.json")
        ensure_runtime_layout()
    except Exception:
    get_logger(__name__).exception('Unhandled exception')
    # 2) add rate limit middleware
    try:
        app.add_middleware(RateLimitMiddleware)
    except Exception:
    get_logger(__name__).exception('Unhandled exception')
