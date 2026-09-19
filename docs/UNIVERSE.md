# The tracked universe: sizing, cost, source and the gate

**2026-09-19 (UTC).** Frank, 2026-09-18:

> *"I need all coins over $1M market cap tracked and the top trending ones
> always visible which can lead to determining the narratives"*

That is a **ledger, not a detector**. Everything this project has built so far
fires once on an event, such as a launch, a crossing or a graduation, and then
forgets the token. Here a token that qualifies enters once and **is never
removed**. A coin that crossed $1M three weeks ago and is running today is on
the page because it never left.

Section 3 was written before the first seed run started (00:33Z) and committed
before that run returned its first gate verdict; the commit's author date is the
evidence. It must not be moved to fit what the universe turns out to hold.

---

## 1. How big is it — measured 2026-09-19 ~00:10Z

| source | tokens ≥ $1M | notes |
|---|---:|---|
| Jupiter `tokens/v2/tag?query=verified` | **668** | one call: 3,476 verified tokens, 5.2 MB, 3s |
| CoinGecko `coins/markets?category=solana-ecosystem` | **784** | 4 pages, plus the `coins/list?include_platform=true` address map |
| overlap of the two | 420 | |
| our own live $1M/$5M crossings since 09-02, still ≥ $1M | **15 of 271** | 94% of what we saw cross $1M is under it now |
| **union** | **1,035** | |

⛔ **The listings miss the coins that are actually running.** In the 23:49Z
market snapshot, **11 of the 42 tokens over $1M (26%) were in neither list**.
They included TIGRINO, PAID ($27.5M), nub, CYPHERCAT and BRRR: fresh launchpad
coins that are not Jupiter-verified and not on CoinGecko. **Those are the coins
Frank is asking about.** Discovery therefore has to include the trending and
traded lists on every pass, our own $1M crossings, and every graduation
(§4, BACKLOG C14). The 1,035 is the listed floor of the universe, not its size.

⚠️ **Under the rule as written (§3) the first live pass found 863, not 1,035.**
For ~170 tokens CoinGecko's market cap is ≥ $1M and Jupiter's is not. The two
disagree on circulating supply. The rule takes Jupiter's number wherever
Jupiter has one, and it was fixed before this was seen, so it stands.
CoinGecko is re-read every 6 hours; a token that Jupiter later puts over $1M
enters then.

### The liquidity gate, sampled

I took a seeded random sample of **80 of the 1,035** tokens and ran a $100
round trip through `chainfields.round_trip()` on each. These are quotes only;
nothing was executed. The sample took 273s.

| verdict | n | Jupiter-reported liquidity, median | 24h volume, median |
|---|---:|---:|---:|
| **TRADEABLE** (< 10% lost) | **52** | $325,601 (min $2,198) | $72,571 |
| COSTLY (10–50%) | 4 | $295 | $22 |
| TOTAL_LOSS (> 50%) | 7 | $19 | $0 |
| NO_SELL_ROUTE | 2 | $12 | $0 |
| NO_BUY_ROUTE | 15 | $0 | $0 |

**TRADEABLE: 52 of 80 = 65.0%, Wilson 95% [54.1%, 74.5%]. That puts roughly
673 of the 1,035 tokens as sellable, with an interval of 560 to 771.** The
median TRADEABLE token loses 0.57% on a $100 round trip.

- By source: **Jupiter-verified 44/59 = 75%**; CoinGecko-only or ours
  **8/21 = 38%**. CoinGecko still earns its place, adding roughly 140 sellable
  tokens that Jupiter's verified list lacks.
- ⛔ **13 of the 15 tokens with no buy route at all carry Jupiter's own
  "verified" tag.** Verified does not mean sellable. A $1M on a listing is not
  $1M that anyone can exit. About a third of the naive universe is exactly
  what Frank said would make it worse than no universe. **The gate is not
  optional.**
- ⭐ **One result I did not expect.** On this sample, Jupiter's *reported*
  liquidity separated the verdicts perfectly: every TRADEABLE token was at or
  above **$2,198** and every other token at or below **$650**. ⛔ **It is not
  used as a gate.** I saw the data before choosing. The 781x overstatement was
  measured on Dexscreener's field on *new launches*, which is where it is
  attacked, and n=80 of established tokens says nothing about that population.
  It is used only to **order** the gate queue, so that likely passes are quoted
  first. It gets re-measured at n ≥ 300 from the gate's own output. If it holds
  there, a pre-filter can be pre-committed then, and not before.

---

## 2. What was wrong with what we had

- `watchlist.py` tracks the $45k–$69k approach band and drops a token once it
  graduates or leaves the band.
- `milestones.py` claims a crossing once and never looks again.
- `market.py` sees about 280 tokens a pass, from lists that rotate hourly.

**None of them answers "what is every real $1M coin doing right now".**

