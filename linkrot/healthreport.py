"""Streaming AI health report — strategic analysis of the full scan."""

from __future__ import annotations

import os
import sys
from collections import Counter
from urllib.parse import urlparse
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .checker import CheckResult


def ai_health_report(results: list["CheckResult"], root: object) -> None:
    """Stream a holistic AI health report using claude-sonnet-4-6."""
    try:
        import anthropic
    except ImportError:
        print("pip install anthropic  # required for --ai-health-report", file=sys.stderr)
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY is not set — export it to use --ai-health-report", file=sys.stderr)
        return

    total = len(results)
    broken = [r for r in results if not r.ok]
    ok_count = total - len(broken)

    if not total:
        print("No links to analyse.")
        return

    # Build compact stats for the prompt
    status_counts = Counter(r.status for r in broken)
    domain_broken: Counter = Counter()
    for r in broken:
        if r.link.is_external:
            try:
                domain_broken[urlparse(r.link.url).netloc] += 1
            except Exception:
                pass

    from collections import defaultdict
    try:
        file_broken: dict = defaultdict(int)
        for r in broken:
            file_broken[r.link.source_file.name] += 1
        top_files = sorted(file_broken.items(), key=lambda x: -x[1])[:5]
    except Exception:
        top_files = []

    top_domains = domain_broken.most_common(5)
    external_broken = sum(1 for r in broken if r.link.is_external)
    internal_broken = sum(1 for r in broken if not r.link.is_external)

    status_summary = ", ".join(f"{s}: {c}" for s, c in sorted(status_counts.items(), key=lambda x: -x[1]))
    domain_summary = ", ".join(f"{d}: {c}" for d, c in top_domains) if top_domains else "none"
    file_summary = ", ".join(f"{f}: {c}" for f, c in top_files) if top_files else "none"

    broken_samples = "\n".join(
        f"  - [{r.status}] {r.link.url[:80]}{'...' if len(r.link.url) > 80 else ''}"
        for r in broken[:15]
    )

    prompt = f"""You are a documentation quality engineer. Analyse this broken-link scan and write a concise strategic health report.

SCAN STATISTICS
  Total links checked : {total}
  Passing             : {ok_count} ({ok_count / total * 100:.1f}%)
  Broken              : {len(broken)} ({len(broken) / total * 100:.1f}%)
  External broken     : {external_broken}
  Internal broken     : {internal_broken}
  Failure types       : {status_summary if status_summary else "none"}
  Top broken domains  : {domain_summary}
  Top files w/ breaks : {file_summary}

SAMPLE BROKEN LINKS (up to 15)
{broken_samples if broken_samples else "  (none)"}

Write a report in this structure (use ## headers, bullets, be specific):

## Executive Summary
2-3 sentences: overall health, most critical finding.

## Root Cause Analysis
What patterns explain the breakage? (domain migrations, deprecated paths, etc.)

## Priority Actions
3-5 specific, actionable fixes — most impactful first.

## Prevention Recommendations
2-3 process/tooling improvements to prevent future rot.

Be direct, developer-focused, and cite specific domains or patterns from the data."""

    client = anthropic.Anthropic(api_key=api_key)

    try:
        from rich.console import Console
        from rich.rule import Rule
        console = Console()
        console.print()
        console.print(Rule("[bold cyan]AI Health Report[/bold cyan]"))
        console.print()
    except ImportError:
        print("\n--- AI Health Report ---\n")

    with client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=1200,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
    print("\n")
