"""Disk-based URL check result cache with configurable TTL."""

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path

CACHE_DIR = Path.home() / ".cache" / "linkrot"


@dataclass
class CachedResult:
    ok: bool
    status: str
    detail: str


def _cache_path(url: str) -> Path:
    key = hashlib.md5(url.encode()).hexdigest()
    return CACHE_DIR / f"{key}.json"


def get_cached(url: str, ttl_hours: float) -> CachedResult | None:
    """Return a cached result if it exists and is within the TTL, else None."""
    path = _cache_path(url)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        if time.time() - data["timestamp"] > ttl_hours * 3600:
            return None
        return CachedResult(ok=data["ok"], status=data["status"], detail=data.get("detail", ""))
    except Exception:
        return None


def set_cached(url: str, ok: bool, status: str, detail: str) -> None:
    """Persist a check result to the on-disk cache."""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cache_path(url).write_text(
            json.dumps({"url": url, "ok": ok, "status": status, "detail": detail, "timestamp": time.time()})
        )
    except Exception:
        pass


def clear_cache() -> int:
    """Delete all cached entries; returns the number of files removed."""
    count = 0
    if CACHE_DIR.exists():
        for f in CACHE_DIR.glob("*.json"):
            f.unlink(missing_ok=True)
            count += 1
    return count
