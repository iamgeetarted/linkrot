"""AI-powered fix suggestions for broken links via the Anthropic API."""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .checker import CheckResult


def suggest_fixes(results: list[CheckResult]) -> None:
    """Stream Claude Haiku suggestions for each broken external URL."""
    try:
        import anthropic
    except ImportError:
        print("pip install anthropic  # required for --suggest", file=sys.stderr)
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print(
            "ANTHROPIC_API_KEY is not set — export it to use --suggest",
            file=sys.stderr,
        )
        return

    broken = [r for r in results if not r.ok and r.link.is_external]
    if not broken:
        print("\nNo broken external links to suggest fixes for.")
        return

    # Cap at 20 to keep the prompt focused
    sample = broken[:20]
    lines = "\n".join(
        f"{i+1}. {r.link.url}  [{r.status}] {r.detail}".strip()
        for i, r in enumerate(sample)
    )

    prompt = (
        "The following external URLs were found broken in documentation files.\n\n"
        f"{lines}\n\n"
        "For each URL give one concise line:\n"
        "• Why it is likely broken (moved, deprecated, merged, domain change, etc.)\n"
        "• The best replacement URL or search query to find it, if you can infer one\n"
        "• Whether web.archive.org likely has a snapshot\n\n"
        "Format: `N. <reason> → <suggestion>`\n"
        "Be brief. Skip speculation when you have no signal."
    )

    client = anthropic.Anthropic(api_key=api_key)

    try:
        from rich.console import Console
        from rich.rule import Rule

        console = Console()
        console.print()
        console.print(Rule("[bold cyan]AI Suggestions for Broken Links[/bold cyan]"))
    except ImportError:
        print("\n--- AI Suggestions for Broken Links ---")

    with client.messages.stream(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
    print()
