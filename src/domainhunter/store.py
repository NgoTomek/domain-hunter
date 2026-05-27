from __future__ import annotations

import json
import sqlite3
import time

from .config import ROOT

DB_PATH = ROOT / "data" / "domains.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS checks (
    domain TEXT PRIMARY KEY,
    available INTEGER,
    source TEXT,
    checked_at REAL
);
CREATE TABLE IF NOT EXISTS prices (
    domain TEXT PRIMARY KEY,
    available INTEGER,
    price REAL,
    renewal REAL,
    premium INTEGER,
    currency TEXT,
    raw TEXT,
    checked_at REAL
);
CREATE TABLE IF NOT EXISTS watchlist (
    domain TEXT PRIMARY KEY,
    added_at REAL,
    last_status TEXT
);
CREATE TABLE IF NOT EXISTS gems (
    domain TEXT PRIMARY KEY,
    name TEXT,
    tld TEXT,
    coolness REAL,
    price REAL,
    renewal REAL,
    premium INTEGER,
    status TEXT,
    strategy TEXT,
    source TEXT,
    score REAL,
    found_at REAL
);
"""


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def _fresh(row: sqlite3.Row | None, ttl_days: int) -> dict | None:
    if not row:
        return None
    if time.time() - row["checked_at"] > ttl_days * 86400:
        return None
    return dict(row)


def get_availability(con, domain: str, ttl_days: int) -> dict | None:
    row = con.execute("SELECT * FROM checks WHERE domain=?", (domain,)).fetchone()
    return _fresh(row, ttl_days)


def save_availability(con, domain: str, available: bool | None, source: str) -> None:
    con.execute(
        "INSERT OR REPLACE INTO checks(domain, available, source, checked_at) VALUES(?,?,?,?)",
        (domain, None if available is None else int(available), source, time.time()),
    )
    con.commit()


def get_price(con, domain: str, ttl_days: int) -> dict | None:
    row = con.execute("SELECT * FROM prices WHERE domain=?", (domain,)).fetchone()
    return _fresh(row, ttl_days)


def save_price(con, domain, available, price, renewal, premium, currency, raw) -> None:
    con.execute(
        """INSERT OR REPLACE INTO prices
           (domain, available, price, renewal, premium, currency, raw, checked_at)
           VALUES(?,?,?,?,?,?,?,?)""",
        (
            domain,
            None if available is None else int(available),
            price,
            renewal,
            1 if premium else 0,
            currency,
            json.dumps(raw)[:4000],
            time.time(),
        ),
    )
    con.commit()


def watch_add(con, domain: str) -> None:
    con.execute(
        "INSERT OR IGNORE INTO watchlist(domain, added_at, last_status) VALUES(?,?,?)",
        (domain, time.time(), "new"),
    )
    con.commit()


def watch_list(con) -> list[str]:
    return [r["domain"] for r in con.execute("SELECT domain FROM watchlist ORDER BY added_at")]


def watch_remove(con, domain: str) -> None:
    con.execute("DELETE FROM watchlist WHERE domain=?", (domain,))
    con.commit()


def save_gems(con, results) -> int:
    """Persist every available/premium find so good names survive across runs."""
    rows = [
        (r.domain, r.name, r.tld, r.coolness, r.price, r.renewal,
         1 if r.premium else 0, r.status, r.strategy, r.source, r.score, time.time())
        for r in results if r.status in ("available", "premium")
    ]
    if not rows:
        return 0
    con.executemany(
        """INSERT OR REPLACE INTO gems
           (domain, name, tld, coolness, price, renewal, premium, status, strategy, source, score, found_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
        rows,
    )
    con.commit()
    return len(rows)


def list_gems(con, available_only: bool = True, max_price=None, tld=None,
              limit: int = 50, unique: bool = False, min_cool=None) -> list[dict]:
    query = "SELECT * FROM gems"
    conds: list[str] = []
    params: list = []
    if available_only:
        conds.append("status = 'available'")
    if max_price is not None:
        conds.append("(price IS NULL OR price <= ?)")
        params.append(max_price)
    if tld:
        conds.append("tld = ?")
        params.append(tld if tld.startswith(".") else "." + tld)
    if min_cool is not None:
        conds.append("coolness >= ?")
        params.append(min_cool)
    if conds:
        query += " WHERE " + " AND ".join(conds)
    query += " ORDER BY score DESC"
    rows = [dict(r) for r in con.execute(query, params)]
    if unique:  # collapse to one row per name (best score = cheapest available TLD)
        seen: set[str] = set()
        deduped = []
        for r in rows:
            if r["name"] in seen:
                continue
            seen.add(r["name"])
            deduped.append(r)
        rows = deduped
    return rows[:limit]


def count_gems(con, available_only: bool = True, unique: bool = False) -> int:
    col = "DISTINCT name" if unique else "*"
    query = f"SELECT COUNT({col}) AS c FROM gems"
    if available_only:
        query += " WHERE status = 'available'"
    return con.execute(query).fetchone()["c"]


def clear_gems(con) -> None:
    con.execute("DELETE FROM gems")
    con.commit()
