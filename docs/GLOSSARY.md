# Glossary

Written 2026-09-17. Plain English, one line each, alphabetical. Phone-readable.

Full operational definitions — what each thing looks like in on-chain data, and whether we
can detect it — are in **`docs/TRENCHES_REFERENCE.md` Part 1**. This file is the fast
lookup; that file is the real one. Creator-side detail is in
**`docs/CREATOR_PLAYBOOK.md`**, tax mechanics in **`docs/TOKEN_MECHANICS.md`**.

---

## The eight numbers worth remembering

| | |
|---|---|
| Graduation | **85 SOL** deposited → **410.8 SOL** FDV ≈ $40,994 at SOL $99.79 (2026-09-17) — *not* the $69,000 everyone quotes. **Read the SOL figure; the USD one drifts.** |
| Tokens that graduate | **0.198%** — about 1 in 500 |
| Tokens that graduate with no social links | **0.110%** — about 1 in 900 |
| Median time to graduate, if it happens | **1.0 minute** |
| Tokens that collapse below $1,000 of liquidity | **98.6%** (pre-Apr-2025, ≥5 trades) |
| Big winners that were manufactured | **82.89%** of tokens returning >100% |
| Supply held by linked wallets, on average | **36.5%** |
| pump.fun creators earning under $1,000 | **83.4%** — of those who earned anything at all, under the old 0.05% creator rate |

Sources and confidence intervals: `TRENCHES_REFERENCE.md`, `CREATOR_PLAYBOOK.md` §2.

---

## A

**airdrop** — Free tokens sent to wallets that meet some condition. Taxable as ordinary income at what they were worth the moment you could touch them.

**Airdrop Mode** — StonkFun's one-time version: a slice of a new token's supply is held out of the pool and sent to existing holders of whatever asset it trades against. The recipient list freezes when the launch is built, so you can't buy in afterward to catch it. → not the same as *Reward mode*.

**ATA (associated token account)** — The little on-chain account that holds your balance of one particular token. Costs about **$0.20** to create and somebody has to pay that — which is why paying 10,000 holders in a new asset costs ~$2,000 in account setup before anything else.

**AMM** — A pool of two assets you trade against, priced by a formula. What a token migrates into after graduation. → *bonding curve* is the thing before it.

## B

**bags / Bags.fm** — A Solana launchpad built around paying creators. Default is a flat 2% trade fee, **1% to the creator** on the curve and 0.75% after graduation, splittable across **up to 100 wallets**.

**basis point (bp)** — One hundredth of a percent. 100 bps = 1%. Fee configs are written this way, so read carefully: 300 bps is 3%, not 0.03%.

**bonding curve** — The formula a brand-new token trades against before it has a real pool. There's no other trader on the far side, just math. You can't "pull liquidity" from one because there isn't any. → `TRENCHES_REFERENCE` §1.1.

**bundling** — The creator putting the mint *and* their own buys from several wallets into one atomic package that lands in a single block. **Nobody can get in front of it at any speed** — it's not a race you can win with a faster connection. It's also the single clearest fingerprint of insider accumulation, and it's permanent on-chain. → `CREATOR_PLAYBOOK` §3.2.

**buyback and burn** — Using revenue to buy your own token off the market and destroy it. Reduces supply. Verifiable on-chain, unlike most promises.

## C

**claimer / fee claimer** — A wallet configured to receive a share of a token's creator fees. Bags allows up to 100, pump.fun up to 10. **The list can usually be changed later by whoever holds admin** — so if you're a recipient rather than the admin, your share isn't guaranteed.

**compounding (fee)** — A slice of trading fees pushed back into the pool instead of paid out, making the pool deeper over time. Bags compounds **25% or 50% of the post-graduation fee** depending on which mode the creator picked. It goes to the pool, not to the creator.

**coordinated accounts** — Wallets that look separate but are one person, linked by the trail of who funded whom. Averages **36.5% of supply** across 41,000+ launches. A token showing 4% "bundled" can still be 40% one person.

**creator fee** — A cut of every trade that goes to whoever launched the token. On pump.fun: 0.300% on the curve, up to 0.950% after graduation, decaying to 0.050% for large tokens. It comes out of the trade, not out of a reserve.

