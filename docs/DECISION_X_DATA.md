# Decision: buy X data before 2026-09-21, or not?

**2026-09-17. Nothing has been signed up for or bought. Frank's call alone.**

---

## Recommendation: **do not buy before the 21st. The deadline does not bind.**

**The data is identical either side of the change. Only the price moves.**
Historical X posts do not expire — the same posts are there on the 25th as on
the 20th. Nothing is lost by waiting except money, and **the most that can be
saved by rushing is about $60 on the sample we would actually run.**

Against that: **we are not ready to buy.** `PRELAUNCH_SIGNAL.md` §6.3 is an
open validity question that could change what we need to purchase, and the
socials capture that feeds the design shipped **today** — so the forward sample
has four days of data in it, not four months. Buying now means buying for a
design that may still change.

**Waiting costs ~$60 and removes the risk of buying the wrong thing.**

---

## What the change actually is

| | until 2026-09-21 12:00 PT | after |
|---|---|---|
| posts | **$5 per 1,000 calls** | **$5 per 1,000 posts** |
| profiles | (included in call price) | **$10 per 1,000 profiles** |

Every post returned counts after the change, **including parent and quoted
posts** pulled in by a thread fetch. That is the part that makes it more
expensive than it first looks.

## Cost, both samples, both sides of the change

**Core sample** — 30 winners + 90 matched controls, ~100 pre-launch posts each
(12,000 posts, 120 profiles). This is the H1/H2 test and the one worth running.

**Full sample** — 177 winners + 531 controls (70,800 posts, 708 profiles).

| | before (10 posts/call) | before (100 posts/call) | **after** |
|---|---:|---:|---:|
| **core** | $6.00 | $0.60 | **$61.20** |
| **full** | $35.40 | $3.54 | **$361.08** |

⚠️ **The "before" column is a range, not a number, because posts-per-call is
unverified.** It is the whole size of the saving and I could not confirm it
without an account. If a call returns 100 posts the saving on the core sample
is ~$60; if it returns 10, ~$55; if it returns 1, there is no saving at all.

**Maximum possible saving by rushing: ~$60 (core), ~$357 (full).**

## What signing up requires

⚠️ **I could not confirm the mechanics** — xAI's public pricing page documents
rates but not account creation, payment terms, approval or waitlist. What is
documented: **there is no subscription**, billing is usage-based per token and
per search, and some accounts have access to promotional credits through a
data-sharing programme.

**So I cannot tell you whether four days is enough**, and that uncertainty is
itself an argument against the deadline. If signup needs a payment method,
identity verification or any approval step, the window could close before
access is granted — **and the only thing lost by missing it is the ~$60.**

## What running core-only loses

Core (30 winners / 90 controls) is the **minimum that clears the standing
n≥30 floor**. It can answer H1 — do winners have a pre-existing account more
often than matched losers — with a Wilson interval on the difference.

It **cannot**:
- split by venue, launch window, or size band — every subgroup falls under n=30
- support S3–S7 (age, cadence, engagement, third-party mentions) at useful
  precision; those need the full sample
- survive heavy attrition. If the expected drop-off is real — most memecoins
  have no X presence — 30 winners could yield 10 resolvable accounts and the
  answer becomes "not answerable", with the money already spent

⚠️ **That last one is the real risk in buying the core sample**, and it is
independent of the deadline. **Resolve §6.3 first** — it tells us the
resolvable-account rate, which is what decides whether 30 winners is enough.

## The thing that IS time-sensitive, and it is free

⛔ **No collector has run since 2026-09-15 05:07:59 UTC.**

The socials capture shipped today is **forward-only**. Every hour without a
collector is sample that cannot be bought back at any price, from xAI or
anyone else. **That is a real, compounding, permanent loss and it costs nothing
to stop** — unlike the X deadline, which costs $60 and stops nothing.

**If one thing gets done on a deadline this week, it is restoring collection,
not buying posts.**

## If he wants to buy anyway

It is a defensible call — $60 is small and it buys optionality. If so:

1. Buy **before** the 21st only if signup completes in time without rushing a
   payment decision.
2. Pull the **core sample only**. The full sample cannot be specified until
   §6.3 resolves.
3. ⛔ **Verify these three before spending**, all named in
   `PRELAUNCH_SIGNAL.md` §7: that X Search returns **historical** posts
   filterable by date (the whole design rests on strict pre-launch filtering),
   that it exposes **account creation date** (S1 and S2 depend on it), and the
   actual **posts-per-call** ratio.

**If the first of those is false, the method dies and no amount of data
rescues it. Check it before paying.**
