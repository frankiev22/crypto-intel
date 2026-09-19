# The buyer's playbook

Written 2026-09-17. Research only. **No code was written or modified, no trade was
placed, no funds were moved.**

Companion to `docs/TRENCHES_REFERENCE.md` (2026-09-16), which is assumed read. That
document defines the vocabulary and classifies signals. This one answers a narrower
question: **given everything in it, what can a buyer with $1,000 actually do.**

Scope note: this file covers **buying only**. Launching tokens, tax-token design and
the glossary belong to a parallel document and are deliberately absent here.

---

## Corrections first, per standing rule 4

Three premises in the brief for this work did not survive checking.

**1. "Median position lost 60%, 3 wins in 69 closes" is ten days stale, and only half of
it traces to anything.** The `GAPS.md` figures it draws on are dated 2026-09-07 and that
file records **1** win at n=7, not 3. The "median lost 60%" half is `GAPS.md`'s 0.4015×
median multiple; **the "3 wins in 69 closes" half is not in any file in this repo** and I
could not find its provenance. Current figures, from `data/findings/REPORT_2026-09-15.md`:

> ⛔ **QUARANTINED 2026-09-17, stated here 2026-09-19.** Every figure in this table and in
> §6.2 is computed on exits priced at the Dexscreener mid with `notional_usd` never applied,
> and 16 positions entered 09-14/15 were never closed. **There is no usable v1 hit rate.**
> The table is kept as history (standing rule 8); `paper.summary()` now returns
> `QUARANTINED` instead of a rate. See `PRECOMMIT_paper_v3.md` §2 and §2a.

| v1 paper ledger, 2026-09-15 | measured | + inferred losses |
|---|---|---|
| all closes | 9/76 = **11.84%** [6.36, 21.00] | 9/123 = 7.32% [3.90, 13.32] |
| excluding 3 sub-3-minute targets | 6/73 = 8.22% [3.82, 16.79] | 6/120 = 5.00% [2.31, 10.48] |

P&L on $100 clips: **−$3,099 over 76 measured closes**, or **−$3,930 with wins capped at
2×**; −$7,799 over 123 including inferred losses. **The direction of the old number was
right and its magnitude is now better measured**, which is the point of the log.

**And v1 is not the whole ledger.** The same report carries **v2 with 353 entries and 277
closes**, arm B_high at 10.34% [4.83, 20.79]. Every figure in this document is v1's
because v1 is the rule with a declared exit and a pinned gate; **quoting "76 closes" while
277 more exist in the same report understates the denominator**, and Part 7 should be read
with that in mind.

**2. "Marino et al. show that buy-and-hold to graduation loses money" is true but
under-quoted, and the paper says so itself.** I retrieved §VI directly, which
`TRENCHES_REFERENCE.md` Part 2.5 recorded as NOT RETRIEVABLE. The paper's own
sentence, verbatim:

> "It is important to stress that this is the breakeven curve **only for buy-and-hold
> strategies**. In other words, it might be possible to devise dynamic strategies
> delivering positive expected profits also when the conditional probability lies
> below the breakeven curve."
>
> — Marino, Naviglio, Tarantelli & Lillo, arXiv:2602.14860 §VI, retrieved 2026-09-17

So the brief's instruction that "that family is dead" is correct as stated — **the
family of rules that enter at a point on the curve and sell at graduation is dead** —
and the authors explicitly decline to extend it further. The distinction is developed
in §3 because Frank's own claim lives in exactly the gap the authors left open.

**3. "Fomo is the expensive one" is not established, and the size of the overpayment is
much smaller than the complaint implies.** Fomo's Solana fee on a $100 order is $0.95,
i.e. 0.95%. Axiom's base tier is 0.95% — **the same number**. GMGN and Photon are 1%,
Pump.fun Terminal ~1.16%, Moonshot 2.5%; Fomo is cheaper than all four and it absorbs gas,
priority fees and token rent, which none of them do. It is **fifth of eleven** on the
`docs/CHAINS.md` §2.3 table, not first. **Jupiter genuinely is cheaper** — $0.20 per $100
round trip on a mature token and $1.00 on one under 24 hours old, against Fomo's $1.90 —
so on the population Frank actually trades he is paying about 90% more than he has to.
That is real and it is $0.90 a trade. What is also true is that Fomo's schedule is
**banded**, and at $100 he pays 0.95% where the headline says 0.50%.

**4. The round-trip cost model in Part 4 probably understates pool fees on pump.fun-lineage
pools, and the parallel task flagged it the same day.** `GAPS.md`'s impact model uses a
0.25% pool fee per side. `docs/RULES.md` **O1** and `CREATOR_PLAYBOOK.md` §1.1 document the
**PumpSwap swap fee as 1.250% falling to 1.200%** above a 420 SOL market cap — protocol,
creator and LP combined. If the 71 pools behind `GAPS.md` Part 5 are predominantly
PumpSwap, the round-trip fee term is ~2.5%, not 0.5%, and every total in §4.4 rises by
about two points: the median $100 round trip becomes **~5.9% rather than 3.89%**, and a bad
fill **~$16.40 rather than $14.35**. **`GAPS.md` does not record which venues those 71
pools are on, so I cannot settle it**, and I have not silently rewritten its model. Two
things survive either way: **the optimal clip size is unaffected** (a constant fee term
drops out of the derivative in Part 5.1), and the direction of the verdict in Part 7 gets
worse, not better. Resolving it is a query over `dex_id` on rows already on disk.

---

## Part 1 — The only two things a buyer knows in advance

This is the frame for everything below, and it is the reason this document is short
on entry rules and long on arithmetic.

