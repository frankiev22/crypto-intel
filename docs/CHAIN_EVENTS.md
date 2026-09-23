# Live chain events: the Helius receiver, what each event triggers, and what it costs

2026-09-23. Frank: *"Wire up the helius receiver. That's definitely useful for
both of these projects."*

It is wired up and **real rows landed**. Four separate silent failures were found
on the way, and the cost arithmetic came out badly enough that it changes the
recommended architecture. Both of those are the substance of this file.

---

## 1. What exists, verified

| | |
|---|---|
| receiver URL | `https://rxofejxostyqlgjlzqmk.supabase.co/functions/v1/helius-events` |
| source | `supabase/functions/helius-events/index.ts` |
| webhook ID | **`d8765cda-6cc4-443e-870b-a004df20af3e`** (pool lane, ours) |
| webhook ID | `75056f75-c129-4f43-b686-0f369f8fa669` (the old wallet lane, **untouched**) |
| tables | `public.chain_events`, `public.chain_watch` (`supabase/migrations/003_chain_events.sql`) |
| control | `heliushook.py` (`list` / `register` / `sync` / `rows`) |
| first real row | ⭐ **2026-09-23 03:53:13Z**, block time 03:53:09Z |

⭐ **Why it lives on Supabase and not on Frank's desktop.** His machine is on
most of the time but not always, and the desktop collector has already died
silently for four days when a reboot lost its drive mount. A receiver that only
works while a laptop is awake is not a receiver.

⛔ **It is a second receiver, not a replacement.** `site/api/helius.mjs` on
Vercel loops `WATCHED_WALLETS` and calls `isActor(tx, wallet)`, so with an empty
wallet list it **drops every event it is given**. Pointing pool addresses at it
would have delivered events and discarded all of them. The wallet lane is left
exactly as it was.

### The evidence, because a 200 from a registration call is not evidence

```
03:46:58Z  webhook created, 18 pool addresses, transactionTypes ANY
03:53:08Z  first row written
03:54:36Z  455 rows, 455 distinct signatures, span 87.9s
04:06:40Z  1,571 rows
```

A sample row, as stored:

```
id 10   received_at 03:53:16.606Z   block_time 03:53:13Z
tx_type SWAP   source OKX_DEX_ROUTER   classification SWAP
watched [HMzvsEEmtzHhvZNw9uwbaG85HCTmFnkbhzUx16cy7ca3]
```

Auth was tested in both directions before anything was trusted:

| request | answer |
|---|---|
| POST, no Authorization | **401** |
| POST, wrong secret | **401** |
| POST, `Bearer <secret>` (Helius sends the value bare) | **401** |
| POST, exact secret, real Helius-enhanced payload | **200, stored** |

---

## 2. What each event triggers

⛔ **Nothing triggers a trade, an order or a wallet write. There is no such code
path and there never will be.** Every classification below is a *description* of
something that already happened, which is the one exception Marino allows.

| classification | how it is decided | what it means for Frank |
|---|---|---|
| **`LIQUIDITY_REMOVE`** | Helius type in `WITHDRAW / WITHDRAW_LIQUIDITY / REMOVE_LIQUIDITY / BURN / CLOSE_POSITION`, **or** a native transfer of >= 50 SOL out of a watched address whatever the label | ⭐ **The one that matters.** Three of our confirmed deaths were a single `Withdraw` as the last event on the pool: USDCAT 09-21 19:54:19Z, OWL 09-22 07:14:06Z, X7 09-22 10:27:06Z. The decoy EMBER's was 11:09:37Z and our 24h check ran 11:12:10Z, 2m33s too late |
| **`POOL_CREATE`** | type in `CREATE_POOL / INIT_POOL / TOKEN_MINT / CREATE` | a new venue for a token we already track, or a first pool. The launch-side signal |
| **`LIQUIDITY_ADD`** | type in `ADD_LIQUIDITY / DEPOSIT / OPEN_POSITION` | depth arriving. Matters because exit depth is the number every headline is gated on |
| **`LARGE_TRANSFER`** | any native transfer >= 50 SOL | a whale moving, not necessarily through our pool |
| **`SWAP`** | type in `SWAP / SWAP_EXACT_OUT` | volume. Stored, but it is context, not an event |
| **`OTHER`** | everything else | ⭐ **Honest.** It means we saw it and did not recognise it. It never means nothing happened, and the raw payload is kept so the classifier can be improved against real traffic rather than guesses |

