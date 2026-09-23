# Coverage expansion: raw research

**Raw material only. This is not a plan.** Every line carries a confidence label
and, where it is a number, the call that produced it.

Produced 2026-09-22, ~22:30-23:10 UTC. All measurements are from that window.

## Confidence labels

| label | means |
|---|---|
| **VERIFIED** | I made the call and saw the result in this session. Solana program IDs were confirmed with `getAccountInfo` via `chainfields._rpc`; EVM contracts with `eth_getCode` on a public RPC. |
| **DOCS** | An official documentation page says so. I fetched the page but did not independently confirm the claim on chain. |
| **UNVERIFIED** | I could not confirm it. Treat as a lead, not a fact. |

No API key appears anywhere below. Every endpoint listed was called keyless
except Jupiter, where `chainfields` used our free key and the keyless
`lite-api.jup.ag` host returns the same data.

---

## 0. Corrections to our own repo, first

Standing rule 1. Two things in our current code are wrong, and one figure in
`CLAUDE.md` has moved.

1. ⛔ **`analysis/daily_2026-09-22/pushback/pool_probe.py:47` has a USDT mint that does not exist on chain.**
   `USDT = "Es9vMFrJKsWFsFd8e25wJdkX8DBMLoMKNfuLDQy2Ae4Z"` returns
   `{"value": null}` from `getAccountInfo`. The real Solana USDT mint is
   `Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB` (VERIFIED: Token program owner,
   6 decimals, supply 3,839,903,702), which `onchain_reserves.py:35` has right.
   Effect: in `pool_probe`, a USDT-quoted pool never matched `QUOTES`, so it was
   labelled `asset Es9vMFrz...` and priced through `asset_usd()` instead of being
   pinned at $1. The dollar figure was roughly right by accident; the label was
   wrong. **VERIFIED.**

2. ⛔ **`analysis/daily_2026-09-22/pushback/pool_probe.py:76`, the Raydium LaunchLab authority, has no account on
   chain.** `WLHv2UAZm6z4KyaaELi5pjdbJh6RESMva1Rnn8pJVVh` returns
   `{"value": null}`. The other four `AUTHORITIES` entries all exist (system
   owned, space 0). So LaunchLab vaults are never classified as
   `authority-held vault` by method A. **VERIFIED.** I did not find the correct
   LaunchLab vault authority, so replacing it is open work (UNVERIFIED as to what
   the right value is).

3. ⚠️ **`CLAUDE.md`'s DefiLlama figures have moved.** It records
   "DefiLlama Solana 24h $3.656B / 125 protocols ... BisonFi alone 12.2%".
   Today's read: **$3,428,858,821 across 125 protocol rows, BisonFi 13.03% of
   that total.** Same shape, different numbers. The direction of the finding is
   unchanged and got slightly worse. **VERIFIED.**

4. ⚠️ **A "% of chain volume" number taken against DefiLlama's chain total is
   not a venue coverage number.** DefiLlama's `/overview/dexs/solana` total mixes
   **venues** (categories `Dexs`, `Launchpad`) with **front-ends** (`Trading App`,
   `Telegram Bot`, `Interface`) whose volume is the same trades counted a second
   time: fomo Wallet $139.6M, Axiom $108.0M, GMGN $33.6M, Terminal $17.9M,
   pump.fun Mobile App $13.4M and Jupiterz $80.8M are all in the 125 rows. Any
   coverage percentage must be computed against the venue-only subtotal.
   **VERIFIED** (categories read off the same payload).

---

## 1. Volume, measured, so the plan can be ordered

Endpoint: `https://api.llama.fi/overview/dexs/{chain}?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true`
Keyless GET, no signup, 200 on all three chains. **VERIFIED.**

| chain | all-category total24h | venue-only total24h | venue rows |
|---|---|---|---|
| solana | $3,428,858,821 | **$3,294,161,378** | 76 |
| base | $1,267,668,269 | **$1,031,919,774** | 105 |
| hyperliquid | $658,961,534 | **$455,948,142** | 41 |

### 1a. Solana, what our program map covers today

Scoring `pool_probe.PROGRAMS` plus `onchain_reserves`'s fluxbeam decoder against
the venue-only subtotal: **51.7% covered ($1.702B), 48.3% blind ($1.592B).**
**VERIFIED.**

⚠️ My "known" name set also contained Serum, Aldrin and Orca Wavebreak, which are
**not** in `pool_probe.PROGRAMS`. All three report $0 of 24h volume, so they move
the figure by nothing, but the 51.7% is a name-match against DefiLlama's labels,
not a program-by-program audit. Treat it as accurate to about a percentage point.

The blind half, ordered:

| share of venue vol | 24h | venue | DefiLlama category |
|---|---|---|---|
| **13.56%** | $446,776,170 | **BisonFi** | Dexs |
| 4.84% | $159,530,747 | GoonFi | Dexs |
| 4.72% | $155,450,579 | Tessera V | Dexs |
| 4.57% | $150,643,551 | Scorch | Dexs |
| 4.14% | $136,427,143 | Manifest Trade | Dexs |
| 2.45% | $80,836,632 | Jupiterz | Dexs |
| 2.33% | $76,654,569 | QuantumAMM | Dexs |
| 1.91% | $63,025,127 | **StonkFun** | Launchpad |
| 1.72% | $56,640,304 | AlphaQ | Dexs |
| 1.50% | $49,337,606 | HumidiFi | Dexs |
| 1.38% | $45,414,317 | Deriverse | Dexs |
| 1.27% | $41,964,451 | SolFi V2 | Dexs |
| 0.96% | $31,556,938 | PancakeSwap AMM V3 | Dexs |
| 0.94% | $30,930,915 | Whalestreet | Dexs |
| 0.82% | $26,908,439 | Byreal | Dexs |
| 0.80% | $26,492,447 | Jupiter Lend DEX | Dexs |
| 0.25% | $8,220,237 | Archer Exchange | Dexs |
| 0.05% | $1,714,142 | Quay | Dexs |

Venues on our side of the line, for scale: Raydium AMM $493.5M (14.39% of the
all-category total), PumpSwap $390.1M, Orca DEX $377.1M, Meteora DLMM $259.6M,
pump.fun $122.2M, LaunchLab $26.3M, Meteora DBC $16.6M, Meteora DAMM v2 $13.5M,
Meteora DAMM v1 $2.9M. **VERIFIED.**

⚠️ Meteora DLMM's $259.6M is inside our "covered" figure by program ID only.
`onchain_reserves`'s own docstring says concentrated-liquidity pools spread
reserves across bin accounts and **will be under-read**, so treat DLMM as
recognised-but-not-measurable. That makes the honest depth-readable share lower
than 51.7%.

### 1b. Base

| share | 24h | venue |
|---|---|---|
| 46.51% | $479,940,090 | Aerodrome Slipstream |
| 16.87% | $174,090,398 | Uniswap V3 |
| 16.70% | $172,291,272 | PancakeSwap AMM V3 |
| 7.74% | $79,833,243 | Uniswap V4 |
| 4.11% | $42,386,718 | Tessera V |
| 2.71% | $27,963,061 | Metric V2 |
| 1.51% | $15,579,994 | Hanji Protocol |
| 1.25% | $12,930,723 | Aerodrome V1 |
| 0.96% | $9,937,162 | ElfomoFi |

