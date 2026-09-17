# A liquidity number we can trust

**2026-09-17. Every number here was measured today, on this machine. Nothing
was bought, nothing was signed up for, no trade was executed.**

---

## Recommendation: **Jupiter quote API. Free, no key, ~370ms per token.**

Frank's framing was the right one and it is also the cheapest one:

> *"if I try to sell 100 USD of this right now, what do I actually get?"*

That is not a proxy for liquidity. **It is the answer itself**, and Jupiter will
tell us for free, in under half a second, without an account.

| | our stored `liq` | Birdeye | Helius direct | **Jupiter** |
|---|---|---|---|---|
| what it measures | base+quote nominal | pool TVL | pool reserves | **USD actually returned** |
| catches one-sided pools | ❌ no | ❌ no | ⚠️ only if decoded | ✅ **yes** |
| catches no-route tokens | ❌ no | ❌ no | ❌ no | ✅ **yes** |
| cost | free | key died after ~7 calls | free w/ key | **free, no key** |
| latency | — | 142–717 ms | **119 ms / 20 tokens** | 181 ms/leg |
| build cost | — | none | **5+ AMM layouts, forever** | none |
| routable today | — | 401 | — | 100% at ≤60/min |

---

## 1. The measurement that decides it

A **$100 round trip**: quote USDC→token for exactly $100, take the token amount
that comes back, quote token→USDC for that exact amount. The difference is what
the market would really cost you, in and out, right now. It needs no price
input, no supply figure and no pool layout — it is self-calibrating.

```
sym       our stored liq   our depth |   JUP round trip   verdict
BONK                   0           0 |       0.08%        deeply liquid
STONK            187,942      45,087 |       0.16%        genuinely liquid
CTO                6,334       2,106 |       6.00%        real, expensive
COIN              15,587       5,300 |     100.00%        you get $0.00 back
RIOROB            95,596      47,884 |      99.99%        you get $0.01 back
USBD               9,133       1,010 |     NO ROUTE       cannot be sold
KHPD              27,105       5,200 |     NO ROUTE       cannot be sold
$1                     0           0 |     NO SELL ROUTE  one-way pool
```

⛔ **COIN and RIOROB are the point.** Both passed our own verification screen.
COIN passed it holding a claimed $995,282,784 FDV against $5,300 of "depth".
Jupiter prices both at a **100% round-trip loss** — put in $100, get back
nothing. **Our screen let them through. A free API caught them in 370ms.**

⭐ **"NO ROUTE" is a first-class answer**, and that matters more than it looks.
It maps exactly onto the rule this repo already enforces everywhere else:
**an unknown must not render as a real value.** Unsellable comes back as
unsellable, not as "$5,200 of depth".

## 2. Why not the other two

### Birdeye — ⛔ the key exists, and it died in seven calls

Per the standing lesson, I checked before pricing: **`BIRDEYE_API_KEY` is
already in `.env`** (32 chars, real). It is not a key we need to buy.

It worked — `/defi/v3/token/market-data` returned `liquidity: 3,119,954` for
BONK in 142ms. Then, after roughly seven calls, `429`, and then **`401
Unauthorized` on every subsequent request, five for five, still 401 fifteen
minutes later.** I did not test whether it resets daily.

Two reasons it is not the answer even if it resets:

1. **It measures the wrong thing.** $3.1M for BONK is pool TVL — *the same
   category of number as the field we are replacing*, just computed more
   carefully. It cannot distinguish a $3M two-sided pool from a $3M pool
   holding one worthless side, which is the entire failure mode.
2. **Scaling it costs money.** Free → Starter **$99/mo** → Premium **$199** →
   Business **$699**. Standing rule is free tools only.

### Helius direct pool reserves — ⚠️ fast, free, and a permanent maintenance bill

Latency is genuinely excellent: **`getMultipleAccounts` returned 20 pool
accounts in 119–132 ms**, ~6ms per token amortised, and **0 of 40 pool accounts
were missing** from chain. If we only needed reserves, this would win.

