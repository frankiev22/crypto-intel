# The backend the site calls: nine read-only endpoints

2026-09-23. **This is the contract between the pipeline session (which owns
`intel.py`) and the site session (which owns `site/`).** Nothing here is
aspirational; every endpoint below was called against live data before this file
was written, and the sample outputs are real.

Frank: *"Let's take everything we have been talking about and discovered and
implement it into our site in a meaningful way. Are you able to add wallet
connection to our site?"*

---

## 0. ⭐ The product thesis, so the wiring serves it

**Connect a wallet and find out what you actually own.**

Reading Frank's wallet by hand on 2026-09-22 taught him, in one sitting, that the
PURR he holds is not Hyperliquid's token, that the thing he called "Fone" is
apeonfone, and that he holds 195,771 units of a mint with no pools. **He had been
trading for weeks.** Every portfolio tracker showed him a green number. None of
them say *this position has no market* or *this cap sits on $342 of real
liquidity*.

⭐ **That gap is the whole product, and it is measurable.** On Frank's own PURR
position of 19,772.37 tokens, his tracker showed **$163.92**. A live sell quote
for that exact quantity returns **$158.50**. Neither number is wrong; only one of
them is what he would receive.

## 1. ⛔ Wallet connection: yes, with one hard boundary

**Yes, the site can connect a wallet, and it must connect it in read-only mode.**

- The site asks the wallet for its **public key** and nothing else.
- It passes that public key to `GET /api/wallet?pubkey=...`.
- ⛔ **It never requests a signature, never builds a transaction, never asks for
  an approval or a delegate, and never touches a private key.**

That boundary is enforced in code, not by convention: `test_intel.py` parses
`intel.py` at the **AST level** and fails if any name in it matches `sign`,
`send_transaction`, `keypair`, `secret_key`, `approve`, `delegate`,
`set_authority`, `place_order` or a dozen more. `intelserve.py` refuses POST,
PUT, PATCH, DELETE and HEAD with **405** before routing. Verified live:

```
POST   /api/wallet -> HTTP 405
DELETE /api/liquidity -> HTTP 405
  "this API is READ ONLY and serves GET only. It has no endpoint that can
   sign, send, approve or custody anything."
```

⚠️ **A message-signature login ("sign this nonce to prove ownership") is still a
signature request** and is out of scope for this backend. If the site ever wants
one, it is a separate decision with Frank, not a detail of this API.

## 2. The response envelope, identical on every endpoint

```json
{
  "kind": "liquidity",
  "subject": "5dvXTZ5q...",
  "ok": true,
  "ts": "2026-09-23T02:11:04Z",
  "took_ms": 257,
  "data":        { ... the answer ... },
  "provenance":  [ {"field": "liq_usd", "source": "dexscreener ... all pairs summed", "at": "...", "note": "..."} ],
  "not_checked": [ {"field": "you_get_usd", "why": "NO SELL ROUTE. There is no market ..."} ],
  "warnings":    [ "..." ]
}
```

⛔ **Three rules the front end must honour, because they are why this exists:**

1. **`not_checked` is not an empty state.** A field listed there was **not
   checked**. It must render as *not checked*, with the `why` string, and never
   as a dash, a zero, a green tick or a blank. This is the
   `authority_live=None` bug class: *not checked* displaying as *checked and
   fine* is how five separate failures happened.
2. **Every number on screen should be able to show its `provenance`.** A number
   with no source is not a number.
3. **`ok: false` means no answer was produced.** It is never "probably fine".

## 3. The endpoints

Base: `GET /api/<name>`. All GET, all public, all cacheable. `Cache-Control` is
set from the per-endpoint TTL and CORS is open, because every response is public
chain and public index data and contains nothing private.

