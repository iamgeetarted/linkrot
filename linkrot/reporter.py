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


def report_domain_summary(results: list[CheckResult], console: "Console | None" = None) -> None:
    """Print a per-domain breakdown of external link health as a Rich table.

    Groups all external URLs by hostname and shows total checked, broken count,
    failure rate, and the most common failure status per domain.  Sorted by
    broken count descending so the worst offenders appear first.

    Args:
        results: All check results (internal + external).
        console: Rich Console to print to; creates one if omitted.
    """
    from urllib.parse import urlparse
    from collections import defaultdict, Counter

    external = [r for r in results if r.link.is_external]
    if not external:
        return

    domain_total: dict[str, int] = defaultdict(int)
    domain_broken: dict[str, int] = defaultdict(int)
    domain_statuses: dict[str, Counter] = defaultdict(Counter)

    for r in external:
        try:
            domain = urlparse(r.link.url).netloc or r.link.url
        except Exception:
            domain = r.link.url

        domain_total[domain] += 1
        if not r.ok:
            domain_broken[domain] += 1
            domain_statuses[domain][r.status] += 1

    domains = sorted(domain_total.keys(), key=lambda d: (-domain_broken.get(d, 0), d))

    if _RICH:
        if console is None:
            console = Console(highlight=False)

        t = Table(
            box=rich_box.ROUNDED,
            show_header=True,
            header_style="bold cyan",
            border_style="cyan",
            title="[bold]Domain Health Summary[/bold]",
        )
        t.add_column("Domain", style="cyan", no_wrap=True)
        t.add_column("Total", justify="right", style="dim")
        t.add_column("Broken", justify="right")
        t.add_column("% Broken", justify="right")
        t.add_column("Top Status", style="dim")

        for domain in domains:
            total = domain_total[domain]
            broken = domain_broken.get(domain, 0)
            pct = f"{broken / total * 100:.0f}%" if total else "—"

            if broken == 0:
                broken_style = "green"
            elif broken / total >= 0.5:
                broken_style = "bold red"
            else:
                broken_style = "yellow"

            top_status = ""
            if domain_statuses[domain]:
                top_status = domain_statuses[domain].most_common(1)[0][0]

            t.add_row(
                domain,
                str(total),
                Text(str(broken), style=broken_style) if _RICH else str(broken),
                Text(pct, style=broken_style) if _RICH else pct,
                top_status,
            )

        console.print(t)
    else:
        print("\n--- Domain Health Summary ---")
        print(f"{'Domain':<40} {'Total':>6} {'Broken':>6} {'%':>7} {'Status'}")
        for domain in domains:
            total = domain_total[domain]
            broken = domain_broken.get(domain, 0)
            pct = f"{broken / total * 100:.0f}%" if total else "—"
            top = domain_statuses[domain].most_common(1)[0][0] if domain_statuses[domain] else ""
            print(f"{domain:<40} {total:>6} {broken:>6} {pct:>7} {top}")


def report_html(results: list[CheckResult], root: Path, show_ok: bool = False) -> str:
    """Return a self-contained HTML report with sortable, filterable results.

    The report uses inline CSS and vanilla JS — no external dependencies.
    Broken links are highlighted in red; warnings in amber; passing links
    appear only when *show_ok* is True.
    """
    from html import escape
    from datetime import datetime, timezone

    def _rel(cr: CheckResult) -> str:
        try:
            return str(cr.link.source_file.relative_to(root))
        except ValueError:
            return str(cr.link.source_file)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    total = len(results)
    broken_count = sum(1 for r in results if not r.ok)
    ok_count = total - broken_count

    visible = [r for r in results if not r.ok or show_ok]

    rows_html: list[str] = []
    for cr in sorted(visible, key=lambda r: (str(r.link.source_file), r.link.line_number)):
        if cr.ok:
            row_class = "ok"
            badge_class = "badge-ok"
            badge_text = cr.status
        elif cr.status == "anchor-missing":
            row_class = "warn"
            badge_class = "badge-warn"
            badge_text = cr.status
        elif cr.status == "timeout":
            row_class = "warn"
            badge_class = "badge-warn"
            badge_text = "timeout"
        else:
            row_class = "broken"
            badge_class = "badge-broken"
            badge_text = cr.status

        url_display = escape(cr.link.url + (f"#{cr.link.anchor}" if cr.link.anchor else ""))
        if cr.link.is_external:
            url_cell = f'<a href="{url_display}" target="_blank" rel="noopener">{url_display}</a>'
        else:
            url_cell = f'<code>{url_display}</code>'

        detail = escape(cr.detail or "")
        final_url = escape(cr.final_url or "")
        if final_url:
            detail = f'{detail} <span class="redirect">→ {final_url}</span>' if detail else f'<span class="redirect">→ {final_url}</span>'

        rows_html.append(
            f'<tr class="{row_class}">'
            f'<td><code>{escape(_rel(cr))}</code></td>'
            f'<td class="num">{cr.link.line_number}</td>'
            f'<td>{url_cell}</td>'
            f'<td><span class="badge {badge_class}">{escape(badge_text)}</span></td>'
            f'<td>{detail}</td>'
            f'</tr>'
        )

    rows_str = "\n".join(rows_html)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>linkrot report — {escape(str(root))}</title>
