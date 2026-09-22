# Social-graph watcher: scope, not a build

2026-09-22. Frank asked for this **scoped, explicitly not built.** What follows is
the request arithmetic, the cost, the latency floor, what is free, and the one
measurement that should happen before a cent is spent.

**The thing being scoped:** detect **following-list deltas** and **profile-picture
changes** on a curated set of high-signal accounts, because the claimed meta is
driven by those and not by tweets. Claimed examples, all **unverified by us**
(`docs/MARKET_META_2026-09.md` §6): pmarca follows musebook and MUSEBOOK reaches
26m; Zuckerberg changes his Facebook profile picture and AGRIPPA reaches 1.4m;
Zuckerberg follows a 224-follower account and AGRIPPA goes 200k to 5m while
MUSEBOOK goes 25m to 48m **within an hour**; Roaring Kitty logs in and posts and a
GME pair reaches 4m.

⭐ **The structural claim is correct and I will not soften it. Our pipeline reads
liquidity, mint authority, holder counts and now token names. There is no code path
that could ever see a follow or a profile picture.**

---

## 1. Our access today: none, and it is not a plan problem

Probed 2026-09-18 and again 2026-09-19 (`scratchpad/xprobe.py`, `xprobe2.py`, which
print status codes only):

- The app-only bearer minted from our consumer key returns **200** on
  `/2/usage/tweets`, so **the app is alive and the keys are valid.**
- ⛔ **Every data endpoint returns 402 `credits-depleted`**, full-archive search
  included. It is a **consumed credit balance, not a lapsed plan**: the 3,000,000
  per month POST cap is untouched at `project_usage 0`.
- So the read side costs money starting from the first call. **There is no free
  configuration of the X API today**, and a credit top-up is Frank's decision
  alone (`docs/DECISION_X_DATA.md`, BACKLOG C11).

Published tiers, for the record: free tier discontinued; **Basic $200/mo closed to
new signups**; Pro closed; **pay-per-use $0.005 per post read** with a 2,000,000
per month cap (about $10,000); Enterprise from roughly $42,000.

⚠️ **The binding unknown is a unit price, and I cannot resolve it.** $0.005 is the
published **post read** price. Whether a **user lookup** (`/2/users`) or a
**following list** page bills as one post read, as something cheaper, or as
something else entirely is **UNVERIFIED**, and verifying it needs one successful
call plus a usage-meter delta, which needs credits. Every dollar figure below is
therefore **conditional on that rate**, and I have labelled it rather than quietly
assuming it.

---

## 2. ⭐ The finding that decides the design: follows and pfps cost 100x differently

| what | endpoint | accounts per call |
|---|---|---|
| **profile picture** | `GET /2/users?ids=…&user.fields=profile_image_url` | ⭐ **100** |
| **following list** | `GET /2/users/:id/following` | ⛔ **1**, and paginated at 1,000 per page |

**A pfp sweep batches. A follow sweep cannot.** That single asymmetry is a factor
of 100 in cost, and it means the two halves of this watcher are in completely
different price brackets.

### Requests per month, N accounts at poll interval T

`calls = ceil(N/100) x 2,592,000/T` for pfps, `calls >= N x 2,592,000/T` for follows.

| configuration | calls/month | cost at $0.005 per call (**UNVERIFIED rate**) |
|---|---|---|
| **pfp**, 200 accounts, every 5 min | 17,280 | **$86** |
| **pfp**, 200 accounts, every 60s | 86,400 | $432 |
| ⭐ **pfp**, 20 accounts, hourly | **720** | ⭐ **$3.60** |
| **follows**, 200 accounts, every 5 min | **1,728,000** | ⛔ **$8,640**, and near the 2M cap |
| **follows**, 200 accounts, hourly | 144,000 | ⛔ $720 |
| **follows**, 20 accounts, every 5 min | 172,800 | ⛔ $864 |

⛔ **Follow monitoring at a useful interval costs more per month than Frank's entire
bankroll, by a wide margin.** The floor for follows is the account count times the
poll rate, and there is no batching to trade against it.