| endpoint | required | optional | TTL |
|---|---|---|---|
| `liquidity` | `mint` | | 60s |
| `resolve` | `ticker` | `since`, `chain`, `max_candidates` | 300s |
| `phantom` | `mint` | | 60s |
| `exit_depth` | `mint` | `size_usd`, `raw_qty` | 30s |
| `safety` | `mint` | | 180s |
| `bundle_check` | `mint` | `n_buyers` | none |
| `paired` | `mint` | | 900s |
| `concentration` | `mint` | `deep`, `max_walk` | 600s |
| `wallet` | `pubkey` | `price_all`, `max_positions` | 30s |

---

### `liquidity(mint)` ⭐ built first, everything depends on it

Liquidity and volume **summed across every pair**, never one pool. Returns
`pair_count`, `liq_usd`, `vol24_usd`, `mcap_usd`, `price_usd`, `venues`,
`quote_assets`, `shape`, `symbol_display`, `symbol_flags`, and crucially
`deepest_pool_liq_usd` + `single_pool_would_understate_by` so the size of the
error a one-pool read would have made is **visible rather than hidden**.

Live, on the real EMBER: **30 pairs, $2,268,256, shape LIQUID, and a one-pool
read would have said $643,121, 3.53x too low.**

⚠️ **`is_floor: true` means the 30-pair API cap was hit.** Dexscreener returns at
most 30 pairs for any mint; SOL returns 30 too. So 30 means "30 or more", the
total is a **floor**, and the missing pools cannot be bounded because the
returned 30 are not ordered by size. **Render a floor as `$2.27M+`, never as
`$2.27M`.**

⚠️ `liq_usd` is a correct sum of an **overstating** field, measured overstating
by a median 781x. It answers *what shape is this token*. It is not an exit price.

---

### `resolve(ticker)` ⭐ the call that would have saved an entire day

Every mint wearing a ticker, which one is real, and **the impersonators named**.

Live, `resolve("EMBER", since="2026-09-10", chain="solana")`:

```
status RESOLVED | 16 candidates | dominance 538.95x
winner  5dvXTZ5qwgafnHtwu3Ls3QrWx1U4LQsFeCuJgkk4QEC6  "embercurve"  $2,266,278  30 pairs
  FEEiSWLL...  Ember Bot     THIN          $4,205      eligible
  8Y72D2ug...  embercurve    NO_LIQUIDITY  $0          eligible
  EPT3ta6E...  embercurve    LIQUID        $1,453,007  REJECTED: first pool 2026-09-22 postdates 2026-09-10
  B2p7GHu6...  Ember The Fox THIN          $6,186      REJECTED: first pool postdates
  FLCr9vGM...  embercurve    PHANTOM       $1          REJECTED: a claimed cap with no liquidity behind it
  DuK4Ni9L...  embercurve    NO_LIQUIDITY  $0          REJECTED: postdates
  DEq8hdb5...  embercurve    NO_LIQUIDITY  $0          REJECTED: postdates
```

⭐ **Six different mints on Solana are named "embercurve".** One of them holds
**$1.45M** and is excluded only by the date rule.

The rule is pre-committed in `intel.resolve()`: candidates from two independent
searches, each measured with all-pairs liquidity; a phantom can never win; if
`since` is supplied, any candidate whose **first pool postdates it** is rejected;
and the leader is only called `RESOLVED` if it holds **>= 5x** the runner-up.
Otherwise `AMBIGUOUS` and **nothing is called real**.

⛔ **`status: "AMBIGUOUS"` must render as "we do not know which one this is",
never as a best guess.** Without the date rule the EMBER case is exactly that.

---

### `phantom(mint)` ⛔ is the market cap backed by anything

Fires on **market cap > $1,000,000 with total liquidity < $1,000 across all
pairs**. Live, on the mint that cost us a day: `PHANTOM`, *"$1,314,046,208 of
claimed market cap on $1.39 of liquidity across all 3 pairs."*

⚠️ Returns **`UNEVALUABLE`**, never `false`, when the pair list was truncated.
Thirty arbitrary pools summing to nothing says nothing about a thirty-first.

---

### `exit_depth(mint, size_usd | raw_qty)` ⭐ the only realizable number here

