"""Check links for validity — internal file links and external URLs."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import httpx

from .cache import CachedResult, get_cached, set_cached
from .scanner import Link


@dataclass
class CheckResult:
    link: Link
    ok: bool
    status: str  # "ok", "missing", "anchor-missing", "error", "timeout", "http-NNN"
    detail: str = ""
    final_url: str | None = None  # redirect destination if URL was redirected


# ---------------------------------------------------------------------------
# Internal link resolution
# ---------------------------------------------------------------------------

def _resolve_internal(link: Link, root: Path) -> CheckResult:
    """Check whether an internal link target exists on disk."""
    url = link.url
    source_dir = link.source_file.parent

    if url.startswith("/"):
        target = root / url.lstrip("/")
    else:
        target = (source_dir / url).resolve()

    if target.exists():
        if link.anchor:
            ok, detail = _check_anchor(target, link.anchor)
            if ok:
                return CheckResult(link, True, "ok")
            return CheckResult(link, False, "anchor-missing", detail)
        return CheckResult(link, True, "ok")

    for suffix in [".md", ".html", ".htm", ""]:
        candidate = target.with_suffix(suffix) if suffix else target / "index.html"
        if candidate.exists():
            return CheckResult(link, True, "ok")

    return CheckResult(
        link,
        False,
        "missing",
        f"File not found: {target.relative_to(root) if target.is_relative_to(root) else target}",
    )


def _check_anchor(path: Path, anchor: str) -> tuple[bool, str]:
    """Look for an anchor/heading in a file."""
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False, "Could not read file"

    def heading_to_anchor(text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"\s+", "-", text)
        return text

    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown"}:
        for line in content.splitlines():
            m = re.match(r"^#{1,6}\s+(.*)", line)
            if m and heading_to_anchor(m.group(1)) == anchor.lower():
                return True, ""
        if re.search(rf'id=["\']?{re.escape(anchor)}["\']?', content, re.IGNORECASE):
            return True, ""
    elif suffix in {".html", ".htm"}:
        if re.search(rf'id=["\']?{re.escape(anchor)}["\']?', content, re.IGNORECASE):
            return True, ""
        if re.search(rf'name=["\']?{re.escape(anchor)}["\']?', content, re.IGNORECASE):
            return True, ""

    return False, f"Anchor '#{anchor}' not found in {path.name}"


# ---------------------------------------------------------------------------
# Async external checking with httpx
# ---------------------------------------------------------------------------

_UA = "linkrot/1.5 (https://github.com/iamgeetarted/linkrot)"

# HTTP status codes worth retrying
_RETRY_STATUSES = {429, 500, 502, 503, 504}


async def _check_one_url(
    url: str,
    client: httpx.AsyncClient,
    timeout: float,
    retries: int = 2,
    retry_backoff: float = 1.0,
) -> tuple[bool, str, str, str | None]:
    """Return (ok, status, detail, final_url) for a single URL.

    final_url is the redirect destination when it differs from url, else None.
    """
    if url.startswith("//"):
        url = "https:" + url

    attempt = 0
    while True:
        try:
            resp = await client.head(url, follow_redirects=True)
            code = resp.status_code
            if code == 405:
                resp = await client.get(url, follow_redirects=True)
                code = resp.status_code

            # Detect redirect destination
            final = str(resp.url) if str(resp.url) != url else None

            if code in _RETRY_STATUSES and attempt < retries:
                wait = retry_backoff * (2 ** attempt)
                await asyncio.sleep(wait)
                attempt += 1
                continue

            if code < 400:
                return True, "ok", f"HTTP {code}", final
            return False, f"http-{code}", f"HTTP {code}", final

        except httpx.TimeoutException:
            if attempt < retries:
                wait = retry_backoff * (2 ** attempt)
                await asyncio.sleep(wait)
                attempt += 1
                continue
            return False, "timeout", f"Timed out after {timeout}s", None
        except Exception as exc:
            msg = str(exc)[:120]
            if attempt < retries and ("connection" in msg.lower() or "network" in msg.lower()):
                wait = retry_backoff * (2 ** attempt)
                await asyncio.sleep(wait)
                attempt += 1
                continue
            if "timed out" in msg.lower():
                return False, "timeout", msg, None
            return False, "error", msg, None


async def _fetch_all_external(
    links: list[Link],
    timeout: float,
    max_workers: int,
    cache_ttl: float | None,
    progress_cb: Callable[[int, int], None] | None,
    start_done: int,
    total: int,
    retries: int = 2,
    retry_backoff: float = 1.0,
) -> list[CheckResult]:
    semaphore = asyncio.Semaphore(max_workers)
    counter = [start_done]
    lock = asyncio.Lock()

    async with httpx.AsyncClient(
        headers={"User-Agent": _UA, "Accept": "*/*"},
        timeout=httpx.Timeout(timeout, connect=min(timeout, 10.0)),
        follow_redirects=True,
    ) as client:

        async def _do(link: Link) -> CheckResult:
            # Cache lookup (no semaphore needed — just a disk read)
            if cache_ttl is not None:
                cached: CachedResult | None = get_cached(link.url, cache_ttl)
                if cached is not None:
                    async with lock:
                        counter[0] += 1
                        if progress_cb:
                            progress_cb(counter[0], total)
                    return CheckResult(link, cached.ok, cached.status, cached.detail)

            async with semaphore:
                ok, status, detail, final_url = await _check_one_url(
                    link.url, client, timeout,
                    retries=retries, retry_backoff=retry_backoff,
                )

            if cache_ttl is not None:
                set_cached(link.url, ok, status, detail)

            async with lock:
                counter[0] += 1
                if progress_cb:
                    progress_cb(counter[0], total)

            return CheckResult(link, ok, status, detail, final_url=final_url)

        return list(await asyncio.gather(*(_do(link) for link in links)))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check_links(
    links: list[Link],
    root: Path,
    check_external: bool = True,
    timeout: float = 10.0,
    max_workers: int = 20,
    ignore_patterns: list[str] | None = None,
    progress_cb: Callable[[int, int], None] | None = None,
    cache_ttl: float | None = 24.0,
    no_cache: bool = False,
    retries: int = 2,
    retry_backoff: float = 1.0,
) -> list[CheckResult]:
    """Check all links; returns a list of CheckResult."""
    ignore_res = [re.compile(p) for p in (ignore_patterns or [])]
    effective_ttl = None if no_cache else cache_ttl

    def is_ignored(url: str) -> bool:
        return any(r.search(url) for r in ignore_res)

    internal = [lk for lk in links if not lk.is_external and not is_ignored(lk.url)]
    external = (
        [lk for lk in links if lk.is_external and not is_ignored(lk.url)]
        if check_external
        else []
    )

    results: list[CheckResult] = []
    total = len(internal) + len(external)
    done = 0

    for lk in internal:
        results.append(_resolve_internal(lk, root))
        done += 1
        if progress_cb:
            progress_cb(done, total)

    # Deduplicate external URLs — same URL may appear in many files
    seen: dict[str, CheckResult] = {}
    unique: list[Link] = []
    for lk in external:
        if lk.url not in seen:
            unique.append(lk)

    if unique:
        ext_results = asyncio.run(
            _fetch_all_external(
                unique,
                timeout=timeout,
                max_workers=max_workers,
                cache_ttl=effective_ttl,
                progress_cb=progress_cb,
                start_done=done,
                total=total,
                retries=retries,
                retry_backoff=retry_backoff,
            )
        )
        for cr in ext_results:
            seen[cr.link.url] = cr

        for lk in external:
            cached_cr = seen.get(lk.url)
            if cached_cr:
                results.append(CheckResult(lk, cached_cr.ok, cached_cr.status, cached_cr.detail))

    return results
