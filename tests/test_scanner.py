"""Tests for the link scanner."""

import tempfile
from pathlib import Path

import pytest

from linkrot.scanner import scan_directory, Link


def _write(tmp: Path, name: str, content: str) -> Path:
    p = tmp / name
    p.write_text(content, encoding="utf-8")
    return p


def test_scan_empty_dir():
    with tempfile.TemporaryDirectory() as d:
        result = scan_directory(Path(d))
        assert result.files_scanned == 0
        assert result.links == []


def test_scan_markdown_inline_links():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        _write(tmp, "doc.md", "See [home](index.md) and [site](https://example.com).\n")
        result = scan_directory(tmp)
        assert result.files_scanned == 1
        urls = {l.url for l in result.links}
        assert "index.md" in urls
        assert "https://example.com" in urls


def test_scan_skips_mailto():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        _write(tmp, "a.md", "[email](mailto:foo@bar.com) [ok](page.md)\n")
        result = scan_directory(tmp)
        urls = {l.url for l in result.links}
        assert "mailto:foo@bar.com" not in urls
        assert "page.md" in urls


def test_scan_skips_ignored_dirs():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        (tmp / "node_modules").mkdir()
        _write(tmp / "node_modules", "pkg.md", "[x](missing.md)\n")
        _write(tmp, "real.md", "[ok](exists.md)\n")
        result = scan_directory(tmp)
        assert result.files_scanned == 1


def test_scan_html_links():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        _write(tmp, "index.html", '<a href="page.html">link</a>\n<img src="img.png">\n')
        result = scan_directory(tmp)
        assert result.files_scanned == 1
        urls = {l.url for l in result.links}
        assert "page.html" in urls
        assert "img.png" in urls


def test_link_is_external():
    link = Link(url="https://example.com/page", source_file=Path("doc.md"), line_number=1)
    assert link.is_external is True


def test_link_is_internal():
    link = Link(url="./other.md", source_file=Path("doc.md"), line_number=1)
    assert link.is_external is False


def test_anchor_split():
    link = Link(url="page.md#section", source_file=Path("doc.md"), line_number=1)
    assert link.url == "page.md"
    assert link.anchor == "section"
    assert link.is_external is False