Every entry signal in `TRENCHES_REFERENCE.md` Part 2 is probabilistic and unvalidated out
of sample. ⚠️ **They are not all "already priced" and I should not have written that.**
Marino's pricing argument applies to features the curve level already encodes.
`TRENCHES_REFERENCE.md` §2.1 is explicit about the scope: *"The only features that can
survive are ones that are **visible at launch, before there is a price**, or ones that are
**expensive enough for others to ignore**."* Kamat's social-link and initial-mcap features
are exactly that category and §3.3 below still finds them short of breakeven — but they
are short for a different reason, and the distinction matters to anyone trying to build
one.

Against that, exactly two quantities are **deterministic and knowable before the trade**:

    1. What the round trip costs.        Computable to the cent from a fee schedule
                                         and a reserve read.
    2. How much quote side exists.       `exit_depth_usd`, already measured, never
                                         retracted.

Both are exit-side. Neither predicts anything. **They are the only part of this
domain where effort converts reliably into dollars**, because they move the outcome
without requiring a forecast to be right.

The rest of this file spends its length there, and treats entry prediction the way
the evidence supports: as an open problem with five retractions behind it.

---

## Part 2 — Leading, coincident and lagging: what I can add

`TRENCHES_REFERENCE.md` §2.2 already classifies these and I am not restating it.
Three additions, all from the Marino full text retrieved today.

### 2.1 The dominant predictor, now with its operational definition

Marino's §VII.B was previously unretrievable. The variable they call the strongest is
defined precisely, and it is cheap:

> "We condition the graduation probability on **the cumulative number of swaps
> observed up to the moment a given vSol threshold is first reached.** … We consider
> five increasing thresholds for trading activity (10, 50, 100, 500, and 1000 swaps)."
> — arXiv:2602.14860 §VII.B

And from the introduction:

> "Fast accumulation of liquidity through a small number of trades is the strongest
> predictor of graduation, **dominating other variables across the entire range of
> vSol**."

**Read it as a ratio: SOL-per-trade.** A token that reached 50 SOL in 40 trades is a
different object from one that reached 50 SOL in 800 trades, and the first is the one
that graduates. It is genuinely leading — the paper is explicit that the variable is
constructed "using only information available up to the current point on the bonding
curve."

**[NOT RETRIEVABLE]** The effect size. The fetch truncated at §VII.B's first
paragraph, before Figure 7's comparison against the breakeven. So I can confirm the
variable is dominant among their predictors and **cannot confirm it clears
breakeven**. Given that the bot-share conditioning explicitly does not (§2.2 below),
assume it does not until someone reads Figure 7.

**Ours? HARD, and harder than my first read of it.** I initially wrote that
`txns.m5.buys/sells` and `fdv` give a usable proxy on a call the scanner already makes.
**That is wrong, and two of our own files say why.** Marino's variable is *cumulative*
swaps up to the moment a vSol threshold is **first reached** — a path-dependent quantity
requiring repeated observation of the same token. `TRENCHES_REFERENCE.md` §4.2 item 2:
*"we could not currently compute it anyway because **we rarely observe the same token
twice**."* `GAPS.md`: *"we have no capability to re-observe a token we have already
seen."* **A 5-minute rolling transaction count is not a cumulative-to-threshold count.**

What would unblock it is already priced: `GAPS.md` costs a re-poll of every live
bonding-curve contract at **54 Dexscreener calls per sweep** (30 addresses per call,
1,615 distinct contracts over 48h), or ~216 calls/day at a 6-hourly cadence — a ~10%
increase in call volume. That buys the *universe* this feature needs. It does not buy the
feature.

### 2.2 The bot-share result, and its ceiling

Marino's isBot definition is operational and does not need a classifier:

> "We distinguished between transactions routed through the official Pump.fun
> frontend (the website) and those directly invoking the smart contract on-chain. The
> latter … are typically associated with automated or scripted trading behavior."

Result, verbatim, and this is the sentence that matters:

> "All conditional graduation-probability curves remain **below the economic
> breakeven over most of the vSol range**, with the notable exception of the p₀.₃
> curve, which **approaches** the breakeven in the vicinity of the graduation
> threshold."

**Precision matters here, and the loose version of this sentence is wrong.** The
bot-share conditioning does not clear breakeven — it approaches it, in one narrow region
near the threshold. It is **not** "the best conditioning in the paper": §2.1 records that
the trade-count variable is the one the authors call dominant, and whether *that* clears
breakeven is **[NOT RETRIEVABLE]**.

The authors' footnote excludes fees under a 1.25% approximation. I originally wrote that
adding them back puts the curve under; **I cannot assert that.** How far below breakeven
p₀.₃ sits near vSol=115 is unknown, because Figure 7 did not come back in the fetch. The
honest statement is the authors' own: the comparison is *"purely qualitative"*, and it
excludes a cost that can only move it the wrong way.

### 2.3 A coincident signal that is worse than coincident

`TRENCHES_REFERENCE.md` §2.2 lists Dexscreener/Axiom trending placement as coincident
because it is computed from volume. There is now a measured reason to call it
*negatively* informative for a follower: DWF Ventures, analysing ~292,000 Fomo
wallets over a 90-day window ending August 2026, found **6.16% profitable on realized
P&L**, and among the profitable, **just 25 wallets cleared $10,000 net** (DWF
Ventures via AlexaBlockchain, 2026-08-28). The mechanism DWF names is execution
asymmetry, not fraud — they state explicitly that the data does not establish that
followed traders trade against followers.

Treat any feed-sourced entry as coincident with a crowd that has already moved.

---

## Part 3 — Frank's sub-25k claim, tested

> *"i have seen a lot of new coins that i can definitely enter sub 25k market cap that
> end up running to bond and then some."*

