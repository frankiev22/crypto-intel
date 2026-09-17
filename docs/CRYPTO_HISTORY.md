# Crypto history, organised around what recurs

**Started 2026-09-17. First pass — this file accumulates and is not finished.**

⭐ **Organising principle: this is not a timeline.** It is arranged by
**mechanism**, because the point is recognising the next cycle while it is
happening, not reciting the last one. Dates and names exist to support the
pattern, never as trivia.

⚠️ **Sourcing standard.** Cite a date and a source for anything load-bearing.
Where something is contested or I am working from general knowledge rather than
a checked source, it is marked ⚠️ **unverified** — those are the entries to
attack first when this file is next opened.

---

## 1. The cycle engine

Four cycles have now run with the same internal structure. **The vehicle
changes every time; the mechanism does not.**

| | trigger | speculative vehicle | ending |
|---|---|---|---|
| 2011–2013 | Bitcoin reaches exchanges | BTC itself, first alts | Mt. Gox collapse (Feb 2014) |
| 2016–2018 | Ethereum enables token issuance | **ICOs** | SEC enforcement + ICO paper worthless |
| 2020–2022 | Zero rates, DeFi composability | **DeFi → NFTs** | Terra/Luna (May 2022), FTX (Nov 2022) |
| 2023–2025 | ETF approval, then permissionless launchpads | **memecoins** | ⚠️ unverified — arguably still resolving |

**The recurring shape, in order:**

1. **A technical unlock lowers the cost of creating a speculative asset.**
   Ethereum's ERC-20 made issuing a token trivial (2015→). pump.fun made it
   free and instant (2024→). *The unlock is always framed as democratisation.*
2. **Early returns are real**, because supply of the new asset type is genuinely
   scarce at first.
3. **Supply expands to meet demand**, and keeps expanding past it. This is the
   part that is structurally guaranteed and always underestimated.
4. **Returns compress to below the base rate**, but *dispersion rises* — a few
   enormous winners keep the narrative alive while the median goes to zero.
5. **A solvency event ends it**, not a valuation argument. Cycles do not end
   because things are expensive; they end when something that was supposed to
   be safe turns out not to be.

⭐ **Step 3 is where this project lives.** A 0.198% graduation base rate
(Kamat, arXiv:2607.02823, n=832,941) **is step 3 quantified.** Memecoins are not
unusually predatory; they are the current cycle's expression of an old
mechanism, running faster because the unlock was more complete.

## 2. What actually starts a cycle

**Not price. Access.** Every cycle began with a change in who could participate
or what they could make.

| unlock | date | what it enabled |
|---|---|---|
| Bitcoin genesis block | 2009-01-03 | the asset exists |
| Mt. Gox as a liquid venue | 2010–2013 | price discovery, and later the collapse |
| Ethereum mainnet | 2015-07-30 | **arbitrary token issuance** — the single most consequential unlock |
| ERC-20 standard | 2015 | tokens become interchangeable infrastructure |
| Uniswap v1 | Nov 2018 | **permissionless listing.** No gatekeeper decides what trades |
| Uniswap v2 | May 2020 | any-token-to-any-token pools; DeFi summer follows |
| Compound `COMP` distribution | Jun 2020 | **yield farming** — paying users in governance tokens |
| Solana mainnet beta | Mar 2020 | fees low enough that micro-speculation is viable |
| Spot Bitcoin ETFs approved (US) | 2024-01-10 | institutional access without custody |
| pump.fun launch | 2024-01 ⚠️ unverified exact date | **token creation at zero cost and zero delay** |

⭐ **The pattern: each unlock removes a gatekeeper.** Exchanges, then listing
committees, then developers, then capital. pump.fun removed the last one — you
no longer need money or skill to create a tradeable asset. **When the cost of
creating an asset hits zero, the base rate of success must approach zero**, for
arithmetic reasons rather than moral ones.

## 3. What ends a cycle

⛔ **Never a valuation argument. Always a solvency event.**

