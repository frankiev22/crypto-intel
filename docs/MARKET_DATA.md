# Market data the pipeline publishes — for the site

**2026-09-18.** Everything here is a real file in `data/`, written by the
collector on every full pass and committed like the rest of `data/`. ⛔ **If a
panel has no file behind it in this list, it has no data. Do not build it as a
placeholder.**

Written by `market.py` (movers, volume, trending, clusters, majors) and
`journal.record_outcome()` / `crossingdepth.py` (crossing depth). Tested by
`test_market.py` and `test_crossingdepth.py`, on the files as written.

## How fresh is it

Every file carries `built_at` (ISO), `built_ts` (epoch) and `origin`
(`scheduled` = cron fired on its own, `dispatch` = a human pressed run,
`manual` = a hand run on Frank's machine). ⚠️ **"Every pass" is ~7 times a
day, not hourly** - GitHub delivers 29% of the requested cadence
(`docs/BACKLOG.md` C10). Show the age from `built_ts`. A 3-hour-old "1h gainers"
list is a 3-hour-old list and should say so.

The first files in `data/market/` are from a `manual` run at 2026-09-18 ~22:55Z.

## `data/market/index.json` — read this first

| field | meaning |
|---|---|
| `files.{name}.status` / `.rows` | `ok` / `empty` / `unreadable`, and the row count **read back from disk** |
| `sources.{label}` | per upstream: `status` ok/empty/error, `http`, `n`, `error`. ⭐ **An empty panel whose source is `error` is a failure; an empty panel whose source is `ok` is a quiet market.** Show which. |
| `universe_n` | how many tokens the lists were drawn from (~280). Not a census of Solana. |
| `round_trips_checked` | how many $100 round-trip quotes ran this snapshot |
| `top_gainers_24h_in_journal` | e.g. `0/25` - how many of the top 24h gainers our launch scanner had ever seen. The scope error, as a number. |
| `caveats` | the text of every caveat, keyed. Render the ones for a panel on that panel. |

## `movers.json`

`lists` holds `gainers_1h`, `gainers_6h`, `gainers_24h` (25 each) and
`losers_1h`, `losers_6h`, `losers_24h` (10 each). Ordered by the move for that
horizon - **size of a move that already happened, not a quality ranking.**
`sol_change_pct` is SOL's own move per horizon. `exclusions` counts, per list,
what was dropped: `under_liquidity_floor` (reported liquidity < $1,000, the
existing `paper.MIN_EXIT_DEPTH`), `liquidity_unknown`, `unknown_value`,
`wrong_sign`.

**Token row** (same shape in `volume.json`):

| field | notes |
|---|---|
| `token` | ⛔ **the contract address. Key on this, never on `symbol`.** |
| `symbol`, `name` | raw, display only. `symbol_flags.bidi` / `.mixed_script` mean it renders as something it is not - see `docs/SYMBOL_ATTACKS.md`; apply the same treatment as `dashboard.safe_sym()` |
| `change_pct` | `5m`, `1h`, `6h`, `24h`, percent |
| `vs_sol_pp` | the move minus SOL's move, **percentage points**, per horizon |
| `volume_usd`, `traders` | `1h`, `24h` |
| `organic_share` | Jupiter's organic ÷ total volume. ⛔ **Not a wash signal** - SOL itself runs ~2%. Show it only beside `volume.json`'s `organic_share_baseline_sol`, if at all |
| `liquidity_usd_reported` | Jupiter's number. **Not realizable depth.** |
| `mcap_usd`, `fdv_usd`, `holders`, `age_h`, `launchpad`, `tags`, `class` | `class` is `base` (SOL/stables/LSTs), `stock`, or `token`, from Jupiter's own tags |
| `audit` | `mint_authority_disabled`, `freeze_authority_disabled`, `top_holders_pct`, `dev_balance_pct` - Jupiter's |
| `organic_score`, `organic_label` | Jupiter's |
| `lists` | which Jupiter rankings the token came from |
| `in_journal` | `true`/`false` - did our scanner ever see it. `null` = journal unreadable |
| `round_trip` | `{verdict, rt_cost_pct, usd_back, probe_usd, price_impact_pct, ts}` - what $100 in and straight back out would return, **quoted, nothing executed**. Verdicts: `TRADEABLE` <10%, `COSTLY` 10-50%, `TOTAL_LOSS` >50%, `NO_SELL_ROUTE`, `NO_BUY_ROUTE` |
| `round_trip_status` | `checked` / `not checked` / `not checked: time budget spent` / `check failed: …`. ⛔ **Show "not checked" as not checked. Never render a missing verdict as a pass.** |

⛔ Every numeric field can be `null`. **Unknown renders as "unknown", never 0
or blank** (standing rule 5).

## `volume.json`

`leaders_24h` - top 25 by 24h volume, everything included (it is SOL, USDC,
USDT at the top every time). `leaders_24h_tokens` - the same ranking with
`class` `base` and `stock` removed; **this is the useful list.** Each row adds
`turnover_24h` (volume ÷ reported liquidity, descriptive, no threshold).
`organic_share_baseline_sol` is SOL's own organic share, the only honest
reference for `organic_share`. ⛔ **Nothing in this file detects wash trading.
Do not label any row as wash or clean.**

## `trending.json`

| key | source | notes |
|---|---|---|
| `jupiter.{1h,6h,24h}` | Jupiter toptrending | `rank`, `token`, `symbol`, `change_pct`, `in_journal` |
| `geckoterminal.{1h,6h,24h}` | GeckoTerminal trending pools | pool-level: `token` (base CA), `pool`, `dex`, `change_pct` (m5/h1/h6/h24), `volume_usd_24h`, `reserve_usd_reported`, `buyers_24h`, `sellers_24h` |
| `boosts_top`, `boosts_latest` | Dexscreener | ⛔ **PAID promotion.** Label it that way. `boost_amount`, `boost_total` |
| `profiles_latest` | Dexscreener | a paid token profile was published |
| `community_takeovers` | Dexscreener | `claim_date` |

Solana only - other chains are dropped.

## `clusters.json`

`ours` - narrative clusters from **our own journal**, last 24h (`clusters.py`,
until today reachable only through `dashboard.html`). Each: `root`, `size`,
`variants` (distinct names), `span_h`, `swarm` (≥10 contracts on ≤2 names - a
mint flood, not a story), `funded_by_reported_liq`, `members` (≤30, each with
`token`, `symbol`, `symbol_flags`, `first_seen`, `pair`), `members_truncated`.
⚠️ **Our journal sees ~1.3% of launches, so a cluster is a floor on a wave, not
its size** - and on the first snapshot the #1 24h gainer's narrative (TIGRINO,
19 contracts) was in `ours` while the coin that actually ran was not.

