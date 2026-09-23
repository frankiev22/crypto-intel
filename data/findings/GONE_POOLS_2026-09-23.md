# `gone`, asked properly: derive the pool from the mint, on chain

**2026-09-23.** Rule: `PRECOMMIT_pool_discovery.md`, written before a single
sample contract was read. Instrument validated first on mints outside the sample.

Frank: *"I think the 1.7% testing result is inaccurate. We need to use the
contract address to find the real pool so we can see it after bonding."*

---

## 1. ⛔ Lead with it: the method was wrong, and fixing it barely moved the number

**My pre-registered prediction was 15% to 45%. The measured answer is 2.5%.**

| | |
|---|---|
| ⛔ **headline** | **2.5% [0.85, 7.09], 3 of 120** have a pool holding >= $100 of quote-side reserves on chain |
| ⚠️ it is a **LOWER BOUND**, and the ceiling is measured | **at most 10.8%** (§7) |
| the result Frank rejected | 1.7%, and **it sits inside that interval** |
| his expectation | "materially higher than 1.7%" |
| my pre-registered prediction | **15-45%**, refuted — ⛔ even the worst-case ceiling falls short of 15% |
| ⭐ reproducibility | run twice 14 min apart, **0 verdict changes across 120 contracts** |

⛔ **So I was wrong and so was the expectation.** The pre-commit said in advance
what under 5% would mean, and it means it: *"`gone` is roughly honest about
liquidity even though it is wrong about mechanism."*

⭐ **The method fix was still necessary, and it earned something the old one could
not:** the old run asked the same indexer twice and could not tell an empty pool
from an absent one. This run reads the pool's own vaults, so every number below is
a fact about chain state rather than about Dexscreener's coverage.

---

## 2. ⭐⭐ The real correction is to the WORD, not to the rate

⛔ **`gone` says the pool is gone. It is not. 105 of 120 contracts have a pool on
chain right now: 87.5% [80.4, 92.3].**

| verdict | n | what it means |
|---|---|---|
| **POOL_QUOTE_DUST** | **96** | ⭐ **the pool EXISTS and holds essentially nothing** (< $10 quote side) |
| NO_POOL_FOUND | 15 | ⚠️ we did not find one. **A FLOOR, not proof of absence** |
| POOL_QUOTE_100 | **3** | >= $100 of quote side. ⭐ **All three verified sellable, section 4** |
| POOL_QUOTE_10 | 3 | $10 to $100 |
| POOL_QUOTE_UNVALUED | 3 | ⛔ a pool whose quote asset we do not price. **Its own bucket, never dust** |
| UNREADABLE | **0** | nothing was lost to our RPC budget |

⭐ **The precise statement `gone` should have made:** *the pool still exists and
has been emptied.* Four states were collapsed into one word (`journal.py:974`) and
this separates them. The dominant state, 80% of the sample, is **an empty pool**,
not a missing one.

## 3. ⛔ And my own hypothesis about WHY was wrong

I predicted a high rate because I expected these tokens to have **bonded
successfully** and moved to a pool our row never recorded. The venue split says
otherwise:

| venue of the discovered pool | n |
|---|---|
| **`pumpfun_curve`** | **82** |
| `pumpswap` | 25 |

⛔ **Most of this population never bonded. They died ON the curve**, which is
exactly the case where an empty pool is the honest answer and the indexer dropping
the pair is the correct behaviour. Only 25 of 120 have a PumpSwap pool at all.

⚠️ **BACKLOG A52 is not contradicted, but its reach is narrower than I implied
here.** A52 measured 243 rows on 135 contracts scored against a curve after
migration. On THIS 120-contract sample, our recorded pair **was** one of the
discovered pools **93 times**. So the wrong-pool defect is real but affects
**27 of 120 (22.5%)**, not the majority.

⭐ **And it lands on the cases that matter: 2 of the 3 contracts with real money
in them had a recorded pair that is NOT the pool holding the money.** That is
Frank's point, confirmed, on the rows where being wrong costs something.

