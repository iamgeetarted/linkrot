# linkrot

**Find broken links in Markdown and HTML files — fast.**

---

## What's New in v2.1.0

### Priority Fix Queue (`--priority-sort`)
Ranks broken links by a composite priority score (severity × impact) so you fix the most important issues first:
```bash
linkrot . --priority-sort
```
Output shows each broken link's priority score, how many files reference it, and the error type.

### GitHub Actions CI Summary (`--ci-summary`)  
When running in GitHub Actions, write a Markdown step summary to `$GITHUB_STEP_SUMMARY`:
```bash
linkrot . --ci-summary
```
Shows a formatted broken-link table directly in your Actions workflow summary.

### Rate-Limit Report (`--rate-limit-report`)
Identifies domains that rate-limited (HTTP 429) your checker — these may be false negatives, not real link rot:
```bash
linkrot . --rate-limit-report
```

---

## What's New in v2.0

### 1. Per-Domain Rate Limiting (`--domain-concurrency N`)

Prevent hammering individual hosts by capping concurrent requests per domain. Each domain gets its own `asyncio.Semaphore` with a configurable limit, applied on top of the global `--workers` cap.

```bash
linkrot docs/ --domain-concurrency 2   # max 2 simultaneous requests to any one domain
linkrot docs/ --domain-concurrency 5   # more aggressive (default: 3)
```

This stops linkrot from overwhelming rate-limited hosts like GitHub or internal wikis while still running the overall check concurrently across many domains.

### 2. Impact Scoring (`--impact-report`)

After the main report, show a table of broken URLs ranked by how many distinct files reference them. Instantly surfaces the highest-priority fixes — a broken URL referenced in 10 files is far more urgent than one referenced in 1.

```bash
linkrot . --impact-report
```

```
╭────────────────────────────────────────────────┬──────────┬───────────────┬────────╮
│ URL                                            │ Status   │ Files Affected│ Impact │
├────────────────────────────────────────────────┼──────────┼───────────────┼────────┤
│ https://old-api.example.com/reference          │ http-404 │             5 │  HIGH  │
│ https://deprecated-pkg.io/install              │ timeout  │             2 │ MEDIUM │
│ ./setup.md                                     │ missing  │             1 │   LOW  │
╰────────────────────────────────────────────────┴──────────┴───────────────┴────────╯
```

Impact levels: **HIGH** (≥3 files), **MEDIUM** (2 files), **LOW** (1 file).

### 3. AI Triage (`--triage`)

After the scan, stream a Claude Haiku analysis that categorizes broken links by failure type (missing file, HTTP 404, HTTP 5xx, timeout, other), prioritizes which to fix first, suggests a concrete fix strategy per category, and estimates relative effort.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
linkrot docs/ --triage
```

```
────────────────────── AI Triage Report ──────────────────────
1. HTTP 404 (Not Found) — HIGH priority, Medium effort
   These URLs have moved or been removed. Check redirects or search for updated docs.
   Strategy: grep source files for the domain, update links in bulk with sed/find.

2. Timeouts — MEDIUM priority, Low effort
   Likely flaky hosts or overly strict firewall rules in CI.
   Strategy: re-run with --retries 3 --retry-backoff 2.0; suppress persistent offenders with --ignore.

3. Missing internal files — HIGH priority, Low effort
   Files renamed or deleted without updating references.
   Strategy: run with --no-external first to fix internal links quickly, then tackle external.
```

Requires `ANTHROPIC_API_KEY` in your environment.

---

## What's New in v1.9.0

### 1. Wayback Machine Fallback (`--wayback`)

For every broken external URL with a 404 or connection error, linkrot now queries the **Wayback Machine CDX API** and surfaces the most recent archived snapshot. No API key required. Results appear as a Rich table alongside the main report, giving you instant replacement candidates without leaving the terminal.

```bash
linkrot docs/ --wayback
```

```
────────────────── Wayback Machine Snapshots ──────────────────────
╭──────────────────────────────────────┬───────────────────────────────────────────╮
│ Broken URL                           │ Archived Snapshot                         │
├──────────────────────────────────────┼───────────────────────────────────────────┤
│ https://old-docs.example.com/api     │ https://web.archive.org/web/20240312.../  │
│ https://deprecated-lib.io/guide      │ https://web.archive.org/web/20231108.../  │
╰──────────────────────────────────────┴───────────────────────────────────────────╯
  2 snapshots found · 1 not archived
```

### 2. Interactive Fix Mode (`--fix`)

After the scan, walk through each broken link interactively. Type a replacement URL and linkrot rewrites it in the source file — Markdown `[text](url)`, HTML `href/src`, and bare URLs are all handled correctly. Press Enter to skip or `q` to quit early.

```bash
linkrot docs/ --fix
```

```
───────────── Broken link 1/3 ──────────────────────
  URL:    https://old-api.example.com/v1/reference
  Status: http-404  HTTP 404
  File:   docs/api.md  (line 42)

  Replacement URL (blank=skip, q=quit): https://api.example.com/v2/reference
  ✓ Fixed → https://api.example.com/v2/reference

