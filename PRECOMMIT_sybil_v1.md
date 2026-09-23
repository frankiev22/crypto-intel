# PRE-COMMIT: the stacked-signal coordination detector, v1

**Written 2026-09-23 before a single wallet was scored against it.** Standing
rule 6, and Frank's own instruction: *"you pre-committed the verdict rule to a
file before querying, and that is why the 1.7% result is trustworthy. Do that on
every experiment from now on."*

---

## 1. What this is, and what it is not

Frank, 2026-09-23: sophisticated bundlers *"fund 20-plus wallets through paths
that defeat naive funding-graph clustering."*

⛔ **So the funding graph is already defeated and cannot be the detector.** It is
kept, demoted, for **hub identification only**.

⭐ **The output is a CONFIDENCE LEVEL with its contributing signals named. Never
a binary verdict**, and never a number that could be read as a ranking of which
token to buy. This describes coordination that has **already happened**, which is
the narrow exception Marino allows. It says nothing about what the price will do.

⛔ **And the framing already failed once on this population, which is why v1 is
built to report a negative loudly.** Measured 2026-09-23: top holders of fresh
pump.fun graduates are **not** fresh wallets, every one carried **3,000+
signatures**, and **0 of the top 10 of either tested graduate was fresh**.
Collapsing those wallets by shared funder would have manufactured clusters out of
ordinary market participants. **"All of these are established traders" is a real
result and this module must be able to say it.**

---

## 2. The four signals, and why each is ranked where it is

Ranked by **how hard each is to defeat**, which is the only ranking that matters
for an adversarial signal. Each is weak alone. None is sufficient.

| # | signal | why it is hard to defeat | weight |
|---|---|---|---|
| **S1** | **same-slot co-buying** | Splitting one buy across 20 wallets is *what makes them arrive together*. Defeating it means staggering across slots, which costs the launch price you were bundling to get. | **3** |
| **S2** | **wallet age and history** | Ageing 20 wallets costs real time and rent, and cannot be bought after the fact. | **2** |
| **S3** | **post-launch behavioural correlation on sells** | The exit is harder to disguise than the entry: the reason to bundle is to sell into the crowd, and that has to happen. | **2** |
| **S4** | **shared funder** | ⛔ Already defeated by anyone competent. **Hub identification only.** | **1** |

⭐ **S4 may never be the largest contributor to a level.** If S4 alone fires, the
level is capped at WEAK and the report says the funding graph is defeatable.

---

## 3. The thresholds, fixed now

Measured against the **first `N_BUYERS = 30`** distinct wallets to receive the
mint, excluding the pool account and the mint itself.

**S1, same-slot co-buying.** A *co-buy group* is 2 or more distinct buyer wallets
receiving the mint **in the same slot**.
- fires when `max_group >= 3`, or when `>= 2` distinct groups of `>= 2` exist
- `co_buy_share` = buyers in any group / buyers examined

**S2, wallet age.** A wallet is **FRESH** when `activity_before(wallet, its
first signature on this mint)` returns nothing.
⛔ **Never date a wallet by walking its history** - that gave WOFI an age of
**minus 0.1 hours** (`docs/DEV_WALLET.md`).
- fires when `fresh_share >= 0.30` of the wallets whose age could be established
- ⚠️ a wallet whose age could not be established is counted in neither numerator
  nor denominator, and the count of those is reported

**S3, exit correlation.** Of the buyers that sold at all, the share that sold
within `EXIT_WINDOW_S = 600` of another buyer in the set.
- fires when `>= 3` wallets sold inside one window and that is `>= 0.30` of
  sellers

**S4, shared funder.** Two or more buyers funded by the same wallet, where the
funder is not a known router or exchange.
- fires when `>= 3` buyers share one funder

## 4. From signals to a level

`points` = sum of the weights of the signals that fired.

| points | level |
|---|---|
| 0 | **NONE OBSERVED** |
| 1 to 2 | **WEAK** |
| 3 to 4 | **MODERATE** |
| 5 or more | **STRONG** |

⛔ **Caps, and they bind before the table:**
- If **only S4** fired, the level is **WEAK**, whatever the points say.
- If fewer than `MIN_BUYERS_TO_JUDGE = 8` buyers could be examined, the level is
  **INSUFFICIENT DATA** and no signal is reported as having fired. A thin sample
  is not a clean token.
- If the buyer walk was **truncated**, the level carries `truncated: true` and
  is a **FLOOR**: it proves presence, never absence (the recurrence lesson).

## 5. What this will never output

- ⛔ No score, grade, rank, rating or expected return. `test_sybil.py` fails at
  the AST level if such a name appears.
