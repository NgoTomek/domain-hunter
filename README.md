# domain-hunter

A CLI that generates cool-looking domain names, finds the ones nobody owns, prices them via the Porkbun API, flags hidden "premium" traps, and ranks the genuine cheap gems.

**Status:** working v0.1. See [`PLAN.md`](./PLAN.md) for the full design.

## How it works

Generating names is free; checking availability and price is slow and rate-limited. So the tool is a funnel:

```
generate flood → score "coolness" cheaply → DNS/RDAP/WHOIS cull the taken ones (free)
   → assign TLD base price → rank → (optional) verify the top gems via Porkbun
```

Two-tier pricing, because Porkbun's per-domain `checkDomain` is limited to **1 request / 10 seconds**:

- **Bulk:** availability via RDAP/WHOIS (free, fast) + the TLD base price from Porkbun's unlimited `pricing/get`. Prices show with a leading `~` (base rate, premium not yet confirmed).
- **Verify:** `checkDomain` on just the top N gems → authoritative price + **premium flag**. These show without the `~`. This is what catches the "available but secretly $174" traps.

## Setup

```bash
cd domain-hunter
uv venv && uv pip install -e .        # or: python -m venv .venv && .venv/bin/pip install -e .
cp .env.example .env                  # add your Porkbun API key + secret
source .venv/bin/activate             # then the `dh` command is on PATH
```

Get a free API key/secret at Porkbun → Account → API Access. Put them in `.env`:

```
PORKBUN_API_KEY=pk1_...
PORKBUN_SECRET_KEY=sk1_...
```

## Usage

`dh` is the command this installs (short for *domain hunter*).

```bash
dh hunt                       # generate → find available → price → rank (base prices, fast)
dh hunt --verify 5            # also premium-verify the top 5 gems (~10s each)
dh hunt --tld .com,.io --budget 20 --strategy brandable,leet
dh hunt --limit 270 --export exports/gems.csv

dh loop                       # hunt over and over until Ctrl-C, piling up gems (great overnight)
dh loop --hours 8             # run ~8 hours, then stop on its own

dh check velk.io plate.dev    # authoritative availability + price for specific domains
dh check zuno                 # bare label → expands across configured TLDs
dh score velkana              # show the coolness breakdown for one name
dh gems                       # browse gems saved from past hunts (one row per name)

dh watch add velk.io          # save a domain; `dh watch run` re-checks the list
```

### Run it overnight

`dh loop` repeats hunts until you stop it (or for `--hours N`). Because each round samples *different* names, the gem pile keeps growing instead of re-checking the same ones:

```bash
dh loop --hours 8                          # leave it running; Ctrl-C anytime
dh loop --strategy words,seeds,brandable   # brandier names (skips the leet vowel-dropper)
dh gems --max-price 5                       # next morning: browse the cheap finds
```

Each round prints a one-line tally and everything lands in `dh gems`. The defaults (4s between rounds, 12 concurrent lookups) are deliberately polite to the RDAP/WHOIS servers — leave them be for long runs.

`hunt` knobs (also in `config.toml`): `--limit` total domains checked (÷ TLD count = distinct names explored), `--budget`, `--tld`, `--strategy` (`brandable,words,seeds,leet`), `--verify N`, `--export *.csv|*.json`, `--show`.

## Name strategies

- **brandable** — invented pronounceable words (`velk`, `mira`), biased by a char-level Markov model trained on real words.
- **words** — adjective+noun / noun+noun compounds (`lunarfox`); no bare dictionary words (those are all taken).
- **seeds** — mutations of your `seeds` from `config.toml` (affixes + portmanteau blends).
- **leet** — vowel-drops and letter swaps of real words (`flickr` style); highest unregistered hit-rate.

## Notes & caveats

- **TLD coverage (live-verified):** `.com .app .dev .xyz .ai` use RDAP; `.io .co .sh .me` fall through to WHOIS (port 43). Availability is authoritative either way; a TLD with no RDAP *and* an unreachable WHOIS host shows `unknown`.
- **Renewal traps:** the `renew` column surfaces costs that dwarf the first year (e.g. `.io` $28 reg → **$52 renew**).
- **`~` prices are TLD base rates** — a domain can be a registry *premium* (much pricier) until you `--verify` it. `dh check` always verifies.
- **Every hunt auto-saves its available finds** to a `gems` table in `data/domains.db` (deduped, accumulates across runs) — browse anytime with `dh gems` (one row per name; `--all-tlds` to expand, `--max-price` / `--min-cool` / `--tld` to filter, `--export` to dump, `--clear` to reset). Availability + verified prices also cache there (7-day TTL), so re-runs are fast and resumable.
- Uses only the official Porkbun API + public RDAP/WHOIS — no scraping.

## Development

```bash
pip install -e ".[dev]"
pytest -q                              # offline unit tests: scorer, parser, ranking, generators
python -m compileall -q src/domainhunter
```

CI (GitHub Actions) runs the suite on every push across Python 3.11–3.13. Tests need no network or API keys.