The problem is the decode. In a 40-pool sample from our own rows:

| owner program | pools | what it is |
|---|---:|---|
| `6EF8rrec…F6P` | 26 | pump.fun bonding curve |
| `pAMMBay6…XEA` | 6 | PumpSwap |
| `dbcij3LW…qdN` | 5 | Meteora DBC |
| `cpamdpZC…sGG` | 2 | Meteora DAMM v2 |
| `FLUXubRm…m1X` | 1 | FluxBeam |

**Five distinct binary layouts in forty pools**, across six account sizes
(151B, 125B, 301B, 424B, 1112B, 324B) — and that sample contains no Raydium v4,
no Raydium CLMM, no Orca Whirlpool, no Meteora DLMM. Realistically eight to ten
layouts to write and then maintain forever, against programs that redeploy
without telling us.

⛔ **This is not a hypothetical cost. It is the bug we already have.**
`onchain_reserves.exit_depth()` fails on 5 of 6 reads for exactly this reason,
and `exit_depth_usd` is `> 0` on only **23.9%** of rows. Helius-direct is the
approach that is already failing.

And even when it works it returns **reserves**, not **realizable output** — it
would still not have caught COIN.

## 3. What Jupiter costs us, measured not assumed

Reliability at three call rates, 25 calls each: **75/75 succeeded**, p50 181ms,
p95 216ms. Repeat quotes on the same token agree to **0.0016%**.

Then it stops dead. A sustained run found the wall precisely:

```
t=  0- 30s  {200: 24}
t= 30- 60s  {200: 25}
t= 60- 90s  {200: 25}
t= 90-120s  {200: 23, 429: 1}
t=120-150s  {429: 26}      <- hard cutoff, no partial service
```

**~97 calls, then 429 on everything.** So the working budget is **≈60 quotes/min
= ~30 round trips/min = ~1,700 tokens/hour**, and any client **must** back off
rather than retry. That is ample: we see ~2,500 distinct contracts/day, and we
only need to price the ones that matter.

⚠️ **This rate limit is the one real weakness.** It rules Jupiter out as a
per-row field on every scan of every token. It rules it *in* as the gate that
decides whether something counts.

## 4. ⭐ Plan to replace the poisoned field

**The good news: the gate is already correct. Only the measurement is broken.**

