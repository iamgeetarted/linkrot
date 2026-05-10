"""Discover links from sitemap.xml / sitemap_index.xml files."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from .scanner import Link

_SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
_SITEMAP_FILENAMES = ("sitemap.xml", "sitemap_index.xml")


def _parse_locs(root_elem: ET.Element) -> list[str]:
    """Return all <loc> text values from an already-parsed XML element tree."""
    urls: list[str] = []
    # Try namespace-qualified tags first, then bare tags
    for tag in (f"{{{_SITEMAP_NS}}}loc", "loc"):
        for elem in root_elem.iter(tag):
            text = (elem.text or "").strip()
            if text:
                urls.append(text)
        if urls:
            break
    return urls


def _is_sitemap_index(root_elem: ET.Element) -> bool:
    """Return True if the document root is a <sitemapindex> element."""
    tag = root_elem.tag
    # Strip namespace if present
    if "}" in tag:
        tag = tag.split("}", 1)[1]
    return tag == "sitemapindex"


def _parse_sitemap_file(path: Path) -> tuple[bool, list[str]]:
    """Parse a local sitemap file.

    Returns (is_index, urls) where is_index means the document is a
    sitemapindex listing other sitemaps rather than page <loc> entries.
    """
    try:
        tree = ET.parse(path)
    except ET.ParseError:
        return False, []

    root_elem = tree.getroot()
    is_index = _is_sitemap_index(root_elem)
    urls = _parse_locs(root_elem)
    return is_index, urls


def _parse_sitemap_text(text: str) -> tuple[bool, list[str]]:
    """Parse a sitemap from a string (used when fetching referenced sitemaps)."""
    try:
        root_elem = ET.fromstring(text)
    except ET.ParseError:
        return False, []

    is_index = _is_sitemap_index(root_elem)
    urls = _parse_locs(root_elem)
    return is_index, urls


def _fetch_remote_sitemap(url: str) -> tuple[bool, list[str]]:
    """Fetch a remote sitemap URL and parse it. Falls back to empty list on error."""
    try:
        import urllib.request

        with urllib.request.urlopen(url, timeout=15) as resp:  # noqa: S310
            text = resp.read().decode("utf-8", errors="replace")
        return _parse_sitemap_text(text)
    except Exception:
        return False, []


def discover_sitemaps(root: Path) -> list[Link]:
    """Walk *root* looking for sitemap files, extract all <loc> URLs.

    Handles sitemap index files by fetching each referenced child sitemap.
    Returns a list of :class:`~linkrot.scanner.Link` objects attributed to the
    sitemap file they were found in.  All links are marked external so they flow
    through the normal HTTP-checking path.
    """
    links: list[Link] = []

    # Walk the entire directory tree for any file named sitemap.xml or
    # sitemap_index.xml (case-insensitive on the filename).
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.name.lower() not in _SITEMAP_FILENAMES:
            continue

        is_index, urls = _parse_sitemap_file(path)

        if is_index:
            # Each URL in a sitemapindex points to another sitemap.
            # Fetch and expand each child sitemap.
            for child_url in urls:
                if not child_url.startswith(("http://", "https://")):
                    continue
                child_is_index, child_urls = _fetch_remote_sitemap(child_url)
                for page_url in child_urls:
                    if page_url.startswith(("http://", "https://")):
                        links.append(
                            Link(url=page_url, source_file=path, line_number=1)
                        )
                # Recursion into multi-level index is intentionally omitted to
                # avoid unbounded HTTP fetching; real-world sitemaps are ≤2 deep.
        else:
            for url in urls:
                if url.startswith(("http://", "https://")):
                    links.append(Link(url=url, source_file=path, line_number=1))

    return links
