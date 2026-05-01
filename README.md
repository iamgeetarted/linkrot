# linkrot

**Find broken links in Markdown and HTML files — fast.**

`linkrot` scans a directory tree for `.md` and `.html` files, extracts every link, and tells you which ones are dead. It checks:

- **Internal links** — file existence and heading anchors (`#section`)
- **External URLs** — concurrent HTTP HEAD requests with fallback to GET

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

**Requires Python 3.11+. No third-party dependencies.**

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
