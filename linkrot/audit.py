"""JSONL audit log — writes each check result as a structured JSON line."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .checker import CheckResult


def write_audit_log(results: list[CheckResult], log_path: Path, root: Path) -> int:
    """Append each *result* to *log_path* as a newline-delimited JSON record.

    Each record includes: ``ts``, ``file``, ``line``, ``url``, ``ok``,
    ``status``, ``detail``, ``is_external``, ``final_url``.  The file is
    opened in append mode so successive runs accumulate in one log.

    Args:
        results:  Check results to serialize.
        log_path: Path to the ``.jsonl`` file (created or appended).
        root:     Project root used to make ``file`` paths relative.

    Returns:
        Number of records written.
    """
    ts = datetime.now(timezone.utc).isoformat()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with log_path.open("a", encoding="utf-8") as fh:
        for cr in results:
            try:
                rel = str(cr.link.source_file.relative_to(root))
            except ValueError:
                rel = str(cr.link.source_file)

            record = {
                "ts": ts,
                "file": rel,
                "line": cr.link.line_number,
                "url": cr.link.url,
                "ok": cr.ok,
                "status": cr.status,
                "detail": cr.detail or "",
                "is_external": cr.link.is_external,
                "final_url": cr.final_url or "",
            }
            fh.write(json.dumps(record) + "\n")
            count += 1

    return count
