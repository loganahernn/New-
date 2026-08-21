"""SQLite history.

Two jobs: never apply to the same role twice, and keep an auditable record of
what was sent where, so you can answer "did I already go for that one?".
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .models import ApplicationResult, MatchResult, Role

SCHEMA = """
CREATE TABLE IF NOT EXISTS roles (
    id          TEXT PRIMARY KEY,
    url         TEXT,
    title       TEXT,
    company     TEXT,
    location    TEXT,
    pay         TEXT,
    deadline    TEXT,
    first_seen  TEXT NOT NULL,
    last_seen   TEXT NOT NULL,
    payload     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS matches (
    role_id     TEXT NOT NULL,
    fits        INTEGER NOT NULL,
    score       REAL NOT NULL,
    source      TEXT NOT NULL,
    reasons     TEXT NOT NULL,
    blockers    TEXT NOT NULL,
    evaluated_at TEXT NOT NULL,
    PRIMARY KEY (role_id, source)
);

CREATE TABLE IF NOT EXISTS applications (
    role_id      TEXT PRIMARY KEY,
    status       TEXT NOT NULL,
    detail       TEXT NOT NULL,
    cover_letter TEXT NOT NULL,
    submitted_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # --- roles ---

    def record_role(self, role: Role) -> bool:
        """Upsert a role. Returns True if this is the first time we've seen it."""
        now = _now()
        cur = self.conn.execute("SELECT id FROM roles WHERE id = ?", (role.id,))
        is_new = cur.fetchone() is None
        if is_new:
            self.conn.execute(
                "INSERT INTO roles (id, url, title, company, location, pay, deadline,"
                " first_seen, last_seen, payload) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    role.id, role.url, role.title, role.company, role.location,
                    role.pay, role.deadline, now, now, json.dumps(role.to_dict()),
                ),
            )
        else:
            self.conn.execute(
                "UPDATE roles SET last_seen = ?, payload = ? WHERE id = ?",
                (now, json.dumps(role.to_dict()), role.id),
            )
        self.conn.commit()
        return is_new

    def seen_role_ids(self) -> set[str]:
        return {r["id"] for r in self.conn.execute("SELECT id FROM roles")}

    # --- matches ---

    def record_match(self, result: MatchResult) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO matches"
            " (role_id, fits, score, source, reasons, blockers, evaluated_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (
                result.role_id, int(result.fits), result.score, result.source,
                json.dumps(result.reasons), json.dumps(result.blockers), _now(),
            ),
        )
        self.conn.commit()

    # --- applications ---

    def has_applied(self, role_id: str) -> bool:
        cur = self.conn.execute(
            "SELECT 1 FROM applications WHERE role_id = ? AND status = 'applied'",
            (role_id,),
        )
        return cur.fetchone() is not None

    def record_application(self, result: ApplicationResult) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO applications"
            " (role_id, status, detail, cover_letter, submitted_at) VALUES (?,?,?,?,?)",
            (
                result.role_id, result.status, result.detail,
                result.cover_letter, result.submitted_at,
            ),
        )
        self.conn.commit()

    def applications_since(self, since: datetime) -> int:
        cur = self.conn.execute(
            "SELECT COUNT(*) AS n FROM applications"
            " WHERE status = 'applied' AND submitted_at >= ?",
            (since.isoformat(timespec="seconds"),),
        )
        return int(cur.fetchone()["n"])

    def applications_today(self) -> int:
        midnight = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return self.applications_since(midnight)

    def history(self, limit: int = 50) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                "SELECT a.role_id, a.status, a.detail, a.submitted_at,"
                " r.title, r.company, r.url"
                " FROM applications a LEFT JOIN roles r ON r.id = a.role_id"
                " ORDER BY a.submitted_at DESC LIMIT ?",
                (limit,),
            )
        )

    def prune(self, older_than_days: int = 180) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=older_than_days)).isoformat()
        cur = self.conn.execute(
            "DELETE FROM roles WHERE last_seen < ? AND id NOT IN"
            " (SELECT role_id FROM applications)",
            (cutoff,),
        )
        self.conn.commit()
        return cur.rowcount
