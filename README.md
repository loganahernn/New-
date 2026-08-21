# tt-autoapply

Scans the [Talent Talks](https://www.talenttalks.co.uk/auditions/) auditions
board, matches each brief against your casting profile, and applies to the ones
you actually fit.

It is deliberately **not** a spray-and-pray bot. Every brief goes through hard
filters first — playing age, gender, ethnicity where the brief specifies it,
pay, travel distance, deadline — and anything that fails is skipped with a
stated reason. Dry-run is the default; you have to pass `--apply` to submit
anything.

## Read this first

Two things worth knowing before you point it at your account:

1. **Check Talent Talks' terms.** Most casting sites' T&Cs restrict automated
   access, and enforcement is usually an account suspension. That is your call
   to make, but make it knowingly. Start in `manual` or dry-run mode.
2. **It applies to everything you fit, by default.** The caps are off
   (`limits: 0`), so any brief that clears the filters gets an application.
   That's the intent — but it also means those filters are the only thing
   between you and a role you shouldn't have gone for. Tune them with `scan`
   until the verdicts look right, *then* pass `--apply`.

## Install

```bash
git clone <this repo> && cd New-
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
playwright install chromium
```

Optional, for LLM matching of free-text briefs:

```bash
pip install -e '.[llm]'
export ANTHROPIC_API_KEY=sk-ant-...
```

## Setup

```bash
cp config.example.yaml config.yaml
cp profile.example.yaml profile.yaml
```

Log in once. A real browser opens, you sign in with your existing Talent Talks
account, and the cookies are saved to `state/session.json`. Your password is
never handled by the tool:

```bash
tt-autoapply login
```

### Import your profile instead of retyping it

Your playing age, height, accents, skills and credits are already on their site.
Pull them straight off your own profile page:

```bash
tt-autoapply import-profile --url https://www.talenttalks.co.uk/profile/you
tt-autoapply import-profile --dry-run --url ...   # see what it found first
```

It reads definition lists, two-column tables and `Label: value` lines, maps what
it recognises onto the profile schema, and prints every field it changed. Values
you'd already set by hand are kept where the import found nothing, the previous
`profile.yaml` is saved as `profile.yaml.bak`, and anything still blank that the
matcher needs is listed at the end.

Whatever it can't find — phone number, travel radius — fill in by hand. Everything
the matcher and the cover-letter writer say about you comes from this file and
nothing else, so accuracy pays off directly.

### Point it at the real page structure

The selectors shipped in `config.example.yaml` are **placeholders** — I couldn't
reach talenttalks.co.uk to read the real markup. Run this to get the real ones:

```bash
tt-autoapply discover
```

It dumps the page HTML and a screenshot to `state/discover/`, then prints the
repeated blocks that look like listing cards and every form field it found.
Paste the winners into `selectors.listing_item`, `selectors.title`,
`selectors.link` in `config.yaml`. Then do the same for a single role page to
map the application form:

```bash
tt-autoapply discover --url https://www.talenttalks.co.uk/auditions/some-role/
```

If `discover` finds nothing, the listings are probably behind the login —
run `tt-autoapply login` first, or use `--headed` to watch what happens.

## Use

```bash
tt-autoapply import-profile  # build profile.yaml from your own profile page
tt-autoapply scan            # scrape and match, apply to nothing
tt-autoapply run             # dry run: fills forms, screenshots, submits nothing
tt-autoapply run --apply     # live: actually submits
tt-autoapply watch --interval 60 --apply   # check hourly
tt-autoapply history         # what you've applied to
```

`scan` is the one to live in while you tune. Each line tells you the verdict and
why:

```
  [FIT 0.85] playing age 18-25 overlaps yours; casting male; location: London  Male Lead - TV Commercial
  [SKIP 0.50] casting female, you are male                                     Female Lead - Feature Film
  [SKIP 0.50] unpaid / expenses only                                           Graduate Short Film
```

Every role you apply to is recorded in `state/applications.db`, so a role is
never applied to twice even across runs.

The only permanent skip is a role you've already applied to. Everything else is
re-checked on every run, so a brief that got passed over — a run that died
part-way, a submission that failed, a listing edited after it was posted — is
picked up next time rather than lost. Set `matching.skip_rejected: true` if
you'd rather not re-spend LLM calls on roles already ruled out.

There's no cap on how many roles a run will apply to. The 45-second gap between
submissions stays regardless; that's about not hammering the site with a burst,
not about limiting how many roles you go for. To throttle yourself while
tuning, set `limits.max_applications_per_run` to a number, or pass `--limit`.

## How matching works

**Rules** (default, free, no API key). Hard filters that block outright:

| Filter | Blocks when |
|---|---|
| Playing age | The brief's range doesn't overlap yours |
| Gender | The brief casts a gender you don't play |
| Ethnicity | The brief specifies one you don't match (ignored for "all ethnicities welcome", and for incidental words like "black comedy") |
| Pay | `paid_only` is set and the brief says unpaid / expenses only / profit share |
| Location | Outside your travel list, and not a self-tape |
| Deadline | Already passed |
| Keywords | Anything in `exclude_keywords`, or nudity when `exclude_nudity` |

Anything that survives is scored, and `keyword_boosts` plus matching skills push
it over `min_score`.

**LLM** (`matching.mode: rules+llm`). Rules handle the mechanical filters; Claude
reads the prose for the things regex can't — "must be comfortable with heights",
"playing a junior doctor", "Northern accent essential" — and drafts a cover
letter that references the actual production. Both have to agree before anything
is submitted: the model can veto a role but never overrides a rules blocker.
Costs a fraction of a penny per brief at `llm_effort: low`.

## Applying

Three modes, set by `application.mode`:

- `form` — drives the site's own apply form (default).
- `email` — for briefs that say "email your CV to…". Pulls the address out of
  the brief, attaches your CV and headshot.
- `manual` — matches and drafts, submits nothing. A shortlist in your terminal.

Dry runs screenshot the filled-in form to `state/screenshots/` so you can check
exactly what would have been sent before you go live.

## Tests

```bash
pip install -e '.[dev]' && pytest
```

69 tests. The matcher ones cover the filters above, including the cases that
bite: `"female"` not being read as `"male"`, `"a black comedy"` not being read
as an ethnicity requirement, dry runs never counting as applications, and a
seen-but-not-applied role staying eligible on the next run. Four end-to-end
tests run the full scrape → match → fill → submit chain, and the profile
import, against a local fake casting site in a real browser (skipped if
Chromium isn't installed).

## Layout

```
tt_autoapply/
  cli.py          commands and the run pipeline
  config.py       YAML loading, ${ENV} expansion
  browser.py      Playwright session, interactive login
  scraper.py      listing + detail extraction
  selectors.py    selector parsing (no browser dependency)
  discover.py     selector discovery for a site you haven't mapped yet
  profile_import.py  builds profile.yaml from your own profile page
  matcher.py      rule-based matching — the filters live here
  llm.py          optional Claude brief matching
  coverletter.py  Jinja2 cover letters
  applier.py      form filling and submission
  store.py        SQLite dedupe + history
  notify.py       run summaries, optional webhook
```

`config.yaml`, `profile.yaml` and `state/` are gitignored — they hold your
personal details and your live session cookies. Keep it that way.