⛔ **The Helius type is deliberately not trusted on its own.** A large native
transfer out of a watched pool is graded `LIQUIDITY_REMOVE` regardless of what
Helius called it. Missing a drain because it was mislabelled is the expensive
error; a false `LIQUIDITY_REMOVE` is cheap and visible.

⭐ **And that caution was worth testing rather than assuming. Measured on our
three known drains: Helius typed all three `WITHDRAW`.** 3 of 3, on PumpSwap
pools. ⚠️ **But TSLA is dead too and its pool shows no `WITHDRAW` at all** in a
100-transaction window (SWAP 14, UNKNOWN 43, TRANSFER 43), and UOTF's pool is
delisted entirely. So the typed-`WITHDRAW` path catches **3 of 5** confirmed
deaths, n=5, far below the n=30 bar. **That is an observation and not a rate.**

⛔ **Nothing is alerted on yet.** Rows land and are queryable. Wiring
`LIQUIDITY_REMOVE` to Discord is the next step and is deliberately separate,
because an alert that fires on an unverified event is exactly what standing
rule 4 forbids.

---

## 3. ⛔ The cost arithmetic, and it does not fit the free tier

Helius bills **per delivered webhook event**. The free tier is **1,000,000
credits a month**. Everything below is measured on our own traffic, not quoted.

### Measured delivery rate

| watchlist | delivered | rate | per month |
|---|---|---|---|
| 18 pool addresses, 9 tokens | 824 events / 148.5s | **5.55/sec** | ⛔ **14,574,000** |
| after removing JEANPHIL and CATE (14 addresses) | 36 events / 60s | **0.60/sec** | ⛔ **~1,600,000** |

⭐ **Liquidity does not predict event volume, and the relationship is inverted.**
Per-address counts over the same 88 seconds:

| pool | liquidity | events | per month |
|---|---:|---:|---:|
| JEANPHIL pumpswap | $323,460 | **389** | 10,219,641 |
| JEANPHIL meteora | $374,960 | **381** | 10,009,468 |
| CATE pumpswap | $3,505,090 | 70 | 1,839,010 |
| CATE meteora | $1,072,425 | 60 | 1,576,294 |
| STONK meteora | $2,773,960 | 20 | 525,431 |
| KNOTS meteora | $298,790 | 7 | 183,901 |
| ZCAT meteora | $1,077,366 | 7 | 183,901 |
| PURR meteora | $250,506 | 6 | 157,629 |
| EMBER meteora | $742,386 | 4 | 105,086 |
| PURR raydium | $528,956 | 4 | 105,086 |
| ZCAT raydium | $1,656,402 | 2 | 52,543 |
| KNOTS raydium | $1,068,572 | 1 | 26,272 |
| HYPE orca | $3,070,457 | 1 | 26,272 |
| **STONK raydium** | **$5,136,541** | **1** | 26,272 |
| HYPE meteora, LOOP x2, EMBER #2 | | **0** | 0 |

**STONK at $5.1M fires once. JEANPHIL at $323k fires 389 times.** A 389x spread
in the opposite direction to depth. ⭐ **So a watchlist can never be sized by
liquidity; it has to be sized by measured event rate**, and the rate has to be
measured before the addresses are registered, not after.

⚠️ **SOL's two deepest pools were excluded before anything was registered**, on
the reasoning that SOL is the one token in the set with no rug risk and
`58oQChx4...` is among the busiest accounts on Solana. That judgement was not
measured and the pools are kept as inactive rows if it ever needs testing.

### ⛔ And type filtering does not rescue it

The obvious lever is `transactionTypes`: ask Helius for liquidity events only and
skip the swaps. **Measured on 1,571 delivered rows, it saves almost nothing:**

| Helius type | share | our classification |
|---|---:|---|
| `UNKNOWN` | **47.82%** | OTHER |
| `TRANSFER` | **41.38%** | OTHER |
| `SWAP` | 9.65% | SWAP |
| `CLOSE_ACCOUNT` | 0.49% | OTHER |
| `INITIALIZE_ACCOUNT` | 0.24% | OTHER |
| `INITIALIZE_BIN_ARRAY` | 0.24% | OTHER |
| `INITIALIZE_POSITION` | 0.12% | OTHER |
| `SWAP_EXACT_OUT` | 0.06% | SWAP |

