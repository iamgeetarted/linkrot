"""Scan files for links and extract them with location metadata."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generator


@dataclass
class Link:
    url: str
    source_file: Path
    line_number: int
    anchor: str = ""
    is_external: bool = False

    def __post_init__(self):
        self.is_external = self.url.startswith(("http://", "https://", "//"))
        if "#" in self.url and not self.is_external:
            parts = self.url.split("#", 1)
            self.url = parts[0]
            self.anchor = parts[1]
        elif "#" in self.url and self.is_external:
            # Keep full URL but note anchor separately for display
            pass


@dataclass
class ScanResult:
    links: list[Link] = field(default_factory=list)
    files_scanned: int = 0


_MD_LINK_RE = re.compile(r'\[(?:[^\]]*)\]\(([^)]+)\)')
_MD_REF_RE = re.compile(r'^\[(?:[^\]]+)\]:\s+(\S+)', re.MULTILINE)
_MD_IMG_RE = re.compile(r'!\[(?:[^\]]*)\]\(([^)]+)\)')
_HTML_HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
_HTML_SRC_RE = re.compile(r'src=["\']([^"\']+)["\']', re.IGNORECASE)

_SKIP_SCHEMES = {"mailto:", "tel:", "javascript:", "#", "data:"}


def _should_skip(url: str) -> bool:
    url = url.strip()
    if not url:
        return True
    return any(url.startswith(s) for s in _SKIP_SCHEMES)


_CODE_SPAN_RE = re.compile(r'`[^`]*`')
_CODE_FENCE_RE = re.compile(r'^```', re.MULTILINE)


def _strip_code_spans(line: str) -> str:
    """Replace backtick code spans with blanks so link patterns don't match inside them."""
    return _CODE_SPAN_RE.sub(lambda m: ' ' * len(m.group()), line)


def _iter_non_code_blocks(content: str):
    """Yield (lineno_start, block_text) for sections outside fenced code blocks."""
    segments = _CODE_FENCE_RE.split(content)
    lineno = 1
    for i, seg in enumerate(segments):
        if i % 2 == 0:  # outside a code fence
            yield lineno, seg
        lineno += seg.count("\n")


def _extract_from_markdown(content: str, path: Path) -> list[Link]:
    links = []

    patterns = [_MD_LINK_RE, _MD_IMG_RE]
    for block_start_lineno, block in _iter_non_code_blocks(content):
        block_lines = block.splitlines()
        for rel_lineno, raw_line in enumerate(block_lines):
            lineno = block_start_lineno + rel_lineno
            line = _strip_code_spans(raw_line)
            for pat in patterns:
                for m in pat.finditer(line):
                    url = m.group(1).strip()
                    url = re.split(r'\s+"', url)[0].strip()
                    if not _should_skip(url):
                        links.append(Link(url=url, source_file=path, line_number=lineno))

            # Reference-style links at the start of a line
            ref_m = _MD_REF_RE.match(line)
            if ref_m:
                url = ref_m.group(1).strip()
                if not _should_skip(url):
                    links.append(Link(url=url, source_file=path, line_number=lineno))

    return links


def _extract_from_html(content: str, path: Path) -> list[Link]:
    links = []
    lines = content.splitlines()

    for lineno, line in enumerate(lines, start=1):
        for pat in [_HTML_HREF_RE, _HTML_SRC_RE]:
            for m in pat.finditer(line):
                url = m.group(1).strip()
                if not _should_skip(url):
                    links.append(Link(url=url, source_file=path, line_number=lineno))

    return links


def _iter_files(root: Path, extensions: set[str]) -> Generator[Path, None, None]:
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in extensions:
            yield p


def scan_directory(
    root: Path,
    extensions: set[str] | None = None,
    ignore_dirs: set[str] | None = None,
) -> ScanResult:
    if extensions is None:
        extensions = {".md", ".markdown", ".html", ".htm"}
    if ignore_dirs is None:
        ignore_dirs = {".git", "node_modules", ".venv", "__pycache__", "vendor"}

    result = ScanResult()

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in ignore_dirs for part in path.parts):
            continue
        if path.suffix.lower() not in extensions:
            continue

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        result.files_scanned += 1
        suffix = path.suffix.lower()

        if suffix in {".md", ".markdown"}:
            result.links.extend(_extract_from_markdown(content, path))
        elif suffix in {".html", ".htm"}:
            result.links.extend(_extract_from_html(content, path))

    return result