| event | date | mechanism |
|---|---|---|
| Mt. Gox halts withdrawals | Feb 2014 | custodial insolvency; ~850k BTC |
| The DAO hack | Jun 2016 | smart-contract risk is real; forces the ETH/ETC fork |
| ICO market collapse | 2018 | supply exhaustion + SEC enforcement |
| "Black Thursday" | 2020-03-12 | correlated liquidation; MakerDAO auctions clear at $0 |
| Terra/Luna collapse | May 2022 | **algorithmic stablecoin reflexivity** — the "safe" leg was the risk |
| 3AC insolvency | Jun–Jul 2022 | leverage transmitted Terra's failure to lenders |
| Celsius, Voyager freeze | Jun–Jul 2022 | duration mismatch on customer deposits |
| FTX collapse | Nov 2022 | customer funds lent to an affiliate |

**The recurring lesson, and it is the one that matters here:**
⭐ **The thing that ends the cycle is always the thing everyone had agreed was
safe.** Gox was "the exchange". UST was "a dollar". FTX was "the regulated one".
**Assess the leg nobody is examining.**

⚠️ The 2020–2022 cluster shows the second mechanism: **contagion runs through
leverage, not through price.** Terra alone was survivable; Terra plus 3AC's
borrowings was not.

## 4. The vehicles, and why each one arrived when it did

### DeFi (2020–2021)
**Unlock:** Uniswap v2 + `COMP` farming. **Mechanism:** protocols bought
liquidity with their own newly-issued governance tokens.
⭐ **The pattern that recurs: emissions are a cost dressed as a yield.** TVL
followed emissions and left when they stopped — "mercenary capital". Any
project paying for its own liquidity is running this trade.

### NFTs (2021–2022)
**Unlock:** ERC-721 plus a marketplace (OpenSea) plus cheap credit.
**Mechanism:** provable scarcity applied to things that were not otherwise
scarce. ⚠️ The honest summary is that **floor prices were a liquidity illusion**
— a "10 ETH floor" meant one bid at 10 ETH, not a market that would absorb size.
⭐ **This is exactly the failure mode of reported liquidity in `LIQUIDITY.md`.**
The NFT cycle already ran the experiment: a quoted price with no depth behind it
is not a price. **Same error, different asset class, four years apart.**

### Memecoins (2023–2025)
**Unlock:** low fees (Solana) + zero-cost issuance (pump.fun).
**Mechanism:** the asset's only claim is attention. No cashflow, no protocol, no
pretence of one. ⭐ **Memecoins are the honest form of what the previous two
cycles were doing implicitly** — and that honesty is why the base rate is
measurable at all.

### AI tokens (2024–2025)
**Unlock:** narrative transfer from equities. ⚠️ **unverified** — I have not
checked whether AI-token launches carry a materially different base rate from
other memecoins, and **that is a testable question with our own data.** Flagged
as an open item rather than asserted.

## 5. ⭐ What recurs, compressed

**The list to check the next cycle against:**

1. **Every cycle's vehicle is the previous cycle's unlock, made cheaper.**
2. **Returns compress as issuance cost falls.** Not a moral claim — arithmetic.
3. **Dispersion rises while the median falls.** The survivors are loud; the
   base rate is quiet. ⛔ *This is why survivorship discipline is a standing
   rule here.*
4. **Quoted price is not depth.** NFT floors, memecoin liquidity, FTX's balance
   sheet — the same error in three costumes.
5. **The safe leg is the dangerous one.**
6. **Contagion travels through leverage**, not sentiment.
7. **Each cycle's tooling becomes the next cycle's infrastructure.** Uniswap was
   a 2020 speculation vehicle and is now plumbing. ⭐ **Watch what is currently
   being speculated on for a hint at what becomes boring and load-bearing next.**
8. **Regulation lags by roughly one full cycle** and arrives after the damage.

## 6. Open items for the next pass

⛔ **Do not treat this file as complete. Named gaps:**

- **Dates marked ⚠️ unverified above**, especially pump.fun's launch date and
  the 2023–2025 cycle boundary.
- **The AI-token base-rate question** in §4 — answerable from our own
  observations once a collector is running.
- **Pre-2013 history is thin here** and mostly asserted from general knowledge.
- **Non-US regulatory history** is absent entirely (MiCA, Japan post-Gox, China's
  bans and their market effects).
- **Solana's own history** — the 2022 outages, the FTX association and the 2023
  recovery — deserves its own section, since it is the chain we actually trade.
- **No sources are linked yet.** Kamat (arXiv:2607.02823) is the only citation
  in this file that meets the standard set at the top. **That is the first
  thing to fix.**
