# Memecoin rules and running observations

Started 2026-09-17. **This is a running file. Append, date every addition, never delete —
supersede in place and say what it replaced.**

## What this file is, and what it is not

This is **not** `/RULES.md` at the repo root. That file holds the 24 standing rules
(numbered 1–23, plus 10a) for
how this repo does research — reporting discipline, measurement discipline, shipping
discipline — and every one of them was bought with a specific mistake. It still governs
everything here.

This file is about **memecoins as an activity**: launching them and buying them. Rules
here are numbered with a letter prefix so they can never be confused with the standing
rules:

| Prefix | Section | Owner |
|---|---|---|
| **C** | Creator side | seeded 2026-09-17 |
| **B** | Buyer side | **reserved — see §B** |
| **O** | Observations not yet rules | open |

**Every rule carries a source or a measurement.** Rules that are opinion are labelled
`[OPINION]` and may be argued with. Rules with a number behind them may not be relaxed
without producing a better number.

---

# §C — Creator side

## Hard lines

**C1. Never buy your own token through a wallet that does not obviously belong to you,
and never sell a dev buy into arrivals.**
*Source: DOJ/USAO-MA "Operation Token Mirrors", charges 2024-10-09; CLS Global guilty plea
Jan 2025 to conspiracy to commit market manipulation and wire fraud; ten further
defendants charged N.D. Cal. March 2026.* The charge was **wire fraud**, which does not
require the token to be a security, so the SEC's 2025-02-27 staff statement that memecoins
aren't securities does not help. On-chain evidence is permanent and reconstructs easily
after the fact.

**C2. Fee-recipient wallets and trading wallets stay strictly disjoint.**
*Source: platform mechanics — Bags allows up to 100 fee claimers, pump.fun up to 10
(medium confidence on the 10).* A wallet that both receives fees and trades the token is
indistinguishable on-chain from a bundle. There is no upside to mixing them.

**C3. A platform offering a feature is not a legal opinion.**
*Source: StonkFun documents a dev buy of up to 75% of supply, landed atomically as the
pool's first trade; pump.fun's self-buy is measured by Kamat as raising graduation odds.*
Both are disclosed features. Neither is a defence to selling into buyers you attracted.

**C4. Apply the hostile-reconstruction test before every launch.** If a full on-chain
history of the token, published by someone who dislikes you, would embarrass you — don't.
`[OPINION]`, but it is a prediction about what discovery looks like and it takes ten
seconds.

**C5. Get a CPA before the first launch, not after.**
*Source: IRS Rev. Rul. 2019-24 — airdrops are ordinary income at fair market value on
dominion and control; creator fees received in SOL are income at receipt and every later
disposal is a separate capital event.* At any meaningful launch volume this is thousands
of taxable events per year, attached to a real LLC.

## Economics

**C6. Creator revenue is `volume × rate`. You control the rate by choosing a platform.
You do not control volume at all.**
*Source: pump.fun/docs/fees (2026-05-20); docs.bags.fm fee modes.* Every creator-side
decision that is not about volume is rearranging a small multiplier on an unknown.

**C7. Set all three social links on every launch, because they are free — not because
you expect 17.4×.**
*Source: Kamat 2026, n=832,941: all three socials 1.919% vs 0.110% graduation, 17.4× lift;
Telegram alone 8.94×, Cox HR 5.402.* **The measured variable is link presence in metadata,
not audience size**, and Kamat explicitly declines causality, offering effort-proxy and
selection as competing readings. `[OPINION]` — most of that lift is probably the effort
channel, which does not transfer to someone who sets the link and changes nothing else.

**C8. Never accept the 30.00 SOL platform default.**
*Source: Kamat 2026 — launches left at exactly 30.00 SOL initial market cap graduated
**1 time in 91,247**, a rate of 0.0011%.* Almost certainly a selection effect rather than a
mechanism, which means changing the number without changing the care behind it changes
nothing — but there is no argument for keeping the default either.

**C9. Kamat's 31.04 SOL is a market cap, not a deposit. Do not price a self-buy off it
until the unit is settled.**
*`CREATOR_PLAYBOOK.md` §2.4.* The pump.fun curve is seeded at 30 virtual SOL and Kamat's
Q2 is "exactly 30.00 SOL (platform default)", so crossing into Q4 means moving market cap
by **1.04 SOL, not depositing 31.04.** The breakeven is
`deposit / (0.005491 × 0.0095)` and the two readings differ ~30×: at ~1 SOL it needs
**~$2.0M** of post-graduation volume, at 31.04 SOL it needs **~$59.4M**. **I originally
wrote the second and it inverted the conclusion.** `[OPINION]` — the ~1 SOL reading is
almost certainly right. Settleable from the curve parameters in `TRENCHES_REFERENCE` §1.1
plus Kamat's mcap definition. **Until it is settled, this rule says "don't price it",
not "don't do it".**

**C9a. Whatever the size, a self-buy is a position and gets position discipline.**
Kamat's effect is associational; `TRENCHES_REFERENCE` §2.2 records curve-first tokens
returning ≥2× at **0.01%** — two wins in 14,802. And selling it into arrivals is C1 at any
size. Size changes the restitution figure, not the character of the act.

