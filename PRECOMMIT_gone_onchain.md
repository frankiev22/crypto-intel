# PRE-COMMIT: is a contract we called `gone` actually dead, read FROM CHAIN

**Written 2026-09-23 before a single account was read.** Standing rule 6.

---

## 1. Why the 1.7% result is not good enough, in Frank's words

Frank, 2026-09-23: *"118 of 120 returned NO_PAIRS on BOTH methods. Both arms asked
the same indexer and got the same silence, so the test measured 'does Dexscreener
list this' and not 'is this token dead.' Requeue it properly: re-check a sample of
`gone` contracts by reading pool accounts ON CHAIN, not through an indexer."*

He is right, and he also caught that the two figures matching was rounding rather
than corroboration: **2/120 = 1.67% and 3/178 = 1.69%**. Two numbers that round
to the same 1.7% are not two confirmations.

⛔ **And the underlying defect is older than the experiment.** `record_outcome`
writes `gone` when **two INDEXER lookups fail** (`journal.py:974`), which
collapses four different states into one word:

1. the pool was closed
2. the pool is near zero but open
3. the indexer dropped it
4. we were reading the wrong pool

**Only the chain can separate those.** This experiment asks the chain.

---

## 2. The sample, fixed before it is drawn

- Every distinct **contract address** with `status == "gone"` on an outcome row in
  the last **72 hours**, paired with the **pool address** that row recorded.
- Ordered by the row's own timestamp, newest first, and the first
  **`N_SAMPLE = 60`** distinct contracts are taken. ⛔ No other selection, and
  nothing is dropped for being inconvenient.
- ⚠️ A contract whose row carries no pool address is **counted and reported
  separately**, never silently skipped. If we do not know which pool we priced,
  that is itself a finding about the row.

## 3. The verdict rule, per pool, from `getAccountInfo` on chain

| chain answer | verdict | what it means |
|---|---|---|
| `value == null` | **POOL_ABSENT** | the account does not exist. The pool really is gone |
| account exists, owner is a known AMM program, data non-empty | **POOL_EXISTS** | ⛔ the pool is still on chain. `gone` was wrong about this contract |
| account exists, owner is **not** a known AMM program | **NOT_A_POOL** | the address we recorded was never a pool account. A row-quality defect, not a market event |
| the RPC failed or errored | **UNREADABLE** | ⛔ counted, never folded into either side |

⛔ **`UNREADABLE` is its own bucket and may never be reported as POOL_ABSENT.**
That is the `authority_live=None` shape and it is the single most repeated failure
in this repo.

⚠️ **Existence is not liquidity.** A pool account that exists may hold nothing.
This experiment answers **"is the pool gone"** and explicitly does **not** answer
"is there a market". The second question needs vault balances, which our chain
reader cannot parse for Raydium CPMM (`docs/BACKLOG.md`, PONDER), so it is out of
scope here and must not be smuggled in.

## 4. What counts as the headline number

**`POOL_ABSENT / (POOL_ABSENT + POOL_EXISTS)`**, with its n and a Wilson interval.

- `NOT_A_POOL` and `UNREADABLE` are **excluded from the denominator and reported
  beside it**, both counts and both shares.
- ⛔ If `UNREADABLE + NOT_A_POOL` exceeds **one third** of the sample, **no rate
  is published at all** and the finding is about our rows rather than about the
  market.

## 5. What would make the result wrong

- ⛔ If most verdicts are **POOL_EXISTS**, then `gone` is largely an indexer
  artefact, the word must change in `journal.py`, and **every historical count
  that used `gone` as death is suspect** - including anything downstream that
  treated it as a total loss.
- ⛔ If most are **POOL_ABSENT**, then `gone` is roughly honest and the 1.7%
  all-pairs delta stands as a statement about description rather than verdicts.
- ⚠️ Either way the answer is about **72 hours of rows on one chain**, is not a
  base rate for all time, and is reported with its window attached.

## 6. Pre-registered prediction, so the result cannot be rationalised afterwards

⭐ **I expect mostly POOL_EXISTS.** The reasoning, stated now: `gone` is written
on two failed *indexer* lookups, and the indexer preferentially drops illiquid
tokens (`docs/GORILLA_ARCHIVE.md` section 3, where **86.4% [73.3, 93.6]** of 44
index-absent tokens failed a live round trip). A dropped listing is not a closed
account, and closing an AMM pool account is a deliberate act that earns the
closer almost nothing.