⛔ **Clanker, Zora and Virtuals do not appear as venues in Base's DefiLlama DEX
list at all.** Their tokens trade on Uniswap v3/v4 pools, so their volume is
already inside the Uniswap rows. `BaseStonk` ($432,872) and `Umia` ($58,421) are
the only Base rows with category `Launchpad`. **VERIFIED.** Implication for a
plan: on Base, "launchpad coverage" and "venue coverage" are two separate jobs.
Four venues (Aerodrome Slipstream, Uniswap V3, PancakeSwap V3, Uniswap V4) are
**87.8%** of Base venue volume.

### 1c. Hyperliquid

| share | 24h | venue |
|---|---|---|
| **69.17%** | $315,391,484 | **Hyperliquid Spot Orderbook** (HyperCore, HIP-1) |
| 16.31% | $74,353,721 | Project X |
| 6.97% | $31,795,667 | nest CL |
| 2.66% | $12,140,943 | Ramses CL V2 |
| 1.17% | $5,312,533 | Metric V2 |
| 1.12% | $5,106,034 | LiquidCore |
| 0.76% | $3,465,134 | HyperSwap V3 |
| 0.71% | $3,217,789 | Ring Swap |
| 0.49% | $2,229,804 | Hybra V4 |
| 0.38% | $1,712,861 | Kittenswap Algebra |

⭐ **69% of Hyperliquid venue volume is one order book reachable by one free
unauthenticated HTTP POST.** Everything in section 8 below was VERIFIED in this
session. Cheapest coverage win on the board by a wide margin.

`Unit` ($180,039,349) is category `Bridge`, not a venue, and sits in the
all-category total. It is the HyperCore spot bridge for BTC/ETH/SOL. **VERIFIED.**

---

## 2. The single most useful thing I found: Jupiter publishes the map

⭐ `GET https://lite-api.jup.ag/swap/v1/program-id-to-label`
Keyless, no signup, 200, **107 entries**, program ID to human label. This is
Jupiter's own routing table, so it is exactly the set of venues that appear in
our quotes. **VERIFIED** (called it; every ID below then confirmed on chain
separately). It also names the ones `CLAUDE.md` lists as unrecognised.

⛔ **It is a label map, not a launch feed and not a pool index.** It tells you
which program a name means. It does not tell you a pool exists, or hold reserves.

---

## 3. Solana program IDs

Every row below: `getAccountInfo(<id>, {encoding: base64, dataSlice: {offset: 0,
length: 0}})` returned a live account with `executable: true` owned by
`BPFLoaderUpgradeab1e11111111111111111111111`. That is the definition of
VERIFIED here. Source of the ID is stated because "the ID is real" and "the ID
belongs to that venue" are two different claims.

### 3a. AMMs and order books we do not cover

| venue | program ID | confidence | ID source |
|---|---|---|---|
| **BisonFi** | `BiSoNHVpsVZW2F7rx2eQ59yQwKxzU5NvBcmKshCSUypi` | **VERIFIED** | Jupiter label map |
| BisonFi Predict | `2DNbzPochEcyCcWMbL4d9S3u9QqQEj5bbe6cSZFvKsbh` | **VERIFIED** | Jupiter label map |
| **GoonFi V2** | `goonuddtQRrWqqn5nFyczVKaie28f3kDkHWkHtURSLE` | **VERIFIED** | Jupiter label map |
| **Tessera V** | `TessVdML9pBGgG9yGks7o4HewRaXVAMuoVj4x83GLQH` | **VERIFIED** | Jupiter label map |
| **Scorch** | `ojh19ojaKduoJZuaJADhcVGp4xt1TcdAvZmpVsCorch` | **VERIFIED** | Jupiter label map |
| **Manifest** | `MNFSTqtC93rEfYHB6hF82sKdZpUDFWkViLByLd1k1Ms` | **VERIFIED** | Jupiter label map |
| **Quantum / QuantumAMM** | `QuaNtZsgYRe5Z9Bk4LZ4cTD9tbkVoyCNf1R2BN9bBDv` | **VERIFIED** | Jupiter label map |
| **HumidiFi** | `9H6tua7jkLhdm3w8BvgpTn5LZNU7g4ZynDmCiNN3q6Rp` | **VERIFIED** | Jupiter label map |
| **Kipseli** | `3TK9D8aoBFYjYZtKCjciPrVrRStsnvo7KmpcJqDavpaU` | **VERIFIED** | Jupiter label map |
| **Flux** | `FLUX6xBayGxLX9UcimVRxXFMHH6q43mAbRvDzSpCsvfK` | **VERIFIED** | Jupiter label map |
| **Quay** | `QUayE6nexQWYNZAEqfN8FxoNwQDSu3CAzT2qq9J1ArG` | **VERIFIED** | Jupiter label map |
| AlphaQ | `ALPHAQmeA7bjrVuccPsYPiCvsi428SNwte66Srvs4pHA` | **VERIFIED** | Jupiter label map |
| Byreal | `REALQqNEomY6cQGZJUGwywTBD2UmDT32rZcNnfxQ5N2` | **VERIFIED** | Jupiter label map |
| SolFi V2 | `SV2EYYJyRz2YhfXwXnhNAevDEui5Q6yrfyo13WtupPF` | **VERIFIED** | Jupiter label map |
| WhaleStreet | `FW6zUqn4iKRaeopwwhwsquTY6ABWLLgjxtrC3VPnaWBf` | **VERIFIED** | Jupiter label map |
| Deriverse | `DRVSpZ2YUYYKgZP8XtLhAGtT1zYSCKzeHfb4DgRnrgqD` | **VERIFIED** | Jupiter label map |

⛔ **Jupiterz ($80.8M/day) has no single program in the label map.** The map lists
`Jupiter Lend Earn`, `JupLend AMM`, `JupiterRfqV2` and `Jupiter Lend DEX`
separately. Which of those DefiLlama means by "Jupiterz" is **UNVERIFIED**.

⛔ **StonkFun ($63.0M/day, the second-biggest Launchpad on the chain after
pump.fun) has no entry in the Jupiter label map and I did not find its program
ID.** The repo already knows the venue exists: `pool_probe.asset_usd`'s docstring
records STONKBROS trading on a Raydium CPMM quoted in STONK, and Jupiter's token
feed uses `launchpad: "stonkfun"`. **UNVERIFIED** as to program ID. This is the
single biggest named gap on Solana after BisonFi.

### 3b. Launchpads we do not cover

| venue | program ID | confidence | notes |
|---|---|---|---|
| **Raydium LaunchLab** (= LetsBonk.fun) | `LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj` | **VERIFIED** | already in `pool_probe.PROGRAMS` |
| LetsBonk.fun platform config | `FfYek5vEz23cMkWsdJwG2oa6EphsvXSHrGpdALN4g6W1` | **VERIFIED** | see 5b |
| **Heaven** | `HEAVENoP2qxoeuF8Dj2oT1GHEnu49U5mJYkdeC8BAX2o` | **VERIFIED** | Jupiter label map |
| **Boop** | `boop8hVGQGqehUK2iVEMEnMrL5RbjywRzHKBmBE7ry4` | **VERIFIED** | already in `pool_probe.PROGRAMS` |
| **Moonshot** (Jupiter now calls it Moonit) | `MoonCVVNZFSYkqNXP6bxHLPL6QQJiMagDL3qcqUQTrG` | **VERIFIED** | already in `pool_probe.PROGRAMS` |
| **Meteora DBC** | `dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN` | **VERIFIED** | already in `pool_probe.PROGRAMS` |
| **Meteora DAMM v2** | `cpamdpZCGKUy5JxQXB4dcpGPiikHawvSWAd6mEn1sGG` | **VERIFIED** | already in `pool_probe.PROGRAMS` |
| Meteora DBC vault authority | `FhVo3mqL8PW5pH5U2CN4XE33DokiyZnUwuGpH2hmHLuM` | **VERIFIED** | system-owned, space 0; see 5a |
| Meteora DAMM v2 vault authority | `HLnpSz9h2S4hiLQ43rnSD9XkcUThA7B8hQMKmDaiTLcC` | **VERIFIED** | system-owned, space 0 |
| **Bags** Fee Share V2 (current) | `FEE2tBhCKAt7shrod19QttSVREUYPiyMzoku1mL1gqVK` | **VERIFIED** | docs.bags.fm/principles/program-ids |
| **Bags** Fee Share V1 (legacy) | `FEEhPbKVKnco9EXnaY3i4R5rQVUx91wgVfu8qokixywi` | **VERIFIED** | same |
| Bags address lookup table | `Eq1EVs15EAWww1YtPTtWPzJRLPJoS6VYP9oW9SbNr3yp` | **VERIFIED** | exists, owned by the ALT program, space 2424 |
| **Virtuals** (Solana) | `5U3EU2ubXtK84QcRjWVmYt9RaDyA8gKxdUrPFXmZyaki` | **VERIFIED** | Jupiter label map |
| **Believe** token authority | `5qWya6UjwWnGVhdSBL3hyZ7B45jbk6Byt1hwd7ohEGXE` | account **VERIFIED**, role **UNVERIFIED** | see 5c |
| StonkFun | none found | **UNVERIFIED** | |

