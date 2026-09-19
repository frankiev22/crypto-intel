# PRE-COMMITTED: the safety verdict, v1 — written 2026-09-19, before it is computed on any token

Frank, 2026-09-19: *"those top coins need to also pass safety tests. We can't
have honeypots and fake volume."* Every token the universe tracks (member,
refused or candidate) carries this verdict. ⛔ **A token that fails is shown,
flagged, never hidden.** "Running and dangerous" is information.

## The levels

| level | meaning |
|---|---|
| **DANGER** | at least one check below found a mechanism that can take his money: he cannot sell, the issuer can freeze or take his tokens, or the pool is a proven fake (D1) |
| **WARN** | at least one check found something that should change how he sizes, and no DANGER |
| **NO FLAGS** | nothing checked found a problem. ⛔ **Never rendered as "safe".** Every verdict lists what was NOT checked |
| **UNKNOWN** | the sell check has never produced a verdict. A token whose sellability is unknown is never NO FLAGS |

Unknown inputs are `null` and listed under `not_checked`. They never pass.

## The checks, each with its source and its evidence standard

| id | check | DANGER when | WARN when | source | standing |
|---|---|---|---|---|---|
| S1 | **sellable (honeypot)** — a real $100 buy then sell | `TOTAL_LOSS`, `NO_SELL_ROUTE` | `COSTLY` (10–50% lost); verdict older than 48h (stale) | the universe gate, `chainfields.round_trip()` via Jupiter | a real quote, not an inference |
| S2 | **freeze authority** — the issuer can freeze any holder's account, which blocks selling | active, on a `token`-class mint | active on a `stable`/`major` (issuer-controlled by design; shown, not DANGER) | the mint account, read from chain | fact |
| S3 | **mint authority** — supply can be inflated | — | active, on a `token`-class mint | the mint account, read from chain | fact |
| S4 | **Token-2022 extensions** | `permanentDelegate`, `nonTransferable`, `pausable`, `defaultAccountState` frozen, transfer fee ≥ 10% | `transferHook`, transfer fee > 0 and < 10% | the mint account, read from chain | fact |
| S5 | **D1 fake pool** — `liq/fdv ≥ 0.95 AND sells_h1 == 0 AND buys_h1 ≥ 10` on the token's most liquid pair | fires | — | Dexscreener pair, `detector.d1()` | ⭐ **the only validated detector**, out of sample (`detector.py`) |
| S6 | D2 — `liq ≥ $1M AND txns_h1 ≤ 5` | never | never — shown as a hypothesis | same | ⛔ in sample, NOT validated; shown, affects nothing |
| S7 | **cap mostly unbacked** (the wallet farm, `docs/UNIVERSE.md` §3a) | — | `cap_backing_pct < 1` AND graduation-sourced AND ticker shared by > 1 tracked contract | the universe | descriptive; the signature that found the farm, not a validated detector |
| S8 | **holder concentration** | — | top holders > 50% of supply; fewer than 100 holders | Jupiter token data | descriptive, conventional thresholds |
| S9 | **RugCheck** (third party, attributed on every row) | `rugged: true` | any RugCheck risk at level `danger`; an insider network holding ≥ 10% of supply | `api.rugcheck.xyz` report, keyless, ≤ 1 request/s | theirs, unvalidated by us. ⚠️ Terms not yet found; the verdict must stand without it |
| S10 | **fake volume** | never | never | — | ⛔ **NOT CHECKED. There is no validated test.** Our M1/M2 rule failed (`docs/VOLUME_INTEGRITY.md` §3c) and M1′ was null against the farm (§3e). Every verdict says so, in words |
| S11 | LP locked | — | the most liquid market reports LP locked < 50% | RugCheck `markets[].lp` | descriptive; 4 of 4 tested read 100% on 09-18, so it may discriminate little |

## Cadence

S1 at the gate's cadence (members 24h, trending 6h, refused 48h). S2–S4 once per
token and every 24h thereafter (one `getMultipleAccounts` per 100 mints). S5,
S6, S8 on every live refresh. S9, S11 every 24h per token, trickled.

## What this is not

It does not rank anything and it does not predict. NO FLAGS is not a buy
signal; DANGER is not a short signal. It describes mechanisms that exist now.

## Amendment v1.1 — 2026-09-19 ~02:50Z, AFTER the first computation. Declared, not silent.

The first dry run over all 924 tracked tokens (nothing published) found two
defects in what I committed at `feb591a`. Both are corrected below. **The
thresholds did not move.**

1. **Class names that do not exist.** S2 exempted `stable`/`major`; the
   universe's classes are `token`, `stock` and `base` (stables, LSTs, wrapped
   majors). The exemption's own reason, "issuer-controlled by design", now
   applies to `base` and `stock`, and covers the issuer-control extensions in
   S4 (permanent delegate, pausable, default-frozen), because 162 of the 196
   permanent delegates are tokenized equities (150 xStocks share one issuer
   delegate). They are shown as **info**, with the words "issuer-controlled by
   design". A `token`-class contract with a live permanent delegate (29) or
   freeze authority (82) is still **DANGER**, including RWAs and stables that
   Jupiter does not tag, which are true flags about a real mechanism.
2. **S9's insider clause cannot be evaluated.** RugCheck's insider-network
   `tokenAmount` is not a share of supply: BONK's "transfer" network of 35,335
   wallets reads 98%, and one token's reads 175%. The clause is removed and
   stated on every verdict as **not checked**. With it goes the only bundle
   source we had: **bundle detection has no valid source today.**

| level | v1 as committed | v1.1 |
|---|---:|---:|
| DANGER | 265 | 143 |
| WARN | 344 | 416 |
| UNKNOWN | 49 | 95 |
| NO FLAGS | 266 | 270 |

UNKNOWN rose because xStocks that Jupiter cannot buy (`NO_BUY_ROUTE`) were
DANGER only through their delegate; with that shown as info, their
sellability is honestly unknown.

**First published run (v1.1, 2026-09-19 ~02:48Z, origin manual), 926 tracked
tokens:** DANGER **143**, WARN **431**, UNKNOWN **95**, NO FLAGS **257**. The
dry-run table above predates the insider clause's removal and read RugCheck
for 6 tokens; this run read it for 161 (765 deferred and counted, trickled by
later passes), which is why WARN is higher here.