**C10. Quote creator-earnings distributions on the full denominator, or say you can't.**
*`/RULES.md` standing rule 3, applied to external data.* The published pump.fun
distribution — 83.4% under $1,000, 34.9% under $100 — is measured on **3,566 creators who
claimed something**, not on all launches, and under the old 0.05% creator rate. Against a
launch population on the order of **13,700/day** *(derived from Kamat's n over an inferred
~61-day window — order-of-magnitude only)*, the unconditional figure is far worse and is
not published.

**C11. Distinguish the two creator strategies before picking one.**
*Source: SolanaFloor top-100 analysis, 2025-06-04.* 43% of top-100 earners launched fewer
than five tokens (26 launched exactly one); 19% launched over 1,000 each. Mean 1,626,
**median 10**. `[OPINION]` — only the industrial path is a *strategy*; the other is an
outcome, and it is a software problem, not a creative one.

## Reading the platforms

**C12. Read the fee page before every launch, not once.** pump.fun's own fee page states
the platform may change these fees at any time without notice. The schedule in
`CREATOR_PLAYBOOK.md` is a snapshot dated 2026-05-20.

**C13. Fee splits are mutable. If you are a recipient rather than the admin, you have no
guarantee.**
*Source: `bags config update` and `bags config transfer-admin` in Bags' own CLI docs;
"The claimer list is not immutable — the fee-share owner can call `setClaimers`" in the
EVM docs.*

**C14. Express every threshold in SOL, never USD.**
*Standing rule inherited from `TRENCHES_REFERENCE` §W1, which found `GRADUATION_MCAP_USD =
69000` encoding a USD constant against a SOL-denominated mechanism.* Partially corroborated
2026-09-17: **Bags' own docs list 85 SOL as the graduation raise for five of seven fee
modes.** **Do not merge the raise and the FDV** — 85 SOL is $8,482, and it only maps to a
~$41k FDV through pump.fun's specific curve geometry. Bags' own 96%-locked mode graduates
on a 55 SOL raise at a stated ~4,978 SOL FDV: **same kind of raise, wildly different FDV,
because less supply is in the pool.** StonkFun separately configures a **$40,000** market
cap. None of the three is near $69,000; only the pump.fun query settles §W1.

## Tax tokens

**C15. On any tax token, check three fields before anything else.**
*Source: Solana Foundation docs on `TransferFeeConfig`, retrieved 2026-09-17.*

| Field | Question |
|---|---|
| `transferFeeConfigAuthority` | Can the rate change? Non-null = yes, with two epochs' warning. |
| `withdrawWithheldAuthority` | **Who owns the tax stream?** This is the counterparty. |
| `newerTransferFee.transferFeeBasisPoints` | What rate will actually apply. |

All three are in the `getAccountInfo(jsonParsed)` response the scanner **already makes**.
Zero additional API calls.

**C16. Tax collection is trustless. Tax distribution is not.**
*Source: Solana docs — the fee is withheld by the token program automatically, and
`HarvestWithheldTokensToMint` is permissionless; but `WithdrawWithheldTokensFromMint`
requires the authority, and the sell-and-distribute leg is pure off-chain policy with no
on-chain event when it stops.* The trustless first half is what makes the discretionary
second half look trustless.

**C17. Do not launch a tax-and-distribute token.** `[OPINION]`, stated as a
recommendation in `TOKEN_MECHANICS.md` §5.2, on three grounds: both hosted paths pay the
creator **zero**; the DIY path makes Frank the sole party able to convert a pool of other
people's withheld tokens into money against a public promise to return it, with a real name
and a real LLC attached; and the design needs volume, converting the modal outcome (no
attention) into the bad-looking outcome (took money, distributed nothing).

**C18. "Passive income" is the wrong word and using it is how people get misled.**
*Identity:* `distributed ≈ tax_rate × volume`, and `volume = buys + sells`. There is no
third term and nothing is produced. The best statement of this is on StonkFun's own side of
the table: *"Distributions to reward-token holders are a mechanical property of the token,
not a dividend or yield."* **Attribution caveat:** that line is in the third-party GitBook,
not confirmed on a first-party page — `[UNVERIFIED]` that StonkFun itself says it.

## Discipline

