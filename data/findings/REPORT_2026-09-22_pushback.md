# Frank's pushback, answered from chain. 2026-09-22

Every number below comes from a call made today. Chain reads are Helius RPC
(`getTokenAccounts`, `getMultipleAccounts`, `getProgramAccounts`,
`getTransaction`, `getSignaturesForAddress`). Jupiter, Dexscreener,
GeckoTerminal, RugCheck and DefiLlama are labelled where used. Scripts:
`analysis/daily_2026-09-22/pushback/`.

**Frank is right on the two things he pushed hardest on.** He is 4 for 4 now.

---

⛔⛔ **RETRACTED IN PART, 2026-09-23. READ THIS FIRST.**
**Everything below about EMBER is about the wrong contract.** It analysed
`FLCr9vGMTkbDcRCoirP5Hx8gB7TW1Azt3pkw3qp2HTsh`, which is a **phantom**: 3 pairs,
**$1.39** of liquidity summed across all of them, $1.31 **billion** of claimed cap,
first pool 09-21 10:55Z. The EMBER Gorilla named on 09-10 is
`5dvXTZ5qwgafnHtwu3Ls3QrWx1U4LQsFeCuJgkk4QEC6`: **30 pairs, $2,331,895 of
liquidity, $17.9M cap, both authorities revoked, and a $2,000 sell costs 1.30%.**
⭐ **Frank said EMBER was at $17.2M and alive. He was right.** The pool reads, the
timestamps and the `Withdraw` trace below are all correct — about the phantom. What
is retracted is the identification, and with it every EMBER conclusion here.
Record: `data/findings/RETRACTION_2026-09-22_ember.md`.
⛔ **Corrections 2 and 3, the `gone` audit, the curve-vs-label finding and the
venue-blindness figures are unaffected** and still stand.

---

## ⛔ RETRACTED — Correction 1: EMBER was not dead this morning. It was rugged at 11:09:37Z.

`FLCr9vGMTkbDcRCoirP5Hx8gB7TW1Azt3pkw3qp2HTsh`, PumpSwap pool
`AVW2pYeHAWUgSGaz1F46pGVXVZ8d4DWerDfpa3NKWS43`.

Vault balances read from chain, sampled across the pool's whole life:

| time | SOL in the pool | EMBER in the pool |
|---|---|---|
| 09-21 10:55:29Z (pool created) | 1,055.0 | 17.07B |
| 09-21 17:18:01Z | 2,515.2 | 8.91B |
| 09-22 00:54:02Z (peak) | 3,585.8 | 3.82B |
| 09-22 10:36:32Z | 2,689.8 | 475M |
| **09-22 11:09:37Z** | **0.0** | **0.003** |

At 10:36 this morning that pool held **2,690 SOL, about $317,000**. The
transaction at **09-22 11:09:37Z** is a PumpSwap `Withdraw` signed by the pool
creator `HoX8uwcQiEmzF3qEzMznkqDG9PR4qa48ugHdf29vinsz`, taking **2,907.565 SOL
(about $343,000)** and 454M EMBER, then burning the LP tokens. Our 24h outcome
check ran at **11:12:10Z, 2 minutes 33 seconds later**, and my re-check for the
morning report ran around 11:45Z. I reported the corpse and called it a coin
that "did not last a day".

⭐ **Our $292k depth figure was right.** We recorded $291,723 of quote-side
depth at 17:11:30Z on 09-21; chain shows 2,515.2 SOL in the vault at 17:18:01Z,
about $292k at that day's SOL price. The 3.97x was real and stayed realizable
for roughly 18 more hours.

⛔ **What was wrong was the framing and one number.** "All three pools hold
$2.64" was a Dexscreener figure. On chain the token has **5 pool accounts
across 3 venues** (PumpSwap, two Meteora DAMM v2, a Meteora DBC curve) holding
**$20.36** of quote side in total.

**Is it dead now? Yes.** Jupiter's $100 round trip returns **$0.32**
(TOTAL_LOSS), 109 holders on chain, mint and freeze authority both revoked.
EMBER died at a timestamp, by a person, not by never having been real. It is
also **not a pump.fun token**: Jupiter reports launchpad `met-dbc` (Meteora
DBC), graduated 09-21 10:55:09Z, which is the same minute the PumpSwap pool was
created.

### ⛔ RETRACTED — Correction added 2026-09-22 from the @CryptoGorilla archive

