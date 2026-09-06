# Open items, tracked to closure

2026-09-06. Status of the seven items on the standing list. **Three were already
closed before the list was compiled** — that is a reporting failure on my side,
not a disagreement, and they are marked so below.

| # | item | status |
|---:|---|---|
| 1 | Multiple-accuracy validation at write time | **CLOSED** — free check shipped |
| 2 | GeckoTerminal has no exit-depth measure | **CLOSED as far as it can be** — cannot be computed; now recorded |
| 3 | Holder concentration blocked on free RPC | **CLOSED 2026-09-06** — $0/month |
| 4 | Mint/freeze authority | **CLOSED 2026-09-05** — built, measured, worthless |
| 5 | Deployer history | **OPEN** — unblocked by the same free key as #3 |
| 6 | Forward-recorded paper log | **CLOSED 2026-09-06** — live, hash-chained |
| 7 | The 1h horizon decision | **ANSWERED** — keep it; the label is the problem, not the horizon |

## ⚠️ A retraction from today, recorded here because it is the newest thing

**The graduation detector's first firing was a false positive, caught within the
hour.** It announced `GRADUATED GTA 6 Coin ... fdv $437 after 2.87h in band`.

The token entered the approach band at **$62,876** of FDV and had collapsed to
**$437 with $0.04 of liquidity** and $0.0163 of exit depth. It still satisfied
`real_pool`, because `meteora` is an AMM venue and the quote reserve was
non-null at $0.0001542. **`real_pool` had no magnitude floor, so four cents
counted as a graduation.** It rugged; it did not graduate.

Fixed: `GRAD_MIN_DEPTH = $500` of quote-side depth, and `real_pool` now also
requires `fdv >= BAND_LO`, so a token falling out of the band *downward* can
never be called a graduation. Verified against five cases — the false positive
is rejected, a healthy graduation and an FDV-crossed curve token still fire, and
a shallow in-band pool no longer does.

The original claim was **not deleted** (rule 13). A `graduation_retracted`
milestone was appended alongside it with the reason and the fix. The false
announcement never reached Discord — the watchlist prints, it does not ping.

---

## 1. Multiple-accuracy validation at write time — CLOSED

The blocker was cost: `check_multiple` reads both sources, and GeckoTerminal
sustains under 10 successful calls a minute against ~213 outcome lookups per
pass. It could only ever run above 2.0x.

**A free check exists and now runs on every row.** `price_usd / price_native` is
the *quote asset's* own USD price, and both fields are already in the pair
object. Measured across 3,043 observations carrying both:

| implied quote price | share | reading |
|---|---:|---|
| $50–400 | **94.71%** | SOL, median $104.04 |
| $0.50–2 | 5.00% | USDC/USDT |
| neither | 0.30% (9 rows) | $0.000015 to $79,770 |

The 9 outliers are not all corrupt — AAPLx implies $79,770, which is simply a
BTC-quoted pair. **So the actionable test is consistency, not range:** if the
entry implies SOL and the exit implies USDC, the two prices came from pools with
different quote tokens and their ratio is not a return. Same defect class as the
cross-pool division that fabricated FLORK's 444x.

`pricecheck.check_quote_consistency()` → `journal.record_outcome()`, which now
stores `price_native`, `base_price_native`, `quote_asset_entry`,
`quote_asset_exit` and `quote_consistent` on every row, and marks a mismatched
row unrealizable with the reason recorded.

**Forward-only.** Historical outcome rows carry no `price_native`, so this
cannot be backtested and no retrospective claim is made from it. Where a field
is missing the check returns *trustworthy* — an absent measurement is not
evidence of a fault.

## 2. GeckoTerminal exit depth — CLOSED as far as it can be

**It cannot be computed.** Confirmed against a live pool payload: the only
reserve field GT returns is `reserve_in_usd`, a combined total.
`base_token_price_quote_token` and `quote_token_price_usd` are present, but
without reserve *amounts* the split cannot be derived.

So the gap was quantified instead. n=104 rows carrying both a measured depth and
a reported liquidity:

    depth / liq    p05 0.008   p25 0.482   median 0.496   p75 0.499   p95 0.500

A healthy constant-product pool sits at almost exactly 0.5, as the arithmetic
requires — so using `liq` where depth is unknown overstates exitable size about
2x, which is tolerable. **But 16 of 104 (15.4%) sit below 0.10**, and there the
overstatement reaches 125x. That is the one-sided-pool population.

Exposure, measured:

- **495 of 599 realizable rows (82.6%) have no measured depth.**
- **161 of 201 rows at ≥2x (80.1%) were judged without ever seeing the quote side.**
- All 20 GT-sourced realizable rows lack depth, **though none is currently ≥2x** —
  the specific feared failure has not bitten yet.

`depth_unmeasured` is now on every outcome row, derived on read for the whole
archive so nothing is rewritten. **Recorded, not filtered** — marking 82.6% of
realizable rows unusable on an unvalidated rule is exactly what standing rule 10
exists to prevent.

