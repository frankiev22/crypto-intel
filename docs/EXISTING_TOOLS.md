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

---

## 4. ⛔ The untrusted register — `RULES.md` rule 24 (2026-09-19)

Frank, permanent: every third-party crypto tool is untrusted. Two relationships
only: **REBUILD** (the capability becomes a feature of our site) or **AGGREGATE**
(read its public output over plain HTTP, never depend on it, never authenticate).
⛔ No wallet is ever connected to any of them. ⛔ No dependency that needs auth.
⚠️ Their numbers are marketing until our own data or the chain agrees.

**Method, 2026-09-19:** plain HTTP only (browser User-Agent, 20s timeout, no
browser, nothing installed, no login, no wallet), by two background agents; raw
responses kept in the session scratchpad. ⚠️ **Assessment touched paths that
robots.txt disallows**: 3 requests under fomolens `/api/` and 1 to copyfomo
`/api/find`, each the page's own call with its own example input. From here on
**AGGREGATE never reads a robots-disallowed path**, which rules both out as
sources regardless of label.

| tool | what it demonstrably does | public, keyless output | label | why |
|---|---|---|---|---|
| **degentape.com** | a tape of tracked traders' calls and closes across Robinhood, Base, ARC, Solana, BNB; publishes its own 37% win rate on 9,979 closes | the tape | **AGGREGATE** (relay, established) | ⛔ do not rebuild a tape. ⭐ **182 / 182 sampled fills verify on chain**; the 37% is a different quantity from ours (§4a). Its public tape is the per-wallet buy data we lack |
| **trenchscope.live** | alerts when 3+ top-PnL wallets buy one token inside 10 min for ≥ $1,500 combined; wallets re-ranked nightly on 90-day realized PnL; Helius gRPC | none worth reading; record shows winners only, fine print calls figures illustrative | **REBUILD** (relay, established) | the rule is pre-committed as a test before it becomes a feature: `PRECOMMIT_cluster_rule.md`, **NOT RUN** |
| **hogen.pro/fomo-helper** | an MIT-licensed Chrome extension ("Fomo Lens" v0.9.26), no server of its own; one card from Fomo (user's login), DeBot, FxTwitter, Dexscreener | none of its own | **REBUILD** | holders card = Helius holders + swap parsing (`chainfields.holder_count`, `devwallet.first_buyers` cover part); pools we already read. ⛔ Installs unpacked outside any store and runs script on GMGN/XXYY pages where trading wallets are logged in. Fomo holder theses are behind a login: not rebuildable |
| ↳ **DeBot story endpoint** (`app.debot.ai/api/v1/nitter/story/latest?ca_address=`) | AI-written token narrative, background, developer info | ✅ 200 without login (BONK, entry 24 days old) | **AGGREGATE candidate, not adopted** | terms not found (`robots.txt` 404). ⛔ carries `rating.score` - a quality score, which the site may never display. Needs its own terms check first |
| **fomolens.app** | claims an unofficial fomo.family API: handle ↔ wallet, profiles, graph, "sampled PnL" | `/api/public/coverage` (aggregate counts: 427,186 users, 328,055 Solana mappings); free lookup 1 req/10s site-wide | **REBUILD** | robots.txt disallows `/api/`; terms forbid extracting the dataset; paid tiers $49 / $549 / $1,399 per 30 days in USDC; operator unnamed; PnL is sampled from Fomo, not chain. Identity map needs Fomo login data: not rebuildable under rule 15 |
| **copyfomo.com/find** | finds a Fomo trader's wallet, then copy-trades it through a Telegram bot | truncated addresses only; full ones in Telegram | **neither** | ⛔ **the same handle returns two different wallet pairs** (API/home vs `/traders/unipcs`, different follower and trade counts); custody contradicts itself; a token, referrals, ad pixels despite a no-tracking policy; executes trades. robots.txt disallows `/api/` |
| **fomowalletfinder.com** | paste a Fomo handle, get "verified" wallets | `api-production-9541.up.railway.app/get-user/{handle}`, no auth | **REBUILD** | ⛔ **every address came back null with status "verified"**, on all three of its own example handles. Backend is FomoScan (paid, $79-$1,395/mo); its public spec says Fomo's fee/referral payment is recorded on Solana, so Fomo trades are identifiable from chain by fee recipient. Rebuild = index that recipient with Helius; needs one confirmed Fomo trade to read the address off |
| **nockterminal.com** (+ `/scout`) | Telegram trading/copy bot and a wallet leaderboard | leaderboard sits in a Supabase table needing the site's embedded key (401 without); Base path is a Blockscout pass-through (429) | **neither** | Robinhood Chain and Base only, **no Solana path**; paid trending placement (49/89/149); ranks wallets by simulated copy profit; "non-custodial" bot that holds keys. No terms page |
| **985monitor.xyz/fomo** | unknown | unknown | **not assessed** | ⛔ the ISP's own filter (Spectrum Security Shield) blocks it as "Suspicious Site Blocked"; HTTPS resets, no Wayback copy. DNS resolves (Cloudflare). Assessable only from another network (the runner) or if Frank allowlists it - his call |

⚠️ **`AgmLJBMDCqWynYnQiPCuj9ewsNNsBJXyzoUhD9LJzN51` - the alleged "Fomo co-sign
wallet that marks scams and farms".** From chain (2026-09-19): a high-volume app
**fee payer / co-signer**, ~73k transactions an hour, fee payer on 60/60 sampled,
2 signers per transaction, routing through DFlow. It **signs** users' swaps; nothing
in any sampled transaction labels, flags or refuses a token. fomolens has no
Fomo user mapped to it, and none of the three Fomo tools names it or any co-signer.
⭐ **And the Fomo traders' own fills do not carry it:** in the degentape sample (§4a)
the 3 fomo.family-sourced traders' **37 fills have no co-signer at all** (the
wallet signs alone), and AgmLJ appears in **0 of 182** fills. The only recurring
co-signer is `FHpcNSe6tb2n15bAdq4BkeYWGyZKFD7yLYrH92ng7wCT`, on 37 USDC fills by
pump.fun-sourced traders, taking a small USDC fee. n = 3 Fomo traders is small.
**Verdict: a co-signer, not a labeller. The Fomo attribution is unsupported by
the chain and the "marks scams" claim has no support.** Use: at most an AGGREGATE source of one
app's retail order flow, and a wallet that must never count as a trader in any
cluster test (`PRECOMMIT_cluster_rule.md`, definition of wallet).

