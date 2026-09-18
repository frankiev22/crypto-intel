// Shared read layer for the dashboard. Underscore prefix: Vercel does not route it.
//
// WHERE THE DATA COMES FROM. The pipeline's state store is git: `data/` is
// committed after every collector pass, and the repo is public. So the site
// reads the pipeline's own files over HTTPS and never touches the pipeline.
// Nothing here is a secret and nothing here is newly public.
//
// SNAPSHOT-CONSISTENT READS. We resolve the newest commit that touched data/
// and read every file AT THAT SHA. Reading the branch tip file by file can tear:
// liveness.json from one pass and milestones from the next. A sha cannot.
// If the GitHub API refuses (60 req/h unauthenticated, shared egress IPs), we
// fall back to the branch and SAY SO in the response.
//
// THIS LAYER SELECTS AND JOINS. IT NEVER JUDGES. No detector, no clustering and
// no scoring is reimplemented here: that logic lives in the pipeline, and a
// second copy in JS would drift. `score`, `grade` and `passed` are never read.

const OWNER = "frankiev22";
const REPO = "crypto-intel";
const BRANCH = "master";

// Standing rule 12: Cloudflare-fronted hosts reject default agents with a bare
// 403 that looks like an auth failure. GitHub's API requires one outright.
const UA = "crypto-intel-site/1.0 (+https://crypto-intel-one-eta.vercel.app)";

// milestones.py BACKFILL_EPOCH, 2026-09-02 05:00Z. Crossings at or before this
// are a one-minute replay of history, not detections. Mirrors the pipeline.
export const BACKFILL_EPOCH = Date.UTC(2026, 8, 2, 5, 0, 0) / 1000;

// watchlist.GRAD_MIN_DEPTH. The pipeline's own floor for calling a pool real.
// Reused, not invented: the site sets no thresholds of its own.
export const REAL_POOL_MIN_DEPTH_USD = 500;

const warm = { sha: null, files: new Map(), snapAt: 0, snap: null };

async function get(url, accept) {
  try {
    const r = await fetch(url, {
      headers: { "User-Agent": UA, ...(accept ? { Accept: accept } : {}) },
      signal: AbortSignal.timeout(9000),
    });
    const text = r.ok ? await r.text() : "";
    return { ok: r.ok, status: r.status, text, bytes: text.length };
  } catch (e) {
    return { ok: false, status: 0, text: "", bytes: 0, error: String(e && e.name || e) };
  }
}

export async function snapshot() {
  // One API call per 45s per warm lambda, at most.
  if (warm.snap && Date.now() - warm.snapAt < 45000) return warm.snap;
  const r = await get(
    `https://api.github.com/repos/${OWNER}/${REPO}/commits?path=data&per_page=1&sha=${BRANCH}`,
    "application/vnd.github+json");
  let snap;
  try {
    const c = JSON.parse(r.text)[0];
    snap = { mode: "commit", ref: c.sha, sha: c.sha, committed_at: c.commit.committer.date };
  } catch {
    snap = {
      mode: "branch", ref: BRANCH, sha: null, committed_at: null,
      note: `GitHub API unavailable (HTTP ${r.status}); read the branch tip, files may be from different passes`,
    };
  }
  warm.snap = snap; warm.snapAt = Date.now();
  if (snap.sha !== warm.sha) { warm.sha = snap.sha; warm.files.clear(); }
  return snap;
}

// Never throws. `absent` (404) is a fact about the repo; any other failure is
// a read error. The two are reported differently all the way to the screen.
export async function readFile(snap, path) {
  const key = `${snap.ref}:${path}`;
  if (snap.sha && warm.files.has(key)) return warm.files.get(key);
  const r = await get(`https://raw.githubusercontent.com/${OWNER}/${REPO}/${snap.ref}/${path}`);
  const out = {
    path, ok: r.ok, status: r.status, bytes: r.bytes,
    absent: r.status === 404, error: r.ok ? null : (r.error || `HTTP ${r.status}`),
    text: r.text,
  };
  if (snap.sha && (r.ok || out.absent)) warm.files.set(key, out);
  return out;
}

export function parseJson(f) {
  if (!f.ok) return null;
  try { return JSON.parse(f.text); } catch { f.ok = false; f.error = "invalid JSON"; return null; }
}

export function parseJsonl(f) {
  if (!f.ok) return [];
  const rows = [];
  let bad = 0;
  for (const line of f.text.split("\n")) {
    const s = line.trim();
    if (!s) continue;
    try { rows.push(JSON.parse(s)); } catch { bad++; }
  }
  f.bad_lines = bad;
  return rows;
}

export const utcDay = (ms) => new Date(ms).toISOString().slice(0, 10);
export const utcMonth = (ms) => new Date(ms).toISOString().slice(0, 7);

export function lastDays(nowMs, n) {
  const out = [];
  for (let i = 0; i < n; i++) out.push(utcDay(nowMs - i * 86400000));
  return out;
}

// Months a window touches, newest first. A 7-day window on the 3rd needs two.
export function monthsFor(nowMs, windowH) {
  const a = utcMonth(nowMs), b = utcMonth(nowMs - windowH * 3600000);
  return a === b ? [a] : [a, b];
}

export function fileReport(files) {
  const rep = {};
  for (const f of files) {
    rep[f.path] = { ok: f.ok, status: f.status, bytes: f.bytes, absent: f.absent,
                    error: f.error, bad_lines: f.bad_lines || 0 };
  }
  return rep;
}

// What an observation row is allowed to say to the browser. A whitelist, the
// same discipline as journal.record(): a field not listed here does not leave.
// ⛔ score, grade, grade_label, passed, weights_version and paper_v2_* are
// deliberately absent. See CLAUDE.md, "What this is NOT".
const OBS_FIELDS = [
  "token", "pair", "symbol", "ts", "network", "dex_id", "venue_type", "has_amm_pool",
  "fdv", "liq", "liq_quote", "exit_depth_usd", "price_usd", "age_hours",
  "vol_h1", "vol_h24", "txns_h1", "buys_h1", "sells_h1", "chg_h1", "chg_h24",
  "can_mint", "can_freeze", "authorities_checked", "authorities_error",
  "integrity_flags", "impersonation", "template_suspect", "liquidity_plausible",
  "has_twitter", "has_telegram", "has_website", "flags",
];

export function publicObs(o) {
  const out = {};
  for (const k of OBS_FIELDS) out[k] = o[k] === undefined ? null : o[k];
  return out;
}

// Newest observation per token, plus sighting counts. `ts` is PER BATCH, not per
// token (standing rule 13), so it dates the pass that saw the row, nothing finer.
export function indexObs(rows) {
  const latest = new Map();
  const seen = new Map();
  for (const o of rows) {
    if (!o || !o.token) continue;
    const t = o.ts || 0;
    const s = seen.get(o.token) || { n: 0, first: t, last: t };
    s.n++; s.first = Math.min(s.first, t); s.last = Math.max(s.last, t);
    seen.set(o.token, s);
    const cur = latest.get(o.token);
    if (!cur || t > (cur.ts || 0)) latest.set(o.token, o);
  }
  return { latest, seen };
}