───────────── Broken link 2/3 ──────────────────────
  URL:    ./setup.md#quick-start
  Status: anchor-missing  Anchor '#quick-start' not found
  File:   README.md  (line 7)

  Replacement URL (blank=skip, q=quit):   ← (Enter to skip)

Fixed 1 / 3 broken link(s).
```

Combine with `--wayback` to look up snapshots first, then fix with the archive URL in hand.

### 3. Per-File Health Report (`--file-report`)

Append a per-file breakdown to any scan. Files are sorted by most broken links first — instantly shows which docs need the most attention.

```bash
linkrot . --file-report
```

```
╭─────────────────────────────────────┬───────┬────────┬────┬────────╮
│ File                                │ Total │ Broken │ OK │ Health │
├─────────────────────────────────────┼───────┼────────┼────┼────────┤
│ docs/legacy-migration.md            │    18 │      6 │ 12 │    67% │
│ docs/api-reference.md               │    31 │      3 │ 28 │    90% │
│ README.md                           │    12 │      1 │ 11 │    92% │
│ docs/quickstart.md                  │     8 │      0 │  8 │   100% │
╰─────────────────────────────────────┴───────┴────────┴────┴────────╯
```

---

## What's New in v1.8.0

### 1. Interactive HTML Report (`--format html`)

Generate a self-contained, dark-themed HTML report with **sortable columns**, **live search filtering**, and **status-based filtering**. No external dependencies — everything is inline CSS and vanilla JS. Works perfectly as a CI artifact or email attachment.

```bash
linkrot . --format html -o report.html
```

Features:
- Dark GitHub-style theme with color-coded rows (red = broken, amber = warnings)
- Click any column header to sort ascending/descending
- Search box filters by URL, file path, or status in real-time
- Status filter dropdown (All / Broken only / Warnings only / Passing only)
- Broken link count badge in the browser tab title

### 2. Webhook Notifications (`--notify-webhook URL`)

After the scan, POST a summary to any HTTP endpoint. Automatically uses **Slack Block Kit** format for `hooks.slack.com` URLs; sends a generic JSON payload for everything else. Only fires when broken links are found by default.

```bash
# Slack
linkrot . --notify-webhook https://hooks.slack.com/services/T.../B.../xxx

# Custom endpoint / Discord / Teams
linkrot . --notify-webhook https://my-ci-server.internal/linkrot-hook

