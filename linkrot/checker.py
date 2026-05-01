"""Check links for validity — internal file links and external URLs."""

import re
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .scanner import Link


@dataclass
class CheckResult:
    link: Link
    ok: bool
    status: str  # "ok", "missing", "anchor-missing", "error", "timeout", "http-NNN"
    detail: str = ""


def _resolve_internal(link: Link, root: Path) -> CheckResult:
    """Check whether an internal link target exists on disk."""
    url = link.url
    source_dir = link.source_file.parent

    if url.startswith("/"):
        target = root / url.lstrip("/")
    else:
        target = (source_dir / url).resolve()

    # Try exact path first
    if target.exists():
        if link.anchor:
            ok, detail = _check_anchor(target, link.anchor)
            if ok:
                return CheckResult(link, True, "ok")
            return CheckResult(link, False, "anchor-missing", detail)
        return CheckResult(link, True, "ok")

    # Try with common index file suffixes
    for suffix in [".md", ".html", ".htm", ""]:
        candidate = target.with_suffix(suffix) if suffix else target / "index.html"
        if candidate.exists():
            return CheckResult(link, True, "ok")

    return CheckResult(
        link, False, "missing", f"File not found: {target.relative_to(root) if target.is_relative_to(root) else target}"
    )


def _check_anchor(path: Path, anchor: str) -> tuple[bool, str]:
    """Look for an anchor/heading in a file."""
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False, "Could not read file"

    # Convert anchor to heading text (GitHub style: lowercase, spaces→hyphens, strip punctuation)
    def heading_to_anchor(text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'\s+', '-', text)
        return text

    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown"}:
        for line in content.splitlines():
            m = re.match(r'^#{1,6}\s+(.*)', line)
            if m:
                if heading_to_anchor(m.group(1)) == anchor.lower():
                    return True, ""
        # Also look for explicit HTML anchors embedded in markdown
        if re.search(rf'id=["\']?{re.escape(anchor)}["\']?', content, re.IGNORECASE):
            return True, ""
    elif suffix in {".html", ".htm"}:
        if re.search(rf'id=["\']?{re.escape(anchor)}["\']?', content, re.IGNORECASE):
            return True, ""
        if re.search(rf'name=["\']?{re.escape(anchor)}["\']?', content, re.IGNORECASE):
            return True, ""

    return False, f"Anchor '#{anchor}' not found in {path.name}"


def _check_external(link: Link, timeout: float, user_agent: str) -> CheckResult:
    """Perform an HTTP HEAD (fallback GET) request to validate a URL."""
    url = link.url
    # Normalize scheme-relative URLs
    if url.startswith("//"):
        url = "https:" + url

    req = urllib.request.Request(url, method="HEAD")
    req.add_header("User-Agent", user_agent)
    req.add_header("Accept", "*/*")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = resp.status
            if code < 400:
                return CheckResult(link, True, "ok", f"HTTP {code}")
            return CheckResult(link, False, f"http-{code}", f"HTTP {code}")
    except urllib.error.HTTPError as e:
        if e.code == 405:
            # HEAD not allowed — try GET
            req2 = urllib.request.Request(url, method="GET")
            req2.add_header("User-Agent", user_agent)
            try:
                with urllib.request.urlopen(req2, timeout=timeout) as resp:
                    code = resp.status
                    if code < 400:
                        return CheckResult(link, True, "ok", f"HTTP {code}")
                    return CheckResult(link, False, f"http-{code}", f"HTTP {code}")
            except Exception as e2:
                return CheckResult(link, False, "error", str(e2)[:120])
        return CheckResult(link, False, f"http-{e.code}", f"HTTP {e.code}: {e.reason}")
    except TimeoutError:
        return CheckResult(link, False, "timeout", f"Timed out after {timeout}s")
    except OSError as e:
        msg = str(e)
        if "timed out" in msg.lower():
            return CheckResult(link, False, "timeout", msg[:120])
        return CheckResult(link, False, "error", msg[:120])
    except Exception as e:
        return CheckResult(link, False, "error", str(e)[:120])


def check_links(
    links: list[Link],
    root: Path,
    check_external: bool = True,
    timeout: float = 10.0,
    max_workers: int = 20,
    ignore_patterns: list[str] | None = None,
    progress_cb: Callable[[int, int], None] | None = None,
) -> list[CheckResult]:
    user_agent = "linkrot/1.0 (https://github.com/iamgeetarted/linkrot)"
    ignore_res = [re.compile(p) for p in (ignore_patterns or [])]

    def is_ignored(url: str) -> bool:
        return any(r.search(url) for r in ignore_res)

    internal = [l for l in links if not l.is_external and not is_ignored(l.url)]
    external = [l for l in links if l.is_external and not is_ignored(l.url)] if check_external else []

    results: list[CheckResult] = []
    total = len(internal) + len(external)
    done = 0

    # Internal links — fast, sequential (usually just stat calls)
    for link in internal:
        results.append(_resolve_internal(link, root))
        done += 1
        if progress_cb:
            progress_cb(done, total)

    # Deduplicate external URLs (same URL may appear many times)
    seen_external: dict[str, CheckResult] = {}
    unique_external: list[Link] = []
    for link in external:
        if link.url not in seen_external:
            unique_external.append(link)

    if unique_external:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(_check_external, link, timeout, user_agent): link
                for link in unique_external
            }
            for future in as_completed(futures):
                cr = future.result()
                seen_external[cr.link.url] = cr
                done += 1
                if progress_cb:
                    progress_cb(done, total)

        # Map results back to all occurrences
        for link in external:
            cached = seen_external.get(link.url)
            if cached:
                results.append(CheckResult(link, cached.ok, cached.status, cached.detail))

    return results
