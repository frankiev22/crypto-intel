# The creator side: how a launch actually works, and what it pays

Written 2026-09-17. Research only. **Nothing was launched, deployed or bought. No collector
code was touched.**

Companion to `docs/TRENCHES_REFERENCE.md`, which covers the buyer's view and is assumed
read. Terms defined there are not redefined here; `docs/GLOSSARY.md` links across.
Rules distilled from this document live in `docs/RULES.md` as the `C` series.

SOL reference price used throughout: **$99.79** (CoinGecko via search, 2026-09-17).
Where a figure is SOL-denominated it is given in SOL first and USD second, because
`TRENCHES_REFERENCE` §W1 is the standing lesson that USD constants against SOL mechanisms
drift silently.

---

## 0. The one-paragraph version

Launching costs approximately nothing and pays a fraction of a percent of whatever volume
your token does. Volume is the entire variable and you do not control it. In the last
published distribution, **83.4% of pump.fun creators who earned anything at all earned
under $1,000**, and that is measured on a denominator that already excludes everyone who
earned zero. The legal exposure is not in collecting fees — that part is clean — it is in
buying your own coin through wallets you control and selling into the people who arrive
after you, which is what the wire fraud statute is for and which is trivially visible
on-chain forever. Distribution is the whole business and you have none.

---

# Part 1 — The mechanics

## 1.1 pump.fun

**Primary source: `pump.fun/docs/fees`, "Last Updated: 20 May 2026", retrieved 2026-09-17.**
This is the authoritative schedule and it is worth re-reading before any launch, because
the page states outright that the fees may change at any time without notice.

### What it costs

| Action | Cost |
|---|---|
| Create a coin | **0 SOL** (platform fee) |
| Graduation (curve → PumpSwap) | 0.015 SOL (~$1.50) |
| Solana base transaction fee | 0.000005 SOL (~$0.0005) per signature |
| Account rent to create the mint and metadata | **[UNVERIFIED]** — see below |

**On the total cost of a launch: I could not verify it and will not invent it.** The
platform fee is zero and the base network fee is negligible, but creating a mint account,
a metadata account and an associated token account each requires rent-exempt funding, and
I could not establish from pump.fun's documentation which of these the platform covers.
For scale, a plain SPL token account alone is 0.00203928 SOL (~$0.20) — see
`TOKEN_MECHANICS.md` §2.2. **Anywhere this document reasons about per-launch cost it says
so and marks the assumption.**

There is no presale, no team allocation and no liquidity to seed. That is the platform's
own framing and it is accurate: the curve is a formula, not a counterparty.

### What the creator earns

Two regimes, and the discontinuity between them is the most under-appreciated fact on the
page.

**On the bonding curve** — flat, regardless of anything:

| Creator | Protocol | LP | Total |
|---|---|---|---|
| **0.300%** | 0.950% | 0% | 1.250% |

**After graduation, on the PumpSwap canonical pool** — tiered by SOL-denominated market
cap. The top of the schedule:

| Market cap (SOL) | Creator fee | Total fee |
|---|---|---|
| 0 – 420 | 0.300% | 1.250% |
| **420 – 1,470** | **0.950%** | 1.200% |
| 1,470 – 2,460 | 0.900% | 1.150% |
| 2,460 – 3,440 | 0.850% | 1.100% |
| … decaying … | | |
| 98,240 and up | 0.050% | 0.300% |

**The discontinuity.** `TRENCHES_REFERENCE` §W1 computes graduation FDV as **410.8 SOL**.
The 0.950% band starts at **420 SOL**. So a token that has just graduated has to rise
**2.24%** before the creator's fee rate roughly **triples**.

    graduation FDV      410.8 SOL   ($40,994 at SOL $99.79)
    0.950% band starts  420.0 SOL   ($41,912)
    rise required       420/410.8 - 1 = 2.24%

This is arithmetic on two published numbers, not a claim about behaviour. But it means the
creator's economics are almost entirely decided in the first few percent of price movement
after graduation, and it means **the fee schedule is aggressively shaped to pay creators
for tokens in the $42k–$147k band and almost nothing for tokens that get large.** A token
that goes to a 100,000 SOL market cap pays its creator 0.050%, one nineteenth of the peak
rate. Whatever pump.fun is optimising for, it is not whales.

A USDC-denominated schedule exists — the fee page states *"As of May 21, 2026, token
creators can use USDC as the paired token."* Same shape, **materially different bands**:
the 0.950% plateau runs from 59,000 to 300,000 USDC, against $41,912–$146,691 for the SOL
schedule at today's price. Roughly a 40% difference at the lower bound, which is exactly
the silent-drift problem §W1 is about, appearing inside a single fee page.

### What the creator controls

Set at creation: name, symbol, image, description, and the social links — which surface as
`info.socials` and `info.websites` in the Dexscreener payload the collector already
fetches. **[UNVERIFIED]** whether pump.fun permits editing any of these after launch; I
found no statement either way and the fee page does not address metadata. Assume not, and
check before relying on it.

