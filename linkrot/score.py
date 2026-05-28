"""Compute a 0-100 link health score for CI gating and trending."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .checker import CheckResult


_GRADE_THRESHOLDS = [
    (97, "A+"),
    (93, "A"),
    (90, "A-"),
    (87, "B+"),
    (83, "B"),
    (80, "B-"),
    (77, "C+"),
    (73, "C"),
    (70, "C-"),
    (67, "D+"),
    (60, "D"),
    (0,  "F"),
]


def _grade(score: float) -> str:
    for threshold, letter in _GRADE_THRESHOLDS:
        if score >= threshold:
            return letter
    return "F"


def compute_score(results: list["CheckResult"]) -> dict:
    """Return a health score dict with overall score, grade, and breakdown."""
    total = len(results)
    if total == 0:
        return {"score": 100, "grade": "A+", "total": 0, "broken": 0, "pct_ok": 100.0, "breakdown": {}}

    broken = [r for r in results if not r.ok]
    broken_count = len(broken)
    ok_count = total - broken_count
    pct_ok = ok_count / total * 100

    # Base score from pass rate
    base = pct_ok

    # Penalty multipliers
    # High-severity 5xx errors are worse than 4xx
    http5xx = sum(1 for r in broken if r.status.startswith("http-5"))
    timeout = sum(1 for r in broken if r.status == "timeout")
    missing = sum(1 for r in broken if r.status == "missing")

    # Each severe failure subtracts a small extra point from the base
    penalty = (http5xx * 0.1 + timeout * 0.05 + missing * 0.08) / max(total, 1) * 100
    score = max(0.0, min(100.0, base - penalty))

    breakdown = {
        "total": total,
        "ok": ok_count,
        "broken": broken_count,
        "pct_ok": round(pct_ok, 1),
        "http_5xx": http5xx,
        "timeouts": timeout,
        "missing": missing,
    }

    return {
        "score": round(score, 1),
        "grade": _grade(score),
        "total": total,
        "broken": broken_count,
        "pct_ok": round(pct_ok, 1),
        "breakdown": breakdown,
    }


def print_score(results: list["CheckResult"], console: object | None = None) -> None:
    """Print the health score panel to console (Rich if available)."""
    info = compute_score(results)
    score = info["score"]
    grade = info["grade"]
    bd = info["breakdown"]

    try:
        from rich.console import Console as _Console
        from rich.table import Table, box as rbox
        from rich.panel import Panel
        from rich.text import Text

        if console is None:
            console = _Console(highlight=False)

        if score >= 90:
            score_style = "bold green"
        elif score >= 70:
            score_style = "bold yellow"
        else:
            score_style = "bold red"

        t = Table(box=rbox.SIMPLE, show_header=False, pad_edge=False)
        t.add_column("Metric", style="cyan")
        t.add_column("Value", justify="right")

        t.add_row("Links checked", str(bd["total"]))
        t.add_row("Passing", f"[green]{bd['ok']}[/green]")
        t.add_row("Broken", f"[red]{bd['broken']}[/red]" if bd["broken"] else "[green]0[/green]")
        if bd["http_5xx"]:
            t.add_row("  HTTP 5xx", f"[red]{bd['http_5xx']}[/red]")
        if bd["timeouts"]:
            t.add_row("  Timeouts", f"[yellow]{bd['timeouts']}[/yellow]")
        if bd["missing"]:
            t.add_row("  Missing", f"[red]{bd['missing']}[/red]")
        t.add_section()
        t.add_row("Pass rate", f"{bd['pct_ok']}%")
        t.add_row("Health score", Text(f"{score}  {grade}", style=score_style))

        console.print(Panel(t, title="[bold]Link Health Score[/bold]", border_style="cyan", box=rbox.ROUNDED))

    except ImportError:
        print("\n--- Link Health Score ---")
        print(f"  Score : {score}  ({grade})")
        print(f"  Total : {bd['total']}")
        print(f"  OK    : {bd['ok']}  ({bd['pct_ok']}%)")
        print(f"  Broken: {bd['broken']}")