`journal._exit_liquidity_ok()` and `verify_win()` already **fail closed** when
depth is missing — that was fixed on 2026-09-11, and the comment in `journal.py`
already names the exact failure (`judged = exit_depth if ... else liq`, which
"silently turned a $1,000 exit-depth floor into a $1,000 reported-liquidity
check"). Nothing about that logic needs to change.

So this is not a rewrite. It is **swapping the source that feeds one field**.

| step | change | files |
|---|---|---|
| 1 | add `jupiter.py`: `round_trip(mint, usd=100)` → `(usd_back, cost_pct, verdict)`, `None` on no-route, token-bucket limiter at 55/min, exponential backoff on 429 | new |
| 2 | add `exit_realizable_usd` + `exit_rt_cost_pct` + `exit_quote_ts` to the `journal.record()` whitelist — ⛔ **and to `test_whitelist.py`**, or it becomes silent drop number six | `journal.py`, `test_whitelist.py` |
| 3 | point the gate at the new field, keeping `exit_depth_usd` written alongside for comparison. **Do not delete the old field** — standing rule, nothing is ever deleted | `journal.py:88`, `evidenceguard.py:171` |
| 4 | quote **only at decision points** — watchlist entry, paper entry, paper exit, milestone crossing — never on every scanned row. This is what keeps us inside 60/min | `paper.py`, `watchlist.py`, `detector.py` |
| 5 | surface `NO_ROUTE` distinctly on the dashboard. Not `$0`, not blank — **"unsellable"** | `dashboard.py` |
| 6 | leave `liq` in place as *reported* liquidity, and rename it in every user-facing surface to `liq_reported` so it can never again be read as exitable | `dashboard.py`, `check.py` |

**19 files reference `liq`, but only two decide anything with it** —
`journal.py:88` and `evidenceguard.py:171`, which are the same expression. That
is the whole blast radius.

## 5. ⛔ Re-verifying the wins — and the trap in the question

**First, a correction: the figure 165 does not re-derive.** The populations that
actually exist are **185** (mult≥2, flagged realizable) and **141** (mult≥3,
flagged realizable). I ran the full 141.

```
141 winners, Jupiter $100 round trip, measured TODAY

  TRADEABLE      (<10% cost)      8    5.7%
  COSTLY       (10-50% cost)      7    5.0%
  TOTAL_LOSS     (>50% cost)     70   49.6%
  NO_SELL_ROUTE                  26   18.4%
  NO_BUY_ROUTE                   30   21.3%
  -------------------------------------------
  EXITABLE AT ANY SANE COST      15   10.6%
```

⛔ **This does NOT mean 126 of the wins were fake, and I will not let it be
read that way.** These are historical outcomes measured with a *present-day*
quote. Memecoins die; a token that genuinely tripled three weeks ago and is
worthless now would score exactly like a phantom that was never exitable. **A
quote taken today cannot verify what was true at the time of the win.** Claiming
otherwise would be the same error class as the retracted dwell finding — reading
a measurement taken at the wrong moment as if it described another one.

What it **does** establish, and this is still damning:

- **Age does not explain it.** Median age is only **14.8 days**, and the
  1–3-week band (n=114) is **12.3% exitable** against **4.3%** for over three
  weeks. Deaths are not concentrated in the old rows.
- **The `realizable` flag does not predict exitability.** All 141 were *flagged
  realizable by our own gate*. Today 10.6% are. The flag is not measuring what
  its name says.
- **The honest status of the win history is "unverifiable", not "verified" and
  not "false".** It cannot be fixed retroactively at any price.
- ⭐ **It can be fixed forward, starting immediately and for free** — record a
  round-trip quote at entry and at exit on every paper position and the ledger
  becomes genuinely verified within days.

**The 15 that are still exitable today**, named, since fabricated samples have
been caught here before:

| symbol | peak | RT cost | $ back |
|---|---:|---:|---:|
| WYNX | 10.5x | 3.02% | $96.98 |
| CONK | 7.4x | 3.33% | $96.67 |
| Anonymouse | 9.9x | 3.67% | $96.33 |
| QCAT | 3.8x | 6.40% | $93.60 |
| APEC | 19.1x | 6.58% | $93.42 |
| ROCK | 31.8x | 8.37% | $91.63 |
| MICRO | 3.6x | 9.07% | $90.93 |
| peepeepoopoo | 3.5x | 9.36% | $90.64 |
| DCAT | 4.1x | 10.02% | $89.98 |
| AURA | 5.2x | 10.66% | $89.34 |
| TESTICLE | 7.5x | 10.70% | $89.30 |
| JR2000 | 3.1x | 10.85% | $89.15 |
| NTDA | 3.0x | 11.09% | $88.91 |
| USWS | 4.6x | 11.11% | $88.89 |
| WOFI | 333.3x | 11.66% | $88.34 |

⚠️ **Even the best of these costs 3% to round-trip at $100.** Nothing in this
list is a free exit, and WOFI's 333x sits alongside an 11.66% cost to move a
hundred dollars.

## 6. ⚠️ A side finding worth more than it looks

Sorting our own rows by stored `liq` puts these at the top:

```
Fartcoin   $7,406,577,362      RAY   $3,323,443,498
CC         $4,995,408,775    ‮ETAC   $2,511,355,171
```

**None of them are the real token.** Our "Fartcoin" is mint
`6fWd7KWn…VquS`; real Fartcoin is `9BB6NF…pump`. Our "RAY" is `7VoiKfrL…78ike`;
real RAY is `4k3Dyjz…kX6R`. Jupiter's verdict on ours: *"The token
6fWd7KWn… is not tradable"*. (`‮ETAC` and `‮LLORT` are the RTL-override
impersonators — the same class that crashed a terminal here earlier.)

