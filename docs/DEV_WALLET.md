# Dev wallet history, funding graphs, first buyers, LP

**2026-09-17. `devwallet.py` is built and every number below came from running
it on real contract addresses, not from reading a diff.**

> *"Dev wallet history is super important and you already mentioned it but
> didn't come up with a way to track it."* — Frank

⭐ **He is right that it is the highest-signal item available.** Liquidity can be
seeded, volume washed, holders farmed, socials bought. **A deployer's history
already happened, so it cannot be bought — only evaded.** And the evasion has
its own signature.

⛔ **But read §5 before trusting any of it. On n=4 the deployer signal did not
separate good tokens from bad ones.** The plumbing works; the signal is
unvalidated.

---

## 1. The method, and what it actually costs

| step | how | measured |
|---|---|---|
| deployer | RugCheck `creator` | ~600 ms, free, no key |
| back catalogue | Helius v0 `type=CREATE` | ~500 ms |
| existed before launch? | `getSignaturesForAddress(before=<create sig>)` | **one call** |
| funding chain | v0 page-walk, earliest inbound SOL, per hop | 1–4 s/hop |
| first buyers | oldest mint signatures → batched v0 enrichment | **0.9–3.7 s** |
| buyer funding overlap | funding chain per buyer | 16–32 s |
| LP detail | RugCheck `lockers` / `markets` | ~600 ms |

### ⛔ Two methods I tried that do not work — do not repeat them

**Dating the deployer wallet by walking its history.** A busy deployer never
reaches the start within any sane page budget, so the oldest transaction seen
**post-dates the launch** and the age comes out **negative** — WOFI returned
`-0.1h`. A negative age is not an age; it is a nonsense number wearing the
costume of a measurement, which is the failure class this repo keeps repeating.
⭐ **The fix is to ask a different question.** Not *"how old is this wallet"* but
*"did it exist before the launch"*, which is one call with `before=<create
signature>` and is exact.

**Finding the creation transaction by paginating the mint's signatures.** WOFI
has **over 12,000**. Stopping early returns a transaction that merely looks
oldest and attributes the token to the wrong wallet — worse than returning
nothing. **Use RugCheck's `creator`.**

## 2. Live output — the deployer chain

```
WOFI     [14.5s]  Qd8wLfS6rsBKB6Ku46YQEFjUc8HSjD799UE81Pi2dBk
   prior_launches=0   had_prior_activity=True   -> FIRST_LAUNCH_AGED_WALLET
POGGERS  [ 1.2s]  7aMh7hr1M5i3gH3ELhBkqRZ7jMDSyaxMvhxexPFB9NKh
   prior_launches=0   had_prior_activity=None   -> FIRST_LAUNCH_AGED_WALLET
ROCK     [28.1s]  DpA1fm1bwHQnS6WDu7c6ouY1tcZi8dkTCDx8X6c9s6Rd
   prior_launches=None had_prior_activity=None  -> UNKNOWN_HISTORY
WYNX     [ 1.6s]  AezgKrZDywao7FztLwNVu23BTyeX9yJZ9aojJy5bwrXq
   prior_launches=1   had_prior_activity=True   -> SOME_HISTORY
```

⚠️ **`had_prior_activity=None` on POGGERS is not `False`.** The query failed.
"We could not check" and "this wallet is brand new" are different answers and
only one of them is damning; the code keeps them distinct.

### The funding graph works

WOFI's deployer, three hops back:

```
hop1  A3Dwoqhoz1v3MSt2Ggzd4Cka3G3xAwbrsQUjnuQSEn4S   0.0000 SOL  2026-09-03 04:20
hop2  EwzmRWB9nNZQfjpnzJvfR4PGGP4zKW82Qz43rF16fj5Q   0.0653 SOL  2026-08-27 18:44
hop3  iGdFcQoyR2MwbXMHQskhmNsqddZ6rinsipHc4TNSdwu    0.0653 SOL  2026-08-27 18:41
```

**This is the machinery that defeats the fresh-wallet evasion**, and it runs.
On WOFI the funder had 0 prior launches, so it did not fire — but the traversal
is the part that had to exist.

## 3. First buyers and shared funding

On young tokens from the 2026-09-17 capture:

```
sym         buyers  distinct funders  top funder count   SHARED
solami           6                 6                 1   False
beer             6                 6                 1   False
SOLDIERS         4                 4                 1   False
TPAID            4                 2                 3   ⭐ True
```

⭐ **TPAID: four first buyers, two funders, one of which funded three of them.**
That is the shape Frank described — *"ten wallets funded from one wallet is a
bundle wearing a costume."*

### ⚠️ Two false-positive classes found by running it, now handled

1. **The pool is not a buyer.** solami's first "buyer" was `AvjLsYC4…` — its own
   pair address. The first token transfer on any mint goes into the pool.
   `first_buyers(exclude={pair})` now drops it.
2. ⭐ **Routers are not bundlers.** `beer`'s six first buyers initially shared
   one funder: **`AxiomRXZAq1Jgjj9pHmNqVP7Lhu67wLXZJZbaK87TTSk`** — the Axiom
   trading terminal. Terminals fund and route for thousands of unrelated users,
   so a shared router is **a queue at the same till, not a conspiracy**.
   `router_funder` now flags it and suppresses the bundle claim.

### ⛔ A limitation I created and must flag

**The funder identified depends on how deep the walk went.** `beer` reported
Axiom as sole funder at 12 pages and six distinct funders at 3 pages, because
"earliest inbound transfer I saw" is not "the funding transaction" unless the
walk reached the wallet's beginning. `funding_chain()` carries an `exact` flag
per hop; **`buyer_funding_overlap()` currently discards it.**

⚠️ **So TPAID's `SHARED=True` is a candidate, not a finding.** Fix before
quoting: propagate `exact`, and treat any overlap built on inexact hops as
`UNKNOWN`.

## 4. LP detail

```
sym       lockers  lpLocked%  LP providers   liquidity   mint authority
WOFI            0        100             0       2,039   none
POGGERS         0        100             0           1   none
ROCK            1        100             1     184,217   none
WYNX            0        100             0      44,593   none
```

⚠️ **`lpLockedPct` is 100 for all four and therefore discriminates nothing here**
— pump.fun burns LP by default, so "locked" is the norm rather than a virtue.
**`n_lockers` and `total_lp_providers` do vary** (ROCK 1/1, the rest 0/0) and are
the more informative fields. ⛔ **Unknown stays `None`: "could not read the lock
state" is not "unlocked".**

## 5. ⛔ The honest verdict: it runs, it does not yet discriminate

**On the four tokens tested, deployer history did not separate good from bad:**

| token | independent label | deployer verdict |
|---|---|---|
| WOFI | **bad** — 43 holders, top10 100% | FIRST_LAUNCH_AGED_WALLET |
| POGGERS | **bad** — TOTAL_LOSS, 90% dup sizes | FIRST_LAUNCH_AGED_WALLET |
| ROCK | **good** — 1,466 holders, TRADEABLE | UNKNOWN_HISTORY |
| WYNX | **good** — TRADEABLE, 1,350 holders | SOME_HISTORY |

**The two bad ones got the same verdict, and one good one got no verdict at
all.** ⭐ Frank's thesis may still be right — a deployer with a graveyard is
surely damning — **but none of these four deployers had a graveyard**, so this
sample cannot test it. **It needs serial launchers in the sample, and n ≥ 30 per
arm.**

### Known coverage gap

**`type=CREATE` only fires for curve launches.** ROCK was deployed off-curve and
returns no CREATE events at all, which is why it scores `UNKNOWN_HISTORY` rather
than "clean". ⛔ **Do not read `UNKNOWN_HISTORY` as a pass.** Closing it means
detecting AMM-pool creation as a launch event too.

## 6. Next, in order

1. **Propagate `exact` through `buyer_funding_overlap`** — cheap, and the
   current output overstates confidence without it.
2. **Close the off-curve coverage gap** so `UNKNOWN_HISTORY` becomes rare.
3. **Build a labelled sample containing known serial ruggers.** Until then the
   verdicts are plumbing output, not evidence.
4. **Pre-commit thresholds before that run** — `FRESH_WALLET_SECONDS` and the
   serial-launcher cut at 3 are already written into the module, unvalidated and
   labelled as such.