**Where the list came from, and whether 985monitor is worth routing around**
(2026-09-19, relay's observations from Frank's bookmarks; ⚠️ **not verified by
us** - reading X needs credits we do not have, BACKLOG C11):

- **The same eight tools were reposted four days later by a Chinese account
  (@qkl2058) with two referral links appended** (GMGN and FOMO, both `/r/` codes).
  Same list, two accounts, monetised on the second pass: **treat the whole list as
  promotional distribution, not independent recommendation.** It fits what the
  assessment found on its own: of eight, one is worth aggregating, and three
  make claims their own output contradicts.
- **A narrative-method post from @0xPINK3** carries its content inside images, so
  nothing is machine-readable; the account was an earlier paid partnership. Low
  priority, not assessed.
- **985monitor.xyz: blocked, not assessed, and not worth routing around.** The
  ISP's own security filter flags it as suspicious; it came from a list now known
  to be promotional; and the seven siblings that could be read produced one
  aggregate source between them. If it is ever wanted, the only acceptable route
  is a text-only fetch from the GitHub runner (another network, no browser, no
  script execution) - not a change to the filter on Frank's network.

### 4a. degentape's win rate against our paper log, and its fills against the chain

**The relay's "37% over 9,979 closed" is a live rolling figure, not a record.**
The homepage number is `wins / closed` from `GET /api/stats?window=24h`, all
chains pooled. Read 2026-09-19 ~18:30Z:

| window | wins / closed | rate |
|---|---:|---:|
| 1h | 168 / 406 | 41.4% |
| 24h | 3,725 / 9,781 | 38.1% |
| 7d | 21,611 / 57,880 | 37.3% |
| all (data from 2026-09-07) | 27,910 / 74,207 | 37.6% |
| Solana only, 24h | 3,406 / 8,657 | 39.3% |

**What their number counts (inferred from their own records, not published):** a
trade is one wallet's position in one token; it closes when that wallet's sells
seen by the site cover its buys; **a win is any realized profit above $0** (a
+$0.20 trade is a win), counted per trade, not weighted by size. Checked on 16
wallets whose trades rebuild fully from the tape: the count matched "profit > 0"
on all 16. **Whose trades: 905 wallets imported from leaderboards** (442 pump.fun,
215 fomo.family, 147 robinhoodtrenches, 90 hoodwatch, ~11 user-added).

**Our side (`paperv3.summary()`, 2026-09-19 18:40Z):** 58 entries, **24 closes on
24 distinct contracts**, 34 open, 0 voids. Below the pre-committed n = 30, so
**no rate** (`PRECOMMIT_paper_v3.md` §7, standing rule 7). Counts only: **5 of 24
closed above cost**, all five at the 2.0x target (2.06x - 5.17x); **11 were total
losses** (Jupiter `NO_ROUTES_FOUND`, pool drained); the **8 max-hold closes were
all below 0.16x**. Nothing closed between 0.16x and 2x.

⭐ **The two numbers are not in conflict, because they are not the same quantity:**

| | degentape | our v3 |
|---|---|---|
| who picks the trade | 905 wallets **chosen from leaderboards**, i.e. selected on past profit | a pre-committed rule over every token our scanner sees |
| win | **any profit > $0** | exit at **>= 2.0x**, or held to 24h |
| exit | whenever the trader chooses, including small profits | the rule's, never discretionary |
| fills | the traders' own, on chain | Jupiter quotes at $100 |
| survivorship | a wallet removed from their list is removed from the history (inferred: stats equal the sum over currently tracked wallets) | append-only, nothing removed |

