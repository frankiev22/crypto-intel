# Who actually holds this, and is that one buyer or twenty wallets

2026-09-23. Built from Frank's idea, which is the best one in the conversation:

> *"nobody should ever be able to buy more than 1%-2% of a coin that early on...
> Not sure how we could police that."*

He is right about both halves. **A per-wallet cap stops only the lazy version**:
splitting one buy across twenty fresh wallets costs a few cents of rent. So the
cap is not the measurement. The clustering is.

⛔ **And then running it produced a different and better answer than the one it
was built for.** That reversal is the substance of this file.

---

## 1. ⭐ The finding: the same wallets top-hold launch after launch

Two pump.fun graduations picked at random out of our own ledger share **three of
their top-10 holders**. Nothing about them is fresh: every top holder carries
**3,000+ signatures**.

So the question got measured properly. **Population, pre-committed before the
run:** 60 consecutive distinct mints from our graduation ledger, newest first.
Per mint, `getTokenLargestAccounts` with pool vaults and program-owned accounts
excluded, top 10 wallet holders kept.

| | |
|---|---|
| mints measured | **60** |
| distinct top-10 wallets across them | **474** |
| ⭐ **wallets in the top 10 of MORE THAN ONE mint** | ⭐ **43 / 474 = 9.1% [6.8, 12.0]** |
| ⭐ **median share of a token's top 10 that also top-hold another mint** | ⭐ **20%** |

Recurrence distribution, wallets by number of mints they top-hold:

| mints | wallets |
|---:|---:|
| 1 | 431 |
| 2 | 21 |
| 3 | 8 |
| 4 | 1 |
| 5 | 2 |
| 6 | 3 |
| 7 | 1 |
| 8 | 2 |
| 9 | 2 |
| ⭐ **10** | **3** |

⭐ **Three wallets are top-10 holders of 10 of the 60 sampled launches, which is
17% of everything that graduated in that window:**
`27HFmP7ccLadGswvQfvea4o3juLw75cPF4V6jWpHM3MX`,
`8N4QDR8m54PuV2KgHSu39QRHrNooNEK667hBeKVokZoc`,
`9UnZnrFJ1CXCmCorgGU9NvYkX5np1h4v4ympx3Nrdw3v`.

⚠️ **Every number here is a FLOOR.** The registry can only see mints this system
has already looked at, so a wallet shown in 10 launches appears in **at least**
10. **It can prove presence and never absence.**

## 2. ⛔ Why this reframes the concentration question rather than answering it

A fresh graduate looks exactly like Frank's worry:

```
DqpMAS35Lkx745JucFjjTXpb8JEmJjR9QmBye7Dmpump
  raw top 1        17.54%
  raw top 10       64.03%
  wallets over 2%  8
```

Read naively that is eight people holding two thirds of the supply. But:

```
  top-10 holders also seen top-holding other launches:  8 of 10  (80%)
  the worst of them also top-holds 9 other launches
  fresh wallets among the top holders:                  0
  established wallets (hundreds to thousands of txs):   all of them
```

⭐ **Against a measured median of 20%, this token is at 80%.** Its "whales" are
industrial participants present across launch after launch, not one person
cornering supply. **That is a completely different fact, and it is checkable.**

⛔ **Neither reading is a verdict.** A token full of recurring snipers is not
thereby safe, and one with no recurring holders is not thereby honest. The
number describes who is there. It does not say what happens next.

## 3. The three ways this measurement goes wrong, all handled in code

1. **A pool is not a whale.** The largest token accounts for almost any memecoin
   are AMM vaults. Accounts whose owner is a **program** rather than the System
   Program are excluded and counted separately as `n_pool_vaults_excluded`.
   Without this every healthy token shows a 60% whale.
2. ⛔ **An exchange hot wallet funds everybody.** Two wallets both funded by
   Coinbase are not a cluster, and collapsing them would flag every real token
   on earth. So a funder's **outbound breadth** is measured, and one paying
   `HUB_BREADTH` (25) or more distinct wallets is labelled a hub and **never
   collapsed**. `devwallet.funding_chain()` names this problem and declines to
   solve it; this solves it by measuring rather than by maintaining a list of
   exchange addresses.
3. ⛔⛔ **Most top holders are not sybils at all, and this was found by running
   it.** A wallet is only eligible to be collapsed when its entire history was
   reached **and** it carries at most `FRESH_MAX_SIGNATURES` (250) signatures.
   Collapsing two 3,000-transaction traders because a walk found a common
   ancestor would **manufacture** a cluster. ⭐ **"All top holders are
   established traders" is a real answer and the module says it out loud**,
   rather than returning a silent zero.

## 4. ⛔ Two bugs found by running it, both recorded

**The oldest transaction is usually not the funding one.** The first version read
only a wallet's single oldest signature and failed on **6 of 8 real wallets**
with *"the oldest transaction did not fund this wallet"*. The reason: that
transaction is normally one the wallet **signed**, so it paid a fee and its
balance went **down**. `funder()` now scans forward from the oldest signature
until it finds the first transaction where the balance actually increased. That
took the success rate from 2 of 8 to 5 of 8 on the same wallets.

**The walk depth is a ceiling, not a measurement.** `_sig_pages` stops at 3,000
signatures, so any busier wallet reports `exact: false`. That is correctly
treated as "cannot be clustered", never as "no cluster found".

## 5. ⛔ This is description. It is not a score and may never become one

Marino applies to anything forward-looking, and five ranking models have been
built and retracted in this repo. **This predicts nothing.** It states a
checkable fact about the present:

> *these eight wallets hold 64% between them, and six of them are wallets we
> have already seen top-holding other launches, one of them nine others*

Every part of that is verifiable by the reader against the chain. **It needs no
hit rate to defend, because it makes no claim about what happens next.**
`test_intel.py` fails at the AST level if any API field name contains `score`,
`grade`, `rank`, `expected_return`, `prediction` or `rating`.

## 6. Where it lives

| | |
|---|---|
| `concentration.py` | the module; `holders()`, `funder()`, `breadth()`, `recurrence()`, `analyse()` |
| `intel.concentration(mint)` | the API endpoint, with provenance and honest nulls |
| `data/holders/*.jsonl` | ⭐ the append-only registry. **Every `analyse()` call adds to it, so the measurement strengthens at zero marginal cost** |
| `analysis/holder_recurrence/measure.py` | the 60-mint run that produced the base rate |

⭐ **Cost: RPC reads and arithmetic. No model call anywhere, on any path.**

## 7. What is not done

- ⚠️ **The base rate is 60 mints and one launchpad.** It is pump.fun graduations
  only, so it describes that population and not Base, BSC or the other Solana
  venues. Widening it is the same work as `docs/COVERAGE_PLAN.md`.
- ⛔ **Two hops of separation defeat the cluster half entirely**, and nothing
  here pretends otherwise. The recurrence half is unaffected, because it needs
  no funding walk at all.
- ⚠️ `getTokenLargestAccounts` returns **at most 20 accounts**, so this is
  top-20 concentration and never the full distribution. `is_partial` is always
  true and says so.
