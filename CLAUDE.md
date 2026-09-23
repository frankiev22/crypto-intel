# crypto-intel

**Handoff file. Read this first, then the two or three `docs/` files your task
touches. Do not re-derive what is written here.**

Last updated 2026-09-22. ⚠️ **Keep this current. It is the handoff, not a
one-off** — if you change architecture, numbers, or blockers, update it in the
same session.

---

## What this is

A **filter and an explainer** for Solana memecoins. Frank trades his own picks in
**$100 clips**. The system's job is to **show him things he would otherwise
miss** and to **stop a class of loss**, then get out of the way. He makes the
call.

## ⛔ What this is NOT

**It does not predict winners. Five attempts have been built and retracted.**

The Marino result is why: perfect knowledge of graduation probability still
loses money, because price outruns probability. By the time a signal is
readable, it is priced. **Do not propose a scoring model that ranks tokens by
expected return.** `dashboard.py` enforces this in code — sections sort by
recency or size, never by anything readable as a quality ordering, and `score`
is never displayed.

⛔ **The 70-99 score band is DELETED from the v1 entry gate as of 2026-09-18.**
It refused a token graded **100** - the cleanest grade the scorer awards - with
"score 100 outside 70-99", on two intervals that overlap (4.55% [2.62, 7.78] vs
1.20% [0.64, 2.27]) measured on a population its own gate had hollowed out.
**It had been "fixed" once before and only the wording changed.** The band now
survives solely in `paper.qualifies_v1_historical()`, which explains the 409
frozen rows and defines RULE_V2's arms. ⭐ **`test_scoreband.py` fails if a score
term reappears in the branch of any entry gate**, checked at the AST level -
`ENTRY_GATES` there is the list of guarded function names, so a new entry gate
must be added to it.

**The exception, and it is narrow:** describing something that has **already**
happened is not predicting. The 1M tracker (`docs/TRACKER_SCOPING.md`) watches
completed crossings and explains them. Marino does not apply to description.
**It does apply to anything forward-looking**, including "will this run
further" — scope those separately and hold them to the measurement bar below.

---

## The numbers. Use these, do not recompute them casually

