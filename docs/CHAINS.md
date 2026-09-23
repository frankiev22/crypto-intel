# Chains and venues

Written 2026-09-17. Research only. **No code was written or modified, no account was
created, no trade was placed, no funds were moved.**

Two parts. Part 1 is the chains Fomo supports and what covering each would cost us.
Part 2 is the venue comparison, reframed around Frank's mid-task instruction:
**safety is a gate, then fill quality, then fees, then chain coverage.**

---

# Part 1 — The chains

## 1.0 The list, verified rather than assumed

Fomo's help centre lists six: **Solana, Base, BNB Chain, Monad, Ethereum, Robinhood
Chain.** Fee treatment differs across them and that difference is itself informative:
Fomo covers gas, priority fees and token rent on Solana, Base, BNB Chain, Monad and
Robinhood Chain, and **passes network fees through on Ethereum** "due to higher
on-chain costs."

Source: `help.fomo.family` trading-fee article, quoted with retrieval date by
FomoAppGuide, verified 2026-08-20. **Both sites carrying this are referral-affiliate
sites.** Fomo's own Terms, rewritten 2026-08-17, name no fee figure outside perps and
reserve the right to change the schedule "at any time in its sole discretion," so the
binding number is the one on the confirmation screen.

## 1.1 The size of each market

DEX volume, DefiLlama API, all pulled within minutes of each other **2026-09-17**:

| chain | 24h DEX volume | 7d | vs Solana |
|---|---:|---:|---:|
| **Solana** | $2,703,297,666 | $18,124,096,493 | — |
| **Robinhood Chain** | $1,543,159,491 | $12,778,542,046 | 57% |
| **Ethereum** | ~$1,495,000,000 | — | 55% |
| **BNB Chain** | $1,245,311,950 | $8,650,646,542 | 46% |
| **Base** | $1,035,945,629 | $6,446,428,134 | 38% |
| **Monad** | $132,665,994 | $765,392,321 | 4.9% |

**The surprise is Robinhood Chain at 57% of Solana**, two and a half months after mainnet
(2026-07-01). It is developed below and most of that number should be discounted.

**Trackers disagree badly on Monad** and this is worth knowing before trusting any
single source: DefiLlama $131–150M, GeckoTerminal $28.72M, Dexscreener $5.0M, same
day. That is a 26× spread. Different coverage and methodology; **do not treat any of
them as the number.**

## 1.2 Per chain

### Solana — the only one worth our attention, and we already cover it

| | |
|---|---|
| DEX volume | $2.70B/24h, #1 |
| swap cost | base 5,000 lamports + priority + tip ≈ **$0.005** uncontested; $3–7 on a contested launch |
| launchpad | **pump.fun dominant.** Share estimates disagree by metric: 85.9% of issuance (Bitget, Feb 2026), ~90% (CoinMarketCap Academy), ~62% of launchpad revenue / 55% of volume in another window. They measure different things |
| launches/day | record **263,000+ in one day on 2026-09-09** (Cryptopolitan, Cryptonomist, ret. 2026-09-17) |
| bot share | **[UNVERIFIED for 2026.]** The only published measurement is sandwich bots at 2.9% of daily DEX volume (range 1.7–5.4%), Flipside via SolanaFloor — **dated March 2025**. No 2026 bot-vs-human share of memecoin volume exists |
| free data | Dexscreener (60/min, no key, **no paid tier exists**), GeckoTerminal (10/min on-chain), Helius (1M credits/mo, 10 rps, **permanent free**) |
| coverage cost to us | **$0. Already built, already running, 11% of the Helius free tier.** |

**Verdict: this is the chain. Stay.** Not because it is good, but because it is the
only one where our coverage cost is zero and our instrument already exists.

### Robinhood Chain — the interesting one, and mostly not real

| | |
|---|---|
| what | permissionless EVM L2 on Arbitrum Orbit/Nitro, ~100ms blocks, **gas token is ETH**, chain ID 4663 |
| mainnet | **2026-07-01** (public testnet 2026-02-10) |
| DEX volume | $1.54B/24h, #2 of the six |
| launchpad | **Pons**, overwhelmingly dominant. Bonding curve, 1B supply, 4.2 ETH reserve, auto-migrates to Uniswap. **~20,000 coins/day** in late Aug 2026. Distinctive: creators can back a coin with a tokenized stock (NVDA, SPY, TSLA, GME) and over a third do |
| user gas cost | **$0 today** — subsidised. Underlying network median swap cost rose **$0.012 → $0.48 (40×)** between Aug 22 and Sep 3 (Bitquery on-chain audit, verified 2026-09-04) |
| free data | Dexscreener slug `robinhood` (28,296 pairs), GeckoTerminal network `robinhood`, DefiLlama `robinhood-chain`. **Not on Birdeye.** Public RPC + Blockscout explorer |

**Three findings that gut the volume number, all from Bitquery's own on-chain audits:**

- **79% of the gas-demand spike came from 8 addresses** — a swap router "with the shape
  of arbitrage," a settlement contract whose 31 wallets trace to a single funding
  wallet, and ERC-4337 bundlers.
- On Pons, **~1,000 wallets each making 1,000+ trades account for over 25% of all
  volume**, nine of which "look like one owner."
- Volume hit **18× TVL** on some days; a FalconX-cited analysis says wash trading
  "can't be ruled out." Stock tokens, the chain's stated purpose, are only **~9% of
  volume** ($3B of $34.6B).