Not *there is $500k of liquidity* but *you get $94 back on $100*.

- `?size_usd=2000` buys and sells straight back, and returns `verdict`,
  `usd_back`, `cost_pct`, `price_impact_pct`, `venues`.
- ⭐ `?raw_qty=19772370000000` prices **the exact position held**. This is the
  one that matters in a wallet, because a $100 probe says nothing about exiting
  195,771 units.

Live on Frank's PURR position: `QUOTED, $158.50, impact 1.16%, via Meteora DLMM`.

⛔ **Both legs are quotes. Nothing is executed and no wallet is involved.**

⛔ `NO_SELL_ROUTE` is an **answer**: it means there is no market at any size.
`QUOTE_FAILED` is **not** an answer and must never render as `$0` or as a loss;
it appears in `not_checked`.

---

### `safety(mint)` ⭐ `check.py` published

The project's one characterised component, with its numbers attached: **D1
precision 97.3% [86.2, 99.5], recall 50.0% [38.7, 61.3], n=37 flagged, out of
sample. D2 is in sample and unvalidated.**

⛔ **`not flagged` means "neither of two frauds was detected", on a detector that
misses half of what it looks for.** It is not a clean bill of health. The
response always carries `fake_volume` and `bundles_insiders` in `not_checked`,
**in words**, so the front end cannot imply they were covered.

---

### `bundle_check(mint)` ⛔ read the label before wiring this

**Correction to the brief, led with:** the ask was *"the thing the Stonk fee
backlash is about. `check.py` is our one validated component. Publish it."*
`check.py` is published, as `safety()` above. ⛔ **But `check.py` is not a bundle
checker and never was.** It does not look at first buyers or funding graphs.

What we actually have is `devwallet.buyer_funding_overlap()`, and it ships
labelled: **`status_of_this_check: "UNVALIDATED"`**. On n=4 it did not separate
good tokens from bad (`docs/DEV_WALLET.md` §5). It is here because a first-buyer
funding graph is informative to look at, **not** because it has a measured hit
rate. It has none. ⛔ **Do not gate anything on it, and render the UNVALIDATED
label next to any output.** It is also slow and RPC-heavy, so `wallet()` never
calls it.

---

### `paired(mint)` ⭐ what it is denominated in, and what the tax does

Live, on Hypurr:

```
is_asset_paired      True
paired_to            ["HYPE", "PURR", "VCF"]
quote_assets         HYPE $541,218 | SOL $270,877 | PURR $55,517 | USDC $51,380 | VCF $4,713
token_program        Token-2022
transfer_fee_bps     300      tax_pct 3.0      round_trip_tax_pct 6.0
fee_can_be_changed   False    (transferFeeConfigAuthority is null: the rate is FIXED)
withdraw_withheld_authority  5KXDF6QnqhBj72hDtJNkkpFaQVUfbFXNybMsp3DiK6tD
withheld_tokens      359,171  (0.0372% of supply, about $2,978)
```

⛔ **There is no oracle anywhere.** A "pair" is the AMM pool's **quote asset**, so
the USD price is `pool ratio x quote asset USD`. ⛔ **And the reward stream is
REDISTRIBUTION, not yield**: it is funded by other traders' transfer tax, and the
same tax is charged on the way in and on the way out.

⛔ **`holder_has_been_paid` is always in `not_checked`, and no APR is published,
because none was measured.** Confirming a specific holder was paid needs that
wallet's own history. **The front end must not display a yield figure.**

---

### `concentration(mint)` ⭐⭐ sybil-adjusted, and the recurrence finding

Frank: *"nobody should ever be able to buy more than 1%-2% of a coin that early
on... Not sure how we could police that."* A per-wallet cap stops the lazy
version only, so this reports **effective** concentration with pool vaults
excluded and wallets sharing a funding source collapsed.

⛔⛔ **Running it produced a better answer than the one it was built for**, and
the front end should lead with that one. On real tokens the top holders are not
fresh sybil wallets; they carry 3,000+ signatures each, and **the same wallets
top-hold launch after launch**.