Mint and freeze authority are revoked automatically — `TRENCHES_REFERENCE` §1.1 measures
227 of 228 launchpad tokens with both revoked. LP is burned automatically at migration
(pump.fun Web Help Center, *Liquidity on PumpSwap*, via `TRENCHES_REFERENCE` §1.1), so the
classic LP-pull rug is structurally unavailable to you even if you wanted it.

Changeable after launch: as of a 2026-01-10 update, the creator fee can be **split across
up to 10 wallets**, assignable after launch through the app, and the recipient assignment
is also available to CTO admins. Unclaimed fees are reported as permanently claimable and
not seizable by admins. *(Source: multiple trade-press reports of the 2026-01-10
announcement, retrieved 2026-09-17. I could not find this on pump.fun's own fee page,
which documents rates but not the splitting feature. Treat the "10 wallets" number as
**medium confidence**.)*

## 1.2 Bags

**Primary source: Bags' own developer documentation, `docs.bags.fm`, retrieved
2026-09-17.** This is the best-documented launchpad of the five and the docs are public
and specific.

### Verifying the claim in the brief

The brief said: *"Bags reportedly gives 1% of every trade to the creator, splittable
across up to 100 wallets. Verify that's still true."*

**Verdict: substantially true, with one correction.**

- **1% of every trade** — true *pre-migration only*. Bags' Default config is a flat 2%
  trade fee split 50/50 protocol/creator, so **1% to the creator on the bonding curve**.
  Post-migration the Default config diverts 25% of the fee to compounding back into pool
  liquidity, leaving **0.75% to the creator**. So it is 1% then 0.75%, not 1% forever.
  Source: `docs.bags.fm/how-to-guides/customize-token-fees`.
- **Up to 100 wallets** — **confirmed from primary source.** The Create Fee Share Config
  endpoint reads: *"Create a fee sharing config with multiple fee claimers (up to 100)…
  All fees must be explicitly allocated using basis points. When there are more than 15
  fee claimers, lookup tables are required."* Fee sharing config is **required** for all
  Bags launches.
- **Correction worth having:** the claimer list is **mutable**. `bags config update`
  changes claimers and their bps, `bags config transfer-admin` hands the authority to
  another wallet, and the EVM docs note explicitly *"The claimer list is not immutable —
  the fee-share owner can call `setClaimers`."* If you are ever a *recipient* of someone
  else's fee split rather than the admin, your share can be revised to zero. That is a
  counterparty fact nobody advertises.

### The seven fee modes

Bags lets the creator pick the fee structure at launch, and it is locked once chosen.
This is real optionality that pump.fun does not offer.

Creator columns are the creator's cut only; "compounding" goes to the pool, not to you.

| Mode | Pre: total / creator | Post: total / creator | Compounds | Graduates at |
|---|---|---|---|---|
| **Default** | 2% / **1%** | 2% / **0.75%** | 25% | 85 SOL |
| Low Pre / High Post | 0.25% / 0.125% | 1% / 0.25% | 50% | 85 SOL |
| High Pre / Low Post | 1% / 0.5% | 0.25% / 0.0625% | 50% | 85 SOL |
| **High Flat** | **10% / 5%** | 10% / 2.5% | 50% | 85 SOL |
| 2% Flat, 85% supply locked | 2% / 1% | 2% / 0.75% | 25% | ~100 SOL |
| Default with 1K supply | 2% / 1% | 2% / 0.75% | 25% | 85 SOL |
| 2% Base, 96% supply locked | 2% / 1% | **2%→0.5%** total, creator = 37.5% of it (0.75% → 0.1875%) | 25% | 55 SOL |

Two notes on reading this table. **The mode names describe the total fee, not the
creator's cut** — "High Pre" means a 1% total fee pre-migration, which is *higher* than
Low Pre's 0.25% but pays the creator *less* than Default's 1%. And the last mode's
"2%→0.5%" is the **total** decaying with market cap; **post-migration** the creator takes
37.5% of whatever that total currently is (pre-migration that mode is a plain 50/50, so
1%). Bags' own docs give the decay as exponential, bottoming out *"once the market cap is
roughly 25x its value at graduation"* — quoted, not derived.

The High Flat mode charges traders 10% per trade. It exists, it is documented, and it is
the single clearest illustration that "creator fee" and "toll on the people buying your
coin" are the same number seen from two sides.

### Independent confirmation of the 85 SOL threshold

Bags' own docs list **85 SOL** as the graduation *raise* for five of seven modes. That is
a second, independent primary source for the same number `TRENCHES_REFERENCE` §W1 uses.

**Be careful what this does and does not corroborate.** 85 SOL is $8,482, not $40,000 —
the ~$40k figure is an **FDV**, and it only follows from 85 SOL via pump.fun's specific
curve geometry (85 SOL against a 2.069×10⁸-token pool). Bags' curve parameters are not
published, so Bags' 85 SOL does **not** independently imply a ~$40k FDV. Indeed Bags'
96%-locked mode graduates at 55 SOL with a stated FDV of ~4,978 SOL, which is the same
raise producing a wildly different FDV because less supply is in the pool.

So the honest statement of the convergence is two separate observations:

- **The raise** is 85 SOL on two independent platforms (pump.fun via Marino et al., Bags
  via its own docs).