**And the subsidy is reportedly ending.** crypto.news (2026-09-04) and CoinGape
(2026-07-11) independently report a 90-day gas subsidy from July 1 expiring around
**2026-09-29**. ⚠️ **Robinhood's own docs do not mention a subsidy, a free-gas
programme, or an expiry anywhere.** Treat the date as consistently-reported inference
from on-chain fee data, **not a primary-source fact**. Corroborating signal: daily fees
went $3.75M (Sep 1) → $4.45M (Sep 2) → **$1.06M (Sep 11) — a 76% fall from the Sep 2 peak,
despite record trading volume.**

⛔ **One hard blocker, and it is not about data.** Robinhood's Stock Tokens are **not
available to US persons**. Frank is in New York. The distinctive thing about this chain
— stock-backed memecoins — is the part he cannot legally access, and it is only 9% of
volume anyway.

🚩 **Source-integrity flag.** A search for the subsidy expiry surfaced a GitHub release
note (`Ricosworks1/blockchain-payment-flow-analysis`, titled like a market update,
claiming $47B volume) ranking alongside real journalism. A GitHub release is not a news
source and this has the shape of SEO-injected content. It was not used. Separately, a
fetch of `api.geckoterminal.com` returned a page-injected redirect to `sandwiched.me`,
which was not followed — **worth knowing if anything here ever scripts against that
endpoint.**

**Verdict: no.** Two months old, gas economics about to change by an unverified date,
volume with three independent wash-trading indicators against it, and the one feature
that differentiates it is closed to him.

### Base — the credible second, and still not worth it

| | |
|---|---|
| DEX volume | $1.04B/24h |
| swap cost | L2 min base fee 0.005 gwei ≈ $0.0024 execution-only; blogs say $0.01–$0.10 all-in. **Base's own docs say the L1 security fee is typically larger than the L2 fee, and no current USD figure for it was found** |
| launchpads | **Zora and Clanker.** Zora reported at 92.5% share on a single day (2026-07-28 — one-day snapshot, not a trend). Clanker peaked ~13,000 launches/day in Feb 2026, record 21,870 in a day |
| launches/day, current | **not found** |
| graduation rate | **not found — no Base launchpad publishes one** |
| bot share | **not found.** No dashboard, report or research piece quantifies it |
| free data | Dexscreener ✓, GeckoTerminal ✓, Alchemy free tier ✓ (30M CU/mo, permanent) |

**Verdict: the only chain here with a real case, and the case is still no.** It has
38% of Solana's volume, working free data, and a live launchpad ecosystem. What it does
not have is **any published graduation rate, any bot-share measurement, and any
equivalent of the 832,941-launch literature we lean on for Solana.** Every threshold in
this repo would have to be re-derived from scratch against nothing.

### BNB Chain — no

$1.25B/24h, swap ≈$0.007–0.02 (calculated from the official 0.05 gwei minimum, not a
published swap figure). Launchpads GraFun (~13,000 tokens), four.meme (~6,800), Flap
(~250) — **but the source is DWF Labs research dated 2024-10-18 and "updated 9 March
2026," and the underlying counts may not be genuinely refreshed.** Four.meme's
graduation threshold is reported as 18 BNB by one source and 24 BNB by another; they
disagree. Whether the four.meme boom persisted into 2026: **not found.** Bot share:
no percentage exists; the best available is an ACM paper (DOI 10.1145/3736763, June
2025) giving absolute counts — 44,471 sniper bots, 1,716,917 operations, $137.5M
turnover — with **no denominator published**.

**Verdict: no.** Half Solana's volume, stale launchpad data, and no measurable base
rate.

### Ethereum — no, and for a reason worth recording

**The one genuine surprise in this research: Ethereum gas is currently negligible.**
Etherscan gas tracker, 2026-09-17: 0.179 gwei standard, ETH $2,421.85, Etherscan's own
calculator quoting **a swap at $0.154 standard / $0.17 rapid.** (A search snippet of
the same page at the same timestamp showed 0.055 gwei — intraday swing or caching;
either way, sub-0.2 gwei.)

That inverts the usual assumption. It does **not** make Ethereum a memecoin venue:
there is still **essentially no bonding-curve launchpad ecosystem on mainnet**,
multiple sources attributing this to the years when gas did push the model to Solana
and Base. Launches per day: not found, because there is nothing to count.

Also note this is the **one chain where Fomo passes network fees through** rather than
absorbing them, so the cost model in `TRADING_PLAYBOOK.md` Part 4 does not apply.

**Verdict: no.** Deep liquidity, no launch stream.

### Monad — no, with a note

Mainnet **2025-11-24** (The Block). $133M/24h, 4.9% of Solana. DEX concentration is
extreme: **Kuru is ~75%** of it. Native launchpad **nad.fun** exists but GeckoTerminal
showed the launchpad category at only **1,117 txns/24h** against 120k+ chain
txns/day — launchpad activity is a small slice. Record $513M single-day volume on
2026-09-08 after the MIP-8 gas upgrade (activated 2026-09-02, cut clustered
storage-read gas ~98%). Both Dexscreener and GeckoTerminal index it.

The note: **Blockvision's Monad Indexing API is Pro-only at $199/mo**; the free tier
gets raw JSON-RPC only. So Monad is the one chain here where the indexed-data path has
a real price on it.

**Verdict: no.** 5% of the volume, one DEX holding three quarters of it, and the
trackers disagree by 26×.

## 1.3 What coverage would actually require

Two aggregators cover **all six chains for free** and are already what this project
uses:

| | free limit | key | paid tier |
|---|---|---|---|
| **Dexscreener** | 60 req/min per endpoint | no | **none exists** — no pricing page |
| **GeckoTerminal** | **10 calls/min** (on-chain endpoints) | no | CoinGecko Basic $35/mo → 250/min |

GeckoTerminal network IDs verified by paginating all three pages of
`api.geckoterminal.com/api/v2/networks` (229 networks): `solana`, `base`, `bsc`, `eth`,
`monad`, `robinhood`. **All six present.**

**So the naive answer is that multi-chain coverage costs $0 in data fees.** That answer
is wrong, and `COVERAGE.md` already explains why: GeckoTerminal's `/new_pools` feed dies
at page 10, spans ~37–67 seconds of launches per page, and a residential IP sees 429s
at 20 calls/min. **We already observe only ~1.9% of the Solana launch stream on a
rate limit we are saturating.** Adding chains divides that budget; it does not add to
it.

The RPC/indexer layer, for the record:

| provider | chains of the six | free tier | permanent? | first paid |
|---|---|---|---|---|
| **Helius** | Solana only | 1M credits/mo, 10 rps | **permanent** | $49/mo |
| **Alchemy** | SOL, Base, BNB, ETH | 30M CU/mo, 25 rps | **permanent** | PAYG $0.525/1M CU |
| **Ankr** | SOL, ETH, Monad | 200M credits/mo freemium | permanent | $0.10/1M credits |
| **Codex** | **all six** | 10,000 req/mo, 5 rps | permanent, gated by a **$1 card verification** | $350/mo |
| **The Graph** | SOL, Base, BNB, ETH | 100,000 queries/mo | permanent | $2/100K |
| QuickNode | all six | 10M credits | **TRIAL, 1 month** | $49/mo |
| Bitquery | SOL, Base, BNB, ETH, RH | 10K points | **TRIAL, first month** | $49/mo |
| Birdeye | all but Robinhood | 30,000 CU/mo, 1 rps, **3 endpoints only** | permanent | $99/mo *(their own two pages disagree — docs say $99/3M CU, pricing page says $39 Lite / $99 Starter, both 8M CU)* |
| Blockvision | Monad, ETH, BNB | 10M CU/mo | permanent, but **Monad indexing is Pro-only $199/mo** | $29/mo |
| **Moralis** | all six | **NONE — free plan discontinued 2026-09-01** | retired | **$149/mo** |

⚠️ **Moralis is the trap.** Cached pages and its own FAQ still describe a free tier; the
live pricing page shows it ended 2026-09-01. Anything written before September that
recommends Moralis as the free multi-chain option is now wrong.

**Alchemy's permanent 30M CU/mo free tier covers Solana, Base, BNB and Ethereum in one
key**, which is the single most useful line in that table if multi-chain ever happens.
At the ~114k calls/month this project actually consumes (`ONCHAIN_COST.md`), 30M CU is
roughly 8% utilisation.

## 1.4 The chains verdict

**No non-Solana chain earns Frank's attention, and the reason is not volume.**

Base has 38% of Solana's DEX volume and free data on both aggregators. On volume alone
it is arguable. What kills it, and kills every alternative, is the **measurement
asymmetry**: Solana has 832,941-launch survival analysis, a 655,770-token breakeven
study, a 6.4M-token rug dataset and a 41,000-launch entity-linked dataset. Base has a
one-day launchpad market-share snapshot and no graduation rate at all. **Every
threshold, base rate and prior in this repository would have to be rebuilt from
nothing**, on a chain where nobody has published the denominators.

And the binding constraint is not chain count. It is that we see **1.9% of one chain's
launch stream** and `GAPS.md` W2 already rules coverage a near-wall that does not
matter for trading — because if there is no edge, seeing more launches produces more
losing trades.

**Adding a chain multiplies a negative number.**

The one thing worth doing costs nothing: `venue.py` already classifies `dex_id`, and
Dexscreener returns a `chainId` on every payload. **Recording the chain on every
observation, while continuing to collect only Solana**, means that if this ever changes
the history exists. Nothing can be measured later that was not recorded now.

---

# Part 2 — Venues

Reframed per Frank's instruction: **safety is a gate, then fill quality, then fees,
then chain coverage.** Anything failing the safety gate is out regardless.

## 2.0 Correction: two premises in the brief

**1. BullX is not an option. Trading has been suspended since 2026-06-01.**
Announced via official Discord 2026-05-31, effective 00:00 UTC. Wallets and
withdrawals reportedly continue; trading does not. No timeline, no roadmap, no feature
announcement since. (crypto.news 2026-06-01; PANews.)

Corroborated by usage: **BullX did $953.64 in Solana fees over 30 days** against
Axiom's $41.11M (DefiLlama, 2026-09-17). That is not a rounding error, that is a
shutdown. `neo.bullx.io` still serves an app shell; its changelog was last touched
**September 2024**.

**BullX and BullX Neo are not different products.** Neo (v2) launched ~2024-12-11, same
team, shared docs, shared fees, shared ToS. Treating Neo as a separate, safer thing is
not supported.

**2. The Axiom insider story is real, and the version in circulation overstates what
was admitted.** Developed in 2.1.

## 2.1 Safety gate

⚠️ **Scope of this gate, stated so the verdict in §2.6 is not read as more than it is.**
I ran a full safety workup on **Axiom and BullX only**, because those are the two Frank
named. **Jupiter, Trojan, Fomo and the rest were checked for custody model and for
"any security incident found", and that is not the same thing.** A not-found on a
platform I did not investigate in depth is weak evidence. Treat §2.6's rankings
accordingly.

