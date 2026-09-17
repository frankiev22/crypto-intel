# Pre-launch signal: backtest design

**2026-09-17. Design only. Nothing has been run and no data has been bought.**

**The question, in Frank's words:** *"go back to Stonk, look at their Twitter and
see if there were any signs of this being a great project before it launched.
The goal is to find projects that are upcoming and to front-run them before the
public catches on."*

**That is a falsifiable hypothesis, and it is the most promising idea in this
project.** This file specifies how to test it so the answer means something.

---

## 1. ⭐ Why this one is not killed by Marino

Every forward-looking idea in this repo has died on the same rock: perfect
knowledge of graduation probability still loses money, because **price already
reflects the probability** by the time the signal is readable.

**Pre-launch, there is no price.** A project with a building audience and no
token has no market quoting odds on it. Marino's mechanism — the thing that
kills scoring models — **has nothing to act on before launch.** That is a real
structural difference, not a loophole, and it is why this idea deserves the
flagship slot.

⚠️ **The honest counter, which the test must survive.** You cannot buy pre-launch.
By the time you can, there is a price, and it may already reflect exactly the
audience the signal measured. **So the hypothesis is not "pre-launch signal
exists" — it is "pre-launch signal predicts outcomes measured from the first
price a retail buyer could actually pay."** If the edge lives entirely in the
gap before that price exists, it is not tradeable and the answer is still no.

**Pre-commit the entry point as the first observable price at or after launch**,
not the launch price, not the low.

---

## 2. ⛔ The three ways this goes wrong, and the design that prevents each

### 2.1 Survivorship — the fatal one

**"Go back to a winner and look for signs" always succeeds.** Every winner will
have *something* in its history that looks like a signal, because you already
know the answer. This is the single most likely way to produce a confident,
worthless result.

**Required: a matched control group.** For every winner, sample contracts that
launched in the same window, on the same venue, and did **not** cross. The
question is never "did winners have signal X" — it is **"did winners have signal
X *more often than* non-winners"**, with an interval on the difference.

### 2.2 Hindsight in the signal definition

If the signal is defined after looking at the winners, it will fit them.

**Required: pre-commit the full signal list to a file before any winner's
history is examined** — per the standing rules, same as every threshold in this
repo. The file is written, committed, and *then* the data is pulled. Section 4
is that list; it must be frozen before section 5 runs.

### 2.3 Base rates

If a signal appears in 80% of winners and 79% of non-winners it is worthless,
and it will still look impressive in isolation. With a graduation base rate of
**0.198%**, almost any filter applied to winners alone will look spectacular.

**Required:** report the contrast and its interval, never the winner-side rate
alone. ⛔ **Never quote lift against the 2.10% figure** — it is computed on the
liquidity field that overstates by a median 781x. Use 0.198% (Kamat) or our
clean 0.22%.

---

## 3. Sample

**Winners — from our own verified data, keyed by contract address:**

| pool | n available | notes |
|---|---:|---|
| `graduated` milestones | 32 | strongest definition |
| verified $5M crossings | 115 | verified = passed the §3.2 integrity gate |
| verified $1M crossings | 177 | largest usable pool |

**Use the verified sets only.** Unverified crossings are ~75% phantoms
(`TRACKER_SCOPING.md` §3) and a phantom has no project behind it to have had a
pre-launch signal. Including them guarantees noise.

**Controls:** for each winner, **3 contracts** matched on (a) launch date within
±24h, (b) same venue/`dex_id`, (c) FDV at first observation within the same
decile — that did **not** reach $1M. Our observations give a large pool to draw
from: ~2,500 distinct contracts/day.

**Target: n≥30 winners with a resolvable X account** — the standing floor — and
90 matched controls. Below 30, report nothing.

⚠️ **Expect heavy attrition.** Most memecoins have no X presence at all, and
**that absence is itself a measurement**, not a dropped row. Record it as
`no_account`, do not discard.

---

## 4. ⛔ Pre-committed signal list — freeze this before pulling any data

All measured **strictly before** the launch timestamp. Any post, follower count
or engagement dated at or after launch is excluded; timestamp discipline is what
makes this a backtest rather than a story.

| # | signal | type | measured as |
|---|---|---|---|
| S1 | account exists pre-launch | bool | account creation date < launch |
| S2 | account age at launch | days | launch − creation |
| S3 | followers at launch | int | ⚠️ see 6.2 — historical value may be unavailable |
| S4 | pre-launch post count | int | posts in the 30d before launch |
| S5 | posting cadence | posts/day | S4 / 30 |
| S6 | pre-launch engagement | median replies+reposts per post | over the 30d window |
| S7 | third-party mentions pre-launch | int | distinct accounts mentioning the project before launch |
| S8 | website live pre-launch | bool | `info.websites` resolves (median fetch 0.69s, §4.1b) |
| S9 | account is linked in token metadata at launch | bool | from `info.socials` — ⛔ **not currently stored**, see §6.1 |

**Primary hypothesis (H1):** winners have a materially higher rate of **S1**
(a pre-existing account) than matched controls.

**Secondary (H2):** among contracts that have an account, winners show higher
**S2** and **S6** — age and engagement, not raw follower count.

**Frank's stated instinct maps to H1 and H2**, and they are the cheapest to
measure. Test those first; S3–S7 are supporting.

---

## 5. ⭐ What would falsify it — write this down before running

The test fails, and the idea is dropped, if **any** of these hold:

1. **S1 contrast interval includes zero** at n≥30 winners and 90 controls. If a
   pre-existing account is no more common among winners than among matched
   losers, the hypothesis is dead as stated.
