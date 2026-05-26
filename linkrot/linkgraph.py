"""Build and export a file-to-file link dependency graph."""

from __future__ import annotations

import json
from pathlib import Path


def build_graph(links: list, root: Path) -> dict[str, list[str]]:
    """
    Build an adjacency map {source_file → [target_file, ...]} from *links*.

    Only internal (non-external) links are included. Paths are expressed
    relative to *root* for portability.
    """
    graph: dict[str, list[str]] = {}

    for link in links:
        if link.is_external:
            continue

        try:
            src = str(link.source_file.relative_to(root))
        except ValueError:
            src = str(link.source_file)

        if not link.url:
            continue

        target_raw = (link.source_file.parent / link.url).resolve()
        try:
            tgt = str(target_raw.relative_to(root))
        except ValueError:
            tgt = str(target_raw)

        graph.setdefault(src, [])
        if tgt not in graph[src]:
            graph[src].append(tgt)

    return graph


def export_json(graph: dict[str, list[str]]) -> str:
    """Serialise the graph as a JSON adjacency list."""
    return json.dumps(graph, indent=2, sort_keys=True)


def export_markdown(graph: dict[str, list[str]], root: Path | None = None) -> str:
    """Render the graph as a Markdown document."""
    lines = ['# Link Graph\n']
    if not graph:
        lines.append('_No internal links found._\n')
        return '\n'.join(lines)

    lines.append('## File Dependencies (source → targets)\n')
    for src in sorted(graph):
        targets = sorted(graph[src])
        lines.append(f'### `{src}`\n')
        for tgt in targets:
            lines.append(f'- `{tgt}`')
        lines.append('')

    # Reverse index: which files link TO each file
    reverse: dict[str, list[str]] = {}
    for src, targets in graph.items():
        for tgt in targets:
            reverse.setdefault(tgt, []).append(src)

    lines.append('## Inbound Links (target ← sources)\n')
    for tgt in sorted(reverse):
        sources = sorted(reverse[tgt])
        lines.append(f'### `{tgt}`\n')
        for s in sources:
            lines.append(f'- `{s}`')
        lines.append('')

    return '\n'.join(lines)


def print_graph_rich(graph: dict[str, list[str]], console: object) -> None:
    """Pretty-print the graph to a Rich console."""
    from rich.table import Table, box as rbox
    from rich.panel import Panel

    if not graph:
        console.print('[dim]No internal links found for graph.[/dim]')
        return

    # Reverse index
    reverse: dict[str, list[str]] = {}
    for src, targets in graph.items():
        for tgt in targets:
            reverse.setdefault(tgt, []).append(src)

    t = Table(
        box=rbox.ROUNDED,
        show_header=True,
        header_style='bold cyan',
        border_style='dim',
    )
    t.add_column('Source', style='cyan')
    t.add_column('Links to', style='white')
    t.add_column('Linked from', style='dim')

    for src in sorted(graph):
        targets_str = ', '.join(sorted(graph[src]))
        sources_str = ', '.join(sorted(reverse.get(src, [])))
        t.add_row(src, targets_str, sources_str)

    # Files that are only targets (no outbound links)
    only_targets = sorted(set(reverse) - set(graph))
    for tgt in only_targets:
        sources_str = ', '.join(sorted(reverse[tgt]))
        t.add_row(f'[dim]{tgt}[/dim]', '—', sources_str)

    node_count = len(set(graph) | set(reverse))
    edge_count = sum(len(v) for v in graph.values())
    console.print(Panel(
        t,
        title=f'[bold]Link Graph[/bold] — {node_count} files, {edge_count} edges',
        border_style='cyan',
        box=rbox.ROUNDED,
    ))