## 4. ⭐⭐ The three that are real, verified against a live sell quote

⛔ These are labelled `gone` in our own record. All three round-trip **$100 to
about $90** on a live Jupiter quote taken minutes after the chain read.

| contract | symbol | chain quote side | live Jupiter $100 round trip | our pair was the real pool? |
|---|---|---|---|---|
| `EKShF2iKiGZNLh9QjXF7tu822AapGh4rNj9h6y8upump` | NOOS | **$398.78** | ⭐ **TRADEABLE, $90.13 back** | yes |
| `3ZvY6acjpewyFphnwQrpF89YmoMqjdC3QqHALvgbpump` | JEANB | **$440.14** | ⭐ **TRADEABLE, $90.24 back** | ⛔ **no** |
| `9VwDGtyezNwrTQTLobyczWKbNje45zyXgBkZpKMnpump` | LOOONGJAK | **$362.59** | ⭐ **TRADEABLE, $90.02 back** | ⛔ **no** |

⚠️ **Quotes, not fills. Nothing was signed and no wallet was involved.**

## 5. ⭐ The pre-committed $100 band separated sellable from unsellable exactly

The threshold was fixed in the rule file before any sample data was read, on the
grounds that $100 is Frank's clip. On the six non-dust contracts it split
perfectly:

| contract | chain quote side | live Jupiter $100 round trip |
|---|---|---|
| NOOS | $398.78 | ⭐ TRADEABLE, $90.13 |
| JEANB | $440.14 | ⭐ TRADEABLE, $90.24 |
| LOOONGJAK | $362.59 | ⭐ TRADEABLE, $90.02 |
| Spider-Man | $41.07 | ⛔ NO_SELL_ROUTE |
| $mgey | $15.84 | ⛔ TOTAL_LOSS, $7.21 back |
| NP | $14.44 | ⛔ TOTAL_LOSS, $6.61 back |

⚠️ **n=6. That is an observation, not a rate**, and no threshold should be trusted
on six points. But it is the right direction and it was pre-committed.

⛔⛔ **And it proves the limit the rule already stated: EXISTENCE IS NOT
LIQUIDITY.** A pool holding **$41.07** of WSOL returns **NO_SELL_ROUTE**. So
`POOL_QUOTE_10` may never be read as "you can sell this", and a discovered
reserve is **shape**, never an exit price. The exit stays
`chainfields.round_trip()`.

## 5a. ⭐⭐ Tested again on 15 ALREADY-LABELLED contracts: 0 false positives, 2 misses

To stop the threshold resting on six points, I ran the same chain read against the
**15 contracts in `data/findings/REPORT_2026-09-22_pushback.md`**, each of which
already carries a live Jupiter $100 answer. ⚠️ Different population, so it never
enters the `gone` rate - this is instrument validation only.

| | n |
|---|---|
| chain flags >= $100 **AND** a live sell returns >= $50 | **6** |
| ⭐ chain flags but **NOT** sellable | **0** |
| ⛔ chain clears but **IS** sellable (a MISS) | **2** |
| chain clears and not sellable | 7 |
| **agreement** | **86.7%**, n=15 |

⭐⭐ **Zero false positives across 21 contracts in total.** Nothing the chain band
called >= $100 failed to sell. That is exactly the property the headline needs,
because the headline is a claim that these tokens ARE alive.

⛔⛔ **But the two misses are the honest cost, and they are the FLOOR made
visible.** `9KmeDWVt…9soG` (STONKBROS) and `HXQ66zSR…n391` (GO) both read
**NO_POOL_FOUND** on chain while a live $100 round trip returns **$93.56** and
**$96.44**. So **2 of 15 (13.3%) sellable tokens were missed**, and the ladder's
negatives are demonstrably not proof.

⭐ **And `excluded_owners` - the field standing rule 15 made me record -
diagnosed both.** Two distinct causes, neither of them a logic error:

1. ⛔⛔ **STONKBROS: its quote asset is STONK, which the pre-committed VALUED map
   does not price - and OUR OWN DOCS ALREADY SAID SO.**
   `docs/ASSET_PAIRED_TOKENS.md` records that valuing only SOL/USDC/USDT read
   STONKBROS as **$0.03** while Jupiter sold $100 of it for **$94**. So even a
   perfectly found pool would have graded **POOL_QUOTE_UNVALUED**, never
   POOL_QUOTE_100. ⚠️ **This is the same failure the repo had already documented,
   reappearing in a new module**, and it is why the 3 unvalued rows are in the
   ceiling above rather than treated as dust.
   Its owners compound it: `DWRrtxDte6zpBopy3TJXzRvCpNmGAmKWftoAyRCTfuxn` (under
   `DsxdELwZ…`, 27 trillion base units, **zero vaults of its own** - an escrow or
   lock, not a pool) and `HULfmqDFHXQnxbhyvSPTC15rU6hRZhvsNjayusXu6cUp` (under
   `defAh9DW…`, 5.29 trillion base units and **0.0809 WSOL**, about $9). Both
   programs are **executable BPF programs** the 09-22 probe also classed only as
   `other`, and I am **not guessing names for them.**
2. ⛔ **GO: the top-N-by-BASE-AMOUNT cut misses a pool that does not hold a large
   base share.** GO is a Token-2022 mint with **2,884** token accounts; rung 2
   resolved the top 100 and **truncated 2,784**. Its pool vault is not among the
   largest base holders.

⚠️ **I also made an error diagnosing this and caught it.** I printed those owner
addresses truncated to 14 characters, then completed them from memory in a
follow-up query - which naturally returned two nonexistent accounts. The addresses
above are read from a fresh `discover()` call. **A truncated identifier is not an
identifier.**

⛔ **Neither fix was applied before the sample ran, deliberately.** Adding programs
to the map after seeing which rows failed is post-hoc tuning, and the whole point
of the pre-commit is that it cannot be edited to suit the result. The gap is
recorded and is BACKLOG work, not a patch to this run.

## 6. ⛔ A trap I walked into, one step before publishing

I first assembled controls by resolving symbols from our own rows and got **three
of four wrong.** The 09-22 pushback report's OWL is
`671dNhKr12xRoPmfkevzG1daqi4c9KMAA9J83ExyMWJ7`; the newest row symbol'd OWL is
`GVhegCjHmy2GByvdEAq9ZYtd7hrpHnPB5XZHWvg2pump`. **Different contracts, same
ticker.** Same for TSLA.

⛔ **I had a $264.61 "correction to our own report" written and it was about a
different token.** Standing rule 2, and the same shape as the EMBER retraction.
The addresses in this file are read from the rerun JSON and from our own rows by
`token`, never from a symbol.

## 7. What the instrument costs, and what it missed

| | |
|---|---|
| RPC calls | **778** for 120 contracts, ~6.5 per contract |
| wall clock | **239.8s** |
| RPC errors / rate limited | **0 / 0** |
| UNREADABLE verdicts | **0**, so the pre-committed one-third kill rule never triggered |
| rung 1 answered | 99 of 120 |
| escalated to rung 2 (full enumeration) | 21, and **all 15 NO_POOL_FOUND escalated** |
| ⚠️ rows that truncated holders at rung 2 | **7, worst dropped 115 of 215** (rule 15: recorded, not just counted) |

### ⭐⭐ And the floor is not hand-waving: it is BOUNDED

I went back and re-read all 15 NO_POOL_FOUND rows to ask what each of them had
**excluded**. The answer is unusually clean:

| | |
|---|---|
| NO_POOL_FOUND rows that saw an **unknown executable program** | ⭐ **0 of 15** |
| NO_POOL_FOUND rows read to **COMPLETION**, zero holders dropped | ⭐ **8 of 15** (2, 3, 3, 7, 9, 15, 23 and 2 holders) |
| NO_POOL_FOUND rows that **truncated** | ⚠️ **7 of 15** (86 to 115 holders dropped of 148 to 215) |
| truncations anywhere else in the 120 | **0** |

