"""Command-line interface for linkrot."""

import sys
from pathlib import Path

import argparse

from . import __version__
from .scanner import scan_directory
from .checker import check_links
from .reporter import write_report
from .config import load_config
from .cache import clear_cache

try:
    from rich.progress import (
        Progress,
        SpinnerColumn,
        BarColumn,
        TaskProgressColumn,
        TextColumn,
    )
    from rich.console import Console
    _RICH = True
except ImportError:
    _RICH = False


def _build_parser(cfg: dict) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="linkrot",
        description="Find broken links in Markdown and HTML files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  linkrot .                        # scan current directory
  linkrot docs/ --no-external      # skip external URL checks
  linkrot . --format json          # output as JSON
  linkrot . --format csv -o out.csv
  linkrot . --format markdown      # output as Markdown document
  linkrot . --ignore 'localhost'   # ignore URLs matching pattern
  linkrot . --show-ok              # show passing links too
  linkrot . --timeout 5            # 5s timeout for HTTP requests
  linkrot . --format github        # GitHub Actions annotations
  linkrot . --retries 3            # retry 429/5xx up to 3 times
  linkrot . --show-redirects       # report URLs that changed destination
  linkrot . --watch 60             # re-check every 60s, show diff
""",
    )
    p.add_argument(
        "paths",
        nargs="*",
        default=["."],
        metavar="PATH",
        help="Directories to scan (default: current directory). Multiple paths are merged.",
    )
    p.add_argument(
        "--no-external",
        action="store_true",
        default=cfg.get("no_external", False),
        help="Skip external URL checks",
    )
    p.add_argument(
        "--format", "-f",
        choices=["table", "json", "csv", "markdown", "github", "sarif"],
        default=cfg.get("format", "table"),
        help="Output format (default: table)",
    )
    p.add_argument("--output", "-o", metavar="FILE", help="Write output to file instead of stdout")
    p.add_argument(
        "--ignore", "-i",
        action="append",
        metavar="PATTERN",
        default=list(cfg.get("ignore", [])),
        help="Ignore URLs matching regex pattern (can repeat)",
    )
    p.add_argument(
        "--timeout", "-t",
        type=float,
        default=cfg.get("timeout", 10.0),
        metavar="SECONDS",
        help="HTTP request timeout in seconds (default: 10)",
    )
    p.add_argument(
        "--workers", "-w",
        type=int,
        default=cfg.get("workers", 20),
        metavar="N",
        help="Max concurrent HTTP workers (default: 20)",
    )
    p.add_argument(
        "--show-ok",
        action="store_true",
        default=cfg.get("show_ok", False),
        help="Also show passing links in table output",
    )
    p.add_argument(
        "--cache-ttl",
        type=float,
        default=cfg.get("cache_ttl", 24.0),
        metavar="HOURS",
        help="Cache external results for this many hours (default: 24). Set 0 to disable.",
    )
    p.add_argument(
        "--no-cache",
        action="store_true",
        default=cfg.get("no_cache", False),
        help="Bypass the on-disk URL result cache",
    )
    p.add_argument(
        "--clear-cache",
        action="store_true",
        help="Delete all cached URL results and exit",
    )
    p.add_argument(
        "--suggest",
        action="store_true",
        default=cfg.get("suggest", False),
        help="After the report, stream AI suggestions for broken external links (requires ANTHROPIC_API_KEY)",
    )
    p.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=cfg.get("verbose", False),
        help="Print timing breakdown and cache statistics after the report",
    )
    p.add_argument(
        "--retries",
        type=int,
        default=cfg.get("retries", 2),
        metavar="N",
        help="Retry transient failures (429/5xx) up to N times (default: 2)",
    )
    p.add_argument(
        "--retry-backoff",
        type=float,
        default=cfg.get("retry_backoff", 1.0),
        metavar="SECONDS",
        help="Base backoff seconds between retries, doubles each attempt (default: 1.0)",
    )
    p.add_argument(
        "--show-redirects",
        action="store_true",
        default=cfg.get("show_redirects", False),
        help="Print a table of URLs that redirect to a different destination",
    )
    p.add_argument(
        "--watch",
        type=int,
        default=cfg.get("watch", 0),
        metavar="SECS",
        help="Re-run every SECS seconds and show diff of newly broken/fixed links (0 = disabled)",
    )
    p.add_argument(
        "--domain-summary",
        action="store_true",
        default=cfg.get("domain_summary", False),
        help="After the report, show a per-domain health breakdown table",
    )
    p.add_argument(
        "--log-file",
        metavar="FILE",
        default=cfg.get("log_file", None),
        help="Append each result as a JSON line to FILE (newline-delimited JSON / JSONL)",
    )
    p.add_argument(
        "--sitemap",
        action="store_true",
        default=cfg.get("sitemap", False),
        help="Discover sitemap.xml / sitemap_index.xml files and add their URLs to the check queue",
    )
    p.add_argument(
        "--save-baseline",
        metavar="FILE",
        default=None,
        help="Save broken URLs to FILE as a JSON baseline after checking",
    )
    p.add_argument(
        "--load-baseline",
        metavar="FILE",
        default=None,
        help="Load a baseline FILE; only report links that are new breakages not in the baseline",
    )
    p.add_argument("--version", action="version", version=f"linkrot {__version__}")
    return p


def _print_verbose_summary(
    console: "Console",
    scan_elapsed: float,
    check_elapsed: float,
    results: list,
    args: "argparse.Namespace",
) -> None:
    from rich.table import Table, box as rbox
    from rich.panel import Panel
    from collections import Counter

    status_counts: Counter = Counter(r.status for r in results)
    broken = [r for r in results if not r.ok]

    t = Table(box=rbox.SIMPLE, show_header=True, header_style="bold cyan", pad_edge=False)
    t.add_column("Metric", style="cyan")
    t.add_column("Value", justify="right", style="white")
    t.add_row("Scan time", f"{scan_elapsed:.2f}s")
    t.add_row("Check time", f"{check_elapsed:.2f}s")
    t.add_row("Total time", f"{scan_elapsed + check_elapsed:.2f}s")
    t.add_row("Links checked", str(len(results)))
    t.add_row("Broken", str(len(broken)))

    if status_counts:
        t.add_section()
        for status, count in sorted(status_counts.items(), key=lambda x: -x[1]):
            t.add_row(f"  {status}", str(count))

    console.print(Panel(t, title="[bold]Timing & Stats[/bold]", border_style="dim", box=rbox.ROUNDED))


def _print_redirects(console: "Console", results: list) -> None:
    """Print a Rich table of URLs that were redirected to a different destination."""
    from rich.table import Table, box as rbox

    redirects = [r for r in results if r.ok and r.final_url]
    if not redirects:
        console.print("[dim]No redirects detected.[/dim]")
        return

    t = Table(
        box=rbox.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        border_style="cyan",
        title="[bold]Redirect Report[/bold]",
    )
    t.add_column("File", style="cyan", no_wrap=True)
    t.add_column("Original URL", no_wrap=False)
    t.add_column("→ Final URL", style="yellow", no_wrap=False)

    for cr in sorted(redirects, key=lambda r: str(r.link.source_file)):
        try:
            rel = str(cr.link.source_file.relative_to(root))
        except ValueError:
            rel = str(cr.link.source_file)
        t.add_row(rel, cr.link.url, cr.final_url or "")

    console.print(t)
    console.print(f"[dim]{len(redirects)} redirect{'s' if len(redirects) != 1 else ''} found.[/dim]")


def _one_pass_rich(
    args: argparse.Namespace,
    roots: list[Path],
    console: "Console",
    prev_broken: set[str] | None = None,
) -> tuple[int, list, float, float]:
    """Run one scan+check pass and return (exit_code, results, scan_elapsed, check_elapsed)."""
    import time

    # Use first root as the display root; fall back to CWD for multi-root
    root = roots[0] if len(roots) == 1 else Path.cwd()

    t0 = time.perf_counter()
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Scanning files…", total=None)
        all_links = []
        files_scanned = 0
        for scan_root in roots:
            scan = scan_directory(scan_root)
            all_links.extend(scan.links)
            files_scanned += scan.files_scanned

        # Deduplicate external URLs across roots to avoid double-checking
        seen_external: set[str] = set()
        deduped_links = []
        for link in all_links:
            if link.is_external:
                if link.url in seen_external:
                    continue
                seen_external.add(link.url)
            deduped_links.append(link)

        # Reuse the scan container shape but with merged links
        from .scanner import ScanResult
        scan = ScanResult(links=deduped_links, files_scanned=files_scanned)
        progress.remove_task(task)
    scan_elapsed = time.perf_counter() - t0

    if args.sitemap:
        from .sitemap import discover_sitemaps
        sitemap_links = []
        for scan_root in roots:
            sitemap_links.extend(discover_sitemaps(scan_root))
        if sitemap_links:
            scan.links.extend(sitemap_links)
            console.print(
                f"[dim]Sitemap: added {len(sitemap_links)} URL(s) from sitemap files.[/dim]",
                highlight=False,
            )

    console.print(
        f"Found [bold]{len(scan.links)}[/bold] links in"
        f" [bold]{scan.files_scanned}[/bold] files.",
        highlight=False,
    )

    if not scan.links:
        console.print("No links found.")
        return 0, [], scan_elapsed, 0.0

    total = len(scan.links)

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TextColumn("[dim]{task.completed}/{task.total}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Checking links…", total=total)

        def _cb(done: int, tot: int) -> None:
            progress.update(task, completed=done)

        t1 = time.perf_counter()
        results = check_links(
            scan.links,
            root=root,
            check_external=not args.no_external,
            timeout=args.timeout,
            max_workers=args.workers,
            ignore_patterns=args.ignore,
            progress_cb=_cb,
            cache_ttl=args.cache_ttl if args.cache_ttl > 0 else None,
            no_cache=args.no_cache,
            retries=args.retries,
            retry_backoff=args.retry_backoff,
        )
        check_elapsed = time.perf_counter() - t1

    # Baseline: load, filter, and summarise
    baseline_urls: set[str] = set()
    if args.load_baseline:
        from .baseline import load_baseline
        from pathlib import Path as _Path
        baseline_urls = load_baseline(_Path(args.load_baseline))
        if baseline_urls:
            new_results = [r for r in results if r.ok or r.link.url not in baseline_urls]
            suppressed = len(results) - len(new_results)
            new_broken = sum(1 for r in new_results if not r.ok)
            console.print(
                f"[dim]Baseline: [bold]{new_broken}[/bold] new breakage(s),"
                f" [bold]{suppressed}[/bold] known from baseline (suppressed).[/dim]",
                highlight=False,
            )
            results = new_results

    exit_code = write_report(
        results,
        root=root,
        fmt=args.format,
        show_ok=args.show_ok,
        output_file=args.output,
    )

    if args.save_baseline:
        from .baseline import save_baseline
        from pathlib import Path as _Path
        save_baseline(_Path(args.save_baseline), results)
        console.print(
            f"[dim]Baseline saved to {args.save_baseline}[/dim]",
            highlight=False,
        )

    if args.show_redirects:
        console.print()
        _print_redirects(console, results)

    if prev_broken is not None:
        _print_watch_diff(console, results, prev_broken)

    if args.domain_summary:
        from .reporter import report_domain_summary
        console.print()
        report_domain_summary(results, console=console)

    if args.log_file:
        from .audit import write_audit_log
        n = write_audit_log(results, Path(args.log_file), root)
        console.print(
            f"[dim]Audit log: {n} record{'s' if n != 1 else ''} appended to {args.log_file}[/dim]",
            highlight=False,
        )

    if args.suggest:
        from .suggest import suggest_fixes
        suggest_fixes(results)

    if args.verbose:
        _print_verbose_summary(console, scan_elapsed, check_elapsed, results, args)

    return exit_code, results, scan_elapsed, check_elapsed


def _print_watch_diff(console: "Console", results: list, prev_broken: set[str]) -> None:
    """Highlight newly broken and newly fixed links compared to previous run."""
    from rich.rule import Rule

    curr_broken = {r.link.url for r in results if not r.ok}
    newly_broken = curr_broken - prev_broken
    newly_fixed = prev_broken - curr_broken

    if not newly_broken and not newly_fixed:
        console.print("[dim]  ↻ No changes since last run.[/dim]")
        return

    console.print()
    console.print(Rule("[bold]Watch Diff[/bold]", style="cyan"))
    for url in sorted(newly_broken):
        console.print(f"  [bold red]✗ NEW BROKEN:[/bold red] {url}")
    for url in sorted(newly_fixed):
        console.print(f"  [bold green]✓ NOW FIXED:[/bold green]  {url}")


def _run_with_rich(args: argparse.Namespace, roots: list[Path]) -> int:
    import time
    console = Console(stderr=True)

    if len(roots) > 1:
        console.print(
            f"[dim]Scanning {len(roots)} paths: {', '.join(str(r) for r in roots)}[/dim]",
            highlight=False,
        )

    if args.watch:
        prev_broken: set[str] | None = None
        iteration = 0
        while True:
            if iteration > 0:
                console.clear()
            exit_code, results, _, _ = _one_pass_rich(args, roots, console, prev_broken)
            prev_broken = {r.link.url for r in results if not r.ok}
            console.print(
                f"[dim]  ↻ watch mode — refreshing in {args.watch}s (Ctrl-C to stop)[/dim]"
            )
            try:
                time.sleep(args.watch)
            except KeyboardInterrupt:
                break
            iteration += 1
        return 0

    exit_code, _, _, _ = _one_pass_rich(args, roots, console, prev_broken=None)
    return exit_code


def _run_plain(args: argparse.Namespace, roots: list[Path]) -> int:
    import threading
    import time

    is_tty = sys.stdout.isatty()

    def _spinner(stop_event: threading.Event, message: str) -> None:
        frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        i = 0
        while not stop_event.is_set():
            print(f"\r{frames[i % len(frames)]} {message}", end="", flush=True)
            i += 1
            time.sleep(0.1)
        print("\r" + " " * (len(message) + 4) + "\r", end="", flush=True)

    root = roots[0] if len(roots) == 1 else Path.cwd()

    if is_tty:
        stop = threading.Event()
        t = threading.Thread(target=_spinner, args=(stop, "Scanning files…"), daemon=True)
        t.start()

    t0 = time.perf_counter()
    all_links = []
    files_scanned = 0
    for scan_root in roots:
        s = scan_directory(scan_root)
        all_links.extend(s.links)
        files_scanned += s.files_scanned

    seen_external: set[str] = set()
    deduped = []
    for link in all_links:
        if link.is_external:
            if link.url in seen_external:
                continue
            seen_external.add(link.url)
        deduped.append(link)

    from .scanner import ScanResult
    scan = ScanResult(links=deduped, files_scanned=files_scanned)
    scan_elapsed = time.perf_counter() - t0

    if is_tty:
        stop.set()
        t.join()

    if args.sitemap:
        from .sitemap import discover_sitemaps
        sitemap_links = []
        for scan_root in roots:
            sitemap_links.extend(discover_sitemaps(scan_root))
        if sitemap_links:
            scan.links.extend(sitemap_links)
            if is_tty:
                print(f"Sitemap: added {len(sitemap_links)} URL(s) from sitemap files.")

    if is_tty:
        print(f"Found {len(scan.links)} links in {scan.files_scanned} files.")

    if not scan.links:
        print("No links found.")
        return 0

    def _progress_cb(done: int, tot: int) -> None:
        if is_tty:
            print(f"\r  Checking {done}/{tot}…", end="", flush=True)

    t1 = time.perf_counter()
    results = check_links(
        scan.links,
        root=root,
        check_external=not args.no_external,
        timeout=args.timeout,
        max_workers=args.workers,
        ignore_patterns=args.ignore,
        progress_cb=_progress_cb if is_tty else None,
        cache_ttl=args.cache_ttl if args.cache_ttl > 0 else None,
        no_cache=args.no_cache,
        retries=args.retries,
        retry_backoff=args.retry_backoff,
    )
    check_elapsed = time.perf_counter() - t1

    if is_tty:
        print("\r" + " " * 40 + "\r", end="", flush=True)

    # Baseline: load, filter, and summarise
    if args.load_baseline:
        from .baseline import load_baseline
        baseline_urls = load_baseline(Path(args.load_baseline))
        if baseline_urls:
            new_results = [r for r in results if r.ok or r.link.url not in baseline_urls]
            suppressed = len(results) - len(new_results)
            new_broken = sum(1 for r in new_results if not r.ok)
            print(
                f"Baseline: {new_broken} new breakage(s),"
                f" {suppressed} known from baseline (suppressed)."
            )
            results = new_results

    exit_code = write_report(
        results,
        root=root,
        fmt=args.format,
        show_ok=args.show_ok,
        output_file=args.output,
    )

    if args.save_baseline:
        from .baseline import save_baseline
        save_baseline(Path(args.save_baseline), results)
        if is_tty:
            print(f"Baseline saved to {args.save_baseline}")

    if args.domain_summary:
        from .reporter import report_domain_summary
        report_domain_summary(results, console=None)

    if args.log_file:
        from .audit import write_audit_log
        n = write_audit_log(results, Path(args.log_file), root)
        if is_tty:
            print(f"Audit log: {n} record{'s' if n != 1 else ''} appended to {args.log_file}")

    if args.suggest:
        from .suggest import suggest_fixes
        suggest_fixes(results)

    if args.verbose:
        from collections import Counter
        status_counts = Counter(r.status for r in results)
        broken_count = sum(1 for r in results if not r.ok)
        print(f"\n[Timing] scan={scan_elapsed:.2f}s  check={check_elapsed:.2f}s  total={scan_elapsed+check_elapsed:.2f}s")
        print(f"[Stats]  checked={len(results)}  broken={broken_count}")
        for status, count in sorted(status_counts.items(), key=lambda x: -x[1]):
            print(f"         {status}: {count}")

    return exit_code


def main(argv: list[str] | None = None) -> int:
    try:
        cfg = load_config()
    except ValueError as e:
        print(f"linkrot: config error: {e}", file=sys.stderr)
        return 2

    parser = _build_parser(cfg)
    args = parser.parse_args(argv)

    if args.clear_cache:
        n = clear_cache()
        print(f"linkrot: cleared {n} cached result{'s' if n != 1 else ''}.")
        return 0

    roots: list[Path] = []
    for raw in (args.paths or ["."]):
        p = Path(raw).resolve()
        if not p.exists():
            print(f"linkrot: path not found: {p}", file=sys.stderr)
            return 2
        if not p.is_dir():
            print(f"linkrot: not a directory: {p}", file=sys.stderr)
            return 2
        roots.append(p)

    if not roots:
        roots = [Path(".").resolve()]

    if _RICH and sys.stderr.isatty():
        return _run_with_rich(args, roots)
    return _run_plain(args, roots)


def entry_point() -> None:
    sys.exit(main())