⛔ **Excluding `SWAP` removes 9.7% of the bill.** And filtering down to the
liquidity types would drop `UNKNOWN` and `TRANSFER`, which is **89.2% of
everything we actually receive** and is where a Meteora liquidity operation
lands: Helius types PumpSwap `Withdraw` correctly and leaves Meteora DLMM
positions as `UNKNOWN` and `INITIALIZE_BIN_ARRAY`. **Filtering by type would buy
affordability by throwing away the bucket the drain hides in.**

### ⭐ The budget is now enforced in code, and it refused a token I wanted

`heliushook.register()` **probes every address from the chain and refuses the
whole call** before anything is registered. The thresholds are a derivation, not
a discovery: the free tier is 1M credits a month, the same key serves RPC for
`chainfields` and `graduations`, so the webhook lane gets 600,000 of it, which is

    600000 / (30.4 * 86400) = 0.228 delivered events per second

for the whole watchlist, with any single address capped at **0.05/sec**
(131,000 a month) so no one pool can eat the budget alone.

On-chain transaction rate for all twenty pools, measured over a 600-second
window per address:

| pool | rate /sec | per month | verdict |
|---|---:|---:|---|
| JEANPHIL meteora | **38.2459** | 100,455,258 | ⛔ refused |
| SOL raydium | **35.8280** | 94,104,492 | ⛔ refused |
| CATE pumpswap | **34.0326** | 89,388,781 | ⛔ refused |
| JEANPHIL pumpswap | **33.6295** | 88,329,837 | ⛔ refused |
| CATE meteora | 27.9342 | 73,370,763 | ⛔ refused |
| SOL orca | 18.8252 | 49,445,435 | ⛔ refused |
| PURR raydium | 11.9095 | 31,281,144 | ⛔ refused |
| STONK meteora | 6.1498 | 16,152,757 | ⛔ refused |
| PURR meteora | 2.3164 | 6,084,283 | ⛔ refused |
| HYPE meteora | 1.2501 | 3,283,421 | ⛔ refused |
| STONK raydium | 0.5036 | 1,322,785 | ⛔ refused |
| ZCAT meteora | 0.3598 | 944,964 | ⛔ refused |
| KNOTS meteora | 0.1963 | 515,581 | ⛔ refused |
| HYPE orca | 0.1665 | 437,377 | ⛔ refused |
| EMBER meteora #2 | 0.1113 | 292,261 | ⛔ refused |
| ⚠️ **EMBER meteora #1** | **0.0543** | 142,618 | ⛔ **refused, by 0.0043** |
| KNOTS raydium | 0.0388 | 101,850 | ✅ allowed |
| ZCAT raydium | 0.0307 | 80,649 | ✅ allowed |
| LOOP meteora | 0.0184 | 48,377 | ✅ allowed |
| LOOP raydium | 0.0044 | 11,509 | ✅ allowed |

**Four of twenty.** Their total is **0.0923/sec = 242,431 credits a month**,
inside the 600,000 budget with room to spare.

⛔⛔ **It refused EMBER, which is the token I most wanted covered, by 0.0043
events per second.** The cap stayed where it was pre-committed. Moving a
threshold after the data arrives, so that a favourite gets in, is exactly the
score-band mistake this repo deleted a whole feature over. ⭐ **The way to cover
EMBER is the reserve poller below, not a wider gate.**