⭐ **The poisoned `liq` field is what floated ticker impersonators to the top of
our own data.** Replacing it removes a whole category of fake, not just bad
numbers. And it is the direct argument for the standing rule that keys are
contract addresses and never tickers.

---

## 7. AMM subscription — the numbers, no decision asked for

### ⭐ Yes, Helius filters server-side. It was accepted and it works.

⚠️ **My first attempt at this measured filtered and unfiltered in sequence and
got nonsense** — the "filtered" stream came back *busier* than the unfiltered
baseline, because memecoin traffic is bursty and the two samples covered
different minutes. Re-run with **four subscriptions open simultaneously on the
same traffic**:

```
subscription      msgs   msgs/s      KB/s     credits/mo    share
unfiltered        3124     52.0      28.7      1,525,059   100.0%
dataSize=137      1389     23.1      12.2        649,728    42.6%
dataSize=151      1242     20.7      11.4        605,030    39.7%
dataSize=125       401      6.7       3.4        182,568    12.0%
```

`memcmp` was also **accepted** (arbitrary byte-offset matching), so filtering is
not limited to account size.

⛔ **The limit that matters:** `memcmp` is equality-only. **"Reserves above
$1M" cannot be expressed server-side** — a numeric threshold is not a byte
match, and market cap is derived, not stored. Server-side filtering narrows
*which accounts*, never *which values*. The floor must still be applied locally.

### Cost, CPU and where it actually runs

Helius bills **20 credits/MB** (2 per 0.1MB), and `programSubscribe` is
**available on every plan including Free**. Free is **1M credits/mo**;
Developer is **$49/mo for 10M**.

| | credits/mo | verdict |
|---|---:|---|
| unfiltered | 1,525,059 | ⛔ exceeds Free — needs $49 Developer |
| one `dataSize` filter | ~650,000 | ✅ **fits the free tier** |
| tight filter | ~183,000 | ✅ 18% of free tier |

⭐ **Server-side filtering moves this from $49/mo to $0/mo.**

⚠️ Two honest caveats: the 1M free credits are **shared with the collector's
own RPC calls**, and this measures **one program**. A real crossing detector
needs PumpSwap, Meteora and Raydium too, each adding its own volume. Treat
~650k as the floor for one venue, not the total.

**CPU is a non-issue.** Full parse + base64 decode + reserve unpack on every
message: **1.16% of one core** at 77.7 msg/s. The binding constraint is
bandwidth and credits, never the processor.

### Desktop vs a $4–6 VPS

| | Frank's desktop | $4–6/mo VPS |
|---|---|---|
| cost | $0 | $48–72/yr |
| uptime | ⛔ **this is the whole problem** | ~100% |
| bandwidth | 30–110 GB/mo on home internet | included |
| CPU needed | 1.16% of a core | 1.16% of a core |

⛔ **The desktop's record is the argument.** Nothing has collected since
**2026-09-15 05:07:59 UTC** — a reboot killed it and nothing noticed. A
subscription that must hold a socket open forever is precisely the workload a
machine that reboots cannot do. **A VPS costs $48–72/yr against $8,600 of paper
notional already deployed** (§8), and it is the only line item here that buys
uptime.

## 8. ⚠️ Re-derived while checking a figure: the paper P&L has moved

I quoted "$335 at risk" from memory while drafting §7. It does not re-derive, so
here is the ledger recomputed from `data/paper/ledger.jsonl`:

| | value |
|---|---:|
| non-void closes | **86** |
| deployed ($100 each) | $8,600.00 |
| returned, by recorded `mult` | $6,104.64 |
| **P&L by multiple** | **−$2,495.36** (−$29.02/round trip) |
| returned, by recorded `realizable_usd` | $4,432.24 |
| **P&L once exit depth is honoured** | **−$4,167.76** (−$48.46/round trip) |

⭐ **The gap between those two lines is the whole thesis of this document.**
The same 86 closes lose **$2,495** if you believe the price multiple and
**$4,168** if you believe what could actually have been sold — a **$1,672**
difference produced entirely by whether liquidity is taken seriously.

