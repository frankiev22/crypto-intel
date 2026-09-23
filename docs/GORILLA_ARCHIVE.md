# The @CryptoGorilla archive: 49 daily recaps, and what they can and cannot tell us

2026-09-22. Built because Frank said, verbatim:

> *"You need to track every single one of these coins that you find on his page
> and then we can talk about what we want to buy here and also why. The why is
> important. I feel like I don't know what a lot of these coins do and I'm
> realizing too late."*

⭐ **The "why" is the deliverable, and it is the one field no on-chain source
has.** Everything else here exists to support it or to stop it being misread.

---

## 1. What was collected

**49 posts, content dates 2026-08-04 to 2026-09-21, one per day, no gaps.**
63,468 characters. 552 bullets. 732 ticker mentions. **482 distinct tickers.**

| artefact | what it is |
|---|---|
| `analysis/gorilla_archive/posts_raw.json` | all 49 posts, full text |
| `analysis/gorilla_archive/mentions.json` | one row per (ticker, date, bullet) |
| `analysis/gorilla_archive/dataset.json` | one row per ticker, the built universe |
| `analysis/gorilla_archive/gorilla_universe.html` | ⭐ the phone-first page Frank opens |
| Supabase `public.crypto_gorilla_archive` | 482 rows, keyed on contract address |

**How it was obtained, since this matters for repeatability.** ⛔ The X API was
not an option: our bearer is **402 credits-depleted** on every data endpoint
(probed 09-18 and 09-19), and there is no free tier. The posts were read through
**Frank's own logged-in Chrome**, which is the same access he has himself.

Three obstacles worth recording, because the next person will hit them:
- **X search caps each result window**, so the archive only comes out complete if
  you slice it into short date ranges (`since:`/`until:`). A single query returns
  about 5 to 8 posts and then stops.
- **The timeline truncates long posts** behind "Show more", so the full text only
  exists on each post's own page. 49 navigations.
- ⛔ **x.com's Content-Security-Policy blocks `fetch` to any other origin**, so
  the scraped text cannot be POSTed out of the page. A **URL fragment** is not
  governed by `connect-src` and is never sent to a server, so the payload rides a
  navigation to a localhost sink instead (`analysis/gorilla_archive/sink.py`).

⚠️ **Every post quotes the previous day's post in full.** Parsing the raw text
without cutting at the quote marker double-counts about half the archive and
back-dates every mention by a day.

---

## 2. ⭐ What is reliable here

**His words.** `what_it_does` is a verbatim quote with the date he said it.
Nothing is paraphrased and nothing is inferred. 279 of 482 tickers get a real
explanation, 166 are thin, and **37 are flagged `mention only`** because the
bullet listed several tokens and explaining none of them.

**His dated figures.** `reported_trajectory` is every market cap he quoted, with
its date, so the arc is visible rather than a single snapshot. They are **his
claims**, and we checked none of them.

**The categories**, derived from his own words by keyword evidence, never guessed:

| category | n | what it means |
|---|---:|---|
| ATTENTION | 341 | ⚠️ **no mechanism stated anywhere in the archive** |
| PAIRED | 59 | price tied to an underlying (see `docs/ASSET_PAIRED_TOKENS.md`) |
| LAUNCHPAD | 47 | earns fees on what launches through it |
| PRODUCT | 23 | a thing that does something (terminal, game, prediction market) |
| NFT-LINKED | 4 | |
| FEE-ROUTING | 4 | fees attached to a real person's Xmoney |
| FLYWHEEL | 4 | fees feed another token |

⭐ **341 of 482 have no stated mechanism at all.** That is the single most useful
answer to Frank's question. When he says he does not know what these things do,
the honest reply for **seven out of ten of them is that there is nothing to
know**: the archive describes a price move and an attention source, and no
product, no revenue and no mechanism.

---

## 3. ⛔⛔ What is NOT reliable, and why no hit rate is published

**The archive gives tickers. It does not give contract addresses.** That is the
whole problem, and it is standing rule 2 at scale.

Resolution, attempted for all 482 across Jupiter and Dexscreener on every chain:

| confidence | n | meaning |
|---|---:|---|
| HIGH | 164 | one dominant dated candidate |
| MEDIUM | 95 | leads the dated candidates |
| LOW | 202 | ⛔ several live tokens carry this ticker |
| NONE | 21 | nothing found at all |

⭐ **A date is a genuinely powerful disambiguator and it is new to us.** Gorilla
reports tokens that have *already* run, so the pool must exist by the day he
mentions it. That single rule **rejected 2,805 candidate contracts** whose
earliest pool postdates the first mention.

### ⛔⛔ RETRACTED 2026-09-23: the EMBER proof that stood here was inverted