⛔ **Bags has no bonding curve program of its own.** Its own docs list only
`Meteora DAMM v2` + `Meteora DBC` plus two fee-share programs. **DOCS**, and
**VERIFIED** on chain: the largest token account of a live `launchpad: "bags.fun"`
mint (`DFhzNwiCM2Vu4peicYct7rsdf8Exd7B78R6xTeCvBAGS`) is owned by
`FhVo3mqL8PW5pH5U2CN4XE33DokiyZnUwuGpH2hmHLuM`, which is the Meteora DBC vault
authority already in our map.

⛔ **The same is true of tokens Jupiter labels `launchpad: "moonshot"` today.**
A live one (`EWBg5u1dbYWEjbZEPdhMvxQeXtnytQt6JUJD1By7moon`) holds
999,801,039,398,327 raw units in an account owned by the **Meteora DBC**
authority, not by `MoonCVV...`. **VERIFIED.** So a launchpad *label* and a
launchpad *program* are different things, and keying off the label alone will
put four brands in one program and one brand in two programs.

### 3c. Repo IDs re-verified

All 17 entries in `pool_probe.PROGRAMS` resolve and are executable. **VERIFIED.**
Four of five `pool_probe.AUTHORITIES` exist; the LaunchLab one does not (see §0).

---

## 4. ⭐ The census: two completely different kinds of venue

`getProgramAccounts(<program>, {dataSlice: {offset: 0, length: 0}})`, accounts
grouped by size. One call per venue, keyless. **All VERIFIED.**

| venue | accounts | dominant size (count) | 24h volume |
|---|---|---|---|
| Raydium LaunchLab | **1,407,730** | 429 B (1,402,712), 944 B (2,602) | $26.3M |
| Moonit | **220,111** | 409 B (186,911), 337 B (33,194) | $0.25M |
| HumidiFi | **158,029** | 2,440 B (157,926) | $49.3M |
| Heaven | **50,230** | 2,304 B (50,217) | $0 |
| Boop | **49,933** | 125 B (49,931) | ~$1 |
| Virtuals Solana | **18,026** | 90 B (18,025) | $0 |
| Manifest | **4,011** | 576/336/496/224/656/736 B, many sizes | $136.4M |
| Kipseli | 207 | 9 B (201) | not listed |
| Scorch | **188** | 658 B (150), 592 B (37) | $150.6M |
| Quantum | **37** | 2,280 B (36) | $76.7M |
| GoonFi V2 | **35** | 2,048 B (33) | $159.5M |
| Tessera V | **29** | 1,264 B (27) | $155.5M |
| Quay | 22 | mixed, 22 distinct-ish | $1.7M |
| **BisonFi** | **17** | 2,048 B (17) | **$446.8M** |
| Flux | **7** | 2,080 B (7) | not listed |

⭐ **This is the finding that should shape the phasing.** The blind half of
Solana volume splits cleanly:

**Class A, proprietary market makers. There is no per-token pool and no launch.**
BisonFi turns over **$446.8M a day through 17 accounts**. GoonFi $159.5M through
35. Tessera V $155.5M through 29. Scorch $150.6M through 188. Quantum $76.7M
through 37. Flux through 7. Adding Quay (22) that is **30.07% of Solana venue
volume across roughly 300 accounts**; adding HumidiFi and Kipseli takes it to
**31.6%**. They are single-vault or few-vault market
makers that Jupiter routes into. They have no bonding curve, nothing graduates
there, and there is no "pool for token X" to look up. A "read reserves for this
venue" parser is the wrong shape for them entirely.

⚠️ What they *do* break is the reverse direction: when Jupiter fills against
BisonFi, the fill is real and our chain reader cannot see where the other side of
it came from. That is a **quote-verification** problem, not a coverage problem,
and `chainfields.round_trip()` already handles it because Jupiter prices the
route regardless of venue.

**Class B, per-token venues.** LaunchLab (1.4M pool accounts of 429 B), Moonit,
Heaven, Boop, Virtuals, and Manifest's 4,011 order-book markets. These have a
launch event, a per-token account, and something to read.

⛔ **Heaven, Boop and Virtuals-Solana are dead by volume right now.** Heaven 50,230
accounts and **$0** 24h. Boop 49,933 accounts and **~$1**. Virtuals Solana 18,026
accounts and **$0**. Moonit $252,194. Building readers for these buys almost no
volume today. **VERIFIED** (census + DefiLlama in the same window).

⛔ **Manifest is a central limit order book, not an AMM.** 4,011 accounts across
at least six distinct sizes because order slots are dynamic. $136.4M/day. Its
"depth" is an order book, so `vaults()` and the two-vault model do not apply, the
same way they do not apply to Phoenix or OpenBook. **VERIFIED** from the size
spread; the CLOB claim itself is **UNVERIFIED** beyond that inference plus the
name.

---

## 5. What a parser needs, per Solana venue

### 5a. ⭐ For reserves, we may already be done

`onchain_reserves.vaults()` is **layout independent by construction**: it fetches
the pool account, treats every 1-byte-aligned 32-byte window as a candidate
pubkey, batch-asks the chain which are SPL token accounts, and keeps those
holding the pool's own mints. Its own docstring says so.

I tested it on live pools of venues it was never written for. **All VERIFIED:**

| venue | pool tested | result |
|---|---|---|
| Meteora DAMM v2 | `A8dNMVhgTyA4fPEJnH1ZEUjXXgd7rcn8iCPbV4Wp4qtx` | `{WETZjtpr...: 5,965,338.93, USDC: 458,232.46}` |
| Meteora DBC | `E7C1ZAUJhhzDG6nJR78KUbepoMDWW3krP5Caot5TZ5JZ` | `{tDfWU6Qf...: 1,000,000,000.0, USDC: 125.15}` |
| Meteora DBC via Bags | `27NxC8YjZn2whjzH4Uo9DNbwbG8Ks6Qsw7JjhbM9QJQN` | `{...BAGS: 999,990,185.66, WSOL: 0.00294}` |
| PumpSwap | `2DVbU5h8JCd37gaXAJUZ4t77HsjJW22LLduTZk7GSa43` | `{...pump: 21,313,197.70, WSOL: 2,510.50}` |

