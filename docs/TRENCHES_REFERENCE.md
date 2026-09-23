# The trenches: a working reference

Written 2026-09-16. Research only. **Nothing here was built, and no existing code was
touched.**

## What this document is, and what it is not

It is an outside view. Everything in `RULES.md`, `FRAUD_DETECTION.md`,
`TEMPLATE_ATTACK.md`, `VENUE.md`, `GAPS.md` and `CONTAMINATION.md` is assumed read and is
not restated. This document does three things those do not:

1. Defines the vocabulary **operationally** — for each term, the on-chain signature that
   lets you detect it, and whether we can currently get that signature.
2. Separates precursors to a move into **leading, coincident and lagging**, because most
   of what the trenches calls a "signal" is coincident and therefore useless for entry.
3. States the fraud taxonomy with **the numbers practitioners actually use**, and says
   plainly where no number exists.

### Honesty constraints applied

- Every factual claim carries a source and a date. Where practitioners disagree, both
  positions are given.
- Where a number could not be verified, it says so rather than supplying a plausible one.
  There are several of these and they are marked **[UNVERIFIED]**.
- Retail tooling (Bubblemaps, RugCheck, TrenchRadar) publishes thresholds that are
  *conventions*, not measurements. They are labelled as conventions. A convention with
  no published error rate has exactly the status that standing rule 10 assigns it.
- The Linux sandbox mount was broken on 2026-09-16 (Windows update, 2026-09-08; Plan9
  share not mounted). All repo reading was done with file tools. No shell was available
  and none was needed.

### The two questions

Everything below reduces to two questions asked in this order, which is standing rule 20
generalised:

    CAN I GET OUT?    — capability and counterparty. Binary. Checkable now.
    IS IT GOING UP?   — prediction. Probabilistic. Five attempts, five retractions.

The literature and the tooling both confirm the ordering. Nothing in this document
changes the standing conclusion that we have no validated answer to the second question.

---

# Part 1 — Terminology, defined operationally

Column key:

- **Signature** — what it looks like in data.
- **Ours?** — can we detect it today?
  `YES` = implemented. `FREE` = detectable with data we already fetch, not implemented.
  `CHEAP` = needs Helius calls inside the free tier. `HARD` = needs infrastructure we
  do not have. `NO` = not detectable with anything currently available.

## 1.1 Launch and venue mechanics

### bonding curve

A deterministic pricing contract holding *virtual* reserves. On pump.fun the curve is
seeded with 30 virtual SOL and 1.073×10⁹ virtual tokens against 0.7931×10⁹ real tokens;
buys move along a constant product. There is no counterparty and no liquidity to remove —
you are trading against a formula. Fee 1.25% per swap, 0.3% to the creator and 0.95% to
the protocol; launching costs the creator nothing.
Source: Marino, Naviglio, Tarantelli & Lillo, *Predicting the success of new
crypto-tokens: the pump.fun case*, arXiv:2602.14860, Feb 2026, §III.

**Why it matters to a buyer.** On a curve there is no "liquidity" in the AMM sense, so
every liquidity-based safety check is meaningless. Dexscreener reports
`liquidity.usd = 0` with no reserve split for curve pairs, which is correct behaviour and
not a data failure.

**Signature.** `dexId` in the curve set (pump-fun, meteora-dbc, launchlab, boop,
moonshot, believe, heaven, bags, bonk-fun …). **Ours? YES** — `venue.venue_type`.

### graduation / migration

The curve completes when **85 real SOL** have been deposited (115 SOL total virtual), and
the position is migrated atomically to a PumpSwap pool of (85 SOL, 2.069×10⁸ tokens).
Source: Marino et al. 2026, §III; pump.fun bonding-curve docs (retrieved 2026-09-16).

**The threshold is denominated in SOL, not USD.** This is the single most consequential
mechanical fact in this section and it is developed in Part 4. Implied graduation FDV:

    p_grad   = 85 / 2.069e8              = 4.108e-7 SOL per token
    FDV_grad = 1e9 tokens x p_grad       = 410.8 SOL
    at SOL $97.31 (2026-09-16)           ~ $39,978
    at SOL $102.30 (CoinGecko, same day) ~ $42,028
    the familiar "$69,000" implies SOL   ~ $167.90

Sources for SOL: OKX and CoinGecko spot, retrieved 2026-09-16.

**Ours? YES for the venue transition, WRONG for the threshold** — `GRADUATION_MCAP_USD`,
`BAND_HI` and `watchlist.GRADUATION_FDV` are all the constant `69000`.

### graduation rate

Three measured regimes, all from record-level data:

| window | rate | n | source |
|---|---|---|---|
| Q4 2024 | < 2% | — | Mancino, D., arXiv:2512.11850 (⛔ we credited "Mzoughi et al." until 2026-09-23; the author is Davide Mancino) |
| Sep–Oct 2025 | **0.63%** | 655,770 | Marino et al., arXiv:2602.14860 |
| ⛔ May–Jun 2026 | **0.198%** [0.189, 0.208] | 832,941 | ⛔⛔ **arXiv:2607.02823 v1 ONLY - SUPERSEDED by v4 (10 Sep 2026), which retitles to an AUDIT, uses n=749,816 and reports NO graduation rate. Do not publish.** See `data/findings/CITATIONS_2026-09-23.md` |

Kamat's steady-state figure excluding a four-day tracker warm-up is **0.207%**
[0.198, 0.218] on n=763,091. Kamat decomposes the 3.18× decline as substantially
compositional: launches with creator self-buy (initial mcap > 31 SOL) still graduate at
**0.634%**, almost exactly the 2025 pooled rate; the remaining 75% graduate at 0.053%.

**The "1–2%" number every blog repeats is three regimes stale.** Our own
`GRADUATION.md` figure of **0.22%** (30 of 13,709 mature contracts ever exceeding $69,000)
agrees with the current literature to within noise. Our `VENUE.md` figure of **2.10%**
(397 of 18,920 ever reaching $69,000 of *reported* liquidity) does not, and the reason is
almost certainly that it is computed on the Dexscreener `liquidity.usd` field that
`TEMPLATE_ATTACK.md` shows overstated by a median 781×. See Part 4.

### time to graduation

| statistic | Marino (Sep–Oct 2025) | Kamat (May–Jun 2026) |
|---|---|---|
| median | 4.4 min | **1.0 min** |
| p90 | — | 2.0 min |
| max observed | — | 5.0 min (5.98 on chain time) |
| median steps | ~457 curve swaps | — |

Kamat: *"any launch that does not clear the bonding-curve threshold within roughly five
minutes of detection effectively does not graduate."*

This is the strongest external confirmation of our own filed finding that discovery is a
"~1%-wide window at birth". It is stronger than ours because n=832,941.

### LP burn vs LP lock

- **Burned** — LP tokens sent to an unspendable address. Liquidity can never be removed
  by anyone, including the deployer. Irreversible.
- **Locked** — LP tokens held by a time-lock program. Removable when the lock expires.
  A lock is a promise with a date on it; a burn is a fact.

**On pump.fun graduations this is already settled: LP tokens are burned automatically at
migration to PumpSwap and liquidity cannot be pulled manually — the only way out is
trading.** Source: pump.fun Web Help Center, *Liquidity on PumpSwap*, retrieved
2026-09-16.

**Why this matters more than it looks.** For the pump.fun → PumpSwap population, which
is the bulk of what we observe, **the classical LP-pull rug is structurally impossible.**
The failure mode is not liquidity removal; it is *supply distribution* — insiders selling
into a burned pool until the quote side is gone. That is exactly what `exit_depth_usd`
measures, and it is the reason our instrument is the right one. It is also the reason
building an LP-burn checker would have been wasted work in our universe.