**C19. Do not do fraud detection and token launching under the same name.** `[OPINION].`
The repo's one proven asset is a fraud detector with published precision
(`FRAUD_DETECTION.md`: 100% [85.7, 100] at 46.94% recall, still carrying
`TRENCHES_REFERENCE` §4.0's open fluxbeam caveat). Detection and launching are
adjacent in topic and opposite in reputation; doing both makes the first unpublishable.

**C20. Record first, score nothing.** *`/RULES.md` standing rule 10, restated for this
domain.*
Anything new learned about creators — tax fields, fee modes, launch metadata — gets written
down on every observation and filters nothing until it has precision and recall against a
labelled set.

---

# §B — Buyer side

*Seeded 2026-09-17 from `docs/TRADING_PLAYBOOK.md` and `docs/CHAINS.md`, into the §B block
the creator task reserved. **Nothing in §C was modified and no C-number was reused.***

The creator task left one cross-reference inside the reserved block, and it is kept
verbatim because it is the right thing to have at the top of this section: **the fee a
creator collects and the cost a buyer pays are the same number seen from two ends.** Bags'
High Flat mode charges 10% per trade, of which 5% is the creator's, and that is not two
facts.

## The arithmetic of entry

**B1. The breakeven graduation probability is just the ratio of market caps:
`required p = entry mcap / graduation mcap`.**
*Source: Marino, Naviglio, Tarantelli & Lillo, arXiv:2602.14860 §VI eq. (3), retrieved
2026-09-17: `p(vSol;θ) > vSol²/115²`. Price on the curve is `vSol²/k`, so FDV ∝ vSol² and
the substitution collapses it.* No curve mathematics needed at the point of use. This
closes a gap `TRENCHES_REFERENCE` §2.5 marked NOT RETRIEVABLE.

**B2. A $25,000 entry needs a 61% chance of graduation. The best cohort anyone has
published is 1.919%.**
*Arithmetic on B1 at FDV_grad = $40,932; cohort from Kamat 2026, n=832,941, all three
socials.* **$25k is not early — it is 70% of the way up the curve** (vSol ≈ 89.9, 59.9
real SOL deposited of 85). Even at the cheapest possible entry, our median observed curve
FDV of $2,938, the required 7.18% is **3.7× above** the best published cohort.

**B3. Do not overstate B1. Marino kill buy-and-hold-to-graduation and explicitly leave
dynamic strategies open.**
*Verbatim, §VI: "It is important to stress that this is the breakeven curve **only for
buy-and-hold strategies**… it might be possible to devise dynamic strategies delivering
positive expected profits also when the conditional probability lies below the breakeven
curve."* Holding past the bond divides the requirement by the realised post-graduation
multiple: at $25k, 61.08% ÷ m. Still far above any measured rate, but a different order of
impossible, and the distinction is the paper's own.

**B4. Graduation market cap is $41,000 ± $1,000, it moves with SOL, and nothing alarms
when it does.**
*410.8 SOL FDV from the curve mechanism; SOL $99.64 Kraken, $98.41 Coinbase, 2026-09-17 →
$40,932 / $40,427. The `$69,000` constant implies SOL ≈ $167.90.* Recompute per pass from
the price already fetched for `onchain_reserves.quote_price_usd`. This is
`TRENCHES_REFERENCE` §W1 and it is a buyer-side rule too: every entry threshold quoted in
USD drifts silently.

**B5. Record SOL-per-trade. Score nothing.**
*Source: arXiv:2602.14860 §VII.B, retrieved 2026-09-17 — the conditioning variable is "the
cumulative number of swaps observed up to the moment a given vSol threshold is first
reached," thresholds 10/50/100/500/1000, and "fast accumulation of liquidity through a
small number of trades is the strongest predictor of graduation, dominating other
variables across the entire range of vSol."* ⚠️ **Not computable today, and my first pass
said it was.** The variable is *cumulative* swaps to a threshold **first reached** — path
dependent — and `TRENCHES_REFERENCE` §4.2 and `GAPS.md` both state we *"rarely observe the
same token twice"* and have *"no capability to re-observe a token we have already seen."*
A 5-minute rolling `txns` count is not a cumulative-to-threshold count. **`GAPS.md` prices
the re-poll that would unblock it at 54 Dexscreener calls per sweep**, ~216/day at 6-hourly
cadence, a ~10% increase in call volume — that buys the universe, not the feature.
**[NOT RETRIEVABLE]** whether it clears breakeven: the fetch truncated before Figure 7.
The bot-share conditioning does not, so assume this does not either.

**B6. Test your own selection before trusting it, on the full denominator.**
*`/RULES.md` rules 3 and 14, applied to Frank's Fomo history.* Count **every** sub-$25k
entry since 2026-09-10 and what fraction reached the bond, against the 61% in B2. Counting
only the memorable ones is exactly the survivorship rule 3 exists to catch.

## Cost and sizing

**B7. `clip = min( sqrt(0.95 × exit_depth_usd), 190 )`.**
*Derived: minimising `1.90/S + 2S/(D+S)` — Fomo's flat $1.90 round-trip fee in the
47.50–190 USDC band against `GAPS.md`'s constant-product impact model.* At the median
tradeable depth of $13,330 this gives **$112.50**; at a freshly graduated 85 SOL pool
(~$8,469) it gives **$90**. Above D ≈ $38,000 the answer is always $190, the top of the
flat band. **Optimises cost, not return.**

**B8. If you are going to use one clip size instead of B7, use $100. If you are going to be
wrong about size, be wrong small.**
*Arithmetic on B7: at the median tradeable depth of $13,330, $100 costs 3.89% round trip
against the $112.50 optimum's 3.86% — three basis points.* The penalty is asymmetric: $50
costs +1.2 points (the flat fee stops amortising), $500 costs +4.8 points. **B7 supersedes
this whenever `exit_depth_usd` is known**, which on our own rows is always; B8 is the
fallback, not a competing answer.

**B9. Inside Fomo's flat band, a smaller order is strictly worse on fees and better on
slippage. Let B7 arbitrate, and never split the difference by habit.**
*Source: `help.fomo.family` fee bands, verified 2026-08-20 — flat 0.95 USDC across the
whole 47.50–190 band.* A $50 order pays 1.90% and a $190 order pays 0.50% **for the
identical $0.95.** ⚠️ **My first pass wrote this as "never size between $47.50 and $99,"
which contradicts B7's own worked examples** ($90 on a fresh 85 SOL pool, $48 on a $2,000
pool) — on a thin pool the slippage saving genuinely beats the fee penalty, which is what
the square root in B7 encodes. The usable version is the gradient, not a floor. **The
referral discount does not touch the flat band**, so it is worth nothing at this size.