This gets a full section because it is the one place where a specific, falsifiable
claim meets a specific, published result. **The claim is testable and it fails, but
not for the reason the brief assumed, and the failure has an exact number attached.**

### 3.1 The arithmetic, simplified to one line

Marino's breakeven, equation (3), retrieved verbatim 2026-09-17:

    p(vSol; θ)  >  vSol² / 115²

Price on the curve is `vSol²/k` (their equation, §III), so FDV is proportional to
`vSol²`. Substituting collapses the whole thing:

    required graduation probability  =  entry market cap / graduation market cap

**That is the entire result and it needs no curve mathematics to use.** To break even
buying at market cap X and selling at graduation, you need the probability of
graduating to exceed X as a fraction of the graduation market cap.

Graduation market cap, from the mechanism (85 real SOL, PumpSwap pool seeded at
85 SOL / 2.069×10⁸ tokens, 10⁹ supply → 410.8 SOL FDV):

| SOL price | source, 2026-09-17 | graduation FDV |
|---|---|---:|
| $99.64 | Kraken public ticker | **$40,932** |
| $98.41 | Coinbase | $40,427 |
| $97.31 | OKX, 2026-09-16 | $39,975 |
| $102.30 | CoinGecko, 2026-09-16 | $42,025 |

**The threshold is $41,000 ± $1,000 and it moves with SOL, not with anything about
the token.** This is `TRENCHES_REFERENCE.md` W1 restated; it is repeated here because
the required-probability table below is meaningless without it.

### 3.2 The table

Using FDV_grad = $40,932. Real SOL deposited = vSol − 30.

| entry mcap | required p to break even | vSol | real SOL in | % of curve done |
|---:|---:|---:|---:|---:|
| $2,938 *(our median curve observation)* | **7.18%** | 30.8 | 0.8 | 1% |
| $5,000 | 12.22% | 40.2 | 10.2 | 12% |
| $10,000 | 24.43% | 56.8 | 26.8 | 32% |
| $15,000 | 36.65% | 69.6 | 39.6 | 47% |
| $20,000 | 48.86% | 80.4 | 50.4 | 59% |
| **$25,000** | **61.08%** | **89.9** | **59.9** | **70%** |
| $30,000 | 73.29% | 98.5 | 68.5 | 81% |
| $40,932 | 100% | 115.0 | 85.0 | 100% |

*Median curve FDV $2,938 from `GAPS.md` ("Discovery is a ~1%-wide window at birth", filed
2026-09-10), n=7,033. **Not `FEASIBILITY.md`** — `TRENCHES_REFERENCE.md` §4.4 attributes it
there and that is wrong; `FEASIBILITY.md` carries no FDV distribution.*

**A $25,000 entry is not early. It is 70% of the way up the curve**, and it requires a
61% chance of graduation to break even on a hold-to-bond.

### 3.3 What is actually achievable, at both ends

**At the $25,000 end.** The right comparison is `p_std(vSol ≈ 90)` against 61.08%. Marino
state that `p_std` lies below the breakeven curve — *"it is not possible to make profits
with a buy-and-hold strategy based only on vSol (or the price)"*, §VI — and that the
bot-share conditioning stays below it *"over most of the vSol range"*, approaching only
near 115. **I have not read a value for `p_std(90)` and the paper's figures did not come
back**, so the strict statement is: the authors say no for the unconditioned case, and no
cohort in any literature I found reaches 61% at vSol=90. **Answer: no, on the authors'
statement rather than on a number I can quote.**

**At the launch end**, where "sub-25k" is more charitably read as "as early as I can
get in", the required probability is 7.18% at the median observed FDV. Against that,
the best published conditional graduation rates, all Kamat 2026, n=832,941:

| cohort | graduation rate | shortfall vs 7.18% |
|---|---:|---:|
| all launches | 0.198% [0.189, 0.208] | **36×** |
| creator self-buy, initial mcap > 31.04 SOL | 0.634% | 11× |
| Telegram link in metadata | 1.485% | 4.8× |
| **all three socials — the best published cohort** | **1.919%** | **3.7×** |

**The best-conditioned cohort anyone has published is short of breakeven by a factor
of 3.7, at the cheapest possible entry point, before fees.** That is the cleanest
refutation available and it does not depend on Marino's figure at all.

**Both ends fail, and the middle fails by Marino's categorical statement.** There is
no entry market cap at which the hold-to-bond version of this claim works.

### 3.4 Where the claim is not refuted, stated fairly

Three things cut Frank's way and none of them is dismissible.

**(a) The paper leaves dynamic strategies explicitly open.** Quoted in full at the top
of this file. Frank's "and then some" is not a buy-and-hold-to-graduation trade. If
he holds past the bond, the breakeven becomes

    p  >  (entry mcap / graduation mcap) / m        where m = realised multiple past graduation

At $25,000 that is 61.08% ÷ m. With m = 3 he needs 20.4%. With m = 10 he needs 6.1%.
**Those are still far above any measured cohort rate, but they are a different order
of impossible, and the honest version of this section says so.**

**(b) Our own 0.01% curve figure cannot test his claim, and I am not going to pretend
it can.** `VENUE.md` measures curve-entry tokens at **0.01% ≥2x, two wins in 14,802**.
That looks decisive against him and it is not, because of a timing artifact: Kamat's
median time to graduation is **1.0 minute**, p90 2.0 minutes, and our first outcome
checkpoint is at **1 hour**. A token that bonded at t+60s and round-tripped by t+40min
is recorded by this system as a loss. **The 0.01% figure partly measures our
checkpoint schedule rather than the strategy.** It stands as a measurement of what
*we* would have captured; it does not stand as a measurement of what was available.

