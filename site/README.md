# site/

The hosted dashboard. Live at **https://crypto-intel-one-eta.vercel.app**.
Deployed 2026-09-18. This directory is the whole web app; it never imports or
edits pipeline code.

## Data flow

```
collector pass -> commits data/ to the public repo
                        |
     api/feed.mjs reads data/ AT ONE COMMIT SHA (snapshot-consistent)
                        |
     index.html renders it, computing every age in the browser
```

- `api/_data.mjs` read layer. Resolves the newest commit touching `data/`, reads
  every file at that sha. Falls back to the branch tip if the GitHub API refuses,
  and says so. Holds the field whitelist: `score`, `grade`, `passed`, `flags`
  (the retired scorer's editorial) and `paper_v2_*` never reach a browser.
- `api/feed.mjs` one payload: collector liveness, pass history, four sections.
- `api/ca.mjs` lookup of one contract address against the last 3 days of journal,
  the month's milestones, the approach band and the quarantine list.
- `api/helius.mjs` the webhook receiver. Pre-existing, untouched.
- `honest.mjs` the honesty layer. Pure functions, shared by the page and the tests.
- Macro digest, headlines and whale events still come from Supabase in the
  browser, with the same publishable key as before.

## The honesty rule, and where it is enforced

The old dashboard printed "No clusters. That is a real answer, not a gap" during
a total outage, because each section wrote its own empty state and `[]` meant
three things. Here **a section cannot write its own empty state.** It supplies a
noun; `honest.emptySentence()` writes the sentence and needs coverage facts to
say "none found".

| state | meaning | looks like |
|---|---|---|
| Current / Late | looked within 6h / 12h | green / amber rail |
| Stale | last look over 12h ago | red rail, tiles print "stale" not a number |
| No data collected | nothing looked inside the window | red, "outage, not a quiet market" |
| Could not read | source file failed to load | red, a fault on our side |
| Cannot verify | source publishes no heartbeat (whale listener) | amber dashed |
| Not connected | data does not reach the site yet | grey dashed |

Thresholds are the pipeline's, not invented here: 6h (`dashboard.py` dimming,
runner's worst measured gap 5.5h) and 12h (`liveness.py` alarm). Collector
liveness is judged on **unattended** passes only, per `liveness.py`; a manual run
is shown but never turns the board green. `$500` is `watchlist.GRAD_MIN_DEPTH`.

A depth reading only counts toward a crossing if it was read **at or after** the
crossing. On the first build all 12 crossings joined to depth read 8 to 17 hours
earlier, which verifies nothing.

## Commands

```
node test_honest.mjs     # 2,470 checks: honesty sweep, type rules, copy lint
node dev.mjs             # http://localhost:4173, static + api handlers
DEV_FAULT=outage node dev.mjs       # collector dead 3 days
DEV_FAULT=unreadable node dev.mjs   # every source fails to read
DEV_FAULT=feeddown node dev.mjs     # /api/feed returns 500
vercel deploy --prod --yes          # from this directory
```

`test_honest.mjs` also lints the shipped files: no type under 1rem, no uppercase,
no positive letter-spacing, no em or en dash, no control or bidi characters in
source. Run it before every deploy. It has been mutation-checked: reintroducing
the original outage bug, a manual-run-goes-green bug, and a tiny uppercase tracked
label each fail it.

## Deploy notes

- The Vercel project is **not git-connected**. Deploys are CLI-driven from here.
- Preview deployments sit behind Vercel login (302), so a preview cannot be
  checked headlessly. `vercel curl` would mint a protection-bypass secret on the
  project; that was deliberately not done. Verify on production, roll back if wrong.
- Rollback: `vercel rollback` or `vercel promote <deployment>`. The last
  deployment of the old page is `crypto-intel-d38pnkauz`.
- ⚠️ Special characters must be built from code points (`String.fromCodePoint`),
  never typed as escapes through tooling. An eaten escape shipped a NUL byte into
  the CSS once and a literal U+202E into a comment once. The lint now catches both.

## What the site needs from the pipeline

See "Not connected yet" on the page. In order of value:
1. `exit_depth_at_crossing` on mcap milestone rows (graduation rows already
   carry it). Without it no tier crossing can be verified.
2. A published cluster output (e.g. `data/clusters.json` with a build timestamp).
3. Persisted D1 / D2 detector verdicts per observation.
4. `analyze(CA)` exposed as a service for the lookup box.
5. A paper v3 ledger file, once it exists.
6. A heartbeat from the whale listener, so silence can be told from failure.
