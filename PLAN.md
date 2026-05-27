# Domain Hunter — Plan

> A CLI that **generates cool-looking names**, checks which ones **nobody owns**, **prices them via Porkbun**, flags **hidden premium traps**, and ranks the surviving gems. The query we own: *"short, brandable, available, genuinely cheap to register — show me the ones I'd actually want."*

## Decisions locked (from kickoff Q&A)

| Decision | Choice | Why it matters |
|----------|--------|----------------|
| Language | **Python** | Best ecosystem for DNS/RDAP/WHOIS + async HTTP + SQLite + pretty tables. It's a standalone CLI, not a web app. |
| Pricing + premium detection | **Porkbun API** (free key) | Only clean way to get *real per-domain prices* AND a *premium flag* — the "available but secretly $3,000" traps. |
| Name styles | **All four**: short brandables · real words & pairs · seed/theme · leet/vowel-drop | Maximize surface area; the scorer decides what's "cool". |
| TLDs | **Curated tech set**: `.com .io .co .app .dev .xyz .ai .sh .me` | Best balance of desirable + where unregistered gems hide. |

## The core insight that shapes everything

Generating names is free and instant. **Availability and price checks are the slow, rate-limited steps.** So the whole design is: *generate a flood, score them cheaply, and only spend network/API calls on the best candidates.* Every stage is a funnel that gets narrower and more expensive.

```
seeds + config
      │
      ▼
┌─────────────┐   cheap, in-process, millions/sec
│ 1 GENERATE  │   brandable · words · seeds · leet
└─────────────┘
      │  flood of candidate strings
      ▼
┌─────────────┐   cheap, in-process
│ 2 SCORE     │   "coolness" 0–1 → drop the bottom, keep top-K
└─────────────┘
      │  top-K names × N TLDs = candidate domains
      ▼
┌─────────────┐   free, fast, parallel — NEGATIVE filter only
│ 3 DNS       │   resolves? → definitely taken, drop it
└─────────────┘
      │  survivors
      ▼
┌─────────────┐   free, authoritative availability
│ 4 RDAP      │   404 = available · 200 = taken · (WHOIS fallback)
└─────────────┘
      │  available domains only
      ▼
┌─────────────┐   Porkbun, rate-limited — spend calls ONLY here
│ 5 PRICE     │   real price + premium flag + renewal
└─────────────┘
      │
      ▼
┌─────────────┐
│ 6 RANK +    │   coolness × cheapness × shortness − premium penalty
│   OUTPUT    │   rich table · CSV/JSON · SQLite · watchlist
└─────────────┘
```

Everything is cached in SQLite so re-runs are cheap and resumable.

---

## Stage-by-stage design

### 1. Generation (`generate/`)
Four pluggable generators, each yields candidate strings. All composable; output is deduped and capped before scoring.

- **`brandable.py`** — invented pronounceable words. Phonotactic patterns (`CVCV`, `CVCVC`, `CCVCV`, `VCVCV`, …) over weighted consonant/vowel sets, then biased toward real-sounding output by the Markov model below. Length 4–6. Optional trendy affixes.
- **`words.py`** — real dictionary words (bundled wordlists: common nouns, adjectives, a "cool words" set) + 2-word combos (adjective+noun, noun+noun → `lunarfox`, `driftbyte`). Pairs explode combinatorially, so we **sample + score-cap**, never materialize the full cartesian product.
- **`seeds.py`** — you supply seeds/roots/affixes in config; it mutates around them: affix attach (`-ly -ify -io -hub -labs neo- get- try- use-`), portmanteau blends (merge two seeds at an overlapping phoneme), vowel swaps.
- **`leet.py`** — vowel-drop (`flickr`, `grnd`) and letter-swaps (`i→y s→z c→k`) over real words. Highest unregistered hit-rate.
- **`markov.py`** — character bigram/trigram model trained on a bundled corpus of real words + known brand names. Returns a pronounceability log-likelihood used both to *bias* the brandable generator and as a *scoring* signal.

### 2. Coolness scoring (`score.py`)
Cheap, deterministic, 0–1. Drives both the pre-filter (drop the bottom before any network call) and final ranking. Starter formula (all weights tunable in config):

