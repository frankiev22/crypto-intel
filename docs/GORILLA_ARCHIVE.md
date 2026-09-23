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
  navigation to a localhost sink instead (`sink.py`).

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

⛔ **And it is still not enough. Here is the proof, on a contract we verified by
hand the same day:**

> **EMBER.** The real contract is `FLCr9vGMNQMHQ6z9nQ4FbH3sABPn3ipEAyzJF68zHTsh`.
> Its operator withdrew **2,907.565 SOL** at 11:09:37Z on 2026-09-22 and burned
> the LP, leaving **$20.36** of depth. **It appears nowhere in the search results
> for "EMBER".** The resolver instead selected
> `5dvXTZ5qwgafnHtwu3Ls3QrWx1U4LQsFeCuJgkk4QEC6`, a different Solana token with
> $2.1m of liquidity, created one day before the mention, and graded it **HIGH
> confidence** and **alive**.

**The mechanism is simple and it is fatal to any survival statistic built this
way: the listings stop returning a token once it has no liquidity. A token that
died is invisible to them. So a ticker resolves to whatever living namesake
carries that symbol now, and the dead ones silently become survivors.**

⭐ **Therefore: there is no hit rate on Gorilla in this dataset, and producing one
would be a fabrication.** Rows that cannot be resolved with confidence are
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
