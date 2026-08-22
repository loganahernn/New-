"""Submitting an application.

Two modes:

* ``form``  — drive the site's own apply form in the browser (default).
* ``email`` — send the note to an address scraped from the brief, for the
  listings that say "email your CV to ...".

Dry-run is the default everywhere: the form is filled in and screenshotted but
the submit button is never clicked unless you pass ``--apply``.
"""

from __future__ import annotations

import re
import smtplib
import time
from email.message import EmailMessage
from pathlib import Path

from typing import TYPE_CHECKING

from jinja2 import Environment

from .config import Config
from .coverletter import SilentUndefined
from .models import ApplicationResult, Role
from .selectors import as_list, parse_selector

if TYPE_CHECKING:  # pragma: no cover - import only needed for type checking
    from playwright.sync_api import Page

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


_JINJA = Environment(undefined=SilentUndefined)


def _render(value: str, context: dict) -> str:
    return _JINJA.from_string(str(value)).render(**context).strip()


def _locate(page: "Page", candidates):
    """First candidate selector that resolves to a visible element."""
    for raw in as_list(candidates):
        css, _ = parse_selector(raw)
        try:
            locator = page.locator(css).first
            if locator.count() > 0:
                return locator
        except Exception:
            continue
    return None


def href_is_rejected(href: str | None, reject: list[str]) -> str | None:
    """The rejected fragment this href matches, if any."""
    lowered = (href or "").lower()
    if not lowered:
        return None
    for fragment in reject:
        if fragment.lower() in lowered:
            return fragment
    return None


def rejected_href(locator, reject_hrefs) -> str | None:
    """Check a located control's href against the reject list."""
    reject = as_list(reject_hrefs)
    if not reject:
        return None
    try:
        href = locator.get_attribute("href")
    except Exception:
        return None
    return href_is_rejected(href, reject)


def _screenshot(page: "Page", cfg: Config, role: Role, label: str) -> Path | None:
    directory = cfg.resolve_path("application.screenshot_dir", "state/screenshots")
    try:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{role.id}-{label}.png"
        page.screenshot(path=str(path), full_page=True)
        return path
    except Exception:
        return None


def apply_via_form(
    page: "Page",
    cfg: Config,
    role: Role,
    profile: dict,
    cover_letter: str,
    *,
    dry_run: bool = True,
) -> ApplicationResult:
    """Fill and (optionally) submit the site's application form."""
    form_cfg = cfg.get("application.form", {}) or {}
    context = {"role": role, "profile": profile, "cover_letter": cover_letter}

    if not role.url:
        return ApplicationResult(role.id, "failed", "role has no URL to apply on")

    page.goto(role.url, wait_until="domcontentloaded")

    trigger = _locate(page, form_cfg.get("trigger"))
    if trigger is not None:
        # Signed out, the site shows the same "APPLY FOR THIS JOB" button but
        # points it at the login page. Clicking would silently do nothing and
        # look like a successful run, so stop here instead.
        rejected = rejected_href(trigger, form_cfg.get("reject_hrefs"))
        if rejected:
            return ApplicationResult(
                role.id,
                "failed",
                f"apply button leads to {rejected} - you are signed out."
                " Run: tt-autoapply login",
            )
        try:
            trigger.click()
        except Exception as exc:
            return ApplicationResult(role.id, "failed", f"could not open apply form: {exc}")

    for raw in as_list(form_cfg.get("wait_for")):
        css, _ = parse_selector(raw)
        try:
            page.wait_for_selector(css, timeout=int(cfg.get("site.timeout_ms", 30000)))
            break
        except Exception:
            continue

    filled: list[str] = []

    for field in form_cfg.get("fields", []) or []:
        locator = _locate(page, field.get("selector"))
        value = _render(field.get("value", ""), context)
        if locator is None:
            if field.get("optional", True):
                continue
            return ApplicationResult(
                role.id, "failed", f"required field not found: {field.get('selector')}"
            )
        try:
            locator.fill(value)
            filled.append(str(field.get("selector")))
        except Exception as exc:
            if not field.get("optional", True):
                return ApplicationResult(role.id, "failed", f"could not fill field: {exc}")

    for field in form_cfg.get("selects", []) or []:
        locator = _locate(page, field.get("selector"))
        if locator is None:
            continue
        try:
            locator.select_option(label=_render(field.get("value", ""), context))
        except Exception:
            continue

    for raw in as_list(form_cfg.get("checkboxes")):
        locator = _locate(page, raw)
        if locator is None:
            continue
        try:
            locator.check()
        except Exception:
            continue

    for upload in form_cfg.get("uploads", []) or []:
        locator = _locate(page, upload.get("selector"))
        path = Path(str(upload.get("path", ""))).expanduser()
        if locator is None or not path.exists():
            if not upload.get("optional", True):
                return ApplicationResult(
                    role.id, "failed", f"upload missing: {upload.get('path')}"
                )
            continue
        try:
            locator.set_input_files(str(path))
            filled.append(f"upload:{path.name}")
        except Exception:
            continue

    if dry_run:
        shot = _screenshot(page, cfg, role, "dryrun")
        detail = f"dry run - form filled ({len(filled)} fields), not submitted"
        if shot:
            detail += f"; screenshot {shot}"
        return ApplicationResult(role.id, "dry_run", detail, cover_letter=cover_letter)

    submit = _locate(page, form_cfg.get("submit"))
    if submit is None:
        return ApplicationResult(role.id, "failed", "submit button not found")

    try:
        submit.click()
    except Exception as exc:
        return ApplicationResult(role.id, "failed", f"submit click failed: {exc}")

    page.wait_for_timeout(2500)

    success_markers = as_list(form_cfg.get("success"))
    if success_markers:
        for raw in success_markers:
            css, _ = parse_selector(raw)
            try:
                if page.locator(css).count() > 0:
                    _screenshot(page, cfg, role, "applied")
                    return ApplicationResult(
                        role.id, "applied", "submitted", cover_letter=cover_letter
                    )
            except Exception:
                continue
        # The click went through; only the confirmation wording is unrecognised.
        # Recording this as "failed" would retry next run and apply twice, so
        # it gets its own status that counts as applied for de-duplication.
        shot = _screenshot(page, cfg, role, "unconfirmed")
        return ApplicationResult(
            role.id,
            "unconfirmed",
            f"submitted, but no success message matched - check {shot}",
            cover_letter=cover_letter,
        )

    _screenshot(page, cfg, role, "applied")
    return ApplicationResult(
        role.id, "applied", "submitted (no success marker configured)", cover_letter=cover_letter
    )


