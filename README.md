# linkrot

**Find broken links in Markdown and HTML files — fast.**

`linkrot` scans a directory tree for `.md` and `.html` files, extracts every link, and tells you which ones are dead. It checks:

- **Internal links** — file existence and heading anchors (`#section`)
- **External URLs** — fully async HTTP/2 requests with deduplication and on-disk caching

---

## What's New in v1.3.0

### 1. Full async upgrade with httpx

External URL checking now uses `asyncio` + `httpx.AsyncClient` instead of `ThreadPoolExecutor` + `urllib`. This brings proper HTTP/2 support, better connection pooling, and cleaner concurrency via `asyncio.Semaphore` — all without changing the CLI interface.

```bash
# Same command, now backed by an async engine
linkrot docs/ --workers 40
```

### 2. On-disk URL result cache (`~/.cache/linkrot/`)

External URL checks are cached to `~/.cache/linkrot/` (MD5-keyed JSON files) with a configurable TTL. Re-running on the same docs skips already-verified URLs, making repeated runs near-instant.

```bash
linkrot .                       # caches results for 24 h (default)
linkrot . --cache-ttl 48        # keep cache valid for 48 hours
linkrot . --cache-ttl 0         # TTL=0 effectively disables caching logic
linkrot . --no-cache            # bypass cache entirely, re-check everything
linkrot --clear-cache           # wipe all cached results
```

Config file support (`.linkrot.toml`):

```toml
cache_ttl  = 12.0   # hours
no_cache   = false
```

### 3. AI fix suggestions (`--suggest`)

After the broken-link report, stream Claude Haiku suggestions for each dead external URL — probable reason it broke, likely replacement, and whether the Wayback Machine has a snapshot.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
linkrot docs/ --suggest
```

```
── AI Suggestions for Broken Links ──────────────────────────────────────────
1. https://old.example.com/guide  [http-404]
   → Likely moved to https://example.com/docs/guide (domain restructure).
     Wayback Machine snapshot probable.
2. https://deprecated-api.io/v1  [error]
   → Domain no longer resolves; service appears shut down.
     Search for successor at https://github.com/search?q=deprecated-api
```

Requires `ANTHROPIC_API_KEY` in your environment. Suggestions are streamed token-by-token as they arrive.

---

## What's New in v1.2.0

### 1. Rich terminal UI

When [`rich`](https://github.com/Textualize/rich) is installed, linkrot automatically uses a live progress bar with a spinner and completion counter during scanning and checking, and renders results in a polished ROUNDED-box table with cyan headers and colour-coded status cells.

```bash
pip install "linkrot[rich]"   # or: pip install linkrot rich
linkrot .
```

No code changes required — the UI upgrades automatically when `rich` is available and stdout is a TTY. Falls back to the plain ANSI output when running in CI or piped output.

### 2. `--format markdown` output

Generate a self-contained Markdown report with per-file headings, status icons (✅ / ❌ / ⚠️), and a summary table — perfect for saving alongside your docs or posting in a GitHub issue.

```bash
linkrot . --format markdown
linkrot . --format markdown -o link-report.md
```

Example output:

```markdown
# Link Check Report

## Summary

| Metric | Count |
|--------|-------|
| Total links | 42 |
| Passing | 39 |
| Broken | 3 |

## Results by File

### `docs/api.md`