**Ours? N/A for PumpSwap, NO elsewhere.** `onchain_reserves.SWAP_V1` decodes `pool_mint`
at offset 99 but never reads its supply or authority, so for a fluxbeam or orca pool we
cannot currently say whether LP is burned.

### mint authority / freeze authority

Two fields on the SPL mint account. `mintAuthority` non-null means the deployer can print
supply into your bid. `freezeAuthority` non-null means the deployer can freeze your token
account so you cannot sell — **this is the Solana honeypot**, and it is the mechanism, not
a metaphor.
Source: Helius docs, *Find Solana Mint, Freeze, and Update Authority*; RareSkills,
*The Solana Token 2022 Specification* — both retrieved 2026-09-16.

**Signature.** `getAccountInfo(mint, jsonParsed)` → `info.mintAuthority`,
`info.freezeAuthority`. One free call.
**Ours? YES** — `onchain.authorities()`, hard disqualifier in `paper.qualifies()` and
`paperv2.qualifies()`, grade 0 in `scanner.surface_grade`, fail-closed on `None`.

**And near-worthless as a discriminator in our universe**, as `VENUE.md` already records:
227 of 228 have both revoked because launchpads revoke automatically. Keep it as a
disqualifier — it caught QUBT and PTN, both scoring 100 with both authorities live — but
it is a trap detector, not a feature.

### Token-2022 extensions / transfer hooks

The newer token program supports extensions that reintroduce seller-side control after
authorities are revoked. The ones that matter:

| extension | effect |
|---|---|
| `TransferHook` | arbitrary program runs on every transfer and can abort it |
| `Pausable` | issuer can halt all transfers |
| `DefaultAccountState = frozen` | new holder accounts start frozen; issuer whitelists |
| `PermanentDelegate` | a delegate can move or burn anyone's balance, forever |
| `TransferFee` | tax on transfer, can be set to confiscatory levels |

Source: Neodyme, *SPL Token-2022: Don't shoot yourself in the foot with extensions*;
RareSkills Token-2022 spec — retrieved 2026-09-16.

**Why it matters.** A Token-2022 mint with a live transfer hook and both classic
authorities revoked passes every check we currently run and is still a honeypot.

**Ours? NO — and this is a real hole.** `onchain.authorities()` reads only
`mintAuthority`, `freezeAuthority`, `decimals` and `supply` from the jsonParsed response
and has no notion of `extensions`. Cost to close: zero extra calls — the extension list is
in the response we already receive.

**[UNVERIFIED]** — what share of the Solana memecoin launch stream is Token-2022 rather
than classic SPL. I could not find a measurement. Our own corpus can answer it from data
already on disk.

## 1.2 Coordination and supply capture

### bundling / bundle buy

A **Jito bundle** is up to 5 transactions guaranteed to execute sequentially in the same
block (~400 ms slot), atomically, all-or-nothing. A "bundled launch" puts the mint and
the creator's buys from multiple wallets into one bundle.
Source: multiple bundler vendors, e.g. SolBundler *How to Bundle on Pump.fun* and
Alphecca *Pump.Fun Bundler Guide*, retrieved 2026-09-16; Jito's 5-transaction bundle limit
is the constraint they all work around.

**The structural point, which is not obvious and matters more than anything else in this
section:** because the mint and the insider buys are in the *same atomic bundle*, there is
**no latency at which an outsider can get in front of them**. This is not a race that can
be bought. Multi-wallet launches chain a primary bundle with follow-on bundles, and
vendors sell a "bundle + stagger" mode explicitly marketed as bypassing bundle detection.

**Signature, in order of strength:**

1. Token-creation instruction and ≥2 buy instructions in the **same slot** as the mint.
2. Buyer wallets funded from a **common ancestor** within a short window before launch
   (the funding graph is the part staggering cannot hide — the SOL has to come from
   somewhere).
3. Near-identical buy sizes across distinct wallets.
4. Those wallets subsequently selling within a narrow time window.

**Ours? HARD for (1), (3), (4); HARD for (2).** Nothing in the repo touches this. `grep -i
'bundl|snip'` across all `.py` returns exactly one hit, and it is a sentence of dashboard
prose (`dashboard.py:371`), not a check. It needs `getSignaturesForAddress` on the mint
plus per-transaction parsing, which `OPEN_ITEMS.md` already prices as "many calls per
token" and deliberately defers.

### coordinated accounts (the entity-linked view)

Stronger than bundling: accounts linked as one entity by funding and transfer traces,
regardless of whether they acted in the same block.

**The number that should change how you read every holder chart:**
across 41,000+ Solana launches and 200M+ transactions, **an average of 36.5% of token
supply is held by coordinated accounts.**
Source: Hu, Tekin, Xu & Liu, *MELT: A Behavioral Trace Dataset for High-Risk Memecoin
Launch Detection*, arXiv:2602.13480 v2, May 2026.

MELT is open: 122 behavioral features, bundle-trace data linking same-entity accounts,
risk annotations, code and data at `github.com/git-disl/MELT`. It is the single most
directly useful external artifact found in this research.

**Ours? NO.**

### sniped / sniper bots

Third-party bots buying at or immediately after launch, before discretionary buyers see
the token. Distinct from bundling: a sniper is an *outsider* competing with you; a bundle
is the *insider* pre-buying. **From a holder chart at t+1 minute they look identical, and
they mean opposite things.**

Industry claim, widely repeated and **not peer-reviewed**: by the time organic buyers see
a token, 3–5 bot wallets hold 40–60% of supply. Source: paragraph.com, *How to Launch a
Solana Memecoin Without Getting Sniped in 2026*, retrieved 2026-09-16. Treat as folklore
with a plausible shape, not a measurement.

Our own measurement — **>50% of new tokens sniped in the genesis block, sub-400 ms** — is
firmer than anything public I found. Note that 400 ms *is* one Solana slot, i.e. exactly
the Jito bundle window, which means our measurement as stated cannot distinguish an
external sniper from the creator's own bundle. See Part 4.

**Signature.** Buys in slot 0 or 1 from wallets with no prior history of buying this
creator's tokens, funded from unrelated sources.
**Ours? HARD.** `wallets.early_buyers()` takes the oldest 60 of 200 signatures on the
mint, which is "earliest transactors", not block-0 buyers, and it is wired into nothing.

### dev wallet / deployer

The address that signed the create instruction (`coin_creator` in the pump.fun program).

**The counterintuitive finding:** creator self-buy at launch is associated with a *higher*
graduation rate, not a lower one. Kamat's market-cap quartiles (n=832,941):

| initial mcap | n | graduation rate |
|---|---:|---|
| Q1 [1.39, 30.00) SOL | 326,691 | 0.0848% |
| **Q2 exactly 30.00 SOL (platform default)** | 91,247 | **0.0011%** — 1 in 91,247 |
| Q3 (30.00, 31.04] | 206,768 | 0.0256% |
| **Q4 > 31.04 SOL (creator self-bought)** | 208,235 | **0.6339%** |

Cox hazard ratio for `log(1 + mcap_sol)`: **4.506** [4.293, 4.729], p < 10⁻³⁰⁰.

So "dev bought his own coin" is not a red flag for *graduation*. It is a red flag for
*what happens after*, which is a different question and is not answered by this table.
Both can be true: self-buy predicts reaching the DEX and predicts having someone with a
large low-basis position standing over the pool once it gets there.

**Signature of the dev dump:** the creator address, or an address it funded, selling into
the pool. **Ours? NO.** No deployer identity is stored, no deployer history is looked up.
`OPEN_ITEMS.md` item 5 has this as the one genuinely open item and calls it "reportedly
the most predictive single feature". Nothing in the literature I found validates that
claim; Marino et al. tested only a "most prolific creator" indicator and the results
section was not retrievable.