2. **The contrast survives but the entry does not.** If winners are
   distinguishable pre-launch but the edge disappears when measured from the
   first purchasable price (§1), it is not tradeable. **This is the most likely
   failure mode and the most important one to check.**
3. **Attrition makes it unanswerable.** If fewer than 30 winners have a
   resolvable account, report "not answerable at this sample size" and stop.
   Do not lower the floor.

**Report both ways**, per standing rules: with and without contracts whose
account could not be resolved.

---

## 6. What has to change before this can run

### 6.1 ✅ SHIPPED 2026-09-17 — socials are now captured

`has_telegram`, `has_twitter`, `has_website` and `social_count` are derived by
`scanner.socials_of()` and persisted by `journal.record()` (commit `ce0d33a`).
Verified on 67 rows from a real pass, read back from disk: all four present on
67/67, no nulls.

⚠️ **Forward-only. It does not backfill.** The 177 existing verified winners
have no socials and never will. **The usable sample starts accumulating from
2026-09-17 and only while a collector is running** — which currently it is not
(`CLAUDE.md`, blockers). Every day without collection is still sample lost.

### 6.3 ⛔ OPEN VALIDITY QUESTION — does the metadata exist at launch?

**This could invalidate S1, S9 and the cheapest half of the design, so resolve
it before spending money on section 7.**

First real capture, 67 rows: **0% telegram, 0% twitter, 1% website.** Those rows
are tokens seconds old, so a near-zero rate is plausible. **But there is a
second explanation that would be fatal:** Dexscreener's `info` block is
populated when someone submits or pays for it, not at mint. If it fills in
*hours or days after launch*, then capturing at scan time measures **"has the
team filed their Dexscreener metadata yet"**, not **"does this project have a
Twitter"** — and a real project with a two-year-old account would read as
`has_twitter: False` at launch.

**That is the same failure class as reading a stale market cap as live**: the
field is present, it is just not measuring what its name says.

A first probe is suggestive but far too small to conclude: of 20 contracts first
seen 2026-09-15, only **2 were still listed** two days later, and **1 of those 2
had acquired a twitter link** it did not have at scan time.

**The test, once a few days of capture exist and costs nothing:** for contracts
captured at t≈0, re-read `info` at t+24h and t+72h and compare against the
stored value. **If the fill-in rate is material, S1/S9 must be measured from a
delayed re-read rather than from the launch-time row**, and the backtest must
use X directly for the pre-launch window rather than trusting Dexscreener
metadata as a proxy for account existence.

⚠️ **Do not buy X data until this is resolved.** If Dexscreener metadata cannot
identify the project's account at launch, the handle-resolution step in section 7
is harder and more expensive than costed there.

### 6.2 ⚠️ Historical follower counts probably do not exist

X does not expose a follower-count time series. S3 as specified measures
**today's** follower count, which is contaminated by the very pump we are
studying. **Either drop S3 or redefine it** as "followers today", labelled as
contaminated and excluded from H1/H2. **Do not quietly use today's number as if
it were the launch-day number** — that is the same class of error as reading a
stale market cap as live.

---

## 7. Cost, and a deadline that matters

**The reframe:** `X_API.md` (2026-09-07) correctly concluded that *continuous*
narrative monitoring is unaffordable — the cheapest useful configuration costs
about twice Frank's entire bankroll every month. **A backtest is a different
shape.** It is a bounded, one-time historical pull, and it is cheap.

Via xAI's X Search API:

| item | price |
|---|---|
| posts fetched | **$5 per 1,000** |
| user profiles fetched | **$10 per 1,000** |

Estimate for the full design:

| line | volume | cost |
|---|---:|---:|
| 177 winners × ~100 pre-launch posts | 17,700 | $88.50 |
| 531 controls × ~100 posts | 53,100 | $265.50 |
| 708 profiles | 708 | $7.08 |
| **total, one-time** | | **~$361** |

Trimmed to the H1/H2 core — 30 winners, 90 controls — it is **~$65 one-time.**

⚠️ **Deadline: the pricing changes on 2026-09-21 at 12:00 PT.** Until then X
Search bills **$5 per 1,000 calls**; after, **$5 per 1,000 posts**. A single call
returns many posts, so **pulling before the 21st is materially cheaper** —
potentially by an order of magnitude depending on posts-per-call. **That is four
days away.** If this experiment is going to run, the data pull is the part worth
front-loading.

⛔ **Nothing has been signed up for and nothing has been bought.** Standing rules
are free tools only; any xAI account and any spend is **Frank's decision alone**.
This section prices it, nothing more.

### ⚠️ Verify before spending anything

1. **Does X Search return historical posts with usable timestamps, filterable by
   date range?** The entire design rests on strict pre-launch filtering. If it
   only serves recent posts, this method dies and the money should not be spent.
2. **Does it resolve an account's creation date?** S1 and S2 depend on it.
3. **What is the actual posts-per-call ratio**, which decides whether the
   pre-21st pull is worth rushing.

---

## 8. If it works

**If pre-launch signal is real and survives the first-purchasable-price test,
that is the product**, and it is genuinely novel — it is the one thing in this
repo that is not a filter on things that have already happened.

It would also change what the 1M tracker is for: the tracker becomes the
**outcome recorder** that validates the pre-launch model, rather than the
product itself. **Build the tracker's verification gate either way** — this
experiment needs exactly the same "did it really cross" machinery
(`TRACKER_SCOPING.md` §3.2), and that gate is currently broken
(`exit_depth()`, 5 of 6 reads failing).