⚠️ This also supersedes the previously reported **"76 closes, −$3,099,
−$40.78/round trip"**. That figure no longer re-derives: the population is now
86 closes, and neither the total nor the per-trade number matches on either
basis. **B22 in `RULES.md` still carries the old figure and is already flagged
there as not re-deriving.**

**No decision is being asked for and none has been made.**


---

# Part 2 - the Jupiter key, and the head-to-head that settles it

**2026-09-17, later. Frank supplied a Jupiter free-tier key (read-only quote
access, no funds, no write scope). It is in `.env`, which is gitignored at line
2, has never been committed and is not staged.** ⛔ **The key value appears in no
doc, log, commit or report.**

## 9. The key is live, and it does not buy speed

`api.jup.ag/swap/v1/quote` with `x-api-key`: **HTTP 200 in 310 ms**, returning an
`outAmount` identical to the keyless endpoint on the same token.

⚠️ **Measured rate ceiling, and it is not what I expected:**

| | keyless | **keyed** |
|---|---|---|
| burst | ~97 calls, then a **hard 429 on everything** | ~30, then refills |
| 1.0 req/s | ok | **45/45 (100%)** |
| 2.0 req/s | - | 30/45 (67%) |
| 3.0 req/s | - | 23/45 (51%) |
| effective ceiling | ~1 req/s | **~1.1 req/s** |

⭐ **The key buys reliability and a refilling bucket, not throughput.** The
keyless endpoint dies completely; this one degrades and recovers. **The
decision-point-only rule stands - this still must not go on the per-row scan
path.**

**Usage tracking** is `chainfields.usage()`, persisted to
`data/_jupiter_usage.json`. Free tier is **25,000,000 credits/month**, then $1/M.
After all the work in this document: **95 quotes = 0.00038% of the allowance.**
At 1 req/s we could not exhaust it if we tried - about 2.6M/month is the physical
ceiling. ⛔ **Flag it if that ever stops being true.**

## 10. ⭐ The depth curve - one number cannot express depth

`chainfields.depth_curve()` quotes a round trip at several notionals:

```
sym              $10         $100         $500        $1000
BONK           0.04%        0.11%        0.15%        0.27%
ROCK           8.28%        8.51%        9.51%       10.51%
WOFI           3.46%       11.63%  NO_SELL_ROUTE  NO_SELL_ROUTE
```

⛔ **At $10, WOFI (3.46%) looks CHEAPER than ROCK (8.28%). At $500 WOFI cannot be
sold at all and ROCK is unchanged.** A single liquidity figure - ours, Birdeye's,
anyone's - cannot represent that, and the token that looks best at small size is
the one that traps you at real size.

**BONK scales (0.04% to 0.27%). ROCK is expensive but honest and flat. WOFI is a
cliff.** Frank trades $100 clips, so $100 is the number that matters - but the
curve either side of it says whether the price survives sizing up.

## 11. ⭐ Settling "pools under a dollar"

**The claim came from the poisoned field and Frank never believed it. The honest
answer is that it was mostly right, and wrong in a way nobody predicted.**

Population: **954 distinct contracts with 0 < `liq` < $1**, and **26,780 at
exactly 0**. Tested the 14 with the largest reported FDV, where a lie shows most:

| verdict | n |
|---|---|
| TOTAL_LOSS | 8 |
| NO_BUY_ROUTE | 3 |
| NO_SELL_ROUTE | 2 |
| **TRADEABLE** | **1** |

**13 of 14 confirm the pools really were empty.** The sub-dollar reading was
correct about them.

⛔ **But the one exception is the important one.** A row recorded at
**`liq = $0.01`** came back **$99.98 of $100 - TRADEABLE**. Checking the mint
rather than the ticker, per the standing rule:

- our mint: `2zMMhcVQEXDtdE6vsFS7S7D5oUodfJHE8vd1gnBouauv`
- that **is** real PENGU (Pudgy Penguins)
- on-chain supply **76,722,827,861**, real FDV via `chainfields`: **$557,244,807**