⭐ **So 113 of 120 contracts were read to completion**, and **every single
truncation in the whole run landed on a NO_POOL_FOUND row.**

⭐⭐ **Which makes the bound arithmetic, not rhetoric** - though my first
attempt at that arithmetic was wrong, so lead with the correction:

⛔ **I first published a ceiling of 8.3% and it was too low.** It counted
truncation only and forgot the rows whose quote asset we cannot value. Corrected:

| source of a possible miss | rows |
|---|---|
| truncated at rung 2 | **7** |
| ⛔ holds a vault in an asset we do not price (could be worth anything) | **3** |
| ⛔ a venue missing from the AMM map | ⭐ **0**, and that is MEASURED (below) |
| overlap between the above | 0 |
| **worst case additional rows** | **10** |

⭐⭐ **So the true ceiling is (3 + 10) / 120 = 10.8%**, and the honest headline is
**at least 2.5%, at most 10.8%**. ⛔ It still does not reach the 15% I predicted,
so the conclusion survives the correction - but the figure in my first write-up
was wrong and this replaces it.

### ⭐ Why the unknown-venue term is 0, measured rather than assumed

Run 2 persisted `unknown_programs` per row and **10 of 120 rows saw exactly one
unknown program**: `3s1rAymURnacreXreMy718GfqW6kygQsLNka1xDyW8pC`. I read the
account it owns.

⛔⛔ **`HWGoJ1HaMFUiDgfD7FVxMaYJAE2A5JjF7si6CgWSvRFQ` holds 31,487 token accounts
across 31,479 DISTINCT MINTS, plus 233.96 WSOL.** A pool holds one pair. An
account holding thirty-one thousand mints is a router or a sweeper, the same
family as the pump.fun fee program. It is now in `NOT_POOLS` **with that
measurement as the reason**, and ⭐ **adding it changes no verdict in the run** -
all 10 of those rows had already found a real pool - which is what makes it a
method fix rather than post-hoc tuning.

⛔ **And the underlying reason the ladder is a ladder at all:** resolving every
holder is not affordable. EMBER has **60,691** token accounts and batching all
their owners returned **HTTP 429** immediately. **Finding a pool is proof. Finding
none is not.**

## 7a. ⭐⭐ Run twice, fourteen minutes apart: IDENTICAL

Standing rule 16 is verify the output. So the whole sample was re-run to capture
the audit fields, and the second run is a reproducibility check:

| | run 1 | run 2 |
|---|---|---|
| sample (same 120 contracts, in order) | — | ⭐ **identical** |
| verdict changes across 120 contracts | — | ⭐ **0** |
| headline | 2.5% [0.85, 7.09] | **2.5% [0.85, 7.09]** |
| any pool at all | 87.5% [80.4, 92.28] | **87.5% [80.4, 92.28]** |
| venue split | 82 / 25 | **82 / 25** |
| RPC calls / wall | 778 / 239.8s | **778 / 240.0s** |

Run 1 is kept as `result_run1_authoritative.json` because it is the run the
pre-commit governs; run 2 is `result.json` and carries the audit trail.

### ⚠️ Two places the code differs from the rule, declared rather than buried

1. The pre-commit says the AMM map is *"the same one
   `analysis/gone_onchain/probe.py` uses"*. **`pooldiscovery.AMM_OWNERS` adds two:
   `moonshot` and `raydium_launchlab`**, both added before the sample ran.
   ⭐ This can only make discovery BROADER, so it cannot have deflated the
   headline - but it is a difference and the rule did not authorise it.
2. `NOT_POOLS` gained `3s1rAymU…` **after** the run, from the 31,479-mint
   measurement. ⭐ **Verified to change no verdict** (all 10 affected rows had
   already found a real pool), which is the only reason it is not tuning.

