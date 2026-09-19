# Consolidation plan — one place for all of the crypto work

**2026-09-18, revised 2026-09-19 for the tracked universe (§8). A PLAN. Nothing
has been moved, deleted, dropped or republished.**
Frank: *"I want to mesh all of the crypto stuff into one place."* Every item
below was inventoried live today; each "retire" or "drop" is its own yes from
Frank at the time it happens, because moving things is how links break.

⛔ **The test:** one URL Frank opens, one repo he can clone, one backlog, one
handoff file. **If it doesn't reach him through those, it doesn't exist.**

---

## 1. What the single place is — confirmed, with three corrections

**Confirmed: the repo is the system, the hosted site is the face.**
`github.com/frankiev22/crypto-intel` holds the code, the data (`data/` is the
state store, committed every pass), the docs, the backlog and the handoff.
`https://crypto-intel-one-eta.vercel.app` is the only page Frank opens.

**Correction 1 — the site is not yet the face. There are four faces today:**

| face | what it is | fate |
|---|---|---|
| Vercel site | reads `data/` from the public repo at one commit | ⭐ **THE face** |
| `data/dashboard.html` | static page rebuilt every pass by the collector | retire after the site reaches parity (§5) |
| claude.ai "crypto-intel dashboard" artifact | a snapshot, last updated 09-17 | ⛔ **stale duplicate — retire** (§4) |
| Discord alerts + phone reports (daily research, digests) | push | keep as a channel; **every message links to the site and carries no number the site doesn't show** |

**Correction 2 — two things cannot live in the repo, by necessity, and that is
fine as long as their CODE and SCHEMA do:**
- **Secrets.** The repo is public. Keys live in four stores: local `.env`,
  GitHub Actions secrets, Vercel env, Supabase `private.crypto_config`.
  CLAUDE.md lists the names, never the values. "Clone the repo" gets
  everything except keys.
- **Always-on runtimes** — GitHub Actions (the collector), Supabase pg_cron
  (news, every minute), the Vercel function (Helius webhook). They are deploy
  targets, not places. ⛔ **Violated today:** seven Supabase views and one
  public grant exist only in the live database, in no migration (§3).

**Correction 3 — "one repo" has a neighbour.** `github.com/frankiev22/bots`
holds `crypto_bot/` (a perp **funding-carry** paper bot) beside Polymarket,
ticket and GPU bots, reported to Frank daily by the `paper-bots-daily` task.
It is crypto, but a different strategy class with its own ledger and its own
Windows Task Scheduler launcher (which this repo deliberately removed).
**Decision for Frank (§7b).**

---

## 2. Inventory — everything crypto, where it is, and its verdict