### Axiom — passes, with two live caveats

**The February 2026 incident, verified against primary sources.**
2026-02-26: ZachXBT published an investigation (thread
`x.com/zachxbt/status/2027016064534757659`); Axiom responded the same day
(`x.com/AxiomExchange/status/2027018976929423583`). Both reported by The Block and
CoinDesk.

Named: **Broox Bauer**, senior business-development employee. Alleged conduct: used
**internal customer-support dashboards** to look up any user by referral code, wallet
address or UID; shared screenshots of private wallet data (April and August 2025);
helped compile a sheet of KOLs' undisclosed wallets. On audio, described ramping up
lookups gradually "so it does not look that suspicious." Several people named
independently confirmed the wallet data was accurate.

Axiom's statement, in full, because the wording is the finding:

> "We are surprised and disappointed to hear that someone on our team abused internal
> customer support tools to look up user wallets. We have removed access to these
> tools and will continue to investigate and hold the offending parties responsible."

**They confirmed the data abuse. They did not confirm insider trading.** ZachXBT
himself was explicit that he could not establish it — CoinDesk reports he "cautioned
that without access to Axiom's internal logs, it is difficult to establish
high-confidence examples of insider trading based solely on on-chain data."

So the honest read: **confirmed surveillance capability and confirmed misuse of it;
alleged but unproven front-running.** That is still serious — staff could query your
wallet graph — but "Axiom admitted front-running its users" is not what happened.

⚠️ Two sourcing notes. The widely-repeated **$400,000 figure is not in The Block or
CoinDesk**; it appears only in aggregation. And the framing that reached me came from
**Trojan's own marketing blog, a direct competitor**, which overstated the admission.
It did not invent the incident.

**[UNVERIFIED] The SSN claim.** The allegation that Axiom demanded name, address and
SSN to release rewards around end-2025 could not be verified. Axiom's own docs across
six pages — signup, fees, rewards, points, referral, FAQ — **mention no KYC, no SSN, no
identity gate on rewards**, and advertise an explicitly no-KYC fiat on-ramp. That is
evidence against, not a refutation of a one-off event. **Do not act on it either way.**

🚨 **The live risk, and it is nine days old.** 2026-09-09, Socket Threat Research:
four malicious Chrome/Firefox extensions (`J7Tracker`, `VREO` ×2, `Orbit Tracker`)
harvest **authenticated Axiom session tokens, `bundleKey`, `sBundles`, `eBundles` and
cookies** and exfiltrate them. Chrome listings were pulled in July 2026; **`Orbit
Tracker` was still live on Firefox at publication.** Socket's assessment: "a direct
path from a malicious browser extension to account compromise and cryptocurrency
theft."

**This does not exploit Axiom — it runs inside an already-logged-in browser session.**
It names **Axiom and Padre/Pump.fun Terminal only, not BullX**. IOCs are in the source.
Practical implication: a clean browser profile with no extensions, for trading only.

**Custody: the best in the survey.** Turnkey (third-party non-custodial key
management), email/Google/Phantom signup, **no KYC**, and — the important one —
**"Access your recovery phrase at any time in your settings."** Unlimited export, not
one-shot. Axiom's own docs recommend importing the phrase into Phantom or Solflare
"to ensure that you always have direct access to your funds under any circumstances."
No withdrawal allowlist.

**Still maintained:** yes. #1 by Solana terminal fees. But revenue is falling hard:
Q3 2025 $225.92M → Q4 2025 $92.34M → Q1 2026 $94.33M → Q2 2026 $57.98M (DefiLlama).
Team is pseudonymous ("Mist", "Cal") but **Y Combinator W25**, so real legal identities
exist behind a real company.

**Gate: PASS**, conditional on a dedicated extension-free browser profile and on
knowing that staff have historically been able to see your wallets.

### BullX / BullX Neo — fails, on availability before anything else

**Gate: FAIL.** Trading suspended since 2026-06-01. Nothing else matters.

For completeness, because Frank used it and may still have funds there:

- **No platform-level compromise was found** — no exploit, front-end/DNS hijack,
  drainer or database leak from any primary source, named firm, ZachXBT, Rekt, court
  filing or established press. **Caveat: X was not searchable during this research, and
  X is where a Solana-native incident surfaces first. Treat as "not found," not
  "clean."**
- The 2024 "drain" was a rumour BullX publicly denied ("There is no drain. Confirmed.")
  What followed was individual Telegram takeovers and phishing, not a platform breach.
- **Verified, named-firm incident, 2025-05-08:** Socket found npm packages
  (`pumptoolforvolumeandcomment`, `debugdogs`) that scan local files and **grep
  specifically for filenames containing "BullX"** to steal private keys.
- **That malware is downstream of BullX's own design.** BullX gives you the private key
  **exactly once** — *"BullX will only provide you with your private keys one time and
  cannot recover them for you in the future"* — which pushes users to save keys into
  local plaintext files. **The one-shot export policy manufactured the exact artifact
  the malware searched for by name.**
- Auth root is **Telegram**, and "2FA" is a user-set 6-digit PIN, not TOTP. That
  explains the recurring "Telegram compromised → BullX drained" pattern.
- Withdrawals go to a **pre-registered allowlisted address only.**
- Fully anonymous team ("BullX Labs, Inc."). ToS requires you are **not a US
  resident** — Frank is. Promised security/audit documentation from 2024 was never
  published.
- The `$BULLX` airdrop, farmed from July 2024, **never happened.** Trustpilot 1.6/5,
  96% one-star on 24 reviews — though at least four of those are fund-recovery scam
  bait, so read it as directional sentiment, not a failure rate.