**(c) His claim is about selection, and the base rates above are not.** "I can enter
sub-25k on coins that bond" is a claim about his own discrimination. Nothing in the
base-rate literature refutes a selector; it only sets the bar the selector must clear.
The bar at $25,000 is 61%.

### 3.5 What would settle it, and it is cheap

Frank has the falsification test in his own Fomo history. **Take every sub-$25k entry he
has made since he started trading live — 2026-09-10, per the brief — count what fraction
reached the bond, and compare to 61%.** No new capability, no new data source, no build. It is the only forward-ish
record of his *own* selection that exists, and standing rule 14 prefers it to
everything above.

Two cautions on running it. Count **every** sub-25k entry, not the memorable ones —
this is rule 3, and recall of trades that bonded is exactly the survivorship the rule
exists to catch. And count reaching the bond, not reaching a profit, so the number is
comparable to the table.

---

## Part 4 — What the round trip costs, to the cent

Frank asked for the arithmetic of a bad fill on a $100 clip. Here it is, in four
components, three of which are free on Solana through Fomo.

### 4.1 Venue fee

Fomo's Solana schedule is **banded by order size**, which almost nobody quoting "0.5%"
notices. From `help.fomo.family`, read and quoted by FomoAppGuide 2026-08-20:

| Solana order | fee | effective rate |
|---|---|---:|
| under 5 USDC | flat 0.10 USDC | 5.00% at $2 |
| 5 – 47.50 USDC | 2% of order | 2.00% |
| **47.50 – 190 USDC** | **flat 0.95 USDC** | **1.90% at $50, 0.95% at $100, 0.50% at $190** |
| 190 USDC and above | 0.50% | 0.50% |

The bands meet exactly at their edges (2% of 47.50 = 0.95; 0.50% of 190 = 0.95), so
nothing jumps. A referral code takes the standard 0.50% rate to 0.45% — a 10% discount on
the **percentage** band only, per the same schedule — and **it does not touch the flat
band**, so it is worth nothing to Frank at $100.

**On a $100 clip Frank pays $0.95 in and $0.95 out. Round trip 1.90% of position.**

Two things to know about that number. First, it is **double the headline rate** he
thinks he is paying. Second, DefiLlama's fee-over-volume ratio for Fomo's Solana side
came out at **~1.36%** realised across all users in a 30-day window read 2026-08-14 —
roughly three times the 0.50% headline — which is what you would expect if most orders
sit in the bands below 190 USDC. Frank is not an outlier; the small-order bands
describe the typical trade on this app.

⚠️ **One caveat on that 1.36% that the figure's own publisher supplies.** DefiLlama flags
Fomo's volume adapter `doublecounted: true`. If the volume denominator is inflated 2×, the
realised take rate is nearer **2.7%**, not 1.36%. I cannot resolve which, and the
arithmetic on the published bands — which does not depend on DefiLlama at all — is the
number to trust. The ratio is corroboration of direction, not a measurement.

⚠️ **The schedule changed three times in twelve days in August 2026** (Aug 8, Aug 14,
Aug 20, per FomoAppGuide's dated readings), and Fomo's rewritten Terms of 2026-08-17
name no fee figure at all outside perps, stating only that the fee "is displayed
before you confirm" and may be modified "at any time in its sole discretion."
**Re-read the confirmation screen. Every number in this section has a date on it for
a reason.**

Source caveat: both sites carrying this schedule are **referral-affiliate sites** that
earn a share of Frank's fees. FomoAppGuide quotes the primary help-center article with
retrieval dates and publishes arithmetic unflattering to the product it sells, which is
why it is used here. It is still an interested party.

### 4.2 Gas, priority fee and token rent

**Zero, on Solana, through Fomo.** Its help center states it covers "all gas fees,
priority fees, and token rent" on Solana, Base, BNB Chain, Monad and Robinhood Chain,
with Ethereum passed through. Token rent is the one-time ~0.002 SOL cost of opening a
token account for a token you have not held before — real, and most venues pass it on.

For comparison, the same swap self-routed costs base fee 5,000 lamports + priority fee
+ Jito tip. Measured 2026-09-17: network-average priority fee ≈ 0.000044 SOL, median
landed Jito tip 2,138 lamports (bundles.jito.wtf tip_floor endpoint), total
**≈ $0.005** at SOL $99.64. Half a cent. **This is not where the money goes and it is
not worth optimising.**

### 4.3 Slippage, which is where the money goes

`GAPS.md` Part 5 models the round trip on constant-product impact,
`2 × size/(depth+size) + 2 × 0.25% pool fee`, across 71 tradeable-shape pools with
median quote-side depth **$13,330**. House model, house pools, 2026-09-07:

| size | p25 | **median** | p75 | p90 | under 5% | over 20% |
|---|---:|---:|---:|---:|---:|---:|
| **$100** | 0.68% | **1.99%** | 7.78% | 12.45% | 70% | **0%** |
| $250 | 0.94% | 4.18% | 17.76% | 27.93% | 59% | **21%** |
| $500 | 1.38% | 7.73% | 32.28% | 48.74% | 37% | 30% |
| $1,000 | 2.25% | 14.46% | 55.34% | 78.23% | 37% | 32% |

### 4.3b MEV and failed transactions, which are smaller than the folklore says

The brief asked for these quantified. Both are real and both are second-order next to
§4.3.

**Sandwiching.** The one peer-reviewed measurement is Gerzon, Weintraub, In, Mislove &
Nita-Rotaru, *Quantifying the Threat of Sandwiching MEV on Jito*, IMC '25 (DOI
10.1145/3730567.3764493), over Feb 9 – Jun 9 2025: **521,903 sandwich attacks,
$7,712,138 in victim losses, attacker gains $9,678,466.** The number that matters to a
$100 clip is their per-transaction figure: **median loss ≈ $5 per sandwiched transaction**,
with "some transactions lost over $100." 28% of sandwiches had no SOL leg and are excluded,
so the totals are a lower bound.