**B10. At $100 clips the fill is worth about seven times the fee. Do not switch venues for
fees alone.**
*Arithmetic: median-depth round trip = 1.90% fee + 1.99% slippage = $3.89; a p90 pool =
1.90% + 12.45% = $14.35.* The entire spread between the cheapest and dearest terminal is
smaller than the gap between a median pool and a bad one.

**B11. Quote `GAPS.md`'s two cliffs separately. They are different claims and both are
right.**
*`GAPS.md` Part 5 states "the cliff is between $100 and $250" and "the cliff is between
$500 and $1,000" in the same section.* The **cost** cliff is $100→$250 (the "over 20%"
column goes 0% → 21%) and governs expected value; the **availability** cliff is
$500→$1,000 (tradeable-within-5% goes 64% → 34%) and governs how many candidates exist.
Memory's "$100 not $500" is the cost cliff and it verifies.

**B12. Re-read the fee schedule before quoting it. Fomo's moved three times in twelve
days.**
*Source: FomoAppGuide's dated readings of `help.fomo.family`, 2026-08-08, 08-14 and 08-20;
Fomo's Terms rewritten 2026-08-17 now name no fee figure outside perps and reserve
modification "at any time in its sole discretion."* The binding number is the one on the
confirmation screen.

## Exit

**B13. At the measured hit rate, the average loser must lose ≤13.4%. It cannot, so the
position has to be refused at entry rather than managed after.**
*Derived from `REPORT_2026-09-15.md`: 9 wins in 76 measured closes, **−$3,930 with wins
capped at 2×** ⟹ 67 losses total $4,830 ⟹ **the average loser gives back 72%**. Breakeven
needs either h = **41.9%** (a **3.5×** improvement against five retracted attempts at
prediction, every one of which turned out to be leakage) or L = $13.43.* ⚠️ **Corrected —
my first pass mixed the capped and uncapped cuts of the ledger and got 60% and 3.2×, which
flattered the strategy.* Against a 3.89% cost floor the true
budget for adverse movement is ~9.5%, and Kamat's median time to graduation is **1.0
minute** while 43% of closes at n=7 were **unpriceable**. **A stop-loss is a promise to
sell at a price; the modal failure here is the absence of a price.**

**B14. A fast target is a quote, not a fill.**
*Source: `REPORT_2026-09-15.md` — Oiled (2.918×) and titcoin (3.353×) both closed 2m49s
after entry on $2,973 and $2,000 of quote depth; nine minutes later both pools held under
$1.* Three of v1's nine gated wins closed inside three minutes. Excluding them takes the
rate from 11.84% to 8.22%.

**B15. Never copy-trade, and treat the feed as coincident with a crowd that has already
moved.**
*Source: DWF Ventures, ~292,000 Fomo wallets, 90 days to 2026-08, via AlexaBlockchain
2026-08-28 — **6.16% profitable on realized P&L; 25 wallets above $10,000 net**.* DWF name
the mechanism as execution asymmetry and are explicit that the data does **not** establish
that followed traders trade against followers. Two vectors need no bad intent: a follower
acting seconds later moves a thin pool against themselves, and a trader can accumulate in
a separate wallet before buying through the public one, so a verified wallet confirms what
happened in *that* wallet without proving it is the complete position.

## Venue and chain