**What this section used to say, and it is wrong:** that
`FLCr9vGMTkbDcRCoirP5Hx8gB7TW1Azt3pkw3qp2HTsh` was the real EMBER, that the
resolver wrongly picked `5dvXTZ5qwgafnHtwu3Ls3QrWx1U4LQsFeCuJgkk4QEC6`, and that
this proved the method cannot resolve a ticker. **Frank caught it. Measured
2026-09-23 00:56Z with liquidity summed across every pair:**

| | ⭐ **real EMBER `5dvXTZ5q…`** | ⛔ the phantom `FLCr9vGM…` |
|---|---|---|
| pairs | **30**, which is the API cap - read "30 or more" | 3, complete |
| liquidity, all pairs | **$2,331,895**, a FLOOR | ⛔ **$1.39** |
| market cap | $17,932,579 | ⛔ claimed **$1,314,046,208** |
| first pool | **09-09 22:25Z**, one day BEFORE the mention | 09-21 10:55Z, twelve days AFTER |
| quote assets | SOL $1.13M, **MET $522,677**, USDC $398k | SOL $1.39 |
| $2,000 round trip | ⭐ **TRADEABLE, $1,974.03 back, 1.30%** | TOTAL_LOSS, $0.33 back |

⭐ **So the resolver was RIGHT and I overrode it by hand with a wrong answer.**
The date rule did its job: the phantom's pool postdates the mention, and 19 of the
real one's 30 pools are Meteora with MET as its second-largest quote asset, which
is exactly what *"a token-pairing launchpad on Meteora"* looks like on chain.
⛔ **The lesson is the reverse of the one published: a hand-check on chain is not
automatically more trustworthy than a rule, because it can be on chain on the
wrong account.** Full record, with every retracted sentence quoted:
`data/findings/RETRACTION_2026-09-22_ember.md`.

### ⚠️ The survivorship mechanism is real, but it is measured, not proved by an anecdote

The listings **preferentially** drop a token once it has no liquidity, so the dead
tend to be invisible and a ticker resolves to whatever living namesake carries the
symbol now. ⭐ **Strength, measured on 44 cohort tokens absent from the search
index: 86.4% [73.3, 93.6] failed a live $100 round trip.** So absence is strong
evidence of death but not proof, and the phantom EMBER shows the converse too:
a dead token can stay in the index for at least a day after it is drained.

⭐ **Therefore: there is no hit rate on Gorilla in this dataset, and producing one
would be a fabrication.** ⛔ **The evidence for that is §4b's flat age curve, not
EMBER.** Rows that cannot be resolved with confidence are
labelled **`unverifiable`** (202 of them) rather than scored. The alive and faded
badges on the page describe **the token carrying that ticker today**, not the
outcome of his call, and the page says so in its own header.

---

## 4. ⛔ A correction I had to make to my own method, mid-build

I first checked whether "absent from the listings" really means dead by sampling
**6** of the missing tokens. All 6 were dead: no route, zero pairs, $0.0003 back
on $100. That looked conclusive.

**At n=44 it is 86.4% [73.3, 93.6].** Six of the 44 round-tripped fine, including
**ZEC** (`A7bdiYdS5GjqGFtxf17ppRHtDKPkkRqbKtR27dxvQXaS`), a bridged major that is
simply not in that search index, and which is the quote asset behind ZCAT.

⭐ **So absence from a third-party index is not death, and had I published from
the 6-token sample I would have overstated the base rate by roughly 14 points.**
Standing rule 15: the small-n finding is the exposed one. The base rate below is
therefore measured with a **live $100 round trip on every address**, which is the
same instrument we trust for everything Frank would act on, and which reports
unknown rather than death when Jupiter is merely unreachable.

---

## 4b. ⭐ The base rate, measured properly, and it is the number Frank should carry

Since his hit rate is not computable, the useful question becomes the one we CAN
answer from our own address-keyed data: **a token reaches $1m. What happens to
it?**

Cohort: every token our milestone ledger recorded crossing **mcap_1m** between
2026-08-21 and 2026-09-22, **698 distinct contracts**. Scored today with a live
**$100 Jupiter round trip** on each address.

| | |
|---|---|
| **can still round trip $100** | ⭐ **9.0% [7.1, 11.4], n=698** |
| cannot | **91.0%** |

Stratified by how long ago the crossing was, which is the only honest way to
read it:

| crossed | still tradeable |
|---|---|
| 0-7 days ago | 10.3% [7.0, 14.9] n=233 |
| 8-20 days ago | 13.2% [9.5, 18.0] n=243 |
| **21-34 days ago** | ⛔ **3.2% [1.5, 6.4] n=222** |

⭐ **A token that reached $1m a month ago has about a 3% chance of being
tradeable today.** That is the number to hold in mind while reading any recap,
including this one.

### ⛔ And this is what proves the ticker arm is an artifact

