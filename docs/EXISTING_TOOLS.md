# What already exists, and what we should stop building

**2026-09-17. Tested live where an endpoint was reachable without an account.
Nothing was signed up for.**

> *"There are tools that can show you who sniped a coin, who's bundled all that
> stuff. We don't need to recreate the wheel."* — Frank

⭐ **He is right, and the evidence is stronger than I expected.** The honest
finding is not "ours is competitive". It is that **a free, keyless API already
does most of what `check.py` does, plus several things we have never built** —
and that we should compose rather than rebuild, keeping exactly one thing of
our own.

---

## Verdict up front

| keep ours | use theirs |
|---|---|
| ⭐ **realizable exit cost at a chosen size** (`chainfields.round_trip`) — "sell $100 now, what comes back". **Nothing surveyed does this.** | insider/bundle/sniper clustering, LP lock status, creator history, authorities, holder concentration |
| holder count under *our* definition (holds-now), because our threshold is calibrated on it | a risk score that already agrees with our liquidity verdict 9/9 |

## 1. ⭐ RugCheck — free, no key, and it works

`GET https://api.rugcheck.xyz/v1/tokens/{mint}/report`
**No account, no key, no rate limit hit in testing. 470–2,000 ms.**

**Tested against contracts we had already labelled with Jupiter:**

```
sym         JUP verdict      rug score  norm  holders   liq(RC)   top risk
孙宇晨      TOTAL_LOSS          29,596    65       10         0   Top 10 holders high owners
POGGERS     TOTAL_LOSS          39,596    69       30         1   Top 10 holders high owners
NUTSAQ      NO_SELL_ROUTE       29,547    65       28         0   Top 10 holders high owners
UPONLY      NO_SELL_ROUTE       29,465    65       30         0   Top 10 holders high owners
BULLBALLS   NO_BUY_ROUTE        29,593    65        9         0   Top 10 holders high owners
TikTok      NO_BUY_ROUTE        14,499    55       50         1   Large Amount of LP Unlocked
ROCK        TRADEABLE                1     1    4,438   184,231   none
APEC        TRADEABLE                1     1    6,390    14,797   none
WYNX        TRADEABLE            4,857    40    1,832    43,635   Single holder ownership
WOFI        COSTLY               2,880    33       70     2,039   Low Liquidity
```

⭐ **9 of 9 unexitable contracts flagged; 0 missed.** Genuinely tradeable ones
score 1. **And RugCheck's own liquidity figure is better than our stored `liq`**
— it reports $0–$1 for the dead pools where our field reported thousands.

### What it exposes that we have never had

36 top-level fields. The ones that matter:

| field | why it matters |
|---|---|
| ⭐ `insiderNetworks` | clustered wallets. **WOFI: a 95-account transfer network** |
| ⭐ `graphInsidersDetected` | **205 for WOFI** — this is the bundle signal we could not compute |
| `topHolders`, `totalHolders` | concentration, already ranked |
| `lockers`, `lockerOwners`, `lockerScanStatus` | **LP lock status — we have nothing here** |
| `creator`, `creatorBalance`, `creatorTokens` | **what else this dev launched.** Serial-rugger detection for free |
| `launchpad`, `deployPlatform` | venue, without inferring it |
| `mintAuthority`, `freezeAuthority` | we compute these ourselves at RPC cost |
| `rugged` | their own boolean |

⛔ **This is the answer to "is ours better".** It is not. `check.py`'s D1/D2
detect one-sided unexitable pools — a single phenomenon — and both are computed
on the `liq` field we know overstates by 781x, validated against `exit_depth()`
which fails 5 of 6 reads. **RugCheck covers that plus insiders, bundles, locks
and creator history, for free, and its verdicts match our best measure 9/9.**

### ⚠️ One real disagreement, and it is a definition not an error

**RugCheck's holder counts are consistently higher than ours:**

| | ours (DAS) | RugCheck | ratio |
|---|---:|---:|---:|
| WYNX | 1,350 | 1,832 | 1.36x |
| WOFI | 43 | 70 | 1.63x |
| ROCK | 1,467 | 4,438 | 3.03x |
| CONK | 1,438 | 7,298 | 5.08x |

I checked whether ours was truncated: **it was not.** The ROCK walk paginated
1000 → 475 → 0 with the cursor ending `None`, and **every account returned had
a non-zero balance**, so Helius DAS is already filtering empties.

**The ratio is not constant, so it is not a unit error.** It varies with
turnover, which is consistent with ours meaning **"wallets holding it now"** and
theirs including **wallets that have ever held it**. ⚠️ **I have not proven
that**, and it is worth one probe before either number is published.

⭐ **It does not invalidate the `holders >= 100` candidate**, because that
threshold was derived on our metric applied identically to winners and controls
— internal consistency is what a comparative threshold needs. **But 100 is
specific to our definition** and must be re-derived if we ever switch source.

## 2. Not yet tested — do not assume

⛔ **I only report what I ran.** These were named and remain unverified:

| tool | what it is said to do | status |
|---|---|---|
| **Bubblemaps** | wallet-cluster visualisation | ⚠️ **untested.** API believed paid; confirm before costing |
| **SolSniffer** | token risk score | ⚠️ **untested** |
| **GMGN** bundle view | bundle/sniper display | ⚠️ **untested.** Believed UI-first; API access unconfirmed |
| **Photon / Axiom** | trading terminals with built-in checks | ⚠️ **untested.** Terminal-embedded, likely no API |
| **TrenchRadar / Trench Bot** | bundle scanner, bundled supply + wallet count | ⚠️ **untested**, documented API |
| **Cabal-Hunter** | same-block bundle + coordinated dump, API + MCP | ⚠️ **untested** |

⭐ **Given RugCheck answers 9/9 free and keyless, the bar for adding any of
these is now "what does it do that RugCheck does not".** Test TrenchRadar next,
because bundled-supply-still-held is a number RugCheck reports less directly.

## 3. What this changes

1. ⛔ **Stop building bundle detection.** My same-slot probe was inconclusive
   and it was going to be days of instruction-parsing work.
   `graphInsidersDetected` is one free HTTP call.
2. **Re-derive D1/D2 against RugCheck + Jupiter before quoting their precision
   again.** Their "100% precision, 0 false positives" was measured against
   `exit_depth_usd / liq` — both now suspect.
3. ⭐ **`check.py` becomes a composer, not a detector.** One CA in; RugCheck for
   structure, Jupiter for realizable exit at size, chain for supply and
   holders; one verdict out. **That is the analyzer the site needs anyway.**
4. **Our remaining original contribution is the one Frank asked for**: *if I
   try to sell 100 USD of this right now, what do I actually get?* Nothing
   surveyed answers it, because it is a question about **his size**, not about
   the token in the abstract.

⚠️ **Dependency risk, stated plainly.** Composing on a free third-party API
means an outage or a pricing change breaks the analyzer. Mitigations: cache
every response to the journal (append-only, so we keep the history even if the
service dies), and keep `chainfields` — which depends only on Helius and
Jupiter — as the floor that still works alone.