⚠️ **The probe measures the ON-CHAIN transaction rate, which is an upper bound
on delivered webhook events, and the ratio between them is NOT established.**
Comparing the probe against the live 88-second delivery window gives ratios from
**1.4x** (EMBER meteora #1) to **297x** (PURR raydium), on single-digit counts
per pool. That is rule 13 territory: one 88-second window cannot calibrate a
per-pool ratio. **So the guard is conservative by an unknown factor**, which is
the correct direction for a guard and the wrong number to quote as a cost.

⭐ **An address whose rate cannot be established is refused too.** Unknown is
not zero. `test_heliushook.py` (24/24, offline, both the probe and the HTTP call
injected) fails if any of that stops being true.

### ⛔⛔ And the STORAGE budget binds harder than the credit budget

This is the finding I should have reached before registering anything, and it is
worse than the credit arithmetic.

**The free-tier Supabase database is 500 MB TOTAL**, shared with everything else
already in the project. Computed from our own delivered rows:

| watchlist | rows/day | full raw ~2 KB | metadata only ~300 B |
|---|---:|---:|---:|
| 18 addresses, 5.55/sec | **479,520** | ⛔ **982 MB per DAY** | 144 MB/day |
| 4 addresses, 0.09/sec | 7,974 | ⛔ **496 MB/month** | 73 MB/month |

⛔ **At the set I actually registered, `chain_events` would have consumed the
entire database in under twelve hours.** It ran for thirteen minutes and wrote
1,571 rows. And even the four addresses the credit budget allows would fill the
database inside a month at full payload.

⭐ **So the fix is not a smaller watchlist, it is to stop storing what we do not
need.** From v6 the receiver keeps the full payload only for the four
classifications that are actual EVENTS - `POOL_CREATE`, `LIQUIDITY_ADD`,
`LIQUIDITY_REMOVE`, `LARGE_TRANSFER` - which are rare. `SWAP` and `OTHER` rows
are still written with every field that is small (signature, slot, block time,
type, source, Helius's own description sentence, fee payer, the watched
addresses, our classification), because the denominator matters and **`OTHER` is
89% of delivered traffic and is where a Meteora liquidity operation hides.** Their
payload and transfer arrays are kept for a bounded **20 per hour** sample, so the
classifier can still be improved against real traffic.

⛔ **An omitted payload is never a null that could read as "there was
nothing".** It is an explicit marker object carrying `omitted: true`, the reason,
the classification and the sample size. Standing rule 5, and standing rule 15:
the sample is bounded and says so.

⚠️ **The row-size figures are estimates, not measurements.** 2 KB and 300 B are
assumptions; the actual average was never measured because the database went down
before it could be. **Re-measure with `pg_total_relation_size` before quoting any
of this as a capacity figure.**

### ⭐ What the numbers actually recommend

**Polling reserves, not subscribing to events**, for the bulk of the watchlist:

- One `getMultipleAccounts` call returns up to 100 pool vault accounts and costs
  **one RPC credit**. At a 30-second cadence that is **2,880 calls a day =
  87,600 a month**, comfortably inside the free 1M, and it scales to ~150 pools
  in a single call.
- It measures **the thing we care about** (quote-side reserves falling to zero)
  rather than a transaction type we have documented reason not to trust.
- ⚠️ Its worst-case latency is the poll interval, so it is 30 seconds behind
  where the webhook is 2 to 4 seconds behind. **For a drain, 30 seconds is
  already far better than the 2m33s that beat us on the decoy EMBER.**

So the webhook keeps the two jobs polling cannot do, on a small address list:
**pool creation** (a new pool has no earlier reserves to compare against) and
**low-latency confirmation** on a handful of positions Frank actually holds.

⛔ **Paying is the alternative and it is Frank's call alone** (standing rule 9).
Helius Developer is $49/mo for 10M credits, which at the measured 0.6/sec covers
roughly 90 pools. That is the same conclusion `docs/TRACKER_SCOPING.md` §5c
already reached from the WebSocket side (~$53-55/month all in), arrived at
independently from the webhook side. **Nothing has been signed up for.**

---

## 4. ⛔ TEN silent failures, all found by probing output rather than execution

⚠️ **Was six. Four more were found on 2026-09-23 afternoon, three of them by a
load test and one by reading a number that turned out to mean something else.**
Sections 4.7 to 4.10 below.

This is standing rule 16 earning its place ten times in one session. Every one
of these would have left a receiver that looked healthy and stored nothing.

**1. `service_role` had no grant on either table.** The tables were created
without one, so the edge function's REST calls came back `401 permission denied`
for both the watchlist read and the insert. The liveness probe said
`watching: 0`, which is what caught it. ⚠️ **`watching: 0` is the
`authority_live=None` shape again**: an empty watchlist is indistinguishable from
"we deliberately watch nothing". `watchlist()` now returns **null** on failure,
the probe reports `watchlist_read: "FAILED"`, and a row whose watchlist could not
be read carries `watched = null` rather than `[]`.

**2. The receiver answered Helius with HTTP 200 while the insert was failing.**
That was a deliberate choice for the wrong reason: a 500 makes Helius retry
forever on a malformed payload. But a **privilege** error is our bug and is
fixable, so a 200 there means Helius marks delivery successful and the event is
gone. Now `401 / 403 / 5xx` from PostgREST returns **500** so Helius retries and
its own error counter rises; only `400 / 409 / 422` returns 200.

**3. The insert asked for `resolution=merge-duplicates`.** That is an UPSERT, so
PostgREST demanded `GRANT UPDATE ON public.chain_events` - on a table that is
append-only by standing rule 8. ⭐ **The fix was the weaker verb, not the wider
grant:** `resolution=ignore-duplicates` needs INSERT only, and a repeated
signature is dropped rather than allowed to overwrite what we already recorded.

**4. ⛔⛔ The watchlist was read on EVERY inbound event, and it took out the
shared REST API.** At the measured 5.5 events/sec that is 11 PostgREST requests a
second on a free-tier project, and each 500 from failure 2 made Helius retry and
multiplied it. **PostgREST stopped answering for every table in the project,
including pre-existing ones** - `/rest/v1/` still returned 401 in 0.29s because
that path never touches the database, while any table query hung past 110
seconds. `pg_stat_activity` showed nine idle connections and no lock on the
table, so the database itself was never the problem. The watchlist is now cached
in the instance for 60 seconds, and a failed refresh returns null rather than
serving a stale list that looks healthy.

⚠️ **That fourth one is on me and it had blast radius beyond this feature.** The
site and `supa.py` share that REST API. **The lesson is not "cache the
watchlist"** - it is that a component whose per-event cost scales with an
unmeasured event rate must have that rate measured **before** it is pointed at
production, which is standing rule 13 wearing different clothes.

---


### ⛔⛔ 5. The deploy turned the gateway back on, and the deploy returned 200

**2026-09-23 06:10Z.** Redeploying the receiver flipped `verify_jwt` back to
**true**, because a Supabase function deploy takes that flag and **defaults it to
true when it is not passed**. The Supabase **gateway** then answered every
request with `UNAUTHORIZED_NO_AUTH_HEADER` in **0.33s, before a single line of
our code ran** - and it would have rejected Helius in exactly the same way.

⛔ **The deploy itself returned a healthy 200 with a new version number.** The
source was correct, the function was `ACTIVE`, and the receiver was unreachable.
There is no reading of the code or of the deploy response that catches this: the
only thing that catches it is an unauthenticated GET to the real URL.

⭐ **Caught within one minute by probing the live URL**, redeployed with
`verify_jwt: false` as v8, and confirmed reachable (`GET 200`). The receiver
authenticates with the SHA-256 of the shared secret, not a Supabase JWT, so that
flag must always be passed explicitly.

⭐ **The guard is now a command:** `python heliushook.py health` does the
unauthenticated GET, reports `gateway_blocking` separately from whether the
database is answering, and **exits 1** when the gateway is in front of us. It
reports `gateway_blocking: null` rather than `false` when the request failed for
some other reason - a network error is not evidence that the gateway is fine.

### ⚠️ 6. The probe had no timeout, so it could not report the outage

When the database stopped answering at ~04:06Z the GET probe **hung** for the
caller's entire timeout instead of saying what was wrong. A diagnostic that
cannot answer while the thing it diagnoses is broken has failed in exactly the
case it was built for.

Every probe read is now bounded at **6s** (`PROBE_TIMEOUT_MS`), and so is the
watchlist read, which sits on the **event** path rather than a diagnostic one.
⭐ **Verified under the real failure**, with the database still down:

```
GET 200 in 30.45s
  rows_total              'unknown'        <- not 0
  watching                None             <- not 0
  watchlist_read          'FAILED'
  read_error              'read failed: TimeoutError: Signal timed out.'
  raw_omitted_rows        None             <- not 0
  storage_budget_working  'unknown - count unreadable'
  newest_rows             None             <- not []
```

Every unknown renders as unknown (standing rule 5), under the exact condition
that produces them. ⚠️ The 30s is five bounded reads in sequence and only
happens while the database is down; a healthy probe returns promptly.

### ⭐ And the storage assertion is now answered by the probe, not by a person

`raw_omitted_rows` and `raw_full_rows` are counted on every probe, so the
question "is the storage budget actually dropping payloads" no longer needs a
hand-run SQL query - which, being manual, was not an answer at all (standing
rule 11). `storage_budget_working` says `NOT OBSERVED YET` when the counts read
zero and `unknown - count unreadable` when they cannot be read, never a bare
"no".

⛔ **Still not answered: bytes per row.** It needs `pg_total_relation_size`,
which PostgREST cannot reach without an RPC, so it stays **ESTIMATED at 2 KB and
labelled as such** in the probe's own output. Every capacity figure in §3 rests
on it. BACKLOG C36.

### ⛔⛔ And my attribution for the outage is NOW CORRECTED, 2026-09-23 12:10Z

**I said the receiver's own load took the database out and that it would come
back once the load stopped. The first half is still the best explanation for the
*start*. The second half is wrong, and I am leading with it.**

The load stopped at **~04:06Z**, when both webhooks went to **0 addresses** -
verified again at 12:09Z, `accountAddresses: "0 addresses"` on
`75056f75-c129-4f43-b686-0f369f8fa669` and on
`d8765cda-6cc4-443e-870b-a004df20af3e`. **So for eight hours nothing at all has
been inserting**, and the database still refuses connections.

Measured at 12:08-12:10Z, three independent paths, all timing out on a Postgres
connection while everything that needs no connection answers instantly:

| path | result |
|---|---|
| PostgREST `/rest/v1/chain_events` | no answer (watcher, every 5.5 min since 04:06Z) |
| management API `execute_sql` | `Connection terminated due to connection timeout` |
| management API `get_advisors` | `Failed to run project user check: connection timeout` |
| management API `get_project` | **200 instantly**, `status: ACTIVE_HEALTHY` |
| `/rest/v1/` root (never touches the DB) | 401 in 0.29s, as designed |
| log tables (`postgres_logs`, `edge_logs`) | `Table does not exist` - not reachable either |

⭐ **AND AT 13:05Z IT GOT MORE SPECIFIC, which narrows it further.** PostgREST
stopped timing out and started answering **`503 PGRST002: Could not query the
database for the schema cache. Retrying.`** That is PostgREST **up and healthy**,
looping on a Postgres that will not answer it. **So the API layer has recovered
and the database itself has not**, which rules out the gateway and leaves the
Postgres instance.

⭐ **What that rules out.** It is not Helius retrying into a failing receiver,
because there is no inbound traffic to retry. It is not the receiver holding
connections, because the receiver is not being called. **A self-inflicted
overload that ends when the load ends does not last eight hours after it.**

⚠️ **What it leaves**, and neither is confirmed: connections leaked
server-side that only a project restart clears, or a platform fault in us-west-2
that `ACTIVE_HEALTHY` does not reflect. ⛔ **`ACTIVE_HEALTHY` is itself an
`authority_live=None` shape** - it reports the control plane's view, not whether
the database answers, so it may never be quoted as evidence that the database is
up.

⛔ **What I deliberately have NOT done, and why it is Frank's call.** The
remedy for both remaining causes is a restart, and the management API exposes no
restart - only **pause** and **restore**. Pausing a free-tier project is not
instant to undo, the project holds pre-existing tables that have nothing to do
with this work, and turning an eight-hour outage into a multi-hour restore
unattended is not a call I should make. **The dashboard's own Restart button is
the right tool and it is his to press.**

⭐ **And the reconciler already behaves correctly through all of it.**
`heliushook.ensure()` returns `acted: "hold"` with the reason spelled out, beats
`chainevents.rows` with `n=0`, and refuses to register addresses into a database
that cannot accept inserts - because registering them is what would restart the
retry storm.

### ⛔⛔ 7. `resolution=ignore-duplicates` DID NOT IGNORE DUPLICATES

Found 2026-09-23 ~14:50Z by replaying **248 real batches** of already-stored
signatures at the live receiver. The committed comment said, in so many words,
that a Helius retry was a no-op because of the unique constraint plus
`Prefer: resolution=ignore-duplicates`.

⛔ **Every one of the 248 came back `409 duplicate key value violates unique
constraint "chain_events_sig_uniq"`**, and every one was written to the log as
`chain_events_drop`.

**Why:** PostgREST emits `ON CONFLICT` against the table's **primary key**
(`id`). The conflict here is a *separate* unique index over `signature`, so the
clause never applied and the violation was raised normally. The fix is to name
the target: `POST /rest/v1/chain_events?on_conflict=signature`.

⛔ **And the consequence was live data loss, not cosmetics.** A POST of an array
is ONE statement, so a single already-stored signature failed the whole batch and
took **every genuinely new event in it** down with it. Helius batches, so this was
reachable in normal operation on any redelivery that overlapped new traffic.

⭐ **Verified fixed on the deployed function** with the same three signatures that
had produced 409s: `{"ok": true, "submitted": 3, "stored": 0, "already_stored":
3}`, and `rows_total` unchanged.

### ⛔ 8. `stored` was the number of rows SENT, not the number written

Straight out of the fix above: once duplicates were being ignored, the success
path still answered `stored: rows.length`. A replay that wrote **nothing** said
`stored: 3`.

⭐ The count now comes from PostgREST's own `Content-Range` (`count=exact`), the
response carries `submitted` and `already_stored` separately, and ⚠️ **an
unparseable header gives `stored: null` with `stored_unknown_why`, never 0 and
never `rows.length`** (standing rule 5).

### ⛔⛔ 9. `chain_watch_sync` could only ever ACTIVATE, so the mirror drifted up

Measured 2026-09-23 14:45Z: **the Supabase mirror held 20 active addresses while
git held 6 and the Helius webhook delivered 6.** The receiver's self-check
reported `watching: 20`, which reads as a fact about the system and was not one.

**Why:** the `chain_watch_sync` RPC ignored the payload's `active` field entirely
and hard-coded `active = true` in its `ON CONFLICT` branch. So every address any
pass had ever registered stayed active forever, and a caller asking it to
deactivate an address **silently re-activated it instead** - which is exactly what
my first attempt at the fix did.

⭐ **Fixed in the RPC** (migration `chain_watch_sync_honours_active`): it now
honours `active`, defaulting to true so every existing caller behaves as before.
⛔ Rows are **deactivated, never deleted** (standing rule 8): the table now reads
6 active / 20 inactive, and the inactive rows remain as a record that we once
watched them.

⭐ **And `heliushook.health()` now compares all three lists every time it runs** -
git, Helius's `accountAddresses` (the only one that decides delivery), and the
mirror - with the addresses in each difference named. ⚠️ `agree` is **None**, not
False, when any list could not be read. Verified: `git 6, helius_delivering 6,
mirror_active 6, agree true`.

⚠️ **This also changes what is possible on this project: DDL now runs**, through
the Supabase MCP `apply_migration`. `CLAUDE.md` says "nothing on disk can run
DDL" and that is still true of the disk, but it is no longer true of this session.
BACKLOG A41 was blocked on exactly that.

### ⚠️ 10. And the receiver had never been EXECUTED by a test, once

There is no Deno on this disk, so until 2026-09-23 no test in this repo could run
a single line of the receiver. Every fix to it, including all of the above, was
verified by reading source or by trusting a deploy's 200.

⭐ The load rule now lives in `supabase/functions/helius-events/backpressure.ts`,
which is deliberately **pure** - no Deno, no `fetch`, no module globals - so
node's type stripping imports and runs it unchanged. `test_backpressure.mjs`
(44 assertions) drives the real module, and `test_backpressure.py` runs that
harness and adds the invariants that can only be checked against `index.ts`.
⚠️ **A missing node is a FAILURE in that suite, not a skip.**

## 4a. ⭐⭐ THE BACKPRESSURE FIX, and the burst that tested it

Frank, 2026-09-23: *"That is a burst problem, not a capacity problem. Fix it with
connection pooling and backpressure on our side, not a bigger plan."*

⛔⛔ **The amplifier was in our own code and it was one line.** The old insert
path computed `ourFault = status === 401 || status === 403 || status >= 500` and
answered **500** when true, with a comment explaining that this way "the event is
not lost". **Helius retries a non-2xx.** So the receiver's response to "the
database cannot take this write" was to ask for the same write again, and the
retries multiplied the load that was already the problem.

⭐ **The rule now, and it is stated in `backpressure.ts` before any of it was
measured:** a 5xx from this receiver is a request for MORE load at the exact
moment the database cannot take what it already has, so **the receiver may never
answer 5xx because a write failed.** It absorbs the failure, records the drop
where a human and a liveness check can see it, and returns 200 so Helius stops.

| failure | can retrying help | what happens |
|---|---|---|
| `congestion` (408, 429, 5xx, thrown fetch) | maybe, later | ONE in-process retry after **250-750ms jittered**, then drop + log, 200 |
| `privilege` (401, 403) | **never** | no retry, drop + log, 200, and the response says EVERY event is being lost until a human fixes a grant |
| `payload` (400, 422) | never | no retry, drop + log, 200 |
| `duplicate` (409 / SQLSTATE 23505) | n/a - **nothing was lost** | `ok: true`, `already_stored`, **not counted as a drop** |

**The breaker:** 3 consecutive congestion failures opens it for 30s, during which
**no insert is attempted at all**. One success closes it. After a served cooldown
exactly one attempt goes through, and a further failure re-opens it immediately
rather than granting another three.

⚠️ **It is per-isolate and that is a damper, not a guarantee.** Supabase runs many
isolates and each starts with its own counter - the same trap the raw-payload
sampler fell into. Every isolate that sees congestion independently stops sending,
so aggregate load falls roughly in proportion to how widely the failure is seen.
The code says so in those words and the test asserts that it does.

⛔ **Every drop is logged as a searchable `chain_events_drop` line carrying the
count AND a signature**, because "some events were dropped" is not actionable.
Verified on the live function: a deliberately malformed row returned **HTTP 200**
with `kind: "payload"`, `dropped: 1`, and the marker was then read back out of
Supabase's own function logs.

### The burst, measured 2026-09-23 ~14:50Z

Replayed **248 batches of 10 real, already-stored signatures** at the live
receiver, ramping 5 -> 10 -> 16 POST/s, with the receiver's own GET polled every
2s as a control (it reads `chain_events` over PostgREST, so if PostgREST stops
answering for the project the control says so).

| measured | result |
|---|---|
| POSTs / row-attempts | 248 / 2,480 |
| receiver status codes | **200 on all 248** |
| achieved rate | **7.5 POST/s, 75 rows/s** |
| latency p50 / max | 0.66-1.06s / 10.9s |
| control reads OK | **11 / 11**, p50 1.67s, max 3.37s |
| breaker opened | never |
| rows created | **0** - `rows_total` 1897 -> 1899, and the +2 was live traffic |

⚠️ **LIMIT OF THIS TEST, stated plainly: it did NOT exceed the request rate that
caused the outage.** The ramp asked for 16 POST/s and achieved 7.5, because
latency and thread scheduling throttled it. The morning outage was ~11 PostgREST
requests/sec. So **"a burst cannot exhaust the pool" is NOT established.**

⭐ **What IS established, and it is the part that matters:** the request cost per
EVENT fell from **2 PostgREST requests** (a watchlist read plus an insert, on
every single event) to **0.1** (one insert per POST, and a POST carries ten rows),
a **20x reduction at this batch size**. And **75 events/sec - 13.5x the 5.55
events/sec that caused the outage - was absorbed with zero non-200s, zero drops
and no loss.**

⛔ **I stopped escalating deliberately.** Pushing past the outage rate on Frank's
only database, on a free tier, to find the breaking point is not a call worth
making when the receiver is live and the site's other endpoints share the project.

⚠️ **And the breaker itself is UNVERIFIED against a real congestion failure.**
Forcing one means making PostgREST return 5xx, which is the outage. Its logic is
executed and asserted in node (44 assertions), and the drop path is verified live
through a payload failure, but **"the breaker opens under real congestion" has not
been observed and is not claimed.**

## 5. What is not done

- ⛔ **No alert fires on anything.** `LIQUIDITY_REMOVE` reaching Discord or the
  site is the next step and needs a pre-committed threshold first.
- ⛔ **No page reads `chain_events`.** By the repo's own test, that means this is
  **IN PROGRESS, not SHIPPED** (`docs/BACKLOG.md` C25, and the SHIPPED-row audit).
- ⚠️ **The program IDs Frank asked for are not registered, and that is a measured
  refusal rather than an omission.** pump.fun alone measured **56
  notifications/sec** (`docs/TRACKER_SCOPING.md` §5c), which is ~145M events a
  month against a 1M free tier. Registering pump.fun, PumpSwap, Raydium v4 /
  CPMM / CLMM, Meteora DLMM / dynamic / DBC, Orca Whirlpools and Stonk Fun would
  exhaust the month's credits in well under an hour and take the RPC key down
  with it, which `chainfields` and `graduations` both depend on. ⭐ **The
  launchpad-coverage answer is not a program webhook anyway**: it is
  `lite-api.jup.ag/tokens/v2/recent`, keyless, 30 rows spanning a median 47
  seconds, which already covers every launchpad (BACKLOG A56).
- ⚠️ **Stonk Fun's program id is still unverified and was not found**
  (`docs/COVERAGE_PLAN.md`), so it could not have been registered even if the
  budget allowed it.
- ⚠️ **The type mix is measured over 1,571 rows on 14 Meteora-and-Raydium-heavy
  pools in one 13-minute window.** Bursty traffic, one window, rule 13: it is
  enough to kill the type-filtering idea and not enough to characterise a venue.
