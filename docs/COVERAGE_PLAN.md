# Coverage expansion: the phased plan, ordered by measured volume

2026-09-22. Written in answer to Frank: *"Again why are we not covering
everything? Other chains, other launchpads too. I shouldn't have to call you out
that's something that you should recognize. We are working on one chain one
launcher right now I'm not sure how you can't figure this out."*

He is right, and the measurement is worse than the complaint. **Our program map
covers 51.7% of Solana venue volume.** The pump.fun-only graduation ledger sees
**14.4%** of the chain by volume, so it misses **85.6%**.

Backing research, 827 lines with every program id and its verification status:
`analysis/coverage_expansion/RESEARCH.md`.

---

## 0. ⛔ Corrections to figures I published earlier today

1. **Solana 24h DEX volume: $3,428,858,821** across 125 protocol rows (later read),
   not the $3,629,601,300 I used a few hours earlier. Venue-only volume
   **$3,294M**. BisonFi is **13.03%** of the all-protocol total and **13.56%** of
   venue-only, not the 12.2% in CLAUDE.md or the 12.3% I quoted. ⚠️ **DefiLlama
   moves through the day; any share quoted from it needs its read time attached.**
2. **Our coverage of Solana venue volume is 51.7%, not 46.4%.** The older figure
   counted all protocol rows rather than venues.
3. ⛔ **A bug in code I wrote today.** `analysis/daily_2026-09-22/pushback/pool_probe.py:47` had the USDT mint as
   `Es9vMFrJKsWFsFd8e25wJdkX8DBMLoMKNfuLDQy2Ae4Z`, which **does not exist on
   chain**. The real mint is `Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB`, which
   `onchain_reserves.py:35` has correctly. Fixed. ⭐ **No number I reported today
   was affected**: the constant only feeds a `return 1.0` fast path, so real-USDT
   pools fell through to `asset_usd()` and priced at $0.9999 from Jupiter anyway,
   and no vetted pool used USDT as its quote side. The damage was robustness, not
   accuracy: a Jupiter outage would have made a USDT pool read unknown.

**And one correction in the other direction, to the research itself.** It reports
the Raydium LaunchLab authority `WLHv2UAZm6z4KyaaELi5pjdbJh6RESMva1Rnn8pJVVh` as
having no account, and treats that as failing to verify it. ⭐ **That is the wrong
test.** An authority PDA is usually uninitialized: Raydium's CPMM authority
`GpMZbSM2…` exists only because something funded it, and both addresses return
signatures at the same block time when queried with `getSignaturesForAddress`. The
label stands, and the APR tracing that used it stands.

---

## 1. The measured board

### Solana: $3,294M of venue volume, 51.7% covered

| venue | 24h volume | share of venue vol | launches tokens? | we see it? |
|---|---|---|---|---|
| **BisonFi** | **$446,776,170** | **13.56%** | ⛔ **no** | ⛔ blind, and see §2 |
| pump.fun + PumpSwap | ~$522M | 14.4% | ✅ yes | ✅ |
| GoonFi | $159,500,000 | 4.8% | ⛔ no | ⛔ |
| Tessera V | $155,500,000 | 4.7% | ⛔ no | ⛔ |
| Scorch | $150,600,000 | 4.6% | ⛔ no | ⛔ |
| Manifest | $136,400,000 | 4.1% | order-book markets | ⛔ |
| Jupiterz | $80,800,000 | 2.5% | ⛔ no single program | ⛔ |
| QuantumAMM | $76,700,000 | 2.3% | ⛔ no | ⛔ |
| **StonkFun** | **$63,025,127** | **1.91%** | ⭐ **yes, 21% of all launches** | ⛔ |
| HumidiFi | $49,300,000 | 1.5% | 158k pool accounts | ⛔ |

### Other chains

| chain | 24h volume | the launch venue on it | its volume |
|---|---|---|---|
| **BSC** | $1,231,598,882 | Genius.fun | $3,074,539 = **0.2% of chain** |
| **Base** | $1,039,045,111 | ⛔ **Clanker, Zora and Virtuals do not appear as venues at all.** Four ordinary DEXs are 87.8% of the chain (Aerodrome Slipstream, Uniswap V3, PancakeSwap V3, Uniswap V4) | ZORA Coins **$11,064**, Virtuals **$10,469** |
| **Hyperliquid** | $639,733,250 | ⭐ **69% of venue volume is one order book behind one free unauthenticated POST** | HYPE $106.8M/day, PURR/USDC $3.29M/day |