⛔ **If the result contradicts this, the prediction was wrong and it says so
here.** That is what a pre-registered prediction is for.


---

# RESULT, 2026-09-23 14:30Z

## ⚠️ FIRST, THE CORRECTION TO MY OWN FRAMING: the headline was already known

⛔ **Before quoting anything below as a discovery:** `docs/BACKLOG.md` A51 already records **0 of 5,816**
distinct pools in 24h of outcome rows closed on chain, measured 2026-09-22
(`data/findings/REPORT_2026-09-22_pushback.md`, "Correction 2"). That sweep covered **every** outcome row,
not just the `gone` ones, so it already bounds this subset at a far larger n. **This run does not discover
that pools are not closed.**

⭐ **What it does add, and only this:**

1. It asks the question **on the rows that carry the label**, under a rule and a pre-registered prediction
   written before a single account was read, so the answer could not be rationalised afterwards.
2. ⛔ **6 of 60 `gone` rows recorded a pool address that no AMM program owns** (`NOT_A_POOL`, 10.0%). For
   those rows we do not know which pool we priced at all. The 5,816 sweep did not separate that out, and it
   is a defect in our rows rather than a fact about the market.

## ⛔⛔ `gone` DOES NOT MEAN THE POOL IS GONE. Not once in 54 readable cases.

| verdict | n |
|---|---|
| **POOL_EXISTS** (the account is still on chain) | **54** |
| **POOL_ABSENT** (the account does not exist) | **0** |
| NOT_A_POOL (the recorded address was never a pool account) | 6 |
| UNREADABLE | 0 |
| NO_POOL_RECORDED | 0 |

**Headline, per section 4: pool actually absent = 0 / 54 = 0.0% [0.0, 6.6].**
Unusable was **6 of 60 = 10.0%**, comfortably inside the pre-committed one-third
ceiling, so the rate is publishable.

⭐ **The pre-registered prediction in section 6 was CORRECT**, and it is recorded
as such — ⚠️ though see the correction above: A51's 5,816-pool sweep meant the
prediction was made with a strong prior already on the record, which makes it a
weaker test of the process than it would have been otherwise: `gone` is written on two failed INDEXER lookups, and a dropped listing is
not a closed account. **Closing an AMM pool account is a deliberate act that earns
the closer almost nothing, and in this sample nobody did it even once.**

⭐ **A detail worth keeping: all 54 are `pumpfun_curve` accounts**, which is
consistent with the earlier measurement that 3,878 of 5,816 recorded pairs (67%)
are pump.fun bonding curves. So the population we label `gone` is dominated by
tokens still sitting on a curve, which the indexer stops listing.

## ⛔ What this means, per section 5, which pre-committed the consequence

Section 5 said: *"If most verdicts are POOL_EXISTS, then `gone` is largely an
indexer artefact, the word must change in `journal.py`, and every historical count
that used `gone` as death is suspect."*

**It is 100%, so:**

1. ⛔ **The word `gone` in `journal.py:974` is wrong and must change.** It should
   say what actually happened: two indexer lookups failed. `INDEXER_SILENT` or
   similar, with the four collapsed states kept apart.
2. ⛔ **Any count that read `gone` as a dead token is suspect**, including
   anything that folded those rows into a loss.
3. ⚠️ **This is 72 hours of rows on one chain**, n=54 readable, and it is not a
   base rate for all time. The window is attached to the number.
4. ⛔ **Renaming the status relabels outcomes across the whole record**, so it
   needs its own pre-commit rather than a patch. It is not done in this session.

## ⚠️ And what this does NOT say

**Existence is not liquidity.** Every one of the 54 pools exists; that is not a
claim that any of them can be sold into. Section 3 ruled vault balances out of
scope on purpose, because our chain reader cannot parse Raydium CPMM. ⛔ **So this
result may never be quoted as "these tokens are alive"** - only as "the pool
account was not closed".

⭐ **It also supersedes the weaker 1.7% framing**, which Frank correctly called
out: that test asked one indexer twice. This one asked the chain, and the answer is
unambiguous in a way the indexer test could never have been.
