"""Run summaries — console, and optionally a webhook (Slack/Discord/ntfy)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from .config import Config
from .models import ApplicationResult, MatchResult, Role


def format_summary(
    roles: list[Role],
    results: list[tuple[Role, MatchResult]],
    applications: list[ApplicationResult],
) -> str:
    fits = [r for r, m in results if m.fits]
    applied = [a for a in applications if a.status in ("applied", "unconfirmed")]
    review = [a for a in applications if a.status == "needs_review"]
    dry = [a for a in applications if a.status == "dry_run"]
    failed = [a for a in applications if a.status == "failed"]

    lines = [
        f"Scanned {len(roles)} roles - {len(fits)} matched"
        f" - {len(applied)} applied, {len(dry)} dry-run,"
        f" {len(review)} need you, {len(failed)} failed"
    ]
    for app in review:
        lines.append(f"  NEEDS YOU {app.role_id}: {app.detail}")
    for role, match in results:
        if match.fits:
            lines.append(f"  MATCH {match.score:.2f}  {role.title}  {role.url}")
    for app in failed:
        lines.append(f"  FAILED {app.role_id}: {app.detail}")
    return "\n".join(lines)


def send(cfg: Config, message: str) -> None:
    if cfg.get("notify.console", True):
        print(message)

    url = cfg.get("notify.webhook_url")
    if not url:
        return

    field = cfg.get("notify.webhook_field", "text")
    payload = json.dumps({field: message}).encode("utf-8")
    request = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        urllib.request.urlopen(request, timeout=15).close()
    except (urllib.error.URLError, OSError) as exc:
        print(f"[notify] webhook failed: {exc}")
