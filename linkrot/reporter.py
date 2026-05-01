"""Format and output check results."""

import csv
import io
import json
import sys
from pathlib import Path

from .checker import CheckResult

# ANSI color codes
_GREEN = "\033[32m"
_RED = "\033[31m"
_YELLOW = "\033[33m"
_CYAN = "\033[36m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_RESET = "\033[0m"

_STATUS_ICON = {
    "ok": f"{_GREEN}✓{_RESET}",
    "missing": f"{_RED}✗{_RESET}",
    "anchor-missing": f"{_YELLOW}⚠{_RESET}",
    "timeout": f"{_YELLOW}⏱{_RESET}",
    "error": f"{_RED}✗{_RESET}",
}


def _icon(status: str) -> str:
    if status.startswith("http-"):
        code = int(status[5:])
        color = _YELLOW if code < 500 else _RED
        return f"{color}✗{_RESET}"
    return _STATUS_ICON.get(status, f"{_RED}?{_RESET}")


def _colorize(text: str, color: str, use_color: bool) -> str:
    return f"{color}{text}{_RESET}" if use_color else text


def report_table(
    results: list[CheckResult],
    root: Path,
    show_ok: bool = False,
    use_color: bool = True,
) -> str:
    lines = []
    broken = [r for r in results if not r.ok]
    ok_count = sum(1 for r in results if r.ok)

    if not broken and not show_ok:
        msg = f"All {ok_count} links OK."
        return _colorize(msg, _GREEN, use_color)

    if show_ok:
        display = results
    else:
        display = broken

    prev_file = None
    for cr in sorted(display, key=lambda r: (str(r.link.source_file), r.link.line_number)):
        rel = cr.link.source_file.relative_to(root) if cr.link.source_file.is_relative_to(root) else cr.link.source_file
        if rel != prev_file:
            lines.append(f"\n{_colorize(str(rel), _BOLD + _CYAN, use_color)}")
            prev_file = rel

        icon = _icon(cr.status) if use_color else ("OK" if cr.ok else "FAIL")
        url_display = cr.link.url
        if cr.link.anchor:
            url_display += f"#{cr.link.anchor}"
        detail = f"  {_colorize(cr.detail, _DIM, use_color)}" if cr.detail else ""
        lines.append(f"  {icon}  L{cr.link.line_number:<5} {url_display}{detail}")

    # Summary
    total = len(results)
    lines.append("")
    summary_parts = [
        _colorize(f"{ok_count} OK", _GREEN, use_color),
        _colorize(f"{len(broken)} broken", _RED if broken else _GREEN, use_color),
        f"of {total} total",
    ]
    lines.append("  ".join(summary_parts))

    return "\n".join(lines)


def report_json(results: list[CheckResult], root: Path) -> str:
    data = []
    for cr in results:
        rel = str(cr.link.source_file.relative_to(root)) if cr.link.source_file.is_relative_to(root) else str(cr.link.source_file)
        url = cr.link.url
        if cr.link.anchor:
            url += f"#{cr.link.anchor}"
        data.append({
            "file": rel,
            "line": cr.link.line_number,
            "url": url,
            "ok": cr.ok,
            "status": cr.status,
            "detail": cr.detail,
        })
    return json.dumps(data, indent=2)


def report_csv(results: list[CheckResult], root: Path) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["file", "line", "url", "ok", "status", "detail"])
    for cr in results:
        rel = str(cr.link.source_file.relative_to(root)) if cr.link.source_file.is_relative_to(root) else str(cr.link.source_file)
        url = cr.link.url
        if cr.link.anchor:
            url += f"#{cr.link.anchor}"
        writer.writerow([rel, cr.link.line_number, url, cr.ok, cr.status, cr.detail])
    return buf.getvalue()


def write_report(
    results: list[CheckResult],
    root: Path,
    fmt: str = "table",
    show_ok: bool = False,
    output_file: str | None = None,
) -> int:
    use_color = sys.stdout.isatty() and fmt == "table" and output_file is None

    if fmt == "json":
        text = report_json(results, root)
    elif fmt == "csv":
        text = report_csv(results, root)
    else:
        text = report_table(results, root, show_ok=show_ok, use_color=use_color)

    if output_file:
        Path(output_file).write_text(text, encoding="utf-8")
    else:
        print(text)

    broken_count = sum(1 for r in results if not r.ok)
    return 1 if broken_count else 0