**On a $100 clip a median sandwich costs $5, i.e. 5% of the position — comparable to the
entire round trip.** But the *frequency* is what is missing and it is missing everywhere:
**the paper does not report what share of swaps get sandwiched** (its 0.038% figure is of
Jito *bundles*, which are not swaps), and **[NOT FOUND]** — no 2026 measurement of the
share of retail memecoin swaps sandwiched, or the per-swap cost, exists publicly. So the
expected MEV cost per trade cannot be computed. What can be said: Fomo routes through
DFlow and advertises MEV protection, and Jupiter Ultra has it on by default, so for both
of Frank's realistic venues this is at least nominally handled. See `docs/CHAINS.md` §2.2
for why "nominally" is doing work in that sentence.

**Failed transactions.** On Solana **fees are charged whether a transaction succeeds or
fails** (solana.com/docs/core/fees/fee-structure), the priority fee is computed from the
*requested* compute-unit limit rather than consumed units, and it is **not refunded**.
Two corrections to widely-repeated claims: SIMD-0096 sent 100% of the **priority** fee to
the validator but **did not touch the base fee**, which is still 50% burned; and the
headline "50–75% of Solana transactions fail" is a bot artifact — the peer-reviewed
measurement (*Proc. ACM Softw. Eng.*, DOI 10.1145/3728943, Aug 2023 – Jul 2024,
n=2.9bn non-vote transactions) puts the **bot-account failure rate at 58.43% and the
human-account rate at 6.22%.**

**On Fomo this line item is zero**, because Fomo absorbs gas and priority fees. Self-routed
at a ~6% human failure rate and ~$0.005 a shot, the expected cost is **well under a cent
per trade.** It is not where the money goes. **[NOT FOUND]** — no 2026 swap-specific or
bot-excluded failure rate; the "76% success" figure circulating in 2026 content traces to
a single self-published post with no error-code parsing and is not usable.

### 4.4 The total, and the answer to "what does a bad fill cost"

| | median-depth pool | p90 (bad) pool |
|---|---:|---:|
| Fomo fee, round trip | 1.90% | 1.90% |
| gas / priority / rent | 0.00% | 0.00% |
| slippage + pool fee, round trip | 1.99% | 12.45% |
| **total round trip on $100** | **3.89% = $3.89** | **14.35% = $14.35** |

**So: a bad fill costs about $14 on a $100 clip, against $1.90 of venue fee. The fill
is worth roughly seven times the fee.**

That is the number Frank asked for, and it has a consequence he did not ask for:
**at $100 clips, no venue's fee schedule can rescue a bad fill.** The spread between the
terminals — $1.50 to $2.32 per $100 round trip — is smaller than the gap between a median
pool and a bad one, which is $3.89 to $14.35.

⚠️ **This is in tension with `docs/CHAINS.md` §2.6, which ranks Jupiter first on cost, and
the two files should be read together rather than separately.** The reconciliation:

- **Among the terminals, cost is not a reason to switch.** Fomo, Axiom, GMGN, Trojan and
  Photon are all within $0.50 of each other per round trip. Switching between them to save
  $0.40 while a bad fill costs $12 is optimising the wrong term.
- **Jupiter is not in that cluster.** At $0.20–$1.00 it is a $0.90–$1.70 saving per round
  trip, which at Frank's measured pace is real money over a month, and it comes packaged
  with better MEV defaults and no custody question. **That is worth switching for — but on
  the total package, not on the fee line alone.**
- **Neither changes the fill.** If the fills are thin pools rather than routing, no venue
  on the list helps. `docs/CHAINS.md` §2.5 is the twenty-trade experiment that tells him
  which it is, and it should be run before any switch, not after.

### 4.5 One correction to a number in our own file

`GAPS.md` Part 5 states the cliff twice and gives two different answers:

> "**The cliff is between $100 and $250**, not between $500 and $1,000."

> "**The cliff is between $500 and $1,000.**"

Both sentences are in the same section and they are not the same claim. They are
measuring different things and both are right:

- **Cost cliff, $100 → $250.** The "over 20%" column goes 0% → 21%. At $100 nothing
  in the sample costs a fifth of the position to round-trip; at $250 a fifth of the
  sample does. This is the one that matters for expected value.
- **Availability cliff, $500 → $1,000.** The "tradeable within ~5%" column goes 64% →
  34%. This is the one that matters for how many candidates exist.

**Memory's version — "$100 not $500, because the cliff is between 100 and 250" — is
the cost cliff and it verifies.** It should carry the qualifier, because someone
reading `GAPS.md` cold will find the other sentence and think one of them is wrong.

---

## Part 5 — Position sizing, derived rather than asserted

### 5.1 The optimal clip is a closed form, and it is $113

Fee falls with size (flat $1.90 round trip, spread over more dollars). Slippage rises
with size. Minimising the sum:

    total(S)  =  1.90/S  +  2S/(D+S)  +  0.005          for 47.50 ≤ S ≤ 190

    d/dS = 0   →   1.90/S²  =  2D/(D+S)²  ≈  2/D        for S ≪ D

    S*  =  sqrt(0.95 × D)

At the median depth D = $13,330 that gives **S\* = $112.50**, total cost 3.86%.
At Frank's $100, total cost 3.89%.

**The difference between the theoretical optimum and what he already does is three
basis points.** At the median tradeable depth his clip size is right and does not need
changing. **At other depths it does** — §5.2 gives the general form, and on a thin pool
the optimum drops below $100. The two are not in conflict: $100 is the right *constant* if
he is going to use a constant, and a constant is not the best available answer.

