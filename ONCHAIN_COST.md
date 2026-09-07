# Unblocking the causal features: which tier, and what it costs

> ## ⚠️ CORRECTION, 2026-09-07: THE KEY ALREADY EXISTED. THIS WAS MY ERROR.
>
> Everything below concluded that holder concentration was "blocked by not
> having an API key" and that obtaining one was Frank's call. **That was wrong.**
> `HELIUS_API_KEY` has been in `.env` since **2026-08-23** — 15 days before this
> document was written — and `config.have("helius")` returned `True` the whole
> time. `config.helius_rpc()` already existed and already returned the correct
> authenticated URL. **Nothing called it**: `sources.py` hardcoded
> `https://api.mainnet-beta.solana.com`.
>
> So the measurements below are real but the conclusion drawn from them was not.
> I benchmarked the *public* endpoint, found it refused the method, and wrote
> that we were blocked — **without ever checking whether we had a key.** Holder
> concentration and the independent reserve read were blocked on nothing but
> not looking, for two weeks.
>
> Verified live 2026-09-07 on three journal mints:
> `getTokenLargestAccounts` returns in **94–193ms** through Helius and **HTTP
> 429** on the public endpoint for the same mint, same moment.
>
> Fixed: `sources.SOL_RPC` now calls `config.helius_rpc()`, falling back to the
> public endpoint when no key is set.

2026-09-06. Instruction was to report **exactly which tier unblocks it and the
monthly cost, so Frank decides with a number**. Here is the number.

**$0/month.** The blocked feature fits inside a free tier — just not the public
endpoint's. Nothing has been signed up for.

## What is blocked and why

`onchain.concentration()` needs `getTokenLargestAccounts`. On
`api.mainnet-beta.solana.com` it returns HTTP 429 *"Too many requests for a
specific RPC call"* — tested at 0s, 5s, 15s, 30s and 45s spacing, **0 of 5
succeeded**. It is limited *per method*: `getAccountInfo` and `getTokenSupply`
on the same endpoint work fine, which is why mint/freeze authority shipped and
concentration did not.

So this is not a rate problem we can pace around. The public endpoint refuses
that method at any spacing.

## What we would actually consume

Measured from this morning's pass — 79 tokens journalled, hourly:

    79 tokens/pass x 24 passes/day x 30 days   =   56,880 token-observations/month

| calls | per month |
|---|---:|
| `getTokenLargestAccounts` (concentration, blocked) | 56,880 |
| `getAccountInfo` (authorities, already working free) | 56,880 |
| **both, if routed through one provider** | **113,760** |

Peak burst is 158 calls in a pass, which at 10 req/s takes 16 seconds.

## Against the free tiers

| provider | free tier | our usage | verdict |
|---|---|---:|---|
| **Helius** | **$0 — 1M credits/mo, 10 req/s** | ~114k credits = **11%** | **fits, comfortably** |
| Alchemy | $0 — 30M CU/mo | ~2.3M CU @ 20 CU/call = **8%** | fits |
| QuickNode | trial only, no permanent free tier | — | rule out |
| public `api.mainnet-beta` | $0 | — | **refuses the method** |

Helius bills a standard RPC call at **1 credit** (`getProgramAccounts`, archival
and DAS calls are the expensive exceptions at 10–100). Even on the pessimistic
assumption that `getTokenLargestAccounts` is billed at 10 credits, the total is
~626k credits — **63% of the free tier, still inside it**.

The paid rungs, for context only: Developer $49/mo (10M credits, 50 req/s),
Business $499/mo, Professional $999/mo. **We need none of them.** Our whole
monthly requirement is a tenth of what they give away.

## The decision, stated plainly

Holder concentration is not blocked by money. It is blocked by **not having an
API key**, and the key that unblocks it is free. Frank's call, because it means
creating an account, and the standing rule is that I surface prices and never
sign up.

Two things worth knowing before he does:

- Helius's **Agent plan** (programmatic signup via their CLI) **requires a 1 USDC
  payment** to deter automated account creation. The ordinary web Free plan is
  the one costed above. Do not take the CLI route by accident.
- The key is a secret. It goes in the runner's secret store, never in the repo,
  never printed, never anywhere a browser can reach it.

Prices are list as of 2026-09-06 and these providers change them often. Re-check
before acting on this page.

## The trap this does not remove

`getTokenLargestAccounts` returns **the pool's own token account**, which for a
fresh launch holds nearly the whole supply. A naive top-10 share is ~99% for
every token, healthy or not — it would look like a devastating signal while
measuring nothing. `onchain.concentration()` already reports the raw share, the
share excluding the largest account, and whether the largest account matches
`liq_base`. Whoever turns this on should read that function before believing any
number it produces.

## And a caution from the feature that already works

Mint/freeze authority shipped, and it is **worthless here**: 227 of 228 tokens
had both already revoked, because the launchpads revoke them automatically. A
zero-variance feature cannot discriminate. Concentration may well go the same
way — it is worth measuring precisely because we do not know, but it should be
measured and reported with counts **before** it goes anywhere near a score.

Nothing in this document filters, gates or scores anything.

## Sources

- [Helius Plans and Pricing](https://www.helius.dev/docs/billing/plans)
- [Helius Pricing](https://www.helius.dev/pricing)
- [Alchemy — Solana RPC providers](https://www.alchemy.com/overviews/solana-rpc)
- [QuickNode — Best Solana RPC Providers 2026](https://www.quicknode.com/blog/best-solana-rpc-providers-2026)
- [RPC Fast — Solana RPC pricing in 2026](https://rpcfast.com/blog/solana-rpc-pricing)