- ⛔ No binary "bundled / not bundled".
- ⛔ No claim that an uncoordinated launch is safe. **Coordination is one fact
  among many**, and its absence is not a verdict about anything else.

## 6. The cluster-buy lane, same machinery

Frank: *"I also want to find a way to see if coins are popping up from multiple
big wallets."*

Fire when **`CLUSTER_MIN_WALLETS = 3` or more wallets from our recurrence
registry** buy the same mint inside `CLUSTER_WINDOW_S = 900`.

⛔ **This is a COORDINATION observation, never a buy signal.** The standing
lesson from the Fomo work is that the most-copied wallet is the worst to copy,
and our own re-derivation of degentape's tape put **6.0% [5.8, 6.3]** of 45,853
closed positions at 2x or better. **Following these wallets is a measured way to
lose money.** What the signal is for is noticing that a launch is being worked.

⚠️ The registry is a **FLOOR by construction**: it holds the wallets we have
happened to see top-holding a mint before. A wallet absent from it is not new,
it is unseen.

## 7. What would make v1 WRONG, stated before it runs

- ⛔ If S1 fires on most ordinary launches, same-slot arrival is a property of the
  venue rather than of coordination, and the weight must move to 0 rather than be
  re-tuned. **A pump.fun graduation migrates in one transaction, so a migration
  slot is not a co-buy** and must be excluded, not explained away afterwards.
- ⛔ If S2's fresh share is near zero everywhere, as the 2026-09-23 holder
  measurement suggests it will be, then freshness is not discriminating on this
  population and the module must say so rather than quietly contributing 0.
- ⭐ Both are checkable from the recorded rows, because **every run records every
  signal's own measurement whether or not it fired**. A detector that records
  only what it flagged cannot be audited.


---

# RESULT, 2026-09-23, the same day the rule was written

## ⛔⛔ S1 AS SPECIFIED IS DEAD. The control killed it, and section 7 said it would.

Section 7 pre-committed this exact test: *"If S1 fires on most ordinary launches,
same-slot arrival is a property of the venue rather than of coordination, and the
weight must move to 0 rather than be re-tuned."*

**Measured on 9 consecutive pump.fun graduations from our own ledger, chosen by
recency and nothing else:**

| mint | buyers | max group | groups | co-buy share | fired |
|---|---|---|---|---|---|
| `4MN7pQ2ZkMroFJ8MS4uPUqg1CoXwNta91h5aZCSDpump` | 30 | 6 | 8 | 0.667 | yes |
| `8X6ShANz6ADqvGQunfH6yESZNmMsckj5ewFVuMhCpump` | 30 | 3 | 9 | 0.733 | yes |
| `BxVALYGUQzCx4zNcdwePoqTneU8UkCjt6dWvswC8pump` | 30 | **23** | 3 | 0.933 | yes |
| `3UYFF99NeKBPK68x8CDE1qzcv8gCp2LjbZFpC9j2pump` | 8 | 3 | 2 | 0.625 | yes |
| `sDYbw2KoXuuMwftSUDAtiCX9VDbj1ygyaS1tAbVpump` | 20 | 6 | 5 | 0.750 | yes |
| `4gxTaTn9gbRvVtmDokkqc5qe7RBFgzot5J2EZN7Gpump` | 30 | 5 | 7 | 0.667 | yes |
| `26EVFPJnjTP83GJcru1PGoNXa9Z2e3DyhuygugMfpump` | 10 | 3 | 3 | 0.800 | yes |
| `55Tn9f8NjeiFpDi3ofoQumtxFaQ3v4GNcpVwVHFKpump` | 30 | 6 | 7 | 0.867 | yes |
| `EoCvLdAnZKbuqEq8zgTi2X2PmYmuhKLLngeJp5w8hK8P` | 17 | 7 | 3 | 0.882 | yes |

⛔ **9 of 9. Co-buy share 0.625 to 0.933, median 0.750.** A signal that fires on
everything separates nothing.

⭐ **The mechanism, and it is obvious in hindsight:** a Solana slot is about 400
ms and packs many transactions, and a launch is a frenzy. Independent buyers land
in the same slot because the slot is wide, not because they are one actor. Sharing
a slot is the BASE RATE at a launch.

⛔ **So `WEIGHTS["S1_same_slot"] = 0`, in code, today.** The measurement is still
taken and still recorded on every row, because that is how the next version gets
a baseline, but it contributes nothing to a level.

⚠️ **And the STRONG verdict this detector produced on its first live run is
WITHDRAWN.** `55Tn9f8NjeiFpDi3ofoQumtxFaQ3v4GNcpVwVHFKpump` scored STRONG on 5
points from S1 and S3. S1 was measuring the venue. **That verdict must never be
quoted.**

