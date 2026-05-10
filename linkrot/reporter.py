"""Format and output check results."""

import csv
import io
import json
import sys
from pathlib import Path

from .checker import CheckResult

try:
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text
    from rich import box as rich_box
    _RICH = True
except ImportError:
    _RICH = False

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


def _url_display(cr: CheckResult) -> str:
    url = cr.link.url
    if cr.link.anchor:
        url += f"#{cr.link.anchor}"
    return url


def _status_style(status: str) -> str:
    if status == "ok":
        return "bold green"
    if status in ("missing", "error"):
        return "bold red"
    if status in ("anchor-missing", "timeout"):
        return "bold yellow"
    if status.startswith("http-"):
        code = int(status[5:])
        return "bold yellow" if code < 500 else "bold red"
    return "bold red"


def _rich_icon(status: str) -> str:
    if status == "ok":
        return "✓"
    if status == "timeout":
        return "⏱"
    if status == "anchor-missing":
        return "⚠"
    return "✗"


def report_rich_table(
    results: list[CheckResult],
    root: Path,
    show_ok: bool = False,
    output_file: str | None = None,
) -> None:
    broken = [r for r in results if not r.ok]
    ok_count = sum(1 for r in results if r.ok)
    total = len(results)

    console = Console(highlight=False)

    if not broken and not show_ok:
        console.print(f"[bold green]All {ok_count} links OK.[/bold green]")
        return

    display = results if show_ok else broken

    table = Table(
        box=rich_box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        border_style="cyan",
        show_lines=False,
        expand=False,
    )
    table.add_column("File", style="cyan", no_wrap=True)
    table.add_column("Line", style="dim", justify="right", width=6)
    table.add_column("", width=2, no_wrap=True)
    table.add_column("URL", no_wrap=False)
    table.add_column("Detail", style="dim", no_wrap=False)

    for cr in sorted(display, key=lambda r: (str(r.link.source_file), r.link.line_number)):
        rel = (
            str(cr.link.source_file.relative_to(root))
            if cr.link.source_file.is_relative_to(root)
            else str(cr.link.source_file)
        )
        style = _status_style(cr.status)
        icon_text = Text(_rich_icon(cr.status), style=style)
        url_text = Text(_url_display(cr), style=style if not cr.ok else "")
        table.add_row(rel, str(cr.link.line_number), icon_text, url_text, cr.detail or "")

    console.print(table)

    broken_style = "red" if broken else "green"
    summary = (
        f"[bold green]{ok_count} OK[/bold green]  "
        f"[bold {broken_style}]{len(broken)} broken[/bold {broken_style}]  "
        f"of {total} total"
    )
    console.print(summary)

    # Category breakdown
    from collections import Counter
    broken_statuses: Counter = Counter(r.status for r in broken)
    if len(broken_statuses) > 1:
        breakdown = Table(box=rich_box.SIMPLE, show_header=False, pad_edge=False)
        breakdown.add_column("Status", style="dim")
        breakdown.add_column("Count", justify="right", style="yellow")
        for status, count in sorted(broken_statuses.items(), key=lambda x: -x[1]):
            breakdown.add_row(f"  {status}", str(count))
        console.print(breakdown)


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

    display = results if show_ok else broken

    prev_file = None
    for cr in sorted(display, key=lambda r: (str(r.link.source_file), r.link.line_number)):
        rel = (
            cr.link.source_file.relative_to(root)
            if cr.link.source_file.is_relative_to(root)
            else cr.link.source_file
        )
        if rel != prev_file:
            lines.append(f"\n{_colorize(str(rel), _BOLD + _CYAN, use_color)}")
            prev_file = rel

        icon = _icon(cr.status) if use_color else ("OK" if cr.ok else "FAIL")
        url = _url_display(cr)
        detail = f"  {_colorize(cr.detail, _DIM, use_color)}" if cr.detail else ""
        lines.append(f"  {icon}  L{cr.link.line_number:<5} {url}{detail}")

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
        rel = (
            str(cr.link.source_file.relative_to(root))
            if cr.link.source_file.is_relative_to(root)
            else str(cr.link.source_file)
        )
        data.append({
            "file": rel,
            "line": cr.link.line_number,
            "url": _url_display(cr),
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
        rel = (
            str(cr.link.source_file.relative_to(root))
            if cr.link.source_file.is_relative_to(root)
            else str(cr.link.source_file)
        )
        writer.writerow([rel, cr.link.line_number, _url_display(cr), cr.ok, cr.status, cr.detail])
    return buf.getvalue()


def _md_status_icon(status: str) -> str:
    if status == "ok":
        return "✅"
    if status == "anchor-missing":
        return "⚠️"
    return "❌"


def report_markdown(
    results: list[CheckResult],
    root: Path,
    show_ok: bool = False,
) -> str:
    broken = [r for r in results if not r.ok]
    ok_count = sum(1 for r in results if r.ok)
    total = len(results)

    lines: list[str] = ["# Link Check Report", ""]

    lines += [
        "## Summary",
        "",
        "| Metric | Count |",
        "|--------|-------|",
        f"| Total links | {total} |",
        f"| Passing | {ok_count} |",
        f"| Broken | {len(broken)} |",
        "",
    ]

    if not broken and not show_ok:
        lines.append(f"All {ok_count} links are OK.")
        return "\n".join(lines)

    display = results if show_ok else broken
    sorted_results = sorted(display, key=lambda r: (str(r.link.source_file), r.link.line_number))

    by_file: dict[str, list[CheckResult]] = {}
    for cr in sorted_results:
        rel = (
            str(cr.link.source_file.relative_to(root))
            if cr.link.source_file.is_relative_to(root)
            else str(cr.link.source_file)
        )
        by_file.setdefault(rel, []).append(cr)

    lines += ["## Results by File", ""]

    for file_path, file_results in by_file.items():
        lines += [f"### `{file_path}`", ""]
        lines += [
            "| Line | Status | URL | Detail |",
            "|------|--------|-----|--------|",
        ]
        for cr in file_results:
            icon = _md_status_icon(cr.status)
            url = _url_display(cr).replace("|", "\\|")
            detail = (cr.detail or "").replace("|", "\\|")
            lines.append(f"| {cr.link.line_number} | {icon} `{cr.status}` | `{url}` | {detail} |")
        lines.append("")

    return "\n".join(lines)


def report_sarif(results: list[CheckResult], root: Path) -> str:
    """Serialize broken links as SARIF v2.1.0 JSON."""
    from . import __version__

    _RULES = {
        "LR001": "Broken internal link — target file not found or anchor missing.",
        "LR002": "Broken external URL — HTTP error, timeout, or connection failure.",
        "LR003": "Anchor not found — the target file exists but the fragment is missing.",
    }

    def _rule_id(cr: CheckResult) -> str:
        if cr.status == "anchor-missing":
            return "LR003"
        if cr.link.is_external:
            return "LR002"
        return "LR001"

    rules = [
        {
            "id": rule_id,
            "name": rule_id,
            "shortDescription": {"text": desc},
            "helpUri": "https://github.com/iamgeetarted/linkrot",
        }
        for rule_id, desc in _RULES.items()
    ]

    sarif_results = []
    for cr in results:
        if cr.ok:
            continue
        rel = (
            str(cr.link.source_file.relative_to(root))
            if cr.link.source_file.is_relative_to(root)
            else str(cr.link.source_file)
        )
        # SARIF uses forward slashes for URIs
        uri = rel.replace("\\", "/")
        sarif_results.append(
            {
                "ruleId": _rule_id(cr),
                "level": "error",
                "message": {
                    "text": (
                        f"{_url_display(cr)} — {cr.detail}"
                        if cr.detail
                        else _url_display(cr)
                    )
                },
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": uri},
                            "region": {"startLine": cr.link.line_number},
                        }
                    }
                ],
            }
        )

    sarif_doc = {
        "$schema": (
            "https://schemastore.azurewebsites.net/schemas/json/sarif-2.1.0-rtm.6.json"
        ),
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "linkrot",
                        "version": __version__,
                        "informationUri": "https://github.com/iamgeetarted/linkrot",
                        "rules": rules,
                    }
                },
                "results": sarif_results,
            }
        ],
    }
    return json.dumps(sarif_doc, indent=2)