⭐ **Three things fall out immediately:**

1. **The launchpads on other chains are noise.** Genius.fun is 0.2% of BSC. ZORA
   Coins and Virtuals do **five figures a day**, and a pool-account census finds
   Heaven, Boop and Virtuals-Solana all reporting **$0** of 24h volume. Anyone
   proposing a Zora parser is proposing a week of work for $11k of daily flow.
   ⛔ **My earlier sketch had them in phase two. The measurement says that was
   wrong.**
2. **The volume on other chains sits in ordinary DEXs and order books**, not in
   launch venues.
3. **Hyperliquid is the real other-chain gap:** $640M/day, zero coverage, and
   Frank's own HYPE and PURR live there.

---

## 2. The ordering question Frank asked directly

> *"Stonk Fun moves to phase one ahead of BisonFi unless you can show BisonFi is
> bigger. Justify the order with measured volume, not my say-so."*

⭐ **BisonFi is bigger. $446,776,170 against $63,025,127, a factor of 7.1.** That
is the honest answer to the question as asked.

⭐⭐ **And Frank's instinct is still right, for a reason neither of us had. I
verified it myself just now:**

```
BisonFi program  BiSoNHVpsVZW2F7rx2eQ59yQwKxzU5NvBcmKshCSUypi
  executable: True, owner BPFLoaderUpgradeab1e...
  getProgramAccounts: 17 accounts
```

**$446.8 million a day through SEVENTEEN accounts.** BisonFi is a proprietary
market maker, not a launchpad and not a per-token AMM. It has no per-token pool,
and **nothing launches there.** GoonFi (35 accounts), Tessera V (29), Quantum (37)
and Flux (7) are the same shape: roughly **300 accounts carrying 30% of Solana
venue volume**, with nothing to discover, nothing to enumerate and no token-level
state to read.

**So parsing BisonFi would add market-maker inventory, not token coverage.** It
drops out of phase one entirely, and not because it is small.

**StonkFun goes first, and its 1.91% understates it three ways:**

- ⭐ **It is 21% of all launches.** In the research's 210-row sample:
  `pump.fun` 148, `stonkfun` 44, `met-dbc` 6. My own pass minutes ago: pump.fun
  24, stonkfun 3, letsbonk.fun 1, met-dbc 1 out of 30.
- Graduated stonk.fun tokens trade on Raydium CLMM/CPMM and Meteora DLMM, so their
  volume is counted under those venues, not under StonkFun.
- ⛔ **Its tokens are the ones that break our numbers.** Token-2022 with a 100 to
  300 bps transfer fee, in pools quoted in ZEC, wNEAR, COPX and STONK. **Our depth
  reader returns $0 for every one of them.** STONKBROS read $0.03 of chain depth
  while Jupiter sold $100 of it for $94.11. A venue we price at zero is worse than
  a venue we cannot see, because zero looks like an answer.

⚠️ **StonkFun's program id is UNVERIFIED and the research could not find it.**
That used to be the blocker. It is not any more, because of §3 phase 1.

---

## 3. The plan

Effort is my own working hours. Each phase names **what is observed** when it is
done, not what is written. Nothing is shipped until it runs unattended and its
output reaches the site or Discord (`docs/BACKLOG.md`).

### Phase 0: stop lying about depth. About 3 to 4 hours. First, because everything else reads through it.

1. **Price any quote asset.** Port `asset_usd()` and `quote_usd()` from
   `analysis/daily_2026-09-22/pushback/pool_probe.py` into the depth path. ⛔ It
   must land in **all four copies** of `resolve.exit_depth_usd` (`resolve`,
   `scanner`, `watchlist`, `paper`) or the divergence `test_depth.py` tracks gets
   worse. BACKLOG A53.
2. **Persist the quote mint and quote symbol on observation rows.** Same shape as
   the `token_name` fix (A48): the value is in the payload and
   `journal.record()`'s whitelist eats it. Without it we cannot ask what any
   historical row was paired against, which is exactly what the copper correction
   needed. BACKLOG A55.
3. **An unpriceable quote asset renders as `unknown`, never $0** (standing rule 5),
   and the win gate treats unknown as unchecked rather than passed, which is the
   `authority_live=None` shape again.

