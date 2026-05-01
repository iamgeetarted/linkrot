"""Command-line interface for linkrot."""

import sys
import threading
import time
from pathlib import Path

import argparse

from . import __version__
from .scanner import scan_directory
from .checker import check_links
from .reporter import write_report


def _build_parser() -> argparse.ArgumentParser:
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
  linkrot . --ignore 'localhost'   # ignore URLs matching pattern
  linkrot . --show-ok              # show passing links too
  linkrot . --timeout 5            # 5s timeout for HTTP requests
""",
    )
    p.add_argument("path", nargs="?", default=".", help="Directory to scan (default: .)")
    p.add_argument("--no-external", action="store_true", help="Skip external URL checks")
    p.add_argument(
        "--format", "-f", choices=["table", "json", "csv"], default="table",
        help="Output format (default: table)",
    )
    p.add_argument("--output", "-o", metavar="FILE", help="Write output to file instead of stdout")
    p.add_argument(
        "--ignore", "-i", action="append", metavar="PATTERN", default=[],
        help="Ignore URLs matching regex pattern (can repeat)",
    )
    p.add_argument(
        "--timeout", "-t", type=float, default=10.0, metavar="SECONDS",
        help="HTTP request timeout in seconds (default: 10)",
    )
    p.add_argument(
        "--workers", "-w", type=int, default=20, metavar="N",
        help="Max concurrent HTTP workers (default: 20)",
    )
    p.add_argument("--show-ok", action="store_true", help="Also show passing links in table output")
    p.add_argument("--version", action="version", version=f"linkrot {__version__}")
    return p


def _spinner(stop_event: threading.Event, message: str) -> None:
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    i = 0
    while not stop_event.is_set():
        print(f"\r{frames[i % len(frames)]} {message}", end="", flush=True)
        i += 1
        time.sleep(0.1)
    print("\r" + " " * (len(message) + 4) + "\r", end="", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    root = Path(args.path).resolve()
    if not root.exists():
        print(f"linkrot: path not found: {root}", file=sys.stderr)
        return 2
    if not root.is_dir():
        print(f"linkrot: not a directory: {root}", file=sys.stderr)
        return 2

    is_tty = sys.stdout.isatty()

    # Scan phase
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

    # Check phase
    counter = {"done": 0}
    total = len(scan.links)

    def progress(done: int, tot: int) -> None:
        counter["done"] = done
        if is_tty:
            print(f"\r  Checking {done}/{tot}…", end="", flush=True)

    if is_tty:
        stop2 = threading.Event()

    results = check_links(
        scan.links,
        root=root,
        check_external=not args.no_external,
        timeout=args.timeout,
        max_workers=args.workers,
        ignore_patterns=args.ignore,
        progress_cb=progress if is_tty else None,
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


def entry_point() -> None:
    sys.exit(main())
