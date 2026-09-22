# The market meta, September 2026: claims received and what we verified

2026-09-22. **Source of the claims: five daily memecoin recaps by
@CryptoGorilla, 2026-09-17 to 2026-09-21**, read in Frank's browser and relayed to
this session. ⛔ **Everything in the CLAIM column is third-party and dated. None
of it is our measurement.** The VERIFIED column is what I checked myself today, on
chain or against a primary source. Blank means not checked.

⭐ **Why this file exists.** Our pipeline's model of the market was
pump.fun-centric and name-centric, and it was wrong in a way no internal
measurement was ever going to reveal: **we were measuring the thing we could see.**
This is the correction, written down so the next session starts from it.

---

## 1. The mechanic: asset-paired tokens, not pump.fun launches

| claim | verified? |
|---|---|
| The dominant mechanic is **asset-paired tokens** | ⭐ **YES, and it is mechanical.** Full write-up in `docs/ASSET_PAIRED_TOKENS.md` |
| Observed pairs: ZCAT/ZEC, NEARKAT/NEAR, VCAT/VVV, XCAT/XRP, ACAT/AVAX, AVACAT/AVAX, COPCAT/copper, MUCHWOW/DOGE, FEELSGOOD/PEPE, QUEEF/Fartcoin, SCHIFFY/gold, WOW/gold, GP/Runescape gold, URANUS/SpaceX, 牛马/Alibaba, a GME pair, SOLCAT, MCAT, GCAT, Tilcayo | ⭐ **3 verified on chain** (ZCAT/ZEC, NEARKAT/wNEAR, COPCAT/COPX). ⚠️ **VCAT could not be resolved**: 19 same-symbol candidates, the top one a pump.fun mint with 2 holders. The rest unchecked |
| The venue is **stonk.fun, not pump.fun** | ⭐ Partly. stonk.fun is real, its tokens are Token-2022 with a 100 to 300 bps transfer fee, and one authority runs the ecosystem. ⛔ **But BisonFi is 7x stonk.fun by volume** and pump.fun plus PumpSwap is still 14.4% of Solana. "Not pump.fun" is right about where the *interesting* flow is, not about where the volume is. `docs/COVERAGE_PLAN.md` §1 |
| Our 09-21 copper finding was a venue feature launch, "after Sunrise added Copper Miner pairs" | ⭐ **YES, and this is a correction to something I told Frank.** See §4 below |

## 2. The macro fact underneath it

| claim | verified? |
|---|---|
| An SEC temporary exemption for tokenized stocks on **2026-09-17** is "the load-bearing fact under this entire meta" | ⭐ **VERIFIED from sec.gov's own press release, dated 2026-09-17**: the "Innovation Exemption", five-year temporary conditional relief for Tokenized Securities Venues from the exchange definition, plus dealer relief for their liquidity providers. Conditions include limits on symbol count and volume, public auditable contracts on a permissionless ledger, and halts coordinated with the primary exchange |
| | ⛔ **Scope bound he did not mention, and it matters:** tokens must give holders "the same rights and privileges as does traditional NMS stock of an equivalent class", so purely synthetic price-tracking tokens are **excluded**. The exemption covers the tokenized-stock **quote assets** (COPX and its kind), not the memecoins denominated in them |
| STONK: 125m on 09-18, 244m later 09-18, 270m on 09-19, ATH near 300m on 09-20 | ⚠️ **Not verified as a series.** Our own chain-side read today: **$258M mcap, $88.2M 24h volume**, same order of magnitude as his 09-20 figure. A market cap path across four days is not something we can reconstruct: we were not watching |

## 3. Venues we do not touch at all

Claimed: **Stonk Fun, Genius launchpad (BSC), Arc, Moonshot, UsePaid, LaunchOnSF,
FLEX, BIDDY, CROSSR, PRISM, Sunrise.**

