#!/usr/bin/env python3
"""Merge a hunt export (run.json) into the persistent ledger: data/gems.json + GEMS.md.

Run in CI after `dh hunt --export run.json`. Accumulates available finds across
scheduled runs, deduped by domain (prefer verified, then higher score), and
regenerates a human-readable GEMS.md leaderboard (one row per name).
"""
from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "data" / "gems.json"
MD = ROOT / "GEMS.md"


def _load(path: Path) -> list[dict]:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return []
    return []


def _verified(r: dict) -> bool:
    return r.get("source") in ("porkbun", "cache")


def _cell(value, verified: bool) -> str:
    if value is None:
        return "—"
    return ("" if verified else "~") + f"${value:,.2f}"


def main() -> None:
    run_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "run.json"
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    new = [r for r in _load(run_path) if r.get("status") in ("available", "premium")]
    ledger: dict[str, dict] = {r["domain"]: r for r in _load(LEDGER)}

    for r in new:
        r.setdefault("found_at", now)
        old = ledger.get(r["domain"])
        if old is None or (_verified(r), r.get("score", 0)) >= (_verified(old), old.get("score", 0)):
            if old is not None:
                r["found_at"] = old.get("found_at", now)  # keep first-found date
            ledger[r["domain"]] = r

    rows = sorted(ledger.values(), key=lambda r: r.get("score", 0), reverse=True)
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(rows, indent=2))

    # GEMS.md — available only, one row per name (best/cheapest TLD).
    available = [r for r in rows if r.get("status") == "available"]
    seen: set[str] = set()
    unique = []
    for r in available:
        if r.get("name") in seen:
            continue
        seen.add(r.get("name"))
        unique.append(r)

    lines = [
        "# Gems found by domain-hunter",
        "",
        f"_Updated {now} · {len(unique)} unique available names · {len(rows)} total finds — "
        "auto-updated by GitHub Actions._",
        "",
        "`~` = TLD base rate (premium unverified). **Availability can change — always re-check before buying.**",
        "",
        "| # | domain | cool | price | renew | status |",
        "|--:|--------|-----:|------:|------:|--------|",
    ]
    for i, r in enumerate(unique[:100], 1):
        v = _verified(r)
        lines.append(
            f"| {i} | `{r['domain']}` | {r.get('coolness', 0):.2f} | "
            f"{_cell(r.get('price'), v)} | {_cell(r.get('renewal'), v)} | {r.get('status')} |"
        )
    MD.write_text("\n".join(lines) + "\n")
    print(f"ledger: {len(rows)} total finds, {len(unique)} unique available names")


if __name__ == "__main__":
    main()