| Line | Status | URL | Detail |
|------|--------|-----|--------|
| 12 | ❌ `missing` | `./endpoints/users.md` | File not found: endpoints/users.md |
```

### 3. Config file support (`~/.linkrot.toml`)

Place a `.linkrot.toml` in your project directory or home directory to set persistent defaults. CLI flags always override config values.

```toml
# ~/.linkrot.toml  or  ./.linkrot.toml
timeout    = 15
workers    = 10
format     = "table"
show_ok    = false
no_external = false
ignore     = ["localhost", "127\\.0\\.0\\.1", "example\\.com"]
```

Supported keys:

| Key | Type | Description |
|-----|------|-------------|
| `timeout` | float | HTTP request timeout in seconds |
| `workers` | int | Max concurrent HTTP workers |
| `format` | string | Default output format (`table`, `json`, `csv`, `markdown`) |
| `show_ok` | bool | Show passing links in table output |
| `no_external` | bool | Skip external URL checks |
| `ignore` | list of strings | Regex patterns — matching URLs are skipped |

Local `.linkrot.toml` takes precedence over `~/.linkrot.toml`.

---

## Install

```bash
pip install linkrot
```

Or from source:

```bash
git clone https://github.com/iamgeetarted/linkrot.git
cd linkrot
pip install -e .
```

**Requires Python 3.11+. Dependencies: `rich`, `httpx[http2]`, `anthropic` (optional for `--suggest`).**

---

## Usage

```
linkrot [path] [options]
```

| Option | Description |
|---|---|
| `path` | Directory to scan (default: `.`) |
| `--no-external` | Skip HTTP checks for external URLs |
| `--format table\|json\|csv` | Output format (default: `table`) |
| `--output FILE` | Write results to file instead of stdout |
| `--ignore PATTERN` | Ignore URLs matching regex (repeatable) |
| `--timeout SECONDS` | HTTP timeout in seconds (default: `10`) |
| `--workers N` | Concurrent HTTP workers (default: `20`) |
| `--show-ok` | Also display passing links in table output |

---

## Examples

### Scan the current directory

```bash
linkrot .
```

```
docs/api.md
  ✗  L12    ./endpoints/users.md  File not found: endpoints/users.md
  ✗  L47    https://old.example.com/guide  HTTP 404

docs/setup.md
  ⚠  L8     README.md#quick-start  Anchor '#quick-start' not found in README.md

3 OK  2 broken  of 5 total
```

### Check a docs folder, skip external links

```bash
linkrot docs/ --no-external
```

### Output as JSON for CI

```bash
linkrot . --format json --output linkcheck.json
```

```json
[
  {
    "file": "docs/api.md",
    "line": 12,
    "url": "./endpoints/users.md",
    "ok": false,
    "status": "missing",
    "detail": "File not found: endpoints/users.md"
  },
  ...
]
```

### Output as CSV

```bash
linkrot . --format csv -o report.csv
```

### Ignore internal/staging URLs

```bash
linkrot . --ignore 'localhost' --ignore 'staging\.example\.com'
```

### Strict CI check (exit code 1 if any broken links)

```bash
linkrot docs/ --no-external || exit 1
```

---

## Status codes

| Symbol | Status | Meaning |
|---|---|---|
| `✓` | `ok` | Link is valid |
| `✗` | `missing` | Internal file not found |
| `⚠` | `anchor-missing` | File exists but anchor heading not found |
| `✗` | `http-404` | External URL returned HTTP error |
| `⏱` | `timeout` | External URL request timed out |
| `✗` | `error` | Connection error (DNS failure, etc.) |

---

## How it works

1. **Scan** — walks the directory recursively, reading every `.md`, `.markdown`, `.html`, and `.htm` file. Ignores `.git`, `node_modules`, `.venv`, `__pycache__`, and `vendor` by default.

2. **Extract** — pulls links from:
   - Markdown inline links: `[text](url)`
   - Markdown image links: `![alt](url)`
   - Markdown reference links: `[ref]: url`
   - HTML `href` and `src` attributes

3. **Check internal links** — resolves relative paths from the linking file's location. Falls back to `.md`/`.html` suffixes for extensionless links. Validates heading anchors by scanning the target file for `## Heading` patterns (GitHub-flavored anchor conversion).

4. **Check external URLs** — deduplicates URLs, then fires concurrent HTTP HEAD requests (with GET fallback for 405 responses). Respects `--timeout` and `--workers`.

5. **Report** — groups results by source file, with color-coded output in the terminal. Returns exit code `0` if all links pass, `1` if any are broken.

---

## Running tests

```bash
pip install pytest
pytest tests/
```

---

## License

MIT

## What's New in v1.4.0

### GitHub Actions Annotations (`--format github`)
Emit inline PR annotations for broken links in CI:
```yaml
- name: Check links
  run: linkrot docs/ --format github
```
Output format: `::error file=docs/README.md,line=42,title=Broken link (http-404)::https://example.com/old`

### Verbose Mode (`--verbose`)
See timing breakdowns and status-code distributions after the scan:
```bash
linkrot . --verbose
# → Timing & Stats panel: scan time, check time, per-status counts
```

### Status Breakdown
Broken links are now categorized by failure type (http-404, timeout, error, etc.) in the terminal summary for faster triage.