- **The graduation market cap** is configured at **$40,000** outright by StonkFun (§1.5),
  which is a *third* platform arriving near the computed pump.fun FDV by a different route.

None of the three is near $69,000. That is enough to remove any remaining reason to doubt
§W1, and not enough to settle it — the query against the 86 witnessed curve→AMM
transitions is still what settles it.

## 1.3 LetsBonk / bonk.fun

Lower confidence — I could not retrieve first-party fee documentation.

Secondary reporting from unnamed comparison blogs (retrieved 2026-09-17) puts the creator
share at **0.5%–1.5%** varying with trading fees or market cap reached, and graduation at
**approximately 85 SOL** for SOL pairs or **$58,783** for USDC pairs. **[UNVERIFIED] —
all three figures, not just the fee range.** The 85 SOL is consistent with everything else
and the oddly precise $58,783 is exactly the kind of number that gets copied between blogs
without anyone checking it. If Frank gets serious about LetsBonk, the schedule needs to
come from the platform.

## 1.4 Believe

Lower confidence, and the numbers in circulation conflict.

Reporting says Believe raised the creator share to **70%** of its fee take as of June 1
(year not stated in the source), from 50%, with 0.9% retained by platform operations and
0.1% to "Scouts" who discover and promote tokens. Earlier reporting describes a flat
50/50 split and "creators earn 0.5% SOL on every transaction." **These do not reconcile
and I am not going to pretend they do.** Believe's distinguishing mechanic is launching by
replying to a post on X, which structurally requires an X account with reach — the exact
thing the brief says Frank does not have.

## 1.5 Moonshot

Lowest confidence of the five. The only figure I found is **1% of every trade routed to
the creator's wallet**, in a secondary listicle with no primary citation. Moonshot's
stated differentiator is mobile-first onboarding and native placement in its own app.
**Do not act on the 1% figure without checking it.**

## 1.6 StonkFun — the odd one out, and the one Frank asked about

Covered in full in `docs/TOKEN_MECHANICS.md`, because its interesting property is a token
mechanic rather than a fee schedule. The creator-relevant summary:

- Launches are **Standard** (no tax; creator gets 0.5% of the 1.25% total fee) or
  **Reward** (Token-2022 transfer tax of 1% or 3%, and **the creator gets nothing at all**).
- Graduation is configured at **$40,000** market cap, flagged "about to graduate" at
  $32,000.
- The **dev buy cap is 75% of supply**, executed as the pool's literal first trade inside
  the same atomic Jito bundle as the mint. See §3.2 — this is the thing to be careful about.

*Source: a third-party GitBook (`github.com/krisbuild/Stonkfun-gitbook-`, retrieved
2026-09-17) that reproduces StonkFun's API behaviour and on-chain program IDs in
verifiable detail, cross-checked against `stonkfun.xyz/rewards`. It is not StonkFun's own
documentation and should be treated as **medium confidence** on anything not independently
checkable.*

---

# Part 2 — What it actually pays

## 2.1 The arithmetic, which is the easy part

Creator revenue is `lifetime volume × fee rate`. That is the whole model. On pump.fun:

| Lifetime volume | Never graduates (0.300%) | Graduated, trading in the 0.950% band |
|---:|---:|---:|
| $1,000 | $3 | — |
| $5,000 | $15 | — |
| $10,000 | $30 | $95 |
| **$50,000** | **$150** | **$475** |
| $100,000 | $300 | $950 |
| $500,000 | $1,500 | $4,750 |
| $1,000,000 | $3,000 | $9,500 |

**The right-hand column is an over-estimate.** It applies 0.950% to the whole lifetime
volume, but the first 85 SOL of any token's life is curve volume at 0.300%, and the 0.950%
band does not start until 2.24% above graduation. Read it as a ceiling. The case analysis
immediately below does it properly.

**The brief's specific question — a coin that does $50,000 of lifetime volume:**

*Case A, never graduates.* All $50,000 on the curve at 0.300% = **$150 gross**, less
launch cost (unverified, see §1.1) and a few cents to claim. **≈ $150**, before income tax.

*Case B, graduates but stays under 420 SOL market cap.* The rate is still 0.300%, so this
is Case A minus the 0.015 SOL graduation fee. **≈ $148.50.** Graduating, by itself, is
worth nothing.

*Case C, graduates and clears the 420 SOL boundary early.* The curve absorbs 85 SOL ≈
$8,482 to complete, then $41,518 trades post-graduation at 0.950%:

    curve      $8,482  x 0.300%  =  $25.45
    post-grad  $41,518 x 0.950%  = $394.42
    less graduation fee 0.015 SOL = -$1.50
    ------------------------------------------
    net                            ~$418

Case C is an **upper bound** — it assumes the token clears the 2.24% gap to the 0.950%
band immediately and never falls back. Real tokens oscillate across that boundary and the
true figure sits somewhere between C and B.

**So a $50k-volume coin pays its creator somewhere between about $148 and $418, and where
it lands in that range is decided almost entirely by whether it holds above a 420 SOL
market cap.** Note what that means: **graduating is worth nothing by itself.** The thing
that pays is clearing a threshold 2.24% above it.

## 2.2 The distribution, which is the part that matters

