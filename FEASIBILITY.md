# Could the fraud check be a product? A feasibility read

2026-09-07. Not a pitch. **The answer is "not yet, and here is the gate."**

## ⚠️ Correction, first: there ARE redistribution terms

It was established earlier that Dexscreener publishes a rate limit but no
redistribution terms, and that this could not be inferred. **That was wrong —
the terms exist**, at `docs.dexscreener.com/api/api-terms-and-conditions`, and
they are restrictive. Quoting the actual wording:

> "The API Services may be used for both non-commercial and commercial
> purposes, subject to the limitations set forth in this Agreement."

> "You are prohibited from assigning, selling, marketing, licensing, or
> otherwise dealing in any way with the API Services for any unauthorized
> purpose, including but not limited to making the API Services, or any portion
> thereof, available for third parties."

> "Users cannot utilize the API Services to construct, enhance, or market a
> product or service whose primary purpose is to compete directly with DEX
> Screener's product or the API Services itself."

No attribution requirement and no caching or storage clause appear.

**What this means, and the honest limit of my reading:**

- Commercial use is *explicitly permitted*. That is the good news and it is
  clearly stated.
- **Redistributing the data is prohibited.** Showing a customer `liq`, `fdv`,
  prices or reserves pulled from their API is "making a portion thereof
  available for third parties" on any plain reading.
- A *verdict* — "this pool cannot be exited at its reported size" — is a
  derived conclusion, not their data. That is probably outside the redistribution
  clause. **Probably is doing a lot of work in that sentence, and it is a
  lawyer's call, not mine.** The word "enhance" in the competing-product clause
  is broad enough to be argued either way.
- The rate limit on the reference page reads **60 requests/minute**, which is
  lower than the 300/min this repo has been pacing the pairs endpoint against.
  That discrepancy needs resolving before any volume claim is made.

**This is the gate, and it is a legal gate rather than a technical one.** Nothing
should be sold to anyone until someone qualified reads those three clauses
against the specific thing being sold.

## What is actually provable today

One detector, out of sample, on a labelled set built from reserves:

| | flagged | precision | recall |
|---|---:|---|---|
| **D1 — silence** | 23 | **100% [85.7, 100]** | 45.1% [32.3, 58.6] |
| D2 — magnitude+inactivity | 14 | 100% [78.5, 100] | 27.5% [17.1, 40.9] |
| union | 37 | 100% [90.6, 100] | 72.6% [59.1, 82.9] |

**Only D1 is validated.** D2 was derived on 2026-09-07 from the very rows it is
scored against, so its interval is in-sample and means nothing yet. The union
row inherits that contamination and is reported for shape, not for sale.

The defensible sentence today is: *"one rule, derived before the data existed,
flags one-sided pools with a precision floor of 85.7% at 95% confidence and
admitted recall of 45%, n=23."* Nothing more.

## What it would take to be usable by someone other than Frank

1. **n.** The precision floor is 85.7% *because* n=23. It moves on its own —
   every additional true positive tightens it, at zero cost but time. At n≈100
   with no false positives the floor reaches roughly 96%. **This is the only
   work item that requires no decisions.**
2. **D2 validated forward.** It cannot be quoted until it has been scored on
   rows observed after 2026-09-07.
3. **Recall, honestly bounded.** 45% for D1, 72.6% for the union. A buyer will
   ask what the other half looks like, and "we know: it is a different
   mechanism, here it is" is a much stronger answer than a higher blended
   number.
4. **A second ground truth.** Everything rests on `exit_depth_usd` derived from
   Dexscreener's own reserve split. If that field is ever wrong, the labels are
   wrong and the detector is unfalsifiable. An independent read of pool reserves
   from chain would fix this and is the single biggest structural weakness.
5. **The legal gate above.**

## Ongoing cost

Today, at one pass an hour, everything runs on free tiers:

| | per pass | per month | tier |
|---|---:|---:|---|
| Dexscreener enrichment + outcomes | ~292 | ~210,000 | free |
| GeckoTerminal discovery | 5 | ~3,600 | free, and already saturated |
| Solana RPC (authorities) | ~3 | ~2,200 | free public |
| **cash cost** | | **$0** | |

**What is already at its limit:** GeckoTerminal sustains under 10 successful
calls a minute, measured, and the fallback path already fails about half its
attempts. That is the binding constraint on everything, and it is not solved by
money at this scale — it is solved by not needing the fallback.

Holder concentration, the one causal feature still unmeasured, needs a free
Helius key: **1M credits/month against our ~114k requirement, $0**. See
`ONCHAIN_COST.md`.

## What breaks at volume

- **The 60/min figure**, if it is the real pairs limit rather than 300. At 60/min
  a single pass of ~292 calls takes five minutes of pure requests. Multi-tenant
  serving would need a paid tier, and that changes the ToS conversation
  materially.
- **Coverage, not throughput.** Discovery is a ~5-minute window polled hourly,
  so we see roughly 4–9% of launches. A customer asking "is *this* token fake"
  is a different system from one that samples the stream — it needs on-demand
  lookup, which is one call, but also needs the answer to be right for a token
  we have never seen. **D1 and D2 both work on a single observation with no
  history, which is the one piece of good news here.**
- **Ground-truth staleness.** Dexscreener stops indexing pairs between 6h and
  24h (resolution: 1h 99.9%, 6h 99.9%, 24h 36.8%, 168h 5.2%). Labels can only
  ever be built on fresh pairs. That is survivable — fraud is detectable at
  observation time — but it caps how far back any audit can reach.
- **Adversarial drift.** The template pools share `depth/liq = 0.00796` to five
  decimal places, which says one operator running one script. The moment that
  script changes, D1's recall drops and nobody is notified. **A detector with no
  drift monitor is a detector with an unknown expiry date.**

## The sequence, which is the constraint

Prove it → publish the record → then charge. **We are one day into a record.**

The one-day-old record currently contains: 20 paper entries, 0 closed, and one
detector at n=23. The honest status is *"we have the first provable thing and a
ledger with no completed trades in it."*

The thing that would change this fastest is not a feature. It is four weeks of
the same passes running, with the interval reported daily and nothing tuned.

## What I would not claim to anyone

That a 100% precision figure means the detector never errs — n=23, and the
floor is 85.7%.

That recall of 45% is a limitation to be worked around. **It is the credibility.**
A vendor quoting one number without the other is telling you which one is bad.

That any of this predicts price. It does not, it is not intended to, and four
attempts to do so have failed.