⭐ **The half of this that survives:** EMBER really is a token-pairing launchpad
on Meteora, and that is confirmed on chain now that the right mint is being read —
19 of `5dvXTZ5q…`'s 30 pools are Meteora and its second-largest quote asset is
**MET, Meteora's own token, at $522,677**.
⛔ **The half that is wrong:** it was applied to `FLCr9vGM…`, so "EMBER is a
Meteora DBC launch, not pump.fun" describes the phantom. The real one is SPL, not
Token-2022, and spans meteora / orca / raydium / pumpswap / meteora-dbc.


**It is a token-pairing LAUNCHPAD on Meteora**, and it had already round-tripped
before our journal ever saw it. His two dated lines, verbatim:

- **2026-09-10:** *"$EMBER, a token-pairing launchpad on Meteora hit $6m"*
- **2026-09-11:** *"$EMBER ran to $40m, but had a harsh correction sub $10m"*

⭐ **So the arc was $6m → $40m → under $10m over 11 and 12 September, and our
first sight of it was ten days later, on the way down.** We then measured a real
$292k of depth at 17:11Z on 09-21 and called a 3.97x, which was true and stayed
realizable for about 18 more hours, and then its operator withdrew 2,907.565 SOL.

⛔ **Two things this changes.** First, calling EMBER a memecoin in the morning
report was wrong, and the thing that was rugged was a piece of launch
infrastructure, which is a different and more serious event. Second, **EMBER is
the pairing meta's own plumbing**: a launchpad whose product is token pairing,
in the same weeks that ZCAT/ZEC, NEARKAT/wNEAR and COPCAT/COPX were running
(`docs/ASSET_PAIRED_TOKENS.md`). We were watching the tokens and missed that we
were also holding the venue.

⚠️ Source: five days of that archive were relayed to us, and this session
scraped all 49 posts (2026-08-04 → 2026-09-21). **His figures are his claims,
dated, not our measurement.** What we verified ourselves is the chain side: the
withdrawal, the timestamps, the $20.36 of remaining depth.

## Correction 2: "the pools no longer exist" never happened. Not once.

I checked **every distinct pool address in the last 24h of outcome rows**
against chain: **5,816 pools, 0 closed.** Frank's instinct was exactly right.
What actually happens is that Dexscreener stops returning the pair, and our
label calls that the token dying.

## Correction 3: 3 of the 10 I wrote off can still be sold today

| contract | symbol | my morning call | chain quote side | Jupiter $100 sells for | holders |
|---|---|---|---|---|---|
| `FLCr9vGM…HTsh` | EMBER | drained | $20 | $0.32 | 109 |
| `GPqoXbff…HR6T` | USDCAT | drained | $0 | no sell route | 13 |
| `3gAXa6kh…QtfJ` | TSLA | drained | $0 | $0.02 | 68 |
| `671dNhKr…MWJ7` | OWL | drained | $0 | no sell route | 12 |
| `BsE3aa5F…ErTK` | X7 | drained | $3 | $1.44 | 65 |
| `MjimYVjN…epump` | ChatGPT | down 96%+ | $105 | **$89.44** | 24 |
| `HGNPr1zt…xpump` | MrBeast | down 96%+ | $32 | no sell route | 71 |
| `EHY56TBN…Spump` | tradecat | down 96%+ | $306 | **$90.07** | 37 |
| `5vg9KLxC…3pump` | Vortex | down 96%+ | $115 | **$89.47** | 2,011 |
| `k4WcTJwc…Ppump` | UOTF | down 96%+ | $24 | no sell route | 9 |
| `9KmeDWVt…9soG` | STONKBROS | still trading | see below | $94.11 | 426 |
| `54c53Nao…spump` | VSOF | still trading | $324 | $90.12 | 89 |
| `CdhZy8wr…Kfx7` | X7 | still trading | $43,007 | $95.56 | 1,733 |
| `BLSuVTxK…8pump` | CATEWALK | still trading | $50,028 | $97.65 | 13,433 |
| `HXQ66zSR…n391` | GO | still trading | $19,627 | $96.45 | 963 |

**8 of 15 are still sellable**, not 5. Of the 10 I called collapsed, **7 are
genuinely unsellable and 3 are not**.

⚠️ **STONKBROS is the shape of the bug Frank is describing, inside my own
tool.** Its only real market is a Raydium CPMM pool quoted in **STONK**, not
SOL or USDC. My chain reader only valued SOL, USDC and USDT, so it read
**$0.03** while Jupiter sells $100 of it for $94.11 and reports $13,153 of
liquidity. Fixed in the probe during this run; the same blindness in the
pipeline is unfixed (see below).

⭐ **And 4 of the 5 dead ones died the same way EMBER did: a `Withdraw`, as the
last event on the pool.**

