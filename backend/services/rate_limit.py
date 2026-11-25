import ipaddress
import math
import threading
import time
from collections import OrderedDict, deque

MAX_KEYS = 5000
_hits = OrderedDict()
_lock = threading.Lock()


def visitor_key(address):
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return address or "unknown"
    # One IPv6 visitor usually controls a whole /64, so count the block, not each address.
    return str(ipaddress.ip_network(f"{ip}/64", strict=False)) if ip.version == 6 else str(ip)


def retry_after(key, rules, now=None):
    now = time.monotonic() if now is None else now
    longest = max(window for _, window in rules)
    with _lock:
        hits = _hits.setdefault(key, deque())
        _hits.move_to_end(key)
        while hits and now - hits[0] >= longest:
            hits.popleft()
        for limit, window in rules:
            inside = [t for t in hits if now - t < window]
            if len(inside) >= limit:
                return max(1, math.ceil(window - (now - inside[-limit])))
        hits.append(now)
        while len(_hits) > MAX_KEYS:
            _hits.popitem(last=False)
    return None