**If Frank still has a balance on BullX, getting it out is the only action item here.**

### Custody, ranked — the real differentiator

Headline fees are commoditised at ~1% across the terminals. Key custody is not, and the
spread is wide:

| tier | platforms |
|---|---|
| **Full export, anytime, arbitrary withdrawal** | Jupiter, Trojan (Privy), Axiom (Turnkey), Nova |
| One-time key reveal, ever | **Photon**, BullX, Bloom |
| **No export at all** | **Banana Gun** (docs say plainly "you can't"), **Maestro** (keys AES-encrypted on Maestro's servers — custodial in practice), **GMGN** (export prohibited even for keys you imported; whitelist + 2FA + 3h/24h time locks) |

⛔ **Anything in the bottom tier fails the gate.** A platform that will not give you
your key is a custodian that has not said so.

## 2.2 Fill quality — the honest state

Frank's read, from use: **Fomo has bad fills, good UI, good social trading.** I am
taking that as his measurement and I am not going to argue with a user's own
experience. But I could not corroborate it, and the reason is worth stating.

**I found no independent execution-quality audit of any of these venues, and every
fill-quality claim I did find is self-published.** Stating it as "none exists" would be a
universal negative from a constrained search — Reddit and X were both inaccessible to the
tooling used — and it would also be wrong in spirit, because **independent measurement of
execution harm on Solana does exist**: Gerzon et al., IMC '25, 521,903 sandwiches and
$7.7M of victim losses over four months, peer-reviewed. What does not exist is anything
comparing *these venues against each other*. The self-published claims:

- Jupiter's Ultra V3 release claims **+0.6 bps average positive slippage** against
  "−1 bps to −14 bps on other platforms" and **34× better sandwich protection** — with
  no methodology, no named comparison set, no third-party replication.
- DFlow, which **Fomo confirms on its own site that it routes through**
  (`fomo.family/answers/is-fomo-app-safe`: "Trades execute through DFlow for secure,
  fair order routing"), publishes volume and integration counts and no execution
  quality data.
- **No published comparison of realised slippage between any two of these venues
  exists.**

### What I did find out about DFlow, because it is the mechanism most likely to explain a bad fill

Two architectures exist under the same name and the marketing conflates them.

**The 2022 design** was an order-flow auction: market makers *"purchase the right to
fill future order flow"* in on-chain auctions, and were *"programmatically required to
fill within a governable threshold of the best price"* per a Pyth oracle. **That is a
mechanism that would systematically trade fill quality for sandwich protection.**

**The currently documented product has none of it.** No auction, no purchase of
exclusivity, no Pyth, and **no price threshold mentioned anywhere.** What is documented
instead: off-chain "endorsers" attach a signed toxicity signal (an 8-byte float in
[0,1]) to a transaction; DEXs and prop AMMs read it and voluntarily quote better prices
to flow marked non-toxic. DFlow charges **no protocol fee** and **does not take
positive slippage**, both stated in its FAQ.

**Where the rebate goes: the app, not the trader.** Consistent across both eras. 2022:
*"wallets and crypto swapping apps can monetize their retail volume by routing to
DFlow and receiving market maker rebates."* Current: DFlow's Breakpoint keynote frames
its payout as **"$34M in application revenue"** to developers. The user's benefit is
supposed to arrive as a better quoted price, not as a rebate.

**Three things I could not verify, and the first is decision-relevant:**

1. ⚠️ **Whether Fomo uses DFlow's `/order` path or `/intent` path. Fomo does not
   disclose it.** `/intent` is the genuinely sandwich-resistant one — the user signs an
   open order with no fixed route and DFlow lands open+fill atomically as a Jito bundle
   — and DFlow's own docs say it is **opt-in and the minority path** ("the majority of
   builders stay on `/order`"). So "MEV protection via DFlow" may mean the strong
   guarantee or the weak one. **This is the single most important unknown in this
   document and it is not answerable from public data.**
2. The value of the "governable threshold." **Never published, and absent from current
   docs entirely.**
3. A field called **`segmenterFeePct`** exists in DFlow's OpenAPI spec on the `/intent`
   path — a segmenter taking a percentage of the platform fee. **Value undocumented.**

**Conclusion on fills: the mechanism that would have made bad fills structural is not
in DFlow's current documented product, so I cannot corroborate Frank's read from the
architecture.** That is not a contradiction of his experience. It means the cause is
somewhere I could not see, and §2.5 gives the experiment that would find it.

## 2.3 Fees, at Frank's actual size

The comparison everyone publishes is at $500 or $1,000 and it inverts at $100. Round
trip on a **$100 clip**, my arithmetic on each platform's own published rate:

Gas/priority for self-routing is **≈$0.005 per side** (measured 2026-09-17, see
`TRADING_PLAYBOOK.md` §4.2) — under one cent a round trip, so it is shown but does not
move any ranking.

| venue | rate | **$100 round trip** | gas/priority | custody |
|---|---|---:|---|---|
| **Jupiter Ultra**, token >24h old | 0.1%/side | **$0.20** | own, ≈$0.01 | full export |
| **Jupiter Ultra**, token <24h old | 0.5%/side | **$1.00** | own, ≈$0.01 | full export |
| Jupiter Manual | 0%/side | $0.00 | own | ⚠️ **no MEV protection by default** |
| Axiom, Champion tier | 0.75%/side | $1.50 | own, ≈$0.01 | full export |
| **Fomo** | **flat $0.95/side** (47.50–190 band) | **$1.90** | **covered** | full export |
| Axiom, base (Wood) | 0.95%/side | $1.90 | own, ≈$0.01 | full export |
| GMGN | 1%/side | $2.00 | own, ≈$0.01 | ⛔ **no export** |
| Trojan | 1%/side, 10–35% cashback | $2.00, **$1.30 at the top cashback tier only** | own, ≈$0.01 | full export |
| Photon | 1%/side | $2.00 | own, ≈$0.01 | ⛔ one-time reveal |
| Pump.fun Terminal | **[UNVERIFIED]** — no official fee page exists anywhere; ~1.16% is my back-out of DefiLlama's fees ÷ volume, not a published rate | ~$2.32 | own, ≈$0.01 | whitelisted withdrawal |
| **Moonshot** | **2.5% under $100** — *the cited band does not say per-side; $5.00 assumes it is, and $2.50 if it is not. Either way it is last* | **$5.00** | own, ≈$0.01 | full export |

**Axiom's fee is resolved and the disagreement is settled.** Axiom's own docs state
the base fee is 1% (*"Axiom's Fee: $10,000 × 1% = $100"* on the referral page) with
volume-tiered cashback: Wood 0.95% → Bronze 0.90% → Silver 0.875% → Gold 0.85% →
Platinum 0.825% → Diamond 0.80% → Champion 0.75%, plus a documented 10% referral
discount. **The "Axiom is 0.5%" figure circulating on comparison sites is wrong and no
Axiom document supports it.** Frank would start at Wood, i.e. $1.90 — identical to
Fomo.

**Two things fall out of that table.**

**Fomo is mid-table, not the expensive one — and Frank is still overpaying, just not by
much.** At $100 it costs exactly what Axiom's base tier costs, less than GMGN, Trojan,
Photon, Pump.fun Terminal and Moonshot, and it absorbs gas, priority fees and token rent,
which none of the others do. It is **fifth of eleven.** But on the population Frank
actually trades — tokens under 24 hours old — **Jupiter is $1.00 against Fomo's $1.90, so
he is paying about 90% more than he needs to.** That is real; it is also $0.90 a trade,
against a bad fill costing $12. What is separately true is that the flat band makes him
pay **0.95% where the headline says 0.50%**, and **a fee that is double what you believe
it to be will feel like a bad fill.** Those are different problems with different fixes
and §2.5 separates them.

**Jupiter is 2× to 10× cheaper than everything else and it is not close.** On a mature
token it is $0.20 against Fomo's $1.90. Even on a token less than 24 hours old — which
is most of what Frank trades — it is $1.00 against $1.90.

⚠️ **Moonshot's 2.5% band under $100 is the worst possible tier for $100 clips.** Rule
it out on cost alone.

## 2.4 Where the volume actually is

DefiLlama, Solana fees over 30 days, retrieved **2026-09-17**:

| platform | Solana fees, 30d | share |
|---|---:|---:|
| **Axiom** | $41.11M | ~48% |
| **fomo Wallet** | $31.01M | ~37% |
| Pump.fun Terminal | $5.30M | ~6% |
| GMGN | $5.13M | ~6% |
| Trojan | $1.14M | ~1.3% |
| Photon | $575,897 | ~0.7% |
| Moonshot | $296,570 | ~0.3% |
| BONKbot | $110,617 | <0.2% |
| **BullX** | **$953.64** | **~0%** |
| Nova | $0.75 | ~0% |

**Four things that contradict every listicle:**

1. **It is a two-horse race.** Axiom + Fomo ≈ **85% of Solana terminal fees.** Fomo leads
   on *volume*; Axiom leads on *fees*. ⚠️ **I originally wrote "because its take rate is
   2–4× higher" and that is wrong and unsourced.** Axiom's documented base is 1%
   (§2.3, its own docs); Fomo's realised fee/volume ratio reads ~1.36% (DefiLlama,
   2026-08-14) — so Axiom's take rate is plausibly *lower*, and the three figures are
   jointly impossible if Fomo also leads on volume. **I have no volume figure for either
   venue and should not have inferred the ratio.** What the table supports is only that
   Axiom collects more fees. **Frank is not on a fringe app** — he is on the #1 or #2
   venue on Solana either way.
2. **GMGN's dominance is not Solana.** Only ~10% of its fees are Solana (57% Robinhood
   Chain, 28% BSC — DefiLlama's per-chain split on its protocol page). Any table ranking
   GMGN #1 for Solana is wrong.
3. **Photon has collapsed** to **$19,197/day** ($575,897 over 30 days, from the table
   above). And the widely-repeated claim that **"Photon rebranded to Axiom" is false** —
   both are separate, live, independently tracked protocols.
4. **Jupiter operates at a different layer entirely**: $17–23bn volume per 30 days for
   $20.51M in fees, a ~0.1% aggregator take rate against the terminals' ~1%.

**Newcomers, honestly: the cohort is thin and there is one real name.** Fomo itself is
the only genuine share-taker (30d fees +194% MoM, volume +265% MoM; $75M Series B from
Index Ventures and USV on 2026-06-22 at a reported $550M valuation) — and it is
**UNPROVEN at scale**, with its Solana ramp only ~2 months old and the last 7 days
down 42–47% off peak. Pump.fun Terminal is a rebrand of an acquired book (Padre,
2025-10-24), not a new entrant. **Telemetry** is real but tiny (~$41k/30d) and is the
BONKbot team's second product. **Vector is dead** — acquired by Coinbase, apps shut.
Investigated and ruled out: LAB Terminal, MEVX, o1.exchange, Maxbid, Propr, Pumper,
BlazingApp, Looter, SUITE.

## 2.5 The experiment that settles "fee or fill", and costs nothing

Frank's complaint has three possible causes and they have three different fixes.
**They are separable in about twenty trades.**

| cause | signature | fix |
|---|---|---|
| **The flat fee band** | fee line on the confirmation screen is $0.95 on a $100 order, i.e. 0.95% not 0.50% | size to $190, or move venue |
| **Routing / execution** | fill price differs from the Dexscreener mid at the same second by more than the pool's own depth accounts for | move venue |
| **Pool depth** | fill price is what constant-product impact predicts given `exit_depth_usd` | **nothing.** Intrinsic. No venue fixes it |

**The test:** for the next 20 trades, record (a) the fee shown on the Fomo confirmation
screen, (b) the fill price, (c) the Dexscreener `priceUsd` and `exit_depth_usd` for the
same pair at the same second, and (d) the notional. Then compare the realised slippage
against `2 × size/(depth+size) + 0.25%` — the same model `GAPS.md` Part 5 uses.

**If realised slippage tracks the model, the fills are not bad, the pools are thin, and
switching venues buys nothing.** If it is systematically worse than the model, the
routing is the problem and it is worth leaving. `check.py` already computes every input
on the right-hand side.

This is standing rule 5 — **every claim backed by a call actually made** — applied to a
claim about his own trading. It is the only way to know which of the three it is, and
right now nobody knows, including me.

## 2.6 The venue verdict

**Ranked on Frank's own criteria: safety gate first, then fills, then fees, then chain
coverage.**

| | verdict |
|---|---|
| **Jupiter** | **Cheapest by a factor of 2–10, and nothing found against it — but it did not get the workup Axiom and BullX got.** Non-custodial with full key export; MEV protection on by default in Ultra (per Jupiter's own docs: ShadowLane private landing, "no external relays or order-flow sales" — **their claim, unaudited**); #1 aggregator by volume; no security incident found. **$0.20–$1.00 per $100 round trip against Fomo's $1.90.** ⚠️ **Its fill quality is as unmeasured as everyone else's** (§2.2), so it wins on the one axis that is actually knowable and is untested on the axis Frank cares most about. What it does not have: a social feed, copy trading, a mobile-first UI, gasless swaps, or an Apple Pay on-ramp |
| **Fomo** | **Passes the safety gate.** Full export, gasless, #1 by Solana volume. Fee at $100 is $1.90, identical to Axiom base and cheaper than GMGN/Photon. **The fill question is unresolved and not resolvable from public data** — §2.5 is how to resolve it |
| **Axiom** | **Passes, conditionally.** Best custody in the survey. Two caveats: staff had wallet-lookup capability and one abused it (Feb 2026, confirmed), and there is an **active browser-extension campaign harvesting Axiom session tokens as of 2026-09-09.** Requires a dedicated extension-free browser profile. Costs exactly what Fomo costs at $100 |
| **Trojan** | Passes. Most permissive custody. 1%/side with 10–35% cashback. Small on Solana |
| **BullX / Neo** | ⛔ **OUT. Trading suspended 2026-06-01. Retrieve any balance** |
| **GMGN, Maestro, Banana Gun** | ⛔ **OUT on custody.** No key export |
| **Photon** | ⛔ **OUT on custody.** One-time key reveal, and the platform has collapsed to ~$10k/day |
| **Moonshot** | ⛔ **OUT on cost.** 2.5% under $100 |

**The thing Frank gives up by leaving Fomo is the social layer — and that is the part
measured to be losing money.** DWF Ventures, ~292,000 Fomo wallets over 90 days to
August 2026: **6.16% profitable on realized P&L; 25 wallets above $10,000 net.** DWF
names the mechanism as execution asymmetry, and is explicit that the data does **not**
establish that followed traders trade against followers. But the direction is not
ambiguous: a follower acting on a signal seconds later is not making the same trade,
and in a thin pool the follower's own buying is what moves the price against them.

⚠️ **Two things I should not slide past.** The ~292,000 are **all Fomo wallets, not
copy-traders**, so the 6.16% is not a measurement of the copy feature. And "6.16%
profitable" does not make the remainder "93.84% lost money" — it folds break-even into
losses. **The correct statement is that 6.16% of Fomo wallets showed a realized profit
over 90 days, and DWF does not attribute that to the feed.**

### ⭐ Correction 2026-09-23: use 5 to 7 percent, multiply-sourced, and never the "500"

Frank, via the relay: **"Use 5 to 7 percent net positive, multiply-sourced. Do not
quote the 500 figure as fact."**

⛔ **The viral claim that only about 500 Fomo traders have ever been above
$1,000 comes from a single X post and is not independently sourced.** It is not to
be repeated as a fact, here or to Frank.

⭐ **What IS multiply-sourced is a net-positive share of roughly 5 to 7 percent**,
and three independent derivations land inside that band:

| source | population | net positive |
|---|---|---|
| independent rerun, as of 2026-09-02 | 476,627 wallets | **27,130 = 5.69%** |
| DWF Ventures, 90 days to Aug 2026 | ~292,000 wallets | **6.16%** (realized) |
| our own re-derivation of degentape's tape | 45,853 closed positions | **6.0% [5.8, 6.3]** at proceeds >= 2x cost |

⭐ **That third row is ours and it is the one with an interval** - and it is
measuring a different thing on a different population (positions, not wallets;
a 2x bar, not "above zero"), so its agreement with the other two is a coincidence
of magnitude rather than a confirmation. ⚠️ **The band is the claim. Any single
number inside it is one study's definition of "profitable."**

⚠️ **And the caveat above still governs all three:** "5 to 7 percent net
positive" does not make the rest losers, because every one of these folds
break-even into the negative side. Only 229 Robinhood Chain FOMO users are above
$10,000 in profit, which is a separate and much narrower statement.

**So the honest framing of the switch is not "cheaper fees," and not "the feed is
costing him money" either** — neither is established. It is: the UI and the feed are the
reason to stay, the one population-level number anyone has published about this app is
unflattering and mechanistically plausible, and the cost saving is real but second-order
next to the $12–14 a bad fill costs on a $100 clip (`TRADING_PLAYBOOK.md` §4.4).

**⚠️ Note on Fomo's copy-trade button, per the memory flag.** The exit-liquidity
mechanism is verified as a described mechanism and the intent is not. The chain is:
a trader with followers buys a thin token → followers see it and buy → their buying
lifts the price → the original holds a lower basis → when they sell, follower bids are
what absorbs it. **Plus a second vector DWF names that transparency does not fix:** a
trader can accumulate in a separate wallet before buying through the public one, so a
verified wallet confirms what happened in *that* wallet without proving it is the
trader's complete position. **Neither requires bad intent to hurt a follower, and
neither is detectable from the feed.**

---

## Sources

Retrieved **2026-09-17** unless stated. Volume and fee figures are DefiLlama's unless
named otherwise; DefiLlama's own surfaces disagree by 10–25% between pages, it calls
Axiom's volume "a floor," and it flags Fomo's volume adapter `doublecounted: true`, so
**nothing beyond two significant figures should be treated as precise.**

**Primary / platform documentation**
- `docs.axiom.trade` — fees, referral program, signup, FAQs (custody, tiers, 1% base)
- `bullx.gitbook.io/bullx-neo-docs` — private keys, wallet manager, fees and gas
- `docs.jup.ag` — Ultra Mode fee schedule, MEV protection
- `docs.dflow.net`, `pond.dflow.net`, dflow.net/blog — segmentation, JIT routing,
  `/order` vs `/intent`; DFlow launch thread (2022-08-26) and Pyth interview
  (2022-09-30) for the superseded auction design
- `fomo.family/answers/is-fomo-app-safe`, `/memecoin-trading-app-lowest-fees` (2026-02-08)
  — DFlow routing confirmed by Fomo
- `help.fomo.family` fee article via FomoAppGuide, verified 2026-08-20
- `docs.robinhood.com/chain/gas-and-fees`, Robinhood mainnet newsroom post (2026-07-01)
- `docs.base.org/base-chain/network-information/network-fees`; Etherscan gas tracker
- `api.geckoterminal.com/api/v2/networks` (all 3 pages); `docs.dexscreener.com`
- Helius, Alchemy, Codex, Moralis, Birdeye, Blockvision, Ankr, The Graph pricing pages

**Independent measurement / journalism**
- ZachXBT thread 2026-02-26 + Axiom response, reported by The Block and CoinDesk
- Socket Threat Research — browser extensions harvesting Axiom/Padre sessions,
  2026-09-09; malicious npm packages targeting BullX key files, 2025-05-08
- Bitquery — Robinhood Chain gas investigation (verified 2026-09-04), Pons launchpad
  investigation
- crypto.news 2026-06-01 (BullX suspension), 2026-09-04 (RH subsidy); CoinGape 2026-07-11
- The Block 2025-11-24 (Monad mainnet)
- ACM DOI 10.1145/3736763 (June 2025) — sniper bot counts, ETH and BSC
- DWF Ventures via AlexaBlockchain, 2026-08-28 — 292,000 Fomo wallets

**Flagged as affiliate/referral-driven or competitor-authored — used for direction
only, never as a source of fact:** `axiompedia.com`, `solanatools.io`,
`memegateway.com`, `theterminalroom.com`, `dexrank.com`, `pumpparade.com`,
`bullxneo.net`, `fomoappguide.com`, `intercom.help/cryptoreferralcodes`,
`solanatracker.io`, `moby.win`, `trojan.com/blog`, and exchange content marketing at
`bitget.com/academy`, `mexc.com/news`, `phemex.com/news`. One "press release"
syndicated identically across mexc.com, crypto-reporter.com and kulfiy.com is **a
marketing buy, not three sources.**

**Marketing claims actively rejected as false:** "Axiom (ex-Photon)" / "Photon
rebranded to Axiom"; "BullX collected $2.29 billion in trading fees" (DefiLlama
all-time is $203M, so wrong by ~11×); "Axiom 20% off with code" (contradicts Axiom's
documented 10%); "Axiom charges 0.5%" (contradicts Axiom's own fee page).

**Not verified, explicitly:** whether Fomo routes `/order` or `/intent`; DFlow's
governable threshold; `segmenterFeePct`; the Axiom SSN allegation; any follow-up to
the Feb 2026 Axiom incident; Reddit and X sentiment for any platform (both
inaccessible to the tooling used); any BullX platform-level compromise; Pump.fun
Terminal's actual fee (no official page exists); Fomo's official fee page and MEV
documentation; current bot share on any chain; Base/BNB/Monad launches per day;
post-subsidy Robinhood Chain swap cost.

---

*Research document. No code was modified, no account created, no venue recommended for
signup, and no trade placed or advised. Prices and fee schedules change often — Fomo's
moved three times in twelve days in August 2026 — so every figure here carries a date
and should be re-checked before it is acted on.*