| # | item | where | state, verified 2026-09-18 | verdict |
|---|---|---|---|---|
| 1 | pipeline, data, docs, tests | repo | live; scheduled runs committing | ✅ **the system** |
| 2 | site + `/api/feed`, `/api/ca` | repo `site/` → Vercel | live | ✅ **the face** |
| 3 | Helius webhook receiver | repo `site/api/helius.mjs` → Vercel | answering, watching **0 addresses** (BACKLOG C8) | ✅ in; already in the repo |
| 4 | paper ledgers v1/v2/v3 | repo `data/paper/` | v1/v2 quarantined, v3 live | ✅ in |
| 5 | `data/market/` (new) | repo | written by an unattended run 23:49Z | ✅ in |
| 5a | ⭐ `data/universe/` (new 2026-09-19): every Solana token ≥ $1M that passes a $100 round trip, kept for good, plus narratives | repo | seeded 2026-09-19 (manual); scheduled from the next pass | ✅ in — **the new centre of the face** (§8) |
| 5b | ⭐ `data/graduations/` (new 2026-09-19): every pump.fun graduation, BACKLOG C14 | repo | seeded 2026-09-19 (manual) | ✅ in |
| 6 | `data/dashboard.html` | repo | rebuilt every pass | ⏳ retire after site parity (§5) |
| 7 | claude.ai **"crypto-intel dashboard"** `AhG3R2EG…` | claude.ai | snapshot, 09-17 | ⛔ **retire — stale duplicate** |
| 8 | claude.ai **"Crypto Intel Teardown"** `BLEBQtXB…` | claude.ai | 08-22 review. Its headline security finding (non-crypto tables readable with the public key) **no longer reproduces**: those tables 404 on this project's API today (count-only probe, no rows read) | ⛔ **retire — but ⚠️ NOT copied verbatim: the repo is PUBLIC and the review names non-crypto tables that held personal data.** Copy only its crypto findings into `docs/reviews/2026-08-22_teardown.md`; the rest stays private, Frank's call (corrected 2026-09-19) |
| 9 | Supabase — 7 analytic views | Supabase only | 6 publicly readable, 1 denied; computing retracted metrics live | ⛔ **drop** (§3) |
| 10 | Supabase — `crypto_score_weights` public read | Supabase only | 5 rows, last 09-14; grant in no migration | ⛔ **revoke anon read** |
| 11 | Supabase — observations/outcomes mirror | Supabase, fed by `journal._push` | live (last row 23:49Z) | ⛔ **stop** once the views are gone — git is the store |
| 12 | Supabase — `crypto_news` + pg_cron `crypto-news` | code in repo, runs on Supabase | every minute; `news.py` reads it | ✅ **keep as a service** |
| 13 | Supabase — `crypto_digests` + `crypto-digest` | code in repo | last 23:30Z; `site/index.html` reads it | ✅ keep until site parity, then decide |
| 14 | Supabase — `crypto_whale_events` + `_public` view | receiver writes; view public | **2 rows, last 08-22** | drop the view with #9; table stays for C8 |
| 15 | scheduled task `crypto-collect-hourly` | `Documents/Claude/Scheduled` | **dead since 09-15**; Actions replaced it | ⛔ **retire**, and drop `test_stages.py` §9 — a repo test depending on a file outside the repo is itself scatter |
| 16 | tasks `crypto-api-keys-morning`, `crypto-keys-noon` | same | one-off reminders from 08-21 | ⛔ **delete** |
| 17 | task `crypto-daily-research` | same | routes a daily report to Frank's phone; reads the **Supabase mirror**; committed "Daily research report" 09-10, 09-11, 09-14 | 🔁 **fold**: read the repo, write the report into `docs/research/`, send Frank a link |
| 18 | task `paper-bots-daily` | same | reports on the `bots` repo | decision §7b |
| 19 | `Desktop/Projects/crypto-inefficiency-research.md` | loose file, 06-09, 25 KB | predates the repo | 🔁 **move into `docs/archive/`** |
| 20 | X/Twitter keys | `dispatch-workspace/.env`, two `gateway.cmd` | only copies; none in `crypto-intel/.env` | 🔁 **copy into `crypto-intel/.env`** (gitignored; values never printed). Originals stay — other projects use them |
| 21 | competing backlogs: `GAPS.md`, `OPEN_ITEMS.md`, `QUESTIONS.md`, `SCOREBOARD.md` | repo root | last touched 09-15, 09-06, 09-07, 08-28 | 🔁 **audit every open item into `docs/BACKLOG.md`, then stamp each "SUPERSEDED"** (not deleted) |
| 22 | competing handoffs: `README.md`, root `RULES.md`, Claude memory | repo / `~/.claude` | README describes the 08-20 "regime dashboard"; `RULES.md` vs `docs/RULES.md` ("do not confuse") | 🔁 README → ten lines pointing at the site, CLAUDE.md and the backlog; fold root `RULES.md` into CLAUDE.md; memory keeps pointers only |
| 23 | ~30 analysis docs at repo root | repo | referenced from code comments, CLAUDE.md, site README | 🔁 **`docs/INDEX.md` now; move into `docs/` later, only behind a reference checker** (§6) |

---

## 3. The Supabase views — recommendation: KILL, after capturing them

Project `rxofejxostyqlgjlzqmk`. Probed today with the publishable key:

| object | public? | rows | what it computes |
|---|---|---:|---|
| `crypto_scoreboard` | **readable** | 107,664 | per-observation result at 1/6/24h, live |
| `crypto_scoreboard_hits` | **readable** | 35,888 | one row per flagged token, three horizons |
| `crypto_score_bands` | **readable** | 21 | **win rate by score band** |
| `crypto_scoreboard_lift` | **readable** | 6 | passed vs rejected "lift" |
| `crypto_feature_lift` | **readable** | 6 | per-gate win rate, pass vs fail |
| `crypto_whale_events_public` | **readable** | 2 | truncated whale events, last 08-22 |
| `crypto_obs_gates` | denied | — | gate recomputation on `liq` thresholds |

**Why kill, not fold:** they compute exactly the numbers this project has
retracted — win rates by score band (the band was deleted from every entry
gate), "lift", on reported liquidity (overstates a median 781x), from a mirror
of the quarantined ledgers' population. They are public, live, and will
disagree with the site. There is nothing in them worth folding: git already
holds every row they read.

**Order, so nothing is lost:** (1) migration `002_capture_live_state.sql` puts
the live definitions of all seven views and the `crypto_score_weights` grant
into the repo — the repo becomes true to the database *before* anything is
removed; (2) confirm zero readers in Supabase's API logs (Frank's dashboard
access — the public key cannot see logs); (3) migration `003` drops the views
and revokes the grant; (4) stop `journal._push` by removing the Supabase
secrets from the runner — reversible by putting them back.

**Kept on Supabase, as services with their code in the repo:** news (pg_cron,
every minute - the only collector that doesn't depend on GitHub's cadence),
digests (until the site no longer needs them), whale events (for C8).

---

## 4. The duplicates in the "retire so there aren't two versions" category

1. ⛔ **claude.ai "crypto-intel dashboard"** — the one you named.
2. ⛔ **claude.ai "Crypto Intel Teardown"** — same category: a page of numbers
   and verdicts from 08-22 that no longer match the system.
3. ⛔ **`data/dashboard.html`** — a second live face in the repo itself, rebuilt
   every pass. Not linked from anywhere Frank opens, but it is what the
   claude.ai dashboard was built from, and it will drift from the site.
4. ⛔ **The seven Supabase views** — a third, public, set of numbers.
5. ⚠️ **`SCOREBOARD.md`** at the repo root — pre-retraction scoring numbers
   (08-28) sitting beside the current ones.

**Retiring an artifact without breaking its link:** republish it as a
one-screen tombstone — "This moved to <site URL>", no numbers — then delete it
after 14 days. Deleting at once kills the link Frank may have bookmarked;
leaving it keeps the stale numbers. The tombstone does neither.

---

## 5. The face: what the site needs before `dashboard.html` can stop

⚠️ **Superseded in part by §8**: the face is no longer the launch scanner with
market panels added. The section below still lists what `dashboard.html` shows
and must not be lost.


Parity, section by section, against what `dashboard.html` shows today:
narrative clusters · graduated · approaching band · fraud flags · movers. Plus
what only the repo has: `data/market/` (movers, volume, trending, tape),
crossings with `exit_depth_at_crossing`, paper v3, liveness freshness, and a
**backlog page rendering `docs/BACKLOG.md`** — "one backlog" means Frank reads
it on the same URL. Schema: `docs/MARKET_DATA.md`.

---

## 6. Sequencing — each phase is independently reversible

| phase | what | user-visible? | needs Frank's yes |
|---|---|---|---|
| **0** | migration 002 (capture live Supabase state) · reference-checker test (✅ `test_references.py`, 2026-09-19) · `docs/INDEX.md` · the Teardown's **crypto findings only** into `docs/reviews/` · copy X keys into `.env` | no | no — additive only |
| **1** | tombstone both claude.ai artifacts · delete the two 08-21 reminder tasks · retire `crypto-collect-hourly` | yes | **yes, each** |
| **2** | Supabase: drop the seven views, revoke `score_weights`, stop the mirror | public API | **yes** |
| **3** | fold `crypto-daily-research` into the repo · every alert carries the site URL | phone | **yes** |
| **4** | site parity (§5) → stop committing `dashboard.html` | yes | yes |
| **5** | move root docs into `docs/`, with the reference checker green | no | no |