**B16. Custody is a gate, not a score. No key export, no trade.**
*Source: each platform's own docs, retrieved 2026-09-17.* Full export anytime: Jupiter,
Trojan, Axiom (Turnkey), Nova. One-time reveal: Photon, BullX, Bloom. **No export at all:
Banana Gun ("you can't"), Maestro (keys AES-encrypted on Maestro's servers), GMGN
(prohibited even for keys you imported).** A platform that will not give you your key is a
custodian that has not said so.

**B17. Check a dormant venue is still trading before returning to it.**
*Source: BullX suspended trading 2026-06-01 (Discord announcement 2026-05-31; crypto.news,
PANews). DefiLlama: **$953.64 of Solana fees over 30 days** against Axiom's $41.11M.* Its
site still serves an app shell and its changelog was last touched September 2024. **BullX
and BullX Neo are the same product**, not a successor and a predecessor.

**B18. Trade from a dedicated browser profile with no extensions.**
*Source: Socket Threat Research, 2026-09-09 — four malicious Chrome/Firefox extensions
harvest authenticated **Axiom** session tokens, `bundleKey`, `sBundles`, `eBundles` and
cookies. Chrome listings pulled July 2026; `Orbit Tracker` still live on Firefox at
publication.* Names Axiom and Pump.fun Terminal specifically. It does not exploit the
platform — it runs inside an already-logged-in session, so no platform's security posture
protects against it.

**B19. Do not add a chain. Record `chainId` on every observation anyway.**
*`docs/CHAINS.md` Part 1.4.* Base has 38% of Solana's DEX volume and free data on both
aggregators; what it does not have is **any published graduation rate or bot-share
measurement**, so every threshold in this repo would be rebuilt against nothing. And per
`GAPS.md` W2 we already see ~1.9% of one chain's launch stream on a saturated rate limit —
**adding a chain multiplies a negative number.** Recording the chain costs zero calls and
nothing can be measured later that was not recorded now.

**B20. Separate "bad fee" from "bad fill" from "thin pool" before switching venues. They
have three different fixes and one of them is `nothing`.**
*`/RULES.md` standing rule 5, applied to a claim about our own trading.* For 20 trades
record the fee shown, the fill, and Dexscreener's `priceUsd` and `exit_depth_usd` at the
same second, then compare realised slippage against `2 × size/(depth+size) + 0.25%`. **If
it tracks the model the pools are thin and switching buys nothing.** `check.py` already
computes every input on the right-hand side.

**B21. Fomo is mid-table on fees, not the expensive one — and Jupiter is 2–10× cheaper
than every terminal including Fomo.** `[OPINION]` on the framing, arithmetic on the inputs.
*Round trip on $100 from each platform's published rate: Jupiter Ultra $0.20 (mature) or
$1.00 (token under 24h); Axiom Champion $1.50; **Fomo $1.90; Axiom base $1.90**; GMGN,
Trojan and Photon $2.00; Pump.fun Terminal ~$2.32 (**[UNVERIFIED]** — no official fee page
exists); Moonshot $5.00.* Fomo is **fifth of eleven** and absorbs gas, priority fees and
token rent, which none of the terminals do. **But on tokens under 24 hours old — most of
what he trades — Jupiter is $1.00 against Fomo's $1.90, so he is paying ~90% more than he
needs to.** That is real and it is $0.90 a trade, against a bad fill costing ~$12 (B10).
Separately true: the flat band makes him pay 0.95% where the headline says 0.50%, and **a
fee that is double what you believe it to be feels like a bad fill** — which is why B20
exists.

## Discipline

**B22. Buying memecoins looks negative expected value at this size — and under standing
rule 2 that is a read, not a finding, until n=200.** `[OPINION]` on the framing, measured
on the substance.
*76 forward-recorded v1 closes on $100 clips: **−$3,099, an average of −$40.78 per round
trip**; −$63.41 including inferred losses. Every v1 cut is negative.* ⚠️ **The hit-rate
interval is [6.36, 21.00] — fifteen points wide — and `GAPS.md` G1 sets the bar for any
statement about edge at n≥200 with width ≤10pp**, which `REPORT_2026-09-15.md` puts at "the
week of 9/21". v2's 277 closes are a separate rule and are not aggregated in. **Do not cite
B22 as a rule-2-compliant conclusion; cite it as the honest read of an incomplete record,
with a date about a week out when it becomes one.**

What is not provisional: both breakeven levers (B13) are out of reach and there are only
two, and three independent literatures point the same way — Marino on the buy-and-hold
breakeven, Kamat on cohort rates, and Mongardini et al. (arXiv:2507.01963, n=34,988) that
**82.89% of tokens returning over 100% show evidence of artificial growth**, so the right
tail is mostly manufactured by someone whose exit is being funded.

**B23. The one asset here is not an entry rule, and the cost work is robust to being
wrong about all of it.**
*`FRAUD_DETECTION.md`: D1 at 100% precision [85.7, 100], 46.94% recall, still carrying
`TRENCHES_REFERENCE` §4.0's open fluxbeam caveat.* D1 does not make money, it stops a
class of loss. And B7–B12 save a few points per round trip if he trades and cost nothing
if he stops — **the only recommendation in §B that does not depend on the verdict in
B22 being right.**

**B24. Front-running the copiers of a widely-copied wallet is REJECTED. Do not re-propose
it without the measurement named below.** `[REJECTED 2026-09-17]`

*The idea, and it is not a silly one.* Copying a heavily-copied wallet is already ruled
out — copying it makes you its exit liquidity, the same objection raised against Fomo's
copy button. The proposed improvement was to **not** copy, but to detect the wallet's buy
and get in ahead of the wave of copy-buys that follows it.

*Why it is rejected: the signal is not scarce.* Cupsey, the named example, traded
**9,380 times across 1,144 distinct contracts in seven days** (KOL Explorer, week to
2026-09-17). That is **~1,340 trades a day, ~56 buys an hour.** A buy from this wallet is
close to a continuous event. So the strategy does not reduce to "detect his buy" — it
reduces to **"predict which of ~56 buys an hour draws a wave worth fronting"**, which is a
second prediction problem with **the same shape as the one Marino killed**: by the time
the wave is detectable, it is priced. Trading one unsolved prediction for another is not
progress.

*What would reopen it.* A **measured** copy-wave effect, not an assumed one. The test is
well formed: for each tracked buy, count follow-on buys and the price path over the next
N seconds against a matched control. Transaction-level history is available
(`/v0/addresses/{addr}/transactions`, unblocked 2026-09-17 — see `TRACKER_SCOPING.md`
§0.5). Standing rules apply in full: **pre-commit the window and the effect size to a file
before looking, key on contract address, n≥30 distinct contracts, report the interval.**
Until that exists this is an idea, not an edge.

*What is NOT rejected.* **Observing the wallet.** That is cheap, carries no exit-liquidity
risk, and the machinery already exists — `WATCHED_WALLETS` in `site/api/helius.mjs`.
**Observation is not copying, and it is not front-running either.**

---

# §O — Observations not yet rules

Things measured or found that are not yet load-bearing. An observation is promoted to a
rule when it has a number and a decision attached, or deleted when it turns out to be
noise.

**O1 (2026-09-17). The pump.fun creator fee schedule has a cliff 2.2% above graduation.**
Graduation FDV is 410.8 SOL (`TRENCHES_REFERENCE` §W1). The 0.950% creator-fee band starts
at 420 SOL. So a freshly graduated token has to rise **2.24%** (420/410.8 − 1) before the
creator's rate roughly **triples**, from 0.300% to 0.950%. Arithmetic on two published
numbers.
No decision attached yet. **Possible implication for the buyer side too**: the fee a buyer
pays also changes at that boundary, and the total actually *falls* from 1.250% to 1.200%
while the creator's share triples — the **protocol's** share collapses from 0.950% to
0.050% and the **LP's** rises from 0% to 0.200%, so the protocol hands almost its entire
cut to the creator at exactly that point. **[DERIVED]** — pump.fun's fee page publishes
protocol and LP columns for both regimes, but the framing "hands its cut to the creator" is
my reading, not a platform statement. Worth someone checking whether the discontinuity is
visible in trade behaviour.

**O2 (2026-09-17). The fee schedule pays creators least for the largest tokens.**
0.950% at a 420–1,470 SOL market cap, decaying to **0.050%** above 98,240 SOL — one
nineteenth of the peak. Whatever pump.fun is incentivising, it is tokens in the
$42k–$147k band, not winners.

**O3 (2026-09-17). Nothing points at $69,000; two different quantities point near $40k and
must not be merged.** pump.fun's FDV computes to 410.8 SOL ≈ $40,994 — **an FDV**. Bags
documents an 85 SOL **raise** for five of seven fee modes, which is $8,482 and implies
nothing about FDV without Bags' curve parameters (its 96%-locked mode graduates on 55 SOL
at a stated ~4,978 SOL FDV). StonkFun configures a **$40,000 market cap**, flagging "about
to graduate" at $32,000 — *third-party GitBook, medium confidence.* So: one computed FDV,
one independent raise, one configured mcap. This does not prove `TRENCHES_REFERENCE` §W1,
which still needs the query against the 86 witnessed curve→AMM transitions.