What the curve does say is that the penalty is **asymmetric**, and steeper upward:

| clip | total round trip, median depth |
|---|---:|
| $50 | 5.05% |
| **$100** | **3.89%** |
| $113 | 3.86% |
| $190 | 4.31% |
| $250 | 5.18% |
| $500 | 8.73% |

Halving to $50 costs 1.2 points because the flat fee stops amortising. Going to $500
costs 4.8 points. **If he is going to be wrong about size, be wrong small.**

### 5.2 The rule that generalises

`S* = sqrt(0.95 × D)` holds only while the flat band does, so the usable form is:

    clip = min( sqrt(0.95 × exit_depth_usd), 190 )

    exit_depth  $2,000   →   $44   → but the 2% band applies below $47.50, so use $48
    exit_depth  $8,469   →   $90        (a freshly graduated PumpSwap pool, 85 SOL)
    exit_depth $13,330   →  $113        (our median tradeable pool)
    exit_depth $38,000   →  $190        (above here the answer is always $190)

`check.py` already computes `exit_depth_usd` on every row, `DEFAULT_CLIP_USD` is
already environment-overridable at `CRYPTO_CLIP_USD`, and `dashboard.py` already
prints round-trip cost at a fixed `CLIP = 100.0`. **Making the clip a function of
measured depth rather than a constant is the one sizing change with a derivation
behind it**, and it is a display change, not a rule change.

Stated honestly: this optimises *cost*, not *return*. It makes a losing strategy lose
slightly less. It is filed as arithmetic, not as an edge.

### 5.3 Why sizing up is not available as a response to losses

`GAPS.md`: at $1,000 only **34%** of candidates are tradeable within 5% slippage,
against 79% at $100. And the paper ledger's own pathology — **two** of the three sub-three-minute wins, Oiled
and titcoin, closed on pools holding **$0.67 and $0.74** nine minutes later — is a depth
failure, not a price failure. Those exits were $292 and $335 against quote sides that
evaporated. **At $500 clips they would not have been exits at all.**

---

## Part 6 — Exit discipline, and the arithmetic that says it is the whole game

The brief asserts exit matters more than entry when the base rate is 0.2%. Here is
the proof from Frank's own ledger rather than from principle.

### 6.1 The decomposition

⚠️ **Corrected. My first pass had this wrong and the error flattered the strategy.** It
assumed wins cap at 2.0× while using the *uncapped* P&L, which double-counted the win
column. The report gives both cuts and they must not be mixed.

From `REPORT_2026-09-15.md`: 9 wins in 76 measured closes, P&L **−$3,099**, or
**−$3,930 with wins capped at 2×**. Taking the capped cut, because RULE_V1's declared exit
*is* a 2.0× target and the uncapped wins are late closes:

    9 wins    × (+$100)  =  +$900
    total P&L            =  −$3,930
    ⟹ 67 losses total    =  −$4,830        ⟹  L = $72.09

**The average loser gives back 72% of the position, not 60%.**

The uncapped cut is a cross-check and it reconciles: losses are the same $4,830, so wins
totalled $1,731, an average realised win of **$192** — because at least three of the nine
closed well above target (OPAI 5.375×, titcoin 3.353×, Oiled 2.918×). **So "wins close at
2.0×" is not literally true**, and the capped figure is the conservative statement of the
same ledger.

I am not pairing this with `GAPS.md`'s 0.4015× median. That is a **median over all 7
closes including the winner**; this is a **mean over 67 losers only**. Different statistics
on different populations at n=7 against a declared `MIN_N` of 30 — which under
`/RULES.md` rule 1 is precisely the mixed-population error the rule exists to catch. The
corrections section of this file says the n=7 figures should not be quoted, and that
applies here too.

### 6.2 The two levers, priced

> ⛔ The 11.84% below is the **quarantined** v1 rate (see the note in §1). The arithmetic of
> the two levers holds for any h; the starting h does not. Recompute from v3 at n ≥ 30.

Breakeven requires `h × 100 = (1−h) × L`.

**Lever A, raise the hit rate.** Holding L at $72.09:

    h*  =  72.09 / 172.09  =  41.9%

From 11.84% to 41.9%. **A 3.5× improvement in entry selection.** Five attempts at entry
prediction have been retracted (`GAPS.md` W1). They produced *apparent* lifts of 14.5×,
5.4× and 16.1× — **every one of which was leakage**, a feature and an outcome measured
from the same historical record. So the honest version is not "none produced a 3.5×
anything"; it is that **the only things that ever looked like a 3.5× improvement here were
artifacts**, which is a worse fact, not a better one.

**Lever B, cut the average loss.** Holding h at 11.84%:

    L*  =  0.1184 × 100 / 0.8816  =  $13.43

**The average loser must lose no more than 13.4%.** Round-trip cost alone is 3.89%, so
the true budget for adverse price movement is about **9.5%** — and **~7.5% if correction
#4 above is right about pool fees.**

*(This lever is unchanged by the §6.1 correction: `L*` depends only on `h` and the win
size, not on the observed loss. It is the one number in Part 6 my first pass got right.)*

### 6.3 And lever B is not available either, which is the finding

A 13.4% average loss requires stopping out inside a 9.5% adverse move. Against that:

- Kamat: median time to graduation **1.0 minute**, p90 2.0 minutes. The whole event
  completes faster than any polling loop this project runs.
- Li et al. (arXiv:2608.20271, n=6.4M tokens): "a vast majority of these memecoins
  exhibit rug-pull characteristics **within one hour of launch**."
- Our own record: two pools drained from $2,973 and $2,000 to under $1 in **nine
  minutes**.