**Observed when done:** a ZEC-quoted row carries a non-null depth and a
`quote_symbol`; STONKBROS reads near $94, not $0.03.

### Phase 1: ⭐ one free endpoint replaces most of the launchpad problem. About 4 to 6 hours.

`GET https://lite-api.jup.ag/tokens/v2/recent`, keyless, 200, 30 rows, about 0.7s.
**I called it myself and read the payload.** Each row carries:

```
id  symbol  name  launchpad  dev  holderCount  usdPrice
audit    { mintAuthorityDisabled, freezeAuthorityDisabled,
           devBalancePercentage, devMints }
firstPool{ id, createdAt }
```

⭐ **That is nearly everything our launch-side enrichment computes, for every
launchpad at once, in one free call.** `launchpad: "stonkfun"` labels stonk.fun
directly, **so StonkFun coverage no longer waits on finding its program id.**

⚠️ **Cadence, per standing rule 13, measured before use:** 30 rows span a median
47s, about **38 launches/minute**. A **30-second poll cannot miss**; a 60-second
poll drops rows. ⛔ **The feed is the sampler, so the interval is not a preference,
it is a correctness condition.** This is also the honest answer to the 1.26% launch
coverage figure in `COVERAGE.md`, which was never a pump.fun problem.

Alongside it, two cheap stonk.fun specifics:
- Read `transferFeeConfig` on every Token-2022 mint and **surface the fee as an
  explicit cost line**. A 3% tax is 3% off entry and 3% off exit.
- ⛔ **Flag a live `transferFeeConfigAuthority` as a capability**, exactly like a
  live mint authority. `safety.py` already has the shape.
- ⭐ **Cross-check the feed against chain, do not trust it** (rule 16 and rule 17):
  the fee authority `5KXDF6QnqhBj72hDtJNkkpFaQVUfbFXNybMsp3DiK6tD` touches every
  stonk.fun token to harvest its fee, so paging its signatures independently
  enumerates the same universe, the way `graduations.py` pages pump.fun's
  migration authority. **Two sources, one of them ours.**

**Observed when done:** rows appear unattended for a launchpad that is not
pump.fun; a stonk.fun token reaches the universe with its fee and paired asset
shown; the two enumerations agree on a stated fraction.

### Phase 2: pool discovery for the per-token venues. About 2 to 3 hours per venue, cheaper than I said this morning.

⭐ **The research found that `onchain_reserves.vaults()` is layout-independent**
and proved it live on **Meteora DAMM v2, Meteora DBC, Bags and PumpSwap.** So
reserve parsing is largely already done and my earlier "one new vault layout per
venue" estimate was pessimistic. **The missing piece is pool discovery.**

- ⭐ **One PDA does four venues at once:**
  `FhVo3mqL8PW5pH5U2CN4XE33DokiyZnUwuGpH2hmHLuM`, the Meteora DBC vault authority,
  covers DBC and therefore **Bags, Believe and Moonshot-labelled** tokens.
- ⛔ **Meteora DBC is not optional: EMBER was a DBC launch and I called it a
  pump.fun token in a report.**
- Per-token venues by pool-account census: LaunchLab **1.4M** pool accounts (429 B
  each), Moonit 220k, HumidiFi 158k, Heaven 50k, Boop 50k, Virtuals 18k, Manifest
  4k order-book markets. ⚠️ **1.4M accounts is not something to `getProgramAccounts`
  casually**; discovery there has to be signature-driven or feed-driven.
- Program ids for Scorch, Manifest, Quantum, HumidiFi, Kipseli, Flux, Quay, Heaven,
  Boop, Moonit, Meteora DBC/DAMM v1/DAMM v2/DLMM, Raydium LaunchLab, Virtuals,
  AlphaQ, Byreal, SolFi V2, WhaleStreet, Deriverse and both Bags fee-share programs
  are **VERIFIED executable** in `analysis/coverage_expansion/RESEARCH.md` §5. Jupiter's free
  `/swap/v1/program-id-to-label` supplied 107 of them.

**Observed when done:** a Meteora DBC pool's quote-side depth read from its own
vaults agrees with Jupiter's round trip on at least 10 tokens, within a stated
tolerance.

### Phase 3: Hyperliquid. About 8 to 12 hours.