Live, on a recent pump.fun graduate:

```
raw_top1_pct                       17.54
raw_top10_pct                      64.03
wallets_over_2pct                  8
n_fresh_wallets                    0        <- none of them is a per-launch wallet
n_established_wallets              all
n_top10_seen_in_other_launches     8
top10_recurring_share_pct          80.0     <- against a measured median of 20%
recurring_holders[0]               also top-holds 9 other launches
```

⭐ **Base rate, measured over 60 consecutive graduations: 9.1% [6.8, 12.0] of
474 distinct top-10 wallets appear in more than one, and the median token has
20% of its top 10 recurring.** Three wallets top-hold 10 of the 60.

⚠️ **Every recurrence number is a FLOOR.** The registry sees only mints this
system has looked at, so a wallet shown in 10 launches appears in **at least**
10. It proves presence, never absence. Render it as `9+`, never `9`.

⛔ **Neither reading is a verdict.** A token full of recurring snipers is not
thereby safe, and one without them is not thereby honest. Full method,
including the two bugs found by running it, in `docs/CONCENTRATION.md`.

### `wallet(pubkey)` ⭐⭐ the headline feature

Read-only. Every token account across **both** SPL and Token-2022, each one run
through all-pairs liquidity, the phantom rule, a position-sized sell quote and
the pairing check.

Live, against a public address, **4.8 seconds**:

```
realizable $3,521.87
  USDT      Es9vMFrz...  30 pairs  reported $0        you get unknown
  BP        BPxxfRCX...  30 pairs  reported $0.14     you get unknown    paired: BP, WSK
  USDC      EPjFWdd5...  30 pairs  reported $0        you get unknown
  STONK     6GmAFSYs...  30 pairs  reported $0.68     you get unknown    paired: SPYx, VCF
  Fartcoin  9BB6NFEc...  30 pairs  reported $954.04   you get $958.80    paired: PYUSD
  SOL       So111111...  30 pairs  reported $2,278.58 you get $2,271.63  paired: USD1
  GP        HTmQz7My...  30 pairs  reported $292.97   you get $291.44    paired: GP, GLDx
```

Per position: `symbol` (display only), `pair_count`, `liq_all_pairs_usd`,
`liq_is_floor`, `shape`, `mcap_usd`, `phantom`, `paired_to`, `quote_assets`,
`transfer_fee_bps`, `fee_can_be_changed`, `mint_authority`, `freeze_authority`,
`reported_value_usd`, ⭐ **`you_get_usd`**, `sell_verdict`, `price_impact_pct`,
`reported_vs_realizable`, `symbol_flags`, plus its own `provenance` and
`not_checked`.

Top level: `sol_balance`, `n_token_accounts`, `realizable_total_usd`, and
`flags`, which is the four questions no tracker asks:

```json
"flags": {"no_market": [], "phantom": [], "cannot_sell": [],
          "taxed": [], "tax_can_be_raised": [], "ticker_collision": []}
```

⛔ **`realizable_total_usd` is a FLOOR over the positions that could be quoted.**
When any position has no quote, `realizable_total_usd_complete` appears in
`not_checked` with the count. **Never label it "portfolio value".**

⚠️ **Cost control, stated rather than hidden.** Each position costs one
all-pairs call, and each priced position costs a Jupiter quote on top, against a
process-wide cap of 55/min. Positions under **$1** of reported value are listed
but not quoted, each saying so in `not_checked`; `price_all=true` quotes
everything. Above `max_positions` (default 60) the extra mints are returned in
`unmeasured_mints` rather than dropped, because **a truncated sample must record
what it missed** (standing rule 15).

---

## 4. ⚠️ Deployment: the one thing not yet decided, and it is the site session's call

`intel.py` is Python. The site is a Vercel **Node** app. They cannot share a
process, so one of these has to happen and none of them is free of trade-offs:

| option | what it costs | honest assessment |
|---|---|---|
| **Vercel Python functions** (`api/*.py` in the site repo) | $0 on the current plan | ⭐ **Most likely right.** Same domain, no CORS, no extra host. ⚠️ Cold starts, and a 10s default execution limit that a big `wallet()` call with `price_all` could exceed. |
| **A small always-on VPS** running `intelserve.py` | **$4 to 6/mo**, already scoped for `programSubscribe` in `docs/TRACKER_SCOPING.md` §5c | ⭐ No time limit, warm cache, and the same box can host the real-time watcher. Needs a domain and TLS. |
| **Port the logic to Node** inside `site/api/` | no hosting cost, real duplication cost | ⛔ **Recommend against.** It would create a second implementation of the all-pairs and phantom rules, and this project already has four copies of `exit_depth_usd` and has been bitten by their divergence. |

⛔ **This session does not stage `site/` files**, so wiring is the site session's
work. `intelserve.py` runs today with `python intelserve.py 8799` and answers
every endpoint above.

## 5. What is deliberately absent

- ⛔ **No scoring, no ranking, no "expected return".** Marino: perfect knowledge
  of graduation probability still loses money, because by the time a signal is
  readable it is priced. Five ranking models have been built and retracted.
  **Nothing in this API orders tokens by quality**, and nothing should.
- ⛔ **No APR or yield figure**, for the reason in `paired()`.
- ⛔ **No hit rate on any ticker-only source.** See `docs/GORILLA_ARCHIVE.md` §4b.
- ⛔ **No buy or sell recommendation anywhere.** The system shows him what he
  would otherwise miss and stops a class of loss. He makes the call.

## 6. ⛔⛔ The product is facts, not a score

Frank: *"We need to seriously improve our scoring system before we can sell
it."* ⭐ **The answer is to retire it as a product rather than improve it.** The
reason is Marino and it has not moved: perfect knowledge of graduation
probability still loses money, because by the time a signal is readable it is
priced. Five ranking models have been built and retracted here.

**What is sellable is the set of things that are checkable and that nobody
publishes**, and every endpoint above returns one of them:

| fact | endpoint |
|---|---|
| liquidity real or phantom | `liquidity`, `phantom` |
| exit depth at a stated size | `exit_depth` |
| mint and freeze authority live or revoked | `safety`, `wallet` |
| which of several same-ticker mints this is | `resolve` |
| taxed, and can the tax be raised after you buy | `paired` |
| who holds it, and how many other launches those wallets top-hold | `concentration` |

**None of these needs a hit rate to defend, because none of them predicts
anything.** ⛔ **No endpoint returns a score, grade, rank or expected return, and
`test_intel.py` fails at the AST level if a field name ever contains one.** Any
internal score stays internal and never reaches a response.

## 7. ⛔ No model call on the hot path

Every number in every response is arithmetic over RPC and index reads. The
wallet checker costs RPC plus index calls and nothing else. **If an endpoint
ever needs a model call to return a number, that is a design error.**
`test_intel.py` also fails if a model client is imported into `intel.py`. A
narrative layer may sit on top, cached per contract, but never between a
question and its number.

---

## 9. ⭐⭐ `pair_legs(mint)` — both legs of every pair

**Added 2026-09-23. This is the novel one.** Frank: *"our detector should run on
BOTH legs of every pair... That would be a genuinely novel check."*

A memecoin can have its own mint and freeze authorities cleanly revoked and still
sit in a pool whose **quote asset** the issuer controls completely. Nobody checks
the other leg.

`GET /pair_legs?mint=<CA>` reads the quote leg of **every** pair for the mint and
reports, per leg, in plain sentences:

| field | what it means |
|---|---|
| `freeze_authority` | live, or null for revoked |
| `permanentDelegate` | the issuer can MOVE your tokens with no signature from you. ⚠️ **EXPECTED on a regulated tokenised security** |
| `pausableConfig` | the issuer can halt every transfer |
| `defaultAccountState` | ⚠️ **reported verbatim.** `initialized` is NOT `frozen` |
| `transferHook` | every transfer runs issuer code that can reject it |
| `transfer_fee_bps` | your entry cost and your exit cost, both |

