// GET /api/feed -> everything the dashboard renders from the pipeline, in one
// snapshot-consistent read.
//
// ⛔ THE CONTRACT THAT MATTERS. This endpoint never says "nothing happened".
// It reports, per section: whether the source could be READ, when the pipeline
// last LOOKED (as_of), how many passes covered the window, and the rows. The
// browser decides what sentence to print from those facts at view time, against
// its own clock. An empty `rows` with no coverage is an outage, and the payload
// carries enough to tell it apart from a quiet market. See index.html, stateOf().

import {
  snapshot, readFile, parseJson, parseJsonl, lastDays, monthsFor, fileReport,
  publicObs, indexObs, BACKFILL_EPOCH, REAL_POOL_MIN_DEPTH_USD,
} from "./_data.mjs";

const H = 3600;
const WINDOWS = { graduated_h: 168, crossings_h: 24, flags_h: 48 };

const iso = (ts) => (ts ? new Date(ts * 1000).toISOString() : null);
const toTs = (s) => { const t = Date.parse(s || ""); return Number.isFinite(t) ? t / 1000 : null; };

function sig(live, name) {
  const s = (live && live[name]) || null;
  if (!s) return { known: false, last_ts: null, last_unattended_ts: null, last_origin: null };
  return {
    known: true,
    last_ts: s.last_ts || toTs(s.last_at),
    last_unattended_ts: s.last_unattended_ts || toTs(s.last_unattended_at),
    last_origin: s.last_origin || null,
  };
}