⚠️ **Not to be confused with `PRECOMMIT_universe_v1.md` (2026-09-10)**, which
defines the *launch-side* bands, graduated and approaching, for the old
dashboard. It is a different population and does not conflict with this file.
**Its own pre-committed size bar can now be tested:** it called the band
*"useless as a dashboard above ~500"* new contracts a day. The graduation
ledger's seed measured **944 graduations in 21.0h (~45 an hour, ~1,070 a day)**.
The graduated band therefore fails the bar it set for itself. The $1M
universe, which adds tens of tokens a day, is the second cut that file said
would be needed.

---

## 3. ⛔ Membership rule — PRE-COMMITTED before the first seed run

| state | rule |
|---|---|
| **candidate** | reported market cap **≥ $1,000,000**, taken from Jupiter's `mcap` (price × circulating supply), or from CoinGecko's `market_cap` where Jupiter has none, from any discovery source in §4 |
| **member** | a **$100 round trip returns `TRADEABLE`** (< 10% lost). The boundary is `chainfields.round_trip()`'s existing one (BACKLOG A1), **not fitted to the sample above** |
| **refused** | the admission round trip returned anything else. The token is **kept, with its verdict**, and retried after **48h** (after **6h** if it is trending), but **only while its market cap is still ≥ $1M** |

- ⛔ **A member is never removed.** Members are re-quoted on rotation. A failed
  re-check sets `gate.status = "failing"` with `failing_since`, and the token
  is shown as failing, never hidden. A member under $1M stays a member with
  `below_floor_since`.
- ⛔ **A check that could not run is not a verdict.** A timeout or exception
  leaves the state unchanged and records `gate.error`.
- Keyed on the **contract address**. Symbols are for display only and carry
  `symbol_flags` (bidi and mixed script).
- **Quotes only. Nothing is executed and no wallet exists.**
- `class` comes from Jupiter's own tags: `base` (SOL, stables, LSTs), `stock`,
  or `token`. All three are tracked, and narratives use `token` only.

### 3a. ⛔ What the gate does NOT verify: the market cap — found on the first seed, 2026-09-19

**Seed result (manual run, 00:33–01:29Z):** 903 candidates quoted, **680
admitted (75.3% [72.4, 78.0])**, 223 refused (NO_BUY_ROUTE 142, TOTAL_LOSS 53,
COSTLY 19, NO_SELL_ROUTE 9). The rate is higher than the sample's 65% because
the rule's Jupiter-first market cap drops most of the CoinGecko-only tail.

⛔ **And the gate admitted a wallet farm.** 30 members came from the graduation
ledger and share a ticker with another member: TDOF ×6, NTDA ×5, WOTF ×4, ECTF
×3, WSOS ×3, WOFI, USWR, VOFI, USDF ×2. Their profile:

- **graduated within the last day**;
- about **2,000 holders** each;
- the top 10 holders own a **median of 9.8%** (every other member: 34.8%);
- Jupiter's organic score is **0**;
- together they **claim $3.53B** of market cap, **$827M for one**, against pools
  holding around $640k of SOL;
- **5 of them are in the top 20 tokens by market cap**.

The supply is spread across a wallet farm and the pool holds almost none of
it. Price × supply is fiction, yet a $100 round trip still passes at 0.6%,
because the pool's SOL is real.

**So the gate does what Frank asked, verifying the liquidity at his size, and
it does not verify the market cap.** Nothing clean gates the market cap:

- Cap backing (below) overlaps: farm median 0.51% against real members' 1.85%,
  but the real members' 10th percentile is 0.087%.
- Organic score 0 is shared by 141 of 370 Jupiter-verified members.
- Any cut chosen now would be chosen after seeing this data.

**Therefore, from 2026-09-19, and not a gate:**

- Every member carries **`cap_backing_pct`**: the quote half of Jupiter-reported
  liquidity over the cap, i.e. what the pool could pay out if every holder sold.
- Every member also carries **`ticker_contracts`**: how many tracked contracts
  share its ticker (standing rule 2).
- Every cluster and theme carries **`mcap_backed_usd`**, `shared_ticker_n`,
  `from_graduation_ledger_n` and `median_top_holders_pct`.
- ⛔ **No page may show, sort or sum a market cap without its backing beside
  it.** The caveat is published in `narratives.json`.
- ⛔ **Decision for Frank** (CONSOLIDATION_PLAN §7g): exclude the farm signature
  from the universe, which needs a detector validated at n ≥ 30 per arm first,
  or keep showing it flagged. Until he decides, it is shown flagged, because
  hiding it would be choosing for him.

---

## 4. Which source, and what it costs