| Signal | Direction | Notes |
|--------|-----------|-------|
| Length | shorter better | sweet spot 3–7; steep penalty >10 |
| Pronounceability | higher better | Markov log-prob, normalized |
| Vowel/consonant balance | balanced better | penalize 3+ consonant clusters |
| Digits / hyphens | penalty | exempt in leet mode |
| Real-word / blend signal | bonus | contains or *is* a recognizable word |
| Syllable count | fewer better | proxy for memorability |
| Awkward clusters | penalty | `xqz`, `vkt`, … unless deliberately leet |

Worked example: `velk` → short (+), pronounceable (+), no digits (+), 1 syllable (+) → high score. `xq7labs` → long-ish, digit, awkward cluster → low score, never reaches the network.

### 3. DNS pre-check (`availability/dns.py`)
Async, highly parallel, **free**. Query NS/SOA/A. **Negative filter only:** if it resolves or has NS records → registered → drop. *No* records ≠ available (parked/registered-without-DNS domains exist), so we never conclude "available" from DNS — that's RDAP's job. This stage exists purely to cheaply delete the obviously-taken before we spend authoritative calls.

### 4. RDAP availability (`availability/rdap.py` + `whois.py`)
Authoritative, still free.
- Load IANA's RDAP bootstrap (`https://data.iana.org/rdap/dns.json`) → map TLD → RDAP base URL. Cache it.
- `GET {base}/domain/{name}` → **404 = available**, **200 = taken**, 429/503 → backoff + retry (honor `Retry-After`).
- **WHOIS fallback** (`whois.py`, port 43) for TLDs lacking RDAP. ⚠️ In our set, `.com .co .app .dev .xyz .me` have solid RDAP; **`.ai` and `.sh` may be WHOIS-only** and `.io` should be verified at build time. WHOIS servers rate-limit hard and return inconsistent text → parse defensively, throttle politely.

### 5. Pricing + premium detection (`pricing/porkbun.py`)
- **`POST /api/json/v3/pricing/get`** — *public, no auth.* Per-TLD base registration/renewal/transfer prices. Used to set per-TLD budget gates and as the baseline to detect premiums.
- **`POST /api/json/v3/domain/checkDomain/{domain}`** — *authed* (apikey + secretapikey in JSON body). Returns authoritative availability **+ real price + premium flag** for that *specific* domain. This is what catches the hidden traps.
- **Hidden-premium logic:** if `checkDomain` price ≫ the TLD base price (or the premium flag is set) → mark `premium`, heavily penalize or exclude. A "hidden gem" = available + non-premium + short + high coolness + under budget.
- **Politeness:** Porkbun rate-limits (verify the current per-second/per-domain limit in their docs at build time). Bounded concurrency + exponential backoff + honor 429. Because RDAP already culled the taken ones, Porkbun only ever sees a small, available set → we stay well under limits.

> **BUILD FINDING (verified against the live API):** `checkDomain` is limited to **1 request / 10 seconds** (it returns HTTP 400 when exceeded). Pricing every candidate this way is infeasible. So the shipped design is two-tier: bulk runs use RDAP/WHOIS for availability + the *unlimited* `pricing/get` table for the TLD base price (shown with a leading `~`), and `checkDomain` is reserved for premium-**verifying** the top N gems (serialized ≥10.5s apart). Confirmed live: `plate.dev` looked like a ~$11 base-price gem but `checkDomain` revealed a **$174 registry premium** — exactly the trap this catches. Also verified: `.com/.app/.dev/.xyz/.ai` have RDAP; `.io/.co/.sh/.me` need WHOIS.

> Note: `checkDomain` also returns availability, so for Porkbun-supported TLDs it can *confirm* what RDAP found. RDAP stays first because it's free and keeps Porkbun quota for pricing.

### 6. Ranking + output (`rank.py`, `cli.py`)
Final score = `coolness × cheapness × shortness − premium_penalty − unavailable`. Output:
- **rich** terminal table, sorted, color-coded (gem / ok / premium-trap / taken).
- **CSV / JSON** export.
- Everything persisted to **SQLite** for later querying.
- **Watchlist**: save favorites, re-check on a schedule, alert on drops/availability changes.

---

## Project structure