**O4 (2026-09-17). A launchpad documents the creator's opening buy as an atomic same-slot
bundle, and sells it as a feature.** *"The creator's opening buy, if any, is submitted as
part of the same atomic Jito bundle as the payment, mint, pool and liquidity"*;
*"executed as the pool's literal first trade… there is no block in which anyone else could
trade ahead of it."* Cap: **75% of supply.**

**Provenance matters here and I overstated it on the first pass.** This is the third-party
StonkFun GitBook, **medium confidence** — not StonkFun's own published product copy, and
not a measurement. So it is *corroborating description* of the mechanism behind
`TRENCHES_REFERENCE` §W3 — that a same-slot buy is structurally the creator's, because no
outsider can be atomic with a mint — **not external confirmation that our >50%/sub-400ms
figure is mostly bundling.** §W3 still needs the funding-graph test to move from
reinterpretation to finding. What this does add: **at least one launchpad ships bundling
as a product**, which raises the prior on §W3's reading considerably.

**O5 (2026-09-17). Probable source confusion, flagged before it propagates.** A search
summary attributes to MELT the claim that **98.7% of pump.fun token-creation transactions
also contain a buy from the developer.** I did not retrieve this from the paper.
**`TRENCHES_REFERENCE` §1.3 and §3.2 attribute an identical 98.7% to Solidus Labs for a
completely different claim** — tokens showing pump-and-dump or rug characteristics. The
exact numeric match is strong evidence the Solidus figure was re-attributed by a summariser.
**Do not use the number.** `[UNVERIFIED]`. If some version of it holds it matters, because
it would mean "dev bought" carries almost no information and only "dev bought a lot" does —
the same unit question as **C9**. MELT is open at `github.com/git-disl/MELT`.

**O6 (2026-09-17). The parameter that decides everything on the creator side is not
measured anywhere.** The distribution of **post-graduation lifetime volume** is what turns
a fee rate into money, and I found no published measurement of it. Every expected-value
calculation in `CREATOR_PLAYBOOK.md` §2 is parameterised on it. **It is computable from
the repo's own witnessed graduations** and would be the highest-value single query before
any creator-side work.

**O7 (2026-09-17). Nobody is measuring the tax-token population.** No paper, dataset or
vendor I could find has measured what fraction of tax-and-distribute tokens stop
distributing, or how fast. Given the repo already makes the `getAccountInfo` call that
reads the extension list, this is an original measurement available at **zero additional
API cost.** Same shape as the D1 one-sided-pool detector: ahead of the public state of the
art because we read a field almost nobody reads.

**O8 (2026-09-17, buyer side). Our 0.01% curve figure cannot test a sub-25k entry claim,
and should stop being quoted as though it can.** `VENUE.md` measures curve-entry tokens at
**0.01% ≥2×, two wins in 14,802**. But Kamat's median time to graduation is **1.0 minute**
(p90 2.0 min) and our first outcome checkpoint is at **1 hour**. A token that bonded at
t+60s and round-tripped by t+40min is recorded here as a loss. **The 0.01% partly measures
our checkpoint schedule rather than the strategy.** It stands as a measurement of what
*we* would have captured; it does not stand as a measurement of what was available.
Fixable by adding a sub-10-minute checkpoint for curve-entry rows, which is a collection
change and not mine to make.