`dexscreener_metas` - Dexscreener's own narrative categories, **all chains**:
`name`, `slug`, `token_count`, `mcap_usd`, `mcap_change_pct` (m5/h1/h6/h24),
`volume_usd`, `liquidity_usd_reported`.

## `majors.json` — the tape

`sol` (`price_usd`, `change_24h_pct`, `volume_24h_usd`, `mcap_usd`, and
`change_pct` 5m/1h/6h/24h from Jupiter), `btc`, `eth`, `crypto_market`
(`total_volume_24h_usd`, `total_mcap_usd`, `mcap_change_24h_pct`),
`solana_dex` (`volume_24h_usd`, `volume_prev_24h_usd`, `volume_7d_usd`,
`change_1d_pct`, from DefiLlama). This is what every row's `vs_sol_pp` is read
against.

## `history/YYYY-MM.jsonl`

Append-only. One line per list per snapshot: `ts`, `kind`, `cols`, `rows` (arrays
in `cols` order). For "what was running at 14:00", not for the live page.

## Crossing depth — `exit_depth_at_crossing` on mcap and multiple tiers

The site's item 1. Two sources, same field names:

- **Forward, from 2026-09-18:** every new `mcap_*` and `realizable_*` row in
  `data/milestones/YYYY-MM.jsonl` carries `exit_depth_at_crossing`,
  `depth_unmeasured_at_crossing`, `realizable_at_crossing`,
  `exit_pair_at_crossing`, `horizon_h`, `outcome_checked_ts`. **Measured in the
  same call that claimed the crossing** - no join, no staleness.
- **History:** `data/milestones/depth_at_crossing.jsonl`, one row per
  `(token, milestone)`, same fields plus `crossed_ts`, `delta_s` (0-2s; one at
  5s) and `provenance: "recovered"`. **1,097 crossings.** Every live crossing
  from 2026-09-09 onward is in it. The 643 from 09-02 to 09-08 are not, because
  they were never claimed at a real measurement (the `mcap=None` bug) - show
  those as unverifiable, not as missing data.

⛔ `exit_depth_at_crossing: null` means the check could not read depth. It is
not zero, and it is not a pass. `depth_unmeasured_at_crossing: true` means the
quote side was never seen and reported `liq` stood in - treat as unverified.