- 43% of closes at n=7 were **unpriceable** — the exit could not be valued at all,
  which is the failure mode a stop cannot protect against because there is no price to
  stop on.

**A stop-loss is a promise to sell at a price. The modal failure here is the absence
of a price.** The median position does not decline through 9.5%; it gaps through it
into a pool with no quote side.

### 6.4 What exit discipline actually reduces to

Given the above, "exit discipline" cannot mean a stop. It means three things, in
order, and all three are pre-trade:

1. **Refuse positions where the exit does not exist.** `exit_depth_usd ≥ $1,000`, quote
   side only, from reserves. This is **one of `RULE_V1`'s three conditions** — the others
   are `venue_type == "amm"` and `70 ≤ score ≤ 99` — and `PAPER_LOG.md` calls it *"the only
   measure here that has never been retracted."*
2. **Size to the exit, not to the bankroll.** Part 5.2.
3. **Treat a fast target as a quote, not a fill.** Three of nine wins closed in under
   three minutes; **two of those three — Oiled and titcoin — were on pools that held under
   $1 nine minutes later.** The third, OPAI, closed at 5.375× in 1m56s on a pool holding
   $2,948 of liquidity and $1,475 of quote side, where a $100 entry is ~7% of the quote
   and a $537 exit is ~16% of it. `GAPS.md` (2026-09-14) already says a two-minute target
   is a quote rather than a fill; the ledger now has the ending attached to two of them.

None of these is an exit *rule* in the sense of a trigger. They are entry refusals
that happen to be about the exit, which is standing rule 20 — **can I get out** before
**is it going up** — restated at the level of a single trade.

---

## Part 7 — The verdict

The brief asked for willingness to conclude that buying memecoins is negative expected
value for Frank. **It is, on the evidence available — with one procedural caveat that has
to come before the verdict rather than after it.**

⚠️ **Standing rule 2 says refuse to conclude below a stated minimum, and this is below
it.** `MIN_N` is 30 closes for *reporting*; `GAPS.md` G1 sets the bar for any statement
about *edge* at **n≥200 with interval width ≤10pp** and says plainly that "2026-09-14 is
the first date any statement about edge is worth hearing."
`REPORT_2026-09-15.md` puts v1's n=200 at "the week of 9/21" in practice. v1 is at **n=76
with a hit-rate interval of [6.36, 21.00]** — fifteen points wide.

**So the formal finding is withheld, and what follows is the honest read of an incomplete
record, labelled as such.** It is not a rule-2-compliant conclusion and must not be cited
as one. The date it becomes one is about a week away.

**The measured position.** 76 forward-recorded v1 closes on $100 clips: −$3,099, an
average of **−$40.78 per round trip**, or −$3,930 with wins capped at target. Including
inferred losses, 123 closes for −$7,799, **−$63.41 per round trip**. **Every v1 cut is
negative.** v2's 277 closes sit in the same report with B_high at 10.34% [4.83, 20.79] —
a different rule, also not shown profitable, not aggregated here because the entry criteria
differ.

And "the most honest measurement in this repository" would be too kind to it. 81 of 182 v1
closes came from a host pass where "whether anyone was watching is unknown," 16 from a hand
sweep, and `GAPS.md` (2026-09-14) documents that `close_decision` never consults the
quarantine — one B_high win closed on a price flagged ten hours earlier for 3.36× source
divergence. **It is the best-constructed record here and it has documented irregularities
in it.**

**The structural position.** To break even at the current hit rate, the average loser must
lose ≤13.4% against a cost floor of 3.89% — or ~5.9% if correction #4 is right — and a
population that gaps to zero in minutes. To break even at the current average loss of 72%,
the hit rate must rise **3.5×** against five retracted attempts at prediction, every one of
which produced an apparent lift that turned out to be leakage. **Neither lever looks
reachable**, and they are the only two levers there are.

**The literature agrees from three independent directions.** Marino: a buy-and-hold to
graduation keyed on the curve level is below breakeven, and the bot-share conditioning
stays below it over most of the range, before fees. Kamat: the best published cohort (all three socials,
1.919%) falls short of the 7.18% needed even at the cheapest entry point. Mongardini
et al. (arXiv:2507.01963, n=34,988): **82.89% of tokens returning over 100% show
evidence of artificial growth**, so the right tail Frank is buying is mostly
manufactured by someone whose exit he is funding.

**And the social layer is measured to be part of the problem, not the compensation.**
DWF Ventures, ~292,000 Fomo wallets, 90 days to August 2026: **6.16% profitable on
realized P&L, 25 wallets above $10,000 net.** Frank is trading through the feed with
no audience and no connections, which places him on the receiving end of the execution
asymmetry DWF describes rather than the sending end.

**So: buying memecoins is negative expected value for Frank at $1,000, in $100 clips, on
the evidence available, and I would rather say that than let the arithmetic sit in a
table.**

Three qualifications, because the conclusion should be exactly as strong as the
evidence and no stronger:

1. **This is a read on the strategy the system currently expresses, at n=76, below the
   repo's own threshold for saying it.** It is not a proof that no strategy works. Marino
   explicitly leave dynamic strategies open, and §3.5 describes a test of Frank's own
   selection that has never been run.
2. **The one asset here is not an entry rule.** D1, the one-sided-pool detector, holds at
   100% precision [85.7, 100] at **46.94% recall** on 23 flags against reserves, and
   `TRENCHES_REFERENCE.md` found no published prior art for it. **It carries an open
   caveat that must travel with it:** 33 of 38 D1 flags are fluxbeam pools, and
   `TRENCHES_REFERENCE.md` §4.0 states that *"until the non-fluxbeam test reads out at
   n≥20, 'fraud detector' and 'fluxbeam detector' are not distinguished."* It does not
   make money; it stops a specific class of loss. That is a different and more defensible
   product than a trading edge, and `GAPS.md` already says so.
