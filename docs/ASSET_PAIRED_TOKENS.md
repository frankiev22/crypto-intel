# Asset-paired tokens: the mechanic, verified on chain

2026-09-22. Prompted by five days of @CryptoGorilla recaps (09-17 to 09-21) read
in Frank's browser. **His claims are third-party and dated; what follows is what
I verified myself, with his claims labelled as claims.**

---

## ⛔ Correction first: our "copper narrative" was the shadow, not the object

On 2026-09-21 I told Frank that the one genuinely new multi-name theme in the
launch stream was **copper**: 24 contracts, 8 distinct names, 4 of which passed a
real round trip, with COPCAT around $1.18M. I presented it as an organic
narrative forming.

**It was a venue feature launch.** CryptoGorilla's recap says COPCAT ran to $3M
"after Sunrise added Copper Miner pairs" (his claim, undated beyond the recap).
The chain supports the mechanism: COPCAT's primary pool is quoted in
**`CzLTZppPdZtTjyq3WGpHLstoc3GLhu7zH5Zg6xUa6Gv5` = COPX, "Global X Copper Miners
ETF"**, a tokenized-stock mint (Token-2022, tags `stocks`, `rwa`, `backpack`).

So the sequence was: a venue added COPX as a pairable quote asset, and a swarm of
copper-named tokens appeared **against that asset**. My clustering read the
names. The object was the **new quote asset**. ⭐ **The leading indicator is the
appearance of a new quote mint, not a new word in a ticker.**

---

## What a "pair" actually is, at the contract level

Checked today on ZCAT, NEARKAT, COPCAT (VCAT unresolved, see below). Method:
resolve the token, list its pools, read each pool's vaults from chain, then
resolve the identity of the non-token side.

| token | contract | deepest pool | venue | quote asset held in the vault |
|---|---|---|---|---|
| ZCAT | `HcRLc9VDgjLeK154xDawfb1dmVJ98DoSqcwTHGqiDeJR` | `BTccxxTFi7a9…` | Raydium | **556.93 ZEC** (`A7bdiYdS5GjqGFtxf17ppRHtDKPkkRqbKtR27dxvQXaS`, "Zcash", $1,550) |
| NEARKAT | `6UtY9iTZMQQ5QZVrbzFnNaJntV7oySm9k97mvwnuZcxr` | `G19cwhvY4tei…` | Raydium | **48,642 wNEAR** (`3ZLekZYq2qkZiSpnSvabjit34tUkjSwD1JFuW9as9wBG`, "Wrapped NEAR", $4.40) |
| COPCAT | `HhcfXbZ2rukoKx8oAH8rfkmzXbwvfdh6MMLZjneg4rWk` | `FDy48HT3x8xV…` | Raydium | **343.53 COPX** (`CzLTZppPdZtTjyq3WGpHLstoc3GLhu7zH5Zg6xUa6Gv5`, Global X Copper Miners ETF, $90.53) |

### The answer: mechanical, but not an oracle

1. ⭐ **The link is DENOMINATION.** The token's primary market is an ordinary AMM
   pool whose quote side is a tokenized or bridged version of the paired asset.
   Price discovery happens in that asset, so the token's USD price is
   `(ratio in the pool) x (USD price of the paired asset)`. If ZEC rises 10% and
   the pool ratio does not move, ZCAT's USD price rises 10% **automatically**,
   with no oracle and no code.
2. ⛔ **Nothing on chain reads the paired asset's price.** Raydium CPMM/CLMM and
   Meteora DLMM carry no price feed. There is no programmatic tracking, no
   rebase, no synthetic exposure. The transmission is arbitrage by traders and
   bots between the paired asset's own market and this pool.
3. ⭐ **The reward payout uses the same asset.** stonk.fun reward tokens withhold
   a Token-2022 transfer fee and distribute it in the pool's quote asset,
   verified on chain 2026-09-22: distributor
   `HuBMeYW3aDn8BH65fo8xxbP4oiexyup8udzKyccgi8Ga` paid **4,747 distinct wallets
   in 300 transactions over 37 seconds**, in quote assets. So holding a paired
   token pays you in the paired asset.

**Therefore a paired token IS analyzable, and in a way a plain memecoin is not.**
Its return decomposes cleanly:

```
token USD return  =  paired asset USD return  +  pool ratio return
                     (beta, explainable)         (idiosyncratic, the real signal)
```