**O9 (2026-09-17, buyer side). Whether Fomo routes DFlow's `/order` or `/intent` path is
undisclosed, and it decides what "MEV protection" means.** Fomo confirms DFlow routing on
its own site (`fomo.family/answers/is-fomo-app-safe`). DFlow's docs describe `/intent` as
the genuinely sandwich-resistant path — user signs an open order with no fixed route,
DFlow lands open+fill atomically as a Jito bundle — and say it is **opt-in and the
minority path** ("the majority of builders stay on `/order`"). **Fomo does not say which
it uses.** Also undocumented: the value of DFlow's "governable threshold" on fill price
(present in 2022 marketing, absent from current docs entirely) and a `segmenterFeePct`
field that exists in DFlow's OpenAPI spec with no published value. **There is no
independent execution-quality audit of DFlow, Jupiter, or any terminal in this space.**
Every fill-quality claim in the entire sector is self-published.

**O10 (2026-09-17, buyer side). Moralis's free tier ended 2026-09-01 and its own cached
pages still advertise it.** Minimum is now $149/mo. Anything written before September that
names Moralis as the free multi-chain indexer is now wrong. **Alchemy's permanent 30M
CU/mo free tier covers Solana, Base, BNB and Ethereum on one key** — roughly 8%
utilisation at this repo's measured ~114k calls/month (`ONCHAIN_COST.md`) — and is the
replacement if multi-chain ever happens.

**O11 (2026-09-17, buyer side). Two source-integrity artifacts encountered during venue
research, recorded so nobody hits them cold.** A search for the Robinhood Chain gas
subsidy surfaced a **GitHub release note** formatted as a market update, ranking alongside
real journalism — a GitHub release is not a news source and it has the shape of
SEO-injected content. And a fetch of `api.geckoterminal.com` returned a **page-injected
redirect to `sandwiched.me`**, which was not followed. Neither was used. The second one
matters operationally: `sources.py` polls that endpoint.

**O12 (2026-09-17, buyer side). Nobody publishes a 2026 bot-vs-human share of memecoin
volume on any chain.** The most-cited Solana figure — sandwich bots at 2.9% of daily DEX
volume — is Flipside via SolanaFloor and dated **March 2025**. For Base and Monad nothing
exists at all; for Ethereum and BNB there are absolute sniper-bot counts (ACM DOI
10.1145/3736763, June 2025) with **no denominator published**, so no percentage can be
derived. Marino's isBot definition is the one operational alternative and it is cheap:
**transactions routed through the pump.fun frontend versus direct on-chain program calls**,
readable from transaction logs. Same shape as O7 — an original measurement available
because we read a field almost nobody reads.

**O13 (2026-09-17, buyer side). §B's curve geometry settles C9's open unit question, and
it lands on the reading C9 did *not* endorse.** B1 establishes that FDV ∝ vSol² with
FDV_grad = 410.8 SOL at vSol = 115. Apply it to Kamat's 31.04 SOL **market cap**:

    vSol = 115 × sqrt(31.04 / 410.8) = 31.61   ⟹   real SOL deposited = 1.61

**1.61 SOL, not ~1.04.** That is exactly `CREATOR_PLAYBOOK.md` §2.4's *second* row
("mcap from constant-product FDV → ~1.6 SOL ≈ $160"), not the ~1.04 reading C9 calls
*"almost certainly right"* `[OPINION]`. The same geometry puts the no-deposit seed market
cap at **27.96 SOL, not 30.00**, which undercuts C9's supporting argument that the curve
seed *is* 30 because Kamat's Q2 is "exactly 30.00 SOL." **§B built the tool that closes C9
and did not notice; §C left open a question §B had already answered.** Both sides should
look at this before C9 is relaxed or acted on. The remaining ambiguity is whether Kamat's
"initial market cap" is computed on the same constant-product convention pump.fun displays;
if it is, the question is closed at 1.61 SOL.

**O14 (2026-09-17, both sides). The two halves of this file state the graduation FDV and
the 85 SOL figure with three different numbers, same day.**

| | buyer side (§B, `TRADING_PLAYBOOK.md`) | creator side (§C, `GLOSSARY.md`, `CREATOR_PLAYBOOK.md`) |
|---|---|---|
| SOL price | $99.64 (Kraken) | $99.79 (CoinGecko) |
| graduation FDV | **$40,932** | **$40,994** |
| 85 SOL | **$8,469** | **$8,482** |

Immaterial in magnitude and material in principle: `GLOSSARY.md` is the cross-linking
artifact and now carries a number §B's B4 contradicts. **This is B4 and C14 both being
right and neither being applied** — the underlying quantity is 410.8 SOL, and every USD
figure derived from it is a snapshot of a spot price that differs ~5% across venues on the
same day. **Quote the SOL figure; derive USD at the point of use with the source named.**
Kamat's social-link figures are consistent across both sides and need no reconciliation.

---

# Change log

**2026-09-17, tracker-scoping task.** §B extended with **B24**, the first `[REJECTED]`
entry in this file: front-running the copiers of a widely-copied wallet, rejected on the
arithmetic of signal scarcity (~56 buys/hour) rather than on principle, with the
measurement that would reopen it named. **Nothing superseded, nothing deleted, no B number
reused.** ⚠️ Filed, not acted on: **B22's "−$3,099, an average of −$40.78 per round trip"
does not re-derive.** Recomputing the same 76 measured v1 closes on the realizable basis
gives **−$3,542.08, mean −$46.61**; the win count 9/76 = 11.84% reproduces exactly and
`paper.summary()` has no dollar-P&L path at all, so the figure was computed by hand in
`REPORT_2026-09-15.md`. B22 was left as written rather than edited by this task.