⭐ **The stored field recorded one cent of liquidity for a half-billion-dollar
token.** Any dust filter keyed on `liq` would have silently discarded one of the
most liquid assets on Solana.

**So the field is not merely inflated. It is unreliable in BOTH directions**, and
"low `liq`" was never safe to read as "dust" any more than "high `liq`" was safe
to read as "deep". ⚠️ Three of the four rows we labelled "PENGU" are
impersonators on different mints - the ticker problem again.

## 12. ⭐ Head to head: stored vs Helius reserves vs Jupiter

18 random contracts with a non-zero stored `liq`:

```
Helius reserve reads : 2 ok / 16 FAILED  (89% failure)
Jupiter              : answered all 18
Jupiter verdicts     : NO_BUY_ROUTE 7, TOTAL_LOSS 8, NO_SELL_ROUTE 2, TRADEABLE 1
```

| | |
|---|---|
| contracts Jupiter says are unexitable | **17 of 18** |
| stored liquidity claimed for those | **$7,467,996,005** |
| actually recoverable, $100 probe each | **$1.68** |
| stored `liq` of the ONE tradeable token | **$6** |

⭐ **The single tradeable contract had the LOWEST stored liquidity of any of them
- $6, returning $90.79.** Meanwhile the $7.4 billion claim is the "Fartcoin"
impersonator, which has no route at all. **In this sample the stored field is not
merely noisy; it points the wrong way.**

⛔ **Helius direct is not a fallback.** 89% failure here against the 5-of-6
recorded earlier - worse, not better. **It cannot be the source, and it cannot be
the cross-check either.**

## 13. Call sites of the poisoned field - inventory before changing anything

**Decision sites (these change behaviour):**

| file:line | what it decides |
|---|---|
| `journal.py:88`, `:109`, `:198` | exit floor and `verify_win` - already fails closed |
| `evidenceguard.py:171` | same expression, same fix |
| `detector.py:79` | **D1 SILENCE** - `liq/fdv >= 0.95` |
| `detector.py:85` | **D2 MAGNITUDE** - `liq >= $1M` |
| `journal.py:864-869` | rug/dead classification, `liq < 1000` |
| `paper.py:821` | `DEAD_LIQ_USD` on the ledger |
| `plausibility.py:130`, `:132` | hard and soft liquidity ceilings |
| `resolve.py:44`, `journal.py:50` | `MIN_EXIT_LIQ_USD` from scanner config |
| `clusters.py:174` | `funded = liq > 0` |
| `pricecheck.py:123` | dust floor - **allowlisted, see below** |

**Display only (rename, do not re-key):** `dashboard.py:280`, `check.py:177-291`,
`findings.py:19`.

✅ **I flagged `pricecheck.py:123` as an unfixed sixth instance of the
substitution bug. I was wrong.** `evidenceguard.audit_substitutions()` already
catches the whole class and carries an explicit allowlist entry for it: *"Dust
check only... Its verdict can only make a quote LESS trusted, never more."*
Running the audit returns **2 findings, both `accepted: True` with written
justifications** (`pricecheck.py:123` and `resolve.py:214`). **The guard works.**

### Replacement order

1. **`detector.py` D1 and D2 first.** They are the only sites whose output is
   shown to Frank as a judgement, and both are keyed directly on `liq`.
   Re-derive their precision against `round_trip()` before quoting it again.
2. **`plausibility.py` ceilings** - calibrated against a distribution whose
   maximum is an impersonator.
3. **`journal.py` rug classification** - `liq < 1000` should become
   `exit_verdict in (TOTAL_LOSS, NO_SELL_ROUTE, NO_BUY_ROUTE)`.
4. **Rename `liq` to `liq_reported` on every display surface.** Nothing is ever
   deleted; it stops being readable as exitable.
5. ⛔ **`clusters.py:174` `funded = liq > 0` is the worst of them** - it treats
   any non-zero reported liquidity as a funded pool, and 82.7% of rows are
   exactly 0 while real PENGU sat at $0.01.
