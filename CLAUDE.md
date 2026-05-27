# Domain Hunter — cool, cheap, unowned domain finder

> A Python CLI (`dh`) that generates brandable names, finds the ones nobody owns (RDAP/WHOIS), prices them via Porkbun, flags hidden registry-premium traps, and ranks the genuine cheap gems.

This file is read into every Claude Code session. Keep it tight; deeper detail lives in `PLAN.md` and `README.md`.

## Docs
| Topic | File |
|-------|------|
| Full design, funnel, build findings | `PLAN.md` |
| Setup + usage + caveats | `README.md` |

## What it is
The pipeline is a funnel — each stage narrower and more expensive than the last:
`generate flood → score "coolness" (cheap) → DNS/RDAP/WHOIS cull taken (free) → TLD base price → rank → optional Porkbun checkDomain verify of the top gems`.

## Stack
- Python 3.11+ (built/tested on 3.14), packaged with **hatchling**, installed editable into `.venv`. Entry point: `dh = domainhunter.cli:app`.
- `httpx[http2]` (async RDAP + Porkbun), `dnspython` (async DNS), `typer` + `rich` (CLI), `pydantic-settings` (config from `.env`), stdlib `sqlite3` (cache) + `asyncio` (WHOIS over port 43).
- Porkbun API for pricing + premium detection. IANA RDAP bootstrap for availability. **No scraping.**

## Project structure
- `src/domainhunter/` — `generate/` (brandable, words, seeds, leet, markov), `availability/` (dns, rdap, whois), `pricing/` (porkbun). Top level: `pipeline.py` (orchestration), `cli.py`, `score.py`, `rank.py`, `store.py`, `config.py`, `models.py`, `wordlists.py`.
- `data/wordlists/` — curated adjectives + nouns (the Markov corpus also samples `/usr/share/dict/words`). `data/domains.db` and `data/rdap_bootstrap.json` are gitignored caches.
- `config.toml` — tlds, budget, check_limit, strategies, seeds, and `[generation]`/`[scoring]`/`[network]` knobs.

## Architecture decisions / gotchas (don't relearn the hard way)
1. **Porkbun `checkDomain` is rate-limited to 1 request / 10s** (returns HTTP 400 when exceeded). NEVER price bulk candidates with it. Bulk = RDAP/WHOIS availability + the *unlimited* `pricing/get` base price (rendered with a leading `~`). `checkDomain` is reserved for `--verify N` of the top gems and is serialized ≥10.5s apart inside `Porkbun.check_domain`.
2. **Premium detection is the headline feature.** Base price ≠ real price for registry premiums (verified live: `plate.dev` base ~$11, real **$174**). Only `checkDomain` reveals premium; verified rows drop the `~`.
3. **DNS is a NEGATIVE filter only.** Resolves → taken. Absence of DNS ≠ available — always confirm with RDAP/WHOIS.
4. **RDAP coverage (verified):** `.com .app .dev .xyz .ai` have RDAP; `.io .co .sh .me` fall back to WHOIS. Bootstrap cached 30 days.
5. **Coolness = weighted geometric mean** of structure (length / consonant-clusters / clean-chars / vowel-balance) and Markov pronounceability, so unpronounceable strings tank. The `words` generator emits only **compounds** — single dictionary words are all taken and just waste the check budget.
6. **Everything caches to SQLite (7-day TTL):** availability in `checks`, authoritative prices in `prices`. Every hunt also auto-saves available/premium finds to the `gems` table (deduped; `dh gems` browses + filters them). Re-runs are fast + resumable. The generator RNG is intentionally **unseeded** — fresh candidate names every hunt.
7. **Trust boundary:** official Porkbun API + public RDAP/WHOIS only.

## Commands
```bash
uv pip install -e ".[dev]"          # dev install (+ pytest)
dh hunt [--verify N] [--tld .com,.io] [--budget 20] [--strategy brandable,leet] [--limit 270] [--export f.csv]
dh gems [--all] [--max-price 15] [--tld .com] [--export f.csv] [--clear]   # browse saved finds
dh check <domain|label> ...         # authoritative (always verifies)
dh score <name>                     # coolness breakdown
dh watch add|list|rm|run            # save + re-check favorites
pytest -q                           # offline unit tests · python -m compileall -q src/domainhunter
```

## What NOT to do
- **Never commit `.env`** (Porkbun API key + secret) — it's gitignored; keep it that way.
- Don't price bulk candidates with `checkDomain` (the 1/10s limit).
- Don't conclude "available" from DNS alone.
- Don't add registrar web-scraping — official API + public RDAP/WHOIS only.