**Observed live against STONK** (`6GmAFSYs4gk3FDao5FzzySQpPZaWsa4rUJHacpMpUNgx`),
over HTTP, 2026-09-23:

```
DISCLOSURE       : ISSUER RETAINS CONTROL OF A QUOTE LEG
powers disclosed : ['SPYx']
taxed legs       : {'VCF': 800, 'Circuit': 400}
pairs / floor    : 30 / True   legs read: 9
WARN: DISCLOSURE, not a warning about safety: this token is quoted in SPYx,
      whose issuer can freeze an account and move a holder's balance without
      the holder's signature. For a regulated tokenised security that is
      REQUIRED, and a tokenised equity lacking it would be the unusual one.
WARN: The cost that IS yours: VCF 800 bps, Circuit 400 bps. A transfer tax on
      the quote asset is charged on the way in and again on the way out.
```

### ⛔⛔ CORRECTED 2026-09-23: this is a DISCLOSURE, not a danger verdict

The first version published **"ISSUER CONTROLLED LEG"** as a verdict, which reads
as a red flag. **Frank pushed back and was right:** *"rwa stonk pairs seem to be
safe. I understand they have alarming readings but I think you need to research
more into those. There may be a reason nobody checks the other leg."*

⭐ **The reason is that the answer is expected.** A freeze authority and a
permanentDelegate are what a regulated tokenised security is **required** to
carry, so the issuer can comply with court orders, sanctions and securities law.
A tokenised equity **without** them would be the anomaly. Shipping that as a
warning would have cost us credibility with anyone who knows this space.

⭐ **What stays a genuine, quantified cost is the TRANSFER TAX**, and it is now
reported as its own field: VCF **800 bps**, Circuit **400**, and ZCAT, RAYCAT,
PURR-sol, LOOP, KNOTS at **300**. Charged on the way in and again on the way out,
so it is a round-trip cost and not a yield.

⛔ **Still not checked, and labelled:** no issuer's terms have been read, so which
holders may actually redeem, and under what restrictions, is unknown.

⚠️ **Frank's own STONK position is the worked example**, which is why this
endpoint exists rather than a note in a doc.

### What it refuses to say

- ⛔ **`authority_ever_used` is explicitly NOT CHECKED**, on every response.
  Presence of an authority is **capability, not an event**; proving use needs the
  authority's own signature history.
- ⚠️ **The quote-leg set is a FLOOR** whenever `pair_count == 30`, because that
  is Dexscreener's hard cap for any mint and the 30 are not the biggest 30
  (standing rule 18). `quote_legs_is_floor` says so.
- ⛔ A quote symbol with **no mint address** is listed in `not_checked`, never
  guessed at. Six different mints answer to COPX.
- ⛔ A leg that could not be read is `ok: false` with a reason. ⭐ If the
  published registry holds it, the answer comes from there **labelled
  `from_registry` with its read time**, counted separately in
  `legs_from_registry`, so one RPC blip cannot launder an issuer-controlled leg
  into an unknown one.

### The registry behind it

`legs.py` publishes `data/legs/quote_assets.json` from the **market stage**: one
RPC per quote mint, refreshed daily, capped per pass. The set of quote assets is
small and slow-moving while the set of tokens quoted in them is large, so this is
the cheap half.

**Measured 2026-09-23: 32 quote assets, 32 read ok, 2 issuer-controlled (COPX,
SPYx), 7 freezable, 7 taxed.** The taxed ones are the ones that pay "yield":
LOOP, KNOTS, PURR-sol and RAYCAT at 300 bps, Circuit at 400, VCF at 800.

⚠️ **The registry is forward-only and incomplete by construction.** Its input is
`quote_mints` on outcome rows, which landed on 2026-09-23, so no history carries
it. The file states this in its own `not_checked` block.