**So the expensive part of expanding coverage is not the reserve read.** For any
Class B venue that stores its vaults as pubkeys in the pool account, reserves
come for free with two RPC calls and no new layout. What is missing is:

1. **which account is the pool** for a given mint, and
2. **which venue that pool belongs to.**

Two exceptions, both already documented in the module or found here:
- concentrated liquidity (Meteora DLMM, Raydium CLMM, Orca Whirlpool, every EVM
  v3/v4) spreads reserves across bin/tick accounts and **must be excluded, not
  reported low**;
- order books (Manifest, Phoenix, OpenBook) have no vault pair at all.

### 5b. Finding the pool: owner classification has a hole

`pool_probe`'s method A classifies a mint's token-account owners by the program
that owns the owner. ⛔ **On several launchpads the vault owner is a system-owned
PDA, so `ownerProg` is `11111111111111111111111111111111` and the venue is
invisible unless the PDA is in a hardcoded list.** VERIFIED on live mints:

- `launchpad: "bags.fun"` and `launchpad: "moonshot"` tokens: vault owner is
  `FhVo3mqL8PW5pH5U2CN4XE33DokiyZnUwuGpH2hmHLuM`, system-owned, space 0. That one
  PDA is the Meteora DBC authority and therefore covers **Bags, Moonshot-labelled
  tokens, Believe and every other DBC-based launchpad at once.** Highest leverage
  single entry available.
- LaunchLab's equivalent is the entry that does not resolve (§0).

⭐ **A LaunchLab pool state is 429 bytes and a platform config is 944 bytes**
(VERIFIED from the census: 1,402,712 at 429 B, 2,602 at 944 B).

⭐ **`FfYek5vEz23cMkWsdJwG2oa6EphsvXSHrGpdALN4g6W1` is LetsBonk.fun's platform
config and it is self-identifying.** VERIFIED: owned by
`LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj`, 944 bytes, and the raw bytes
contain the literal ASCII `letsbonk.fun` and `https://letsbonk.fun/`. So the
brand behind a LaunchLab pool is readable from chain with no third party, by
following the pool's `platform_config` field to a 944-byte account and reading
its name string. The same is presumably true of every other LaunchLab tenant
(**UNVERIFIED** for tenants other than LetsBonk).

⚠️ I attempted to locate LaunchLab's `quote_mint` offset empirically with 90
`getProgramAccounts` memcmp probes at 4-byte steps over offsets 0 to 356. Only
offset 48 matched anything, and that was one 160-byte account, not a pool. So the
offset is beyond 356, or not 4-aligned, or the probe was throttled silently.
**The offset is UNVERIFIED and, per 5a, probably not needed.**

### 5c. Believe