**The only published, on-chain-derived distribution of pump.fun creator earnings I could
find:** SolanaFloor, *"Pump.fun's Creator Revenue Sharing: Reality vs. Hype"*,
published **2025-06-04**, Flipside data, n = 3,566 creators, window 2025-05-12 to
2025-06-04. **Note the date: this is over a year stale** and the reason it is still the
best available is that nobody has repeated the analysis under the current fee regime.

| Earned | Share of creators |
|---|---|
| under $100 | **34.9%** |
| $100 – $1,000 | 48.5% |
| **under $1,000 (cumulative)** | **83.4%** |
| $1,000 – $5,000 | 13.7% |
| $5,000 – $10,000 | 1.8% |
| over $10,000 | ~1.1% |

Top earner: $104,000 from three coins. Tenth-highest: ~$25,000.

**Two corrections have to travel with that table or it will mislead.**

**(1) It is measured under a different fee regime.** The same SolanaFloor article describes
that regime: pump.fun had been charging 0.25% on PumpSwap trades (0.2% to LPs, 0.05% to
protocol) and **added a further 0.05% on top as the creator's share**, taking the total to
0.3%. So the creator rate in the measurement window is **0.05%**. Today's published
schedule pays 0.300% on the curve and up to 0.950% post-graduation — **6× to 19× more**.
The *levels* are stale. The *shape* — a power law with a long, nearly worthless tail — is
the durable part, and the shape is what you are buying into.

**(2) The denominator is wrong, in the direction that flatters.** Standing rule 3 in
`/RULES.md`: *use the full denominator.* Those 3,566 are creators who **claimed something**.
Every launch that earned literally zero is outside the count. Kamat's n=832,941 over a
May–June 2026 window works out to on the order of **13,700 pump.fun launches per day**
*(derived: 832,941 ÷ ~61 days. **The window length is my inference, not Kamat's
statement** — treat the figure as order-of-magnitude, and carry that caveat wherever it is
requoted)*. Against a launch population of that size, 3,566 earning creators over 23 days
is a rounding error. **The unconditional per-launch earnings distribution is far worse
than the chart shows, and I cannot compute how much worse because the unique-creator
count for the window is not published.**

## 2.3 The two strategies, both visible in the data

Among the top 100 earners in that same analysis:

- **43% launched fewer than five tokens**, and 26 of them launched exactly one.
- **19% launched over 1,000 tokens each.**
- Mean tokens launched: 1,626. **Median: 10.**

That gap between mean and median is the whole finding. There are two ways to be a top-100
creator and they have nothing in common. One is to hit once. The other is industrial
volume — launch thousands, collect 0.300% of whatever trickles through, treat each launch
as a cheap lottery ticket.

**Only the second is a strategy in the sense of being repeatable.** The first is an
outcome. Someone who launched one token and made $104,000 did not have a method; they had
a token that worked. The honest framing for a nobody with no audience is the industrial
one, and it lives or dies on a cost comparison I cannot currently make: **per-launch cost
is unverified (§1.1)** and expected revenue per dud is small — if a dud does $2,000 of
curve volume, 0.300% is $6. Whether that is a margin or a loss depends entirely on the
account-rent figure, which is the first thing to establish before anyone writes a line of
launcher code. Either way it requires automation to matter. **It is a software business,
not a creative one.**

## 2.4 The self-buy question, and a unit error worth not making

`TRENCHES_REFERENCE` §1.2 reports Kamat's finding that **initial market cap** above
31.04 SOL — read as "the creator bought their own launch" — raises graduation from
0.0848% (Q1) to **0.6339%**, Cox HR 4.506. n=832,941, p < 10⁻³⁰⁰. The obvious creator
inference is "self-buy to improve my odds."

**⚠️ Read the unit before doing any arithmetic. 31.04 SOL is a market cap, not a deposit.**

I got this wrong on the first pass and it inverted the conclusion, so it is worth stating
the trap explicitly. The pump.fun curve is *seeded* at 30 virtual SOL
(`TRENCHES_REFERENCE` §1.1), and Kamat's Q2 is "exactly 30.00 SOL (platform default)" —
i.e. **a launch with no dev buy already reads 30.00**. Crossing into Q4 therefore requires
moving market cap by **1.04 SOL, not depositing 31.04 SOL**.

**How much SOL that actually is depends on Kamat's market-cap convention, which I could
not pin down**, and the two readings differ by ~30×:

| Reading | Deposit to cross | Breakeven E[fees] | Post-grad volume needed at 0.950% |
|---|---:|---:|---:|
| **mcap ≈ vSol** (so 30.00 = the seed exactly) | **~1.04 SOL ≈ $104** | $18,900 | **~$2.0M** |
| mcap from constant-product FDV | ~1.6 SOL ≈ $160 | $29,100 | ~$3.1M |
| (the wrong reading — full 31.04 deposited) | 31.04 SOL ≈ $3,097 | $564,000 | ~$59.4M |

    breakeven volume = deposit / (marginal P(grad) x creator fee rate)
                     = deposit / (0.005491 x 0.0095)

