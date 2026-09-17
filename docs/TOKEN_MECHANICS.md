# Tax tokens, reflections, and the "get paid in another project's coin" mechanic

Written 2026-09-17. Research only. **Nothing was launched, deployed or bought. No collector
code was touched.**

Companion to `docs/TRENCHES_REFERENCE.md` §1.1 (Token-2022 extensions) and
`docs/CREATOR_PLAYBOOK.md`. Terms are in `docs/GLOSSARY.md`.

This document exists because Frank asked specifically about *"the logistics of how these
tax coins work that airdrop you coins of another project (stonk)."* **The first thing to
do is correct the premise**, which is §3.

---

## 0. The one-paragraph version

A transfer tax is a fee skimmed off every movement of a token. On Solana it is a declared,
readable property of the mint (Token-2022's `TransferFeeConfig`); on Ethereum it is
arbitrary code inside the contract's transfer function, which is a much worse trust model.
Reflection tokens pay the tax back to holders in the same token, using an accounting trick
that avoids paying anyone at all. The variant Frank is asking about pays holders in a
*different* asset, which requires somebody to actually sell the tax and actually send
thousands of transfers, and therefore requires trusting that somebody. **Every one of these
designs is funded entirely by trading volume, and a large share of that volume is people
selling — so "passive income" is, mechanically, other holders' exits.** It is not yield,
it is not a dividend, and nothing produces it.

---

# Part 1 — How a transfer tax is actually implemented

## 1.1 Solana: Token-2022 `TransferFeeConfig`

**Primary source: Solana Foundation docs,
`solana.com/docs/tokens/extensions/transfer-fees` (source mdx retrieved from
`github.com/solana-foundation/solana-com`), 2026-09-17.**

This is a **protocol-level extension**, not custom code. The token program itself enforces
it. Sequence:

1. The mint is created with the `TransferFeeConfig` extension, specifying a rate in basis
   points, a `maximumFee` per transfer, and two authorities.
2. Every token account for that mint is automatically initialised with a
   `TransferFeeAmount` extension.
3. On every transfer, the token program reduces the transferred amount by the fee and
   **records the withheld fee on the *destination* token account.** It does not go to a
   treasury. It sits on the receiver's account, inaccessible to the receiver.
4. `HarvestWithheldTokensToMint` — **permissionless**, anyone may call it — sweeps
   withheld amounts from token accounts up to the mint account.
5. `WithdrawWithheldTokensFromMint` (or `…FromAccounts`, going direct) moves them to a fee
   receiver. **This requires the withdraw-withheld authority to sign.**
6. `SetTransferFee` changes the rate. It takes effect **two epochs later**, and requires
   the `transferFeeConfigAuthority`.

**The three facts that matter for reading any tax token:**

| Field | Question it answers |
|---|---|
| `transferFeeConfigAuthority` | **Can the rate change?** If non-null, someone can raise it. Two epochs of warning, which on Solana is a few days — but only if someone is watching. If null, the rate is frozen forever. |
| `withdrawWithheldAuthority` | **Who owns the tax stream?** Whoever this is, is the only party who can turn withheld fees into money. This is the counterparty. |

| `maximumFee` | Caps the absolute fee per transfer, which matters because a percentage rate on a large transfer is otherwise unbounded. |

*(Field names above are the `jsonParsed` RPC keys, which is what the collector would read.
The Rust instruction names differ — `withdraw_withheld_authority`,
`transfer_fee_config_authority`. Use the camelCase form in code that parses RPC output.)*

Both authorities can be set to `None` at creation, which is the only version of "renounced"
that means anything.

**Why this is the good design, relatively.** The tax is a property of the mint, readable
from a single `getAccountInfo(mint, jsonParsed)` call — the same call
`onchain.authorities()` already makes. It applies on every venue, so there is no cheaper
pool to route around it. And critically, **the enforcement is the token program's, not the
deployer's**, so a Solana transfer fee cannot selectively block your sell. It can make the
sell expensive; it cannot make it fail. (A `TransferHook` *can* make it fail — different
extension, covered in `TRENCHES_REFERENCE` §1.1. Do not confuse them.)

## 1.2 Ethereum / BSC: the older ERC-20 pattern

There is no protocol-level fee on ERC-20. The token contract's `_transfer()` is hand-
written, and the tax is whatever that code does. That means:

- The rate can differ on buy vs sell vs wallet-to-wallet, by checking whether the
  counterparty address is a known pool.
- Addresses can be whitelisted out of the tax — typically the deployer's.
- The function can simply **revert** for some callers. This is the classic Ethereum
  honeypot: buys work, sells do not.
- There is no standard field to inspect. You have to read bytecode or trust a scanner.

**The trust model is categorically different and this is the single most useful thing to
carry between chains.** On Solana, "does this token have a tax and who controls it" is one
free RPC call returning structured data. On Ethereum it is a reverse-engineering problem.
This is also why `TRENCHES_REFERENCE` §1.3 is right that the Solana honeypot is freeze
authority / hook / `DefaultAccountState`, and **not** the Ethereum sell-blocking
`transfer()` override — the mechanism does not port.

---

# Part 2 — Reflections, and why the obvious implementation does not scale

## 2.1 Same-token reflection (the SafeMoon family)

The promise: hold the token, your balance goes up, you never click anything.

The implementation is not a payment. It is a **scaled-balance accounting model**: each
holder's stored quantity is in an internal unit, and the displayed balance is that
quantity divided by a global scaling factor. The tax adjusts the scaling factor, which
raises every holder's displayed balance at once, in a single state change, regardless of
how many holders exist. *(Description of the general pattern from reading how these
contracts are commonly built. **[UNVERIFIED]** — I did not read a specific contract, and
implementations differ in detail.)*

So it scales perfectly, because **nobody is ever paid.** Your token count rises; the total
supply's claim on the pool does not. If nothing else changes, a "reflection" is a
denomination change. It only becomes value if the price holds while your share of supply
grows — and your share grows because *other people transacted*, which is the same
zero-sum statement as everywhere else in these documents.

## 2.2 Cross-asset distribution, and why it is expensive

The moment you want to pay holders in a **different** asset — SOL, USDC, ZEC, a tokenized
stock, another project's token — the accounting trick stops working. You now need:

1. Somebody to **harvest** the withheld tax (permissionless on Solana).
2. Somebody to **withdraw** it (requires the authority).
3. Somebody to **sell** it on a real market for the payout asset — with slippage, on a
   pool whose depth is the token's own.
4. Somebody to **snapshot** the holder set at a defined block.
5. **N transfers**, one per recipient.

Step 5 is the cost wall, and the driver is not the transaction fee — it is **rent**:

    SPL token account rent-exempt minimum   0.00203928 SOL  (2,039,280 lamports)
    at SOL $99.79                           $0.2035 per new recipient account
    Token-2022 accounts with extensions are LARGER and cost more

*(Source: Solana docs on token accounts and multiple wallet/infra guides, retrieved
2026-09-17. Solana's own docs warn against hard-coding it — query
`getMinimumBalanceForRentExemption` instead.)*

A holder who has never held the payout asset has no token account for it, so **the
distributor pays ~$0.20 just to create somewhere to send the money.** Paying 10,000 fresh
holders costs on the order of **20 SOL ≈ $2,000 in rent alone**, before fees, before
slippage, before the compute limits that cap how many transfers fit in a transaction.

**This is why every real implementation batches against a threshold.** Two live examples:

| Platform | Trigger | Source |
|---|---|---|
| **StonkFun** (transfer tax) | Accrues to a pot; pays out when the pot crosses a market-cap-scaled threshold: **$50** under $50k mcap, $200 at $50–100k, $250 at $100–125k, **0.1% of mcap** from $125k to ~$50M, **capped at $50,000** above that | third-party GitBook, **medium confidence** |
| **Bags index tokens** (creator fees) | Bot scans ~once a minute, starts a cycle once claimable fees reach **0.001 ETH** | Bags' own docs, **primary** |

**⚠️ The StonkFun ladder as transcribed is non-monotonic and one of its numbers is
probably wrong.** 0.1% of $125,000 is **$125**, so the threshold would *drop* from $250 to
$125 exactly at the boundary. Either the $250 band, the $125k boundary or the 0.1% rate is
mis-stated in the source. I am reproducing it as written rather than silently smoothing
it, and flagging that **at least one of those three numbers should not be relied on.**
The upper end does reconcile: 0.1% × $50M = $50,000, matching the stated cap.

And it is why both exclude some recipients. Bags' docs are explicit: contracts are
excluded (pools, the token itself, the fee-share contract, the bot wallet), **there is no
minimum balance**, but *"a share that rounds down to zero base units pays nothing for that
asset."* Small holders are formally included and practically paid nothing.

---

# Part 3 — The mechanic Frank asked about, and the correction

## 3.1 Correcting the premise

Frank's description: *"tax coins that airdrop you coins of another project (stonk)."*

**STONK is not that token. STONK is the platform token of StonkFun, a Solana launchpad.**
Verified from `stonkfun.xyz` and from a third-party GitBook reproducing its API:

- STONK itself launched through StonkFun's **Standard** flow — **no tax at all** — paired
  against SPYx, a Backed tokenized S&P 500 tracker. Fixed supply, mint and freeze
  authority revoked.
- STONK's own value mechanic is a **buyback and burn** funded by platform treasury revenue,
  not a tax distribution.
- It ripped >250% in 24 hours on 2026-09-06/07 on a Raydium LaunchLab integration
  announcement, hitting $0.212 and ~$135M daily volume.
  *(AirdropAlert, 2026-09-08 — a trading blog, and the price figures should be treated as
  such.)*

**The mechanic Frank is describing is StonkFun's Reward launch mode, which any creator on
the platform can select for their own token.** STONK is the ticker he happened to hear;
the thing itself is a launch option.

## 3.2 Three different things all called "airdrop," which is where the confusion comes from

Worth separating explicitly, because they behave nothing alike:

| Name | What it is | When |
|---|---|---|
| **Reward mode** | A permanent 1% or 3% Token-2022 transfer tax, harvested, sold for the quote asset, paid pro rata to holders in batches | Continuous, forever |
| **Airdrop Mode** | A one-time slice of supply held out of the pool and sent to existing holders of the *quote* asset (top 100 by default, exchange/custody/program wallets stripped and backfilled) | **Once, at launch.** The recipient list is frozen the instant the launch is built — you cannot buy in afterward to catch it |
| **Ecosystem Flywheel** | 5% of trading fees from every Reward pool, used to buy back and burn whichever platform tokens are currently top-10 by market cap | Continuous, but it burns, it does not distribute |

## 3.3 How Reward mode actually works, end to end

Source: `github.com/krisbuild/Stonkfun-gitbook-` (third-party, **medium confidence**,
but it publishes on-chain program IDs that are independently checkable), cross-read
against `stonkfun.xyz/rewards` (first-party).

**At launch.** The creator picks a quote asset from a curated list and a mode. Both are
permanent. Reward mode mints under **Token-2022** (`TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb`),
9 decimals, 1,000,000,000 supply, mint and freeze authority revoked automatically, with a
transfer tax of **1% or 3% fixed permanently at creation**. The creator chooses which.

**The quote asset is the payout asset.** Holders are paid in whatever the token trades
against — SPYX, NVDAX, TSLAX, ANTHROPIC, OPENAI, NEURALINK, USDC, xSOL, ZEC, HYPE,
another memecoin. A quote asset needs ≥$50,000 of Raydium liquidity and explicit team
whitelisting to be eligible.

**Where the tax goes.** Withheld on destination accounts by the token program, as §1.1
describes. Then:

> *"Once that tax starts accruing, one wallet — operated by StonkFun, and it alone — holds
> the authority to pull it out of every Reward mint on the platform. It harvests whatever's
> accrued, sells it on the open market for that token's own quote asset, and pays the
> proceeds out to holders in batches."*

That wallet is published as `5KXDF6QnqhBj72hDtJNkkpFaQVUfbFXNybMsp3DiK6tD`. **This is the
single most important fact in this document** and §4.2 is about it.

**What the creator gets.** *Nothing.* Reward tokens have no creator fee position at all.
Read that again in light of `CREATOR_PLAYBOOK.md` §2: the only way a Reward-mode creator
makes money is the **dev buy, capped at 75% of supply**, landed as the pool's literal
first trade inside the same atomic Jito bundle as the mint.

**Published scale.** Per team statements reported mid-September 2026: **>$35,000,000**
distributed across the StonkFun ecosystem, including **>$5,000,000 of ZEC** to $ZCAT
holders and **>$1,000,000 of HYPE** to HYPE-paired tokens. *(Team-stated, relayed by
AirdropAlert 2026-09-08 and a related post; **not independently audited.** Note that as of
retrieval on 2026-09-17, `stonkfun.xyz/rewards` itself rendered "No distributions yet" —
almost certainly because the page loads its data client-side and my fetch got the empty
shell, but I am recording that I did not see the numbers on the first-party page.)*

## 3.4 The other implementation: Bags index tokens

Same user-facing promise, **completely different plumbing**, and the difference is
instructive. Source: `docs.bags.fm/robinhood/index-tokens.md` — Bags' own docs, primary.

An index token is *"a Bags token on Robinhood Chain whose creator fees are automatically
converted into a basket of 1–10 tokenized assets (stocks like TSLA, NVDA, AAPL, …) and
distributed pro rata to the token's holders."*

    trades happen
    └── creator fees accrue (WETH) to the Bags claimer wallet
        └── bot claims once >= 0.001 ETH is claimable
            ├── snapshots current token holders
            ├── splits the ETH evenly across the basket (1-10 assets)
            ├── buys each asset
            └── transfers each asset to holders, pro rata by snapshot balance

To make this work the token must launch with **the Bags bot wallet as its only fee claimer
at 100%** (`0x6828E679Fb51b6d0416035370aF6Ec0fb2f2055a`). Initialisation is rejected with
403 otherwise. The basket is **immutable** after registration — 409 on re-init. Bags
claims **"no skim"**: 100% of claimed ETH is spent on basket assets, and
`distributableWei` always equals `totalWei` in the history payload, which is an auditable
claim because the full cycle history is a public API endpoint with transaction hashes.

**Head to head:**

| | StonkFun Reward | Bags index token |
|---|---|---|
| Funded by | Transfer tax, 1% or 3%, every transfer, every venue | Creator's half of the 2% trade fee |
| Applies to | All transfers including wallet-to-wallet | Trades only |
| Creator earns | Nothing | Nothing |
| Payout asset | The single quote asset | A basket of 1–10 |
| Trigger | Mcap-scaled threshold, $50 → $50k cap | 0.001 ETH |
| Controlled by | One StonkFun wallet, across every Reward mint | One Bags bot wallet, per token, required at 100% |
| Chain | Solana | Robinhood Chain (EVM) |
| Auditability | Payout history on a web page | Full cycle history API with tx hashes and snapshot stats |

**The design insight, and it is a real one.** StonkFun's docs explain why they chose a
transfer tax over a fee share: a fee-share reward *"is attached to a single pool, and a
competing pool for the same pair can undercut it elsewhere, routing volume — and the
reward stream — away."* A transfer tax is a property of the mint, so there is no cheaper
pool to route around. **That is correct and it is the sharpest argument for the tax
design.** Bags' index tokens have exactly the vulnerability StonkFun describes.

The flip side: a transfer tax also taxes you moving your own tokens between your own
wallets, and taxes the person selling — so it is more robust *and* more extractive.

---

# Part 4 — Being skeptical about this, on purpose

## 4.1 The structural statement

**None of this is yield.** No asset is produced. Every dollar distributed came out of
somebody's trade, and since a sell is a transfer, a meaningful share of every "reward" is
funded by the people leaving. A holder receiving a distribution is receiving a slice of
the exit liquidity of the person who just sold to get away from them.

Stated as an identity: over any period, `distributed ≈ tax_rate × volume`, and
`volume = buys + sells`. There is no third term. When volume goes to zero the distribution
goes to zero and the 3% you have been calling a feature becomes a 3% toll on your exit.
And volume does go to zero: `TRENCHES_REFERENCE` §1.3 records that **98.6% of pump.fun
tokens launched before April 2025 with ≥5 trades collapsed below $1,000 of remaining
liquidity.** Both qualifiers matter — the population is pre-April-2025, and the measure is
remaining liquidity rather than volume — but a pool bled to under $1,000 is not
transacting enough to pay anyone.

**Nothing about this makes it a scam.** It makes it a redistribution schedule, correctly
described. What makes it misleading is the marketing vocabulary — "dividends," "passive
income," "APY" — every word of which imports a production assumption that is not there.

The sharpest statement of this comes from StonkFun's own side of the table: *"Distributions
to reward-token holders are a mechanical property of the token, not a dividend or yield."*
**Provenance caveat:** that line sits in the third-party GitBook's "What StonkFun is not"
section. I could not confirm it on a first-party page — `stonkfun.xyz` renders client-side
and my fetch returned an empty shell — so **whether StonkFun itself says this is
[UNVERIFIED]**, which matters, because I am using it as the section's honesty benchmark.

## 4.2 The failure modes, ranked by how much they should worry you

**1. The withdraw authority is the whole system, and on StonkFun it is one wallet for
every Reward token on the platform.**

`5KXDF6QnqhBj72hDtJNkkpFaQVUfbFXNybMsp3DiK6tD` alone can turn accrued tax into money.
The tax accrues on-chain automatically and permissionlessly. **The distribution does not.**
There is no on-chain obligation to distribute, no escrow, no timelock, no bond. If that key
is lost, compromised, or the company simply stops, the tax keeps being withheld from every
transfer of every Reward token forever and nobody can sweep it. Holders keep paying and
stop getting paid.

This is not a hypothetical about StonkFun's intentions. It is the shape of the system.
**The correct name for it is counterparty risk**, and it is precisely the category
`/RULES.md` rule 20 says to ask about first: *"has anyone sold, can the deployer print
supply, can the deployer freeze the sale, is there a second side at all."* Add one:
**can the entity that owes you money actually be compelled to pay?** No.

**2. Mutable tax rate.** `SetTransferFee` exists. Two epochs of delay is real protection
only for someone watching. **The check is one field: is `transferFeeConfigAuthority` null?**
If it is not null, the 1% you bought into can become something else. StonkFun states its
rate is fixed permanently at launch; I did not independently verify that the authority is
actually `None` on a live Reward mint, and **that is exactly the kind of claim that should
be verified on-chain rather than read in documentation.**

**3. Confiscatory rates.** The fee is expressed in basis points and the extension permits
rates high enough to make selling pointless. Neodyme's *"Don't shoot yourself in the foot
with extensions"* (cited in `TRENCHES_REFERENCE` §1.1) flags `TransferFee` as one of the
extensions that reintroduces seller-side control after the classic authorities are revoked.
A mint with a live transfer fee and both classic authorities revoked **passes every check
`paper.qualifies()` currently runs.**

**4. Distribution that quietly stops.** Distinguish sharply:

| Step | Enforced by | Can it stop? |
|---|---|---|
| Tax withheld on transfer | The token program | No — it is automatic |
| Harvest to mint | Permissionless | No — anyone can call it |
| Withdraw from mint | The withdraw authority | **Yes** |
| Sell and distribute | Nothing. Off-chain policy. | **Yes, silently, with no on-chain event** |

The first two being trustless is what makes the last two look trustless. They are not.

**5. The 75% dev buy.** A Reward-mode creator earns nothing from the tax, so the only
economic reason to launch one is to hold supply. StonkFun permits up to **75% of supply**,
landed atomically as the first trade. That is the extraction vector, it is disclosed, and
it means "the creator has no fee position" — which sounds reassuring — actually points at a
much larger position somewhere else.

**6. It taxes you, not just traders.** Moving tokens to a hardware wallet is a transfer.
Consolidating wallets is a transfer. Each one costs 1% or 3%.

## 4.3 The honest verdict

The brief asked: *if the honest verdict is that most of these are extraction, say it.*

Here is what I can and cannot support.

**What I can say.** The mechanic is real, it is mechanically sound on Solana, and where it
pays, it demonstrably pays — StonkFun's $35M+ figure is team-stated but the payouts are
on-chain and checkable in principle, and Bags' index tokens expose a full cycle history
with transaction hashes, which is more transparency than almost anything else in this
space offers. Both are more honest in their own documentation than their promoters are.

**What I can also say.** The source of every dollar is trading volume, the marketing
vocabulary is wrong in a way that systematically flatters, the entire distribution leg is
an unbonded off-chain promise, and on StonkFun that promise is concentrated in one key
across the entire platform.

**What I cannot say, and will not pretend to.** I have **no measurement of the class-level
failure rate** — what fraction of tax-and-distribute tokens stop distributing, and how
fast. No paper, dataset or vendor I could find has measured it. Given that 98.6% of
pre-April-2025 pump.fun tokens with ≥5 trades collapsed below $1,000 of liquidity, the
base rate for
*anything* memecoin-shaped is brutal, and there is no reason to expect this class to be an
exception. But **"the base rate is brutal" is not the same finding as "these are designed
to extract,"** and asserting the second without evidence would be exactly the kind of
confident-sounding unmeasured claim this repo's standing rules exist to prevent.

**The one thing I would say without hedging:** the promise being sold is *passive income*,
and the thing being delivered is *a claim on other people's trading activity, payable at
the discretion of a party you cannot compel.* Those are different products. Anyone
choosing between them should know which one they are buying.

---

# Part 5 — Could Frank build one, and should he

## 5.1 The three paths

**Path A — launch a Reward token on StonkFun.** Cost: near zero, one signature, one atomic
bundle. **Creator revenue: zero.** The only upside is the dev buy, i.e. a position. So
this is a trade wearing a creator costume, and `CREATOR_PLAYBOOK.md` §2.4 already covers
why mixing those is how the story becomes the justification.

**Path B — launch a Bags index token.** Requires the Bags bot as sole fee claimer at 100%,
so again **creator revenue: zero.** Also EVM, on Robinhood Chain, which is a different
ecosystem from where the repo's instruments and Frank's Fomo workflow live.

**Path C — build it.** Token-2022 mint with `TransferFeeConfig`, plus a keeper service
that harvests, withdraws, swaps through Jupiter, snapshots holders, and batch-distributes.
That is genuinely buildable and the hard parts are not the ones people expect:

- **Keeper uptime.** `/RULES.md` rule 22 is the relevant scar: four systems have produced
  convincing output while doing nothing. A distributor that silently stops is worse than
  one that never started, because holders are still paying the tax.
- **ATA rent funding.** ~$0.20 per fresh recipient, fronted by you, non-recoverable by you.
  This is a real working-capital line that scales with success.
- **Snapshot correctness.** Which block, which exclusions, what rounding. Bags' docs show
  the edge cases: contracts excluded, truncation to zero for small holders. Get one wrong
  and you have either overpaid or shorted someone, on-chain, permanently.
- **Swap slippage.** You are selling the token's own tax into the token's own pool, which
  `TRENCHES_REFERENCE` §3.3 and §W2 show is thinner than any reported `liquidity.usd`
  suggests — overstated by a median 781× on the template population.
- **And the part that is not engineering:** you would hold the withdraw authority. You
  would be the sole party able to convert a pool of other people's withheld tokens into
  money, having publicly promised to send it back to them.

## 5.2 What I'd recommend

**Don't.** Three reasons, in order of weight.

**1. Both hosted paths pay the creator exactly nothing.** That is not a detail, it is the
whole business case. StonkFun and Bags both structure these so the creator's fee position
is surrendered to fund the distribution. The revenue is a *position*, which is trading.
If Frank wants the trade, take the trade and skip the token.

**2. Path C makes Frank the custodian of a promised pool of other people's money, with a
real name and a real LLC attached, and no license of any kind.** The `CREATOR_PLAYBOOK`
§3 finding applies with extra force here: DOJ charged Operation Token Mirrors defendants
with **wire fraud**, not securities fraud, which sidesteps the entire "is a memecoin a
security" question that the SEC's 2025-02-27 staff statement addresses. A scheme where you
collect money against a stated promise to distribute it is the cleanest possible fact
pattern for that statute if the distribution ever falters — including if it falters for
boring reasons like a keeper outage or running out of rent SOL. **Unlike the fee model,
which is structurally defensible, this one requires you to keep performing indefinitely
to stay on the right side of the line.** That asymmetry is the argument.

**3. It needs volume, which is the thing Frank does not have.** Every one of these designs
is a percentage of trading activity. A tax token with no traders distributes nothing,
which is the failure mode holders complain loudest about, which means the design converts
"my launch got no attention" — the overwhelmingly likely outcome per
`CREATOR_PLAYBOOK.md` §4 — into "my launch took people's money and gave nothing back."
**It takes the modal outcome and makes it look like the bad outcome.**

## 5.3 What is worth doing instead, and it is cheap

Not launching. **Reading.** Everything in Part 1 is a detection capability the repo does
not currently have, and `TRENCHES_REFERENCE` §4.3 item 2 already prices it at **zero
additional API calls**:

> `onchain.authorities()` parses `mintAuthority`, `freezeAuthority`, `decimals`, `supply`
> from a `getAccountInfo(jsonParsed)` response that **also contains the extension list**.

Add three fields from the response already being received:

| Field | Why |
|---|---|
| `extensions[].transferFeeConfig.transferFeeConfigAuthority` | non-null = the rate can change |
| `extensions[].transferFeeConfig.withdrawWithheldAuthority` | who owns the tax stream |
| `extensions[].transferFeeConfig.newerTransferFee.transferFeeBasisPoints` | the rate that will apply |

That turns "is this a tax token, who controls it, and can it change" into a fact the
scanner records on every observation, at no cost, and it closes part of the Token-2022
hole `TRENCHES_REFERENCE` §3.1 row 3 flags as absent. Per rule 10: **record it, score
nothing**, until there is a labelled set.

**This is the actual opportunity in this topic.** Nobody is measuring the tax-token
population. The repo already makes the call that would.

---

# Part 6 — What I could not verify

- **[UNVERIFIED]** That `transferFeeConfigAuthority` is actually `None` on live StonkFun
  Reward mints. The documentation says the rate is permanent. **This is checkable with one
  free RPC call on any Reward mint and should be checked before believing it.**
- **[UNVERIFIED]** StonkFun's $35M+ distributed, the >$5M ZEC to $ZCAT and >$1M HYPE
  figures. All team-stated, relayed by a trading blog. The first-party rewards page
  returned an empty shell to my fetch.
- **[MEDIUM CONFIDENCE]** Everything sourced to the third-party StonkFun GitBook —
  payout thresholds, the 75% dev buy cap, the withdraw-authority wallet, the $40,000
  graduation threshold. The program IDs it publishes are independently verifiable on-chain
  and none of them contradicted anything else I found, which is why I am using it, but it
  is not StonkFun's own documentation.
- **[UNVERIFIED]** The exact maximum permissible transfer fee in basis points. I know the
  extension permits rates high enough that Neodyme warns about confiscatory levels; I did
  not confirm the hard cap constant and have not stated one.
- **[NOT MEASURED ANYWHERE]** The class-level survival rate of tax-and-distribute tokens.
  See §4.3. This is the single biggest hole in this document and it is a hole in the
  literature, not just in my research.

---

# Sources

Retrieval date 2026-09-17 for all.

**Primary — protocol**

- Solana Foundation, *Transfer Fees* (`solana.com/docs/tokens/extensions/transfer-fees`;
  mdx source via `github.com/solana-foundation/solana-com`). Withheld-on-destination
  semantics, `HarvestWithheldTokensToMint` permissionlessness, `SetTransferFee` two-epoch
  delay, both authorities.
- Solana Foundation, *Create a Token Account* — ATA rent-exempt minimum 0.00203928 SOL,
  and the warning not to hard-code it.
- Neodyme, *SPL Token-2022: Don't shoot yourself in the foot with extensions* — via
  `TRENCHES_REFERENCE`.

**Primary — platform**

- Bags, *Launch an Index Token* (`docs.bags.fm/robinhood/index-tokens.md`). Cycle
  mechanics, 0.001 ETH threshold, required claimer, no-skim claim, exclusions, immutable
  basket.
- Bags, *Claim Creator Fees* (`docs.bags.fm/robinhood/claim-fees.md`).
- StonkFun, *Rewards* (`stonkfun.xyz/rewards`) — v3 transfer-tax vs legacy 85%-of-4%-pool
  distinction.

**Medium confidence**

- `github.com/krisbuild/Stonkfun-gitbook-` — third-party StonkFun deep dive. Launch modes,
  tokenomics table, payout thresholds, quote-asset categories, program IDs, withdraw
  authority, Airdrop Mode, dev buy cap.
- AirdropAlert, *StonkFun Explained*, 2026-09-08 — STONK/SPYx pairing, price action.
- AirdropAlert, *Holder Airdrops Are Back* / *Tokenized Stock Airdrops* — ZCAT/ZEC and
  HYPE figures. Team-stated, not audited.

**Ours, cited not restated**

`docs/TRENCHES_REFERENCE.md` §1.1, §1.3, §3.1, §3.3, §4.3, §W2; `/RULES.md` rules 10, 20,
22 (the standing rules — **not** `docs/RULES.md`); `FRAUD_DETECTION.md`;
`TEMPLATE_ATTACK.md`.

---

*Research document. Nothing was launched, deployed, bought or sold. No collector code was
read or modified.*