| claim | verified? |
|---|---|
| GSTOCK 17m to 27m, GENIUS over 300m on the Genius launchpad (BSC) | ⚠️ Not verified. ⛔ **But Genius.fun is $3,074,539/24h, which is 0.2% of BSC.** A 300m token on a venue doing 0.2% of its chain is possible and still does not earn a parser. `docs/COVERAGE_PLAN.md` §3 phase 4 |
| ARGUS 36m, TOLLY 25m, LONG 17m on Arc | ⚠️ Not verified. Arc launched 2026-09-16 (Circle L1, USDC gas, PoA). ⛔ Our note in CLAUDE.md said Arc has "no memecoin venue", which this claim contradicts. **Unresolved, and worth resolving** |
| Moonshot (MCAT), UsePaid, LaunchOnSF, FLEX, BIDDY, CROSSR, PRISM, Sunrise | ⚠️ None verified. Sunrise is the one with a traced mechanism, via COPX pairs |

## 4. ⛔ The correction: our copper narrative was the shadow of the object

**What I told Frank on 2026-09-21:** the one genuinely new multi-name theme in the
launch stream was **copper**, 24 contracts across 8 distinct names, 4 passing a
real round trip, COPCAT near $1.18M. I framed it as an organic narrative forming
and as evidence that name clustering works.

**What it actually was:** a venue added a new **pairable quote asset**, and a
swarm of copper-named tokens appeared quoted against it. COPCAT's primary pool
holds **COPX, the Global X Copper Miners ETF** (`CzLTZppPdZtTjyq3WGpHLstoc3GLhu7zH5Zg6xUa6Gv5`,
Token-2022, tagged stocks and rwa), verified on chain today.

⭐ **The generalisable lesson, which is the whole value of this correction:** our
clustering reads **tickers and now token names**, so it can only ever see the
shadow. **The object is the set of quote assets in new pools.** A new quote mint
appearing across several new pools is a venue event, it is cheap to detect, it is
pure description of something that already happened, and it would have caught
COPCAT on day one for the right reason. ⛔ **We do not store the quote mint on any
observation row**, so this cannot be done on history. BACKLOG A55.

This is the same error family as the 781x liquidity finding and the name-storage
gap: **we measured the field we happened to have.**

## 5. The fee-sharing meta

| claim | verified? |
|---|---|
| PAID 36m ATH; ELON at 7.7m routing about 80k of fees to Elon's Xmoney; KEVIN, JASON, CASHED, TIPPED, fomopay | ⚠️ **None verified.** No contract addresses were supplied and these tickers are exactly the collision surface we have measured (398 impersonating contracts) |
| ⭐ The mechanism is real and we traced its stonk.fun form | **VERIFIED**: fee withheld in the mint, harvested and swapped by `5KXDF6Qn…`, then distributor `HuBMeYW3aDn8BH65fo8xxbP4oiexyup8udzKyccgi8Ga` paid **4,747 distinct wallets in 300 transactions over 37 seconds**, in quote assets. ⛔ **Funded by other traders' volume, so it is redistribution, not yield.** The same tax is your entry cost and your exit cost |

## 6. The social-graph-event meta

Claimed, all unverified by us, and stated as **follows and profile-picture
changes, not tweets**:

- pmarca follows musebook, MUSEBOOK reaches 26m.
- Zuckerberg changes his Facebook profile picture, AGRIPPA reaches 1.4m.
- Zuckerberg follows a 224-follower account: AGRIPPA 200k to 5m and MUSEBOOK 25m
  to 48m **within an hour**.
- Roaring Kitty logs in and posts, a GME pair reaches 4m.
- Trump posts, SI and EI drop.

⭐ **The structural claim is correct and I will not soften it: our pipeline reads
liquidity, mint authority, holder counts and now token names. It cannot see a
follow or a profile picture. It is not that we are bad at this, it is that there
is no code path.**

Scoped, not built: `docs/SOCIAL_GRAPH_SCOPE.md`. ⛔ **The first thing to do there
costs nothing and is not an API purchase:** take these five claimed events, find
the token's first on-chain buy, and measure how long the move took. If a move
takes tens of minutes, a 10-second on-chain detector already catches it and a
social watcher buys nothing.

---

## 7. What we should stop saying

- ⛔ **Stop describing the launch stream as pump.fun.** It is 14.4% of Solana by
  volume and the graduation ledger built on it misses 85.6%.
- ⛔ **Stop treating a ticker or name cluster as a narrative.** It is a shadow.
  Cluster on the quote asset.
- ⛔ **Stop reporting depth for a pool we cannot price.** Four of Frank's own
  tokens sit in pools quoted in assets our reader values at $0.