## 8. Two bugs the negative control caught before the sample ran

⭐ Neither cost a single sample row, because the controls ran first.

1. ⛔ **`_pools_from` counted ANY program-owned account as a pool.** The phantom
   EMBER surfaced **eight accounts owned by `pfeeUxB6…`, the pump.fun FEE
   program**, each holding ~112 trillion base units. Those are accumulated creator
   and protocol fees and nobody can sell into them. My pre-commit says a pool is
   an owner owned by a **known AMM program**; my code said "any program", which
   would have graded almost every mint as having a pool. Excluded owners are now
   **recorded with their program id** so a genuinely missing venue is visible.
2. ⛔ **Fetching vaults for those fee accounts cost 12 SECONDS PER CALL**, because
   each owns token accounts across thousands of mints. 120 contracts would have
   been hours instead of four minutes.

`test_pooldiscovery.py` 41/41 pins both, plus the verdict bands, the honest-null
rules, and the AST check that nothing in the module can sign or send.

## 9. ⭐ It is a permanent capability, not an experiment

`intel.liquidity(mint)` now falls back to on-chain pool discovery whenever the
indexer fails **or** answers `pair_count: 0`. The response carries
`source_that_answered`, `indexer_said`, `discovery_verdict`, `discovery_rung`,
`quote_reserves_usd`, `holders_reached` and `absence_is_a_floor`, and every
indexer-only field comes back in `not_checked` as **null with a reason, never 0**.

Contract: `docs/SITE_API.md` section 3. ⛔ **Still not wired to a page** - that is
the site session's work, so by this repo's own test it is IN PROGRESS, not
SHIPPED.

## 9a. ⚠️ What I did NOT do, and why

Frank's instruction named two methods: `getProgramAccounts` with filters, **or**
deriving PDAs where the program allows it. **I used the first and not the second**,
deliberately:

⭐ **Enumerating the mint's token accounts is venue-AGNOSTIC.** It finds a pool at
any venue whose vault owner I can classify, and it **records the owners it refused**
so an unknown venue is visible. Per-venue PDA derivation is strictly narrower: it
finds pools only at venues I have already thought of, and it would have found
nothing at `DsxdELwZ…` or `defAh9DW…` either.

⛔ **But PDA derivation is the specific fix for the GO-class miss**, and that is
worth saying plainly. The pump.fun curve and the PumpSwap pool are both derivable
from the mint, so deriving them would confirm those two pools **regardless of
whether their vault ranks in the top 100 holders by base amount**. That closes
cause 2 in section 5a. It needs the exact seeds per program, which is a coverage
task, not a rule change.

## 10. What should change in the record, and what needs its own pre-commit

⭐ **Safe to do now:** `gone` is the wrong word. The honest label for 80% of this
population is **pool exists, quote side under $10**.

⛔ **Needs its own pre-commit before anything is rewritten:** renaming the status
relabels outcomes across the whole record, and the three verified-sellable
contracts above mean some historical rows are wrong in a direction that affects
win accounting. That is BACKLOG A51's item and it is not a patch.

### The three follow-ups this run earned, in order of value

1. ⭐ **Derive the pump.fun curve and PumpSwap pool PDAs from the mint** (section
   9a). It closes the one miss cause that is ours rather than the market's.
2. ⛔ **Price non-SOL quote assets, or the $100 band will keep under-reading
   asset-paired tokens.** `docs/ASSET_PAIRED_TOKENS.md` already has the case:
   STONKBROS reads $0.03 on a SOL-only valuation and sells $100 for $94. Three
   sample rows are in the ceiling purely for this reason.
3. ⚠️ **Name `DsxdELwZ…` and `defAh9DW…`, or leave them named as unknown.** Both
   are executable programs holding real base tokens; both were `other` to the
   09-22 probe too. **Guessing a name for a program is worse than recording that
   we do not know it.**