export default async function handler(req, res) {
  const nowMs = Date.now();
  const now = nowMs / 1000;
  const snap = await snapshot();

  const covDays = lastDays(nowMs, 8);   // a 7-day window touches up to 8 UTC dates
  const obsDays = lastDays(nowMs, 3);   // a 48-hour window touches up to 3
  const months = monthsFor(nowMs, WINDOWS.graduated_h);

  const [liveF, wlF, covFs, obsFs, msFs] = await Promise.all([
    readFile(snap, "data/liveness.json"),
    readFile(snap, "data/watchlist/active.json"),
    Promise.all(covDays.map((d) => readFile(snap, `data/coverage/${d}.jsonl`))),
    Promise.all(obsDays.map((d) => readFile(snap, `data/observations/${d}.jsonl`))),
    Promise.all(months.map((m) => readFile(snap, `data/milestones/${m}.jsonl`))),
  ]);

  // A day with no passes has no file. That is a fact (zero passes), not an
  // error. Anything else that is not ok IS an error and poisons the section.
  const hardFail = (fs) => fs.filter((f) => !f.ok && !f.absent);

  // ---- collector --------------------------------------------------------
  const live = parseJson(liveF);
  const passes = [];
  for (const f of covFs) {
    for (const r of parseJsonl(f)) {
      if ((r.kind === "pass_complete" || r.kind === "pass_short")
          && (r.stage === "scan" || r.stage === "full") && r.ts) {
        passes.push({ ts: r.ts, stage: r.stage, complete: r.kind === "pass_complete",
                      origin: r.origin || null });
      }
    }
  }
  passes.sort((a, b) => b.ts - a.ts);
  const scan = sig(live, "scan.observations");
  const sweep = sig(live, "watchlist.sweep");
  const collector = {
    readable: !!live && hardFail(covFs).length === 0,
    error: live ? (hardFail(covFs)[0] || {}).error || null : (liveF.error || "liveness.json unreadable"),
    // liveness.py: staleness is judged ONLY on unattended beats. A manual run
    // that turns the board green is the quiet-period failure one level up.
    last_unattended_at: iso(scan.last_unattended_ts),
    last_any_at: iso(scan.last_ts),
    last_origin: scan.last_origin,
    passes: passes.slice(0, 80).map((p) => ({ ...p, at: iso(p.ts) })),
  };
  const coverage = (windowH, stage) => {
    const lo = now - windowH * H;
    const inWin = passes.filter((p) => p.ts > lo && (!stage || p.stage === stage));
    return { passes: inWin.length, complete: inWin.filter((p) => p.complete).length,
             newest_at: inWin.length ? iso(inWin[0].ts) : null };
  };

  // ---- observations index (joins only) ----------------------------------
  const obsRows = [];
  for (const f of obsFs) for (const o of parseJsonl(f)) obsRows.push(o);
  const { latest, seen } = indexObs(obsRows);
  const obsBroken = hardFail(obsFs);
  const joinDepth = (token) => {
    const o = latest.get(token);
    if (!o) return { exit_depth_usd: null, depth_at: null, fdv_now: null, liq_reported: null,
                     integrity_flags: null, impersonation: null, joined: false };
    return { exit_depth_usd: o.exit_depth_usd ?? null, depth_at: iso(o.ts), fdv_now: o.fdv ?? null,
             liq_reported: o.liq ?? null, integrity_flags: o.integrity_flags || [],
             impersonation: o.impersonation || [], joined: true };
  };

  // ---- milestones ---------------------------------------------------------
  const msRows = [];
  for (const f of msFs) for (const r of parseJsonl(f)) msRows.push(r);
  const msBroken = hardFail(msFs);
  const msAllAbsent = msFs.every((f) => f.absent);
  const liveMs = msRows.filter((r) => (r.crossed_ts || 0) > BACKFILL_EPOCH);

  // graduated: watchlist milestone crossings, split the way dashboard.py splits
  // them. real_pool is the PIPELINE's verdict; the site does not second-guess it.
  const gLo = now - WINDOWS.graduated_h * H;
  const grads = liveMs.filter((r) => r.kind === "graduation" && (r.crossed_ts || 0) > gLo)
    .sort((a, b) => b.crossed_ts - a.crossed_ts);
  const gradRow = (r) => ({
    token: r.token, symbol: r.symbol, crossed_at: iso(r.crossed_ts), venue: r.venue || null,
    fdv_at_crossing: r.fdv_at_crossing ?? r.value ?? null,
    exit_depth_at_crossing: r.exit_depth_at_crossing ?? null,
    hours_in_band: r.hours_in_band ?? null, real_pool: !!r.real_pool, ...joinDepth(r.token),
  });
  const graduated = {
    readable: msBroken.length === 0 && !msAllAbsent,
    error: msBroken.length ? msBroken[0].error : (msAllAbsent ? "no milestones file for this period" : null),
    window_h: WINDOWS.graduated_h,
    as_of: iso(sweep.last_ts),
    coverage: coverage(WINDOWS.graduated_h, "full"),
    rows: grads.filter((r) => r.real_pool).slice(0, 20).map(gradRow),
    fdv_only: grads.filter((r) => !r.real_pool).slice(0, 12).map(gradRow),
    fdv_only_n: grads.filter((r) => !r.real_pool).length,
  };

  // crossings: raw FDV tier crossings, one row per contract at its highest tier.
  // ⛔ Raw. Only 25.4% [22.3, 28.8] of $1M crossings survive an integrity
  // screen (TRACKER_SCOPING §2), so every row carries the measured exit depth
  // and the headline count is the depth-gated one, never the raw one.
  const TIER = { mcap_100k: 1e5, mcap_200k: 2e5, mcap_1m: 1e6, mcap_5m: 5e6 };
  const cLo = now - WINDOWS.crossings_h * H;
  const byToken = new Map();
  for (const r of liveMs) {
    if (r.kind !== "mcap" || (r.crossed_ts || 0) <= cLo || !TIER[r.milestone]) continue;
    const cur = byToken.get(r.token);
    if (!cur || TIER[r.milestone] > TIER[cur.milestone]) byToken.set(r.token, r);
  }
  // ⛔ A DEPTH READ BEFORE THE CROSSING VERIFIES NOTHING. Measured on the first
  // build, 2026-09-18: all 12 crossings in the window joined to a depth reading
  // taken 7.8 to 16.7 HOURS EARLIER, because mcap tiers are claimed on the
  // horizon re-check and no new observation row is written. A pool that was deep
  // at breakfast and drained by lunch is exactly the phantom crossing (standing
  // rule 4), so an old reading must never be allowed to bless a new price.
  // `remeasured` is true only when the depth was read AT OR AFTER the crossing.
  // No tolerance, so no threshold of ours is involved.
  const crossRows = [...byToken.values()].sort((a, b) => b.crossed_ts - a.crossed_ts).map((r) => {
    const j = joinDepth(r.token);
    const o = latest.get(r.token);
    const remeasured = !!o && (o.ts || 0) >= r.crossed_ts;
    return { token: r.token, symbol: r.symbol, tier_usd: TIER[r.milestone],
             crossed_at: iso(r.crossed_ts), fdv_at_crossing: r.value ?? null, ...j,
             remeasured,
             has_exit: remeasured && j.exit_depth_usd != null
                       && j.exit_depth_usd >= REAL_POOL_MIN_DEPTH_USD };
  });
  const crossings = {
    readable: msBroken.length === 0 && !msAllAbsent,
    error: graduated.error,
    join_readable: obsBroken.length === 0,
    window_h: WINDOWS.crossings_h,
    as_of: iso(scan.last_ts),
    coverage: coverage(WINDOWS.crossings_h),
    min_exit_depth_usd: REAL_POOL_MIN_DEPTH_USD,
    rows: crossRows.slice(0, 40),
    raw_n: crossRows.length,
    remeasured_n: crossRows.filter((r) => r.remeasured).length,
    with_exit_n: crossRows.filter((r) => r.has_exit).length,
    over_1m_raw_n: crossRows.filter((r) => r.tier_usd >= 1e6).length,
    over_1m_with_exit_n: crossRows.filter((r) => r.tier_usd >= 1e6 && r.has_exit).length,
  };

  // ---- approaching --------------------------------------------------------
  const wl = parseJson(wlF);
  const wlRows = wl ? Object.values(wl).map((m) => ({
    token: m.contract, pair: m.pair || null, symbol: m.symbol,
    fdv: m.last_fdv ?? null, peak_fdv: m.peak_fdv ?? null, added_fdv: m.added_fdv ?? null,
    added_at: iso(m.added_ts), vol_h1: m.last_vol_h1 ?? null,
    checks: Array.isArray(m.checks) ? m.checks.length : (m.checks ?? null),
    ...joinDepth(m.contract),
  })).sort((a, b) => (b.fdv || 0) - (a.fdv || 0)) : [];
  const approaching = {
    readable: !!wl, error: wl ? null : (wlF.error || "watchlist unreadable"),
    window_h: null,                       // a standing list, not a window
    as_of: iso(sweep.last_ts),
    coverage: coverage(24, "full"),
    band: { lo: 45000, hi: 69000 },       // watchlist.BAND_LO / BAND_HI defaults
    rows: wlRows.slice(0, 30), total_n: wlRows.length,
  };

  // ---- integrity flags ------------------------------------------------------
  // Only what the scanner PERSISTS on each row. detector.d1/d2 run inside the
  // pipeline at build time and are not published, so they are not claimed here.
  const fLo = now - WINDOWS.flags_h * H;
  const flagged = [];
  for (const o of latest.values()) {
    if ((o.ts || 0) <= fLo) continue;
    const why = [...(o.integrity_flags || []), ...(o.impersonation || [])];
    if (o.template_suspect) why.push("template_suspect");
    if (why.length) flagged.push({ ...publicObs(o), why, seen_at: iso(o.ts) });
  }
  flagged.sort((a, b) => (b.ts || 0) - (a.ts || 0));
  const obsInWin = [...latest.values()].filter((o) => (o.ts || 0) > fLo).length;
  const flags = {
    readable: obsBroken.length === 0 && !obsFs.every((f) => f.absent),
    error: obsBroken.length ? obsBroken[0].error
      : (obsFs.every((f) => f.absent) ? "no observation files for the last 3 days" : null),
    window_h: WINDOWS.flags_h,
    as_of: iso(scan.last_ts),
    coverage: coverage(WINDOWS.flags_h),
    contracts_examined: obsInWin,
    rows: flagged.slice(0, 40), total_n: flagged.length,
  };

  const body = {
    generated_at: new Date(nowMs).toISOString(),
    snapshot: snap,
    collector,
    sections: { graduated, crossings, approaching, flags },
    journal: { obs_days: obsDays, obs_rows: obsRows.length, contracts: seen.size },
    files: fileReport([liveF, wlF, ...covFs, ...obsFs, ...msFs]),
  };

  // Short edge cache. The browser computes every age from timestamps against
  // its own clock, so a cached payload still ages honestly on screen.
  res.setHeader("Cache-Control", "public, s-maxage=60, stale-while-revalidate=120");
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.status(200).send(JSON.stringify(body));
}
