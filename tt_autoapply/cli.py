"""Command line entry point."""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date

import yaml

from . import notify
from .applier import apply_via_email, apply_via_form, throttle
from .browser import browser_context, interactive_login, is_logged_in
from .config import Config
from .coverletter import DEFAULT_NOTE, brief_asks_for_details
from .coverletter import render as render_cover_letter
from .discover import discover, print_report
from .llm import LLMUnavailable, assess, combine
from .matcher import evaluate
from .models import ApplicationResult, MatchResult, Role
from .profile_import import merge_profile, missing_fields, scrape_profile, write_profile
from .scraper import enrich_role, scrape_roles
from .store import Store
from . import wizard


def _load(args) -> Config:
    return Config.load(args.config)


# --- commands --------------------------------------------------------------


def cmd_login(args) -> int:
    cfg = _load(args)
    interactive_login(cfg)
    return 0


def cmd_discover(args) -> int:
    cfg = _load(args)
    with browser_context(cfg, headless=not args.headed) as context:
        page = context.new_page()
        report = discover(page, cfg, url=args.url)
    print_report(report)
    return 0


def cmd_start(args) -> int:
    """Log in, scan both page types, and write one file to send back."""
    cfg = _load(args)
    state_path = cfg.resolve_path("browser.storage_state")

    print("=" * 62)
    print("  tt-autoapply setup")
    print("=" * 62)

    if state_path.exists() and not args.relogin:
        print(f"\nUsing the saved login at {state_path}")
        print("(run with --relogin to sign in again)")
    else:
        print("\nStep 1 of 2 - logging in")
        print("A browser window is about to open. Sign in to Talent Talks as")
        print("normal, then come back here and press Enter.")
        input("\nPress Enter to open the browser... ")
        interactive_login(cfg)

    print("\nStep 2 of 2 - reading the page structure")
    print("Nothing is applied to and nothing is changed. This only looks.")

    with browser_context(cfg, headless=not args.headed) as context:
        page = context.new_page()
        page.goto(cfg.listing_url, wait_until="domcontentloaded")
        signed_in = is_logged_in(page, cfg)
        if not signed_in:
            print(
                "\n  ! You are NOT signed in - the saved session has expired.\n"
                "    The scan below still works, but it sees the signed-out\n"
                "    version of the site. Re-run with --relogin to fix it."
            )
        path, listing, detail = wizard.run(page=page, cfg=cfg, discover_fn=discover)

    print("\n" + "=" * 62)
    if not signed_in:
        print("  Done, but you were signed out - run: tt-autoapply start --relogin")
    elif wizard.find_listing_blocks(listing):
        print("  Done.")
    else:
        print("  Done, but nothing listing-shaped was found.")
        print("  Most likely the login didn't take. Try: --relogin")
        print(f"  A screenshot of what it saw is in {cfg.resolve_path('discover.output_dir', 'state/discover')}")
    print("=" * 62)
    print(f"\nSend this file back to get your config filled in:\n\n  {path}\n")
    print("It has page structure only - no password, no personal details.")
    print("In Finder: Go > Go to Folder, paste the path above, then drag the")
    print("file into the chat.\n")
    return 0


def cmd_import_profile(args) -> int:
    cfg = _load(args)
    url = args.url or cfg.get("site.profile_url")
    if not url:
        print(
            "No profile URL. Pass --url with the address of your own Talent Talks\n"
            "profile page (the one showing your playing age, height and credits),\n"
            "or set site.profile_url in config.yaml."
        )
        return 1

    with browser_context(cfg, headless=not args.headed) as context:
        page = context.new_page()
        imported = scrape_profile(page, url)

    if not imported:
        print(
            f"Read {url} but found no recognisable profile fields.\n"
            "If the page needs a login, run: tt-autoapply login\n"
            "Otherwise run `tt-autoapply discover --url <that page>` and check the dump."
        )
        return 1

    path = cfg.resolve_path("profile", "profile.yaml")
    existing = {}
    if path.exists():
        existing = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    merged, changes = merge_profile(existing, imported)

    print(f"\nRead {len(imported)} fields from {url}:")
    for change in changes:
        print(f"  {change}")
    if not changes:
        print("  (nothing new — your profile already matches)")

    if args.dry_run:
        print("\nDry run — profile.yaml not written. Drop --dry-run to save.")
        return 0

    backup = write_profile(path, merged)
    print(f"\nWrote {path}" + (f" (previous version kept at {backup})" if backup else ""))

    gaps = missing_fields(merged)
    if gaps:
        print(
            "\nStill blank, and the matcher needs these — fill them in by hand:\n  "
            + ", ".join(gaps)
        )
    return 0