⭐ **Profile-picture monitoring on a small curated set is nearly free even at the
post-read rate, at roughly $4 a month.** That is the only configuration in this
table that is affordable, and it happens to cover two of the five claimed events.

---

## 3. How fast could it fire

**Detection latency has a hard floor equal to the poll interval**, plus X's own
propagation, plus our processing. A 5-minute poll means a median 2.5 minutes and a
worst case just over 5 minutes after the event.

⛔ **Standing rule 13 applies directly: never measure a phenomenon with a sampler
slower than the phenomenon.** The claimed AGRIPPA move ran 200k to 5m **within an
hour**, so an hourly poll is inside the event and useless for follows, while a
5-minute poll is comfortably inside it. ⭐ **Whatever interval is chosen has to be
stated next to every latency claim**, and a scoped design that does not state its
interval is not scoped.

⚠️ **And the false-positive problem is larger than the latency problem.** pmarca
follows thousands of accounts and adds more constantly. **The base rate of "a follow
by a high-signal account precedes a token move" is unknown, and it is almost
certainly tiny.** A detector firing on every follow by 200 busy accounts produces
a stream nobody can act on. ⛔ **This is forward-looking, so it needs a pre-committed
threshold and a measured base rate with n and an interval before it is called a
signal at all** (standing rule 6, and Marino applies in full because "this follow
means the token will run" is a prediction).

---

## 4. ⭐ The measurement to make FIRST, and it is free

Before any purchase decision, answer this from chain, at zero cost:

> For each claimed event, how long did the token take to move?

For AGRIPPA, MUSEBOOK, the GME pair, SI and EI: resolve the contract, then measure
from chain the time of the **first buy**, the time to **2x**, and the time to the
claimed peak.

- If time-to-2x is **tens of minutes**, then a 10-second on-chain detector is
  already inside the window, and the social watcher buys **attribution, not
  advance warning.**
- If time-to-2x is **under a minute**, no poll-based social watcher can help either,
  because the floor is the poll interval.
- ⭐ **There is only a narrow band where this is worth money**, and the free
  measurement tells us whether we are in it.

⛔ **We already have the alternative costed.** `programSubscribe` on the AMM
programs sees every swap as it happens: measured at 56 notifications/sec and 31
KB/s on pump.fun, 1.64M credits/month, which fits Helius Developer at 16%. **Total
about $53 to $55/month including a VPS** (`docs/TRACKER_SCOPING.md` §5c). That is
one tenth of the cheapest useful follow-monitoring configuration and it sees the
consequence of every social event, not just the ones from accounts we curated.

⭐ **Attribution is worth building even if advance warning is not**, and it is
Marino-safe because it describes what already happened: "this token moved, and this
follow preceded it" is a fact about the past. That version needs no real-time
watcher at all, only a retrospective lookup at the moment a move is detected, which
is a **handful of calls per event instead of millions per month.**

---

## 5. What not to do

- ⛔ **Never authenticate to a third-party follow tracker, and never depend on one**
  (standing rule 17, Frank 2026-09-19, permanent). They are AGGREGATE at best: read
  public output over HTTP, never sign in, never connect a wallet.
- ⛔ **And a tracker we cannot measure cannot be quoted for latency.** If we do not
  know its polling interval, rule 13 forbids quoting any duration derived from it.
- ⛔ **No scraping of logged-in X surfaces.** It breaks their terms, it needs
  credentials in a script, and the account is Frank's.
- ⛔ **A profile picture is an image.** Diff it by hashing the bytes at
  `profile_image_url`, never by trusting the URL string, and store the hash and not
  the image.

## 6. The recommendation, in one line

⭐ **Spend nothing yet. Run the free chain-side timing measurement in §4 first, then
the only configuration worth pricing is profile-picture polling on about 20 curated
accounts at roughly $4/month, with follows left alone until a measured base rate
justifies $8,640.**
