import math
import threading
import time
from collections import deque

_hits = {}
_lock = threading.Lock()
_DAY = 24 * 60 * 60


def retry_after(key, rules, now=None):
    now = time.monotonic() if now is None else now
    longest = max(window for _, window in rules)
    with _lock:
        hits = _hits.setdefault(key, deque())
        while hits and now - hits[0] >= longest:
            hits.popleft()
        for limit, window in rules:
            inside = [t for t in hits if now - t < window]
            if len(inside) >= limit:
                return max(1, math.ceil(window - (now - inside[-limit])))
        hits.append(now)
        if len(_hits) > 5000:
            for stale in [k for k, v in _hits.items() if not v or now - v[-1] >= _DAY]:
                del _hits[stale]
    return None
