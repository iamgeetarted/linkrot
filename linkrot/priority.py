"""Priority scoring for broken links — severity × impact."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .checker import CheckResult

# Severity weights by status prefix/exact match
_SEVERITY: dict[str, int] = {
    "missing": 10,
    "http-404": 9,
    "http-410": 9,
    "http-4xx": 7,  # fallback for other 4xx
    "http-5xx": 6,  # fallback for 5xx
    "timeout": 5,
    "anchor-missing": 3,
    "error": 4,
}


def _severity_weight(status: str) -> int:
    """Return the severity weight for a given status string."""
    if status in _SEVERITY:
        return _SEVERITY[status]
    if status.startswith("http-"):
        try:
            code = int(status[5:])
        except ValueError:
            return 4
        if 400 <= code < 500:
            return _SEVERITY["http-4xx"]
        if 500 <= code < 600:
            return _SEVERITY["http-5xx"]
    return 4  # default / error


def compute_priority(result: "CheckResult", impact: int) -> int:
    """Compute a priority score for a single broken link result.

    Args:
        result: A CheckResult for a broken link.
        impact: Number of unique source files that reference this URL.

    Returns:
        Integer priority score: severity_weight × max(1, impact).
    """
    weight = _severity_weight(result.status)
    return weight * max(1, impact)


def rank_broken_by_priority(
    results: "list[CheckResult]",
) -> "list[tuple[CheckResult, int]]":
    """Rank broken links by composite priority score.

    Counts how many unique source files reference each broken URL to use as the
    impact multiplier.  Returns a list of (result, score) tuples sorted
    highest-score-first.  Only one representative CheckResult is kept per URL.

    Args:
        results: All check results (ok and broken).

    Returns:
        List of (CheckResult, priority_score) pairs, sorted descending by score.
    """
    broken = [r for r in results if not r.ok]
    if not broken:
        return []

    # Count unique source files per broken URL
    url_files: dict[str, set[str]] = defaultdict(set)
    url_representative: dict[str, "CheckResult"] = {}

    for r in broken:
        url = r.link.url
        url_files[url].add(str(r.link.source_file))
        # Keep the first encountered result as representative
        if url not in url_representative:
            url_representative[url] = r

    scored: list[tuple["CheckResult", int]] = []
    for url, rep in url_representative.items():
        impact = len(url_files[url])
        score = compute_priority(rep, impact)
        scored.append((rep, score))

    scored.sort(key=lambda x: -x[1])
    return scored