A leaderboard-selected population winning 38% of trades on a profit-above-zero
definition is **not evidence** that a rule can pick winners, and our n = 24 is not
evidence against it. **Neither of us is shown wrong. Neither number transfers.**

⭐ **Re-derived from their own tape, 2026-09-19 ~19:30Z** (`analysis/cluster_rule_2026-09-19/dt_positions.py`):
281,000 Solana tape rows, 09-11 20:56Z → 09-19 18:07Z, rebuilt into **45,853 closed
positions** (671 wallets, 18,804 tokens) opened 09-12 or later. Excluded and
counted: 14,832 wallet-token pairs opened before the window, 8,065 still open,
1,189 with a fill lacking `usd`.

| definition | closed positions | rate [Wilson 95%] |
|---|---:|---|
| **theirs: proceeds > cost** | 18,200 / 45,853 | **39.7%** [39.3, 40.1] |
| their own published all-time Solana figure | 22,947 / 58,313 | 39.4% |
| **ours: proceeds >= 2x cost** | 2,769 / 45,853 | **6.0%** [5.8, 6.3] |
| ours, one close per token (first) | 818 / 18,804 | **4.4%** [4.1, 4.7] |

- **Their headline reproduces from their own fills, within 0.3 points.** Their
  arithmetic is honest.
- **The median closed position returns 0.925x** (p10 0.40, p25 0.67, p75 1.16,
  p90 1.59). **Median hold: 2.4 minutes** (p25 0.4, p75 19.8). The ~38% is mostly
  small, fast scalps by wallets chosen for past profit.
- ⭐ **On our definition, 905 leaderboard-selected wallets double their money on
  6.0% of positions.** That is the first external reference point we have for how
  often a 2x happens, even for traders picked because they win.
- **Against our own base rate** (`PRECOMMIT_cluster_rule.md`, "Result", arm B): a
  token our scanner saw on an AMM reached >= 2x with >= $500 of depth at +6h or
  +24h, authorities revoked, **0.27% [0.05, 1.54] of the time (1 / 364)**. The
  two are still not the same quantity - theirs is a realized trade exit chosen by
  the trader, ours is the pool price at fixed horizons - so the gap (6.0% vs
  0.27%) measures selection and discretionary exits as much as anything. It does
  not show that copying them would work: their exits are theirs.
- v3's paper ledger: 24 closes, below n = 30, no rate (§4a above).

**Their fills against the chain, 2026-09-19.** 30 closed trades (the agent's
sample: 9 from the site's own win records, 21 rebuilt from the tape, 14 traders,
**182 fills**), every signature fetched with `getTransaction`:

- **182 / 182 exist, succeeded, and landed at the stated second.**
- **182 / 182 are signed by the named Solana wallet.**
- **182 / 182 move that wallet's token balance by the stated amount**, in the
  stated direction.
- **182 / 182 match on the quote side**: 145 on SOL (within 5%), 37 on USDC
  (within 2%). The 37 are USDC trades Jupiter routed through SOL; degentape's
  `sol` field is the routing leg and its `usd` is within 0.04% of the USDC paid.
- ⚠️ **Not random**: the sample is what the agent could reconstruct, and 9 of 30
  are the site's own showcased wins. It shows the fills are real, not that the
  rate is.

**Known defects in their data** (the agent's, from their own endpoints): the
7d/30d/all USD totals read **$2.46e27** (one BNCB buy priced at $9.8e26), so some
fills are mispriced; `/api/status` counts 728,489 fills against 453,122 in the
all-time stats, unexplained; their "unverified" flag is about cross-chain
payment proof, not token safety; two positions closed without a matching tape
sell or kept selling after closing (n = 2); index lag median 106s, p90 263s,
max 21 min.

⭐ **What degentape gives us: per-wallet buy data, which our journal does not
have.** `GET /api/tape` (no login, no robots.txt, no terms page found) carries the
Solana wallet in `solana`, the signature in `tx`, `usd`, `token_amt`, `side` and
block time. That is **arm D of `PRECOMMIT_cluster_rule.md`**, runnable without
any chain cost. The agent counted **70 tokens meeting the cluster rule in 4.4h of
Solana tape (~16 an hour)**, a count of fires, with no outcome looked at.

### What the register changes

1. **Nothing here is a dependency.** degentape is the one AGGREGATE source: its
   fills verify on chain and its tape supplies arm D of the cluster test (§4a).
   If it disappears, the test loses an arm and nothing on the site breaks.
2. **The one capability worth building is Fomo-trade identification from chain**
   (fomowalletfinder's backend describes it): Fomo's fee recipient → every Fomo
   trade → per-wallet cash-flow PnL from Helius history. That also yields the
   wallet set trenchscope's rule needs (arm S of the cluster test), without
   anyone's login. Not started; costed with the cluster test.
3. **Three of eight made a claim their own public output contradicts**
   (copyfomo's two wallets for one handle, fomowalletfinder's null "verified"
   addresses, trenchscope's "illustrative" figures). Rule 24's "marketing until
   verified" is not caution for its own sake.
