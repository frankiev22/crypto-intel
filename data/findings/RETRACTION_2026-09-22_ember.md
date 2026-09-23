# ⛔⛔ RETRACTION: the whole EMBER writeup was about the wrong contract

**2026-09-22/23. Frank caught it. He was right and I was wrong, for the third
time today, in the same family.** This file is the permanent record of the error.
Nothing is deleted; the wrong statements are quoted here so they cannot be
quietly re-derived.

---

## 1. The two contracts, both measured 2026-09-23 00:56Z

| | ⭐ **REAL EMBER** | ⛔ the one I analysed all day |
|---|---|---|
| mint | `5dvXTZ5qwgafnHtwu3Ls3QrWx1U4LQsFeCuJgkk4QEC6` | `FLCr9vGMTkbDcRCoirP5Hx8gB7TW1Azt3pkw3qp2HTsh` |
| pairs | **30, which is the API cap - read "30 or more"** | 3 |
| liquidity, ALL pairs | **$2,331,895**, a FLOOR (see §7) | ⛔ **$1.39**, complete |
| 24h volume | $6,858,875 | "$75,637,037" on $1.39 of backing |
| market cap | $17,932,579 | ⛔ claimed **$1,314,046,208** |
| price | $0.01771 | $0.00000127 |
| venues | meteora 19, orca 6, raydium 3, pumpswap 1, meteora-dbc 1 | meteora 2, pumpswap 1 |
| quote assets | SOL $1,130,967 · **MET $522,677** · USDC $397,766 · EMBER $280,485 | SOL $1.39 |
| first pool | **2026-09-09 22:25:01Z** | 2026-09-21 10:55:09Z |
| mint / freeze authority | both revoked, SPL | both revoked, SPL |
| $100 round trip | ⭐ **TRADEABLE, $99.19 back, 0.81%** | TOTAL_LOSS, $0.32 back |
| $2,000 round trip | ⭐ **TRADEABLE, $1,974.03 back, 1.30%** | TOTAL_LOSS, $0.33 back |
| shape | LIQUID | **PHANTOM** |

⭐ **Frank said EMBER was at $17.2M and healthy. Measured: $17.93M and a $2,000
sell costs 1.30%. He was right to the first decimal place.**

## 2. What is retracted, verbatim

Every one of these was published today and every one of them is withdrawn:

- ⛔ *"EMBER was NOT dead this morning... its PumpSwap pool held 2,690 SOL"*
- ⛔ *"our $292k depth at 17:11Z on 09-21 is CONFIRMED by chain... the 3.97x was
  real"*
- ⛔ *"dead NOW ($20.36 across 5 pools on 3 venues, $100 → $0.32) but it died at a
  timestamp, by a person"*
- ⛔ *"EMBER is a Meteora DBC launch, not pump.fun"*
- ⛔ *"4 of the 5 dead ones died by a single `Withdraw`... EMBER 11:09:37Z"* — the
  EMBER line of that table only.
- ⛔ and worst, in `docs/GORILLA_ARCHIVE.md` §3 and `analysis/gorilla_archive/build.py`:
  *"The real contract is `FLCr9vGM…`... The resolver instead selected
  `5dvXTZ5q…`"*. **That is exactly backwards.**

## 3. ⚠️ What was NOT wrong, because the distinction matters

**The on-chain trace was correct.** `FLCr9vGM…` really did launch on Meteora DBC
at 2026-09-21 10:55:09Z, really did take in about 2,900 SOL, really was drained by
`HoX8uwcQiEmzF3qEzMznkqDG9PR4qa48ugHdf29vinsz` at 11:09:37Z on 09-22, and really
does have $1.39 left. Every timestamp and every vault read holds.

⛔ **What was wrong was the IDENTIFICATION.** I attached a correct trace of a
24-hour-old impersonator to a two-week-old piece of infrastructure, because I
keyed the two together by the ticker EMBER while telling everyone else to key on
the address. Standing rule 2, broken by me, in prose, one day after I shipped an
AST test to stop it happening in code.

## 4. ⛔⛔ The lesson is the OPPOSITE of the one I published

`GORILLA_ARCHIVE.md` §3 used EMBER to argue that the date-based resolver picks the
wrong contract. The measurement says the resolver was **right**:

- Gorilla named EMBER on **2026-09-10**.
- The real mint's first pool predates that by one day: **09-09 22:25Z**. ✅
- The impersonator's first pool is **09-21 10:55Z**, twelve days AFTER the
  mention. The resolver's date rule rejected it correctly.
- Its quote assets include **MET, Meteora's own token, at $522,677**, and 19 of
  its 30 pools are Meteora. That is precisely what *"a token-pairing launchpad on
  Meteora"* should look like on chain.

⭐ **So: an automated rule got it right and I overrode it by hand with a wrong
answer.** The hand-check felt authoritative because it was on chain, and it was
on chain, on the wrong account. **On-chain is not the same as correct.**

## 5. Root cause, which is the thing to actually fix

Two bugs, one shape, and Frank named it: *"we have been reading one pool on tokens
that trade across thirty."*

1. ⛔ **Single-pair reads.** Everything that priced a token read one pair and
   reported it as the token. On the real EMBER that is a **3.52x understatement**
   ($663,260 of $2,331,895). The more pools a token has, the worse the error, so
   it is worst exactly on the pairing-launchpad assets that are now the
   interesting class.
2. ⛔ **No phantom check.** $1.31 **billion** of claimed cap on **$1.39** of
   backing was allowed to be called EMBER and written up as a real token with a
   real death.

Fixed in `allpairs.py`: every liquidity and volume figure is summed across every
pair for the mint, `pair_count` is stored because it is itself a signal, and
`mcap > $1,000,000` with total liquidity `< $1,000` is labelled **PHANTOM** and
can never produce a finding again.

## 6. What Gorilla's EMBER actually is, redone against `5dvXTZ5q…`

His words, dated, unedited:

- **2026-09-10:** *"$EMBER, a token-pairing launchpad on Meteora hit $6m"*
- **2026-09-11:** *"$EMBER ran to $40m, but had a harsh correction sub $10m"*

Measured now: **$17.93M cap, $2.33M of real liquidity across 30 pools on 5
venues, $6.86M of 24h volume, both authorities revoked, and a $2,000 exit costs
1.30%.** Arc consistent with his account: $6m, a run to $40m, a correction under
$10m, and a recovery to about $18m.

⭐ **It is the same category as stonk.fun** (`docs/ASSET_PAIRED_TOKENS.md`): a
venue whose product is pools denominated in other assets. One pool per paired
asset is why it has 30 of them, and why reading one of them was guaranteed to
mislead.

---

## 7. ⛔⛔ A second correction, to the fix itself, the same day

`allpairs.py` shipped this morning claiming *"30 pairs is the signature of a
pairing-launchpad asset"*. **That is wrong and I found it by probing rather than
by reasoning. 30 is Dexscreener's hard cap.**

| mint | pairs returned |
|---|---|
| SOL, which trades in thousands of pools | **30** |
| USDC | **30** |
| BONK | **30** |
| EMBER `5dvXTZ5q…` | **30** |
| Hypurr `8RNUw4N6…` | **30** |
| a one-pool pump.fun token | 1 |

⚠️ **And the 30 are not the largest 30.** EMBER's returned liquidity order was
`521727, 357897, 664541, 109347, 258316, ...` - not descending. So nothing about
the pools left out can be bounded from what comes back.

⭐ **Consequences, all now enforced in code and tested:**

1. `pair_count == 30` means **"30 or more"**. Stored as `truncated`.
2. Every total at the cap is a **FLOOR**, stored as `total_liq_is_floor`. EMBER's
   $2.33M is a lower bound, not a measurement.
3. ⛔ **A truncated sample may never be graded PHANTOM.** 30 arbitrary pools
   summing to nothing says nothing about a 31st. The phantom that forced the rule
   had **3** pairs, so it was a complete sample and the verdict stands.
4. `pair_count` is a signal at the **low end only**: 1 to 3 pairs is an ordinary
   launch. A high count means "many pools" and nothing more precise.
5. ⛔ **Batching makes it worse, not cheaper.** Three mints in one call returned
   30 pairs TOTAL, split **15 / 14 / 1**. A 30-mint batch would hand back about
   one pair per mint and silently reproduce the exact bug this exists to kill.
   **One call per mint, always.**

⭐ **This is the same error class as the one being retracted above**, caught one
step earlier: I asserted a pattern from a handful of observations that all sat at
a ceiling I had not tested for. Standing rule 15.