`marginal P(grad)` uses Q4 0.6339% against **Q1 0.0848%** — the *highest* non-self-buy
quartile, which is the conservative comparison because a higher baseline means a smaller
lift and a worse breakeven. (The quartile literally adjacent to Q4 is Q3 at 0.0256%, which
would flatter the case.) Against the pooled Q1–Q3 rate of 0.053% the lift is 0.581 pp and
every breakeven above falls by ~6%.

Every breakeven in that table is also a **floor**, because it applies the 0.950% rate to
all post-graduation volume — and §1.1 shows the 0.950% band only starts 2.24% above
graduation. A token that never clears that boundary pays 0.300% and the volume required
triples.

**The first reading is almost certainly correct**, because it is the only one under which
"exactly 30.00 SOL" is the no-dev-buy default, and because 25% of all launches doing a
~1 SOL dev buy is plausible while 25% doing a $3,100 dev buy is not. `[OPINION]`. There is
a related loose end: `TRENCHES_REFERENCE` §1.2's quartile table gives Q1's range as
[1.39, 30.00) — *below* the seed — which no simple convention explains and which the
reference does not comment on.

**So the honest conclusion is not the one I first wrote.** A dev buy on the order of
1 SOL is cheap enough that it plausibly clears its own breakeven on creator fees alone,
needing roughly $2M of post-graduation volume rather than $59M. **That changes the
recommendation from "never" to "it depends on a parameter nobody has measured"** — see
Part 5, where the distribution of post-graduation volume is the largest hole in this
document.

Three things that survive regardless of which reading is right:

1. **Kamat's effect is associational, not causal.** Self-buying may be a proxy for
   creators who also choose better names, write longer descriptions, set up three socials
   and have an audience. If so, buying the proxy buys you nothing. Kamat is explicit that
   these are *"predictive and useful for filter calibration, not actionable trading
   signals without further out-of-sample validation."* **A creator reading a predictor as
   an intervention is making the classic error.**
2. **The position is not free even when it is small.** In the 99.37% of cases where the
   token does not graduate it is worth approximately nothing, and `TRENCHES_REFERENCE`
   §2.2 records curve-first tokens returning ≥2× at **0.01%** — two wins in 14,802.
3. **Selling it into buyers who arrived after you is the conduct Part 3 is about**, and
   that is true at 1 SOL and at 31 SOL alike. Size does not change the character of the
   act, only the restitution figure.

**Resolve the unit before acting on this.** It is settleable from the pump.fun curve
parameters already in `TRENCHES_REFERENCE` §1.1 plus Kamat's stated mcap definition, and
it is the difference between a cheap edge and a bad idea.

## 2.5 The socials finding, read correctly

`TRENCHES_REFERENCE` §2.2 records the largest published launch-time predictors:

| Metadata at creation | Graduation rate | Lift |
|---|---|---|
| All three (X + site + Telegram) | 1.919% vs 0.110% | **17.4×** |
| Telegram link | 1.485% vs 0.166% | 8.94× |
| Website link | 0.264% vs 0.158% | 1.19× HR |
| X link | 0.227% vs 0.149% | 1.31× HR |

**The measured variable is the presence of a link in launch metadata. It is not audience
size.** Frank can set all three links, today, with zero followers, for free. Whether he
gets any of the 17.4× is a completely different question, and Kamat declines to claim
causality, offering three readings: effort proxy, discoverability, selection.

My read, stated as opinion: **most of that 17.4× is the effort/selection channel.** A
creator who sets up three working socials is a different creator from one who mashes the
default button, in ways the link itself does not capture. So:

**Set all three links because they cost nothing and cannot hurt. Do not build a plan on
getting 17.4×.** That is rule C7.

---

# Part 3 — The legal line

**This section is not optional and it is not hedging.** Frank has a real name, a real LLC,
a day job at a licensed brokerage, and real money on-chain. On-chain activity is
permanent, public, and trivially reconstructable years later by anyone with a block
explorer — including a prosecutor who starts from a victim complaint and works backward.

*I am not a lawyer and this is not legal advice. Before launching anything under
Velox Enterprises LLC, this belongs in front of an actual securities/white-collar
attorney and a CPA. What follows is a map of where the enforcement has actually landed.*

## 3.1 What is clean

**Collecting creator fees on a token you launched and disclosed.** You did not promise
anything, you did not sell into anyone, and the fee is a documented, public property of
the platform that every buyer can read before trading. There is no misrepresentation and
no undisclosed position. This is the business.

Note that "creator fee" and "the token holders' loss" are not the same pot — the fee comes
off the trade, from the platform's fee split, not out of a reserve you control. That
structural separation is exactly why it is defensible.

## 3.2 What produces charges

**⛔ Buying your own coin through wallets that do not obviously belong to you, and selling
into the people who arrive afterward.**

That single sentence covers bundling, insider allocation, sock-puppet accumulation and the
dev dump. Every variant has the same two elements: an undisclosed position taken before
the public, and a sale into demand you created or benefited from.

Why this is the line and not something softer:

