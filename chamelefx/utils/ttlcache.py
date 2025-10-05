from __future__ import annotations
import time
from typing import Any, Callable, Tuple, Dict

class TTLCache:
    def __init__(self, ttl_seconds: float = 2.0, max_items: int = 512):
        self.ttl = float(ttl_seconds)
        self.max = int(max_items)
        self._d: Dict[Any, Tuple[float, Any]] = {}

    def get(self, key: Any, fn: Callable[[], Any]):
        now = time.time()
        v = self._d.get(key)
        if v is not None:
            ts, val = v
            if (now - ts) <= self.ttl:
                return val
        val = fn()
        if len(self._d) >= self.max:
            self._d.clear()
        self._d[key] = (now, val)
        return val
