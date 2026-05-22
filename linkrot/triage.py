"""AI-powered triage of broken links via the Anthropic API."""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .checker import CheckResult


def triage_broken_links(results: list[CheckResult]) -> None:
    """Stream a Claude analysis that prioritizes and categorizes broken links."""
    try:
        import anthropic
    except ImportError:
        print(
            "pip install anthropic  # required for --triage",
            file=sys.stderr,
        )
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print(
            "ANTHROPIC_API_KEY is not set — export it to use --triage",
            file=sys.stderr,
        )
        return

    broken = [r for r in results if not r.ok]
    if not broken:
        print("\nNo broken links to triage.")
        return

    missing_file = [r for r in broken if r.status == "missing"]
    http_404 = [r for r in broken if r.status == "http-404"]
    http_5xx = [r for r in broken if r.status.startswith("http-5")]
    timeout = [r for r in broken if r.status == "timeout"]
    other = [r for r in broken if r not in missing_file + http_404 + http_5xx + timeout]

    def _fmt_group(label: str, items: list[CheckResult]) -> str:
        if not items:
            return ""
        lines = [f"{label} ({len(items)}):"]
        for r in items[:10]:
            lines.append(f"  - {r.link.url}  [{r.detail or r.status}]")
        if len(items) > 10:
            lines.append(f"  ... and {len(items) - 10} more")
        return "\n".join(lines)

    sections = [
        _fmt_group("Missing internal files", missing_file),
        _fmt_group("HTTP 404 (Not Found)", http_404),
        _fmt_group("HTTP 5xx (Server errors)", http_5xx),
        _fmt_group("Timeouts", timeout),
        _fmt_group("Other errors", other),
    ]
    body = "\n\n".join(s for s in sections if s)

    prompt = (
        "You are a documentation maintenance expert. The following broken links were found "
        "grouped by failure category.\n\n"
        f"{body}\n\n"
        "Please provide a concise triage report that:\n"
        "1. Prioritizes which category to fix first (consider impact and recoverability)\n"
        "2. Suggests a concrete fix strategy for each category present\n"
        "3. Estimates the relative effort for each category (Low / Medium / High)\n\n"
        "Be direct and actionable. Use plain text with numbered sections."
    )

    client = anthropic.Anthropic(api_key=api_key)

    try:
        from rich.console import Console
        from rich.rule import Rule

        console = Console()
        console.print()
        console.print(Rule("[bold cyan]AI Triage Report[/bold cyan]"))
    except ImportError:
        print("\n--- AI Triage Report ---")

    with client.messages.stream(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
    print()
