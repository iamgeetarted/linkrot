"""Webhook notifications — POST a JSON summary of broken links to a URL.

Supports Slack's incoming-webhook format out of the box, and sends a generic
JSON payload that most HTTP endpoints can consume.  Designed to be called after
a scan completes so teams get alerted in Slack/Discord/Teams or a custom handler.
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .checker import CheckResult


def _slack_payload(broken: "list[CheckResult]", root: Path, total: int) -> dict:
    """Build a Slack-compatible Block Kit payload."""
    broken_count = len(broken)
    ok_count = total - broken_count

    status_emoji = ":white_check_mark:" if broken_count == 0 else ":rotating_light:"
    summary_line = (
        f"{status_emoji} *linkrot scan complete* — "
        f"{broken_count} broken / {ok_count} passing / {total} total"
    )

    blocks: list[dict] = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": summary_line},
        }
    ]

    if broken:
        # Show up to 10 broken links as bullets
        sample = broken[:10]
        lines: list[str] = []
        for cr in sample:
            try:
                rel = str(cr.link.source_file.relative_to(root))
            except ValueError:
                rel = str(cr.link.source_file)
            lines.append(
                f"• `{cr.link.url}` — *{cr.status}* in `{rel}:{cr.link.line_number}`"
            )
        if len(broken) > 10:
            lines.append(f"_…and {len(broken) - 10} more_")

        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "\n".join(lines)},
        })

    blocks.append({"type": "divider"})
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": f"Root: `{root}`  ·  sent by *linkrot*",
            }
        ],
    })

    return {"blocks": blocks}


def _generic_payload(broken: "list[CheckResult]", root: Path, total: int) -> dict:
    """Build a generic JSON payload suitable for any HTTP endpoint."""
    broken_count = len(broken)

    def _cr_dict(cr: "CheckResult") -> dict:
        try:
            rel = str(cr.link.source_file.relative_to(root))
        except ValueError:
            rel = str(cr.link.source_file)
        return {
            "file": rel,
            "line": cr.link.line_number,
            "url": cr.link.url,
            "status": cr.status,
            "detail": cr.detail or "",
            "is_external": cr.link.is_external,
        }

    return {
        "tool": "linkrot",
        "root": str(root),
        "summary": {
            "total": total,
            "broken": broken_count,
            "passing": total - broken_count,
        },
        "broken_links": [_cr_dict(cr) for cr in broken],
    }


def notify(
    results: "list[CheckResult]",
    webhook_url: str,
    root: Path,
    broken_only: bool = True,
) -> None:
    """POST a summary payload to *webhook_url*.

    Automatically uses Slack Block Kit format when the URL contains
    ``hooks.slack.com``; falls back to a generic JSON payload otherwise.

    Args:
        results:      Full list of check results from this run.
        webhook_url:  HTTP/HTTPS URL to POST to.
        root:         Project root (used for relative file paths in the payload).
        broken_only:  If True (default), skip the notification when there are no
                      broken links.  Set to False to always notify.
    """
    broken = [r for r in results if not r.ok]
    total = len(results)

    if broken_only and not broken:
        return

    is_slack = "hooks.slack.com" in webhook_url
    if is_slack:
        payload = _slack_payload(broken, root, total)
    else:
        payload = _generic_payload(broken, root, total)

    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        webhook_url,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "linkrot"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
            status = resp.status
            if status >= 400:
                import sys
                print(
                    f"linkrot: webhook returned HTTP {status} from {webhook_url}",
                    file=sys.stderr,
                )
    except urllib.error.URLError as exc:
        import sys
        print(f"linkrot: webhook notification failed: {exc}", file=sys.stderr)