def _match(
    role: Role, profile: dict, cfg: Config, *, first_seen: date | None = None
) -> MatchResult:
    """Run the configured matching strategy for one role."""
    rules = cfg.get("matching", {}) or {}
    result = evaluate(role, profile, rules, today=date.today(), first_seen=first_seen)
    mode = str(rules.get("mode", "rules"))

    if mode == "rules":
        return result
    if mode == "rules+llm" and not result.fits:
        # No point spending a model call on a role the hard filters already
        # rejected — rules blockers are never overridden by the LLM.
        return result

    try:
        verdict = assess(
            role,
            profile,
            model=str(rules.get("llm_model", "claude-opus-5")),
            effort=str(rules.get("llm_effort", "low")),
        )
    except LLMUnavailable as exc:
        result.reasons.append(f"llm unavailable ({exc}) - rules only")
        return result
    except Exception as exc:  # network, JSON, schema drift
        result.reasons.append(f"llm error ({exc}) - rules only")
        return result

    if mode == "llm":
        combined = MatchResult(
            role_id=role.id,
            fits=verdict.fits,
            score=verdict.confidence,
            reasons=verdict.reasons,
            blockers=verdict.concerns if not verdict.fits else [],
            source="llm",
        )
    else:
        combined = combine(result, verdict)

    combined.cover_letter = verdict.cover_letter
    return combined


def _within_limit(count: int, limit) -> bool:
    """A limit of 0, None or negative means no cap — apply to everything that fits."""
    if limit is None:
        return True
    limit = int(limit)
    return limit <= 0 or count < limit


def _run_pipeline(
    cfg: Config, *, do_apply: bool, limit: int | None, include_existing: bool = False
) -> int:
    profile = cfg.load_profile()
    if include_existing:
        # Opt back into the backlog: no baseline skip, no age cut-off.
        cfg.data.setdefault("matching", {})["max_age_days"] = 0
        cfg.data["first_run_baseline"] = False

    store = Store(cfg.resolve_path("storage.database"))
    template_setting = cfg.get("application.cover_letter_template")
    template = (
        cfg.resolve_path("application.cover_letter_template") if template_setting else None
    )
    note = str(cfg.get("application.note", DEFAULT_NOTE))
    flag_when_asked = bool(cfg.get("application.flag_when_brief_asks", True))

    max_per_run = limit if limit is not None else cfg.get("limits.max_applications_per_run", 0)
    max_per_day = cfg.get("limits.max_applications_per_day", 0)
    already_today = store.applications_today()
    skip_rejected = bool(cfg.get("matching.skip_rejected", False))

    results: list[tuple[Role, MatchResult]] = []
    applications: list[ApplicationResult] = []

    with browser_context(cfg) as context:
        page = context.new_page()
        page.goto(cfg.listing_url, wait_until="domcontentloaded")
        if not is_logged_in(page, cfg):
            print("Not logged in (logged_in_marker not found). Run: tt-autoapply login")
            store.close()
            return 2

        roles = scrape_roles(page, cfg)
        print(f"Found {len(roles)} listings at {cfg.listing_url}")

        # First ever run: record what's already on the board and apply to none
        # of it. Otherwise the first run works through the entire back
        # catalogue, which is the opposite of watching for new posts.
        if store.is_empty() and cfg.get("first_run_baseline", True):
            for role in roles:
                store.record_role(role)
            store.record_baseline(role.id for role in roles)
            print(
                f"\nFirst run — recorded {len(roles)} existing listings as the baseline "
                "and applied to none of them.\nFrom here on only new posts are "
                "considered. To go for these too, run with --include-existing."
            )
            store.close()
            return 0

        for role in roles:
            store.record_role(role)

            # The only permanent skip is a role already applied to. Everything
            # else gets re-checked every run — a brief that was passed over
            # because a limit was hit, a submission failed, or the listing was
            # later edited must not be lost just because we've seen it once.
            if store.has_applied(role.id):
                continue
            if role.already_applied:
                # The board itself says so. Record it, so a hand-made
                # application is never duplicated on a later run either.
                store.record_application(
                    ApplicationResult(role.id, "applied", "already applied (per the site)")
                )
                continue
            if store.is_baseline(role.id) and not include_existing:
                continue  # was already on the board before we started watching
            if skip_rejected and store.was_rejected(role.id):
                continue

            try:
                role = enrich_role(page, cfg, role)
            except Exception as exc:
                print(f"  ! could not open {role.url}: {exc}")
            store.record_role(role)

            match = _match(role, profile, cfg, first_seen=store.first_seen(role.id))
            store.record_match(match)
            results.append((role, match))
            print(f"  {match.summary()}  {role.title}")

            if not match.fits:
                continue

            sent = len([a for a in applications if a.status == "applied"])
            if not _within_limit(sent, max_per_run):
                print("  - per-run application limit reached")
                continue
            if not _within_limit(already_today + sent, max_per_day):
                print("  - daily application limit reached")
                continue

            cover_letter = match.cover_letter or render_cover_letter(
                role, profile, template, note=note
            )

            # A brief asking for specifics deserves a real answer, not
            # "Available" — hold it back rather than send a useless note.
            asked = brief_asks_for_details(role) if flag_when_asked else None
            if asked and not match.cover_letter:
                result = ApplicationResult(
                    role.id,
                    "needs_review",
                    f'brief asks for specifics ("{asked}") - apply to this one yourself',
                    cover_letter=cover_letter,
                )
                store.record_application(result)
                applications.append(result)
                print(f"    -> needs you: {result.detail}")
                continue

            if do_apply and cfg.get("application.require_confirmation", False):
                answer = input(f"    Apply to {role.title!r}? [y/N] ").strip().lower()
                if answer != "y":
                    applications.append(ApplicationResult(role.id, "skipped", "declined at prompt"))
                    continue

            mode = str(cfg.get("application.mode", "form"))
            if mode == "email":
                result = apply_via_email(
                    cfg, role, profile, cover_letter, dry_run=not do_apply
                )
            elif mode == "manual":
                result = ApplicationResult(
                    role.id, "skipped", "manual mode - review and apply yourself",
                    cover_letter=cover_letter,
                )
            else:
                result = apply_via_form(
                    page, cfg, role, profile, cover_letter, dry_run=not do_apply
                )

            store.record_application(result)
            applications.append(result)
            print(f"    -> {result.status}: {result.detail}")

            if result.status == "applied":
                throttle(cfg)

    summary = notify.format_summary([r for r, _ in results], results, applications)
    notify.send(cfg, summary)
    store.close()
    return 0


