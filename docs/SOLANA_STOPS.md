# Stop losses and limit orders on Solana spot: what each one actually does, what it costs, and exactly what it can sign

2026-09-23. Written because Frank is splitting a Ledger cold bag from a hot
trading balance and asked where he can place stops and limits. **Nothing here is
from memory.** Every program id below was read off chain by this session; every
fee is quoted from the operator's own documentation with the page named; and
where two of their pages disagree, the disagreement is printed rather than
resolved by preference.

⛔ **Analysis only. Nothing in this file was executed, no wallet was ever
connected, and no transaction was ever signed.** Placing an order needs Frank's
signature, which this session must never have.

---

## 0. ⛔⛔ Read this before the options, because it is the part that matters

A stop loss on a memecoin is **a best-effort instruction, not a floor.** Jupiter
says so itself, verbatim, on its own docs page:

> "Stop Loss is not guaranteed to execute. When the trigger price is hit, the
> order is submitted for execution with your slippage tolerance applied. If the
> price moves past your Stop Loss trigger faster than the order can execute, or
> if liquidity is insufficient to fill the order within your slippage tolerance,
> the order will not fill. **This is especially common with low-liquidity tokens
> such as new memecoins or tokens that have been rugged.**"

⭐ **Our own data says the same thing, harder.** Of the gate-passing wins that
died between 09-21 and 09-22, **3 confirmed deaths were a single `Withdraw`
instruction as the last event on the pool**: USDCAT 09-21 19:54:19Z, OWL 09-22
07:14:06Z, X7 `BsE3…` 10:27:06Z. In every one of those the liquidity went from
whole to gone inside one transaction.

⛔ **A stop loss cannot fill against a pool that no longer has a quote side.**
There is no price between "healthy" and "zero" for a keeper to sell into. So for
the specific failure mode that actually destroys these positions, a stop loss
does nothing at all. It protects against a **drift down**, which is the failure
mode Frank is least exposed to at a $100 to $2,000 clip.

⚠️ And it is worse than neutral in one way: the trigger is a **USD price**, and a
thin token's printed price is exactly the number we have measured overstating by
a median 781x. A stop can fire on a price that was never obtainable.

---

## 1. ⭐ Jupiter Limit Order V2 (the "Trigger" product), verified on chain

**This is the only option that fits Frank's standing rules, and it is the one I
verified myself rather than read about.**

| | |
|---|---|
| program | `j1o2qRpjcyUwEvwtcfhEQefh773ZgjxcVRry7LDqg5X` |
| verified | executable, owner `BPFLoaderUpgradeab1e…`, **195,276 program accounts** |
| live? | ⭐ **yes** — 1,000 signatures in a single page, all inside 2026-09, newest **2026-09-23T01:17:56Z**, about 90 seconds before I read it |
| instructions seen | `InitializeOrder` 15, `CancelOrder` 6, `FillOrder` 2, `Route` 2, `TransferChecked` 7, `WithdrawFee` 7 (newest 25 transactions) |

### What signing authority it requires, measured rather than assumed

This was the actual question, so it was answered from transactions:

- **Every transaction on the program has exactly one signer** (25 of 25 sampled).
- ⭐ **The fill is signed by a keeper, not by the order owner.** One single keeper
  wallet signed every `FillOrder` in the sample:
  **`j1opmdubY84LUeidrPCsSGskTCYmeJVzds1UWm6nngb`** — note the `j1o` prefix
  matching the program id. The owner is not a signer on their own fill and does
  not need to be online.
- ⭐ **The owner can cancel unilaterally: 20 distinct wallets signed
  `CancelOrder`** in the same sample, i.e. cancellation is the maker's own
  signature, not the keeper's.
- On the legacy V1 program the fill path is visible in full:
  `PreFlashFillOrder` → `Route` → transfers, keeper-signed. It is a flash fill —
  the keeper borrows from the order's vault, routes the swap across Solana
  liquidity, and must return the proceeds in the same transaction.

**So the authority model is: one signature from Frank at order creation, which
moves the tokens he is selling out of his wallet into a program account. The
keeper then signs each fill. He keeps the right to cancel and recover.**

