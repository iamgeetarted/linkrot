"""Command-line interface for linkrot."""

import sys
from pathlib import Path

import argparse

from . import __version__
from .scanner import scan_directory
from .checker import check_links
from .reporter import write_report
from .config import load_config

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
""",
    )
    p.add_argument("path", nargs="?", default=".", help="Directory to scan (default: .)")
    p.add_argument(
        "--no-external",
        action="store_true",
        default=cfg.get("no_external", False),
        help="Skip external URL checks",
    )
    p.add_argument(
        "--format", "-f",
        choices=["table", "json", "csv", "markdown"],
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
    p.add_argument("--version", action="version", version=f"linkrot {__version__}")
    return p


def _run_with_rich(args: argparse.Namespace, root: Path) -> int:
    console = Console(stderr=True)

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Scanning files…", total=None)
        scan = scan_directory(root)
        progress.remove_task(task)

    console.print(
        f"Found [bold]{len(scan.links)}[/bold] links in"
        f" [bold]{scan.files_scanned}[/bold] files.",
        highlight=False,
    )

    if not scan.links:
        console.print("No links found.")
        return 0

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

        results = check_links(
            scan.links,
            root=root,
            check_external=not args.no_external,
            timeout=args.timeout,
            max_workers=args.workers,
            ignore_patterns=args.ignore,
            progress_cb=_cb,
        )

    return write_report(
        results,
        root=root,
        fmt=args.format,
        show_ok=args.show_ok,
        output_file=args.output,
    )


def _run_plain(args: argparse.Namespace, root: Path) -> int:
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

    if is_tty:
        stop = threading.Event()
        t = threading.Thread(target=_spinner, args=(stop, "Scanning files…"), daemon=True)
        t.start()

    scan = scan_directory(root)

    if is_tty:
        stop.set()
        t.join()
        print(f"Found {len(scan.links)} links in {scan.files_scanned} files.")

    if not scan.links:
        print("No links found.")
        return 0

    def _progress_cb(done: int, tot: int) -> None:
        if is_tty:
            print(f"\r  Checking {done}/{tot}…", end="", flush=True)

    results = check_links(
        scan.links,
        root=root,
        check_external=not args.no_external,
        timeout=args.timeout,
        max_workers=args.workers,
        ignore_patterns=args.ignore,
        progress_cb=_progress_cb if is_tty else None,
    )

    if is_tty:
        print("\r" + " " * 40 + "\r", end="", flush=True)

    return write_report(
        results,
        root=root,
        fmt=args.format,
        show_ok=args.show_ok,
        output_file=args.output,
    )


def main(argv: list[str] | None = None) -> int:
    try:
        cfg = load_config()
    except ValueError as e:
        print(f"linkrot: config error: {e}", file=sys.stderr)
        return 2

    parser = _build_parser(cfg)
    args = parser.parse_args(argv)

    root = Path(args.path).resolve()
    if not root.exists():
        print(f"linkrot: path not found: {root}", file=sys.stderr)
        return 2
    if not root.is_dir():
        print(f"linkrot: not a directory: {root}", file=sys.stderr)
        return 2

    if _RICH and sys.stderr.isatty():
        return _run_with_rich(args, root)
    return _run_plain(args, root)


def entry_point() -> None:
    sys.exit(main())