| contract | symbol | LP pulled at | by |
|---|---|---|---|
| `GPqoXbff…HR6T` | USDCAT | 09-21 19:54:19Z | `FF8mFScTU484iR…` |
| `671dNhKr…MWJ7` | OWL | 09-22 07:14:06Z | `7CRkdrfaFt31rZ…` |
| `BsE3aa5F…ErTK` | X7 | 09-22 10:27:06Z | `86iCHjJ1C6DTKb…` |
| `FLCr9vGM…HTsh` | EMBER | 09-22 11:09:37Z | `HoX8uwcQiEmz…` |

TSLA and UOTF show no withdraw in their last 100 transactions, so they are
unresolved, not cleared.

---

## 1. EMBER, falsification attempt

Method, so it can be repeated: every token account for the mint from Helius DAS
(a pool must hold the token in a token account, so no venue can hide), each
owner classified by the program that owns it, plus `getProgramAccounts` memcmp
on the mint at the pool layouts of PumpSwap, Raydium v4/CPMM/CLMM, Orca
Whirlpool and Meteora DLMM/DAMM v1/v2. Then each pool's quote vault read from
chain.

Result: 5 pool accounts, **$20.36** total quote side, price about $0.000037 in
the deepest (Meteora DAMM v2 `GEbjH3Er…`, 0.172 SOL), 109 holders, supply
100.0B, authorities revoked. RugCheck independently reports $21.05 of market
liquidity. GeckoTerminal reports $2.23. Dexscreener reports $1.35 and, on the
drained PumpSwap pool, **$125.6M of 24h volume**, which is generated by bots:
that pool has taken **138,393 transactions since 09-21 10:55Z**, about 5,000 to
6,600 per hour, and kept printing volume after the SOL was gone.

**EMBER is not alive somewhere we were not looking.** It is dead, it died at
11:09:37Z today, and the rug is on chain with a signature and a signer.

## 2. Generalisation

The migration read **is** broken, just not the way it broke EMBER. Of the 5,816
pools we tracked in 24h, **3,878 (67%) are pump.fun bonding curves**, and
**6,511 of 9,930 outcome rows are labelled dead or gone on a bonding curve**.
Against our own graduation ledger: **243 rows on 135 distinct contracts were
checked against a bonding curve AFTER our ledger recorded the token graduating
off it** (233 of them strictly after). Those labels are wrong by our own data.

⚠️ **One intermediate finding of mine did not survive its own check, and I am
reporting it rather than burying it.** A Jupiter $100 round trip said 65% of
dead-or-gone curve contracts were still sellable at about $92 back. That is an
artifact: a pump.fun curve prices off virtual reserves, so a curve holding
**$0 of real SOL** still round-trips $100 at the same cost. I verified the
curves on chain: 0 of 12 sampled held even $1,000. The round trip is not a
depth measurement on a bonding curve.

## 3. The "gone" label, and the code path

`journal.py:974`:

```python
if liq is None:
    status = "gone"
```

`liq` is None when the Dexscreener pair lookup returns nothing (`track.py:280`)
and the token-level fallback also returns nothing (`track.py:323`,
`resolve.resolve`). **Neither is a chain read.** So four different states share
one label:

| state | what we call it | reality today |
|---|---|---|
| a. pool account closed | "gone" | **0 of 5,816** |
| b. pool exists, near-zero reserves | "gone" or "dead" | the common case |
| c. indexer stopped returning it | "gone" | happens, count unmeasured |
| d. we asked about the wrong pool | "gone" | 135 contracts, migration |

All 3,612 gone rows in 24h carry `reasons: [source_dropped, unresolved]`, so
both lookups failed. The fallback budget is 8 per pass (`track.py:49`), and
when it is spent the row is labelled from a lookup that never ran. `track.py`
even says it: *"The primary went quiet. That is NOT the same as the token
dying."* Then it writes the label anyway.

## 4. The fraud labels

⚠️ **I cannot source "23 of 23".** It does not appear in the repo, in today's
report or in yesterday's. Whatever it refers to, I did the audit.

Across the 1,344 tracked universe entries: **188 DANGER, 1,012 WARN, 37 NO
FLAGS, 107 UNKNOWN**. Every DANGER rests on evidence that cannot come from a
bad liquidity read:

- **101** on a Jupiter $100 sell simulation returning TOTAL_LOSS or no sell
  route, which is a honeypot proof, not a statistic
- **87** on chain evidence: live freeze authority, live mint authority, or a
  Token-2022 extension
- **0** on Dexscreener-derived checks alone

The launch-side TRAP label is also chain evidence (`scanner.py:740`, grade 0 for
a live authority). So a wrong liquidity read does not by itself produce a fraud
verdict.

