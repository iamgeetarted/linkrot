"""Interactive broken-link fixer — edits source files in-place."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .checker import CheckResult


def _ask(prompt: str) -> str:
    """Read a line from stdin, stripping whitespace."""
    try:
        return input(prompt).strip()
    except EOFError:
        return ""


def interactive_fix(results: list["CheckResult"], root: Path) -> int:
    """Interactively walk broken links and offer to rewrite them in source files.

    For each broken link the user can:
    - Type a replacement URL → written into the source file.
    - Press Enter (blank) → skip this link.
    - Type ``q`` → quit immediately.

    Returns the number of links that were actually fixed.
    """
    broken = [r for r in results if not r.ok]
    if not broken:
        print("No broken links to fix.")
        return 0

    try:
        from rich.console import Console
        from rich.rule import Rule
        from rich.panel import Panel
        console: object | None = Console()
    except ImportError:
        console = None

    def _print_header(idx: int, total: int, cr: "CheckResult") -> None:
        try:
            rel = str(cr.link.source_file.relative_to(root))
        except ValueError:
            rel = str(cr.link.source_file)
        if console is not None:
            from rich.console import Console as RC
            assert isinstance(console, RC)
            console.print()
            console.print(Rule(f"[bold]Broken link {idx}/{total}[/bold]", style="red"))
            console.print(f"  [bold red]URL:[/bold red]    {cr.link.url}")
            console.print(f"  [bold yellow]Status:[/bold yellow] {cr.status}  {cr.detail}")
            console.print(f"  [bold cyan]File:[/bold cyan]   {rel}  (line {cr.link.line_number})")
            console.print()
        else:
            print(f"\n--- [{idx}/{total}] Broken link ---")
            print(f"  URL:    {cr.link.url}")
            print(f"  Status: {cr.status}  {cr.detail}")
            print(f"  File:   {rel}  (line {cr.link.line_number})")

    fixed = 0
    for idx, cr in enumerate(broken, 1):
        _print_header(idx, len(broken), cr)

        answer = _ask("  Replacement URL (blank=skip, q=quit): ")
        if answer.lower() == "q":
            break
        if not answer:
            continue

        replacement = answer

        # Rewrite the source file
        try:
            src = cr.link.source_file
            content = src.read_text(encoding="utf-8")
            original_url = cr.link.url
            new_content = _replace_url(content, original_url, replacement, src)
            if new_content == content:
                if console is not None:
                    from rich.console import Console as RC
                    assert isinstance(console, RC)
                    console.print(f"  [yellow]⚠ URL not found verbatim in file — skipped.[/yellow]")
                else:
                    print("  ⚠ URL not found verbatim in file — skipped.")
                continue
            src.write_text(new_content, encoding="utf-8")
            fixed += 1
            if console is not None:
                from rich.console import Console as RC
                assert isinstance(console, RC)
                console.print(f"  [bold green]✓ Fixed[/bold green] → {replacement}")
            else:
                print(f"  ✓ Fixed → {replacement}")
        except OSError as exc:
            if console is not None:
                from rich.console import Console as RC
                assert isinstance(console, RC)
                console.print(f"  [red]✗ Could not write {cr.link.source_file}: {exc}[/red]")
            else:
                print(f"  ✗ Could not write {cr.link.source_file}: {exc}")

    if console is not None:
        from rich.console import Console as RC
        assert isinstance(console, RC)
        console.print()
        console.print(f"[bold]Fixed {fixed} / {len(broken)} broken link(s).[/bold]\n")
    else:
        print(f"\nFixed {fixed} / {len(broken)} broken link(s).")

    return fixed


def _replace_url(content: str, old_url: str, new_url: str, path: Path) -> str:
    """Replace the first occurrence of *old_url* with *new_url* in *content*.

    Handles Markdown ``[text](url)`` and HTML ``href="url"`` / ``src="url"``
    patterns so anchors and query strings are preserved correctly.
    """
    escaped = re.escape(old_url)

    # Try Markdown link/image pattern first: ](url) or ](url "title")
    md_pattern = r"(\]\()(" + escaped + r")([\s\)\"])"
    replaced, n = re.subn(md_pattern, rf"\g<1>{new_url}\g<3>", content, count=1)
    if n:
        return replaced

    # Try HTML attribute patterns: href="url" src="url"
    html_pattern = r'((?:href|src)=["\'])(' + escaped + r')(["\'])'
    replaced, n = re.subn(html_pattern, rf"\g<1>{new_url}\g<3>", content, count=1)
    if n:
        return replaced

    # Bare URL (plain text or RST)
    replaced, n = re.subn(escaped, new_url, content, count=1)
    return replaced