**CTO (community takeover)** — Holders of an abandoned token organise and keep promoting it without the original creator. Mechanically it means the deployer has already sold and left. Also a label anyone can simply claim.

**curve** — Short for *bonding curve*.

## D

**DAMM / DBC / LaunchLab / PumpSwap / Raydium** — Names of the specific pools and launch programs different platforms use. For most purposes they all mean "the real pool a token lands in after graduation."

**dev buy / self-buy** — The creator buying their own token at launch. Disclosed and permitted by every major platform (StonkFun allows up to **75% of supply** — `CREATOR_PLAYBOOK` §1.6, medium confidence). Buying it is fine. **Selling it into the people who showed up afterward is the thing that produces charges** (`CREATOR_PLAYBOOK` §3.2). The "31.04 SOL" threshold you'll see quoted is a *market cap*, not a deposit — see §2.4 before doing any math with it.

**dev wallet / deployer** — The address that signed the token into existence. Counterintuitive fact: a creator who bought their own launch is *more* likely to graduate, not less — **0.634% vs 0.053%** pooled, or 0.0848% against the highest non-self-buy quartile. It's a correlation, not a lever.

## E

**epoch** — Solana's scheduling period, a few days long. Matters because a transfer tax rate change takes effect **two epochs later** (Solana docs), which is the only warning you get. *(Exact epoch length not verified here.)*

**exit depth** — How much you could actually sell into, counting only the *other* side of the pool. Not the same as the headline "liquidity" number, which on some pools overstates what's really there by a median of **781×**. → our own instrument; `TRENCHES_REFERENCE` §3.3 and §W2.

## F

**FDV / market cap** — Price × total supply. On a token nobody has traded, this is a number the formula made up, not evidence anyone would pay it.

**freeze authority** — A switch that lets whoever holds it freeze your account so you can't sell. **This is the Solana honeypot, literally.** Launchpads revoke it automatically — 227 of 228 tokens we've checked.

## G

**graduation / migration** — When a token finishes its bonding curve and moves to a real pool. Happens at **85 SOL** deposited, working out to **410.8 SOL** of FDV (~$41k at SOL $99.79). Median time from launch: **one minute**. By the time it shows up in any feed it's already done. **Worth almost nothing to the creator by itself** — the fee rate only jumps 2.24% higher up, at a 420 SOL market cap.

## H

**hard rug** — Someone used a power they had: minted new supply into your bid, froze sales, pulled the liquidity. Rare now, because launchpads take those powers away automatically.

**honeypot** — You can buy and you can't sell. On Solana the ways to do it are freeze authority, a transfer hook that blocks the sale, or accounts that start frozen. On Ethereum it's just code in the contract that refuses.

## I

**index token** — Bags' name for a token whose creator fees automatically buy a basket of 1–10 other assets and hand them to holders. The creator gets nothing. → `TOKEN_MECHANICS` §3.4.

## J

**Jito bundle** — Up to five transactions guaranteed to land together in one block, all or nothing. About 400 milliseconds. The tool that makes *bundling* possible.

**Jupiter** — Solana's main trade router. Where a distribution bot would sell collected tax for whatever it's paying out in.

## L

**larp** — Claiming to be something you're not: a fake team, a fake partnership, a fake exchange listing. Impossible to check on-chain by design. The useful question isn't "is it true" but "who profits if I believe it."

**LP burn vs LP lock** — Burned means the pool tokens were destroyed and nobody can ever remove the liquidity. Locked means they're held under a timer that eventually expires. **A lock is a promise with a date on it; a burn is a fact.** pump.fun burns automatically at graduation.

## M

**maximumFee** — A hard ceiling on the fee taken from any single transfer, regardless of percentage. Without it a 3% tax on a big transfer is unbounded.

**mint authority** — A switch that lets whoever holds it print more supply into your bid. Revoked automatically by launchpads.

## O

**one-sided pool / template pool** — A pool that holds essentially all of a token's supply against almost nothing real, priced so the "liquidity" number looks enormous. Our own detector flags these at 100% precision **[85.7, 100]** and 46.94% recall — with the open caveat that 33 of 38 flags are fluxbeam pools, so "fraud detector" and "fluxbeam detector" aren't yet told apart. → `TEMPLATE_ATTACK.md`, `TRENCHES_REFERENCE` §4.0.