# Always notify, even when all links pass
linkrot . --notify-webhook https://... --no-notify-broken-only
```

Slack message example:
```
🚨 linkrot scan complete — 3 broken / 41 passing / 44 total
• https://old-docs.example.com/api — http-404 in docs/api.md:12
• https://deprecated-pkg.io — timeout in README.md:88
• ./setup.md#quick-start — anchor-missing in docs/install.md:5
```

Set `notify_webhook` in `.linkrot.toml` to fire on every CI run without repeating the flag.

### 3. Full Config File Coverage

`.linkrot.toml` now supports **all** CLI flags, not just the original six. Every flag added since v1.2 can be persisted as a default:

```toml
# .linkrot.toml — full v1.8 key set
timeout          = 15.0
workers          = 30
format           = "html"
show_ok          = false
no_external      = false
ignore           = ["localhost", "127\\.0\\.0\\.1"]
cache_ttl        = 48.0
no_cache         = false
suggest          = false
verbose          = false
retries          = 3
retry_backoff    = 1.5
show_redirects   = true
watch            = 0
sitemap          = false
domain_summary   = true
log_file         = "linkrot-audit.jsonl"
notify_webhook   = "https://hooks.slack.com/services/..."
notify_broken_only = true
```

---

## What's New in v1.7.0

### 1. Domain Health Summary (`--domain-summary`)

After the regular report, print a per-domain breakdown of external link health: total checked, broken count, failure rate, and the most common failure status. Sorted worst-first so you can see which third-party domains are rotting fastest.

```bash
linkrot . --domain-summary
```

```
╭─────────────────────────────────────────────────────────────────────────╮
│ Domain Health Summary                                                   │
├──────────────────────────┬───────┬────────┬──────────┬─────────────────┤
│ Domain                   │ Total │ Broken │ % Broken │ Top Status      │
├──────────────────────────┼───────┼────────┼──────────┼─────────────────┤
│ docs.old-vendor.com      │    12 │      8 │      67% │ timeout         │
│ api.deprecated.io        │     5 │      3 │      60% │ http-404        │
│ github.com               │    40 │      1 │       3% │ http-404        │
│ example.com              │     3 │      0 │       0% │                 │
╰──────────────────────────┴───────┴────────┴──────────┴─────────────────╯
```

### 2. JSONL Audit Log (`--log-file FILE`)

Append every check result as a newline-delimited JSON record to a file. Each record includes timestamp, file, line, URL, ok/broken status, HTTP status, and redirect destination. Pipe to `jq`, ingest into ELK, or track over time in CI.

```bash
linkrot . --log-file linkrot-audit.jsonl
```

Each line:
```json
{"ts": "2026-05-13T10:00:00Z", "file": "docs/guide.md", "line": 42, "url": "https://example.com/old", "ok": false, "status": "http-404", "detail": "", "is_external": true, "final_url": ""}
```

Run it in CI and `tail -f linkrot-audit.jsonl | jq 'select(.ok == false)'` to stream new failures.

### 3. Multi-Path Scanning

Pass multiple directories to scan them all in a single run. External URLs are deduplicated so each one is only checked once regardless of how many files reference it.

```bash
linkrot docs/ src/ README.md/..   # scan multiple roots
linkrot . tests/ --format json    # merge results across paths
```

---

## What's New in v1.6.0

### 1. SARIF output format (`--format sarif`)

Export results as [SARIF v2.1.0](https://sarifweb.azurewebsites.net/) — the standard consumed by GitHub Code Scanning — so broken links appear as inline code-scanning alerts on pull requests.

```bash
linkrot . --format sarif -o results.sarif
```

Each broken link becomes a SARIF result with a rule ID (`LR001` internal, `LR002` external, `LR003` anchor-missing), `"error"` severity, a human-readable message, and a precise file + line location.

### 2. Sitemap discovery (`--sitemap`)

Automatically find `sitemap.xml` and `sitemap_index.xml` files anywhere under the scanned directory, extract every `<loc>` URL, and add them to the check queue as external links. Sitemap index files (which list other sitemaps) are followed one level deep via HTTP fetch.

```bash
linkrot . --sitemap
linkrot . --sitemap --no-external   # parse sitemaps but skip HTTP checks
```

Discovered URLs respect `--ignore` patterns and `--no-external` exactly like any other link.

### 3. Baseline delta tracking (`--save-baseline` / `--load-baseline`)

Save the set of currently broken URLs to a JSON file after a run, then load that baseline on future runs to suppress already-known failures and highlight only **new** breakages.

```bash
# First run — establish a baseline
linkrot . --save-baseline baseline.json

# Later runs — only report new failures
linkrot . --load-baseline baseline.json

# Combine: update baseline and report new breakages
linkrot . --load-baseline baseline.json --save-baseline baseline.json
```

Output when a baseline is active:
```
Baseline: 2 new breakage(s), 5 known from baseline (suppressed).
```

---

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

## What's New in v1.5.0

### 1. Retry Logic with Exponential Backoff (`--retries`, `--retry-backoff`)

Transient failures (HTTP 429, 500, 502, 503, 504, and network errors) are automatically retried before being reported as broken. This dramatically reduces false positives from rate-limited or momentarily unavailable servers.

```bash
linkrot . --retries 3               # retry up to 3 times (default: 2)
linkrot . --retries 3 --retry-backoff 2.0   # 2s, 4s, 8s waits
linkrot . --retries 0               # disable retries entirely
```

Backoff doubles on each attempt: with `--retry-backoff 1.0` the waits are 1s → 2s → 4s.

### 2. Watch Mode (`--watch SECS`)

Re-run the full scan every N seconds and show a **diff** of what changed — newly broken links highlighted in red, newly fixed links in green. Perfect for keeping a terminal open while editing docs.

```bash
linkrot . --watch 30        # re-check every 30 seconds
linkrot docs/ --watch 60    # works with any other flags
```

Output after the first run:
```
↻ watch mode — refreshing in 30s (Ctrl-C to stop)
```
Subsequent runs print the diff:
```
─────────────────── Watch Diff ──────────────────────────────────
  ✗ NEW BROKEN:  https://example.com/moved-page
  ✓ NOW FIXED:   https://example.com/was-down
```

### 3. Redirect Tracking (`--show-redirects`)

After the main report, print a table of every URL that answered OK but redirected to a different final destination. Useful for finding outdated links that still "work" but should be updated to point directly at the new location.

```bash
linkrot . --show-redirects
```

```
╭─────────────────────────────── Redirect Report ───────────────────────────────╮
│ File              │ Original URL                   │ → Final URL               │
│ docs/install.md   │ https://old.example.com/guide  │ https://example.com/guide │
│ docs/api.md       │ http://example.com/api         │ https://example.com/api   │
╰───────────────────────────────────────────────────────────────────────────────╯
2 redirects found.
```

---

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