**Meme coins being "not securities" does not help you.** The SEC's Division of Corporation
Finance staff statement of **2025-02-27** says the offer and sale of meme coins does not
involve securities. It also says, in the same document, that *fraudulent conduct involving
meme coins remains subject to other federal and state laws*, that the statement does not
cover assets labelled "meme coin" to evade registration, and — per the SEC's own
publication — that staff statements are not binding law or statements of the Commission.
Commissioner Crenshaw published a dissenting response the same week. **Read it as
narrowing one theory of liability, not as a shield.**

**Prosecutors have already routed around the securities question.** In the District of
Massachusetts case announced 2024-10-09 ("Operation Token Mirrors"), the DOJ charged 14
individuals and four entities — Gotbit, ZM Quant, CLS Global, MyTrade — with market
manipulation and wash trading of crypto tokens. The FBI created its own token, NexFundAI,
as the sting vehicle. Over $25 million was seized. **CLS Global pleaded guilty in January
2025 to conspiracy to commit market manipulation and wire fraud, and to wire fraud.**
A further ten foreign nationals across four firms were charged in the Northern District of
California in March 2026 on the same theory. *(Sources: DOJ/USAO-MA press releases,
SEC press release 2024-166, TRM Labs, Decrypt — all retrieved 2026-09-17.)*

The pattern to internalise: **they charged wire fraud.** No Howey analysis required, no
argument about whether the token is a security. Wire fraud needs a scheme to defraud and
an interstate wire. A blockchain transaction is an interstate wire.

**The evidence is already written and you cannot unwrite it.** Defence-side and
analytics-firm write-ups of these cases describe them as built from wallet tracing,
exchange KYC records, Discord and Telegram messages, developer logs and IP records
*(TRM Labs on Operation Token Mirrors; white-collar defence firm commentary — secondary,
retrieved 2026-09-17, and consistent across sources but **not** a primary DOJ statement)*.
The specific on-chain tells are the ones
`TRENCHES_REFERENCE` §1.2 already catalogues from the detection side:

| Tell | Why it survives |
|---|---|
| Mint and buys in the same slot | atomic bundle; the timestamps are identical and permanent |
| Buyer wallets funded from a common ancestor | **staggering cannot hide this** — the SOL has to come from somewhere |
| Near-identical buy sizes across distinct wallets | statistical, and the sample is the whole chain |
| Those wallets selling in a narrow window | the dump is the actus reus and it is timestamped |

Note the asymmetry that should settle this: **detecting this is hard and expensive in real
time, which is why the repo has not built it. Reconstructing it after the fact, once
someone knows which token to look at, is easy.** The trenches' inability to catch it live
is not protection. It is a latency problem, not an anonymity one.

**Wash trading is the same conduct wearing a different hat.** `TRENCHES_REFERENCE` §1.3
documents the Bitquery case: 200 bot wallets seeded with exactly 0.5 SOL each in 52
seconds; token OpenLie showing $532,461 of volume across 40,523 trades from 233 wallets.
Manufactured volume to buy Dexscreener trending placement is the conduct CLS Global
pleaded guilty to. It is not a grey area and it is not a growth hack.

## 3.3 The specific traps a legitimate creator can still walk into

These are the ones that catch people who are not trying to defraud anybody.

1. **Platform-sanctioned dev buys.** StonkFun's documented dev buy executes *"as the
   pool's literal first trade, so there's no window for anyone else to trade ahead of it,"*
   with a cap of **75% of supply**. pump.fun's self-buy raises graduation odds and Kamat
   measured it. Both are legitimate, disclosed platform features. **The platform offering
   a feature is not a legal opinion.** What turns a disclosed dev buy into a problem is
   selling it into arrivals while continuing to promote, and doing so from wallets that do
   not read as yours.
2. **Fee-share wallets that look like buyers.** Bags splits fees across up to 100
   claimers, pump.fun across 10. Those are *fee* wallets. If the same wallets also
   *trade* the token, the on-chain picture is indistinguishable from a bundle. Keep fee
   recipients and trading wallets strictly disjoint.
3. **Promoting a token you hold without saying so.** `[OPINION]` on the framing: the
   disclosure failure is the fraud element, not the holding. The Hawk Tuah matter is the
   commonly cited live example, but **as far as I could determine it has not resolved into
   any charge**, and it should not be cited as if it had.
4. **Ticker squatting and impersonation.** `TRENCHES_REFERENCE` §1.3 measures that 57.9%
   of tokens share a ticker with another and FLORK alone has 25 contracts. Launching
   "FLORK #26" is not fraud. Launching a token that impersonates an existing project's
   name, logo and socials so buyers think they are buying the original is a
   misrepresentation. pump.fun's own footer links a *Trademark guidelines* page and a
   *DMCA policy* (observed on `pump.fun/docs/fees`, 2026-09-17); I did not read either,
   so their contents are **[UNVERIFIED]** — only their existence is observed.
5. **Tax.** Airdrops received are ordinary income at fair market value on dominion and
   control under **Rev. Rul. 2019-24**. The treatment of *creator fee* income is not
   addressed by that ruling and I am not going to state a rule for it. **[UNVERIFIED] —
   get a CPA.** What is not in doubt is the volume: at industrial launch rates this is
   thousands of separate taxable events a year, attached to a real LLC.

## 3.4 The rule