**Structural hollowness is the WARN tier and should be read as description:**
818 WARN on round-trip cost, 564 on holder concentration, 180 on cap backing,
69 on unlocked LP (RugCheck), and the D1 "pool is the whole supply" check
(`detector.d1`, Dexscreener `liq`/`fdv`), which is the only place the
781x-overstating field reaches a verdict at all.

## 5. The 91% graduation miss, by cause

Our own coverage rows answer this. Each scan pass records the discovery window
it saw.

| cause | share | evidence |
|---|---|---|
| **cadence: we only look 7% of the time** | ~93% of the miss | 28 passes in 24h, median window **199s**, median 84 pools; union of all windows **1.68h of 24h = 7.0%** |
| in-window loss (enrichment, filters) | ~26% of what we do see | 86 graduations landed inside a sampled window; **64** reached the journal |
| truncation | ~0 | 1 truncated pass of 28, `pages_lost` 0, median `scan_coverage` 1.000 |
| rate limiting | not observed | no lost pages in 24h |
| wrong definition | no | the ledger reads pump.fun's migration authority, 5,420 graduations all-time, `accounted: true` |

Total: **97 of 1,081 graduations in 24h = 9.0%**, and 7.0% time coverage
explains almost all of it. The source is GeckoTerminal `new_pools`, 20 pools a
page, **page 10 is a hard ceiling** (page 11 returns 429), so one pass can see
at most about 400 seconds of the stream. Full coverage by polling needs a pass
every ~3 minutes, about 400 a day against 28 today.

## 6. Venues, and the AMM subscription

**Coverage by volume (DefiLlama, Solana, 24h):** $3.656B across 125 protocols.

- Venues our chain reader can parse: **46.4%**
- Venues it cannot: **53.6%**, led by **BisonFi at 12.2%**, bigger than
  PumpSwap
- pump.fun plus PumpSwap together: **14.4%**. Our graduation ledger watches only
  pump.fun's migration authority, so as a launch tracker it is blind to
  **85.6%** by volume

Venues Jupiter routed through in today's quotes that we do not recognise at
all: Quantum, BisonFi, Kipseli, HumidiFi, Scorch, Flux, Quay. Launchpads
already visible in our own universe: pump.fun 527, **stonkfun 60**, metadao 11,
met-dbc 7, letsbonk.fun 4, jup-studio 3, heaven 1, Believe 1.

**`programSubscribe` status: no code exists.** I grepped the repo. There is a
websocket URL builder (`config.helius_ws()`) and two docstrings mentioning
websockets. Nothing subscribes. The blocker was never the code, it is the
always-on host.

**The Vercel webhook does run with his PC off, and it is watching nothing.**
Confirmed live today: webhook `75056f75-c129-4f43-b686-0f369f8fa669`, type
enhanced, `transactionTypes: [ANY]`, **`accountAddresses: 0`**, pointing at
`crypto-intel-one-eta.vercel.app/api/helius`.

Whether it can replace the subscription: a webhook is push, so it needs no
always-on process, and Helius accepts up to 100,000 addresses. But the volume
is the problem. We measured **56 notifications/sec on pump.fun alone**
(2026-09-17), which is **4.8M events/day, about 145M/month**, each one a Vercel
function invocation. ⚠️ **I did not verify Helius' per-event webhook price
today**, so I will not put a dollar figure on it; the event count alone is one
to two orders of magnitude above a free serverless tier.

**On Frank's desktop:** it works only while the PC is on and awake, and we have
the evidence of what that costs. The desktop collector died silently from
2026-09-15 to 2026-09-19 when a reboot lost its drive mount. A subscription
there would have the same failure mode, and the gap in a real-time feed cannot
be backfilled.

---

## What this changes

1. ⛔ **Stop writing "gone".** It should say which of the four states we
   observed, and it should read the chain before it says any of them.
2. ⛔ **Follow the token, not the pool.** When a recorded pair is a bonding
   curve and our ledger says the token graduated, the outcome must be scored on
   the AMM pool. 135 contracts in one day.
3. ⛔ **Depth must price any quote asset**, not just SOL/USDC/USDT. STONKBROS
   read $0.03 against a real $13,153.
4. ⭐ **The rug is detectable and it is the loss Frank actually eats.** 4 of 5
   dead winners ended with a single `Withdraw` as the last event on the pool.
   That is one instruction on one account, and it is exactly the class of loss
   this system exists to stop.
5. The graduation miss is a cadence problem with a measured size, and polling
   cannot close it. That is the case for the subscription, now with numbers.
