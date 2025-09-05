cat > App/Services/data_fetch/cache.py <<'PY'
import time
from typing import Any, Dict, Tuple

_TTL_SEC = 5  # short TTL placeholder
_store: Dict[str, Tuple[float, Any]] = {}

def set(key: str, value: Any, ttl: int = _TTL_SEC) -> None:
    _store[key] = (time.time() + ttl, value)

def get(key: str):
    exp_val = _store.get(key)
    if not exp_val:
        return None
    exp, val = exp_val
    if time.time() > exp:
        _store.pop(key, None)
        return None
    return val
PY