⭐ **This is the first genuinely novel analytic this project has had a right to
claim.** "ZCAT is up 12% because ZEC is up 11%" and "ZCAT is up 12% while ZEC is
flat" are different facts, and nobody's dashboard separates them. It is also
pure description of what already happened, so the Marino result does not block
it.

### What it breaks in our pipeline

⛔ **Our depth reader values only SOL, USDC and USDT.** A pool quoted in ZEC,
wNEAR, COPX or STONK reads as **$0**. Measured today: STONKBROS
`9KmeDWVt7TtrEZT2567kxeDkDZxd3cDoTZ1ZrLow9soG` read **$0.03** of chain depth
while Jupiter sold $100 of it for $94.11 against a Raydium CPMM pool quoted in
STONK. Fixed inside `analysis/daily_2026-09-22/pushback/pool_probe.py`
(`asset_usd`, prices any quote asset and names it); **the four copies of
`resolve.exit_depth_usd` are untouched.** BACKLOG A53.

⛔ **We do not persist the quote asset at all.** Observation rows carry `liq_base`
and `liq_quote` as amounts, but no quote mint and no quote symbol, so nothing in
14 days of journal can tell you what any pool was paired against. Same shape as
the `token_name` gap (A48): fetched in the payload, never stored. BACKLOG A55.

---

## The venue: stonk.fun, and how to enumerate it from chain

Frank's own holdings are here, and this is where the meta lives.

- **The reward mechanism is a Token-2022 transfer fee**, 3% on PURR/ZCAT/KNOTS/
  LOOP and 1% on STONKCAT, read from each mint today.
- **One authority runs the whole ecosystem:**
  `5KXDF6QnqhBj72hDtJNkkpFaQVUfbFXNybMsp3DiK6tD` is the withdraw-withheld
  authority on every one of them, and on KNOTS, LOOP and STONKCAT it is also the
  **fee config authority**, meaning the fee can be changed.
- ⭐ **That authority is a free discovery feed.** It touches every stonk.fun
  token constantly: I pulled **400 transactions spanning a 2-minute window**,
  harvesting and swapping fees across many mints. Paging its signatures
  enumerates the stonk.fun universe from chain with no third-party API and no
  key. This is the cheapest discovery path we have found for any venue.
- Volume, DefiLlama 24h: **StonkFun $63,025,127, 1.7% of Solana DEX volume.**
  Note the launchpad's own figure understates the ecosystem, because graduated
  stonk.fun tokens trade on Raydium CLMM/CPMM and Meteora DLMM, which we already
  parse.

## The macro fact under the meta, verified

CryptoGorilla's load-bearing claim is that the SEC granted a temporary exemption
to tokenized stocks on 09-17. **VERIFIED against the SEC's own press release**
(`sec.gov/newsroom/press-releases/2026-90-…`, dated **2026-09-17**):

- An **"Innovation Exemption"**: five-year, temporary, conditional relief letting
  **Tokenized Securities Venues** trade tokenized NMS stock without registering
  as an "exchange", plus relief for their liquidity providers from the "dealer"
  definition.
- Conditions include **limits on the number of symbols and on volume traded**,
  smart contracts that are "auditable, public, and deployed on a public,
  permissionless distributed ledger", and halting when the underlying stock halts.
- ⛔ **Scope bound that matters here:** tokens must "provide holders the same
  rights and privileges as does traditional NMS stock of an equivalent class",
  so **purely synthetic price-tracking tokens are excluded**.

⭐ **So the exemption legitimises the QUOTE ASSET layer (real tokenized equities
such as COPX), not the memecoins denominated in them.** COPCAT is not a
tokenized stock and is not covered by it. The exemption is plausibly why the
pairable-asset menu expanded, which is the actual driver of the paired-token
wave. That is a supply-of-quote-assets story, and it is trackable: watch the set
of quote mints.

---

## Unresolved

- **VCAT / VVV**: Jupiter returns 19 same-symbol candidates and the most liquid
  is a pump.fun mint with **2 holders** and no readable pools. I could not
  identify a credible VCAT. Not verified either way.
- Whether any paired token has ever been implemented with a real oracle. Every
  one I checked is plain denomination. Three tokens is not a survey.
- CryptoGorilla's specific market-cap figures (STONK 125M/244M/270M/~300M ATH,
  AGRIPPA 200k to 5M, MUSEBOOK 25M to 48M, PAID 36M, GENIUS over 300M, etc.) are
  **his claims, not verified by us.** Our own chain read today puts STONK at a
  **$258M market cap** with $88.2M of 24h volume, which is consistent in order of
  magnitude with his 09-20 "near 300M" but is not the same measurement.