- Believe launches run on **Meteora DBC** and graduate to Meteora. **DOCS**
  (third-party API docs, not Believe's own), consistent with the DBC authority
  finding above.
- The address circulated as Believe's token authority,
  `5qWya6UjwWnGVhdSBL3hyZ7B45jbk6Byt1hwd7ohEGXE`, **exists** (system-owned,
  space 0) but its **role is UNVERIFIED** and came from a third-party doc, not
  from Believe.
- ⛔ **It looks dormant.** `getSignaturesForAddress` puts its most recent
  transaction at `blockTime 1785371303`, which is **54.9 days before** the chain
  time I read in the same session (1790116776). **VERIFIED.** If that address is
  really Believe's launch authority, Believe has not launched anything in nearly
  two months and belongs at the bottom of any phasing. Confirm the address role
  before acting on that.
- Believe's own token LAUNCHCOIN `Ey59PH7Z4BFU4HjyKnyMdWt5GGN76KazTAwQihoUXRnk`
  is live and is a **Token-2022** mint (owner `TokenzQdBNb...`, space 464).
  **VERIFIED.**

### 5d. Detection of a launch or graduation, per venue

| venue | how a launch is detectable | confidence |
|---|---|---|
| Meteora DBC (Bags, Believe, Moonshot-labelled, others) | new 8-byte-discriminator account under `dbcij3...`; graduation is a migrate instruction that creates a **DAMM v2** pool under `cpamd...` once the config's quote threshold is hit | program **VERIFIED**; migrate-to-DAMM-v2 semantics **DOCS** (docs.meteora.ag / MeteoraAg GitHub); exact instruction name **UNVERIFIED** |
| Raydium LaunchLab / LetsBonk | new 429-byte pool account under `LanMV9...`; tenant brand from its 944-byte platform config | sizes **VERIFIED**; brand read **VERIFIED for LetsBonk** |
| Heaven | new 2,304-byte account under `HEAVENoP...` | size **VERIFIED**; instruction names **UNVERIFIED** |
| Boop | new 125-byte account under `boop8hV...` | size **VERIFIED**; 125 B is too small to be a curve, so the curve state lives elsewhere. **UNVERIFIED** where |
| Moonit / Moonshot | new 409-byte (or 337-byte) account under `MoonCVV...` | sizes **VERIFIED** |
| Virtuals Solana | new 90-byte account under `5U3EU2ub...` | size **VERIFIED** |
| Manifest | new market account under `MNFST...`, sizes vary | **VERIFIED** that sizes vary |
| BisonFi, GoonFi, Tessera V, Scorch, Quantum, Flux, Quay, Kipseli, HumidiFi | **nothing launches here.** ~300 accounts total across the first seven. Nothing to detect | **VERIFIED** by census |

⛔ **The generic mechanism that needs no per-venue work already exists in
`CLAUDE.md`'s settled conclusions:** `programSubscribe` on the AMM programs, and
mcap computed from reserves on each account update. Adding a venue to that list
is adding one program ID, not writing a decoder. The costing in
`docs/TRACKER_SCOPING.md` §5c (56 notifications/sec, 31 KB/s, 20 credits/MB,
Developer $49/mo at 16% utilisation) was measured on pump.fun alone, so **adding
venues re-opens that budget and it has not been re-measured here.**

---

## 6. Base

Verified with `eth_getCode` on `https://mainnet.base.org` (keyless,
`eth_chainId` = `0x2105`, block 51,663,867 at the time of the call).

| contract | address | bytes | confidence |
|---|---|---|---|
| **Clanker v4.0.0** (factory) | `0xE85A59c628F7d27878ACeB4bf3b35733630083a9` | 12,375 | **VERIFIED**, name from Clanker docs |
| Clanker v4.1 HookDynamicFeeV2 | `0xd60D6B218116cFd801E28F78d011a203D2b068Cc` | 20,230 | **VERIFIED** |
| Clanker v4.1 HookStaticFeeV2 | `0xb429d62f8f3bFFb98CdB9569533eA23bF0Ba28CC` | 16,405 | **VERIFIED** |
| Clanker v4 LpLockerFeeConversion | `0x63D2DfEA64b3433F4071A98665bcD7Ca14d93496` | 24,529 | **VERIFIED** |
| Clanker v3.1 factory | `0x2A787b2362021cC3eEa3C24C4748a6cD5B687382` | 17,351 | **VERIFIED** exists; v3.1 attribution **UNVERIFIED** (not on the docs page I read) |
| **Zora ZoraFactory** (coins) | `0x777777751622c0d3258f214F9DF38E35BF45baF3` | **130** | **VERIFIED**; label from docs.zora.co |
| **VIRTUAL token** | `0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b` | 14,849 | **VERIFIED**, address from whitepaper.virtuals.io |
| **Virtuals bonding curve** | `0x1A540088125d00dD3990f9dA45CA0859af4d3B01` | not checked | **DOCS** only (whitepaper.virtuals.io). ⛔ I did not `eth_getCode` this one |
| Uniswap V2 factory | `0x8909Dc15e40173Ff4699343b6eB8132c65e18eC6` | 13,859 | **VERIFIED** |
| Uniswap V3 factory | `0x33128a8fC17869897dcE68Ed026d694621f6FDfD` | 24,535 | **VERIFIED** |
| Uniswap V4 PoolManager | `0x498581fF718922c3f8e6A244956aF099B2652b2b` | 24,009 | **VERIFIED** |
| Uniswap V4 StateView | `0xA3c0c9b65baD0b08107Aa264b0f3dB444b867A71` | 3,531 | **VERIFIED** |
| Aerodrome PoolFactory (v1) | `0x420DD381b31aEf6683db6B902084cB0FFECe40Da` | 3,516 | **VERIFIED** |
| Aerodrome Slipstream CLFactory | `0x5e7BB104d84c7CB9B682AaC2F3d509f5F406809A` | 4,958 | **VERIFIED** |
| WETH | `0x4200000000000000000000000000000000000006` | 2,041 | **VERIFIED** |
| USDC | `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913` | 1,852 | **VERIFIED** |

⚠️ **The Zora factory is 130 bytes of code.** That is a proxy, not an
implementation, which matches its docs describing an upgradeable canonical
factory. A parser must read events from the proxy address and must not assume the
ABI is stable across upgrades.

### What a Base parser needs

- **Launch detection:** watch `eth_getLogs` on the factory addresses above.
  Clanker and Zora both deploy the token **and** its Uniswap pool in the creation
  call, so one factory log gives mint plus pool plus creator. **DOCS**
  (both docs pages describe this); the exact event topic0 values are
  **UNVERIFIED**, I did not read an ABI.
- **Reserves, Uniswap v2 shape (Aerodrome v1, Uniswap v2, PancakeSwap v2):**
  `getReserves()` selector `0x0902f1ac` returns reserve0, reserve1,
  blockTimestampLast in one `eth_call`. Plus `token0()` `0x0dfe1681` and
  `token1()` `0xd21220a7`. **VERIFIED** (called all three on Ethereum and on
  HyperEVM pools in this session).
- **Reserves, v3 shape (Uniswap v3, PancakeSwap v3, Aerodrome Slipstream):**
  `slot0()` `0x3850c7bd` for sqrtPriceX96 and tick, `liquidity()` `0x1a686502`
  for in-range liquidity. **VERIFIED** (called both). ⛔ **`liquidity()` is
  in-range liquidity only.** Exitable depth for a $100 sell needs tick/bitmap
  walking or a quoter. Reporting `liquidity()` as depth is exactly the 781x class
  of error, in EVM form.
- **Reserves, v4:** there are no pool contracts. One singleton `PoolManager`
  holds every pool keyed by poolId, read via `StateView` (`getSlot0`,
  `getLiquidity`) or raw `extsload`. **DOCS**; both addresses **VERIFIED** to
  have code on Base and Ethereum.
- ⛔ **`onchain_reserves.vaults()` does not port to EVM at all.** Its whole trick
  is that Solana pools reference separate SPL token accounts. EVM pools hold
  balances inside the pool contract's own ERC-20 balances, so the equivalent is
  `balanceOf(pool)` on each of token0/token1 for v2, and nothing so simple for
  v3/v4.

---

## 7. Ethereum, the generic reader

Verified with `eth_getCode` on `https://eth.drpc.org` (keyless).

| contract | address | bytes | confidence |
|---|---|---|---|
| Uniswap V2 factory | `0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f` | 13,859 | **VERIFIED** |
| Uniswap V3 factory | `0x1F98431c8aD98523631AE4a59f267346ea31F984` | 24,535 | **VERIFIED** |
| Uniswap V4 PoolManager | `0x000000000004444c5dc75cB358380D2e3dE08A90` | 24,009 | **VERIFIED** |
| Uniswap V4 StateView | `0x7fFE42C4a5DEeA5b0feC41C94C136Cf115597227` | 3,531 | **VERIFIED** |
| WETH | `0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2` | 3,124 | **VERIFIED** |
| USDC | `0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48` | 2,186 | **VERIFIED** |

Live reads proven on USDC/WETH, all **VERIFIED**:
- v2 pair `0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc`, `getReserves()` returned
  reserves in one call.
- v3 pool `0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640`, `slot0()` and
  `liquidity()` both returned (`liquidity()` = `0x29b24d09dce7e4fc`).

A generic ERC-20 plus Uniswap reader needs, minimally:
`decimals()` `0x313ce567`, `symbol()` `0x95d89b41`, `totalSupply()` `0x18160ddd`,
`balanceOf(address)` `0x70a08231`, plus `token0`/`token1`/`getReserves` for v2 and
`slot0`/`liquidity` for v3, and `StateView` for v4. All selectors above were
exercised in this session except `balanceOf`.

⚠️ **Public Ethereum RPC is the weak link, not the parsing.** Of eight public
endpoints tried: `eth.drpc.org`, `1rpc.io/eth`, `eth-mainnet.public.blastapi.io`
and `rpc.flashbots.net` all returned real WETH bytecode. `eth.merkle.io` returned
429. `rpc.mevblocker.io` and `ethereum-rpc.publicnode.com` failed TLS from this
host (`SSL: WRONG_VERSION_NUMBER`). `api.securerpc.com` and `rpc.payload.de`
failed DNS. ⛔ **And `cloudflare-eth.com` is the dangerous one: it answers
`eth_chainId` with `0x1` and then returns `"0x"` for `eth_getCode` on WETH and
`Internal error` on every `eth_call`.** A reader pointed at it would conclude that
Uniswap does not exist. **VERIFIED, all of it.** Same family as standing rule 16:
the call came back, so it looked fine. Any EVM reader needs multi-endpoint
fallback with a positive liveness assertion, not a `chainId` check.

We already hold an `ALCHEMY_API_KEY` and an `ETHERSCAN_API_KEY` per `CLAUDE.md`,
so keyless is a preference here, not a constraint.

---

## 8. ⭐ Hyperliquid. Frank holds HYPE and PURR and this is all free

Every request below is `POST https://api.hyperliquid.xyz/info` with
`Content-Type: application/json` and **no authentication of any kind**. Every one
returned 200 in this session. **ALL VERIFIED.**

No wallet was connected, nothing was signed, no order endpoint was touched.

### 8a. Request types, what they return

| `type` | returned | measured |
|---|---|---|
| `spotMeta` | `{universe, tokens}`. **503 tokens, 330 pairs.** Each token: `name`, `szDecimals`, `weiDecimals`, `index`, `tokenId` (a 32-hex id), `isCanonical`, `evmContract`, `fullName`, `deployerTradingFeeShare`. Each pair: `tokens: [base, quote]`, `name`, `index`, `isCanonical` | 149,248 bytes |
| `spotMetaAndAssetCtxs` | `[spotMeta, ctxs]`, **869 contexts**. Each: `coin`, `midPx`, `markPx`, `prevDayPx`, `dayNtlVlm` (USD notional 24h), `dayBaseVlm`, `circulatingSupply`, `totalSupply` | 324,988 bytes |
| `allMids` | every mid price keyed by coin | 21,413 bytes |
| `l2Book` (`coin`) | `{coin, time, levels: [bids, asks]}`, each level `{px, sz, n}`, **20 levels per side** | ~1,700 bytes |
| `tokenDetails` (`tokenId`) | `name`, `maxSupply`, `totalSupply`, `circulatingSupply`, `szDecimals`, `weiDecimals`, `midPx`, `markPx`, `prevDayPx`, `deployer`, `deployGas`, `deployTime`, `seededUsdc`, `nonCirculatingUserBalances`, `futureEmissions`, `genesis` | PURR 499 B, ⛔ **HYPE 5,391,801 B** |
| `candleSnapshot` (`{coin, interval, startTime}`) | OHLCV bars: `t`, `T`, `s`, `i`, `o`, `c`, `h`, `l`, `v`, `n` | 766,747 B for `@107` 1h |
| `metaAndAssetCtxs` | perps universe and contexts | 79,657 bytes |
| `validatorSummaries` | **staking side.** Per validator: `validator`, `signer`, `name`, `description`, `stake`, `commission`, `isJailed`, `isActive`, `nRecentBlocks`, and `stats` for day/week/month with `uptimeFraction`, `predictedApr`, `nSamples` | 24,850 bytes |
| `delegations` (`user`) | that wallet's delegations, `[]` for the zero address | |
| `delegatorSummary` (`user`) | `{delegated, undelegated, totalPendingWithdrawal, nPendingWithdrawals}` | |
| `spotClearinghouseState` (`user`) | `balances: [{coin, token, total, hold, entryNtl}]` | |
| `spotDeployState` (`user`) | `{states, gasAuction: {startTimeSeconds, durationSeconds, startGas, currentGas, endGas}}`. The HIP-1 ticker auction | |
| `perpDexs` | builder-deployed perp DEXes. First entry `null`, then e.g. `xyz` with a `deployer` and per-asset OI caps | 22,108 bytes |
| `exchangeStatus` | `{specialStatuses, time}`. Cheap liveness ping | 48 bytes |

### 8b. Values read for Frank's two holdings

**VERIFIED**, from `spotMetaAndAssetCtxs` and `l2Book` in the same minute:

- **HYPE.** Token index **150**, `tokenId` `0x0d01dc56dcaaca66ad901c959b4011ec`,
  `szDecimals` 2, `weiDecimals` 8, `fullName` "Hyperliquid", `isCanonical` false,
  ⛔ **`evmContract: null`**. Its spot pair is index **107**, so its book coin is
  the string **`@107`**, not `"HYPE"`.
  `midPx` 97.1645, `markPx` 97.165, `prevDayPx` 93.3 (**+4.1% on the day**),
  `dayNtlVlm` **$106,812,098**, `dayBaseVlm` 1,123,644.64 HYPE,
  `circulatingSupply` 298,772,932.14, `totalSupply` 998,916,869.16,
  `maxSupply` 1,000,000,000.
  Book: best bid 97.164 x 51.74, best ask 97.165 x 51.46. **Spread is 0.001, one
  tick, about 1.0 bp**, and roughly 5,000 USD sits on each side at the touch.
- **PURR.** Token index **1**, `tokenId` `0xc1fb593aeffbeb02f85e0308e9956a90`,
  `szDecimals` 0, `weiDecimals` 5, `isCanonical` **true**, `evmContract.address`
  `0x9b498c3c8a0b8cd8ba1d9851d40d186f1872b44e` with
  `evm_extra_wei_decimals: 13`. Its pair is the only named one,
  **`PURR/USDC`**, index 0.
  `midPx` 0.147345, `markPx` 0.14756, `prevDayPx` 0.12438 (**+18.5% on the day**,
  mid against prevDayPx),
  `dayNtlVlm` **$3,291,251**, `dayBaseVlm` 24,846,720 PURR,
  `circulatingSupply` 594,870,623.98, `totalSupply` 594,870,634.35.
  `tokenDetails` adds `genesis: null`, `deployer: null`, `futureEmissions: "0.0"`,
  and `nonCirculatingUserBalances` of 6.52278 at the zero address and 3.85374 at
  `0x...dead`.

⭐ **Two naming traps a parser must handle, both VERIFIED.**
(1) A spot pair's `name` is `"@<index>"` for everything except PURR/USDC. To go
from ticker to book you must resolve ticker to token index via `spotMeta.tokens`,
then find the `universe` entry whose `tokens[0]` is that index, then use
`"@" + str(entry.index)`. HYPE is token 150 but pair 107. Keying on the ticker
string fails.
(2) `tokenId` is the stable identity, not the name. This is the Hyperliquid form
of our own standing rule 2, and HIP-1 tickers are auctioned, so name collisions
are a design feature of the chain rather than an attack.

⛔ **`tokenDetails` on HYPE returned 5.39 MB** because `genesis.userBalances`
enumerates every genesis recipient. PURR's was 499 bytes. Never call
`tokenDetails` on a hot path without a size guard.

⛔⛔ **A third trap, and it is the one that would silently mislabel every price.
`spotMetaAndAssetCtxs` does NOT return one context per universe entry.** Measured
in one call: `universe` has **330** entries, `ctxs` has **869**, and
`ctxs[i].coin == universe[i].name` is **False**. The first entries do line up
(`PURR/USDC`, `@1`, `@2`, ...) but the tail does not: the last five contexts are
`#41061`, `#41070`, `#41071`, `@867`, `@868` while the last three universe names
are `@720`, `@867`, `@868`. So the array carries markets that are not in the spot
universe at all, interleaved. **Contexts must be keyed by their own `coin` string,
never by array index.** Indexing by position would attach one token's price to
another token's name, chain-wide, and nothing would error. **VERIFIED.**

⚠️ **`allMids` keys are not tickers either.** 1,103 keys in one call, and of the
first 400 not one is a plain symbol: PURR is keyed `PURR/USDC`, HYPE is `@107`,
and many are `#`-prefixed numeric ids. A re-read a few minutes after the numbers
above gave PURR 0.150235 and `@107` 97.4025, which is also a reminder that these
are live mids and any quoted figure needs its timestamp. **VERIFIED.**

### 8c. Rate limits

**DOCS** (hyperliquid.gitbook.io, rate-limits-and-user-limits): REST shares an
aggregated **1,200 weight per minute per IP**. Weight **2** for `l2Book`,
`allMids`, `clearinghouseState`, `orderStatus`, `spotClearinghouseState`,
`exchangeStatus`. Weight **20** for all other documented `info` requests.

So, arithmetically: ~600 `l2Book` calls/min, or ~60 `spotMetaAndAssetCtxs`
calls/min. One `spotMetaAndAssetCtxs` already carries mid, mark, prev-day and 24h
notional for **all 869 markets**, so a full-chain snapshot costs weight 20 and one
round trip. That is ~1.7% of the minute budget for complete spot coverage.
⚠️ The docs page I read does not state whether info requests need auth. They do
not: every call in this session was unauthenticated. **VERIFIED** by doing it.

### 8d. HyperEVM

`POST https://rpc.hyperliquid.xyz/evm`, keyless JSON-RPC. **All VERIFIED:**
`eth_chainId` = `0x3e7` = **999**, `net_version` = `"999"`, `eth_blockNumber` =
`0x2c76fa5` = 46,624,677, `eth_gasPrice` = `0x5f5e100` = 0.1 gwei,
`eth_getBlockByNumber` and `eth_call` both work.

| token | address | confirmed from chain |
|---|---|---|
| **WHYPE** (wrapped HYPE) | `0x5555555555555555555555555555555555555555` | `symbol()` returns `WHYPE`, `decimals()` 18, `totalSupply()` `0x2c4446cc07c9874f6fac9`. **VERIFIED** |
| **PURR** ERC-20 | `0x9b498c3c8a0b8cd8ba1d9851d40d186f1872b44e` | `symbol()` returns `PURR`, `decimals()` 18. **VERIFIED**, and it matches `spotMeta`'s `evmContract` for PURR |
| USDC `evmContract` from `spotMeta` | `0x6b9e773128f453f5c2c60935ee2de2cbc5390a24` | ⛔ `symbol()`, `decimals()` and `totalSupply()` all **revert**. **VERIFIED** that it is not a normal ERC-20. Spot USDC lives on HyperCore |

⚠️ **HYPE itself has no ERC-20.** `spotMeta` gives `evmContract: null` for HYPE.
It is HyperEVM's native gas token, and `0x5555...5555` is the wrapper. So a HYPE
balance can sit in three places (HyperCore spot, HyperEVM native, HyperEVM WHYPE)
and a single-source read will understate it. **VERIFIED.**

⭐ **HyperEVM AMM factories, discovered from chain, not from a blog.** Method:
take live pairs off Dexscreener's keyless `/latest/dex/search?q=WHYPE`
(`chainId == "hyperevm"`), then ask each pool contract for its own `factory()`
(`0xc45a0155`). The factory address is then a chain fact, not a claim.
**All VERIFIED.**

| dexId | factory | a pool of it | 24h vol of that pool |
|---|---|---|---|
| **prjx** (Project X, 16.3% of HL venue vol) | `0xff7b3e8c00e57ea31477c32a5b52a58eea47b072` | `0xaa37FF279d9e06639368ba6Aac309e9BD4512469` | $285 |
| **nest** | `0xf77bd082c627aa54591cf2f2eaa811fd1ab3b1f3` | `0x535F30F50eBDa33575242C38B976E681D13db6Fa` | $178,738 |
| nest (second factory) | `0x889fd0ada8453c7619cd7f11e9029a1f0848fdf5` | `0x9AA281B23341cE69d4b1500367a43CFc42005538` | $13,021 |
| **hyperswap** | `0xb1c0fa0b789320044a6f623cfe5ebda9562602e3` | `0x5dea7B0545aadC4561cb418976fB6Fa8AEcd38ea` | $51,058 |
| hyperswap (second factory) | `0x724412c00059bf7d6ee7d4a1d0d5cd4de3ea1c48` | `0x5a77b0D96Ad87DEfee407ED5244C942Ff7Fc5779` | $137,358 |
| **ramses** | `0x07e60782535752be279929e2dffdd136db2e6b45` | `0x54175D986b00292B669B9AefA0a466d12B8215D6` | $70,490 |
| ramses (second factory) | `0xd0a07e160511c40ccd5340e94660e9c9c01b0d27` | `0xa33601b7811dC089CAfEB7C7B97fC4c8271899b2` | $19,915 |
| **kittenswap** | `0x5f95e92c338e6453111fc55ee66d4aafcce661a7` | `0x71d1FDE797e1810711E4C9abcFcA6Ef04C266196` | $4,583 |
| kittenswap (second factory) | `0x2e08f5ff603e4343864b14599caedb19918bdcaf` | `0x11f6Ad647c331Bcf927ea9df6BD0F777E0E25FEC` | $57 |
| **hybra-finance** | `0x32b9da73215255d50d84feb51540b75acc1324c2` | `0x006418DcD73f6Da03A667ad161cCB9B39CeEEa60` | $5,152 |
| unlabelled | `0x160bc7667a12bfb0215be3dda07f3a9fac8c7296` | `0xf86021eEcFf551Fe0dA109a5a467174be8152f58` | $8 |

⚠️ **Each brand has at least two factories** (a v2-shape and a
concentrated-liquidity shape), so one address per brand is not enough. And one
sampled pool `0x3C1F6D843aF17d0d87c6924b633cB500047B67bF` answered neither
`factory()` nor `owner()`, with $165,074 of claimed liquidity. **VERIFIED.**
Dexscreener labelled it `unknown`. That is a venue neither we nor Dexscreener can
name, which is the HyperEVM version of the STONKBROS problem already documented in
`pool_probe`.

⚠️ **Kittenswap is Algebra Integral, not a Uniswap v3 clone** (DefiLlama names it
"Kittenswap Algebra"; its docs say Algebra). **DOCS.** So its pool ABI differs
from v3 and `slot0()` may not apply.

### 8e. What a Hyperliquid parser needs

- **HyperCore spot, 69% of the volume.** No chain reader at all. Three POSTs:
  `spotMeta` for identity, `spotMetaAndAssetCtxs` for price and 24h volume across
  all 869 markets, `l2Book` per coin for real depth. ⭐ **And the depth is a real
  order book, so a $100 exit is priced by walking levels, not modelled off a
  reserve ratio.** This is a strictly better liquidity primitive than anything we
  have on Solana: no 781x overstatement is possible because the levels are the
  resting orders.
- **New HIP-1 listings.** Diff `spotMeta.tokens` between polls. `spotDeployState`
  exposes the ticker gas auction (`startGas` 500.0, `endGas` 500.0,
  `durationSeconds` 111,600 at the time of the call). **VERIFIED.**
- **Staking.** `validatorSummaries` for the validator set with per-period
  `predictedApr` and `uptimeFraction`; `delegations` and `delegatorSummary` per
  wallet. All keyless. ⛔ **These need Frank's wallet address, which is his to
  give. Do not guess it and never connect a wallet.**
- **HyperEVM.** Standard EVM tooling against `rpc.hyperliquid.xyz/evm`, plus the
  factory list above, plus the HyperCore linkage: `spotMeta`'s `evmContract` and
  `evm_extra_wei_decimals` is the only mapping between a HIP-1 token and its
  ERC-20, and ⛔ **`evm_extra_wei_decimals` can be negative** (USDC is `-2`) **or
  large positive** (PURR is `+13`). Ignoring it puts a balance off by 10^13.
  **VERIFIED.**
- ⛔ **Frank's holdings are on the 69% side, not the AMM side.** HYPE's
  $106.8M/day and PURR's $3.29M/day are HyperCore spot book volume. HyperEVM AMMs
  are the remaining 31% and none of the pools sampled had more than $1.14M of
  claimed liquidity.

---

## 9. Free public APIs, confirmed by calling them

| endpoint | keyless | what it gives | confidence |
|---|---|---|---|
| `api.llama.fi/overview/dexs/{solana,base,hyperliquid}` | yes | per-venue 24h volume and category | **VERIFIED** |
| `lite-api.jup.ag/swap/v1/program-id-to-label` | yes | 107 Solana program IDs to venue names | **VERIFIED** |
| ⭐ `lite-api.jup.ag/tokens/v2/recent` | yes | see §10 | **VERIFIED** |
| `lite-api.jup.ag/tokens/v2/toptraded/24h?limit=N` | yes | same schema, ranked by volume | **VERIFIED** |
| `lite-api.jup.ag/tokens/v2/toporganicscore/24h?limit=N` | yes | same schema | **VERIFIED** |
| `lite-api.jup.ag/tokens/v2/tag?query=lst` | yes | same schema, 165 rows | **VERIFIED** |
| `lite-api.jup.ag/price/v3?ids=<mint>` | yes | USD price for any mint | **VERIFIED** (used in `pool_probe`) |
| `api.dexscreener.com/latest/dex/search?q=<q>` | yes | pairs with `chainId`, `dexId`, `pairAddress`. Works for `hyperevm` | **VERIFIED** |
| `api.geckoterminal.com/api/v2/networks` | yes | ⭐ **both `hyperevm` and `hyperliquid` exist as networks** | **VERIFIED** |
| `api.geckoterminal.com/api/v2/networks/solana/dexes` | yes | 33 dexIds incl. `heaven`, `humidifi`, `manifest`, `moonit`, `bags-fm`, `virtuals-solana`, `clanker-solana`, `zora`, `meteora-dbc`, `meteora-damm-v2`, `raydium-launchlab`, `printr-v2`, `token-mill`, `wavebreak`, `easya-kickstart`, `metadao`, `daos-fun` | **VERIFIED** |
| `api.geckoterminal.com/api/v2/networks/base/dexes` | yes | 105 dexIds incl. `virtuals-base`, `virtuals-unicorn-base`, `uniswap-v4-base`, `aerodrome-slipstream` | **VERIFIED** |
| `api.hyperliquid.xyz/info` | yes | §8 | **VERIFIED** |
| `rpc.hyperliquid.xyz/evm` | yes | HyperEVM JSON-RPC, chain 999 | **VERIFIED** |
| `mainnet.base.org` | yes | Base JSON-RPC, chain 8453 | **VERIFIED** |
| `eth.drpc.org`, `1rpc.io/eth`, `eth-mainnet.public.blastapi.io`, `rpc.flashbots.net` | yes | Ethereum JSON-RPC | **VERIFIED** |
| ⛔ `cloudflare-eth.com` | yes | **lies silently.** See §7 | **VERIFIED broken** |

⛔ **GeckoTerminal's free tier rate-limits hard.** I hit
`429 You've exceeded the Rate Limit` after roughly 6 calls in quick succession,
mid-script. The published free ceiling is 30 calls/min. Any plan that leans on it
must pace, and ⛔ a 429 must never be allowed to render as "no pools".

⚠️ **GeckoTerminal `new_pools` caps at page 10** per `CLAUDE.md`, so it cannot be
the launch feed for these venues either.

---

## 10. ⭐ Jupiter's `/tokens/v2/recent` is a cross-launchpad launch feed, and I measured its cadence

`GET https://lite-api.jup.ag/tokens/v2/recent`, keyless, 200, **30 rows**, ~0.7s.
**VERIFIED.**

Per row: `id` (the mint), `symbol`, `name`, **`launchpad`**, `metaLaunchpad`,
`dev`, `createdAt`, `firstPool: {id, createdAt}`, `holderCount`, `liquidity`,
`mcap`, `fdv`, `usdPrice`, `circSupply`, `totalSupply`, `decimals`,
`tokenProgram`, `organicScore`, `organicScoreLabel`, `stats5m`/`1h`/`6h`/`24h`,
`twitter`, `website`, `tags`, `partnerConfig`, and
**`audit: {mintAuthorityDisabled, freezeAuthorityDisabled, devBalancePercentage, devMints, devMigrations, topHoldersPercentage}`**.

⭐ That single free call carries the mint, the launchpad, the creation time, the
dev wallet, the holder count, and **both authority flags**, which is most of what
`safety.py` and the v3 gate ask for, for every launchpad at once.

### Cadence, per standing rule 13

Seven passes, 25s apart, 2026-09-22 22:52 to 22:56 UTC. **VERIFIED.**

| pass | oldest row | newest row | span of the 30 rows | cumulative distinct |
|---|---|---|---|---|
| 0 | 22:52:11Z | 22:53:08Z | 57s | 30 |
| 1 | 22:52:44Z | 22:53:36Z | 52s | 44 |
| 2 | 22:53:22Z | 22:54:05Z | 43s | 64 |
| 3 | 22:53:43Z | 22:54:31Z | 48s | 80 |
| 4 | 22:54:06Z | 22:54:52Z | 46s | 95 |
| 5 | 22:54:42Z | 22:55:18Z | 36s | 119 |
| 6 | 22:55:01Z | 22:55:48Z | 47s | **136** |

**Median span of 30 rows: 47 seconds. Implied launch rate ~38/min, and 136
distinct mints over the 217-second window is 37.6/min, which agrees.**

⭐ **So a 30-second poll of a 30-row feed cannot miss a launch, and a 60-second
poll starts dropping them.** That is the sampling-interval statement rule 13
demands, stated before any duration is quoted off this feed. It also means
~2,300 launches/hour chain-wide, against the ~45 pump.fun graduations/hour in
`data/graduations/`.

⚠️ **The window is 217 seconds long, at one time of day.** Memecoin activity is
bursty (standing rule 14), so 38/min is one observation, not a rate. The poll
interval a plan commits to must be derived from the worst observed span, not the
median, and should be re-measured across a full day before it is trusted.

### Launchpad vocabulary observed

Across 210 rows in those 7 passes: `pump.fun` 148, `stonkfun` 44, `met-dbc` 6,
none 5, `raydium-launchlab` 3, `moonshot` 2, `ember` 1, `bags.fun` 1. Across the
other three endpoints I also saw `letsbonk.fun` and `metadao`. **VERIFIED.**

⛔ **`stonkfun` is 21% of launches in this sample and we have no program ID for
it.** That, plus its $63.0M/day, makes StonkFun the biggest single unknown on the
launch side.

⛔ **The `launchpad` string is a brand, not a program**, per §3b: `bags.fun` and
`moonshot` tokens both sit on Meteora DBC. A plan must not treat the label as the
venue key. Our own standing rule 2 applies unchanged: key on the address.

⚠️ **This is an AGGREGATE dependency in the sense of standing rule 17**, not a
REBUILD. It is Jupiter's view of what launched, it can be wrong or incomplete, it
is not authenticated, and nothing should depend on it. The REBUILD version is
`programSubscribe` on the program IDs in §3.

---

## 11. Open questions, honestly labelled

1. **StonkFun's program ID.** UNVERIFIED. $63.0M/day and 21% of launches in the
   sample. Biggest single gap.
2. **Jupiterz.** $80.8M/day, no single program ID identified. UNVERIFIED.
3. **The correct Raydium LaunchLab vault authority.** Ours does not exist and I
   did not find the right one. UNVERIFIED.
4. **Believe's real authority and whether it is alive.** The circulated address
   exists but has been quiet 54.9 days. Role UNVERIFIED.
5. **Exact instruction and event names** for DBC migration, Heaven, Boop,
   Moonit, LaunchLab. I verified program IDs and account sizes, not instruction
   discriminators. UNVERIFIED.
6. **Clanker and Zora factory event topics.** I verified the contracts have code
   and read the docs pages, but did not read an ABI. UNVERIFIED.
7. **Virtuals Base bonding curve `0x1A540088125d00dD3990f9dA45CA0859af4d3B01`.**
   DOCS only. I did not `eth_getCode` it.
8. **What Boop's 125-byte account is.** Too small for a curve. UNVERIFIED.
9. **Whether `onchain_reserves.vaults()` works on LaunchLab, Heaven, Boop,
   Moonit and Virtuals pools.** Proven on Meteora DAMM v2, Meteora DBC and
   PumpSwap. Not yet proven on the other five, because finding one of their pools
   needs the authority PDA that §0 says we have wrong.
10. **`programSubscribe` credit cost with more venues.** The $49/mo Developer
    sizing in `docs/TRACKER_SCOPING.md` §5c was measured on pump.fun alone.
    Adding BisonFi-class programs is cheap (they have ~300 accounts) but adding
    LaunchLab, Moonit, HumidiFi and Heaven means subscribing to programs with
    1.4M, 220k, 158k and 50k accounts. Not re-measured. UNVERIFIED.
11. **HyperCore order-book depth versus a realizable exit.** The book is levels
    of resting orders, which is a better primitive than a reserve ratio, but I
    did not check whether walking 20 levels is enough for a $100 or $500 exit on
    a thin HIP-1 token, nor whether `l2Book` can return more than 20 levels.
    UNVERIFIED.