### top-10 holder concentration

**Ours? YES, measured, surfaced only as a warning, never gated.** `onchain.concentration()`
returns `top1_share`, `top10_share`, `top10_share_ex_largest`, `largest_is_pool`; `TOP_N =
10`; `check.analyse` warns at `top1_share >= 0.50`. It is not persisted by
`journal.record()` and is in no qualify or score path.

The trap is already documented in `VENUE.md` and is worth restating because it is the
reason most public "top 10 hold 99%!" screenshots are noise:
`getTokenLargestAccounts` returns **the pool's own token account**, which on a fresh
launch holds nearly all supply. The 5% pool-match test in `onchain.concentration` is the
right correction and I found no public tool that applies it.

**Conventions (not measurements):** RugCheck flags top-10 > **15%** of supply as
danger-level. Source: Solana Tracker docs, *Token Safety & Rugcheck*, retrieved
2026-09-16. No published precision or recall accompanies it.

### fresh wallet clusters / bubble maps

A visualisation of the transfer graph among holders: nodes are wallets, edges are
transfers, and a tight cluster means one entity. "Fresh wallet" means an address with no
history before this token, which is what bundlers generate in bulk.

**Retail thresholds, from Bubblemaps' own guide** (retrieved 2026-09-16) — explicitly a
convention:

| bundled supply | reading |
|---|---|
| < 5% | normal; some sniping always happens |
| 5–15% | track whether those wallets hold or distribute |
| > 15% | serious — a coordinated cost-basis advantage over every later buyer |
| > 30% | pre-bought by insiders; avoid |

RugCheck uses `totalBundlerPercentage` > **20%** as a serious red flag.

**Read these against MELT's 36.5% entity-linked average.** Those bands measure the
*visible* same-block bundle. The entity-linked figure measures what staggering and
intermediary hops are designed to hide. A token showing 4% bundled can still be 40%
coordinated.

**Ours? NO.**

## 1.3 Fraud and failure modes

### rug pull — hard vs soft

- **Hard rug.** A capability is exercised: LP pulled, supply minted into the bid, sales
  frozen. Instantaneous, attributable, and on Solana requires a live authority or an
  unburned LP.
- **Soft rug.** No capability is exercised. The team stops, the insiders distribute, the
  pool bleeds out. Indistinguishable from failure, which is the point.

**On Solana, hard rugs are the minority and getting rarer**, because launchpads revoke
authorities and burn LP automatically. Li, Kuznetsov, Yanovich, Nott-Whaley & Vodolazov,
*Catching the Rug*, arXiv:2608.20271, 20 Aug 2026 (n = 6.4M tokens over 7 months) state it
directly: *"Unlike Ethereum, where rug pulls often exploit smart contract backdoors,
Solana memecoin rug pulls are predominantly driven by liquidity manipulation and social
dynamics."* They also report that **a vast majority of these memecoins exhibit rug-pull
characteristics within one hour of launch**, and that XGBoost on **the first 5 minutes of
trading data alone** achieves robust detection.

Scale, for context: Solidus Labs reports **98.7%** of pump.fun tokens and 93% of Raydium
pools showing pump-and-dump or rug characteristics; a separate analysis of pre-April-2025
pump.fun tokens with ≥5 trades found **98.6%** collapsed below $1,000 of remaining
liquidity. Sources retrieved 2026-09-16.

**Our position is already correct here and we should say so.** A capability check
(`paper.qualifies`) catches hard rugs. A counterparty check (`exit_depth_usd`,
`sells_h1 == 0`) catches soft rugs. We run both, in that order.

### honeypot

You can buy and cannot sell. On Solana the mechanisms are live freeze authority,
`DefaultAccountState = frozen`, a transfer hook that aborts sells, or `Pausable`. It is
**not** the Ethereum pattern of a sell-blocking `transfer()` override, because SPL token
logic lives in the token program, not the mint.

**Ours? PARTIAL — freeze authority YES, Token-2022 mechanisms NO.**

### one-sided pool / template pool

Ours, not general vocabulary. A pool holding essentially all of a token's supply against a
token amount of quote asset, priced so that `liquidity.usd` looks enormous. Detected by
`liq/fdv >= 0.95 AND sells_h1 == 0 AND buys_h1 >= 10`, validated at **100% precision
[85.7, 100] on 23 flags, 46.94% recall [33.7, 60.6]**, `FRAUD_DETECTION.md` 2026-09-07.

I searched for prior art and **found none**. No published tool, paper or vendor describes
the template-constant fingerprint or the `liq/fdv` conjunction. On the evidence available
this detector is genuinely ours and is ahead of the public state of the art. That is the
one claim in this document where we are the source.

### wash trading / volume bots

Self-dealing to manufacture volume, usually to buy placement on Dexscreener trending.

**Documented case, Bitquery, retrieved 2026-09-16:** one operator seeded **200 bot wallets
with exactly 0.5 SOL each in 52 seconds**; token OpenLie reported **$532,461 of DEX volume
in 12 hours from 233 wallets across 40,523 trades.**

**Published detection heuristics:**

| heuristic | threshold | source |
|---|---|---|
| volume up, price flat | volume > **+500%** d/d with absolute price change < **5%** | Bitquery |
| trades per trader | high ratio; 40,523/233 ≈ **174 trades per wallet** in the case above | Bitquery |
| uniform trade size | near-zero variance in USD size across wallets | Bitquery |
| identical funding amount | N wallets funded with the exact same SOL amount | Bitquery |

Cross-chain, Mongardini et al., *A Midsummer Meme's Dream*, arXiv:2507.01963 (USENIX
Security '26), n=34,988 tokens across 4 chains: **82.89% of tokens returning >100% show
evidence of artificial growth strategies** — wash trading or "Liquidity Pool-Based Price
Inflation", where small strategic buys against a thin pool produce large price prints.
Over 17,000 victim addresses, >$9.3M realized losses.

**That 82.89% figure is the most important single number in this document for anyone
trying to predict runs.** Most things that go up >100% went up because someone made them
go up.

**Ours? PARTIAL and inverted.** `scanner.CFG` has `max_vol_liq_ratio = 40` and
`max_buy_sell_ratio = 6.0` ("too clean, likely bot-driven"). Both are magnitude tests on
aggregates. We have no per-wallet view, so we cannot apply any of the four heuristics
above. Note also that LPI is *our* template attack described from the outside — a thin
quote side producing a large price print is precisely what `exit_depth_usd` refuses.

### vamping / vampire attack

**Contested, and I am not going to pretend otherwise.** Three usages are in live
circulation as of 2026-09-16:

1. **Classic DeFi** — a protocol incentivises another protocol's LPs to migrate
   (SushiSwap/Uniswap, 2020). Source: Coinbase glossary.
2. **Ticker vamping** — a copy of a successful token's ticker and narrative launched on
   another chain or launchpad, draining attention and flow from the original. The Defiant,
   *Memecoin 'Vampire Attacks' Increase*, documents $MOODENG and $NEIRO being recreated on
   Ethereum days after their Solana launches, often self-labelled as community takeovers.