**If a reconstruction of the token's full on-chain history, published by a hostile party,
would embarrass you — do not do it.** That is not a moral test. It is a prediction about
what discovery looks like, and it has the useful property that you can apply it in
advance, alone, in about ten seconds.

---

# Part 4 — Distribution, which is the whole business and which Frank does not have

## 4.1 The uncomfortable statement of the problem

Everything above is mechanics. Mechanics are the easy 10%. The creator's fee is a
percentage of volume and **nothing a creator does at deploy time creates volume.** The
platform does not distribute for you. At roughly 13,700 launches a day (§2.2 — derived,
order-of-magnitude) a new token's window in any "newest first" listing is measured in
seconds. *(That pump.fun's own new-token feed is strictly chronological is my assumption
and is **[UNVERIFIED]** — I did not confirm its ordering. The conclusion survives either
way: whatever the ordering, 13,700 daily competitors is the denominator.)*

So the honest answer to "what does a launch with zero followers reach" is:

- **Sniper bots**, which buy indiscriminately and are not demand.
- **Feed scrapers and copy-trade bots**, same.
- **Nobody else, by default.** Not as a pessimistic framing — as a mechanical consequence
  of ~13,700 daily competitors against a listing nobody reads past the top of.

Kamat's base rate is the measurement of this: **0.198%** [0.189, 0.208] on n=832,941.
Launches with no social links graduate at **0.110%**. That is roughly **one in 900**.

## 4.2 What is documented vs. what is folklore

The brief asked for this split explicitly. Here it is.

**Documented, with an n behind it:**

| Practice | Effect | n | Source |
|---|---|---|---|
| Set all three social links at creation | 1.919% vs 0.110% graduation | 832,941 | Kamat 2026 |
| Set a Telegram link | 1.485% vs 0.166%, HR 5.402 | 832,941 | Kamat 2026 |
| Write a longer description | HR 1.054 [1.034, 1.076] | 832,941 | Kamat 2026 |
| Initial market cap above 31.04 SOL — **a market cap, not a deposit; see §2.4** | 0.634% vs 0.053% | 832,941 | Kamat 2026 |
| Leave initial mcap at the 30.00 SOL default | **0.0011%** — 1 in 91,247 | 91,247 | Kamat 2026 |

Note the last row. **Accepting the platform default is the single most measurably fatal
thing a creator can do**, and it is free to avoid. It is also almost certainly a
selection effect rather than a mechanism — the default is what you get when you do not
care — which is precisely why it works as a filter and does not work as an intervention.
Changing the number without changing the caring changes nothing.

**Folklore — asserted constantly, measured nowhere I could find:**

- That ticker choice, name cleverness or wordplay affects outcomes. No measurement exists.
  Kamat measured description *length*, not quality.
- That art quality affects outcomes. No measurement.
- That launch timing (hour of day, market session) affects outcomes. No measurement, and
  `TRENCHES_REFERENCE` §2.3 records that the best narrative in the repo's own record — the
  2026-08-27 Chinese-language wave — would have been invisible to an English feed anyway.
- That "seeding a community" pre-launch works. No measurement. Note that the honest
  version of this is just "have an audience," which returns to the problem.
- That riding an existing narrative works. `clusters.py` measured the launch-side version:
  **clusters of 10+ tokens produced zero winners across 418 tokens.** Being the fortieth
  token in a narrative is measurably worthless. Whether being the *first* differs is
  **untested and answerable from data already on disk** — that is
  `TRENCHES_REFERENCE` §2.3, third bullet (cluster ordering), and the adjacent and
  distinct §4.3 item 7 (ticker recency ordering). Different objects, both free.
- That 3–5 bot wallets hold 40–60% of supply by the time organic buyers see a token.
  Widely repeated, not peer-reviewed, sourced to a single blog post.

**The ratio of folklore to measurement in creator advice is worse than on the buyer side,
and the buyer side is already bad.** Nobody publishes negative results about launches that
did nothing, because nobody was watching them.

## 4.3 What actually follows from this

Not "build an audience first" — that is true, useless, and does not fit alongside a day
job at BHS and five other brands.

What follows is narrower and more honest:

**The only creator strategy that does not require distribution is the industrial one,
and it is a software problem, not a marketing one.** Launch at volume, set all three
social links every time, don't accept the 30.00 SOL default, don't price a dev buy until
the §2.4 unit question is settled, never sell one into arrivals, and collect 0.300% of
whatever curve volume arrives. The economics are thin and
legal, and **whether they are positive at all turns on the unverified per-launch cost in
§1.1** — establish that number before building anything. Even if it clears, this is not
obviously worth Frank's time versus anything else on his list, and I would say so plainly
if asked.

**The only creator strategy that pays real money requires distribution**, and Frank's
existing distribution is Unlisted NYC — a NYC real-estate audience. That is a *specific*
audience, not a crypto one, and the honest question is not "how do I launch a memecoin"
but "is there a token that this particular audience would want, and would launching it
damage the BHS relationship." Those are strategy questions, not mechanics questions, and
this document cannot answer them.