| figure | value | source |
|---|---|---|
| graduation base rate, published | **0.198%** [0.189, 0.208], n=832,941 | Kamat, arXiv:2607.02823 |
| graduation base rate, ours | **0.22%** (30 / 13,709 mature) | `GRADUATION.md` |
| ⛔ **2.10%** | **NEVER QUOTE** | see below |
| $1M crossings/day, raw | **59.0** | `docs/TRACKER_SCOPING.md` §2 |
| $1M crossings/day, **verified** | **24.5** | same |
| verification pass rate at $1M | **25.4%** [22.3, 28.8], n=696 | same |
| reported liquidity overstatement | **median 781x** | `CONTAMINATION.md`, `TEMPLATE_ATTACK.md` |
| ⭐ **verified wins** | **FIVE, 2026-09-20** — v3 closes that pass all nine checks with depth and swap direction measured at the exit moment from the pool's own vaults: XCrypto **5.17x**, GOOGL 2.21x, Satoshi 2.17x, APM 2.06x, AXIS 2.06x. ⚠ **Quotes, not fills** — no transaction was ever signed. PRISMCAT 2.48x correctly REJECTED ($0 quote side). ⛔ **Never quote these five without §11's result: the rule that produced them FAILED** | `PRECOMMIT_paper_v3.md` §11 |
| ⛔ the old "verified wins: none" | superseded 2026-09-20, but its example stands: `7uMjiTCQ…` "4.58x" FAILED — graded TRAP at observation, then its freeze authority froze 50 buyers the second each bought, and their SOL was the multiple | `docs/BACKLOG.md` A42 |
| ⛔⛔ **RULE_V3, the strategy** | **FAILS ITS OWN PRE-COMMITTED TEST at n=44.** Median realizable multiple **0.0007x**; win rate **13.6%** [6.4, 26.7] against a **36.7%** break-even, the whole interval below it; **−$2,718 / −61.8%** of notional ($4,400 → $1,682), −63.2% unattended-only at n=39. ⭐ The distribution is bimodal with **nothing between 0.5x and 2x**. Closed as a trading rule; ledger still appends | `PRECOMMIT_paper_v3.md` §11 |
| ⛔ paper v1 hit rate | **QUARANTINED - no usable rate.** The retired 9/76 = 11.84% was on mid-priced exits, and 96 v1+v2 positions were never closed (09-15 → 09-17). `paper.summary()` returns `QUARANTINED` from 2026-09-19 | `PRECOMMIT_paper_v3.md` §2a |
| ⭐ median holders, our own "winners" | **9** (54% under 10) | `docs/TRUSTED_FIELDS.md` §1 |
| median holders, Jupiter-TRADEABLE | **1,350** | same |
| median holders, Jupiter-TOTAL_LOSS | **3** | same |
| ⭐ **launch coverage, measured from chain** | **1.26%** [0.49, 3.20], 4/317 creates | `COVERAGE.md`, `coverage_probe.py` |
| ⭐ **graduation coverage, measured from chain** | **1.67%** [1.06, 2.63], 18/1,077 — the whole ledger, every pass (was 1.95%, 5/257 sampled) | `data/graduations/index.json` |
| top-25 24h gainers ever in our journal | **0/25** (first snapshot, 2026-09-18) | `data/market/index.json` |
| ⭐ Solana tokens ≥ $1M on the listings | **1,035** (Jupiter-verified 668 ∪ CoinGecko 784 ∪ ours 15); **863** under the pre-committed rule (Jupiter's mcap wins) | `docs/UNIVERSE.md` §1 |
| ⛔ ...of which a $100 round trip is TRADEABLE | **65.0%** [54.1, 74.5], 52/80 seeded random | same |
| ⛔ ≥ $1M tokens running that NEITHER listing has | **11 of 42** (26%) in one market snapshot | same |
| pump.fun graduations per hour, from the ledger | **~45** (944 in 21.0h, 2026-09-19) — ⚠️ vs a 0.198% base rate, unreconciled | `data/graduations/` |
| ⛔ volume-manipulation rule (M1/M2), validated | **FAILS**: flags 96.7% of sellable vs 90.0% of unsellable tokens; M2 tracks activity. **M1′ alone vs the wallet farm: 0/30 flagged vs 4/30 of the control, null** | `docs/VOLUME_INTEGRITY.md` §3c, §3e |
| ⭐ **our base rate: AMM token → >= 2x with >= $500 quote depth at +6h/+24h, authorities revoked** | **0.27%** [0.05, 1.54], 1 / 364 priced from chain (409 sampled, 09-12 → 09-18) | `PRECOMMIT_cluster_rule.md` "Result" |
| ⛔ **wallet-cluster rule (3+ wallets / 10 min / $1,500)** | **INCONCLUSIVE**: fired on 7 of our 409 sample tokens (bar n=30); degentape's wallets touched only 38 of them | same |
| degentape's "win" (profit > $0), re-derived from their tape | **39.7%** [39.3, 40.1] of 45,853 closed positions - reproduces their own 39.4% | `docs/EXISTING_TOOLS.md` §4a |
| ⭐ ...the same positions on OUR definition (proceeds >= 2x cost) | **6.0%** [5.8, 6.3]; median position 0.925x, median hold 2.4 min | same |
| paper ledger, re-derived 2026-09-17 | 86 closes, **−$2,495** by mult / **−$4,168** realizable | `docs/LIQUIDITY.md` §8 |
| ⛔⛔ **wins verified 2026-09-21, and the gate's TENTH hole** | **17 claims passed the nine checks on chain-measured depth. ⛔ SEVEN are on contracts OUR OWN SCANNER REFUSED** (grade 30–65 against PASS_SCORE 70), and **two more carry `impersonation: claims_incumbent_name`** — a token symbol'd **USDT** at 2.65x and an **OpenAI** at 2.22x/2.29x. **The gate reads depth, sells, authorities and elapsed time; it reads neither `grade` nor `impersonation`.** ⭐ Actionable — surfaced AND passing AND not impersonating: **EVO 3.44x, 💲老六 3.41x, JEANPHIL 3.33x, SpaceX 2.65x, JEANPHIL 2.47x, AXIS 2.36x/2.06x, SCRUB 2.25x** | `docs/BACKLOG.md` D8 |
| ⚠️ **PONDER 6.68x** | **does NOT independently verify.** Its depth is Dexscreener's $27,243 and its pool is **Raydium CPMM**, which our chain vault reader cannot parse, so `depth_measured` FAILS. ⭐ **Its v3 close verifies at 5.41x** on a live Jupiter sell quote ($540.70 out of $100, impact 3.60%, $250 and $500 shadow quotes both TRADEABLE). ⛔ **Quote 5.41x, never 6.68x.** ⚠️ Our scanner graded it **15** on $117 of reported liquidity while Jupiter's round trip called it TRADEABLE — they disagreed and the round trip was right | same |
| ⭐ **what the win gate refuses** | **158 of 166 rows** with a raw multiple ≥ 3x, 09-20 → 09-21 (93 distinct contracts); 8 rows / 6 contracts passed. **23 rows over 1,000x.** ⛔ **Worst: MEMEMAN `7a93AGkVsXAfvJ…` at 12,751,798,561x** — 12.75 **billion** x — on **$0.0006** of quote-side depth | `data/outcomes/` |
| ⭐ **funnel, measured 2026-09-20 before → after** | scan coverage **33-40% → 100%** (carry 143 → 0); 6h horizon **77 rows/108s → 296/107.5s**; rows about to age out unscored **59 → 0**; graduations **10 → 532 a pass**, backlog 880 → 399, lag 11.96h → 5.46h | `funnel.py`, `data/funnel/` |
| ⛔⛔ **gate-passing wins, re-checked a day later - CORRECTED 2026-09-22, re-run all-pairs 2026-09-23** | **8 of 15 are still sellable**, not 5. ⛔ **My morning call of "10 collapsed" was wrong on 3** (ChatGPT $89.48, tradecat $90.10, Vortex $89.51 back on a live $100 Jupiter round trip; VSOF $90.16 too). ⭐ **3 of the dead died by a single `Withdraw` as the LAST event on the pool**: USDCAT 09-21 19:54:19Z, OWL 09-22 07:14:06Z, X7 `BsE3…` 10:27:06Z. ⛔ **The 4th, "EMBER 11:09:37Z", was the wrong contract - see the row below.** ⭐ **TSLA and UOTF are now resolved: both dead** (TSLA PHANTOM, $0.02 back on $100; UOTF 0 pairs, NO_SELL_ROUTE). ⭐ **Re-run with all pairs summed: 12 of 15 SHAPE labels changed, 0 exit verdicts changed** - `round_trip` already routed across every pool, so the single-pair bug corrupted our description of tokens, not our exit prices | `data/findings/REPORT_2026-09-22_pushback.md`, `analysis/daily_2026-09-22/pushback/allpairs_rerun.json` |
| ⛔⛔ **EMBER: RETRACTED 2026-09-23, the whole writeup was the wrong contract** | Frank said EMBER was at **$17.2M and alive** and he was right. ⭐ **The real one is `5dvXTZ5qwgafnHtwu3Ls3QrWx1U4LQsFeCuJgkk4QEC6`: 30 pairs, $2,331,895 liquidity summed across all of them, $17.93M cap, $6.86M 24h volume, SPL, both authorities revoked, first pool 09-09 22:25Z, $2,000 round trip TRADEABLE at 1.30%.** 19 of 30 pools are Meteora and **MET is its 2nd-largest quote asset ($522,677)**, confirming Gorilla's *"token-pairing launchpad on Meteora"* on chain. ⛔ **What I analysed all day was `FLCr9vGMTkbDcRCoirP5Hx8gB7TW1Azt3pkw3qp2HTsh`: a PHANTOM at 3 pairs, $1.39 total liquidity, $1.31 BILLION claimed cap, first pool 09-21 10:55Z - twelve days AFTER the mention.** The 2,690 SOL, the 2,907.565 SOL `Withdraw` by `HoX8uwcQiEmz…` at 11:09:37Z, the $292k, the 3.97x and the $20.36 are all correct **about the phantom** and are withdrawn as statements about EMBER. ⛔ **Never quote any of them** | `data/findings/RETRACTION_2026-09-22_ember.md` |
| ⛔⛔ **"the pool no longer exists" has NEVER happened** | **0 of 5,816** distinct pools in 24h of outcome rows are closed on chain. `record_outcome` writes `gone` when two INDEXER lookups fail (`journal.py:974`), collapsing four states: closed / near-zero / indexer dropped it / wrong pool. **3,878 of 5,816 recorded pairs (67%) are pump.fun bonding curves**, and **243 rows on 135 contracts were scored against a curve AFTER our own ledger said the token graduated off it** | same, BACKLOG A51-A52 |
| ⭐ **graduation miss, by cause** | 9.0% coverage is **~93% cadence**: 28 passes in 24h, median discovery window **199s**, union **1.68h of 24h = 7.0% of the time**. Truncation ~0 (1 pass, `scan_coverage` median 1.000), no rate limiting, definition sound. Of 86 graduations that landed INSIDE a sampled window, 64 reached the journal. ⛔ GeckoTerminal `new_pools` caps at **page 10** (429 at 11), so one pass sees ≤ ~400s: full coverage needs ~400 passes/day | `data/coverage/`, same |
| ⛔ **venue blindness, measured - CORRECTED 2026-09-22 (later read)** | Solana venue-only volume **$3,294M**: our program map covers **51.7%**, not the 46.4% I published hours earlier (that counted all protocol rows, not venues). All-protocol total **$3,428,858,821 / 125 rows**, BisonFi **13.03%** of it and **13.56%** of venue-only. ⚠️ **DefiLlama moves through the day: every share needs its read time attached.** pump.fun + PumpSwap = 14.4%, so the pump-only graduation ledger misses **85.6% by volume**. The blind half, named: BisonFi $446.8M, GoonFi $159.5M, Tessera V $155.5M, Scorch $150.6M, Manifest $136.4M, Jupiterz $80.8M, QuantumAMM $76.7M, StonkFun $63.0M, HumidiFi $49.3M | `docs/COVERAGE_PLAN.md`, `analysis/coverage_expansion/RESEARCH.md` |
| ⭐⭐ **the asset-pairing mechanic, VERIFIED on chain** | A "pair" is the **AMM pool's quote asset** being a tokenized or bridged version of the named asset. ⛔ **No oracle anywhere**: Raydium CPMM/CLMM and Meteora DLMM read no price feed, so the link is (a) denomination, making the token's USD price `pool ratio × quote asset USD`, and (b) rewards paid in that same asset. ZCAT's deepest pool holds **556.93 ZEC**; NEARKAT's **48,642 wNEAR**; COPCAT's **343.53 COPX**. ⚠️ **VCAT unresolved** (19 same-symbol candidates, top one a pump.fun mint with 2 holders). ⭐ So a paired token IS analyzable: its return decomposes into paired-asset beta plus the idiosyncratic ratio move, which is description, not prediction | `docs/ASSET_PAIRED_TOKENS.md` |
| ⛔⛔ **the 09-21 copper finding is CORRECTED** | I reported copper as a new organic narrative (24 contracts, 8 names, 4 passing a round trip, COPCAT ~$1.18M) and as evidence that name clustering works. **It was a venue adding a pairable quote asset:** COPCAT's pool is quoted in **COPX, the Global X Copper Miners ETF** (`CzLTZppPdZtTjyq3WGpHLstoc3GLhu7zH5Zg6xUa6Gv5`, Token-2022, tags stocks/rwa). ⭐ **Our clustering reads names, so it can only see the shadow; the object is the set of quote assets in new pools.** ⛔ And we store no quote mint on any row, so this cannot be run on history (A55) | `docs/MARKET_META_2026-09.md` §4 |
| ⭐⭐ **BisonFi is a market maker, not a launchpad** | Verified myself: program `BiSoNHVpsVZW2F7rx2eQ59yQwKxzU5NvBcmKshCSUypi` is executable and has **17 program accounts** carrying **$446.8M/day**. GoonFi 35, Tessera V 29, Quantum 37, Flux 7: **~300 accounts = 30% of Solana venue volume, and nothing launches on any of them.** ⭐ **So Frank was right to put StonkFun ahead of BisonFi, though BisonFi is 7.1x bigger** - parsing a PMM adds market-maker inventory, not token coverage, and Jupiter already routes through it | `docs/COVERAGE_PLAN.md` §2 |
| ⭐ **StonkFun: 1.91% of volume but 21% of LAUNCHES** | 44 of 210 rows in a sampled launch feed (pump.fun 148, met-dbc 6); my own pass: 3 of 30. Its tokens are Token-2022 with a **300 bps** transfer fee (100 bps on STONKCAT) and pools quoted in ZEC/wNEAR/COPX/STONK, which **our depth reader values at $0**. ⚠️ **Its program id is UNVERIFIED and was not found**; two ways in that do not need it: the `launchpad` label on Jupiter's launch feed, and paging the fee authority `5KXDF6QnqhBj72hDtJNkkpFaQVUfbFXNybMsp3DiK6tD`, which harvests every stonk.fun mint's fee | same, `docs/ASSET_PAIRED_TOKENS.md` |
| ⭐⭐ **the APR mechanism, traced on chain** | Fee withheld in the mint → authority `5KXDF6Qn…` harvests and swaps it (**400 txs in a 2-minute window**) → distributor `HuBMeYW3aDn8BH65fo8xxbP4oiexyup8udzKyccgi8Ga` paid **4,747 distinct wallets in 300 txs over 37 seconds**, in quote assets. ⛔ **Funded by other traders' volume: redistribution, not yield**, and the same tax is your entry and your exit cost | `docs/ASSET_PAIRED_TOKENS.md` |
| ⭐ **free cross-launchpad launch feed** | `lite-api.jup.ag/tokens/v2/recent`, keyless, 200, 30 rows, ~0.7s, **called myself**: `launchpad`, `dev`, `holderCount`, `audit{mintAuthorityDisabled, freezeAuthorityDisabled, devBalancePercentage, devMints}`, `firstPool{id, createdAt}`. ⚠️ **Cadence measured before use (rule 13): 30 rows span a median 47s ≈ 38 launches/min, so a 30s poll cannot miss and 60s drops rows.** ⭐ This is the answer to the 1.26% launch-coverage figure, and it was never a pump.fun problem | BACKLOG A56 |
| ⭐ **exit cost at Frank's real clip, measured 2026-09-22** | Round trip at **$2,000**: HYPE **0.004%**, SOL 0.002%, STONK 0.12%, CATE 0.71%, ZCAT 7.59%, PURR-Solana 8.18%, STONKCAT 10.49%, KNOTS 10.56%, **LOOP 35.31% (effectively unexitable)**. ⛔ **PURR on Hyperliquid does not fill a $2,000 sell at all** ($1,547 of visible bids; 0.40% at $500). Impersonators named, incl. a "SOL" claiming $2.27B on $235k volume and a "HYPE" claiming $1.76B on **$8** of volume | `data/findings/TICKERS_2026-09-22.md` |
| ⭐ **SEC "Innovation Exemption", VERIFIED from sec.gov** | Dated **2026-09-17**: five-year temporary conditional relief letting Tokenized Securities Venues trade tokenized NMS stock without registering as an exchange, plus dealer relief for their LPs. ⛔ **Scope bound that matters: tokens must give holders "the same rights and privileges as does traditional NMS stock"**, so synthetic price-trackers are excluded - it legitimises the **quote-asset layer** (COPX and its kind), not the memecoins denominated in them | `docs/MARKET_META_2026-09.md` §2 |
| ⭐⭐ **BASE RATE: a $1m token, one month later** | **9.0% [7.1, 11.4], n=698** can still round trip $100 today; by age **10.3%** (0-7d, n=233), **13.2%** (8-20d, n=243), ⛔ **3.2% [1.5, 6.4] (21-34d, n=222)**. Cohort is every `mcap_1m` crossing in our own milestones 08-21 → 09-22, scored with a live Jupiter round trip per address. ⚠️ **I nearly published it 14 points wrong from a 6-token sample (6/6 dead); at n=44 it is 86.4% [73.3, 93.6]** - ZEC was among the survivors. Rule 15 again | `analysis/gorilla_archive/control_roundtrip.py` |
| ⛔⛔ **a ticker CANNOT be resolved to a contract after the fact** | The listings **preferentially** drop a token once it has no liquidity, so the dead tend to be invisible and a ticker resolves to a living namesake. Strength, measured: **86.4% [73.3, 93.6] of 44 index-absent cohort tokens failed a live $100 round trip**. ⭐ **Proof it is an artifact: ticker-arm survival is FLAT at 60-69% across every age bucket (incl. 35+ days) while the address-keyed control decays 10→13→3%.** ⛔ **So no hit rate on any ticker-only source may be published**; 202 of 482 rows are `unverifiable`. ⛔⛔ **RETRACTED: the EMBER example that used to sit in this row was INVERTED** - the resolver's date rule picked the right contract and a hand-check overrode it wrongly. The conclusion rests on the flat age curve, never on EMBER | `docs/GORILLA_ARCHIVE.md` §3, `data/findings/RETRACTION_2026-09-22_ember.md` |
| ⭐ **the @CryptoGorilla archive** | **49 daily recaps, 2026-08-04 → 09-21, no gaps**: 552 bullets, 732 mentions, **482 distinct tickers**, each with **what it does in his own words plus the date**. ⭐ **341 of 482 (71%) have NO stated mechanism at all** - the honest answer to "what does this coin do" is usually "nothing is claimed". PAIRED 59, LAUNCHPAD 47, PRODUCT 23. In Supabase `crypto_gorilla_archive` and `analysis/gorilla_archive/gorilla_universe.html` | `docs/GORILLA_ARCHIVE.md`, BACKLOG A60-A62 |
| ⭐ **exit cost RE-QUOTED live 2026-09-22 23:22Z** | At **$2,000**: SOL 0.00%, HYPE **0.012%**, STONK **0.21%**, CATE **0.72%**, ZCAT **7.49%**, KNOTS **8.74%**, STONKCAT **10.79%**, PURR-sol **11.22%**, LOOP **34.16%**. ⛔ **PURR on Hyperliquid still does not fill $2,000** ($1,261 of visible bids). ⛔ **KNOTS, LOOP and STONKCAT have a LIVE `transferFeeConfigAuthority`: the 3% tax can be changed after you buy.** ZCAT and PURR-sol have it revoked | `analysis/tickers_2026-09-22/requote.py` |
| ⛔⛔ **the Dexscreener pair cap** | **30 per mint, for ANY mint.** SOL returns 30. ⚠️ So every all-pairs total at 30 pairs is a **FLOOR**, the missing pools cannot be bounded (the 30 are not sorted by size), and a truncated sample may never be graded PHANTOM. ⛔ **Batching is worse than useless here**: 3 mints in one call returned 30 pairs total (15/14/1) | `allpairs.py`, standing rule 18 |
| ⛔ **phantom share of $1M/$5M crossings** | **85%** (64/75 failed realizability at crossing, 2026-09-22), not "a third" as the research brief says. Verified-crossing figure above (25.4%) is the older, broader screen | same |

⛔ **Never quote the 2.10% graduation rate.** It is 397/18,920 computed on
**reported liquidity** — the field measured overstating by a median 781x. Our
clean figure is 0.22%, which agrees with Kamat's 0.198%. **Any lift ever quoted
against 2.10% needs recomputing.**

⛔ **v1 AND v2 PAPER LEDGERS ARE QUARANTINED (2026-09-17).** Both price fills off
the Dexscreener mid: `notional_usd` is recorded on every entry and **never
applied**, so the multiple is a price nobody could obtain at any size. That is
why the wins do not verify - the exits were fictional, not optimistic. Appends
raise; reads still work. ⛔ **Never quote their P&L again** - specifically the
retired **-$3,099 / -$40.78** and my re-derivation **-$2,495 / -$4,168 over 86
closes**. Honest status: **"no usable P&L"**, not a loss figure. See
`PRECOMMIT_paper_v3.md` §2.

⚠️ **The paper log is a SIMULATION.** Frank has **no realized P&L**. Never
describe paper results as his trading record. `data/paper/ledger.jsonl` (v1) and
`ledger_v2.jsonl` (v2) contain no transaction signatures, wallets, fills or
fees. Any path that depends on a track record has nothing to sell yet.

---

## Standing rules — non-negotiable

1. **Re-derive any figure a brief hands you** before acting on it. Say plainly
   when it is stale or wrong. **Lead with the correction.**
2. **Key on the contract address, never the ticker.** Tickers are display only.
   398 contracts in our data impersonate an incumbent name; one "DOGE" showed
   $86.5B FDV against $0.0002 of real sellable depth. ⛔ **And a ticker can
   render as a name it does not contain:** 112 contracts carry a bidi control in
   the symbol (`'U‮CDЅ'` displays as **USDC**, and claimed the highest
   liquidity of 2026-09-18 with zero sells), 48 more mix Cyrillic into Latin.
   `html.escape()` does NOT neutralise this - use `dashboard.safe_sym()`. See
   `docs/SYMBOL_ATTACKS.md`.
   ⛔⛔ **BROKEN AND FIXED 2026-09-21, in the one lane that was never code.** The
   `scanner-hit` findings lane existed only as prose in the desktop task's
   SKILL.md, and that prose said `--key <SYMBOL>` one paragraph above telling the
   agent to key the TRAP lane on the contract address. **Six distinct BASKET
   contracts, two of them graded 100, collapsed into one `scanner-hit:basket`
   class on 2026-09-20 and everything after the first went silent.** Measured:
   **23 ticker classes held more than one distinct grade-85+ contract** in the
   four days `grade` has existed, covering **34 contracts**, **11 inside a single
   hour**; 285 fires after the first were suppressed across all time. The lane is
   now in `collect.scan_stage`, keyed on the address, and ⭐ **`test_tickerkey.py`
   fails at the AST level if any findings key, dedupe set or `or`-fallback
   anywhere mentions a ticker field** - 12 lanes are exempt, each with a reason.
3. **Liquidity-gate every headline number.** Reported liquidity overstates by a
   median 781x. A market cap, a multiple or a win is not real until it is
   checked against **quote-side depth from on-chain reserves**.
4. ⚠️ **Phantom crossings are the norm, not the exception.** Only **25.4%** of
   $1M crossings survive a basic integrity screen. Never fire an alert on an
   unverified crossing — he will act on it.
5. **Unknown renders as "unknown", never as 0 or blank.** Five separate failures
   came from an absent measurement rendering as a real value. See the `usd()`
   docstring in `dashboard.py` — it is the clearest statement of the rule.
6. **Numbers carry n and a Wilson interval.** Every threshold is pre-committed
   to a file **before** anyone looks at the data.
7. **No hit rate below n=30 closed distinct contracts per arm.** Report both
   ways: late closes in/out, inferred losses in/out.
8. **Nothing is ever deleted.** The journals are append-only.
9. **Free tools only. Never sign up for anything. Never execute a trade.**
   Price things and report; signup is Frank's decision alone.
10. **"Exists but never runs" bugs are verified by observing an unattended run**,
    not by reading config.
11. ⛔ **Never hand Frank a manual process.** "Set the alerts by hand" is not an
    answer. If it cannot be automated, say so and say why.
13. ⛔ **Never measure a phenomenon with a sampler slower than the phenomenon.**
    Three failures from this one class: fast winners logged as losses (first
    checkpoint 1h, median time-to-bond ~1min); and the retracted band-dwell
    finding, where per-batch `ts` and hourly discovery produced "88% seen once"
    by construction. **Before quoting any duration, state the sampling interval
    and show it is shorter than what you are measuring.** When Frank's lived
    experience contradicts a measurement, the measurement is the suspect.
14. ⛔ **A/B measurements on live traffic must run SIMULTANEOUSLY, never in
    sequence.** Memecoin activity is bursty, so two samples minutes apart are
    two different populations. Measuring the filtered and unfiltered Helius
    streams back-to-back made the *filtered* stream look 22% busier than the
    unfiltered baseline — an impossible result that only resolved when four
    subscriptions ran concurrently on the same traffic (`docs/LIQUIDITY.md` §7).
    **If you are comparing two conditions, open both at once and share a start
    barrier.** Same family as rule 13: a measurement taken at the wrong moment
    does not describe the moment you care about.
15. ⛔ **A truncated sample must record WHAT it missed, not just how much.**
    The scanner enriches `pools` newest-first and `break`s on a time budget, so
    the rows it drops are always the tail - systematically the oldest pools in
    the batch. Measured across 399 passes: 97.0% coverage overall, 99% median,
    but 55% of passes truncate and the worst saw 19%. `LAST_SCAN["skipped"]` now
    carries the addresses. ⚠️ **I first reported this as "24% dropped" from a
    single pass I happened to watch - an 8x overstatement, and the same
    generalise-from-one-observation error this rule exists to catch.** Small-n
    findings are the exposed ones; see `docs/SAMPLING_BIAS.md`.
16. ⛔⛔ **VERIFY THE OUTPUT, NEVER THE EXECUTION.** Every failure this week is
    the same mistake: socials dropped (we checked the field was *computed*, not
    that it *landed in a row*), the score band (we checked the *changelog*, not
    the *source*), pool truncation (we checked the pass *completed*, not what
    fraction it *processed*), liquidity off 781x (we checked a number *came
    back*, not that it was *true*), the collector dead 4 days (we checked the
    task *fired*, not that *rows appeared*). **Four of those five were silent.**
    ⭐ **A component that cannot tell us it is broken is worse than one that is
    obviously broken.** Every component asserts its own output; the liveness
    registry counts **rows, not beats**; every headline number carries its n and
    its provenance. **Read `docs/ENGINEERING_DISCIPLINE.md` before adding any
    component**, and `test_discipline.py` enforces what can be enforced.

17. ⛔⛔ **Every third-party crypto tool is UNTRUSTED BY DEFAULT** (Frank,
    2026-09-19, permanent: *"Treat everything as unsafe and something we would
    want to rebuild as a feature of our site. Or something we can use externally
    for aggregation"*). Two relationships only: ⭐ **REBUILD** (build the
    capability into our site) or ⭐ **AGGREGATE** (read its public output over
    HTTP, never depend on it, never authenticate). ⛔ **Never connect a wallet to
    any of them, no exceptions. Never take a dependency that needs auth.**
    ⚠️ **Their claims are marketing until verified against our own data or the
    chain.** Every tool's label lives in `docs/EXISTING_TOOLS.md`; `RULES.md`
    rule 24 has the reasoning.

18. ⛔⛔ **NEVER READ ONE POOL AND CALL IT THE TOKEN** (Frank, 2026-09-22:
    *"we have been reading one pool on tokens that trade across thirty"*).
    Always call the token endpoint and **SUM liquidity and volume across every
    pair for the mint** - `allpairs.token(mint)`. Measured damage: the real EMBER
    holds **$2,331,895 across 30 pools**, and the deepest single pool is
    **$663,260, a 3.52x understatement**; a whole day of analysis went to a
    **phantom** carrying the same ticker with **$1.39** of backing behind a
    **$1.31 billion** claimed cap. ⭐ **Phantom rule, pre-committed:** mcap >
    $1,000,000 with total liquidity < $1,000 across ALL pairs is a ghost, not a
    token, and may never produce a finding - **but only on a COMPLETE sample**,
    see the cap below.
    ⛔⛔ **AND THE ENDPOINT CAPS AT 30 PAIRS, corrected the same day I wrote
    the fix.** I first claimed "~30 pairs is the signature of a pairing-launchpad
    asset". **It is not: 30 is Dexscreener's hard limit.** Probed 2026-09-23 -
    **SOL, which trades in thousands of pools, returns exactly 30**, as do USDC,
    BONK, EMBER and Hypurr; a one-pool pump.fun token returns 1. ⚠️ **And the 30
    are not the biggest 30** (EMBER's returned order was 521727, 357897, 664541,
    109347, ... - not descending), so the remainder cannot be bounded.
    ⭐ **Therefore `pair_count == 30` means "30 or more" and every total at 30 is
    a FLOOR**, carried as `truncated` / `total_liq_is_floor`; `pair_count` is a
    signal at the LOW end only; and a truncated sample may **never** be called a
    phantom. ⚠️ **Batching the endpoint makes it worse, not cheaper**: 3 mints in
    one call returned 30 pairs TOTAL, split 15/14/1, so a 30-mint batch would
    reproduce the original bug silently. **One call per mint, always.**
    ⚠️ **Summing correctly is still a correct sum of an overstating field** -
    it is for shape, venue spread and phantom detection, never an exit price.
    The exit is `chainfields.round_trip()`, which already routes across every
    pool. Same bug family as `journal.py:974` writing `gone` on one failed
    lookup: **one observation of a many-part thing is not the thing.**

12. ⚠️ **Any script hitting a Cloudflare-fronted API must set a `User-Agent`.**
    Python's default `Python-urllib/3.x` is blocked with a bare `403 error code:
    1010`, which looks exactly like an auth failure and is not. `sources.py:12`
    does this correctly; copy it. This has bitten twice.

---

## Architecture: what runs where

| component | what it does | state |
|---|---|---|
| `collect.py` | hourly staged collector: scan, sweep, watchlist, 1/6/24/168h | ✅ **running again on the hosted runner, 2026-09-18** |
| ⭐ `market.py` | **what is running NOW** - movers, volume, trending, clusters, the tape → `data/market/` | ✅ **UNATTENDED, verified 2026-09-18 23:49Z** (scheduled run 35407026193: 412 rows, 18/18 sources ok from GitHub's IPs, 44.6s). ⛔ **The pipeline only ever collected tokens at birth; 0 of the top 25 24h gainers were in our journal.** Schema for the site: `docs/MARKET_DATA.md` |
| ⭐⭐ `universe.py` | **THE TRACKED UNIVERSE**: every Solana token ≥ $1M, admitted only on a TRADEABLE $100 round trip, **never removed**; trending × universe → narratives → `data/universe/` | ✅ **UNATTENDED, verified 2026-09-19 01:48Z** (scheduled run 35413442372: 701 members, 20.3s). Seeded by hand first: 922 quoted, 699 admitted. Rule pre-committed in `docs/UNIVERSE.md` §3. ⛔ **The $100 gate admits a wallet farm ($3.53B claimed on a fraction of a percent of backing): never show a cap without `cap_backing_pct` (§3a).** ⭐ **Read by the site on production from 2026-09-19** (`site/api/market.mjs`, verified ~02:05Z), ⚠️ **but that source is uncommitted until the site session commits it (BACKLOG C16)** |
| ⭐⭐ `safety.py` | **the safety verdict on every tracked token** (DANGER / WARN / NO FLAGS / UNKNOWN), rule `PRECOMMIT_safety_v1.md` v1.1: the $100 round trip, mint account from chain (authorities, Token-2022 extensions), D1 on the live pair, holders, cap backing, RugCheck (attributed, optional). ⛔ **Fake volume and bundles are NOT CHECKED on every verdict, in words** | ✅ **in every universe pass from 2026-09-19, and RENDERED ON PRODUCTION** (observed 18:55Z: per-row verdicts, per-list tallies, "not checked: fake volume, bundles / insiders" in words; BACKLOG A40 SHIPPED) |
| ⭐ `live.py` + `supa.py` | the 10-second path: Jupiter every 10s (hot) / 60s (all), D1 every 60s, published to Supabase `live_*` tables (`supabase/migrations/002_live.sql`) under its own path name; `.live/status.json` on the host | ⛔ **BLOCKED: the schema is not applied** - nothing on disk can run DDL on `rxofejxostyqlgjlzqmk` (BACKLOG A41) |
| ⭐ `graduations.py` | **every pump.fun graduation** (C14): pages the migration authority from a cursor, every signature accounted for → `data/graduations/` | ✅ **UNATTENDED, verified 2026-09-19 01:48Z** on the keyless public RPC (17/17 accounted, lag 11s). Runs before the universe, which re-checks 72h of graduations for $1M |
| ⭐ `paperv3.py` | the ledger that prices fills on real quotes | ✅ **SCHEDULED 2026-09-18** — enters in the scan loop beside v1/v2, sweeps in the sweep stage. ⛔ **Nothing called it before that**, despite 71 passing tests |
| GitHub Actions `collect.yml` | same, hosted | 🟡 **Free and unlimited (public repo), but ⛔ the 11:37, 14:50 and 17:38Z passes on 2026-09-19 were CANCELLED at the 15-min job timeout before they could commit - every row lost, silently** (BACKLOG C17). Fix `b13267f`: job 35 min, Collect step 24, runner pass clock 20 min, outcomes stop at 13, artifact on cancel too, `test_stages.py` §10 ties them together. ✅ **Observed 2026-09-19: scheduled run 35464899959 collected for 16.5 min (past the old limit), committed `f30fd73`, and production served it** |
| Claude desktop task `crypto-collect-hourly` | same, staged, on the host (all ten stages incl. `sweep`) | ✅ **alive again 2026-09-19** after the desktop restart cleared the Plan9 mount: scheduled passes observed 06:24–06:41Z and 07:07Z, and it closed a v3 position unattended (Pigeon, 07:07:55Z). ⚠️ **Recurring outage**: a reboot that loses the mount kills it silently. ⛔ It is NOT Windows Task Scheduler - there is no crypto task there, and none should be added (`479e9cc`) |
| `site/` on Vercel (`crypto-intel-one-eta.vercel.app`) | ⭐ **the deliverable**: trending, tracked universe, narratives, crossings, movers, paper v3 counts. **Owned by the site session**; every cap goes through `honest.capWithBacking()` | ✅ **all four C16 reads live, verified 2026-09-19** from the pipeline side. ⛔ The pipeline session never stages `site/` files, `site/README.md` included |
| `site/api/helius.mjs` on Vercel | Helius webhook receiver → Supabase → Discord | ✅ **deployed and answering**, but watching 0 addresses |
| `data/dashboard.html` | static phone-first dashboard, built by `dashboard.py` | ✅ **rebuilt on every pass from 2026-09-18** (`dashboard.build`, 4.0s, stdlib only, no network). ⛔ Before that it appeared nowhere in `collect.py` and went stale silently |

**State store is git.** `data/` is committed after every run. Supabase is a
write-only mirror (no SELECT grant), so it cannot serve as state.

**Live deployment:** `https://crypto-intel-one-eta.vercel.app` —
`/api/helius` is the receiver. Webhook `75056f75-c129-4f43-b686-0f369f8fa669`
is `active: true`, `transactionTypes: ["ANY"]`, **`accountAddresses: []`**.
⛔ **That empty list is why whale alerts have never fired.**

### Current blockers, in order

1. ⚠️ **`onchain_reserves.exit_depth()` is unreliable — but it is NO LONGER what
   everything depends on, and the old wording here conflated two functions with
   similar names.** Re-derived 2026-09-18:

   - **`onchain_reserves.exit_depth(pool, base, quote)`** — the real on-chain
     read, 5 of 6 failed on 09-17. ⭐ **It has exactly ONE live caller:**
     `paper.py:810`, inside the **quarantined** v1 close path, where it fills a
     supplementary `chain_depth` field. Nothing else in the repo imports it.
   - **`resolve.exit_depth_usd(pair)`** — computed from the Dexscreener
     `liquidity` payload. **This is the one on the hot path**, with ⛔ **four
     copies**: `resolve`, `scanner`, `watchlist`, `paper`. It gates
     `paper.wants_authority_check()` and therefore the whole v3 funnel.

   ⭐ **What verifies a number today is `chainfields.round_trip()`** — Jupiter,
   realizable, used by `check.py` and `paperv3`. The leverage moved with it.
   See `test_depth.py` for the two divergences between the four copies.
2. ✅ **RESOLVED 2026-09-18 — the collector runs on GitHub Actions again.**
   The repo is **public**, so Actions minutes are free and unlimited and the
   ~$31/mo question is closed. Runs take ~9-10 min at the 2026-09-07 pacing
   (`CRYPTO_HTTP_PACE_S` 1.0, correct and not to be reverted).
   ⚠️ **Windows Task Scheduler is NOT the answer and was deliberately removed**
   (`479e9cc`). Do not reintroduce it.
3. ⚠️ **A concurrent push can still cost a pass, and once did.** On 2026-09-18 a
   scheduled run collected a full pass and then died in `Commit the journal`
   because a human pushed during its ~10 minutes; `git pull --rebase` stopped at
   the first conflict and the ephemeral runner was destroyed with the rows on it.
   Fixed two ways: `*.jsonl merge=union` in `.gitattributes`, and a push loop
   that resolves conflicts and uploads `data/` as an artifact if it still cannot
   push. ⛔ **Avoid pushing while a run is in flight anyway.**
4. ⛔ **A cancelled run loses its rows and says nothing** (2026-09-19, BACKLOG
   C17). Three passes ran past the 15-minute job timeout; `cancelled` is not
   `failure`, so nothing alarmed, and origin/master sat at 07:26Z for 11 hours
   while the site served stale data. The desktop task's rows were committed by
   hand (`2ef6de5`). ⛔ **The desktop task never commits** - its rows reach origin
   only when this session commits them. **When a pass grows, check its duration
   against the workflow's timeouts** - `test_stages.py` §10 now does.

---

## Map of the repo

**Start here for a task about…**

| topic | file |
|---|---|
| ⭐ **the flagship experiment** — pre-launch social signal | `docs/PRELAUNCH_SIGNAL.md` |
| ⭐ **liquidity: what to trust, and the plan to replace `liq`** | `docs/LIQUIDITY.md` |
| ⭐⭐ **asset-paired tokens: the verified mechanic, and the copper correction** | `docs/ASSET_PAIRED_TOKENS.md` |
| ⭐⭐ **the phased coverage plan, ordered by measured volume** | `docs/COVERAGE_PLAN.md` |
| ⭐ **the market meta Sept 2026: claims received vs what we verified** | `docs/MARKET_META_2026-09.md` |
| ⭐⭐ **the @CryptoGorilla archive: 482 tickers, what each does, and why no hit rate** | `docs/GORILLA_ARCHIVE.md` |
| ⭐ **social-graph watcher: scoped, NOT built, with the cost arithmetic** | `docs/SOCIAL_GRAPH_SCOPE.md` |
| **every venue's program id and its verification status** | `analysis/coverage_expansion/RESEARCH.md` |
| ⭐ **holders, mcap, volume, bundles — all from chain** | `docs/TRUSTED_FIELDS.md` |
| ⭐ **every killed strategy and whether its killer survives** | `docs/UNKILL.md` |
| ⭐ **what already exists — compose, don't rebuild** | `docs/EXISTING_TOOLS.md` |
| ⛔ **every third-party crypto tool's label (REBUILD / AGGREGATE / neither), degentape verified on chain** | `docs/EXISTING_TOOLS.md` §4 |
| volume manipulation: methods and pre-committed thresholds | `docs/VOLUME_INTEGRITY.md` |
| ⭐ **dev wallet history, funding graphs, first buyers, LP** | `docs/DEV_WALLET.md` |
| ⭐ **paper trader v3 — fills priced on real quotes** | `docs/PAPER_V3.md`, `PRECOMMIT_paper_v3.md` |
| ⛔⛔ **EVERY commitment and its status — read at session start** | `docs/BACKLOG.md` (⛔ read the **SHIPPED-row audit** section first) |
| ⭐⭐ **the tracked universe: size, cost, source, the pre-committed gate** | `docs/UNIVERSE.md` |
| ⭐ **what is running now: every `data/market/` file, field and rendering rule** | `docs/MARKET_DATA.md` |
| ⭐ **one place: what is scattered, what retires, what Frank must decide** | `docs/CONSOLIDATION_PLAN.md` (plan only - nothing moved) |
| ⛔ **Cash Cat is RETRACTED - never cite it as a hit** | `docs/BACKLOG.md` A37 |
| ⭐ **how much of the launch stream we see, and the costed good version** | `COVERAGE.md` (2026-09-18 section) |
| ⛔⛔ **how we test: verify output, not execution** | `docs/ENGINEERING_DISCIPLINE.md` |
| ⛔ **symbols that render as a different token** | `docs/SYMBOL_ATTACKS.md` |
| ⛔ **why no score may gate an entry, and the AST check** | `test_scoreband.py` |
| outcome-queue expiry: 21% of checks, and why | `docs/SAMPLING_BIAS.md` §5 |
| crypto history, organised by recurring mechanism | `docs/CRYPTO_HISTORY.md` |
| the 1M tracker, crossing rates, real-time architecture | `docs/TRACKER_SCOPING.md` (**§5c supersedes §5b**) |
| buyer and creator rules, rejected ideas | `docs/RULES.md` (§B buyer, §C creator, §O observations) |
| standing reporting rules | `RULES.md` (root — different file, do not confuse) |
| terms, base rates | `docs/GLOSSARY.md` |
| chains, venues | `docs/CHAINS.md` |
| trading economics, fees, sizing | `docs/TRADING_PLAYBOOK.md` |
| launch mechanics, curve geometry | `docs/TOKEN_MECHANICS.md`, `docs/CREATOR_PLAYBOOK.md` |
| the long-form reference and open questions | `docs/TRENCHES_REFERENCE.md` |
| the 781x liquidity finding | `CONTAMINATION.md`, `TEMPLATE_ATTACK.md`, `EXIT_DEPTH.md` |
| what the detectors do and their recall | `FRAUD_DETECTION.md` |
| open gaps and their measurement bars | `GAPS.md`, `OPEN_ITEMS.md`, `QUESTIONS.md` |
| X/Twitter API prices | `X_API.md` |
| any pre-committed threshold | `PRECOMMIT_*.md` |

⭐ **Existing credentials — full disk scan 2026-09-18, do not re-ask.** 62
distinct credential names across 37 files. **Values are never printed anywhere.**

**crypto-intel/.env:** `HELIUS_API_KEY` (✅ RPC 200, free tier 1M credits/mo),
⭐ `JUPITER_API_KEY` (free tier, 25M credits/mo then $1/M; **measured ceiling
~1.1 req/s — the key buys reliability, not speed**; usage in
`data/_jupiter_usage.json` via `chainfields.usage()`), `BIRDEYE_API_KEY`
(⛔ **dies after ~7 calls, permanently 401 — do not use**), `ALCHEMY_API_KEY`,
`ETHERSCAN_API_KEY`, `HELIUS_WEBHOOK_SECRET`, Supabase, 4 × `CRYPTO_*_SECRET`.

⭐ **X / Twitter: SEVEN credentials, and the account is ALIVE.** In
`dispatch-workspace/.env` **and** `~/Documents/openclaw-review/gateway.cmd` and
`~/OLD-OC-old/gateway.cmd` (⚠️ bearer is 112 chars in `.env`, 113 in
`gateway.cmd` — the `.env` one is the one that authenticates):
`TWITTER_BEARER_TOKEN`, `_ACCESS_TOKEN`, `_ACCESS_SECRET`, `_CONSUMER_KEY`,
`_CONSUMER_SECRET`, `_OAUTH2_CLIENT_ID`, `_OAUTH2_CLIENT_SECRET`, plus
`TWITTER_USERNAME`/`_PASSWORD` (account, not API).

⛔ **ALL FOUR AUTH PATHS PROBED 2026-09-18** (`scratchpad/xprobe.py`; it prints
status codes only, never a key). The seven names are ONE app's credential set in
four flavours, plus a second bearer that is not a copy of the first:

```
bearer A (.env, 112 ch)   /2/usage/tweets          200  cap 3,000,000  usage 0
                          /2/tweets/search/recent  402  credits depleted
                          /2/tweets/search/all     402  credits depleted  <- historical
                          /2/users/by/username/..  402  credits depleted
                          /2/users/me              403
bearer B (gateway.cmd)    every endpoint           500
OAuth 1.0a user context   usage 403, all data      401  Unauthorized
OAuth2 client_credentials /2/oauth2/token          400  invalid_request
```

⭐ **CORRECTION: this is a DEPLETED CREDIT BALANCE, not a lapsed subscription.**
X's own problem URI is `.../problems/credits-depleted`. Frank remembered buying
credits and not paying for a developer account, and the error matches his
account, not the earlier "billing lapse" reading.
⚠️ **Two different meters, and both statements are true:** the 3M/month POST cap
is untouched (`project_usage 0`), and the consumable read credits are at zero.
⛔ **No credential unlocks full-archive search.** The ask is a **credit top-up**,
not a subscription — and it is Frank's call alone.
⭐ **Re-probed 2026-09-19 18:52Z (`scratchpad/xprobe2.py`):** the app-only bearer
minted from the CONSUMER key/secret (`POST /oauth2/token`) returns 200 and is
**identical to bearer A** - the app is alive, the consumer keys are valid. Every
data endpoint, full-archive included, is **402 credits-depleted**: the same gate as
recent search, not a 403 plan refusal, so credits are the only gate (inferred from
the error type). `~/OLD-OC-old/gateway.cmd` holds the same values as `gateway.cmd`.
BACKLOG C11.

⛔ **Solana now carries VERSION-1 transactions (~5%, measured 2026-09-19).** Any
`getTransaction` must ask for `maxSupportedTransactionVersion: 1`; with `0` the
node returns -32015 and the transaction silently becomes a "fetch failure".

⛔ **`XAI_API_KEY` is DEAD** — `400 Incorrect API key` from `api.x.ai/v1/models`.
Present in the same three files. It needs replacing, not finding.

⛔ **Grep every project `.env` before ever saying a key does not exist.** We lost
15 days to that once, and I repeated a version of it this session: I "corrected"
myself to say the Twitter keys were only in `gateway.cmd`, then found they are in
`dispatch-workspace/.env` too — my scan had printed only the first two locations.

**Key modules:** `collect.py` (orchestrator, `STAGES`/`staged_commands()`) ·
`journal.py` (append-only store; `record()` is a **field whitelist** — a field
not added there does not exist) · `paper.py` / `paperv2.py` (simulation ledgers)
· `check.py` (one CA in, one verdict out — the model for the analyzer) ·
`detector.py` (D1/D2) · `onchain_reserves.py` (quote-side depth) ·
`liveness.py` (origin tagging; `UNATTENDED = ("runner","scheduled")`) ·
`dashboard.py` · `sources.py` (all HTTP; sets the UA correctly) · ⭐ `market.py`
(market-wide snapshot, keyless) · ⭐ `universe.py` (the tracked universe) ·
⭐ `allpairs.py` (⛔ **the all-pairs read: every pool for a mint, summed; `pair_count`, phantom detection**) · ⭐ `graduations.py` (graduation ledger) · `volintegrity.py` (volume M1/M2 under
the pre-committed rule; validation, not a live gate) · `crossingdepth.py` (re-links historical
crossings to the depth measured at them) · `coverage_probe.py` (launch coverage
from pump.fun's own signers).

⚠️ **"Dexscreener's 24h source is degrading" — NOT SUPPORTED, 2026-09-21.** The
figure (`37/189 = 20%`, at the 24h floor) is real and comes from
`track.score_horizon`'s **primary** path — not from the `dexscreener_ok/dropped`
counters, which count only the **fallback**, on rows whose pair lookup had
already missed, and have sat at 10-15% for eleven days. The 24h primary rate
across 09-21's own alarms: **16% (n=19), 15% (65), 19% (69), 17% (118), 20%
(189)** — ⭐ **flat while n grows fivefold.** It alarms more often because the
queue is finally being processed, not because the source got worse.
⛔ **The trend could not be measured at all** until 09-21: `track.HORIZON_HEALTH`
was read only by the daily Discord line, so the rate survived only in the TEXT of
a `lookup-outage` finding, written solely when already under the floor.
`funnel.py` now persists it per horizon per pass, with its pre-committed floor.
⭐ **The third source needs no purchase and we already trust it more:**
`chainfields.round_trip()` (Jupiter, realizable) plus quote-side depth from chain
are what verify a number today, both on free tiers already in use — **cost $0** —
while Dexscreener's `liquidity` is the field overstating by a median 781x.
**The answer to a crossing is not a new feed, it is to stop pricing outcomes off
the overstating field**, which the v3 lane already does and the outcome lane
does not.

⛔⛔ **AND THE CROSSING HAS ALREADY HAPPENED AT 24h.** "One more step down and 24h
outcomes price off one source with no cross-check" understates it: measured
2026-09-21 over 09-20/09-21, **9 of 9** gate-passing wins at the 24h horizon are
**single-sourced** (1h: 3/12, 6h: 1/10; 13 of 31 overall). The gate does not
catch it, **by design** — `pricecheck` sets `trustworthy=True` on the
single-source path, so `verify_win`'s `source_agreement` check passes a price
nothing corroborated. ⚠️ **It is the `authority_live=None` shape again: not
checked reads as passed.** `pricecheck.py:196` already names it an open decision
and defers it because "the n=200 run closes 2026-09-14" — **that date has
passed, so the reason for deferring has expired.** Changing it relabels outcomes
across the record, so it needs a pre-commit, not a patch. BACKLOG A47.

⛔ **Jupiter's "organic" volume split is NOT a wash signal.** SOL itself runs
1.8% organic; a low share is the norm. It is published beside SOL's baseline
and flags nothing. There is no wash detector in `data/market/`.

⭐ **mcap and multiple milestone claims carry `exit_depth_at_crossing`** from
2026-09-18 - the same values the outcome row records, measured in the same call.
History (1,097 crossings, 09-09 onward) is in
`data/milestones/depth_at_crossing.jsonl`.

⭐ **`devwallet.py`** — `deployer()`, `launches()`, `activity_before()`,
`funding_chain()`, `first_buyers()`, `buyer_funding_overlap()`, `lp_detail()`,
`track_record()`. ⛔ **Runs, but on n=4 it did NOT separate good from bad** — see
`docs/DEV_WALLET.md` §5. Never date a wallet by walking its history; ask
`activity_before()` instead (a walk gave WOFI an age of **minus** 0.1h).

⭐ **`chainfields.py` is the trusted-field source** — `round_trip()` (realizable
liquidity), `supply()`, `market_cap()`, `holder_count()`, `trusted()`. ⛔ **Unknown
is None, never 0.** Decision-point only: a process-wide bucket caps Jupiter at
55/min, so it must never reach the per-row scan path. `test_chainfields.py --live`.
⛔ **A failed quote is not a route answer (2026-09-19).** Only Jupiter's own
`errorCode` (`NO_ROUTES_FOUND`…) makes `NO_BUY_ROUTE` / `NO_SELL_ROUTE`
(`chainfields.answered()`). An HTTP 5xx, a dead network or rate limiting is
verdict `None` from `round_trip()` and `QUOTE_FAILED` from `sell_quote()` - before
this, a Jupiter outage would have booked v3 total losses, DANGER verdicts and
universe refusals. v3 retries a failed exit quote and voids only 6h past the hold.

⛔ **The win gate has NINE checks from 2026-09-19**: `authority_live` fails any
multiple measured from a moment when the mint or freeze authority was live
(`authority_live_at_entry` on every outcome row; None = unchecked, not failed).
And a win announcement no longer says "realizable" - nothing in it quotes a sell.

⛔ **The runner has NO `.env`, and two things quietly depend on that.**
`config.helius_rpc()` falls back to `api.mainnet-beta.solana.com`, which
serves `getTokenAccounts` but wants **`mintAddress`** where Helius wants
**`mint`** — `chainfields.holder_count()` switches on the endpoint's own error,
verified keyless at **977 holders**, the same number the keyed path returns.
Jupiter falls back to the keyless lite-api and round-tripped BONK at **0.0244%**.
⭐ **No repo secret is needed.** Without the spelling switch, paperv3 would have
entered normally by hand and **nothing at all unattended**.

⭐ **`holders` is on observation rows from 2026-09-18** — fetched at the decision
point only, for rows that cleared every free condition of RULE_V3 (~7 a pass,
measured 92 of 1,003 rows over three days). Helius DAS, never Jupiter. Forward
only: no historical row has it. `holders_truncated` means the number is a FLOOR.

⚠️ **`journal.record()` is a whitelist and it has silently eaten four fields**
(`vol_to_liq`, `vol_burst`, the news NameError, `paper_v2_arm`) plus
`info.socials`, which is fetched on every row and never stored. **Compute and
persist are two separate steps. Do both.**
⭐ **Fifth case found and fixed 2026-09-22: the full token `name`** (`baseToken.name`) was fetched for
namecheck on every row and dropped - 0 of 2,924 rows had it, which is why the fake-fund wave
(108 contracts, 24 tickers, one story in the names) was invisible to ticker clustering. Now
`token_name`, display and grouping only; the key is still the address. BACKLOG A48.

⚠️ **An aborted pass's duration is unknowable, and the row used to pretend otherwise.**
`record_aborted()` runs in the NEXT pass, so `now - started` is time-to-notice (the flagged
"3,322s against a 178s kill" was a market stage dead at 18:08Z, noticed 19:03Z). Now
`detected_after_s` / `alive_at_least_s`, `ran_for_s` None. BACKLOG A49.

---

## Commands

```
python collect.py solana --stage scan --max-seconds 110   # one staged pass
python check.py <CONTRACT_ADDRESS>                        # fraud check, one CA
python dashboard.py                                       # rebuild data/dashboard.html
python -c "import paper; print(paper.summary())"          # paper ledger counts
python run_tests.py                                       # ⭐ EVERY suite + proves data/ was untouched
python test_stages.py                                     # SKILL.md must match staged_commands()
python test_references.py                                 # every file the repo names exists (run before ANY doc move)
python universe.py --gate-seconds 60                      # one universe pass (writes data/universe/)
gh run list --workflow=collect.yml --limit 10             # runner state
```

**Liveness check that actually means something:** `python liveness.py`. Its last
line answers the only question that matters — **when did a pass NOBODY TRIGGERED
last write rows.** ⛔ **A task firing is not the same as a pass running** (the
desktop task fired hourly for two days while collecting nothing), and **a hosted
runner is not the same as unattended**: `origin()` returned `"runner"` for every
Actions run until 2026-09-18, so a `workflow_dispatch` a human pressed recorded
identically to a cron fire. It now returns **`scheduled`** for cron and
**`dispatch`** for a button press, and only `("runner", "scheduled")` count.
⚠️ **`runner` rows written before 2026-09-18 are a mix of the two and cannot be
re-derived**, so any unattended figure spanning them is an upper bound.

---

## Real-time detection: settled conclusions

**You can trigger on market cap.** Nothing on chain emits it, but every swap
mutates the AMM pool account and mcap is computable from reserves on each
update. **The trigger is possible; the question was only ever how many accounts
you can watch.** Do not tell Frank it is impossible.

**Measured, 2026-09-17 (`docs/TRACKER_SCOPING.md` §5c):**
- Helius webhook ceiling is **100,000 addresses** — never the constraint.
- **Credits are:** a pool at $600k–$1M does a median **206 txns/hour ≈ 4,944
  pushes/day**, so the free 1M credits/month covers only ~7 watched pools;
  $49/mo Developer covers ~66. Webhook **edits cost 100 credits each**.
- ⛔⛔ **RETRACTED 2026-09-17: the "88% / 9-minute dwell" finding was an
  artifact and the claim that nomination cannot work is withdrawn.** `ts` is
  per-batch, not per-token; all 10 "multi-sighting" contracts were inside a
  single pass (gaps of 0–545s), so it measured our scan loop, not coin
  behaviour. **Third instance of this error class — see standing rule 13.**
  Whether nomination works is now an open question, not a settled one.
- ✅ **The answer is `programSubscribe` on the AMM programs** — watch the
  program, not a list of pools. No nomination, no miss window, no address
  ceiling. Needs an always-on process (**VPS ~$4–6/mo**; a Vercel function caps
  at 300s and cannot hold a subscription).
- ✅ **Costed by measurement, 2026-09-17.** Helius bills standard WebSockets at
  **20 credits/MB**. A live 45s `programSubscribe` on pump.fun measured **56
  notifications/sec, 31 KB/s, 542 B median → 82 GB and 1.64M credits/month**.
  **Free tier fails (1.6x over); Developer $49/mo fits at 16%, 6x headroom;
  Business $499 is not needed.** A $4–6 VPS is far more than enough — 56 small
  JSON messages/sec is trivial. **Total real-time cost ≈ $53–55/month.**

## The one genuinely urgent thing

⛔ **Socials capture (commit `ce0d33a`) is forward-only.** Two collectors run
again as of 2026-09-19 (the runner, ~7-9 passes a day, and the desktop task,
hourly while its mount holds), but every hour without one is sample that cannot be
bought back at any price. **Restoring collection outranks every purchase decision on the board** —
see `docs/DECISION_X_DATA.md`.

## Knowledge corpus

Durable knowledge accumulates in `docs/`, one file per domain, **appended to
rather than re-derived each session.** Existing: `CHAINS.md`,
`TOKEN_MECHANICS.md`, `CREATOR_PLAYBOOK.md`, `TRADING_PLAYBOOK.md`,
`TRENCHES_REFERENCE.md`, `GLOSSARY.md`, `RULES.md`.

**Planned, not yet written** — create on first substantive finding, do not
scaffold empty:

| file | covers |
|---|---|
| `docs/RUNNERS.md` | runners this cycle and every prior cycle, by CA, with what drove each |
| `docs/SECTORS.md` | NFTs, gaming, metaverse, DeFi, AI and utility tokens |
| `docs/NEWSFLOW.md` | crypto news sources, insider flow, how narratives propagate |
| `docs/NEW_CHAINS.md` | new chains and how to get in early (Arc launched 2026-09-16 — Circle L1, USDC gas, PoA, institutional validators, no memecoin venue) |
| `docs/UPCOMING.md` | large upcoming on-chain projects |

## X / Grok access — priced, not bought

`X_API.md` (2026-09-07) correctly rules out **continuous** monitoring: the
cheapest useful configuration costs roughly twice Frank's bankroll per month.
**That verdict stands for real-time. It does not apply to a bounded historical
pull.** Via xAI X Search: **$5 per 1,000 posts, $10 per 1,000 profiles**, which
makes the flagship backtest ~$65 at the core sample and ~$361 at full size.
⚠️ **Pricing changes 2026-09-21 12:00 PT** — before then it is $5 per 1,000
*calls*, which is materially cheaper for bulk history.

## ⛔ The backlog is the promise

`docs/BACKLOG.md` holds **every commitment made to Frank, with a status of
SHIPPED / IN PROGRESS / BLOCKED / NOT STARTED and verification evidence on each**.
⭐ **Append-only for commitments; nothing leaves NOT STARTED without evidence of
what was OBSERVED, not what was written.** There is no "designed" or "specced" —
those are NOT STARTED. **Read it at the start of every session.**

⚠️ **It exposed a pattern worth keeping in mind:** `chainfields` is imported only
by `paperv3`, `devwallet` by nothing at all, and `paperv3` is scheduled by
nothing. **A module that only runs when called by hand has not shipped**, and
passing tests are not evidence that it is in the system.

⛔⛔ **Audited 2026-09-19: 13 of the 48 rows marked SHIPPED were not.** 11 run
unattended and write files **no page reads** (market, clusters, crossing depth,
v3, holders, `dashboard.html`); 2 are hand-run only. They are IN PROGRESS now.
**The test for "shipped" is: it runs unattended AND its output reaches the site
or Discord.** Before marking anything SHIPPED, name the page or message it
reaches. The worst case: `exit_depth_at_crossing` lands on every claim and the
site's crossings panel ignores it, so production still shows 0 verifiable.

## Session protocol

⛔ **This repo has one session. Everything routes through it.** Do not start a
second window for crypto-intel work — context is the asset here, and the
findings in this file were expensive to produce.

**Working style Frank has asked for:** be direct, lead with corrections, own
mistakes without softening, and never present a manual workaround as a
deliverable. The goal is something **robust and genuinely novel**, not an
indicator.

**The deliverable is a site**, not chat output: enter a CA, get the analysis,
plus live market information. ⭐ **From 2026-09-19 its centre is the tracked
universe** (Frank: *"all coins over $1M market cap tracked and the top trending
ones always visible"*): trending on top, narratives read off the universe, the
launch-side sections below the fold. `docs/CONSOLIDATION_PLAN.md` §8. Design toward one analyzer with two triggers —
`analyze(CA) -> report`, called both by the automatic crossing detector and by
Frank pasting an address. `check.py` already has that shape.