```
domain-hunter/
├── pyproject.toml              # deps below
├── README.md
├── PLAN.md                     # this file
├── .env.example                # PORKBUN_API_KEY / PORKBUN_SECRET_KEY
├── config.example.toml         # tlds, budget, strategies, seeds, limits, concurrency
├── data/
│   ├── wordlists/              # bundled nouns/adjectives/cool-words/brand corpus
│   └── domains.db              # SQLite cache (gitignored)
└── src/domainhunter/
    ├── cli.py                  # typer entrypoint
    ├── config.py               # pydantic-settings: TOML + .env
    ├── models.py               # Candidate, CheckResult, PriceResult, RankedDomain
    ├── pipeline.py             # orchestrates 1→6 with the funnel + caching
    ├── store.py                # SQLite cache layer
    ├── score.py                # coolness scoring
    ├── rank.py                 # final ranking
    ├── generate/{brandable,words,seeds,leet,markov}.py
    ├── availability/{dns,rdap,whois}.py
    └── pricing/porkbun.py
```

**Dependencies:** `httpx[http2]` (async HTTP), `dnspython` (async DNS), `typer` (CLI), `rich` (tables), `pydantic` + `pydantic-settings` (config/models), `tomli` (if <3.11). Optional: `wordfreq` for word frequency signal. Python 3.11+.

## CLI surface

```bash
hunt                          # full pipeline → ranked table (+ --export csv|json)
hunt --strategy brandable     # restrict generators; --tld .com,.io; --budget 20
check zuno.io velk.com        # availability + price for specific domains
score velkana                 # show the coolness breakdown for one name
watch add velk.com            # manage + re-check a watchlist
export --format json          # dump the SQLite cache
```

## SQLite schema (cache)

- `candidates(name, tld, coolness, strategy, generated_at)`
- `checks(domain PK, dns_status, rdap_status, available, source, checked_at)`
- `prices(domain PK, reg_price, renew_price, currency, premium BOOL, source, checked_at)`
- `watchlist(domain PK, added_at, last_status)`

TTL-based reuse (availability/price can change) → days, configurable. Interrupted runs resume from cache.

## Build phases (each is an independently runnable slice)

| Phase | Deliverable | How we verify it works |
|-------|-------------|------------------------|
| **0 Scaffold** | repo, `pyproject.toml`, config + `.env`, models, SQLite store, CLI skeleton | `hunt --help` runs |
| **1 Availability** | DNS + RDAP + WHOIS fallback + `check` cmd | `check google.com` → taken; `check <random>.com` → available |
| **2 Pricing** | Porkbun `pricing/get` + `checkDomain` + premium flag | `check` now shows real price + flags a known premium domain |
| **3 Generation + scoring** | the 4 generators + Markov + `score` cmd | `score` ranks `velk` ≫ `xq7zz`; generators emit plausible names |
| **4 Pipeline + ranking** | wire 1–6, `hunt` cmd, ranked table + export | end-to-end `hunt` returns real available, priced, ranked gems |
| **5 Polish** | watchlist, TTL tuning, rate-limit hardening, tests | re-runs hit cache; rate limits respected; tests green |

## Risks & gotchas

- **RDAP coverage gaps** (`.ai`, `.sh`, verify `.io`) → WHOIS fallback; WHOIS is rate-limited and messy → throttle + parse defensively.
- **DNS ≠ availability** — never claim "available" from DNS alone; RDAP/Porkbun is the source of truth.
- **Porkbun rate limits** — verify current numbers at build time; RDAP-first culling keeps us well under.
- **ccTLD quirks** — `.ai` often requires 2-year minimum + is pricey; `.io` pricing shifted; reflect real per-TLD cost in budget gates, not just base price.
- **Word-pair explosion** — sample + score-cap before any network call.
- **"Available" but unregisterable** — a domain can be RDAP-available yet not offered by Porkbun (or premium); cross-check before calling it a buy.
- **ToS / legality** — official Porkbun API + public RDAP/WHOIS = clean. We do **not** scrape registrar pages. Politeness (caching, backoff, concurrency caps) is both good citizenship and ban-avoidance.

## Prerequisites you'll need

1. **Porkbun account** → API Access → create an **API key + secret** (free). Some accounts need API access toggled on per-domain, but `pricing/get` and `checkDomain` work account-wide. Put them in `.env`.
2. Python 3.11+.

That's it — no paid services, no scraping.