⛔ **The consequence for a Ledger cold bag is the important part: a stop loss is
not compatible with tokens sitting in cold storage.** The tokens must be
transferred into the order account when the order is created, which means they
must be in a wallet he can sign from, and once escrowed they are in a program
account rather than on the Ledger. **Anything he wants protected by a stop has to
live in the hot balance.** There is no arrangement that leaves coins on the
hardware wallet and still lets a keeper sell them.

### Order types

Verified from Jupiter's own docs:

| type | what it does |
|---|---|
| limit / take profit | sells when USD price rises above your level |
| ⭐ **stop loss** | *"a sell order that triggers when the price falls below your stop level"* |
| ⭐ **trailing stop loss** | launched **2026-07-03**. Tracks the highest price since activation and keeps the trigger a fixed percentage below it: `trigger = watermark × (1 − d)`. Trail **0.5% to 90%**, default 10%. Rises with price, never falls back |
| OCO | one take profit and one stop loss sharing a single deposit; either cancels the other |
| OTOCO | an entry order that, once filled, arms a TP/SL pair |
| DCA | time-based, or price-conditional inside a band |

⚠️ Triggers track **USD price**, not the exchange rate of the two tokens in the
order. Market-cap-based triggers are also offered.

### Cost

| item | amount | source |
|---|---|---|
| base fee, stable or pegged pairs | **0.03%** | Jupiter user docs |
| ⭐ base fee, **everything else — this is Frank's case** | **0.10%** | same |
| Ultra routing fee | **0% to 0.5%**, depending on pair and execution | same |
| trailing stop loss surcharge | ⭐ **none** — *"There is no extra fee for using the trailing order type"* | Solana Compass, 2026-07 |
| ⭐ **rent for the order account** | **0.00225 SOL ≈ $0.27** at SOL $119.01, computed from chain: `getMinimumBalanceForRentExemption(315)` = 2,250,440 lamports, and V1 order accounts measure exactly 315 bytes. **Refundable** when the order closes | measured myself |
| expiry choices | 1 hour, 1 day, **1 week (default)**, 30 days, or a custom date | Jupiter user docs |

⚠️ **Worst case on a memecoin sell is therefore 0.10% + up to 0.5% = 0.6%**, plus
slippage, plus the pool fee. That is real but small next to the exit costs already
measured at his clip: PURR/Hypurr costs **9.14%** to round-trip at $2,000 and LOOP
costs **35.31%**. ⭐ **The fee is not what will hurt him. The spread is.**

### ⛔⛔ The one blocker, and it is unresolved

**Jupiter's own two documentation pages contradict each other on transfer-fee
Token-2022 tokens, which is exactly the class Frank holds.**

| page | what it says |
|---|---|
| `docs.jup.ag/user-docs/trade/swap/limit-orders` | *"Limit Order V2 supports Token-2022 tokens, **including those that charge a transfer fee**"* |
| the same product, elsewhere in the docs | *"Token-2022 standard tokens with transfer tax features are **not supported**"* — because the creator can change the tax rate after the order is placed |
| trailing stop loss | ⛔ **unambiguous: transfer-fee tokens are EXCLUDED** from the trailing type |
| OTOCO | ⛔ refused when the token being **bought** charges a transfer fee |

**My own measurement, which leans toward exclusion but does not settle it:** of
the **40 most-touched mints** in recent V2 order transactions, **20 are
Token-2022 and ZERO of those 20 carry a `transferFeeConfig`**. ⚠️ **n=20 is too
small to call it a rule** — 0/20 still admits a true rate up to about 16% — so
this is consistent with exclusion, not proof of it.

⛔ **This matters directly: PURR (Hypurr) 300bp, ZCAT 300bp, KNOTS 300bp, LOOP
300bp and STONKCAT 100bp are all transfer-fee Token-2022 mints.** If the
exclusion is real, **he cannot place any stop loss at all on the majority of what
he is buying.** JEANPHIL (Token-2022, no fee), EMBER (plain SPL) and SOL are
unaffected either way.

⭐ **The only thing that settles it is placing one real order, and only Frank can
do that**, because it needs his signature. It is not a workaround being handed to
him in place of automation: it is the single step that cannot be delegated. Two
minutes on a minimum-size PURR stop loss answers it permanently, and the rent is
refundable.

---

## 2. ⛔ What does NOT pass Frank's standing rules, and why