$639,733,250/day, and Frank holds HYPE and PURR there. ⛔ **None of our AMM
machinery applies.** HyperCore spot is an order book, so "liquidity" is not a pool
balance and `exit_depth` has no meaning. The honest number is what the book fills
at his size, which `analysis/tickers_2026-09-22/hyperliquid.py` already computes by
walking `l2Book`: HYPE round-tripped $2,000 for **0.004%** today, while PURR's book
**did not fill a $2,000 sell at all**, stopping at $1,547 of visible bids.

Verified endpoints, all keyless POSTs to `api.hyperliquid.xyz/info`: `spotMeta`
(503 tokens, 330 pairs, each token's `evmContract`), `spotMetaAndAssetCtxs`,
`l2Book` (20 real levels per side), `tokenDetails`, `candleSnapshot`,
`validatorSummaries`, `delegations`, `delegatorSummary`,
`spotClearinghouseState`. HyperEVM is chain 999 with a keyless RPC; WHYPE is
`0x5555...5555`.

⛔ **Three traps, all confirmed:**
- **`ctxs` has 869 entries against 330 universe entries and is NOT index-aligned.**
  Keying by list position silently mislabels every price. It gave me a $0.0016 mid
  for HYPE before I keyed on `universe[i]["index"]` and got $97.03, which
  cross-checks against bridged HYPE on Solana at $96.82.
- `l2Book` returns top levels only, so any total is **"visible levels"**, never the
  whole book. Label it that way or it becomes the next 781x.
- **HYPE has no ERC-20** (`evmContract: null`), and `evm_extra_wei_decimals` ranges
  from -2 to +13. Token names on HyperCore are not unique, so key on the token
  index and `tokenId`: the contract-over-ticker rule in its Hyperliquid form.

**Observed when done:** HYPE and PURR appear in the universe with a book-walked
round-trip cost at $500 and $2,000, labelled as an order book, not a pool.

### Phase 4: ⛔ BisonFi and the other proprietary market makers. Demoted, not scheduled.

$446.8M/day through 17 accounts; ~300 accounts across the seven PMMs carrying 30%
of venue volume. **Nothing launches there and there is no per-token pool to read.**
Jupiter already routes through them, so their liquidity **already reaches
`chainfields.round_trip()`**, which is the number we actually trust. What we lose
by not parsing them is an independent cross-check on fills we can already price,
and the research notes adding them is cheap precisely because they are tiny in
account terms. **Do it when the cross-check is the binding constraint, which it is
not today.**

### Phase 5: ⛔ Base and BSC launchpads. Not scheduled. Deliberately.

Genius.fun 0.2% of BSC; ZORA Coins $11,064/day; Virtuals $10,469/day; Clanker,
Zora and Virtuals do not appear as Base venues at all. **These do not earn a
parser.** Revisit only if one crosses about 1% of its chain's volume, which is a
threshold, not a vibe. If we want Base coverage, the volume is in four ordinary
DEXs and that is phase-2-shaped work.

⚠️ **And a warning for whoever does the EVM side:** `cloudflare-eth.com` answers
`eth_chainId` with `0x1`, then returns `"0x"` for WETH's code and `Internal error`
on every `eth_call`. A reader pointed at it **would conclude Uniswap does not
exist.** Standing rule 16, in a new chain's clothing.

---

## 4. What this plan refuses to do

- ⛔ **No new paid feed.** Helius RPC (keyed, already held), Jupiter lite-api,
  DefiLlama and `api.hyperliquid.xyz`. Cost of the whole plan: **$0/month.**
- ⛔ **No venue gets a coverage claim from a passing test.** Every
  observed-when-done line is a chain measurement on real tokens.
- ⛔ **No third-party feed is load-bearing alone.** The Jupiter launch feed is
  AGGREGATE under rule 17, so phase 1 ships with the chain-side enumeration beside
  it.
- ⛔ **No forward-looking scoring anywhere in it.** Every phase adds description of
  what already happened. Marino governs anything that ranks tokens by expected
  return.

## 5. The open unknowns, named

1. **StonkFun's program id.** Not found. $63.0M/day and 21% of launches. Phase 1
   routes around it via the `launchpad` label and the fee authority, but the id
   would let us read its curve state directly.
2. **Jupiterz**, $80.8M/day, has no single program to point at.
3. **Believe's role.** Its circulated authority exists but has been quiet 54.9
   days.
4. **Arc's memecoin venue.** CLAUDE.md says Arc has none; the CryptoGorilla recaps
   claim ARGUS, TOLLY and LONG launched there. Unresolved, and cheap to settle.
