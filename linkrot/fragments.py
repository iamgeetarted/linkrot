"""Validate internal anchor fragment links (#section-heading)."""

from __future__ import annotations

import re
from pathlib import Path


_HEADING_RE = re.compile(r'^#{1,6}\s+(.+)', re.MULTILINE)
_HTML_HEADING_RE = re.compile(r'<h[1-6][^>]*(?:id=["\']([^"\']+)["\'])?[^>]*>(.*?)</h[1-6]>', re.IGNORECASE | re.DOTALL)
_HTML_ID_RE = re.compile(r'\bid=["\']([^"\']+)["\']', re.IGNORECASE)
_STRIP_MD_RE = re.compile(r'[`*_\[\]()!]')


def _heading_to_anchor(heading_text: str) -> str:
    """Convert a Markdown heading string to its GitHub-style anchor fragment."""
    text = _STRIP_MD_RE.sub('', heading_text).strip().lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text).strip('-')
    return text


def collect_anchors(path: Path) -> set[str]:
    """Return all valid anchor IDs defined in *path* (headings + explicit id= attrs)."""
    try:
        content = path.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return set()

    anchors: set[str] = set()
    suffix = path.suffix.lower()

    if suffix in {'.md', '.markdown'}:
        for m in _HEADING_RE.finditer(content):
            anchors.add(_heading_to_anchor(m.group(1)))
        # Also pick up explicit {#id} syntax (Pandoc / kramdown)
        for m in re.finditer(r'\{#([\w-]+)\}', content):
            anchors.add(m.group(1))

    elif suffix in {'.html', '.htm'}:
        for m in _HTML_ID_RE.finditer(content):
            anchors.add(m.group(1))
        for m in _HTML_HEADING_RE.finditer(content):
            if m.group(1):
                anchors.add(m.group(1))
            else:
                raw_text = re.sub(r'<[^>]+>', '', m.group(2))
                anchors.add(_heading_to_anchor(raw_text))

    return anchors


@dataclass_like := None  # avoid unused import


def validate_fragments(links: list, root: Path) -> list[dict]:
    """
    Check each internal link's anchor fragment against the target file.

    Returns a list of dicts:
        {link, target_file, anchor, valid}
    for every link that has a non-empty anchor.
    """
    from .scanner import Link  # local import to avoid circulars

    results = []
    anchor_cache: dict[Path, set[str]] = {}

    for link in links:
        if link.is_external or not link.anchor:
            continue

        # Resolve target file relative to source
        src_dir = link.source_file.parent
        target_path_raw = link.url if link.url else link.source_file
        if link.url:
            candidate = (src_dir / link.url).resolve()
        else:
            candidate = link.source_file.resolve()

        # Also try appending .md / .html if target has no extension
        resolved: Path | None = None
        for candidate_path in [
            candidate,
            candidate.with_suffix('.md'),
            candidate.with_suffix('.html'),
        ]:
            if candidate_path.is_file():
                resolved = candidate_path
                break

        if resolved is None:
            # Target file itself is missing — checker will report the dead link
            results.append({
                'link': link,
                'target_file': candidate,
                'anchor': link.anchor,
                'valid': False,
                'reason': 'target file not found',
            })
            continue

        if resolved not in anchor_cache:
            anchor_cache[resolved] = collect_anchors(resolved)

        valid = link.anchor.lower() in anchor_cache[resolved]
        results.append({
            'link': link,
            'target_file': resolved,
            'anchor': link.anchor,
            'valid': valid,
            'reason': '' if valid else f'#{link.anchor} not found in {resolved.name}',
        })

    return results
