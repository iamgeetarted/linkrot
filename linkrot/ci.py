"""GitHub Actions CI integration — write a Markdown step summary."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .checker import CheckResult

_MAX_ROWS = 50


def write_github_step_summary(
    results: "list[CheckResult]",
    root: Path,
    scan_elapsed: float = 0.0,
    check_elapsed: float = 0.0,
) -> bool:
    """Append a Markdown broken-link table to ``$GITHUB_STEP_SUMMARY``.

    Does nothing (returns False) when the environment variable is not set or
    the file path is empty.

    Args:
        results: All check results from the scan.
        root: The root directory used to make file paths relative.
        scan_elapsed: Seconds spent scanning files (for the summary header).
        check_elapsed: Seconds spent checking links (for the summary header).

    Returns:
        True if the summary was written; False otherwise.
    """
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "")
    if not summary_path:
        return False

    broken = [r for r in results if not r.ok]
    total = len(results)
    broken_count = len(broken)

    def _rel(r: "CheckResult") -> str:
        try:
            return str(r.link.source_file.relative_to(root))
        except ValueError:
            return str(r.link.source_file)

    def _url_display(r: "CheckResult") -> str:
        url = r.link.url
        if r.link.anchor:
            url += f"#{r.link.anchor}"
        return url

    lines: list[str] = [
        "## \U0001f517 Linkrot Report",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total links checked | {total} |",
        f"| Broken links | {broken_count} |",
        f"| Scan time | {scan_elapsed:.2f}s |",
        f"| Check time | {check_elapsed:.2f}s |",
        "",
    ]

    if not broken:
        lines.append("**All links are passing.** ✅")
        lines.append("")
    else:
        lines += [
            "### Broken Links",
            "",
            "| Status | URL | File | Detail |",
            "|--------|-----|------|--------|",
        ]

        display = broken[:_MAX_ROWS]
        for r in display:
            status = r.status.replace("|", "\\|")
            url = _url_display(r).replace("|", "\\|")
            file_path = _rel(r).replace("|", "\\|")
            detail = (r.detail or "").replace("|", "\\|")
            lines.append(f"| `{status}` | `{url}` | `{file_path}:{r.link.line_number}` | {detail} |")

        if len(broken) > _MAX_ROWS:
            overflow = len(broken) - _MAX_ROWS
            lines.append(f"| … | *…and {overflow} more* | | |")

        lines.append("")

    content = "\n".join(lines) + "\n"

    try:
        with open(summary_path, "a", encoding="utf-8") as fh:
            fh.write(content)
    except OSError:
        return False

    return True