def report_github_annotations(results: list[CheckResult], root: Path) -> str:
    """Emit GitHub Actions workflow commands for broken links."""
    lines: list[str] = []
    for cr in sorted(results, key=lambda r: (str(r.link.source_file), r.link.line_number)):
        if cr.ok:
            continue
        rel = (
            str(cr.link.source_file.relative_to(root))
            if cr.link.source_file.is_relative_to(root)
            else str(cr.link.source_file)
        )
        url = _url_display(cr)
        detail = cr.detail or cr.status
        title = f"Broken link ({cr.status})"
        lines.append(f"::error file={rel},line={cr.link.line_number},title={title}::{url} — {detail}")
    return "\n".join(lines)


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
        if output_file:
            Path(output_file).write_text(text, encoding="utf-8")
        else:
            print(text)
    elif fmt == "csv":
        text = report_csv(results, root)
        if output_file:
            Path(output_file).write_text(text, encoding="utf-8")
        else:
            print(text)
    elif fmt == "markdown":
        text = report_markdown(results, root, show_ok=show_ok)
        if output_file:
            Path(output_file).write_text(text, encoding="utf-8")
        else:
            print(text)
    elif fmt == "github":
        text = report_github_annotations(results, root)
        if output_file:
            Path(output_file).write_text(text, encoding="utf-8")
        else:
            print(text)
    elif fmt == "sarif":
        text = report_sarif(results, root)
        if output_file:
            Path(output_file).write_text(text, encoding="utf-8")
        else:
            print(text)
    elif fmt == "table" and _RICH and use_color:
        report_rich_table(results, root, show_ok=show_ok, output_file=output_file)
    else:
        text = report_table(results, root, show_ok=show_ok, use_color=use_color)
        if output_file:
            Path(output_file).write_text(text, encoding="utf-8")
        else:
            print(text)

    broken_count = sum(1 for r in results if not r.ok)
    return 1 if broken_count else 0