<style>
  :root {{
    --bg: #0d1117; --surface: #161b22; --border: #30363d;
    --text: #c9d1d9; --muted: #8b949e;
    --red: #f85149; --amber: #e3b341; --green: #3fb950;
    --link: #58a6ff;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font: 14px/1.5 "Segoe UI", system-ui, sans-serif; padding: 24px; }}
  h1 {{ font-size: 1.4rem; margin-bottom: 4px; }}
  .meta {{ color: var(--muted); font-size: 0.85rem; margin-bottom: 20px; }}
  .stats {{ display: flex; gap: 16px; margin-bottom: 20px; flex-wrap: wrap; }}
  .stat {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 12px 20px; min-width: 100px; text-align: center; }}
  .stat .num {{ font-size: 1.6rem; font-weight: 700; }}
  .stat .label {{ font-size: 0.75rem; color: var(--muted); text-transform: uppercase; letter-spacing: .05em; }}
  .stat.broken .num {{ color: var(--red); }}
  .stat.ok .num {{ color: var(--green); }}
  .controls {{ margin-bottom: 12px; display: flex; gap: 10px; flex-wrap: wrap; }}
  .controls input {{ background: var(--surface); border: 1px solid var(--border); color: var(--text); border-radius: 6px; padding: 6px 12px; font-size: 13px; width: 280px; outline: none; }}
  .controls input:focus {{ border-color: var(--link); }}
  .controls select {{ background: var(--surface); border: 1px solid var(--border); color: var(--text); border-radius: 6px; padding: 6px 10px; font-size: 13px; cursor: pointer; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ background: var(--surface); border-bottom: 2px solid var(--border); padding: 8px 10px; text-align: left; color: var(--muted); font-weight: 600; font-size: 0.78rem; text-transform: uppercase; letter-spacing: .04em; cursor: pointer; user-select: none; white-space: nowrap; }}
  th:hover {{ color: var(--text); }}
  td {{ border-bottom: 1px solid var(--border); padding: 7px 10px; vertical-align: top; }}
  td.num {{ text-align: right; color: var(--muted); font-variant-numeric: tabular-nums; }}
  tr.broken td {{ background: rgba(248,81,73,.05); }}
  tr.warn td {{ background: rgba(227,179,65,.04); }}
  tr:hover td {{ background: rgba(255,255,255,.04); }}
  a {{ color: var(--link); text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  code {{ font-size: 0.85em; color: #79c0ff; }}
  .badge {{ display: inline-block; padding: 1px 7px; border-radius: 12px; font-size: 0.78rem; font-weight: 600; }}
  .badge-broken {{ background: rgba(248,81,73,.2); color: var(--red); }}
  .badge-warn {{ background: rgba(227,179,65,.2); color: var(--amber); }}
  .badge-ok {{ background: rgba(63,185,80,.15); color: var(--green); }}
  .redirect {{ color: var(--amber); font-size: 0.85em; }}
  .hidden {{ display: none; }}
  footer {{ margin-top: 24px; color: var(--muted); font-size: 0.78rem; }}
</style>
</head>
<body>
<h1>linkrot report</h1>
<p class="meta">Root: <code>{escape(str(root))}</code> &nbsp;·&nbsp; Generated: {ts}</p>
<div class="stats">
  <div class="stat"><div class="num">{total}</div><div class="label">Total</div></div>
  <div class="stat broken"><div class="num">{broken_count}</div><div class="label">Broken</div></div>
  <div class="stat ok"><div class="num">{ok_count}</div><div class="label">Passing</div></div>
</div>
<div class="controls">
  <input type="text" id="search" placeholder="Filter by URL, file, or status…" oninput="filterRows()">
  <select id="statusFilter" onchange="filterRows()">
    <option value="">All statuses</option>
    <option value="broken">Broken only</option>
    <option value="warn">Warnings only</option>
    <option value="ok">Passing only</option>
  </select>
</div>
<table id="resultsTable">
  <thead>
    <tr>
      <th onclick="sortTable(0)">File ↕</th>
      <th onclick="sortTable(1)">Line ↕</th>
      <th onclick="sortTable(2)">URL ↕</th>
      <th onclick="sortTable(3)">Status ↕</th>
      <th>Detail</th>
    </tr>
  </thead>
  <tbody id="tbody">
{rows_str}
  </tbody>
</table>
<footer>Generated by <strong>linkrot</strong> · <a href="https://github.com/iamgeetarted/linkrot">github.com/iamgeetarted/linkrot</a></footer>
<script>
function filterRows() {{
  const q = document.getElementById('search').value.toLowerCase();
  const sf = document.getElementById('statusFilter').value;
  document.querySelectorAll('#tbody tr').forEach(tr => {{
    const text = tr.innerText.toLowerCase();
    const cls = tr.className;
    const matchText = !q || text.includes(q);
    const matchStatus = !sf || cls === sf;
    tr.classList.toggle('hidden', !(matchText && matchStatus));
  }});
}}
let sortDir = {{}};
function sortTable(col) {{
  const tbody = document.getElementById('tbody');
  const rows = Array.from(tbody.querySelectorAll('tr'));
  const dir = sortDir[col] = -(sortDir[col] || 1);
  rows.sort((a, b) => {{
    const av = a.cells[col]?.innerText.trim() || '';
    const bv = b.cells[col]?.innerText.trim() || '';
    return av.localeCompare(bv, undefined, {{numeric: true}}) * dir;
  }});
  rows.forEach(r => tbody.appendChild(r));
}}
</script>
</body>
</html>"""


def report_file_health(results: list[CheckResult], root: Path, console: "Console | None" = None) -> None:
    """Print a per-file health table sorted by most broken links first.

    Each row shows total links, broken count, passing count, and a health
    percentage so maintainers can quickly identify the most problematic files.
    """
    from collections import defaultdict

    file_total: dict[str, int] = defaultdict(int)
    file_broken: dict[str, int] = defaultdict(int)

    for cr in results:
        try:
            rel = str(cr.link.source_file.relative_to(root))
        except ValueError:
            rel = str(cr.link.source_file)
        file_total[rel] += 1
        if not cr.ok:
            file_broken[rel] += 1

    if not file_total:
        return

    files = sorted(file_total.keys(), key=lambda f: (-file_broken.get(f, 0), f))

    if _RICH:
        if console is None:
            console = Console(highlight=False)

        t = Table(
            box=rich_box.ROUNDED,
            show_header=True,
            header_style="bold cyan",
            border_style="cyan",
            title="[bold]Per-File Link Health[/bold]",
        )
        t.add_column("File", style="cyan", no_wrap=True)
        t.add_column("Total", justify="right", style="dim")
        t.add_column("Broken", justify="right")
        t.add_column("OK", justify="right", style="dim green")
        t.add_column("Health", justify="right")

        for rel in files:
            total = file_total[rel]
            broken = file_broken.get(rel, 0)
            ok = total - broken
            health_pct = (ok / total * 100) if total else 100.0
            health_str = f"{health_pct:.0f}%"

            if broken == 0:
                broken_style = "green"
                health_style = "bold green"
            elif health_pct < 50:
                broken_style = "bold red"
                health_style = "bold red"
            else:
                broken_style = "yellow"
                health_style = "yellow"

            t.add_row(
                rel,
                str(total),
                Text(str(broken), style=broken_style),
                str(ok),
                Text(health_str, style=health_style),
            )

        console.print(t)
    else:
        print("\n--- Per-File Link Health ---")
        print(f"{'File':<55} {'Total':>6} {'Broken':>7} {'OK':>5} {'Health':>7}")
        for rel in files:
            total = file_total[rel]
            broken = file_broken.get(rel, 0)
            ok = total - broken
            pct = f"{(ok / total * 100):.0f}%" if total else "100%"
            print(f"{rel:<55} {total:>6} {broken:>7} {ok:>5} {pct:>7}")


def report_impact_summary(
    results: list[CheckResult],
    root: Path,
    console: "Console | None" = None,
) -> None:
    """Print a table of broken URLs sorted by how many distinct files reference them."""
    from collections import defaultdict

    broken = [r for r in results if not r.ok]
    if not broken:
        return

    url_files: dict[str, set[str]] = defaultdict(set)
    url_status: dict[str, str] = {}
    for r in broken:
        try:
            rel = str(r.link.source_file.relative_to(root))
        except ValueError:
            rel = str(r.link.source_file)
        url = r.link.url
        url_files[url].add(rel)
        url_status[url] = r.status

    rows = sorted(url_files.items(), key=lambda x: -len(x[1]))

    def _impact_label(count: int) -> str:
        if count >= 3:
            return "HIGH"
        if count == 2:
            return "MEDIUM"
        return "LOW"

    if _RICH:
        if console is None:
            console = Console(highlight=False)

        t = Table(
            box=rich_box.ROUNDED,
            show_header=True,
            header_style="bold cyan",
            border_style="cyan",
            title="[bold]Broken Link Impact Summary[/bold]",
        )
        t.add_column("URL", no_wrap=False)
        t.add_column("Status", style="dim", no_wrap=True)
        t.add_column("Files Affected", justify="right")
        t.add_column("Impact", justify="center")

        for url, files in rows:
            count = len(files)
            label = _impact_label(count)
            if label == "HIGH":
                impact_text = Text(label, style="bold red")
            elif label == "MEDIUM":
                impact_text = Text(label, style="bold yellow")
            else:
                impact_text = Text(label, style="dim")
            t.add_row(url, url_status[url], str(count), impact_text)

        console.print(t)
    else:
        print("\n--- Broken Link Impact Summary ---")
        print(f"{'URL':<60} {'Status':<12} {'Files':>6} {'Impact'}")
        for url, files in rows:
            count = len(files)
            label = _impact_label(count)
            print(f"{url:<60} {url_status[url]:<12} {count:>6} {label}")


def report_rate_limit_summary(
    results: "list[CheckResult]",
    root: Path,
    console: "Console | None" = None,
) -> None:
    """Print a summary of domains that returned HTTP 429 (rate-limited).

    These results may be false negatives — the links could be valid but the
    checker was throttled by the server.

    Args:
        results: All check results from the scan.
        root: Root directory (unused, kept for API consistency).
        console: Rich Console to print to; creates one if omitted.
    """
    from urllib.parse import urlparse
    from collections import defaultdict

    rate_limited = [r for r in results if r.status == "http-429"]
    if not rate_limited:
        return

    domain_count: dict[str, int] = defaultdict(int)
    domain_sample: dict[str, str] = {}

    for r in rate_limited:
        try:
            domain = urlparse(r.link.url).netloc or r.link.url
        except Exception:
            domain = r.link.url
        domain_count[domain] += 1
        if domain not in domain_sample:
            domain_sample[domain] = r.link.url

    domains = sorted(domain_count.keys(), key=lambda d: (-domain_count[d], d))

    note = (
        "These may be false negatives — links appear broken due to rate limits, "
        "not actual link rot."
    )

    if _RICH:
        from rich.panel import Panel

        if console is None:
            console = Console(highlight=False)

        t = Table(
            box=rich_box.ROUNDED,
            show_header=True,
            header_style="bold cyan",
            border_style="yellow",
            title="[bold yellow]Rate-Limited Domains[/bold yellow]",
        )
        t.add_column("Domain", style="cyan", no_wrap=True)
        t.add_column("Count", justify="right", style="yellow")
        t.add_column("Sample URL", no_wrap=False)

        for domain in domains:
            t.add_row(domain, str(domain_count[domain]), domain_sample[domain])

        console.print(t)
        console.print(f"[dim]{note}[/dim]")
    else:
        print("\n--- Rate-Limited Domains ---")
        print(f"{'Domain':<40} {'Count':>6}  {'Sample URL'}")
        for domain in domains:
            print(f"{domain:<40} {domain_count[domain]:>6}  {domain_sample[domain]}")
        print(f"\nNote: {note}")


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
    elif fmt == "html":
        text = report_html(results, root, show_ok=show_ok)
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


def generate_badge_markdown(results: list[CheckResult]) -> str:
    """Return a shields.io Markdown badge reflecting the scan's link health.

    The badge encodes the pass-rate and uses colour thresholds:
      ≥ 99% → brightgreen  ≥ 95% → green  ≥ 90% → yellowgreen
      ≥ 80% → yellow  ≥ 70% → orange  < 70% → red
    """
    from urllib.parse import quote

    total = len(results)
    if total == 0:
        label = "no links"
        colour = "lightgrey"
        badge_text = "no links"
    else:
        broken = sum(1 for r in results if not r.ok)
        passing = total - broken
        pct = passing / total * 100

        if pct >= 99:
            colour = "brightgreen"
        elif pct >= 95:
            colour = "green"
        elif pct >= 90:
            colour = "yellowgreen"
        elif pct >= 80:
            colour = "yellow"
        elif pct >= 70:
            colour = "orange"
        else:
            colour = "red"

        badge_text = f"{passing} passing" if broken == 0 else f"{broken} broken"

    encoded = quote(badge_text, safe="")
    url = f"https://img.shields.io/badge/links-{encoded}-{colour}"
    return f"[![Link Health]({url})](https://github.com/iamgeetarted/linkrot)"
