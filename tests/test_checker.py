"""Tests for the link checker."""

import tempfile
from pathlib import Path

from linkrot.scanner import Link
from linkrot.checker import check_links


def _make_link(url: str, source: Path, line: int = 1) -> Link:
    return Link(url=url, source_file=source, line_number=line)


def test_internal_existing_file():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        src = root / "doc.md"
        target = root / "other.md"
        src.write_text("hello")
        target.write_text("world")
        link = _make_link("other.md", src)
        results = check_links([link], root=root, check_external=False)
        assert len(results) == 1
        assert results[0].ok is True
        assert results[0].status == "ok"


def test_internal_missing_file():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        src = root / "doc.md"
        src.write_text("hello")
        link = _make_link("nonexistent.md", src)
        results = check_links([link], root=root, check_external=False)
        assert len(results) == 1
        assert results[0].ok is False
        assert results[0].status == "missing"


def test_anchor_found():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        src = root / "doc.md"
        target = root / "guide.md"
        src.write_text("see [guide](guide.md#installation)")
        target.write_text("## Installation\n\nSteps here.")
        link = _make_link("guide.md", src)
        link.anchor = "installation"
        results = check_links([link], root=root, check_external=False)
        assert results[0].ok is True


def test_anchor_missing():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        src = root / "doc.md"
        target = root / "guide.md"
        src.write_text("text")
        target.write_text("## Setup\n\nSteps here.")
        link = _make_link("guide.md", src)
        link.anchor = "installation"
        results = check_links([link], root=root, check_external=False)
        assert results[0].ok is False
        assert results[0].status == "anchor-missing"


def test_ignore_pattern():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        src = root / "doc.md"
        src.write_text("text")
        link = _make_link("https://internal.corp.example.com/page", src)
        # Without ignore pattern — would try HTTP (but we skip external here)
        results = check_links([link], root=root, check_external=False, ignore_patterns=["internal\\.corp"])
        # Link is external and external is disabled AND it's ignored — should be absent
        assert len(results) == 0