3. **Launchpad vamping** — one launchpad taking share from another. Tooling exists that
   markets "vamping" a coin as a product feature ("create & vamp meme coins in under 5
   seconds").

For our purposes usage (2) is the operative one and it overlaps almost completely with
**ticker squatting**: minting a token with a ticker that already has attention. It is not
fraud in the capability sense — nothing is stolen — and it is not detectable from any
single token's data. It is detectable from the *index*.

**Ours? FREE, and partly built.** `tickers.note()` already records how many contracts
share a normalised symbol, and we have measured **57.9% of tokens share a ticker with
another; FLORK alone has 25 distinct contracts.** What we do not do is order them by time
— "is this the first contract with this ticker or the ninth?" is a one-line query over
data we hold, and it is the actual vamping signal.

### ticker squatting

See above. Additional case: claiming an incumbent's name outright. `tickers.impersonation`
handles this against a 41-name incumbent list, and `namecheck.check` handles Unicode
lookalikes and bidi tricks with a score-zeroing veto. Measured: flagged n=41 at 2.4% ≥2x
[0.4, 12.6] vs clean n=1,152 at 4.8% [3.7, 6.2]. **Intervals overlap; not established.**

### CTO — community takeover

Holders of an abandoned token organise, take over socials, and continue promoting it
without the original creator. Sources: CoinMarketCap Academy glossary; crypto.news,
*What is a community takeover (CTO)*, retrieved 2026-09-16.

**What it means to a buyer:** a CTO is, mechanically, a token whose original deployer has
already sold and left. The insider overhang is gone, which is genuinely different from a
live launch. It is also a narrative that any deployer can simply assert. Decrypt
(*Meme Coin Takeover Teams Face Legal Entanglement*) notes the label is increasingly
applied by parties with an economic interest in it.

**Signature.** Deployer balance near zero, no deployer sells for an extended period,
socials handed over, and — the honest tell — a pool that is still two-sided long after
launch. **Ours? CHEAP**, via deployer balance, which we do not read.

### larp

Claiming to be someone or something you are not: a fake team, a fake partnership, a fake
CEX listing, a fake KOL endorsement. Unverifiable on-chain by construction. The
corresponding on-chain question is not "is the claim true" but "who benefits if you
believe it", which resolves back to concentration and coordination.

### PvP

The trenches' own description of a zero-sum regime: no new money entering, participants
extracting from each other, every launch a transfer from later buyers to earlier ones.
Source: SolanaFloor, *Traders Blame 'PvP Culture' for Solana's Languishing Memecoin
Market*. It is a sentiment term with no crisp on-chain definition, but it has an
observable correlate: **falling graduation rate with flat or rising launch count.** Kamat's
3.18× decline from 2025 to 2026 against a still-enormous launch stream is that correlate.

### "the trenches"

Trading tokens minutes old on Solana launchpads, against opponents that include automated
bots. A war metaphor, used without irony. Sources: crypto.news and Tiger Brokers guides,
retrieved 2026-09-16.

---

# Part 2 — What actually makes a coin run

## 2.1 The test a signal has to pass

A signal is **leading** only if both of these hold:

1. It is observable strictly before the move, using only past information.
2. **The price has not already adjusted for it.**

Condition (2) is the one everybody skips, and there is now a formal result about it.

### The breakeven result, and why it is the most important finding here

Marino et al. (arXiv:2602.14860, Feb 2026) compute the probability of graduation
conditional on the curve having reached a given level of deposited SOL, `p_std(vSol)`, on
655,770 tokens. A naive buy-at-`vSol`, sell-at-graduation strategy is profitable iff

    p(vSol) > vSol² / 115²

They find **`p_std(vSol)` lies below that curve** over essentially the whole range.

Read that plainly: **even with a perfect, exact, free estimate of the probability that a
token will graduate, buying it and holding to graduation loses money.** The probability
rises with the curve level, but the price you pay rises faster. Conditioning on the best
single feature they have (high non-bot share, θ=0.3) lifts the curve but only *approaches*
breakeven, and only near the threshold. Fees are excluded from their calculation, which
makes the real picture worse, not better.

This is the cleanest available answer to the open question in `QUESTIONS.md`, *"Can any
entry rule be supported at all?"* — for the specific family of rules that key on where a
token sits on its curve, the answer is a measured no, on n=655,770. It says nothing about
rules keyed on anything else.

It also generalises. Any feature that the market can also see is priced into the curve
level by the time you can act on it. The only features that can survive are ones that are
**visible at launch, before there is a price**, or ones that are **expensive enough for
others to ignore**.

## 2.2 The classification

### Leading — observable before, and not yet in the price

| signal | effect | n | when observable | source |
|---|---|---:|---|---|
| **Telegram link in launch metadata** | 1.485% vs 0.166% graduation, **8.94× lift**; Cox HR **5.402** [4.733, 6.166], p = 6.8×10⁻¹³⁸ | 832,941 | **at creation** | Kamat 2026 |
| **All three socials (X + site + Telegram)** | 1.919% vs 0.110%, **17.4× lift** | 832,941 | **at creation** | Kamat 2026 |
| Website link | 0.264% vs 0.158%, HR 1.194 | 832,941 | at creation | Kamat 2026 |
| X/Twitter link | 0.227% vs 0.149%, HR 1.305 | 832,941 | at creation | Kamat 2026 |
| **Initial mcap > 31.04 SOL (creator self-buy)** | **0.634%** vs 0.053% for Q1–Q3; HR on log mcap **4.506** | 832,941 | **at creation** | Kamat 2026 |
| **Initial mcap exactly 30.00 SOL (default)** | **0.0011%** — 1 graduation in 91,247 | 91,247 | **at creation** | Kamat 2026 |
| Description length | HR 1.054 [1.034, 1.076] | 832,941 | at creation | Kamat 2026 |
| **Few trades to reach a given curve level** | *"the strongest predictor of graduation, dominating other variables across the entire range of vSol"* — effect size not retrievable, see caveat | 655,770 | live, causal | Marino et al. 2026 |
| High non-bot share of trades so far (τ) | both θ=0.3 and θ=0.7 curves sit systematically above baseline; **saturates** between them | 655,770 | live, causal | Marino et al. 2026 |
| First-5-minutes trade pattern | XGBoost achieves "robust performance" on rug detection; no precision/recall retrievable from the abstract | 6.4M tokens / 7 months | t + 5 min | Li et al. 2026 |

The Kamat features are the striking ones because they cost nothing and are known **before
the first trade**. Cox concordance for the full five-covariate model is **0.858**.

**Three caveats that must travel with that table.**

1. **All of it predicts graduation, not appreciation.** Marino is explicit that
   graduation *"does not guarantee long-run viability or economic value"*, and Kamat is
   explicit that the elevations are *"predictive and useful for filter calibration, not
   actionable trading signals without further out-of-sample validation."* Our own
   `VENUE.md` measurement is the sharp version: curve-first tokens return ≥2x at
   **0.01% — two wins in 14,802.**
2. **No out-of-sample validation exists in either paper.** Marino uses empirical
   conditional frequencies over the full sample and states there is no train/test split
   and no AUC. Kamat fits Cox on the full sample. By standing rule 14 these are
   retrospective findings, which is the category that has killed five of our own results.
3. Kamat declines to claim causality for the social effect and offers three competing
   readings — effort proxy, discoverability, selection. For filter purposes it does not
   matter which; for anything else it does.

### Coincident — moves with the price, so you are paying for the information

| signal | why it is coincident |
|---|---|
| holder-count velocity | new holders *are* the buys that are moving the price |
| volume, volume/liquidity | same |
| buy/sell imbalance | same |
| FDV or market cap level | a monotone function of the price |
| Dexscreener / Axiom trending placement | computed *from* volume, published on a lag, and directly purchasable — see the OpenLie case, $532,461 of volume from 233 wallets |
| KOL posts | the post is the move; and a paid post is a cost the poster recovers from your fill |
| the graduation event itself | median 1.0 min after launch, p90 2.0 min — by the time it is in any feed, it has happened |

None of these are useless. They are the correct inputs to *abandon* decisions, which is
exactly the surviving fragment of our retracted liquidity-trajectory finding: falling
liquidity gave 0.3% forward ≥2x across 969 rows. **Use coincident signals to get out;
never to get in.**

### Lagging

CEX listing announcements; 24h volume; aggregated hourly social mention counts; any
"holders" figure quoted as a level rather than a rate; our own 1h/6h/24h outcome checks.
CEX *rumours* deserve a separate line: they are unverifiable by construction, they are the
most commonly fabricated larp, and there is no on-chain signature for one.

## 2.3 Narrative and meta timing

The honest state of this is worse than the folklore suggests.

- Our own `X_API.md` concluded that a social feed is not the binding constraint — our
  polling cadence is — and that the best narrative in our record (the 2026-08-27
  Chinese-language wave) would have been missed by an English crypto-Twitter feed anyway.
  **The launches were the signal.**
- `clusters.py` already implements the launch-side version of narrative detection, and our
  own measurement is that **clusters of 10+ tokens produced zero winners across 418
  tokens.** Cluster size is not a quality signal and the code correctly refuses to present
  it as one.
- What has *not* been tested is cluster **ordering** — whether being an early member of a
  cluster that later grows differs from being the fortieth. That is a different question
  from cluster size, it is answerable from data already on disk, and it is the shape the
  ticker-vamping signal would take.

## 2.4 The uncomfortable summary

**82.89% of tokens returning more than 100% show evidence of artificial growth
strategies** — wash trading or liquidity-pool price inflation (Mongardini et al.,
arXiv:2507.01963, USENIX Security '26, n=34,988 across four chains).

So the modal answer to "what makes a coin run" is: **someone made it run, deliberately,
and the run is the extraction.** Any predictor of large returns is therefore substantially
a predictor of *who is being manipulated next*, which is a legitimate thing to model and a
very different thing from what the word "signal" usually implies.

## 2.5 What I could not verify

Stated so that nobody later mistakes silence for evidence.

- **[UNVERIFIED] Holder-count velocity as a leading indicator.** I found no credible
  measurement — no paper, no dataset, no vendor publishing an error rate. It is asserted
  constantly and measured nowhere I could find.
- **[UNVERIFIED] KOL attention as a leading indicator.** Same. No measured lead time, no
  base rate, no controlled comparison. The one adjacent measured fact is Kamat's social-
  *link* result, which is about the token's own metadata, not about third-party attention.
- **[UNVERIFIED] Volume-to-liquidity ratio thresholds.** Our `CFG` uses 0.35 and 40. I
  found no external source for either. They are ours and they are unvalidated.
- **[UNVERIFIED] CEX-listing rumours.** No on-chain signature, no published base rate.
- **[UNVERIFIED]** Share of the launch stream that is Token-2022 rather than classic SPL.
- **[NOT RETRIEVABLE]** Marino et al.'s effect sizes for trade count, smart money and
  creator identity. Their §VII.B onward and the whole Shewhart dump-detection section
  did not come back in either fetch. The qualitative claims quoted above are from their
  abstract and introduction. **If one thing from this research is worth a second pass, it
  is getting those figures**, because trade count is the feature they call dominant.

---

# Part 3 — The fraud taxonomy, with numbers

## 3.1 The decision order

Capability first, counterparty second, magnitude last. This is standing rule 20 and the
external evidence supports it.

| # | question | check | our status |
|---|---|---|---|
| 1 | Can the deployer print supply? | `mintAuthority` non-null | **YES**, hard disqualifier |
| 2 | Can the deployer stop the sale? | `freezeAuthority` non-null | **YES**, hard disqualifier |
| 3 | Can the deployer stop the sale *another way*? | Token-2022 `TransferHook`, `Pausable`, `DefaultAccountState`, `PermanentDelegate` | **NO** |
| 4 | Can liquidity be pulled? | LP mint supply / burn address | **N/A on PumpSwap** (auto-burned); **NO** elsewhere |
| 5 | Has anyone ever sold? | `sells_h1 == 0 && buys_h1 >= 10` | **YES**, hard disqualifier |
| 6 | Is there a second side at all? | `exit_depth_usd` from the quote reserve | **YES**, floor $1,000 |
| 7 | Who holds it, really? | entity-linked supply share | **NO** |
| 8 | Was it bundled at launch? | mint + buys in the same slot | **NO** |
| 9 | Is the volume real? | per-wallet trade distribution | **NO** |

Checks 1, 2, 5 and 6 are implemented and load-bearing. Checks 3, 7, 8 and 9 are absent.
That is the map of the hole.

## 3.2 Thresholds people actually use

**Conventions.** None of these is published with a precision or recall figure. By standing
rule 10 none of them is allowed to filter anything here until it has one.

| pattern | threshold | source | date |
|---|---|---|---|
| bundled supply, safe | < 5% | Bubblemaps guide | ret. 2026-09-16 |
| bundled supply, watch | 5–15% | Bubblemaps | ret. 2026-09-16 |
| bundled supply, serious | > 15% | Bubblemaps | ret. 2026-09-16 |
| bundled supply, avoid | > 30% | Bubblemaps | ret. 2026-09-16 |
| `totalBundlerPercentage` red flag | > 20% | RugCheck via Solana Tracker docs | ret. 2026-09-16 |
| top-10 holders, danger | > 15% of supply | RugCheck via Solana Tracker docs | ret. 2026-09-16 |
| wash-trade pattern | volume > +500% d/d **and** abs price change < 5% | Bitquery | ret. 2026-09-16 |
| Jito bundle size | ≤ 5 transactions, 1 slot (~400 ms) | Jito / multiple bundler vendors | ret. 2026-09-16 |

**Measurements.** These have an n behind them.

| fact | value | n | source |
|---|---|---:|---|
| average supply held by entity-linked coordinated accounts | **36.5%** | 41k+ launches, 200M+ tx | MELT, arXiv:2602.13480 |
| tokens >100% return showing artificial growth | **82.8%** | 34,988 | arXiv:2507.01963 (⚠️ we quoted 82.89%; the paper says 82.8%) |
| pump.fun tokens showing pump-and-dump / rug characteristics | **98.7%** | — | Solidus Labs |
| pump.fun tokens (pre-Apr 2025, ≥5 trades) collapsing below $1,000 liquidity | **98.6%** | — | cited via BloFin, ret. 2026-09-16 |
| memecoins exhibiting rug characteristics **within one hour of launch** | "vast majority" | 6.4M / 7 months | arXiv:2608.20271 |
| ⛔ graduation rate, May–Jun 2026 | **0.198%** [0.189, 0.208] | 832,941 | ⛔⛔ arXiv:2607.02823 **v1, SUPERSEDED** - see `data/findings/CITATIONS_2026-09-23.md` |
| our one-sided-pool detector, precision | **100% [85.7, 100]** at 46.94% recall | 23 flags / 826 labelled | `FRAUD_DETECTION.md` |

Note the shape of that list. **The external numbers are all prevalence; ours is the only
precision figure in it.** That is not because the field is careless — it is because
labelling requires reserves, and reserves are what almost nobody measures.

## 3.3 Pattern library

### Bundled launch
Mint + N buys atomic in one slot. **Unbeatable by latency** — the insider transaction is
in the same atomic unit as the mint. Staggered variants exist and are sold as a feature.
Residual signature after staggering: the **funding graph**, because the SOL must come from
somewhere.

### Sniped launch
External bots buying in slot 0–1. Competes with you; does not imply the creator is
hostile. Indistinguishable from a bundle on a holder chart.

### Honeypot
Buy works, sell reverts. Freeze authority, transfer hook, `Pausable`, or
`DefaultAccountState = frozen`. Detectable from one `getAccountInfo` call **if you read
the extensions**, which we do not.

### Hard rug
A capability exercised. Rare on launchpad tokens because authorities are auto-revoked and
LP is auto-burned.

### Soft rug / slow bleed
Insiders distribute into a burned pool until the quote side is dust. **This is the modal
failure in our universe**, it looks identical to honest failure, and the only thing that
separates it at the moment of the trade is *how much quote side there is to sell into*.

### Template / one-sided pool
Ours. See `TEMPLATE_ATTACK.md`. `depth/liq ≈ 0.00796`, overstated by a median 781×. Drift
check 2026-09-14 put the constant at 0.00804 (n=35, IQR 0.00793–0.00810), so it has not
moved. `FEASIBILITY.md` is right that a detector with no drift monitor has an unknown
expiry date; the monitor exists, which is more than the public tooling has.

### Wash-traded pump
Manufactured volume to buy trending placement, then real buyers arrive. 200 wallets, 0.5
SOL each, 52 seconds. Then LPI: small buys against a thin pool producing large price
prints — which is the template attack described by someone who was looking at prices
instead of reserves.

### Pump-and-dump on a graduated pool
LP is burned so nothing can be pulled; the extraction is the insiders' 36.5% hitting a
pool sized for retail. Our two 2m49s target closes (Oiled, titcoin) with pools under $1
nine minutes later are exactly this, and they are why `FRAUD_DETECTION.md` calls a
two-minute target a quote rather than a fill.

---

# Part 4 — What this changes about what we built

This is the section that matters. Four buckets: what is well founded, what is naive, what
is missing entirely, and what is **wrong**.

## 4.0 First, the fraud detector: what it covers and what it does not

Stated plainly because it is the one proven asset and it should not be oversold.

**What D1 covers.** A pool whose reported liquidity is essentially the token's own supply,
into which many people have bought and nobody has sold. `liq/fdv >= 0.95 && sells_h1 == 0
&& buys_h1 >= 10`. Validated against reserves: **23 flagged, 0 false positives, precision
≥ 85.7% at 95% confidence, recall 46.94% [33.7, 60.6]** on n=826 labelled observations.
Independently corroborated by a second mechanism (source disagreement) on the fluxbeam
template, and carrying a drift monitor on the 0.00796 constant.

I searched for prior art on this and found none. No paper, vendor or open tool I could
find measures the base/quote reserve split to detect an overstated pool. Mongardini et al.
name the *phenomenon* — "Liquidity Pool-Based Price Inflation" — without building the
instrument. **On the available evidence, D1 is genuinely ahead of the published state of
the art, and the reason is that we measure reserves and almost nobody does.**

**What it does not cover, in order of how much it matters:**

| not covered | why it is out of reach of D1 |
|---|---|
| **The other ~53% of one-sided pools** | by construction — 46.94% recall |
| **Any pool where someone has sold** | `sells_h1 == 0` is a hard term of the conjunction. A wash-traded pool with fake sells is invisible to it |
| **Coordinated ownership** | D1 sees the pool, never the holders. A perfectly two-sided pool where one entity holds 36.5% of supply passes cleanly |
| **Bundled launches** | same — no wallet-level view at all |
| **Token-2022 honeypots** | we never read the extensions |
| **Anything on a bonding curve** | no reserves to split; `liquidity.usd = 0` by design |
| **Venue generality** | unresolved. `PRECOMMIT-VENUE.md` records that 33 of 38 D1 flags are fluxbeam and that `dex_id == fluxbeam` alone scores 100% [90.1, 100] at 46.7% recall. **Until the non-fluxbeam test reads out at n≥20, "fraud detector" and "fluxbeam detector" are not distinguished.** Nothing in this research settles it |

**And the thing it was never meant to do:** D1 does not make money. It makes the record
honest. `FRAUD_DETECTION.md` already says this; the external literature gives no reason to
revise it.

## 4.1 Well founded — keep, and stop apologising for

1. **`exit_depth_usd` as a quote-side-only measure.** Standing rule 8. The outside world
   has the phenomenon (LPI, 82.89% of >100% returns) and does not have the instrument. This
   is the most defensible thing in the repo.
2. **Capability before magnitude** (rule 20 / `paper.qualifies` ordering). Matches the
   structure of the rug literature exactly: hard rugs are capability, soft rugs are
   counterparty, and magnitude is neither.
3. **Mint/freeze as hard disqualifiers, failing closed on `None`.** Near-zero variance —
   227 of 228 revoked — and still correct, because QUBT and PTN both scored 100 with both
   live. A zero-variance feature is a bad *score* term and a fine *veto*.
4. **Splitting curve from AMM before any analysis** (rule 9). Marino et al.'s entire paper
   is about the curve as a distinct object with distinct mechanics. Our 227× split is the
   same fact measured from outcomes.
5. **Refusing to infer depth from GeckoTerminal's `total_reserve_in_usd`**
   (`resolve._geckoterminal` returns `None` deliberately). GT has no reserve split. The
   template case showed GT still overstating by ~17× where Dexscreener overstated by ~540×.
   Returning `None` is the right answer and almost nobody gives it.
6. **`namecheck`'s bidi / Cyrillic-lookalike veto.** I found no public Solana tool that
   checks for reversed-display or bidi control characters in symbols.
7. **`clusters.py` refusing to rank on cluster size.** Zero winners in clusters of 10+
   across 418 tokens; the docstring says so and the code does not present size as quality.
   Compare the published work, which routinely ships models without a train/test split.
8. **`MIN_N = 30` and `WITHHELD`.** Marino et al. report in-sample conditional frequencies
   with no held-out set and no AUC; Kamat fits Cox on the full sample. Our reporting
   discipline is stricter than both papers'.

## 4.2 Naive — works, but the number has no provenance

1. **All nine constants in `scanner.CFG`.** `min_liquidity_usd = 8_000`,
   `max_vol_liq_ratio = 40`, `min_vol_liq_ratio = 0.35`, `max_buy_sell_ratio = 6.0`,
   `min_txns_h1 = 25`, and the rest. I looked for external support for any of them and
   found none. They are house numbers. That is not fatal — the score is not the product —
   but they should be labelled as house numbers wherever they are quoted.
2. **The two wash-trading checks are aggregate; the discriminating information is
   per-wallet.** `vol/liq > 40` and `buy/sell > 6.0` are magnitude tests on Dexscreener
   aggregates. The published heuristics that work are distributional: trades per wallet
   (the OpenLie case is 174), uniform trade size, identical funding amounts. The one
   aggregate test with published support — **volume up >500% d/d with absolute price change
   <5%** — we do not have, and we could not currently compute it anyway because we rarely
   observe the same token twice.
3. **`age_hours` is pair age, not token age**, which already cost one withdrawn gate. Worth
   restating in this context: every external study keys on **token creation time from the
   program**, which is unambiguous and free. Dexscreener's `pairCreatedAt` is a different
   quantity and there is no way to make it mean what we want. `plausibility.assess`'s
   `MAX_YOUNG_H = 1.0` branches carry the same defect.
4. **`check.analyse`'s `top1_share >= 0.50` warning.** Unsourced. The public convention is
   top-**10** > **15%** of supply. Ours is a different statistic at a ~3× looser level.
   Keeping it as a warning rather than a gate is correct under rule 10; the threshold
   itself should carry a "house number" label.
5. **The 70–99 score band in `RULE_V1`.** Post-epoch, score 100 is the best band by rate
   and lift (1.95% [0.90, 4.20], 8.31×) and 70–99 has n=73. This is already logged. The
   external addition is only that no published work supports a composite score of
   magnitude features as an entry criterion — Marino's result is that the best-known
   magnitude feature does not clear breakeven.

## 4.3 Missing entirely — ranked by (measured value) ÷ (cost)

### 1. Social links. Zero API cost. Largest published predictor. **We do not read them.**

Dexscreener's token payload — the one `S.dexscreener_token` already fetches on every
enriched row — carries `info.socials` and `info.websites`. We never touch them. `grep`
confirms: no read of either field anywhere in the repo.

Kamat, n=832,941: Telegram alone **8.94× lift** (1.485% vs 0.166%), Cox **HR 5.402**;
all three channels **17.4× lift** (1.919% vs 0.110%).

This is the single largest gap found in this research. It costs **zero additional calls**,
it is a launch-time feature so there is no leakage risk of the kind that killed the
liquidity gradient, and under rule 10 the correct first step is to **record it and score
nothing** until n≥30 forward closes exist. `QUESTIONS.md` already has "do linked socials
outperform?" as an open question. It is open because we never wrote the field down.

### 2. Token-2022 extensions. Zero API cost. Closes a live honeypot hole.

`onchain.authorities()` parses `mintAuthority`, `freezeAuthority`, `decimals`, `supply`
from a `getAccountInfo(jsonParsed)` response that **also contains the extension list**. A
mint with a live `TransferHook`, `Pausable`, `DefaultAccountState = frozen` or
`PermanentDelegate` passes every check we run and is still unsellable. Same call, more
fields.

### 3. Token age, from the program rather than from Dexscreener.

Unblocks the whole family of age-keyed rules that `age_hours` poisoned.

### 4. Deployer identity. We do not even store it.

`coin_creator` is in the pump.fun program data and the mint's oldest signature gives it
for anything else. **Store the address now; do the history later.** `OPEN_ITEMS.md`
correctly defers deployer *history* as expensive and survivorship-prone. Storing the
address is neither, and nothing can be measured later that was not recorded now.

Caution from the literature: the one deployer-adjacent thing that is measured points the
*opposite* way from the folklore — creator self-buy raises graduation odds (HR 4.51), and
a launch left at exactly the 30.00 SOL default graduates once in 91,247.

### 5. Entity-linked holder analysis — and do not build it from scratch.

**MELT** (arXiv:2602.13480, `github.com/git-disl/MELT`) is an open, licensed dataset of
41k+ launches, 200M+ transactions, **bundle-trace data linking same-entity accounts**, 122
behavioral features and risk annotations. It is a labelled set of exactly the kind rule 10
demands and that we have spent months unable to build. Using it as ground truth is a
research task, not an infrastructure task.

### 6. Per-wallet trade distribution, for wash detection.

Needs `getSignaturesForAddress` on the mint plus parsing. This is the expensive one and it
should be last.

### 7. Ticker recency ordering. Free, and half-built.

`tickers.note()` already records how many contracts share a symbol. It does not record
*rank in time*. "Is this the first contract with this ticker or the ninth" is the actual
vamping / ticker-squatting signal, it is a query over data on disk, and it is untested.

## 4.4 Wrong — fix these

### W1. The graduation threshold is 85 SOL, not $69,000. Our approach band sits above it.

`GRADUATION_MCAP_USD = 69000` (venue.py), `GRADUATION_FDV = 69000` and
`BAND_HI = 69000` / `BAND_LO = 45000` (watchlist.py) encode a **USD** constant against a
**SOL-denominated** mechanism.

    curve completes at 85 real SOL; PumpSwap pool seeded (85 SOL, 2.069e8 tokens)
    p_grad   = 85 / 2.069e8        = 4.108e-7 SOL/token
    FDV_grad = 1e9 x p_grad        = 410.8 SOL
      at SOL $97.31  (OKX,       2026-09-16)  ~ $39,978
      at SOL $102.30 (CoinGecko, 2026-09-16)  ~ $42,028
    the $69,000 constant implies SOL ~ $167.90

**If this is right, the $45,000–$69,000 approach band lies entirely above the point at
which graduation happens, which is a complete explanation for why it is empty.**

Our own data corroborates it without any external input. `FEASIBILITY.md` records the
bonding-curve FDV distribution as median $2,938, p75 $3,147, **p95 $42,616**. That p95
lands on the computed graduation FDV almost exactly. The band begins $2,384 *above* the
95th percentile of the entire curve population.

The filed explanation — "the window is roughly 1% wide and it sits at birth" — is also
true and is supported by Kamat's 1.0-minute median. **Both can be true. Only one of them
is a bug.**

**Verification that requires building nothing:** take the 86 witnessed curve→AMM
transitions already in the corpus and read FDV at the transition. Median near $40,000
confirms; median near $69,000 refutes and this item is withdrawn. That is a query, not a
feature.

**And the fix requires no code change either**, which is worth knowing before anyone
reaches for an editor. All three constants are already environment-overridable:

    venue.py:65      GRADUATION_MCAP_USD = float(os.environ.get("CRYPTO_GRADUATION_MCAP", "69000"))
    watchlist.py:49  BAND_LO             = float(os.environ.get("CRYPTO_APPROACH_LO",     "45000"))
    watchlist.py:50  BAND_HI             = float(os.environ.get("CRYPTO_APPROACH_HI",     "69000"))
    watchlist.py:51  GRADUATION_FDV      = venue.GRADUATION_MCAP_USD

One caveat for whoever does it: `dashboard.py:185` carries a **hardcoded** `(45000, 69000)`
fallback that does not read the env vars, so a band moved by environment would still be
displayed at the old numbers on the error path. Changing any of this is a pre-committed
rule change and belongs in a `PRECOMMIT_` file, not in a config tweak.

**Second-order consequence, which is the durable lesson:** any USD threshold against a
SOL-denominated mechanism drifts silently with the SOL price. Nothing alarms. Express it
in SOL, or recompute it per pass from a price we already fetch for
`onchain_reserves.quote_price_usd`.

### W2. Our two graduation base rates differ by 9.5× and one of them is probably the contaminated field.

- `VENUE.md`: **2.10%** — 397 of 18,920 ever reached $69,000 of **reported liquidity**.
- `GRADUATION.md`: **0.22%** — 30 of 13,709 mature contracts ever exceeded $69,000
  liquidity.

They look like the same measurement and they disagree by 9.5×. The external anchor is
**0.198% [0.189, 0.208]** on n=832,941 (Kamat, Jun 2026) and **0.63%** a regime earlier
(Marino, Oct 2025). `GRADUATION.md` agrees with the literature; `VENUE.md` does not.

The likely mechanism is the one the repo already documented: "reported liquidity" is
Dexscreener's `liquidity.usd`, the field shown overstated by a median **781×** on
template pools. A threshold test on an overstated field over-triggers.

This is not cosmetic. **2.10% is used as a base rate, and every lift figure computed
against it is potentially an order of magnitude too small.** The brief for this research
cited 2.10% as the measured base rate; on this evidence it should probably be ~0.2%.
Reconciling the two is a query.

### W3. ">50% sniped in the genesis block, sub-400 ms" may be a bundling measurement wearing a sniping name.

**400 ms is one Solana slot, which is exactly the Jito bundle window.** A buy landing in
the *same slot* as the mint cannot have been placed by an outsider reacting to the mint —
an external sniper must observe the creation first, which costs at least a block. A
same-slot buy is overwhelmingly likely to be **the creator's own bundle**, because that is
the only way to be atomic with the mint.

If that is right, the finding inverts:

| read as | means | implication |
|---|---|---|
| snipers beat us | a speed problem | unfixable; stop |
| **creators bundle their own launches** | **a fraud signal** | **a detector we already have the measurement for** |

These are opposite conclusions from the same data, and one of them is a competitive wall
while the other is an asset. **Distinguishing them requires one thing: for a same-slot
buy, is the buyer wallet funded by, or transacting with, the creator wallet.** That is
cheap on a per-token basis and it would convert a "we cannot compete" finding into a
prevalence measurement of bundling on our own sample — which nobody outside MELT has
published.

Stated honestly: I did not independently verify the >50% / sub-400 ms figure. It came
with the brief. This item is a reinterpretation of it, not a challenge to it.

**It is also load-bearing in public.** `dashboard.py:371` renders the claim to the reader
as settled fact:

> *"Post-graduation is the one door still open — launch sniping is closed (>50% of tokens
> are taken in the genesis block, sub-400ms)."*

That sentence is the repo's only mention of sniping anywhere in code, it is user-facing,
and it draws a strategic conclusion ("the one door still open") from a measurement whose
interpretation is ambiguous in exactly the way described above. If the same-slot buys are
mostly creator bundles, the sentence is asserting a wall that is really a fingerprint. It
should carry the ambiguity until the funding-graph question is answered.

### W4. The cost figure for competing infrastructure is high, and the conclusion stands anyway.

The brief cites competing infrastructure at **$499–4,000/month**. Entry-level Yellowstone
gRPC / Geyser streaming is cheaper than that: **Chainstack from $49/mo**, **Shyft from
$199/mo**, **rpc edge Trader from $249/mo**, Triton One from a $125 prepaid deposit; all
retrieved 2026-09-16. Sub-50 ms streaming is not a four-figure product.

**And it does not matter, because the wall is structural rather than financial.** A
bundled launch puts the mint and the insider buys in one atomic Jito bundle in one slot.
There is no latency — at $49/month or at $40,000/month — that gets an outsider in front of
a transaction that is in the same atomic unit as the mint. The recommendation not to
compete on launch speed is correct, and it is correct for a better reason than price.

A program subscription is a **coverage** instrument, not a race car — Kamat's observer had
a median detection lag of **34.8 seconds** and produced n=832,941, which is a research
instrument. That is a different purchase with a different justification, and
`COVERAGE.md` already frames it that way.

## 4.5 What to do, in order, none of which is a speed play

Every item below is free or inside the Helius free tier, and every one is *record it
first, measure it later* per rule 10.

| # | action | API cost | why |
|---|---|---|---|
| 1 | Record `info.socials` / `info.websites` from the payload already fetched | **zero** | largest published predictor (8.94×/17.4×); answers an open question in `QUESTIONS.md` |
| 2 | Parse Token-2022 extensions from the `getAccountInfo` response already made | **zero** | closes a live honeypot hole in `paper.qualifies` |
| 3 | Re-derive graduation FDV from the SOL price each pass; re-place the approach band | **zero** | W1 — a pre-committed band pre-committed to the wrong number |
| 4 | Reconcile 2.10% vs 0.22% from data on disk | **zero** | W2 — a base rate off by 9.5× poisons every lift |
| 5 | Record the deployer address on every observation | ~1 call/token | cannot be backfilled; costs nothing to start |
| 6 | Read FDV at the 86 witnessed curve→AMM transitions | **zero** | verifies or kills W1 outright |
| 7 | Evaluate MELT as an external labelled set for coordination | **zero** | the labelled set rule 10 demands, already built by someone else |
| 8 | Add time-rank to `tickers.note()` | **zero** | the actual vamping signal, half-built |

Items 1–4 and 6–8 require no new network calls at all. That is the whole list before
anything expensive is considered.

## 4.6 What this research did not change

- **No entry rule is supported.** Marino's breakeven result strengthens the case that
  curve-level entry rules cannot work, and says nothing about any other family. Five
  retractions still stand.
- **Fraud detection is still the product.** Nothing found here suggests otherwise; the
  literature's inability to produce a single precision figure against reserves suggests
  the opposite.
- **Coverage is still deprioritised for trading and relevant for research**, exactly as
  `GAPS.md` W2 has it.
- **The fluxbeam-vs-fraud question is still open.** No external evidence bears on it.

---

# Sources

Ordered by weight. Retrieval date 2026-09-16 for all web sources.

**Peer-quality / record-level**

- Kamat, A.U. (2026). *Pump.fun Graduation Regime Windows: Survival Analysis of 832,941
  Token Launches and the Social-Presence Effect.* arXiv:2607.02823, 10 Jun 2026. Dataset
  RED-PUMP-2026-v1, Zenodo DOI 10.5281/zenodo.20633486, CC-BY-4.0.
- Marino, G., Naviglio, M., Tarantelli, F. & Lillo, F. (2026). *Predicting the success of
  new crypto-tokens: the pump.fun case.* arXiv:2602.14860. n=655,770, Sep–Oct 2025.
  **Sections VII.B onward were not retrievable; see Part 2.5.**
- Hu, S., Tekin, S.F., Xu, Y. & Liu, L. (2026). *MELT: A Behavioral Trace Dataset for
  High-Risk Memecoin Launch Detection.* arXiv:2602.13480 v2, 21 May 2026.
  `github.com/git-disl/MELT`.
- Li, J., Kuznetsov, P., Yanovich, Y., Nott-Whaley, K. & Vodolazov, I. (2026). *Catching
  the Rug: Early Prediction of Fraudulent Memecoins on Solana via Machine Learning.*
  arXiv:2608.20271, 20 Aug 2026. n=6.4M tokens / 7 months.
- Mongardini, A.M. et al. *A Midsummer Meme's Dream: Investigating Market Manipulations in
  the Meme Coin Ecosystem.* arXiv:2507.01963; USENIX Security '26. n=34,988, four chains.
- Mzoughi, M. et al. (2025). *The Memecoin Phenomenon: An In-Depth Study of Solana's
  Blockchain Trends.* arXiv:2512.11850.

**Protocol documentation**

- pump.fun, *The Pump.fun bonding curve* (`pump.fun/docs/bonding-curve`).
- pump.fun Web Help Center, *Liquidity on PumpSwap* — LP burned at migration.
- Helius Docs, *How to Find Solana Mint, Freeze, and Update Authority*.
- RareSkills, *The Solana Token 2022 Specification*.
- Neodyme, *SPL Token-2022: Don't shoot yourself in the foot with extensions*.

**Industry / vendor — conventions and case studies, no published error rates**

- Bubblemaps blog, *How to Spot a Rug Pull Using Bubblemaps* — the 5/15/30% bundled bands.
- Solana Tracker docs, *Token Safety & Rugcheck* — top-10 > 15%, bundler > 20%.
- Bitquery, *Wash Trading on Solana: Case Studies in Market Manipulation* and *Solana's
  Volume Numbers Are a Lie* — the 200-wallet / 52-second and OpenLie cases.
- Solidus Labs, *Solana Rug Pulls & Pump-and-Dumps* — the 98.7% figure.
- SolBundler, *How to Bundle on Pump.fun: Jito Limits, Wallets & Costs (2026)*; Alphecca,
  *Pump.Fun Bundler Guide* — Jito 5-transaction / 1-slot mechanics, stagger evasion.
- Chainstack, Shyft, rpc edge, Triton One — Yellowstone gRPC pricing.
- The Defiant, *Memecoin 'Vampire Attacks' Increase*; CoinMarketCap Academy, *Community
  Takeover (CTO)*; crypto.news, *What are "the trenches"* and *What is a community
  takeover (CTO)*; SolanaFloor, *Traders Blame 'PvP Culture'*; Decrypt, *Meme Coin
  Takeover Teams Face Legal Entanglement*.
- OKX and CoinGecko — SOL spot, 2026-09-16.

**Ours, cited but not restated**

`RULES.md`, `FRAUD_DETECTION.md`, `TEMPLATE_ATTACK.md`, `CONTAMINATION.md`, `VENUE.md`,
`GRADUATION.md`, `GAPS.md`, `FEASIBILITY.md`, `COVERAGE.md`, `X_API.md`,
`PRECOMMIT-VENUE.md`, `OPEN_ITEMS.md`, `QUESTIONS.md`, `ONCHAIN_COST.md`.

---

*Research document. No code was written or modified. Every threshold sourced from outside
this repo is labelled as a measurement or a convention, and the conventions do not have
published error rates, which under standing rule 10 means none of them may filter anything
until they do.*