3. **The cost work in Parts 4 and 5 is worth doing regardless of the verdict.** If he
   trades, it saves a few points a round trip. If he stops, it costs nothing. It is the
   only recommendation here that is robust to being wrong about everything else.

Frank asked for a sharp colleague rather than a yes-man. The sharp version: **the
$1,000 is tuition, the tuition is being paid at −$40 a lesson, and the thing being
learned is already written down in this repository.**

I am not a licensed financial adviser and none of this is investment advice. It is
analysis of a measurement record, which is what was asked for.

---

## Sources

**Retrieved 2026-09-17 unless stated.**

Peer-quality:
- Marino, G., Naviglio, M., Tarantelli, F. & Lillo, F. *Predicting the success of new
  crypto-tokens: the Pump.fun case.* arXiv:2602.14860, submitted 16 Feb 2026. §III,
  §V, §VI incl. eq. (2) and (3), §VII.A read in full from the arXiv HTML;
  **§VII.B onward truncated in fetch and remains unread.**
- Kamat, A.U. arXiv:2607.02823, Jun 2026. n=832,941. *(via `TRENCHES_REFERENCE.md`)*
- Mongardini, A.M. et al. arXiv:2507.01963, USENIX Security '26. n=34,988.
- Li, J. et al. arXiv:2608.20271, 20 Aug 2026. n=6.4M.
- Gerzon, Weintraub, In, Mislove & Nita-Rotaru. *Quantifying the Threat of Sandwiching
  MEV on Jito.* IMC '25, DOI 10.1145/3730567.3764493. **521,903 sandwiches,
  $7,712,138 victim losses, Feb 9 – Jun 9 2025, median loss ≈$5 per sandwiched
  transaction.** No arXiv preprint; full text via the authors' hosted copy.

Fee and venue documentation:
- `help.fomo.family` trading-fee article, as quoted with retrieval dates by
  FomoAppGuide, *fomo Fees: What the fomo App Charges at Each Trade Size*, verified
  2026-08-20. **Referral-affiliate site; quotes primary with dates.**
- `fomo.family/terms`, revised 2026-08-17.
- CryptoReferralCodes, *FOMO App Fees Explained 2026*, re-verified 2026-08-24.
  **Referral-affiliate site.**
- DefiLlama, fomo protocol page — fees/volume ratio, read 2026-08-14 and 2026-09-17.
- `bundles.jito.wtf/api/v1/bundles/tip_floor`, payload 2026-09-16.
- solana.com/docs/core/fees/fee-structure — fees charged on failed transactions.
- Kraken, Coinbase public tickers — SOL spot, 2026-09-17.

Market research:
- DWF Ventures, ~292,000 Fomo wallets, 90-day realized P&L, via AlexaBlockchain,
  2026-08-28. **VC arm of a market maker; the underlying analysis is not published as
  a paper.**

Ours, cited not restated:
`docs/TRENCHES_REFERENCE.md`, `RULES.md`, `GAPS.md`, `VENUE.md`, `PAPER_LOG.md`,
`EXIT_DEPTH.md`, `FRAUD_DETECTION.md`, `FEASIBILITY.md`, `ONCHAIN_COST.md`,
`data/findings/REPORT_2026-09-15.md`.

---

## Appendix — what the verification pass changed

This document was checked against its own sources before it was handed over, per standing
rule 10a's principle that a gate catches what a checklist forgets. The corrections are made
in place and flagged with ⚠️ where they appear. The ones that changed a conclusion:

| # | was | is | why it mattered |
|---|---|---|---|
| 1 | §6.1 average loser **60%**, required improvement **3.2×** | **72%**, **3.5×** | mixed the capped and uncapped cuts of the same ledger; flattered the strategy |
| 2 | Part 7 verdict stated flatly | stated **below rule 2's threshold**, with the date it clears | `GAPS.md` G1 sets n≥200; v1 is at 76 with a 15-point interval |
| 3 | §2.1 SOL-per-trade "derivable on a call we already make" | **not computable** — path-dependent, and we rarely see a token twice | would have sent someone to build a feature the data cannot support |
| 4 | §4.3 pool fee 0.25%/side | flagged: PumpSwap is documented at **1.25%** | if right, the round trip is ~5.9% not 3.89% |
| 5 | Part 1 "every entry signal is already priced" | scoped to curve-level features | Kamat's launch-time features are a different category |
| 6 | §3.3 Marino "categorically, across the range" | quoted as the authors wrote it | the strong version was mine, not theirs |
| 7 | D1 quoted as 100% precision | **plus 46.94% recall and the open fluxbeam caveat** | "fraud detector" and "fluxbeam detector" are not yet distinguished |

Four attributions were also corrected ($2,938 is `GAPS.md` not `FEASIBILITY.md`; the
two-minute-target line is `GAPS.md` not `FRAUD_DETECTION.md`; `RULE_V1` is three conditions
not one; the brief's "3 wins in 69" is in no file here), and the MEV and failed-transaction
quantification the brief asked for was missing entirely and is now §4.3b.

**What did not change:** the required-probability table in §3.2, the closed-form clip size
in §5.1–5.2, the two-cliffs disambiguation in §4.5, and the $13.43 figure in §6.2. Those
reproduced exactly.

---

*Research document. Nothing here filters, gates or scores anything, no code was
modified, and no trade was placed or recommended. Every threshold from outside this
repo is labelled as a measurement or a convention; every number I derived myself is
marked as arithmetic on sourced inputs.*
