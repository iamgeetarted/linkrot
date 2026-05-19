"""Query the Wayback Machine CDX API for archived snapshots of dead URLs."""

from __future__ import annotations

import json
import urllib.request
import urllib.parse
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .checker import CheckResult

_CDX_API = "http://archive.org/wayback/available"
_TIMEOUT = 8.0


def lookup_snapshot(url: str) -> str | None:
    """Return the closest Wayback Machine snapshot URL for *url*, or None.

    Uses the Wayback Availability JSON API which is free and requires no auth.
    """
    try:
        params = urllib.parse.urlencode({"url": url})
        req = urllib.request.Request(
            f"{_CDX_API}?{params}",
            headers={"User-Agent": "linkrot/1.9 (https://github.com/iamgeetarted/linkrot)"},
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read())
        snapshot = data.get("archived_snapshots", {}).get("closest", {})
        if snapshot.get("available") and snapshot.get("url"):
            return snapshot["url"]
    except Exception:
        pass
    return None


def enrich_with_wayback(results: "list[CheckResult]") -> dict[str, str | None]:
    """For every broken external URL, look up an archive snapshot.

    Returns a mapping of ``url → snapshot_url`` (snapshot_url is None when no
    archive is available or the lookup failed).  Only URLs with status
    ``http-404`` or ``error`` are queried to keep API traffic minimal.
    """
    target_statuses = {"http-404", "error", "missing"}
    broken_external = [
        r for r in results
        if not r.ok and r.link.is_external and r.status in target_statuses
    ]
    # Deduplicate by URL
    seen: set[str] = set()
    unique = [r for r in broken_external if not (r.link.url in seen or seen.add(r.link.url))]  # type: ignore[func-returns-value]

    snapshots: dict[str, str | None] = {}
    for cr in unique:
        snapshots[cr.link.url] = lookup_snapshot(cr.link.url)
    return snapshots


def print_wayback_report(results: "list[CheckResult]", snapshots: dict[str, str | None]) -> None:
    """Print a Rich (or plain) table of Wayback snapshots for broken links."""
    hits = {url: snap for url, snap in snapshots.items() if snap}
    misses = {url for url in snapshots if not snapshots[url]}

    try:
        from rich.console import Console
        from rich.table import Table, box as rbox
        from rich.rule import Rule

        console = Console()
        console.print()
        console.print(Rule("[bold cyan]Wayback Machine Snapshots[/bold cyan]"))
        console.print()

        if hits:
            t = Table(box=rbox.ROUNDED, show_header=True, header_style="bold cyan", border_style="dim")
            t.add_column("Broken URL", style="red", no_wrap=False)
            t.add_column("Archived Snapshot", style="cyan", no_wrap=False)
            for url, snap in sorted(hits.items()):
                t.add_row(url, snap or "")
            console.print(t)
            console.print(
                f"  [dim]{len(hits)} snapshot{'s' if len(hits) != 1 else ''} found · "
                f"{len(misses)} not archived[/dim]\n"
            )
        else:
            console.print(
                f"[dim]No Wayback Machine snapshots found for {len(misses)} broken URL(s).[/dim]\n"
            )

    except ImportError:
        print("\n--- Wayback Machine Snapshots ---")
        for url, snap in sorted(snapshots.items()):
            if snap:
                print(f"  ✓ {url}\n    → {snap}")
            else:
                print(f"  ✗ {url}  (no snapshot)")
        print()
