# Every arXiv citation we lean on, checked against arxiv.org

**2026-09-23.** Asked because Frank asked where n=655,770 comes from, and because
these are about to go into a public whitepaper. **Six distinct arXiv IDs are
cited across the repo, 35 citation sites.** All six were fetched from
`arxiv.org` directly.

---

## 1. ⭐ The Marino citation is REAL and every part of it verifies

**arXiv:2602.14860** resolves to a real paper.

| | |
|---|---|
| title | **"Predicting the success of new crypto-tokens: the Pump.fun case"** |
| authors | **Giulio Marino, Manuel Naviglio, Francesco Tarantelli, Fabrizio Lillo** |
| submitted | **16 February 2026** |
| our claimed n | **655,770** |
| ⭐ **verified, verbatim from §IV** | *"a total of 655,770 tokens were created by 243,123 distinct token creator addresses"* |

⭐ **And the finding we rest the whole product on verifies too.** §VI, "An
economic breakeven curve": *"p_std(vSol) lies below the breakeven curve, hence it
is not possible to make profits with a buy-and-hold strategy based only on
vSol"*, and §VII: *"all conditional graduation-probability curves remain below
the economic breakeven over most of the vSol range."* §VI equation (3) is the
profitability condition **p(vSol, θ) > vSol² / 115²**.

⭐ **So "perfect knowledge of graduation probability still loses money" is a fair
summary of a real result in a real paper, with the right authors, the right ID
and the right n.** Nothing to change.

---

## 2. ⛔⛔ The Kamat citation is SUPERSEDED, and the author superseded it himself

This is the one that matters, and it needs to come out of anything public.

**arXiv:2607.02823 has four versions and we are citing v1.**

| version | date | title |
|---|---|---|
| **v1** | 2 Jul 2026 | *"Pump.fun Graduation Regime Windows: Survival Analysis of 832,941 Token Launches and the Social-Presence Effect"* |
| v2 | 13 Aug 2026 | (size drops 1,320 KB → 70 KB) |
| v3 | 17 Aug 2026 | |
| ⛔ **v4, CURRENT** | **10 Sep 2026** | *"Auditing Collector-Generated Graduation Labels on Pump.fun: **Measurement Error and Temporal Non-Generalization**"* |

⭐ **v1 does say exactly what we quote**: *"The pooled graduation rate is 0.198%
(Wilson 95% CI [0.189%, 0.208%])"* on 832,941 launches. **Our citation was
accurate when it was made.**

⛔⛔ **The current version is a different paper with a different conclusion.**
n is **749,816**, not 832,941. It reports **no pooled graduation rate at all.**
Its stated findings, verbatim from the v4 abstract:

- *"The collector's TIMEOUT label does not establish platform-side
  non-graduation."*
- development AUROC **0.8594**, validation AUROC **0.4642**, *"95% percentile
  interval [0.4112, 0.5196] containing 0.5000"* — **the model does not generalise
  at all out of sample**
- *"of nine automated evaluations, two pass, six fail, and one is not evaluable"*
- *"treats outcome ascertainment as a first-order measurement problem rather than
  assuming that an off-chain collector's terminal classification measures the
  platform-side event"*

⛔ **Read that last line against what we have been doing all week.** The author
withdrew a survival analysis because the graduation labels it rested on came from
an off-chain collector and could not be shown to measure the real event. **That
is the same defect class as our `gone` label**, found independently, in the
literature, thirteen days ago.

### What has to change because of it

⛔ **`CLAUDE.md`'s "graduation base rate, published: 0.198% [0.189, 0.208],
n=832,941" may not be quoted as current literature.** It is a v1 figure the
author has since replaced.

⛔⛔ **And our own 0.22% loses its corroboration.** CLAUDE.md says our figure
*"agrees with Kamat's 0.198%"*. That agreement is with a withdrawn framing, so
**0.22% now stands on our own measurement alone** and must be presented that way.

⚠️ **The Social-Presence Effect results in `docs/CREATOR_PLAYBOOK.md`** (1.919%
vs 0.110% graduation on social links, Cox HR 4.506, p < 10⁻³⁰⁰, all at n=832,941)
come from the v1 title's second half. **They rest on the same superseded labels**
and are not to be published either.

---

## 3. The other four, checked

| ID | real? | our claim | verdict |
|---|---|---|---|
| **2602.13480** MELT, Hu, Tekin, Xu & Liu, 13 Feb 2026 (v2 21 May) | ✅ | 41k+ launches, 200M+ tx, **36.5%** supply in coordinated accounts | ⭐ **verifies verbatim** |
| **2608.20271** *"Catching the Rug"*, Li, Kuznetsov, Yanovich, Nott-Whaley & Vodolazov, 20 Aug 2026 | ✅ | 6.4M tokens / 7 months, "vast majority" rug within an hour | ⭐ **verifies** |
| **2507.01963** *"A Midsummer Meme's Dream"*, Mongardini & Mei, 16 Apr 2025 (v2 2 Jan 2026) | ✅ | 34,988 tokens, 4 chains, **82.89%** | ⚠️ **the paper says 82.8%, not 82.89%** — fix the digit |
| **2512.11850** *"The Memecoin Phenomenon"*, 4 Dec 2025 | ✅ | Q4 2024 graduation < 2% | ⛔ **WRONG AUTHOR: we credit "Mzoughi et al."; the author is DAVIDE MANCINO** |

⚠️ **A tooling correction of my own, so it is not repeated.** My first check used
`export.arxiv.org` over curl and returned **zero bytes for every ID including a
control** (`1706.03762`, "Attention Is All You Need"). That was my network path
failing, not the papers. **The control is why I did not report six fake
citations.** Separately, the page summariser called `2608.20271` *"fabricated"*
because it read 20 Aug 2026 as a future date; **today is 23 Sep 2026**, so that
was its stale clock and the paper is real.

---

## 4. The answer to Frank's question, in one line

⭐ **n=655,770 comes from Marino, Naviglio, Tarantelli & Lillo, arXiv:2602.14860,
16 Feb 2026, and it is the count of tokens created on pump.fun in their window.
It is real, correctly attributed, and correctly used.**

⛔ **It was the OTHER paper that needed catching.**
