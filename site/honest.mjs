// The honesty layer. Pure functions, no DOM, imported by index.html and by
// test_honest.mjs.
//
// ⛔ WHY THIS FILE EXISTS. The previous dashboard printed "No multi-name
// narrative clusters in the last 24h. That is a real answer, not a gap" during a
// total outage. It could do that because every section wrote its own empty
// state, and `[]` meant three different things: the section crashed, nobody
// looked, or somebody looked and found nothing.
//
// Here a section CANNOT write its own empty state. It supplies a noun. The
// sentence comes from emptySentence(), which needs coverage facts to say
// "none found" and otherwise says what is actually true: unreadable, never
// looked, or blind. test_honest.mjs sweeps the input space and fails the build
// if a quiet-market sentence can be produced without a look inside the window.

const H = 3600000;

// Borrowed from the pipeline, not invented here.
//   LATE_H 6  : dashboard.py dims rows past 6h, and the runner's worst measured
//               gap was 5.5h (liveness.py, 46 intervals to 2026-09-07).
//   DOWN_H 12 : liveness.py's measured per-pass alarm threshold.
export const LATE_H = 6;
export const DOWN_H = 12;

export function ageMs(iso, nowMs) {
  const t = Date.parse(iso || "");
  return Number.isFinite(t) ? Math.max(0, nowMs - t) : null;
}

export function ageText(iso, nowMs) {
  const a = ageMs(iso, nowMs);
  if (a == null) return "never";
  const m = a / 60000;
  if (m < 1) return "just now";
  if (m < 90) return `${Math.round(m)} min ago`;
  const h = m / 60;
  if (h < 48) return `${h.toFixed(1)}h ago`;
  return `${(h / 24).toFixed(1)} days ago`;
}

export function spanText(hours) {
  if (hours == null) return "";
  if (hours % 24 === 0 && hours >= 48) return `${hours / 24} days`;
  return `${hours}h`;
}

// kind: unreadable | never | blind | down | late | live
//   unreadable  the source could not be read. A fault, not a finding.
//   never       readable, but the pipeline has never reported looking.
//   blind       a window is defined and nothing looked inside it.
//   down/late   the pipeline looked, but too long ago to describe now.
//   live        looked recently enough.
export function stateOf(sec, nowMs) {
  if (!sec) return { kind: "unreadable", reason: "the feed did not include this section" };
  if (!sec.readable) return { kind: "unreadable", reason: sec.error || "source unreadable" };
  // A source with its own cadence may declare tighter thresholds (the cloud
  // digest runs every 30 min, so 6h of grace would call a dead digest current).
  const lateH = sec.late_h ?? LATE_H, downH = sec.down_h ?? DOWN_H;
  const age = ageMs(sec.as_of, nowMs);
  if (age == null) return { kind: "never", reason: null };
  const looks = (sec.coverage && sec.coverage.passes) || 0;
  if (sec.window_h != null && looks === 0 && age > sec.window_h * H) {
    return { kind: "blind", age, looks: 0 };
  }
  const kind = age > downH * H ? "down" : age > lateH * H ? "late" : "live";
  return { kind, age, looks };
}

export const RAIL = { live: "ok", late: "late", down: "down", blind: "down",
                      never: "down", unreadable: "down", off: "off", unverifiable: "late" };

export const STATE_WORD = {
  live: "Current", late: "Late", down: "Stale", blind: "No data collected",
  never: "No data collected", unreadable: "Could not read", off: "Not connected",
  unverifiable: "Cannot verify",
};

// The ONLY source of empty-state copy on the site.
export function emptySentence(sec, noun, nowMs) {
  const st = stateOf(sec, nowMs);
  const when = ageText(sec && sec.as_of, nowMs);
  const win = sec && sec.window_h != null ? spanText(sec.window_h) : null;
  switch (st.kind) {
    case "unreadable":
      return `Could not read this data (${st.reason}). That is a fault on our side. It says nothing about the market.`;
    case "never":
      return "No data collected. The pipeline has never reported looking at this.";
    case "blind":
      return `No data collected. Nothing looked at the market in the last ${win}. The last look was ${when}. This is an outage, not a quiet market.`;
    case "down":
      return `No ${noun} on record, but the pipeline last looked ${when}. That is too old to say anything about now.`;
    default: {
      const n = st.looks;
      const looked = win
        ? (n > 0 ? `Looked ${n} time${n === 1 ? "" : "s"} in the last ${win}, most recently ${when}.`
                 : `Looked most recently ${when}.`)
        : `Checked ${when}.`;
      const late = st.kind === "late" ? " That is later than normal." : "";
      return `No ${noun} found. ${looked}${late}`;
    }
  }
}