| job | source | cost per pass | why this one |
|---|---|---|---|
| discover the listed tail | Jupiter `tag?query=verified` | 1 call, 5.2 MB | carries full stats, so those ~670 are re-checked for free |
| | CoinGecko `coins/markets` (solana-ecosystem) | 4 calls, **every 6h** | ~140 sellable tokens Jupiter's list lacks. The address map (`coins/list`) is refetched only when an unknown id appears, at most once a day |
| discover the runners | Jupiter toptrending/toptraded/toporganicscore, GeckoTerminal trending, Dexscreener boosts | **0 extra** — the market stage already fetches them | the 26% the listings miss |
| | our own `mcap_1m`/`mcap_5m` claims, last 30 days | 0 calls (disk) | |
| | graduation ledger (C14), graduations of the last 72h | re-checked in the batch below | every pump.fun graduation, not the ~2% a pass happens to see |
| **re-check everything** | Jupiter `tokens/v2/search`, **100 mints per call** | ~11 calls for 1,035, ~12s | Dexscreener `tokens/v1` takes 30 per call and GeckoTerminal 30 with a 429 after ~6, so both need 3x the calls for less data: no holders, organic score or audit |
| **gate** | `chainfields.round_trip()` — 2 Jupiter quotes (1 when there is no buy route) | **measured 35 quotes/min**; a full gate of 1,035 ≈ **59 min** | the only realizable liquidity measure in the project |
| themes | Dexscreener `metas/meta/v1/{slug}` | 12 calls | Dexscreener's own categories, top pairs only |

**Excluded:**

- **Birdeye.** Its key dies after ~7 calls, and its paid tier is a signup,
  which is Frank's call alone.
- **Dexscreener as the enumerator.** It has no market-cap listing, and search
  caps at 30 results.

**Money: $0.** Every call is keyless on the runner.

### Cadence, and the honest constraint

- **On GitHub Actions, which delivers ~7 passes a day (C10):**
  - The whole universe is re-checked on every pass.
  - The gate spends at most **150s** of whatever the pass has left. That is
    ~40 round trips a pass, or ~280 a day.
  - The initial fill is **one seeded run (~60 min)**, recorded as `manual`.
  - After that, new candidates are admitted first and members rotate
    oldest-first. At ~700 members, each is re-verified every ~3 days.
- **The constraint is GitHub's cadence, not money.** On a **$4–6/mo always-on
  box** the universe could be re-checked every 5 minutes (11 calls) and fully
  re-gated every hour. That is the same box `programSubscribe` (C5) needs, and
  it is **Frank's call**.

---

## 5. Narratives: trending × the universe

Frank's point was that trending plus the tracked universe is what reveals a
narrative. The cluster finder used to run over **launches**, and ~99% of those
die (the coverage probe put our view of creates at 1.26%). It now also runs
over **the live universe**:

- **`trending_now`**: every token on Jupiter toptrending (1h/6h/24h),
  GeckoTerminal trending, and Dexscreener boosts (**PAID**, labelled as such).
  Each carries its universe status and gate verdict. It is always present in
  the file. ⭐ **`trending_age_s`** is how old the lists are, in seconds, on
  every build; `trending_stale` is true past **3h**, one missed ~2h pass.
  ⚠️ It was 6h until 2026-09-19, when the site read a list 1.75h old marked
  fresh beside a "just now" build time (my hand seed, reading the 23:47 run's
  file). Trending moves faster than any pass we run (standing rule 13), so the
  age is the honest label and the flag is only the alarm.
- ⭐ **Untracked rows are named.** Paid boosts and GeckoTerminal pools we do
  not track arrived with no symbol (13 of 13 paid rows on the site read
  "unknown"). One Jupiter search per 100 mints now fills `symbol`, `name`,
  `mcap_usd` and `cap_backing_pct`, so "not tracked" can show *why* (usually
  under $1M). `resolved_by: null` means Jupiter has never heard of it, and the
  fields stay null.
- **`name_clusters`**: members grouped by a shared root in symbol and name,
  using `clusters.roots()` including the CJK n-grams. Each cluster carries
  aggregate market cap, 24h volume, a market-cap-weighted 24h move, and how
  many members are trending right now. ⚠️ **The site does not show the
  cap-weighted move, and it is right not to:** weighted by caps that can be
  fiction, the farm's "fund" cluster read **+353%**.
- **`themes`**: Dexscreener's trending categories, intersected with the
  universe.

⛔ **Descriptive only.** Clusters are ordered by how many members are trending
now, then by volume. That is size and activity, and never a quality ranking.
Nothing here predicts.

---

## 6. Files (`data/universe/`)

| file | what |
|---|---|
| `members.json` | one entry per contract ever discovered: status, gate, latest snapshot, peak, floor state, trending marks |
| `events/YYYY-MM.jsonl` | append-only: every discovery, gate check and floor crossing |
| `history/YYYY-MM-DD.jsonl` | append-only: one line per pass holding price, market cap, liquidity, volume and gate for every member |
| `narratives.json` | `trending_now`, `name_clusters`, `themes` |
| `index.json` | manifest: counts, sources, gate throughput, what was deferred |

⛔ If `members.json` exists but cannot be read, the pass **refuses to write**.
A fresh file would silently drop every member, and nothing is ever deleted.