**What could break, and the guard:** artifact links (tombstone) · Supabase view
readers (API logs first) · the ~30 root doc paths referenced from code comments,
CLAUDE.md and `site/README.md` (the checker lands in phase 0, before any move) ·
`test_stages.py` §9 reading a file outside the repo (removed with the task).

---

## 7. Decisions only Frank can make

a. **Repo = system, site = face**, with the three corrections in §1. Yes/no.
b. **The `bots` repo's `crypto_bot` funding-carry bot** — fold into this repo,
   or stay separate and appear on the site as a read-only panel? My
   recommendation: **separate code, one face** — the site reads its ledger; the
   code stays where its scheduler is, and is listed in CLAUDE.md.
c. **Supabase**: drop the seven views and stop the mirror. Recommend yes.
d. **claude.ai artifacts**: tombstone-then-delete (recommended) or delete now.
e. **`crypto-daily-research`**: fold into the repo (recommended) or retire.
f. **An always-on box, ~$4–6/mo** (new, 2026-09-19). It moves the universe from
   a ~7-a-day re-check to every 5 minutes, and it is the host C5 needs. Priced,
   not bought. **His call alone; nothing is signed up for.**
g. **The wallet farm in the universe** (new, 2026-09-19, `docs/UNIVERSE.md` §3a):
   30 members, $3.53B of claimed cap on a fraction of a percent of backing, pass
   the $100 liquidity gate. Show them flagged (the current default) or build and
   validate a detector to exclude them.

---

## 8. 2026-09-19 — the tracked universe changes what the face IS

Frank: *"I need all coins over $1M market cap tracked and the top trending ones
always visible which can lead to determining the narratives."* That is a
different product from the one the site shows. The site is built around
**launch events** (graduated, crossed a tier, approaching the band, flags).
Frank is asking for a **standing universe** with trending on top and
narratives read off it. The pipeline half now exists (`docs/UNIVERSE.md`); the
face has to be reorganised around it, not given another panel.

**The single place, restated.** One URL, whose first screen is:

| order | panel | file | status |
|---|---|---|---|
| 1 | **Top trending, always on screen**: every trending token with its universe status and gate verdict. Dexscreener boosts are labelled PAID | `data/universe/narratives.json` → `trending_now` | pipeline ✅, site ⬜ |
| 2 | **Narratives**: name clusters over the live universe, plus Dexscreener themes intersected with it | same file, `name_clusters`, `themes` | pipeline ✅, site ⬜ |
| 3 | **The universe**: every member with gate status and age, market cap, moves, "under $1M since", "failing since" | `data/universe/members.json` | pipeline ✅, site ⬜ |
| 4 | **Movers, volume, the tape** | `data/market/*.json` | pipeline ✅ (unattended 23:49Z), site ⬜ |
| 5 | **Crossings, each with its depth at the crossing** | `data/milestones/` `exit_depth_at_crossing` | pipeline ✅ (unattended), ⛔ **site ignores the field** |
| 6 | Launch-side sections that exist today (graduated, approaching, flags) | as now | ✅ — moves below the fold |
| 7 | Paste a CA → one report, which now also answers "is it in the universe, and does it sell" | `/api/ca` + `members.json` | ⬜ |

**Why it matters for consolidation.** Eleven of the thirteen rows the SHIPPED
audit reclassified (BACKLOG, "SHIPPED-row audit") are pipeline output that
reaches no page. **One site change, reading these four sources, closes most
of the gap**, and it is what lets `dashboard.html` retire (§5) without losing
anything. It is BACKLOG **C16** and it belongs to the site session. The
pipeline side publishes the schemas in `docs/MARKET_DATA.md` and
`docs/UNIVERSE.md` and does not edit `site/`.

**What stays genuinely separate:** the always-on runtime. The universe is
re-checked ~7 times a day because GitHub delivers ~7 passes a day (C10). A
$4–6/mo box would re-check it every 5 minutes and re-gate every member hourly.
The same box serves `programSubscribe` (C5). **That is a purchase and it is
Frank's call** (§7f).
