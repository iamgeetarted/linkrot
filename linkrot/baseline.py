"""Baseline delta tracking — suppress known-broken links between runs."""

from __future__ import annotations

import json
from pathlib import Path

from .checker import CheckResult


def load_baseline(path: Path) -> set[str]:
    """Load a previously saved baseline file and return the set of broken URLs it contains.

    Returns an empty set if the file does not exist or cannot be parsed.
    """
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
    except FileNotFoundError:
        return set()
    except (json.JSONDecodeError, OSError):
        return set()

    if not isinstance(data, list):
        return set()

    urls: set[str] = set()
    for entry in data:
        if isinstance(entry, dict) and "url" in entry:
            urls.add(str(entry["url"]))

    return urls


def save_baseline(path: Path, results: list[CheckResult]) -> None:
    """Save the set of broken URLs from *results* to *path* as a JSON file.

    Only broken results (``ok=False``) are recorded.  The file format is a
    JSON array of objects with ``"url"`` and ``"status"`` keys so it is easy to
    inspect by hand.
    """
    broken = [
        {"url": r.link.url, "status": r.status}
        for r in results
        if not r.ok
    ]
    path.write_text(json.dumps(broken, indent=2), encoding="utf-8")
