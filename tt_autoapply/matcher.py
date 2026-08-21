"""Rule-based brief matching.

Pure functions over text — no network, no browser — so the risky parsing logic
is unit-testable. `evaluate()` returns a MatchResult with explicit blockers, so
every skip is explainable rather than a silent drop.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from .models import MatchResult, Role

# --- text extraction -------------------------------------------------------

_AGE_RANGE_PATTERNS = [
    # "playing age 18-25", "aged 18 - 25", "age: 18 to 25", "18–25 years"
    re.compile(r"(?:playing\s+age|age(?:d|s)?)\s*[:\-]?\s*(\d{1,2})\s*(?:-|–|—|to)\s*(\d{1,2})"),
    re.compile(r"\b(\d{1,2})\s*(?:-|–|—|to)\s*(\d{1,2})\s*(?:years?\s*old|yrs?|years)\b"),
]
_AGE_DECADE = re.compile(r"\b(?:early|mid|late)?\s*(\d0)s\b")
_AGE_SINGLE = re.compile(r"(?:playing\s+age|age(?:d)?)\s*[:\-]?\s*(\d{1,2})\b")

# Ethnicity terms grouped into the categories briefs actually use.
_ETHNICITY_TERMS: dict[str, list[str]] = {
    "white": [r"white", r"caucasian"],
    "black": [r"black", r"afro[- ]?caribbean", r"african"],
    "south asian": [r"south asian", r"indian", r"pakistani", r"bangladeshi", r"sri lankan"],
    "east asian": [r"east asian", r"chinese", r"japanese", r"korean", r"vietnamese"],
    "middle eastern": [r"middle eastern", r"arab", r"persian", r"iranian"],
    "mixed": [r"mixed[- ](?:race|heritage)", r"dual heritage"],
    "latin": [r"hispanic", r"latin[oax]"],
}

# A casting word the ethnicity term has to sit next to, so "black comedy" and
# "wearing all black" don't get read as a casting requirement.
_CASTING_NOUN = r"(?:male|female|man|men|woman|women|actor|actress|performer|boy|girl|character|lead|guy|lad)"

_OPEN_ETHNICITY = re.compile(
    r"\b(all ethnicities|any ethnicity|open to all ethnicities|ethnically diverse"
    r"|all ethnic backgrounds|any race|all races|open casting|colou?r[- ]?blind)\b"
)

_UNPAID_MARKERS = [
    "unpaid",
    "expenses only",
    "travel expenses only",
    "no fee",
    "no payment",
    "profit share",
    "deferred payment",
    "copy, credit and meal",
    "credit and meal",
    "voluntary",
]
_PAID_MARKERS = ["paid", "£", "gbp", "fee:", "day rate", "per day", "bectu", "equity minimum"]

_SELF_TAPE_MARKERS = ["self tape", "self-tape", "selftape", "remote", "online audition", "zoom"]

_NUDITY_MARKERS = ["nudity", "topless", "semi-nude", "intimate scenes", "sexual content"]

_MONEY = re.compile(r"£\s?([\d,]+(?:\.\d{1,2})?)")

_DATE_PATTERNS = [
    (re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"), ("y", "m", "d")),
    (re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b"), ("d", "m", "y")),
]
_MONTHS = {
    m: i
    for i, m in enumerate(
        [
            "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december",
        ],
        start=1,
    )
}
_TEXT_DATE = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]+)\s+(\d{4})\b", re.IGNORECASE
)


def extract_age_range(text: str) -> tuple[int, int] | None:
    """Pull a playing-age range out of a brief, if one is stated."""
    lowered = text.lower()
    for pattern in _AGE_RANGE_PATTERNS:
        m = pattern.search(lowered)
        if m:
            lo, hi = int(m.group(1)), int(m.group(2))
            if lo <= hi and hi <= 99:
                return lo, hi
    m = _AGE_DECADE.search(lowered)
    if m:
        decade = int(m.group(1))
        return decade, decade + 9
    m = _AGE_SINGLE.search(lowered)
    if m:
        age = int(m.group(1))
        return age, age
    return None


def extract_genders(text: str) -> set[str]:
    """Which genders a brief is casting for. Empty set means unspecified."""
    lowered = text.lower()
    found: set[str] = set()
    if re.search(r"\b(any gender|all genders|gender[- ]?neutral|any\s+ethnicity.*gender)\b", lowered):
        found.add("any")
    if re.search(r"\b(female|woman|women|actress|girl)\b", lowered):
        found.add("female")
    # Check "male" only where it isn't the tail of "female".
    if re.search(r"(?<!fe)\b(male|man|men|actor\b(?!/actress)|boy)\b", lowered):
        found.add("male")
    if re.search(r"\b(non[- ]?binary|nb performer|enby)\b", lowered):
        found.add("non-binary")
    if re.search(r"\b(trans|transgender)\b", lowered):
        found.add("trans")
    return found


def normalise_ethnicity(value: str) -> str | None:
    """Map a free-text ethnicity ("White British") to a category ("white")."""
    lowered = (value or "").lower()
    for category, terms in _ETHNICITY_TERMS.items():
        if any(re.search(rf"\b{term}\b", lowered) for term in terms):
            return category
    return None


def extract_ethnicities(text: str) -> set[str]:
    """Ethnicity categories a brief is specifically casting for.

    Empty set means the brief didn't specify — which is the common case and is
    never treated as a blocker.
    """
    lowered = text.lower()
    if _OPEN_ETHNICITY.search(lowered):
        return set()

    found: set[str] = set()
    for category, terms in _ETHNICITY_TERMS.items():
        for term in terms:
            # The term must sit next to a casting noun, in either order.
            near = (
                rf"\b{term}\b(?:\s+\w+){{0,2}}\s+{_CASTING_NOUN}\b"
                rf"|{_CASTING_NOUN}\b(?:\s*,)?\s*(?:\w+\s+){{0,2}}\b{term}\b"
            )
            if re.search(near, lowered):
                found.add(category)
                break
    return found


def is_unpaid(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _UNPAID_MARKERS)


def mentions_pay(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _PAID_MARKERS)


def extract_amounts(text: str) -> list[float]:
    """Every £ amount in the text, largest first."""
    values = []
    for raw in _MONEY.findall(text):
        try:
            values.append(float(raw.replace(",", "")))
        except ValueError:
            continue
    return sorted(values, reverse=True)


def is_self_tape(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _SELF_TAPE_MARKERS)


def has_nudity(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _NUDITY_MARKERS)


_RELATIVE_AGE = re.compile(
    r"\b(?:(\d+)|an?)\s*(minute|min|hour|hr|day|week|month|year)s?\s+ago\b"
)
_AGE_UNIT_DAYS = {
    "minute": 0, "min": 0, "hour": 0, "hr": 0,
    "day": 1, "week": 7, "month": 30, "year": 365,
}
_POSTED_TODAY = re.compile(r"\b(just now|today|posted today|moments ago|new listing|new today)\b")
_POSTED_YESTERDAY = re.compile(r"\byesterday\b")


def extract_posted_date(text: str, *, today: date | None = None) -> date | None:
    """How long ago a listing went up.

    Boards write this every which way — "2 days ago", "Posted yesterday",
    "Posted on 12 August 2026" — so try relative forms first, then absolute.
    """
    today = today or date.today()
    lowered = (text or "").lower()

    if _POSTED_TODAY.search(lowered):
        return today
    if _POSTED_YESTERDAY.search(lowered):
        return today - timedelta(days=1)

    m = _RELATIVE_AGE.search(lowered)
    if m:
        quantity = int(m.group(1)) if m.group(1) else 1
        days = _AGE_UNIT_DAYS.get(m.group(2), 0) * quantity
        return today - timedelta(days=days)

    return _parse_absolute_date(lowered)


def _parse_absolute_date(text: str) -> date | None:
    """Best-effort parse of a written date. Returns None when nothing parses."""
    for pattern, order in _DATE_PATTERNS:
        m = pattern.search(text)
        if m:
            parts = dict(zip(order, m.groups()))
            try:
                return date(int(parts["y"]), int(parts["m"]), int(parts["d"]))
            except ValueError:
                continue
    m = _TEXT_DATE.search(text)
    if m:
        month = _MONTHS.get(m.group(2).lower())
        if month:
            try:
                return date(int(m.group(3)), month, int(m.group(1)))
            except ValueError:
                return None
    return None


def extract_deadline(text: str) -> date | None:
    """When applications close, if the brief states a parseable date."""
    return _parse_absolute_date(text)


# --- matching --------------------------------------------------------------


def _overlaps(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] <= b[1] and b[0] <= a[1]


def role_age_days(
    role: Role, *, today: date | None = None, first_seen: date | None = None
) -> int | None:
    """How old a listing is, in days, or None if we can't tell.

    Prefers the date the site states. Falls back to when we first saw the
    listing, which is what makes "only new posts" work on a board that doesn't
    show dates at all.
    """
    today = today or date.today()
    posted = extract_posted_date(role.posted or "", today=today)
    if posted is None:
        posted = extract_posted_date(role.description or "", today=today)

    candidates = [d for d in (posted, first_seen) if d is not None]
    if not candidates:
        return None
    # The most recent signal wins: a listing we first saw today isn't old just
    # because a date somewhere in the brief parsed as last year.
    return max(0, (today - max(candidates)).days)


def evaluate(
    role: Role,
    profile: dict,
    rules: dict,
    *,
    today: date | None = None,
    first_seen: date | None = None,
) -> MatchResult:
    """Score a role against the performer profile and matching rules."""
    today = today or date.today()
    text = role.searchable_text
    reasons: list[str] = []
    blockers: list[str] = []
    score = 0.5

    # --- hard filters ---
    exclude = [k.lower() for k in rules.get("exclude_keywords", []) or []]
    for keyword in exclude:
        if keyword in text:
            blockers.append(f"excluded keyword: {keyword!r}")

    require = [k.lower() for k in rules.get("require_keywords", []) or []]
    for keyword in require:
        if keyword not in text:
            blockers.append(f"missing required keyword: {keyword!r}")

    if rules.get("exclude_nudity", True) and has_nudity(text):
        blockers.append("brief mentions nudity/intimate content")

    # Playing age
    role_age = extract_age_range(text)
    my_age = profile.get("playing_age") or {}
    if role_age and my_age.get("min") is not None and my_age.get("max") is not None:
        mine = (int(my_age["min"]), int(my_age["max"]))
        if _overlaps(role_age, mine):
            reasons.append(f"playing age {role_age[0]}-{role_age[1]} overlaps yours")
            score += 0.15
        else:
            blockers.append(
                f"playing age {role_age[0]}-{role_age[1]} vs yours {mine[0]}-{mine[1]}"
            )

    # Gender
    role_genders = extract_genders(text)
    my_gender = str(profile.get("gender", "")).lower().strip()
    if role_genders and my_gender:
        acceptable = {my_gender, "any"} | {
            g.lower() for g in (profile.get("also_plays") or [])
        }
        if role_genders & acceptable:
            reasons.append(f"casting {'/'.join(sorted(role_genders))}")
            score += 0.1
        else:
            blockers.append(
                f"casting {'/'.join(sorted(role_genders))}, you are {my_gender}"
            )

    # Ethnicity — only when the brief states it as a character requirement.
    if rules.get("ethnicity_filter", True):
        role_ethnicities = extract_ethnicities(text)
        mine = normalise_ethnicity(str(profile.get("ethnicity", "")))
        if role_ethnicities and mine:
            if mine in role_ethnicities:
                reasons.append(f"casting {'/'.join(sorted(role_ethnicities))}")
                score += 0.1
            else:
                blockers.append(
                    f"brief specifies {'/'.join(sorted(role_ethnicities))}, you are {mine}"
                )

    # Pay
    pay_rules = rules.get("pay", {}) or {}
    if pay_rules.get("paid_only") and is_unpaid(text):
        blockers.append("unpaid / expenses only")
    min_rate = pay_rules.get("min_amount")
    if min_rate is not None:
        amounts = extract_amounts(role.pay or "") or extract_amounts(role.description)
        if amounts and amounts[0] < float(min_rate):
            blockers.append(f"top fee £{amounts[0]:.0f} below your £{float(min_rate):.0f} floor")
        elif amounts:
            reasons.append(f"fee up to £{amounts[0]:.0f}")
            score += 0.1

    # Location
    loc_rules = rules.get("location", {}) or {}
    allowed = [a.lower() for a in loc_rules.get("allowed", []) or []]
    role_location = (role.location or "").lower()
    if allowed:
        if is_self_tape(text) and loc_rules.get("allow_self_tape", True):
            reasons.append("self-tape / remote")
            score += 0.1
        elif not role_location:
            reasons.append("location not stated")
        elif any(a in role_location or a in text for a in allowed):
            reasons.append(f"location: {role.location}")
            score += 0.15
        else:
            blockers.append(f"location {role.location!r} outside your travel list")

    # Freshness — the whole point is catching new posts, not working a backlog.
    max_age = rules.get("max_age_days")
    if max_age:
        age = role_age_days(role, today=today, first_seen=first_seen)
        if age is None:
            if rules.get("require_posted_date", False):
                blockers.append("no posted date and require_posted_date is on")
        elif age > int(max_age):
            blockers.append(f"posted {age} days ago, older than {int(max_age)}-day limit")
        else:
            reasons.append(f"posted {age}d ago")
            # Newer listings score higher: you want to be early in the pile.
            score += 0.1 if age <= 2 else 0.05

    # Deadline
    deadline = extract_deadline(role.deadline or "") or extract_deadline(role.description)
    if deadline and deadline < today:
        blockers.append(f"deadline passed ({deadline.isoformat()})")
    elif deadline:
        reasons.append(f"closes {deadline.isoformat()}")

    # --- soft scoring ---
    for keyword, boost in (rules.get("keyword_boosts", {}) or {}).items():
        if keyword.lower() in text:
            score += float(boost)
            reasons.append(f"+{float(boost):.2f} {keyword}")

    for skill in profile.get("skills", []) or []:
        if str(skill).lower() in text:
            score += 0.05
            reasons.append(f"skill match: {skill}")

    score = max(0.0, min(1.0, score))
    min_score = float(rules.get("min_score", 0.6))
    fits = not blockers and score >= min_score
    if not blockers and score < min_score:
        blockers.append(f"score {score:.2f} below threshold {min_score:.2f}")

    return MatchResult(
        role_id=role.id,
        fits=fits,
        score=score,
        reasons=reasons,
        blockers=blockers,
        source="rules",
    )