## P

**PvP** — The trenches describing itself: no new money coming in, everybody extracting from each other, every launch a transfer from whoever bought later to whoever bought earlier.

## Q

**quote asset** — What a token is priced against. Usually SOL. StonkFun lets you pick almost anything — a tokenized stock, another memecoin, USDC — and whatever you pick is also what holders get paid in.

## R

**reflection token** — A token where the tax "pays" holders in the same token. It isn't really a payment: everyone's balance number goes up at once through an accounting trick, and nobody is sent anything. → `TOKEN_MECHANICS` §2.1.

**Reward mode** — StonkFun's tax version: a permanent **1% or 3%** tax on every transfer, collected, sold, and paid to holders in whatever the token trades against. **The creator earns nothing from it.** → this is the thing people mean by "the STONK airdrop coins."

**rug pull** — See *hard rug* and *soft rug*. The second one is far more common and far harder to tell apart from ordinary failure.

## S

**slot** — One block of Solana time, about 400 milliseconds. A buy in the *same* slot as the mint can't have come from an outsider reacting to it — it was in the package.

**sniping** — Outside bots buying the instant a token launches. Different from *bundling* — a sniper is a stranger competing with you, a bundle is the creator pre-buying. **On a holder chart one minute in they look identical and they mean opposite things.**

**soft rug** — Nobody used any special power. The team just stopped, the insiders sold out slowly, the pool bled dry. Looks exactly like honest failure, which is the point. **This is the normal way these end.**

**SPL Token vs Token-2022** — Two versions of Solana's token program. The old one is simple. The new one supports add-ons like transfer taxes, transfer hooks and permanent delegates — things that can reintroduce control after the obvious switches have been thrown.

**Standard mode** — StonkFun's no-tax version: the creator gets 0.5% of the 1.25% trade fee instead. → contrast *Reward mode*.

**STONK** — **Not a tax coin.** It's the platform token of StonkFun, a Solana launchpad, and it has no tax at all. The tax-and-pay-you-in-another-asset thing is a *launch option* on that platform, not this token. → `TOKEN_MECHANICS` §3.1.

> **All StonkFun entries in this glossary** — *Reward mode*, *Standard mode*, *Airdrop Mode*, the 75% dev buy cap — come from a third-party GitBook and are **medium confidence**. `TOKEN_MECHANICS` Part 6 lists what that means and what wasn't checked.

## T

**ticker squatting / vamping** — Launching a token using a ticker that already has attention. Not fraud in itself — **57.9%** of tokens share a ticker with another, and FLORK alone has 25 separate contracts. Becomes fraud when it's built to make people think they're buying the original.

**Token-2022** — See *SPL Token vs Token-2022*.

**top-10 concentration** — What share of supply the ten biggest wallets hold. **Watch the trap:** the pool's own account is usually in that top 10 and holds nearly everything, which is why most "top 10 hold 99%!" screenshots are meaningless.

**transfer fee / transfer tax** — A cut taken off every movement of a token, including moving it between your own two wallets. On Solana it's a declared property of the token that anyone can read in one call. On Ethereum it's whatever the code does, which is a much worse deal. → `TOKEN_MECHANICS` §1.

**transfer hook** — A program that runs on every transfer and can **cancel it**. Different from a transfer fee, which only makes transfers expensive. This one is a honeypot mechanism; a fee is not.

**the trenches** — Trading tokens minutes old against automated bots. A war metaphor, used without irony.

## W

**wash trading** — Trading with yourself to manufacture volume, usually to buy a spot on a trending list. One documented case: 200 wallets funded with exactly 0.5 SOL each in 52 seconds, then $532,461 of "volume" across 40,523 trades. **People have pleaded guilty to this in US federal court.**

**withdraw withheld authority** — On a Solana tax token, the one wallet that can turn collected tax into actual money. **Whoever holds this owns the entire reward stream, and nothing on-chain obliges them to pass it on.** The single most important field to check on any tax token. → `TOKEN_MECHANICS` §4.2.

**withheld tokens** — Tax that's been taken but not yet collected. It sits on the *receiving* wallet's account, where the receiver can see it and can't touch it, until somebody with the authority sweeps it up.

---

*Reference document. Nothing here was built, launched or traded.*