⛔ **What is NOT allowed here, and it is the tempting move:** redefining S1 as
"co-buy share above the launch baseline" now that the baseline has been seen. That
is choosing a threshold after looking at the data, which is the score-gated-evidence
bug this whole file exists to prevent. **A baseline-relative co-buying signal needs
its own pre-commit, written before it is measured, in its own file.** It is not
part of v1.

## ⭐ What the same run DID establish, and it is the thesis

On the one mint taken deep before the control was run:

| signal | result |
|---|---|
| S2 wallet age | did **not** fire, 2 fresh of 12 datable (16.7%) |
| S4 shared funder | did **not** fire, largest shared-funder group **1** of 10 |

⭐⭐ **The funding graph found NOTHING on a real mint, exactly as Frank said it
would.** Had this been built as a funding-graph detector, which is what every
public bundle checker is, it would have returned "clean". That is the whole
argument for stacking, and it survived contact even though S1 did not.

⚠️ **n=1 for the deep signals, and n=9 for S1.** Neither is a rate. Standing
rule 7 applies and nothing here is published as one.


## ⛔⛔ AND S3 WAS BROKEN TOO, in a way its own control exposed within the hour

Run on the same 9 graduations:

| mint | sellers seen | largest cluster | exit share | fired |
|---|---|---|---|---|
| `4MN7pQ2ZkMro…` | 1 | 1 | **1.000** | no |
| `8X6ShANz6ADq…` | 15 | 15 | **1.000** | yes |
| `BxVALYGUQzCx…` | 22 | 22 | **1.000** | yes |
| `3UYFF99NeKBP…` | 1 | 1 | **1.000** | no |
| `sDYbw2KoXuuM…` | 2 | 2 | **1.000** | no |
| `4gxTaTn9gbRv…` | 3 | 3 | **1.000** | yes |
| `26EVFPJnjTP8…` | 3 | 3 | **1.000** | yes |
| `55Tn9f8Njeii…` | 11 | 11 | **1.000** | yes |
| `EoCvLdAnZKbu…` | 2 | 2 | **1.000** | no |

⛔ **`exit_share` is 1.000 on all nine, including mints with ONE seller**, and
the largest cluster always equals the total seller count. The signal was not
measuring clustering at all: **`flows()` reads the mint's first ~300 signatures,
which all land within minutes of launch, so every sell in the sample is inside a
600-second window BY CONSTRUCTION.** The window is wider than the sample.

⚠️ **That is standing rule 13, in code I wrote today**: never measure a
phenomenon with a sampler narrower than the phenomenon. "Fires on 5 of 9" looked
like a working discriminator and was an artefact of the read.

⭐ **The fix is a PRECONDITION, not a threshold change.** S3 now returns
`fired: None` with `unevaluable: true` and the span it saw, whenever the observed
sells span no more than the window. **Unevaluable is not a clean negative.**

⛔ **Evaluating S3 properly needs the mint's LATER transactions**, which
`flows()` deliberately does not read, because it is built to reach a mint's
FIRST transactions cheaply. That is a capability change and it gets its own
pre-commit before it is measured. Not in v1.

---

# ⛔⛔ WHERE v1 STANDS, stated plainly

| signal | weight | status after its own control |
|---|---|---|
| S1 same-slot co-buying | **0** | **DEAD.** Fires on 9 of 9 ordinary launches. Slot sharing is the base rate at a launch |
| S2 wallet age | 2 | alive, and expected to be near-useless on this population: 2 fresh of 12 datable on the one deep run, and the 2026-09-23 holder work found 0 fresh wallets in the top 10 of two graduates |
| S3 exit correlation | 2 | **UNEVALUABLE** on the current read. Needs later transactions |
| S4 shared funder | 1 | alive, demoted, and it found **nothing** on a real mint - largest shared-funder group 1 of 10 |

⛔⛔ **So v1 has no signal that is both alive and demonstrated to discriminate,
and that is the honest headline.** The machinery is built, wired and running; two
of its four signals were killed by the controls this file demanded, on the day it
was written, before a single verdict was published to Frank.

⭐ **That is the process working rather than failing.** The alternative was
shipping a detector that fires on 9 of 9 ordinary launches and calling it a sybil
finding. ⛔ **The one live verdict it produced, STRONG on
`55Tn9f8NjeiFpDi3ofoQumtxFaQ3v4GNcpVwVHFKpump`, is WITHDRAWN and must never be
quoted.**

⭐ **What IS demonstrated and worth keeping:** the funding graph, which is what
every public bundle checker uses, returned nothing on a real mint where two other
signals were screaming. Frank's claim that it is already defeated is consistent
with the first real measurement we have taken of it.