// May a HEADLINE number be shown for this section? If not, the tile prints words.
// "down" is excluded on purpose: a dimmed 0 from three days ago still reads as
// zero at a glance, and the glance is the whole job of a tile. Rows inside a
// stale section are different, because each row prints its own age.
export function mayShowNumber(sec, nowMs) {
  const k = stateOf(sec, nowMs).kind;
  return k === "live" || k === "late";
}

export const TILE_WORD = { down: "stale", blind: "no data", never: "no data", unreadable: "unreadable" };

// Collector liveness. liveness.py: judged ONLY on unattended beats, because a
// manual run that turns the board green hides a dead scheduler.
export function collectorState(c, nowMs) {
  if (!c || !c.readable) {
    return { kind: "unreadable", word: "Could not read collector state",
             line: (c && c.error) || "liveness data unavailable" };
  }
  const age = ageMs(c.last_unattended_at, nowMs);
  if (age == null) {
    return { kind: "never", word: "No unattended pass on record",
             line: "The scheduled collector has never reported a pass." };
  }
  const kind = age > DOWN_H * H ? "down" : age > LATE_H * H ? "late" : "live";
  const word = { live: "Collecting", late: "Collector is late", down: "Collector is down" }[kind];
  let line = `Last unattended pass ${ageText(c.last_unattended_at, nowMs)}.`;
  const manualNewer = c.last_any_at && c.last_origin === "manual"
    && Date.parse(c.last_any_at) > Date.parse(c.last_unattended_at);
  if (manualNewer) line += ` Newest data is from a manual run ${ageText(c.last_any_at, nowMs)}.`;
  return { kind, word, line, age };
}

export function passesIn(c, hours, nowMs) {
  const lo = nowMs - hours * H;
  return ((c && c.passes) || []).filter((p) => p.ts * 1000 > lo).length;
}

// ---- symbols are hostile input ---------------------------------------------
// Port of dashboard.safe_sym(). Escaping is not enough: U, then U+202E (right to left
// override), then CD, then U+0405 (Cyrillic dze) renders as "USDC" in a browser.
// Controls are stripped AND reported, never
// silently dropped. Mixed alphabets are flagged. docs/SYMBOL_ATTACKS.md.
const BIDI = new Set([0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x2066, 0x2067, 0x2068,
                      0x2069, 0x200E, 0x200F, 0x200B, 0x200C, 0x200D, 0xFEFF]);

function scriptOf(cp) {
  if (cp >= 0x0400 && cp <= 0x04FF) return "Cyrillic";
  if (cp >= 0x0370 && cp <= 0x03FF) return "Greek";
  if ((cp >= 0x41 && cp <= 0x5A) || (cp >= 0x61 && cp <= 0x7A)) return "Latin";
  return null;
}

export function safeSym(sym) {
  const raw = sym == null ? "" : String(sym);
  if (!raw) return { text: "unknown", bidi: false, mixed: false, scripts: [], unknown: true };
  const kept = [];
  let bidi = false;
  for (const ch of raw) {
    if (BIDI.has(ch.codePointAt(0))) { bidi = true; continue; }
    kept.push(ch);
  }
  const scripts = [...new Set(kept.map((c) => scriptOf(c.codePointAt(0))).filter(Boolean))].sort();
  const text = kept.slice(0, 22).join("");
  return { text: text || "unknown", bidi, mixed: scripts.length > 1, scripts, unknown: !text };
}

// ---- numbers ------------------------------------------------------------------
// Port of dashboard.usd(). A measured zero and an unmeasured value must never
// look alike: null is "unknown", 0 is "$0", a sub-cent reading is a bound.
export function usd(v) {
  if (v == null || v === "" || !Number.isFinite(Number(v))) return null;   // caller prints "unknown"
  const n = Number(v);
  if (n < 0) return null;
  if (n === 0) return "$0";
  if (n < 0.0001) return "<$0.0001";
  if (n >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
  if (n >= 1e4) return `$${Math.round(n / 1e3).toLocaleString("en-US")}k`;
  if (n >= 1000) return `$${Math.round(n).toLocaleString("en-US")}`;
  if (n >= 1) return `$${n.toFixed(2)}`;
  return `$${n.toFixed(4)}`;
}

// Port of dashboard.round_trip(): cost to enter and leave at $100, percent.
// Constant-product impact both ways plus a 0.25% pool fee each way.
export function roundTrip(depth) {
  const d = Number(depth);
  if (depth == null || !Number.isFinite(d) || d <= 0) return null;
  return 100 * ((100 / (d + 100)) * 2 + 2 * 0.0025);
}

export function roundTripClass(rt) {
  if (rt == null) return "unk";
  return rt < 2 ? "good" : rt < 5 ? "ok" : rt < 20 ? "bad" : "worst";
}

export function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