## 3. Holder concentration — CLOSED, $0/month

Reported 2026-09-06 in `ONCHAIN_COST.md`. It is blocked by **not having an API
key, not by money.**

`getTokenLargestAccounts` is refused *per method* by `api.mainnet-beta` at every
spacing tested (0 of 5 at 0/5/15/30/45s), while `getAccountInfo` and
`getTokenSupply` on the same endpoint work.

Requirement: 79 tokens/pass × 24 × 30 = **56,880 calls/month** (113,760 if
authorities go through the same provider). **Helius free tier is 1M credits at
10 req/s — we would use 11%.** Even if `getTokenLargestAccounts` bills at 10
credits rather than 1, it is 63% and still inside. Alchemy's 30M CU free tier
also fits. QuickNode has no permanent free tier. Paid rungs start at $49/mo and
none is needed.

Flags: Helius's *Agent* plan wants 1 USDC for CLI signup — the ordinary web Free
plan is the one costed. The key is a secret and goes in the runner's secret
store. **Not signed up for.**

## 4. Mint/freeze authority — CLOSED, and it is worthless

Built in `onchain.py` and measured across 228 tokens:

| | n | wins | rate |
|---|---:|---:|---:|
| mint authority live | 1 | 0 | 0.0% |
| mint authority revoked | 227 | 57 | 25.1% |
| freeze authority revoked | 228 | 57 | 25.0% |

**227 of 228 have both already revoked**, because the launchpads revoke them
automatically. A zero-variance feature cannot discriminate and must not go in a
score. Worth keeping separately: **the template pools pass this check** —
`worthless` and `TIKZZZ` both have mint and freeze revoked, so conventional rug
checks do not catch them.

## 5. Deployer history — OPEN

The one genuinely outstanding item, and reportedly the most predictive single
feature. It needs `getSignaturesForAddress` on the mint plus per-transaction
parsing — many calls per token, on the same public RPC that already method-limits
the cheaper call in #3.

**It is unblocked by the same free key as #3.** One Helius account closes items
3 and 5 together, at $0. That consolidation is the argument for making the
decision, and the decision is still Frank's.

Deferred rather than half-built: a deployer-history feature computed from a
rate-limited sample would be silently biased toward deployers whose transactions
happened to resolve, which is the survivorship error again.

## 6. Forward-recorded paper log — CLOSED, live

`paper.py`, started 2026-09-06. Append-only, hash-chained; editing any earlier
row breaks every hash after it and `verify()` names the first broken index.
Tested against a scratch ledger — duplicate open refused, re-close refused,
in-place edit of row 0 detected.

`RULE_V1` = AMM venue + exit depth ≥ $1,000 from reserves + score 70–99. Exit
rule declared **at entry**: first of 2.0x on quote-side depth or 24h. `MIN_N=30`
declared before any data existed; `summary()` returns
`WITHHELD - k closed, need 30` and will for weeks.

Wired into the scan loop so entries are written before any outcome exists. Live
entries include `$1` (pumpswap, $218,729 depth, score 85), WWR, BILL, KYIRAD,
Intern.

## 7. The 1h horizon — keep it. The label is the problem.

Measured, so this is a decision with numbers rather than a preference.

**Where a ≥2x realizable outcome is first seen**, 135 distinct pairs:

| first seen at | pairs | share |
|---:|---:|---:|
| **1h** | **106** | **78.5%** |
| 6h | 16 | 11.9% |
| 24h | 13 | 9.6% |
| 168h | 0 | 0.0% |

**61 of 135 pairs (45.2%) have a ≥2x row at 1h and nowhere else.** The move is
gone by the 6h check. Retiring the 1h horizon would delete 45% of the evidence
base, for a saving of 32.9% of outcome lookups. **That is the worst trade
available.**

The drift is real but is not an argument for retirement:

| horizon | rows | median elapsed | p90 | on time (≤1.5x) |
|---:|---:|---:|---:|---:|
| 1h | 23,392 | **1.96h** | 5.02h | **45.5%** |
| 6h | 20,824 | 6.99h | 10.04h | 81.8% |
| 24h | 18,293 | 25.88h | 29.05h | **100.0%** |
| 168h | 8,610 | 168.07h | 172.48h | **100.0%** |

Drift is concentrated entirely at 1h, and **that is structural, not a bug.** A
token observed at minute 30 of one hour is due at minute 30 of the next, but an
hourly runner fires at a fixed time — so a median of 1.96h is close to the
theoretical floor for hourly cadence. **You cannot measure a 1h horizon from an
hourly runner.**

**Recommendation: relabel, do not retire.** Call it what it is — a ~2h horizon —
and keep reading `actual_elapsed_h`, which already records the truth. That costs
nothing and loses nothing analytically. Paying for sub-hourly cadence is the only
way to make "1h" literally true, and the case for that is weak when the honest
label is free.

Frank's call, but the numbers point one way.