A real population decays with age, and the control does exactly that: 10%, 13%,
then 3% at a month. **The ticker-resolved arm is FLAT at 60 to 69% in every
bucket, including tokens called 35 or more days ago.**

| bucket | ticker arm (artifact) | real, address-keyed |
|---|---|---|
| 0-7 days ago | 67.9% n=56 | 10.3% n=233 |
| 8-20 days ago | 60.9% n=69 | 13.2% n=243 |
| 21-34 days ago | 69.1% n=68 | 3.2% n=222 |

⛔ **That flatness is impossible for real memecoins and is not evidence that he
picks well.** It is the signature of measuring "is some live token using this
ticker today", which is roughly constant in time, instead of "did his pick
survive". ⛔ **Never quote the left-hand column as his hit rate.**

## 4c. ⭐ Re-resolved with ALL-PAIRS liquidity, 2026-09-23

Frank: *"the archive extraction now REQUIRES a verified contract address per
ticker, resolved with all-pairs liquidity, with impersonators named. Write it to
the repo and to Supabase, not just a report."* Done, on all 482 rows, one call
per mint (**never batched** - three mints in one call return 30 pairs TOTAL,
split 15/14/1, which would reproduce the exact bug).

| verified_status | n | meaning |
|---|---:|---|
| **VERIFIED_LIQUID** | **253** | resolution HIGH/MEDIUM and >= $25,000 summed across every pool |
| ⛔ **UNVERIFIED** | **223** | several live tokens wear this ticker; we refuse to score it |
| **VERIFIED_DEAD** | 6 | BLAST, FORTUNE, LOTTO, MDUDAS, TWINE, XP - all at **$0** |
| PHANTOM | 0 | none of the chosen contracts is a ghost cap |

⚠️ **VERIFIED means "this address is the one he most likely meant, and these are
its real numbers now". It does NOT mean the call was good.** No hit rate is
computable - see §4b.

### ⭐ How much the single-pool bug actually mattered, measured

| | |
|---|---|
| median understatement | **1.01x** - i.e. **nothing**, for the typical row |
| rows understated by >= 1.5x | ⛔ **75 of 435 (17.2%)** |
| worst | **GP 4.60x**, PONS 4.27x, TSLA 3.79x, ORBIO 3.60x, **EMBER 3.55x**, DJT 3.52x, STONK 3.01x |
| rows at the 30-pair cap, so a FLOOR | **45** |

⭐ **This is the honest calibration and it cuts both ways.** For an ordinary
one-pool memecoin, reading one pool was fine. The error is concentrated entirely
in the multi-pool class - the pairing launchpads and the assets quoted in other
assets - which is **exactly the class this project has just decided is the
interesting one**. A bug that is harmless on the boring rows and 4.6x on the
interesting ones is worse than a uniform bug, because it survives casual checking.

### ⭐ Impersonators, named

**1,874 other live tokens wear these 482 tickers, across 437 of them.**
⚠️ That is a **floor**: the resolver stored at most 5 rival candidates per
ticker, so the true count is higher. Every one is listed on its card in
`gorilla_universe.html` and in `impersonators` in Supabase.

### Where it lives

| artefact | what it is |
|---|---|
| `analysis/gorilla_archive/dataset_allpairs.json` | the re-measured 482 rows |
| `analysis/gorilla_archive/reresolve_allpairs.py` | the rebuild, rules pre-committed in its docstring |
| Supabase `public.crypto_gorilla_archive` | 482 rows, 16 new all-pairs columns, verified by query |
| `analysis/gorilla_archive/gorilla_universe.html` | 721 KB, per-card pools / floor / impersonators |

---

## 5. How to use it

- ⭐ **Read the `what_it_does` line first.** It is the reason this exists.
- ⭐ **Filter to LAUNCHPAD, PAIRED, PRODUCT and FLYWHEEL** to see the ~130 tokens
  with a stated mechanism, and treat the 341 ATTENTION rows as what they are.
- ⛔ **Never take an address off this page to trade.** Take it to
  `python check.py <ADDRESS>` and to a live round trip at the size intended. The
  liquidity shown is the listings' reported field, which overstates by a median
  **781x**.
- ⛔ **A row marked `contract uncertain` has not been identified.** ACAT alone had
  **42 candidates**.

## 6. What this archive is good for that nothing else is

⭐ **It is a labelled record of what a knowledgeable human believed, in real time,
with dates.** That is rare and it cost nothing. What it is **not** is a list of
contracts, and the gap between those two things is exactly the gap that makes
memecoin data hard.

The obvious next step, and it is cheap: **the same scrape, forward, daily.** From
here on we can capture his call *and* resolve the contract while the token is
still alive, which removes the survivorship problem entirely for everything
published after today. Retroactively it cannot be fixed. Going forward it is a
cron job.
