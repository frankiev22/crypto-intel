# Trusted fields: every headline number, from chain

**2026-09-17. Companion to `docs/LIQUIDITY.md`, same standard: a number is
derived from chain state or it is labelled as a self-report. Nothing here was
bought, signed up for, or traded.**

> *"Those numbers need to come from the blockchain because fomo isn't
> accurate."* — Frank

---

## Status of each field

| field | source today | trusted source | state |
|---|---|---|---|
| liquidity | Dexscreener `liq` (781x overstated) | **Jupiter $100 round trip** | ✅ measured, `LIQUIDITY.md` |
| market cap / FDV | Dexscreener `fdv` | **`getTokenSupply` × realizable price** | ✅ **measured below** |
| ⭐ holder count | ⛔ **not collected at all** | **Helius DAS `getTokenAccounts`** | ✅ **measured below** |
| concentration | ⛔ not collected | top-N of deduped owners | ⚠️ **my first metric was broken — §3** |
| volume | Dexscreener `vol_h1`/`vol_h24` | distinct signers from chain | ⚠️ **partly — §4** |
| bundles | ⛔ **nothing in the repo does this** | same-slot buys at creation | ⛔ **§5, harder than it looks** |

---

## 1. ⭐ Holder count — Frank's sharpest addition, and it works

> *"A coin can bond with 2 holders. Not something we want to deal with."*

**He is right, and the data is emphatic.**

Helius DAS `getTokenAccounts` enumerates every token account for a mint,
paginated 1,000 at a time. Measured: **~850ms and 3 pages for a ~1,400-holder
token**; BONK took 26 pages and 21.8s. Fresh memecoins are the cheap case,
which is exactly our case.

⚠️ **"Token accounts" is not "holders"** and I checked rather than assumed:
Helius already excludes zero-balance accounts (**0% discarded** on the sample),
and wallets holding more than one account for the same mint were **0**. After
deduplicating by `owner` and requiring balance > 0, raw count ≈ holder count
here. **Still dedupe — that is a property of this sample, not a guarantee.**

### The result: 141 winners vs 60 random controls

```
              n     median   p25      p75      max      under 10 holders
winners      141        9      3       43     1,462      76  (54%)
controls      60        2      1        7       104      50  (83%)
```

⛔ **The median "winner" in our own data has NINE holders.** More than half of
the contracts this system recorded as 3x+ wins have **fewer than ten holders**.

### Holder count separates exitable from dead almost perfectly

Cross-referencing against the Jupiter verdicts from `LIQUIDITY.md` §5:

| Jupiter verdict | n | median holders | p25 | p75 |
|---|---:|---:|---:|---:|
| **TRADEABLE** | 8 | **1,350** | 451 | 1,438 |
| **COSTLY** | 7 | **136** | 43 | 338 |
| NO_BUY_ROUTE | 30 | 23 | 3 | 54 |
| NO_SELL_ROUTE | 26 | 11 | 8 | 12 |
| **TOTAL_LOSS** | 70 | **3** | 3 | 9 |

**Three orders of magnitude between what you can sell and what you cannot.**
Nothing else measured in this repo separates that cleanly.

⭐ **The single best illustration is WOFI** — the 333.3x "winner" from the
liquidity re-verification. **43 holders. Top 10 hold 100% of supply. Real market
cap $2,128.** It is a bundled launch wearing a milestone, which is precisely
the shape Frank described before any of this was measured.

### The proposed gate

| floor | keeps exitable | keeps dead |
|---|---|---|
| ≥ 10 | 15/15 (100%) | 50/126 (40%) |
| ≥ 50 | 13/15 (87%) | 19/126 (15%) |
| ⭐ **≥ 100** | **12/15 (80%)** | **2/126 (2%)** |
| ≥ 200 | 10/15 (67%) | 0/126 (0%) |
| ≥ 500 | 5/15 (33%) | 0/126 (0%) |

**`holders >= 100` removes 98% of the junk and keeps 80% of what is actually
sellable.**

⛔ **This threshold is NOT validated and must not be quoted as if it were.** I
chose 100 *after* seeing the table, which is exactly what standing rule 6
forbids. Its honest status is **"a candidate with a strong in-sample fit"** —
the same status as D2, and D2 is still unvalidated four days later. It needs a
**pre-committed forward test** on contracts observed after the threshold is
written down. Both measurements are also contemporaneous (holders today,
exitability today), so this says nothing yet about whether holder count
*predicts* anything.

## 2. Market cap — supply from chain, price from a real quote

`getTokenSupply` returns supply and decimals in **~200–350ms**. Multiply by the
realizable price implied by a Jupiter quote and the result depends on **two
measured inputs and no reported ones**.

```
sym         supply        real mcap      our stored fdv
WYNX     962,907,167       273,826            44,337
CONK     999,895,411        79,800            32,824
APEC     996,443,008        22,535            27,102
ROCK     999,932,496     1,650,385            46,259
WOFI     999,738,157         2,128            41,318
```

⚠️ **Do not read that as "stored fdv is wrong by 35x".** Stored `fdv` was
recorded at observation time; real mcap is today. **They are different moments
and comparing them directly would be the error this repo keeps making.** What
the table establishes is that **the method works and is cheap** — not a
discrepancy measurement. A like-for-like comparison requires computing both at
the same instant, which only forward collection can do.

⚠️ Supply is near-1e9 for every pump.fun token by construction, so **FDV and
market cap coincide** on this venue. That stops being true for tokens with
locked or vesting supply; **on those, report both and label which is which.**

## 3. ⚠️ Concentration — my first metric was junk, and here is why