def cmd_scan(args) -> int:
    return _run_pipeline(
        _load(args),
        do_apply=False,
        limit=args.limit,
        include_existing=getattr(args, "include_existing", False),
    )


def cmd_run(args) -> int:
    cfg = _load(args)
    if args.apply:
        print("LIVE MODE - applications will be submitted.")
    else:
        print("DRY RUN - nothing will be submitted. Pass --apply to go live.")
    return _run_pipeline(
        cfg,
        do_apply=args.apply,
        limit=args.limit,
        include_existing=getattr(args, "include_existing", False),
    )


def cmd_watch(args) -> int:
    cfg = _load(args)
    interval = args.interval * 60
    print(f"Watching {cfg.listing_url} every {args.interval} min. Ctrl-C to stop.")
    while True:
        try:
            _run_pipeline(cfg, do_apply=args.apply, limit=args.limit)
        except KeyboardInterrupt:
            return 0
        except Exception as exc:
            print(f"[watch] run failed: {exc}")
        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            return 0


def cmd_history(args) -> int:
    cfg = _load(args)
    with Store(cfg.resolve_path("storage.database")) as store:
        rows = store.history(args.limit)
        if not rows:
            print("No applications recorded yet.")
            return 0
        for row in rows:
            print(
                f"{row['submitted_at']}  {row['status']:<8} {row['title'] or row['role_id']}"
                f"\n    {row['url'] or ''}  {row['detail']}"
            )
    return 0


def cmd_prune(args) -> int:
    cfg = _load(args)
    with Store(cfg.resolve_path("storage.database")) as store:
        removed = store.prune(args.days)
    print(f"Removed {removed} stale role records.")
    return 0


# --- argument parsing ------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tt-autoapply",
        description="Scan Talent Talks auditions and apply to the ones you fit.",
    )
    parser.add_argument("-c", "--config", default="config.yaml", help="path to config.yaml")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("login", help="log in once in a visible browser and save the session")
    p.set_defaults(func=cmd_login)

    p = sub.add_parser(
        "start", help="guided setup: log in, scan the pages, write one file to send back"
    )
    p.add_argument("--relogin", action="store_true", help="sign in again even if a session is saved")
    p.add_argument("--headed", action="store_true", help="show the browser while scanning")
    p.set_defaults(func=cmd_start)

    p = sub.add_parser("discover", help="inspect a page and print selector candidates")
    p.add_argument("--url", help="page to inspect (defaults to the auditions listing)")
    p.add_argument("--headed", action="store_true", help="show the browser")
    p.set_defaults(func=cmd_discover)

    p = sub.add_parser(
        "import-profile", help="build profile.yaml from your own Talent Talks profile"
    )
    p.add_argument("--url", help="your profile page (defaults to site.profile_url)")
    p.add_argument("--headed", action="store_true", help="show the browser")
    p.add_argument("--dry-run", action="store_true", help="show what it found, write nothing")
    p.set_defaults(func=cmd_import_profile)

    p = sub.add_parser("scan", help="scrape and match roles without applying")
    p.add_argument("--limit", type=int, help="stop after N matches")
    p.add_argument(
        "--include-existing",
        action="store_true",
        help="also consider listings already on the board, not just new posts",
    )
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser("run", help="scan, match and apply (dry run unless --apply)")
    p.add_argument("--apply", action="store_true", help="actually submit applications")
    p.add_argument("--limit", type=int, help="max applications this run")
    p.add_argument(
        "--include-existing",
        action="store_true",
        help="also apply to listings already on the board, not just new posts",
    )
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("watch", help="run on a loop")
    p.add_argument("--interval", type=int, default=60, help="minutes between runs")
    p.add_argument("--apply", action="store_true", help="actually submit applications")
    p.add_argument("--limit", type=int, help="max applications per run")
    p.set_defaults(func=cmd_watch)

    p = sub.add_parser("history", help="show what you've applied to")
    p.add_argument("--limit", type=int, default=50)
    p.set_defaults(func=cmd_history)

    p = sub.add_parser("prune", help="drop stale role records")
    p.add_argument("--days", type=int, default=180)
    p.set_defaults(func=cmd_prune)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
