// GET /api/ca?ca=<contract> -> what the journal ALREADY RECORDED about one
// contract address. A lookup, not an analysis.
//
// ⛔ This is deliberately not check.py. The analyzer needs on-chain reads, keys
// and the detector, all of which live in the pipeline. Until that is exposed,
// the honest product is "here is what our scanner wrote down, and how old it
// is", and a plain statement when it wrote down nothing. Absence from the
// journal is never rendered as safety.
//
// Standing rule 2: keyed on the contract address. A ticker is never accepted.

import {
  snapshot, readFile, parseJson, parseJsonl, lastDays, monthsFor, fileReport,
  publicObs, BACKFILL_EPOCH,
} from "./_data.mjs";

const BASE58 = /^[1-9A-HJ-NP-Za-km-z]{32,44}$/;
const iso = (ts) => (ts ? new Date(ts * 1000).toISOString() : null);

export default async function handler(req, res) {
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  const ca = String((req.query && req.query.ca) || "").trim();
  if (!BASE58.test(ca)) {
    res.setHeader("Cache-Control", "no-store");
    res.status(400).send(JSON.stringify({
      ok: false, error: "not_an_address",
      message: "That is not a Solana address. Paste the contract address, 32 to 44 base58 characters. Tickers are not accepted, because 398 contracts in our data impersonate an existing name.",
    }));
    return;
  }

  const nowMs = Date.now();
  const snap = await snapshot();
  const obsDays = lastDays(nowMs, 3);
  const months = monthsFor(nowMs, 168);
  const [obsFs, msFs, wlF, qF] = await Promise.all([
    Promise.all(obsDays.map((d) => readFile(snap, `data/observations/${d}.jsonl`))),
    Promise.all(months.map((m) => readFile(snap, `data/milestones/${m}.jsonl`))),
    readFile(snap, "data/watchlist/active.json"),
    readFile(snap, "data/quarantine.json"),
  ]);

  const hits = [];
  let obsRows = 0;
  for (const f of obsFs) {
    for (const o of parseJsonl(f)) {
      obsRows++;
      if (o.token === ca || o.pair === ca) hits.push(o);
    }
  }
  hits.sort((a, b) => (b.ts || 0) - (a.ts || 0));

  const token = hits.length ? hits[0].token : ca;
  const milestones = [];
  for (const f of msFs) {
    for (const r of parseJsonl(f)) {
      if (r.token !== token || (r.crossed_ts || 0) <= BACKFILL_EPOCH) continue;
      milestones.push({ milestone: r.milestone, kind: r.kind, crossed_at: iso(r.crossed_ts),
                        value: r.value ?? null, real_pool: r.kind === "graduation" ? !!r.real_pool : null,
                        exit_depth_at_crossing: r.exit_depth_at_crossing ?? null });
    }
  }
  milestones.sort((a, b) => (a.crossed_at < b.crossed_at ? 1 : -1));

  const wl = parseJson(wlF);
  let watch = null;
  if (wl) {
    const m = Object.values(wl).find((x) => x.contract === token || x.pair === ca);
    if (m) watch = { fdv: m.last_fdv ?? null, peak_fdv: m.peak_fdv ?? null,
                     added_at: iso(m.added_ts), added_fdv: m.added_fdv ?? null };
  }

  const q = parseJson(qF);
  let quarantine = null;
  if (q) {
    const keys = [ca, token, hits.length ? hits[0].pair : null].filter(Boolean);
    const k = keys.find((x) => q[x]);
    if (k) quarantine = { reason: q[k].confidence || null, detail: q[k].detail || null,
                          first_at: iso(q[k].first_ts), last_at: iso(q[k].last_ts), hits: q[k].hits ?? null };
  }

  const all = [...obsFs, ...msFs, wlF, qF];
  const readErrors = all.filter((f) => !f.ok && !f.absent).map((f) => `${f.path}: ${f.error}`);

  res.setHeader("Cache-Control", "public, s-maxage=60, stale-while-revalidate=120");
  res.status(200).send(JSON.stringify({
    ok: true, ca, token, generated_at: new Date(nowMs).toISOString(), snapshot: snap,
    found: hits.length > 0 || milestones.length > 0 || !!watch || !!quarantine,
    matched_on: hits.length ? (hits[0].token === ca ? "token" : "pair") : null,
    searched: { obs_days: obsDays, obs_rows: obsRows, read_errors: readErrors,
                // If a source could not be read, "not found" is not a finding.
                complete: readErrors.length === 0 },
    sightings: hits.length,
    first_seen_at: hits.length ? iso(hits[hits.length - 1].ts) : null,
    last_seen_at: hits.length ? iso(hits[0].ts) : null,
    latest: hits.length ? publicObs(hits[0]) : null,
    milestones, watchlist: watch, quarantine,
    files: fileReport(all),
  }));
}