I computed top-10 share of supply and got **median 100.0% for winners and
100.0% for controls.** That is not a finding, it is an artifact: **most of
these tokens have fewer than ten holders**, so "top 10" is the whole supply by
construction. A metric that returns 100% for everything discriminates nothing.

**Fix before using it:** report top-N only when `holders > N` by a clear margin,
exclude the pool/LP vault (identifiable as an account owned by an AMM program),
and prefer a **Gini or top-10-excluding-largest** figure that is defined at
small n. **Until then, holder count alone is the honest metric** and it already
does the work.

## 4. ⚠️ Volume and wash trading — the access works, the plumbing does not yet

`getSignaturesForAddress` on a pool returned **42 signatures in 153ms**, and
parsing 40 of them yielded **5 distinct signers**, with **82% of sampled
transactions from a single wallet** and 95% from repeat wallets. So the
mechanism Frank wants — *how much of this volume is one wallet talking to
itself* — is directly computable, and it is cheap.

⛔ **But the pool I probed showed 0.17 txns/hour for a token with a $1.65M real
market cap, which cannot be right.** The `pair` address in our stored rows is
the pool as it was at observation; the token has since moved venue. **Volume
must be measured on the pool Jupiter is actually routing through today** — and
Jupiter's `routePlan` names it in the same call we already make for liquidity.

**So: distinct-signer wash measurement is feasible and cheap, but it must key
off the live route, not the stored pair.** Treat the 82% figure as proof the
method runs, not as a measurement of that token.

## 5. ⛔ Bundles — we do not have a detector, and I should say so plainly

**There is nothing in this repo that detects bundling.** I checked before
comparing. `detector.py` has D1 (SILENCE) and D2 (MAGNITUDE + INACTIVITY), and
the "28 flagged / 1 false positive" validation belongs to those. **They detect
one-sided unexitable pools, not coordinated launches — a different phenomenon.**
There is no "ours vs theirs" to judge, because ours does not exist.

⚠️ **Worse, both detectors are computed on `liq` and `fdv`**, and D1's ground
truth is `exit_depth_usd / liq`. **The detectors we trust most are built on the
field we just established is poisoned, validated against the measurement that
fails 5 of 6 reads.** That is not a reason to discard them — D1 is the only
out-of-sample rule in the repo — but it is a reason to re-derive both against
Jupiter before quoting their precision again.

### What bundle detection actually requires

The definition is precise: **buys that land in the same block as token
creation**, placed there deliberately via a Jito bundle so they execute before
anyone outside can see the token exists.

I probed it: pull every signature on the mint, sort by slot, take the earliest
slot, count distinct signers in it.

```
sym     creation slot   txns in slot   distinct signers   holders now
WOFI      444,139,103         1              1                43
ROCK      447,585,034         3              1             1,462
WYNX      444,894,505         1              1             1,350
CONK      444,787,618         1              1             1,438
```

⛔ **Inconclusive, and I am not going to dress it up.** One signer for every
token — including WOFI, which every other metric screams is bundled — means the
probe is not finding the buys. Two likely reasons: pagination stopped before the
true oldest signature on busy mints, and **grouping by slot is not the same as
identifying the pump.fun `create` instruction and the buys attached to it**.
Doing this properly means parsing instruction types, not sorting timestamps.

### Verdict on build vs use

**Use an existing tool first.** [Trench Bot's Bundle Scanner](https://docs.trench.bot/bundle-tools/bundle-scanner-guide)
reports bundled supply, wallet count, and how much those wallets still hold;
Cabal-Hunter exposes same-block and coordinated-dump detection via API.
**Evaluate one against contracts we can already label** — WOFI should come back
heavily bundled, ROCK should not. If a free tier answers by contract address,
that is days of work avoided.

⚠️ **And note holder count already catches WOFI.** Before building or buying
bundle detection, check how much of it `holders >= 100` gets for free.

---

## 6. ⭐ The attention threshold Frank proposed

> *"if a token bonds it deserves our attention. Obviously some can't 'bond' so
> we need a threshold to track."*

**Recommendation: bonding replaces the $1M market-cap trigger for curve
launches, and a holder floor gates both.**

| launch type | trigger | why |
|---|---|---|
| pump.fun / curve | ⭐ **graduation (bonding)** | a discrete on-chain event, not a derived number. No phantom problem — it either completed or it did not |
| no curve (direct AMM) | **$1M real mcap**, computed per §2 | needs an equivalent, and size is the only comparable one |
| **both** | ⛔ **then `holders >= 100`** | *"A bond with 2 holders is not something we want to deal with"* |

**Why bonding beats the $1M trigger where it applies.** The $1M crossing is
derived from reported liquidity and **only 25.4% survive verification**
(`TRACKER_SCOPING.md`). Graduation is a state change on the bonding curve
account — **there is nothing to verify, because nothing is being inferred.**
It is the one milestone in this system that cannot be a phantom.

**Why it does not replace it entirely.** Graduation is a pump.fun-shaped event.
Tokens launched straight onto an AMM never bond, so they need the size
threshold — which is why §2's on-chain mcap matters: **the $1M trigger is only
as good as the market cap behind it, and today that comes from a self-report.**

**Volume: 32 graduations exist in our entire milestone history.** That is a
trigger firing roughly once or twice a day, which is an alert volume Frank can
actually read — against 24.5 verified $1M crossings/day. ⚠️ **Sizing this
properly needs the collector running**, and nothing has collected since
2026-09-15 05:07:59 UTC.

⛔ **Order of operations matters.** The holder gate is applied **after** the
trigger, never as a filter on everything — enumerating holders costs ~1s per
token, which is affordable on 1–2 graduations/day and not on 2,500 contracts.
