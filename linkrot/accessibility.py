"""Check link text accessibility — flag non-descriptive anchor text."""

from __future__ import annotations

import re
from pathlib import Path


_NON_DESCRIPTIVE = frozenset({
    'here', 'click', 'click here', 'this', 'this link', 'this page', 'this article',
    'this post', 'link', 'url', 'read more', 'more', 'details', 'learn more',
    'view', 'see', 'go', 'continue', 'source', 'reference', 'ref', 'info',
    'information', 'page', 'article', 'post', 'doc', 'docs', 'documentation',
    'website', 'site', 'visit',
})

_MD_LINK_TEXT_RE = re.compile(r'\[([^\]]*)\]\(([^)]+)\)')
_HTML_LINK_TEXT_RE = re.compile(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
_HTML_TAG_RE = re.compile(r'<[^>]+>')
_CODE_SPAN_RE = re.compile(r'`[^`]*`')
_CODE_FENCE_RE = re.compile(r'^```', re.MULTILINE)


def _is_non_descriptive(text: str) -> bool:
    cleaned = _HTML_TAG_RE.sub('', text).strip().lower()
    cleaned = re.sub(r'\s+', ' ', cleaned)
    # Ignore purely numeric or icon-only text (e.g. "↗", "🔗")
    if not cleaned or re.fullmatch(r'[\d\s]+', cleaned):
        return False
    return cleaned in _NON_DESCRIPTIVE


def _iter_non_code(content: str):
    """Yield (lineno_offset, segment) for content outside fenced code blocks."""
    segments = _CODE_FENCE_RE.split(content)
    lineno = 1
    for i, seg in enumerate(segments):
        if i % 2 == 0:
            yield lineno, seg
        lineno += seg.count('\n')


def check_accessibility(path: Path) -> list[dict]:
    """
    Scan *path* for links with non-descriptive anchor text.

    Returns a list of dicts: {file, line, url, text, issue}.
    """
    try:
        content = path.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return []

    suffix = path.suffix.lower()
    issues = []

    if suffix in {'.md', '.markdown'}:
        for base_lineno, block in _iter_non_code(content):
            block_lines = block.splitlines()
            for rel_lineno, raw_line in enumerate(block_lines):
                lineno = base_lineno + rel_lineno
                line = _CODE_SPAN_RE.sub(lambda m: ' ' * len(m.group()), raw_line)
                for m in _MD_LINK_TEXT_RE.finditer(line):
                    text, url = m.group(1).strip(), m.group(2).strip()
                    if not text:
                        issues.append({
                            'file': path,
                            'line': lineno,
                            'url': url,
                            'text': '(empty)',
                            'issue': 'empty link text',
                        })
                    elif _is_non_descriptive(text):
                        issues.append({
                            'file': path,
                            'line': lineno,
                            'url': url,
                            'text': text,
                            'issue': f'non-descriptive link text: "{text}"',
                        })

    elif suffix in {'.html', '.htm'}:
        lines = content.splitlines()
        for lineno, line in enumerate(lines, 1):
            for m in _HTML_LINK_TEXT_RE.finditer(line):
                url, raw_text = m.group(1).strip(), m.group(2)
                text = _HTML_TAG_RE.sub('', raw_text).strip()
                if not text:
                    issues.append({
                        'file': path,
                        'line': lineno,
                        'url': url,
                        'text': '(empty)',
                        'issue': 'empty link text',
                    })
                elif _is_non_descriptive(text):
                    issues.append({
                        'file': path,
                        'line': lineno,
                        'url': url,
                        'text': text,
                        'issue': f'non-descriptive link text: "{text}"',
                    })

    return issues


def scan_accessibility(paths: list[Path]) -> list[dict]:
    """Run accessibility checks across all *paths* (files or directories)."""
    extensions = {'.md', '.markdown', '.html', '.htm'}
    issues = []
    for p in paths:
        if p.is_file() and p.suffix.lower() in extensions:
            issues.extend(check_accessibility(p))
        elif p.is_dir():
            for f in p.rglob('*'):
                if f.is_file() and f.suffix.lower() in extensions:
                    skip_dirs = {'.git', 'node_modules', '.venv', '__pycache__', 'vendor'}
                    if not any(part in skip_dirs for part in f.parts):
                        issues.extend(check_accessibility(f))
    return issues