**What I would not do:** treat the creator side as a way to monetise the research already
in this repo. The repo's one proven asset is a fraud detector with published precision
(`FRAUD_DETECTION.md`: 100% [85.7, 100] at 46.94% recall — and carrying
`TRENCHES_REFERENCE` §4.0's open caveat that "fraud detector" and "fluxbeam detector" are
not yet distinguished). Detection and launching are adjacent in topic and opposite in
reputation. Doing both makes the first one unpublishable.

---

# Part 5 — What I could not verify

Stated so nobody later mistakes silence for evidence.

- **[UNVERIFIED]** LetsBonk's creator fee range (0.5%–1.5%). Secondary sources only.
- **[UNVERIFIED]** Believe's current creator share. Two sources conflict irreconcilably.
- **[UNVERIFIED]** Moonshot's creator fee (1%). Single low-quality secondary source.
- **[MEDIUM CONFIDENCE]** pump.fun's 10-wallet fee split. Trade press only; not on
  pump.fun's own fee page.
- **[UNVERIFIED — and probably a source confusion]** The claim, seen in a search summary
  attributing it to MELT, that **98.7% of pump.fun token-creation transactions also
  contain a buy from the developer.** I did not retrieve this from the paper.
  **Note that `TRENCHES_REFERENCE` §1.3 and §3.2 attribute an identical 98.7% to Solidus
  Labs for a completely different claim** — pump.fun tokens showing pump-and-dump or rug
  characteristics. The exact numeric coincidence is strong evidence that a search summary
  re-attributed the Solidus figure to MELT. **Do not use this number until someone opens
  the paper.** If some version of it is right it matters a lot, because it would mean
  "dev bought" carries almost no information and only "dev bought *a lot*" does — which
  is the same unit question as §2.4. MELT is open at `github.com/git-disl/MELT`.
- **[NOT MEASURED ANYWHERE]** The distribution of post-graduation lifetime volume. This is
  the single parameter that decides whether creator fees are worth anything, and I found
  no published measurement of it. Every EV calculation in Part 2 is parameterised on it.
  **It is computable from the repo's own witnessed graduations** and would be the highest-
  value thing to measure before doing anything on the creator side.

---

# Sources

Retrieval date 2026-09-17 for all.

**Primary — platform documentation**

- pump.fun, *Fees* (`pump.fun/docs/fees`), last updated 2026-05-20. Full SOL and USDC fee
  schedules, create and graduation costs.
- Bags, *Customize Token Fees* (`docs.bags.fm/how-to-guides/customize-token-fees.md`).
  Seven fee modes, splits, graduation thresholds, compounding.
- Bags, *Create a Fee Share Config* and *Create Fee Share Admin Update Config*
  (`docs.bags.fm/llms.txt` index). Up to 100 claimers, bps allocation, mutability.
- Bags, *Claim Creator Fees — Robinhood Chain* (`docs.bags.fm/robinhood/claim-fees.md`).
  2% fee, 1% creator half, `setClaimers` mutability.
- Bags, *Launch an Index Token* (`docs.bags.fm/robinhood/index-tokens.md`). See
  `TOKEN_MECHANICS.md`.
- StonkFun, *Rewards* (`stonkfun.xyz/rewards`).

**Primary — legal**

- SEC Division of Corporation Finance, *Staff Statement on Meme Coins*, 2025-02-27.
- SEC Commissioner Caroline Crenshaw, *Response to Staff Statement on Meme Coins*,
  2025-02-27.
- SEC press release 2024-166, *SEC Charges Three So-Called Market Makers and Nine
  Individuals…*
- USAO-MA press releases on Operation Token Mirrors and the CLS Global plea.
- IRS Rev. Rul. 2019-24 (airdrops as ordinary income on dominion and control).

**Measurement**

- Kamat, A.U. (2026), arXiv:2607.02823. n=832,941. Cited via `TRENCHES_REFERENCE`.
- SolanaFloor / Ario, *Pump.fun's Creator Revenue Sharing: Reality vs. Hype*, published
  2025-06-04, Flipside data, n=3,566. Also the source for the 0.25%→0.3% fee change that
  established the 0.05% creator share in the measurement window.
- CoinGecko, SOL spot $99.79, 2026-09-17.

**Secondary — legal commentary, used only where labelled**

- TRM Labs on Operation Token Mirrors; white-collar defence commentary on how digital
  asset fraud cases are assembled. Neither is a primary DOJ statement.

**Medium / low confidence**

- `github.com/krisbuild/Stonkfun-gitbook-` — third-party StonkFun documentation.
- AirdropAlert, *StonkFun Explained*, 2026-09-08.
- Trade press on the 2026-01-10 pump.fun fee-split announcement.
- Comparison blogs for LetsBonk, Believe and Moonshot — **all flagged unverified above.**

**Ours, cited not restated**

`docs/TRENCHES_REFERENCE.md`, `/RULES.md` (the standing rules — **not** `docs/RULES.md`),
`FRAUD_DETECTION.md`, `VENUE.md`, `GRADUATION.md`, `FEASIBILITY.md`, `X_API.md`.

---

*Research document. Nothing was launched, deployed, bought or sold. No collector code was
read or modified. Every fee schedule above is from the platform's own documentation or is
explicitly labelled unverified.*