**2026-09-17** — File created. §C seeded with C1–C20 from `CREATOR_PLAYBOOK.md` and
`TOKEN_MECHANICS.md`. §B reserved for the buyer task. §O opened with O1–O7.
Nothing superseded; nothing deleted.

**2026-09-17, buyer task.** §B seeded with **B1–B23** from `docs/TRADING_PLAYBOOK.md` and
`docs/CHAINS.md`; §O extended with **O8–O14**. **Nothing in §C was modified, and no `C`
number was reused.** The cross-reference note the creator task left inside the reserved §B
block was kept verbatim at the head of §B. *(Ordering note for a cold reader: the §C
corrections logged in the entry below this one were made by the creator task after this
entry was written. "Nothing in §C was modified" refers to the buyer task's edits only.)*

**Two items for the creator side, filed rather than acted on:** **O13** — §B's curve
geometry settles C9's open unit question at **1.61 SOL**, which is not the reading C9
endorses. **O14** — the two sides state the graduation FDV as $40,932 and $40,994 and the
85 SOL figure as $8,469 and $8,482, from two different SOL spot prices on the same day.

Three things in §B correct a premise that arrived with the brief rather than from the
repo, so per `/RULES.md` rule 4 they are named here:

1. **"Median position lost 60%, 3 wins in 69 closes" is ten days stale, and the second
   half is unsourced.** `GAPS.md` (2026-09-07) records **1** win at n=7, not 3; the "3 in
   69" is in no file in this repo. Current is **9/76 = 11.84%** measured, −$3,099 on $100
   clips (`REPORT_2026-09-15.md`).
2. **"Fomo has high fees" does not survive the arithmetic at $100, but he is still
   overpaying.** Fomo is fifth of eleven at $1.90 round trip, identical to Axiom's base
   tier and cheaper than GMGN, Trojan, Photon, Pump.fun Terminal and Moonshot, and it
   absorbs gas, priority fees and token rent. **Jupiter is $1.00 on tokens under 24h,
   so he pays ~90% more than he needs to** — real, and $0.90 a trade. See B21.
3. **Marino's breakeven kills one family of strategies, not all of them.** The paper
   explicitly leaves dynamic strategies open (B3). §B quotes the sentence rather than
   paraphrasing around it.

**Same-day adversarial verification pass, findings applied.** A check of §B and of the two
companion documents against their sources found errors that are corrected in place rather
than left for someone to hit later. The three that mattered:

1. **B13's loss decomposition was wrong and it flattered the strategy.** It assumed wins
   cap at 2× while using the *uncapped* P&L. Corrected: the average loser gives back
   **72%, not 60%**, and the required hit-rate improvement is **3.5×, not 3.2×**. `L* =
   $13.43` is unaffected.
2. **B5 claimed Marino's dominant predictor was computable from data we already fetch.**
   It is not — the variable is path-dependent and `TRENCHES_REFERENCE` §4.2 and `GAPS.md`
   both say we rarely observe the same token twice.
3. **B9 as first written contradicted B7's own worked examples.** Rewritten as a gradient
   rather than a prohibition.

Also corrected: B22 now states plainly that it sits below `/RULES.md` rule 2's threshold
and `GAPS.md` G1's n≥200 bar, and must not be cited as a finding; B21's overstatement of
the Fomo fee conclusion; B23's D1 figures now carry the recall number and the open
fluxbeam caveat from `TRENCHES_REFERENCE` §4.0.

One item was **closed** rather than corrected: `TRENCHES_REFERENCE` §2.5 lists Marino
§VI–VII as **[NOT RETRIEVABLE]**. §VI and §VII.A were retrieved in full on 2026-09-17 and
are quoted in B1, B3 and B5. **§VII.B onward is still unread** — the fetch truncated before
Figure 7, so the effect size of the dominant predictor remains open.

**2026-09-17, same day, after an adversarial verification pass.** Four corrections, all
made because a check found them rather than because anyone noticed later:

1. **C9 rewritten and C9a split out.** The original priced a self-buy at 31.04 SOL
   ($3,097) and concluded it could never pay. **31.04 SOL is a market cap, not a deposit**
   — the curve is seeded at 30 — so the real figure is nearer 1 SOL and the conclusion
   inverts. Per `/RULES.md` rule 4, the correction leads.
2. **C14 and O3 corrected.** They merged an 85 SOL *raise* with a ~$41k *FDV* across
   platforms with different curve geometry. Those are different quantities.
3. **O4 downgraded.** It called a third-party GitBook "direct external confirmation… from
   a launchpad's own description of its product." It is medium-confidence secondary
   material and §W3 still needs the funding-graph test.
4. **O5 reframed.** The 98.7% figure almost certainly collides with the Solidus Labs
   figure already in `TRENCHES_REFERENCE`. Marked do-not-use rather than merely unverified.

Also: O1's protocol-share arithmetic (0.950% → 0.050%, not "collapses to 0.050%" of a
mis-stated residual), the `/RULES.md` rule count (24, not 23), and the `/RULES.md` vs
`docs/RULES.md` citation ambiguity throughout.

---

*Running file. Append with a date. Never delete — supersede in place and name what was
replaced.*