def find_contact_email(role: Role, cfg: Config) -> str | None:
    override = cfg.get("application.email.to")
    if override:
        return str(override)
    match = EMAIL_RE.search(role.description or "")
    return match.group(0) if match else None


def apply_via_email(
    cfg: Config,
    role: Role,
    profile: dict,
    cover_letter: str,
    *,
    dry_run: bool = True,
) -> ApplicationResult:
    """Email the application to the address given in the brief."""
    email_cfg = cfg.get("application.email", {}) or {}
    to_addr = find_contact_email(role, cfg)
    if not to_addr:
        return ApplicationResult(role.id, "skipped", "no contact email found in brief")

    message = EmailMessage()
    message["From"] = email_cfg.get("from") or profile.get("email", "")
    message["To"] = to_addr
    subject_tpl = email_cfg.get("subject", "Application: {{ role.title }} - {{ profile.name }}")
    message["Subject"] = _render(subject_tpl, {"role": role, "profile": profile})
    message.set_content(cover_letter)

    for attachment in email_cfg.get("attachments", []) or []:
        path = Path(str(attachment)).expanduser()
        if not path.exists():
            continue
        message.add_attachment(
            path.read_bytes(),
            maintype="application",
            subtype="octet-stream",
            filename=path.name,
        )

    if dry_run:
        return ApplicationResult(
            role.id, "dry_run", f"dry run - would email {to_addr}", cover_letter=cover_letter
        )

    host = email_cfg.get("smtp_host")
    if not host:
        return ApplicationResult(role.id, "failed", "application.email.smtp_host not configured")

    try:
        with smtplib.SMTP(host, int(email_cfg.get("smtp_port", 587)), timeout=30) as smtp:
            smtp.starttls()
            username = email_cfg.get("smtp_user")
            password = email_cfg.get("smtp_password")
            if username and password:
                smtp.login(username, password)
            smtp.send_message(message)
    except Exception as exc:
        return ApplicationResult(role.id, "failed", f"smtp error: {exc}")

    return ApplicationResult(role.id, "applied", f"emailed {to_addr}", cover_letter=cover_letter)


def throttle(cfg: Config) -> None:
    """Pause between applications so a run doesn't look like a flood."""
    delay = float(cfg.get("limits.seconds_between_applications", 45) or 0)
    if delay > 0:
        time.sleep(delay)