### The Jupiter *developer* Trigger API is custodial. Do not use it.

`developers.jup.ag/docs/trigger` describes a hosted wrapper, not the on-chain
program above, and it says plainly:

> "Vault accounts (custodial) by Privy" … "each wallet gets a single vault (a
> Privy-managed custodial account)" … authentication is "Challenge-response JWT +
> API key".

⛔ **That is a third-party custodial account behind an auth dependency, so it
fails rule 17 (never take a dependency that needs auth) and rule 9 (never sign up
for anything) outright.** ⚠️ It is also why the two readings of "vault" conflict:
the *program* account the UI uses and the *Privy* account the developer API uses
are different things wearing the same word. **The on-chain path is the one
verified in section 1 and the one to use.**

### Legacy Jupiter Limit Order V1: sunset, confirmed by measurement

Program `jupoNjAxXgZ4rjzxzPMP4oxduvQsQtZzyknqvzYNrNu`, executable, 49,597 order
accounts of 315 bytes. ⭐ **I confirmed the sunset independently before finding
it documented:** across a 45-transaction sample spread over all of 2026, the
lifecycle instructions were **56 `CancelOrder`, 1 `InitializeOrder`, 1
`FillOrder`.** That is a program people are closing out, not using. Flat 0.1%
fee, no take-profit or stop-loss, no transfer-fee Token-2022. **Nothing new
should go here.**

### Trading terminals: all blocked by rule 9, not by quality

⚠️ **JTX (Jito Labs)** is the only one worth naming, because it is genuinely
self-custodial: *"JTX has users sign transactions from their own wallet, with
settlement happening on Solana, so funds are not pooled in an exchange-controlled
account."* It offers resting limits, brackets, OCO, stop orders and TWAP.
⛔ **But it is invite/early-access, so using it means signing up, which is
Frank's decision alone and not something this system may do.** ⚠️ **And I could
not verify its fee rate at all** — the fee is described only as "a fee on each
trade", 80% of which buys back and burns JTO. **Unverified: do not quote a JTX
fee number.**

⛔ **Every other terminal in this category (the bot-wallet class) works by holding
a key on Frank's behalf.** That is the one thing rule 17 forbids without
exception. They are not options at any fee.

---

## 3. ⭐ What this means for his actual split

| | |
|---|---|
| **Ledger cold bag** | ⛔ **cannot be protected by a stop loss.** Escrowing requires a signature and moves the tokens into a program account. A cold bag is protected by *being cold*, and its only exit is him signing a sell |
| **hot trading balance** | ⭐ stop losses are available here, on the on-chain V2 program, for **0.10% + up to 0.5%**, one signature per order, **$0.27 refundable rent**, cancel any time, keeper fills |
| ⛔ **the tokens he actually holds** | **blocked or unconfirmed** on the transfer-fee question for PURR, ZCAT, KNOTS, LOOP and STONKCAT. Confirmed usable for JEANPHIL, EMBER and SOL |
| ⛔ **what a stop cannot do** | fill against a withdrawn pool. Three of our confirmed deaths were one `Withdraw` instruction. **The dominant risk in this asset class is not covered by any stop loss that exists** |

⭐ **The honest conclusion: limit orders are worth using and stop losses are worth
setting, but a stop loss must not be treated as a risk control here.** The thing
that actually bounds his loss is position size, which he already has right at
$100 clips, and the exit-cost table in `data/findings/TICKERS_2026-09-22.md`,
which says a $2,000 LOOP position is effectively unexitable at 35.31% before any
stop ever triggers.

---

## 4. What is not answered, stated so nobody assumes it was

1. ⛔ **The transfer-fee question.** Two Jupiter pages disagree; my chain sample
   is n=20. Needs one real order.
2. ⚠️ **JTX's fee.** Not published anywhere I could reach.
3. ⚠️ **Whether the V2 order vault's withdraw authority is provably the maker's.**
   20 distinct wallets signing `CancelOrder` strongly implies it, but the order
   account layout was not decoded, so it is inference from behaviour rather than
   from the program's data.
4. ⚠️ **Keeper latency.** Jupiter documents that fills are not guaranteed but
   publishes no measured time-to-fill, and I did not measure one. **Standing rule
   13 applies: do not quote a duration without the sampling interval**, so no
   figure is given here at all.
