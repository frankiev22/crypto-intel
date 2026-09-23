# Bubblemaps: do not rebuild it. Link out now, embed only if Frank buys in.

**2026-09-23.** Frank: *"There is already bubblemaps. Either reverse engineer or
embed it."* And: *"Our differentiator is the facts around it, not the graph."*

⛔ **Decision: we do NOT build a bundle visualiser.** Under standing rule 17 this
is an **AGGREGATE** relationship, not a REBUILD.

---

## 1. What it actually does, and why rebuilding is the wrong trade

Bubblemaps renders holder wallets as bubbles sized by balance, with edges for
transfers between them, so visually-obvious clusters pop out. It is already
embedded in **DEXScreener, CoinGecko, Etherscan, pump.fun, Photon and DEXTools**,
so it is the de facto standard and our users have already seen it.

⭐ **Rebuilding it would take a week and land us at parity with a free widget.**
Everything that makes our answer different is on the *other* side of the graph:
who those wallets are, whether the pool is real, what a $100 exit actually
returns, whether the authorities are live, whether the quote leg is taxed.

---

## 2. The two integration paths, both probed 2026-09-23

| path | URL | probe result |
|---|---|---|
| ⭐ **link out** | `https://v2.bubblemaps.io/solana/token/<MINT>` | **HTTP 200** |
| **iframe embed** | `https://iframe.bubblemaps.io/map?chain=solana&address=<MINT>&partnerId=<ID>` | **HTTP 200** with `partnerId=demo` |
| (an older host) | `https://app.bubblemaps.io/sol/token/<MINT>` | 301 redirect, so not the current form |

The iframe needs `allow="clipboard-write"` on the tag for its copy buttons.
Supported chains include solana, eth, bsc, base, tron, ton, polygon, arbitrum and
others, so the same integration covers any chain we later add.

## 3. ⛔ The blocker on embedding, and it is a rule-9 blocker

**Their own quickstart says `demo` is for testing and that production needs a
dedicated `partnerId`**, which exists to enforce domain-level access control.
Obtaining one is a commercial step with Bubblemaps.

⛔ **Standing rule 9: "Free tools only. Never sign up for anything."** and rule 17:
**"Never take a dependency that needs auth."** A `partnerId` is an issued
credential tied to our domain, so requesting one is **Frank's decision alone** and
I am not making it.

⚠️ **Pricing is NOT ESTABLISHED.** Their quickstart points at a pricing section
for partner IDs and states no figure. I am not guessing one.

⛔ **And shipping `partnerId=demo` to production is out of the question**: it is
documented as test-only, it would break without warning, and it would be us
depending on someone else's demo key.

## 4. ⭐ What we do now, with no dependency and no signup

**Link out.** On any fact card for a mint, a plain outbound link:

```
https://v2.bubblemaps.io/solana/token/<MINT>
```

- Zero dependency: if Bubblemaps goes down, a link 404s and our facts still load.
- Zero auth, zero credential, zero cost, available today.
- ⛔ **Labelled as theirs**, never styled as our own analysis.

⚠️ **And it is labelled as UNVERIFIED by us**, per rule 17: *their claims are
marketing until verified against our own data or the chain.* We have not audited
their clustering and we do not vouch for it.

## 5. What we publish instead, and it is the differentiator

The graph answers *"do these wallets look connected"*. ⭐ **Our side answers the
questions no visualiser does**, and every one is derived on chain:

| our fact | where it comes from |
|---|---|
| is there a market at all, and what does **$100** actually return | `chainfields.round_trip()` |
| is the pool **real**, and which pool is it | `poolstate.state()` (derived, not indexer-trusted) |
| is the cap **backed** by anything | `intel.phantom` |
| are the authorities **live or revoked** | mint account, from chain |
| is the quote leg **taxed**, and can the rate change after you buy | `legs.py` |
| how many top holders recur **across other launches** | `concentration.py`, 43 of 474 over 60 mints |

⛔ **What we do NOT claim**, and the honesty here is the product: our own
coordination detector has **no signal both alive and demonstrated to
discriminate** (`PRECOMMIT_sybil_v1.md`), so we do not publish a bundle verdict
at all. **A link to someone else's graph plus "we have not validated this" is
more honest than a number we cannot defend.**

## 6. If Frank does want the embed

Then it is two lines of HTML and a `partnerId` in config. Nothing in the backend
changes, because the embed takes only the chain and the mint, both of which every
fact card already has. ⛔ **Until he says so, the link is what ships.**
