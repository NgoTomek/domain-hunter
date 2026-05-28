#!/usr/bin/env python3
"""Merge a hunt export (run.json) into the persistent ledger.

Outputs (committed to gems-feed by CI):
- data/gems.json   — full ledger, deduped by domain (prefer verified, then score)
- GEMS.md          — coolest names first (price ignored), each shown at its cheapest TLD
- GEMS_CHEAP.md    — same but only names whose cheapest TLD is <= $12/yr
"""
from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "data" / "gems.json"
MD = ROOT / "GEMS.md"
MD_CHEAP = ROOT / "GEMS_CHEAP.md"
CHEAP_MAX = 12.0
SHOW = 1000  # rows rendered in each .md (full set lives in data/gems.json)


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


def _cheapest_by_name(rows: list[dict]) -> list[dict]:
    """One row per name: the cheapest available TLD for that name."""
    best: dict[str, dict] = {}
    for r in rows:
        n = r.get("name")
        if n not in best or (r.get("price") or 9e9) < (best[n].get("price") or 9e9):
            best[n] = r
    return list(best.values())


def _write_md(path: Path, rows: list[dict], heading: str, blurb: str, now: str) -> None:
    lines = [
        f"# {heading}",
        "",
        f"_Updated {now} · {len(rows):,} names (showing top {min(len(rows), SHOW):,}) "
        "— auto-updated by GitHub Actions._",
        "",
        blurb,
        "",
        "| # | domain | cool | price | renew | status |",
        "|--:|--------|-----:|------:|------:|--------|",
    ]
    for i, r in enumerate(rows[:SHOW], 1):
        v = _verified(r)
        lines.append(
            f"| {i} | `{r['domain']}` | {r.get('coolness', 0):.2f} | "
            f"{_cell(r.get('price'), v)} | {_cell(r.get('renewal'), v)} | {r.get('status')} |"
        )
    path.write_text("\n".join(lines) + "\n")


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
                r["found_at"] = old.get("found_at", now)
            ledger[r["domain"]] = r

    rows = sorted(ledger.values(), key=lambda r: r.get("score", 0), reverse=True)
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(rows, indent=2))

    # Coolest name first; show each name's cheapest TLD; price tie-breaks.
    uniq = _cheapest_by_name([r for r in ledger.values() if r.get("status") == "available"])
    uniq.sort(key=lambda r: (-(r.get("coolness") or 0), r.get("price") or 9e9))
    cheap = [r for r in uniq if (r.get("price") or 9e9) <= CHEAP_MAX]

    note = "`~` = TLD base rate (premium unverified). **Availability can change — always re-check before buying.**"
    _write_md(MD, uniq, "Gems found by domain-hunter", note, now)
    _write_md(MD_CHEAP, cheap, f"Cheap gems (≤ ${CHEAP_MAX:.0f}/yr)", note, now)
    print(f"ledger: {len(rows)} finds · {len(uniq)} names · {len(cheap)} cheap")


if __name__ == "__main__":
    main()
