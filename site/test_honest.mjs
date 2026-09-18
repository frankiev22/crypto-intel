// node test_honest.mjs   (no dependencies; exits non-zero on any failure)
//
// Guards the three things that decide whether this dashboard can be trusted:
//   1. A quiet-market sentence cannot exist without a look inside the window.
//   2. Frank's type rules: nothing under 1rem / 16px, no uppercase, no wide tracking.
//   3. No em dash or en dash in anything the site ships.
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import * as hx from "./honest.mjs";
import { publicObs } from "./api/_data.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
let failed = 0, passed = 0;
const ok = (cond, name, detail) => {
  if (cond) { passed++; return; }
  failed++; console.error(`FAIL  ${name}${detail ? "\n      " + detail : ""}`);
};

const NOW = Date.parse("2026-09-18T13:00:00Z");
const ago = (h) => new Date(NOW - h * 3600000).toISOString();
const QUIET = /^No .+ found\./;          // the only sentence that asserts "we looked, nothing there"

// Built from code points, never typed as escapes or literals: an escaping layer once
// turned a CSS escape into a NUL byte, and a literal bidi control in source is its own attack.
const cp = (...n) => String.fromCodePoint(...n);
const DASHES = new RegExp("[" + cp(0x2014, 0x2013) + "]");
const DASH_CTX = new RegExp(".{0,30}[" + cp(0x2014, 0x2013) + "].{0,30}");
const HIDDEN = new Set([0x202a, 0x202b, 0x202c, 0x202d, 0x202e, 0x2066, 0x2067, 0x2068, 0x2069, 0x200e, 0x200f, 0x200b, 0x200c, 0x200d, 0xfeff]);
const isHidden = (c) => HIDDEN.has(c) || (c < 32 && c !== 9 && c !== 10 && c !== 13) || (c >= 0x7f && c < 0xa0);
const hasHidden = (s) => [...s].some((ch) => isHidden(ch.codePointAt(0)));
const hiddenAt = (s) => { const i = [...s].findIndex((ch) => isHidden(ch.codePointAt(0))); return i < 0 ? "" : "U+" + [...s][i].codePointAt(0).toString(16) + " near: " + JSON.stringify([...s].slice(Math.max(0, i - 25), i).join("")); };

// ---- 1a. the exact regression: a total outage must not read as a quiet day ----
{
  const outage = { readable: true, error: null, as_of: ago(80), window_h: 24, coverage: { passes: 0 }, rows: [] };
  const s = hx.emptySentence(outage, "narrative clusters", NOW);
  ok(!QUIET.test(s), "outage is not rendered as a quiet market", s);
  ok(/No data collected/.test(s) && /outage, not a quiet market/.test(s), "outage says it is an outage", s);
  ok(!hx.mayShowNumber(outage, NOW), "outage tile may not print a number");
  ok(hx.stateOf(outage, NOW).kind === "blind", "outage classifies as blind");
}

// ---- 1b. sweep the input space ----------------------------------------------------
{
  let n = 0;
  for (const readable of [true, false])
  for (const asOfH of [null, 0.1, 5.9, 6.1, 11.9, 12.1, 23, 25, 47, 49, 167, 169, 500])
  for (const passes of [0, 1, 9])
  for (const windowH of [null, 24, 48, 168])
  for (const cov of [true, false]) {
    n++;
    const sec = { readable, error: readable ? null : "HTTP 500", as_of: asOfH == null ? null : ago(asOfH),
                  window_h: windowH, rows: [] };
    if (cov) sec.coverage = { passes };
    const s = hx.emptySentence(sec, "things", NOW);
    const looks = cov ? passes : 0;
    const lookedInWindow = readable && asOfH != null && (windowH == null || looks > 0 || asOfH <= windowH);
    const tag = JSON.stringify({ readable, asOfH, passes: looks, windowH });
    if (QUIET.test(s)) {
      ok(lookedInWindow, "quiet sentence requires a look inside the window", `${tag} -> ${s}`);
      ok(asOfH <= hx.DOWN_H, "quiet sentence requires a look newer than the down threshold", `${tag} -> ${s}`);
      ok(/ ago|just now/.test(s), "quiet sentence always states when it last looked", s);
    }
    ok(hx.mayShowNumber(sec, NOW) === (readable && asOfH != null && asOfH <= hx.DOWN_H && lookedInWindow),
       "a headline number needs a readable source and a look newer than the down threshold", tag);
    if (!hx.mayShowNumber(sec, NOW)) ok(!!hx.TILE_WORD[hx.stateOf(sec, NOW).kind], "every no-number state has a word to print instead", tag);
    if (!readable) ok(/Could not read/.test(s) && !hx.mayShowNumber(sec, NOW), "unreadable is a fault, never a count", `${tag} -> ${s}`);
    if (readable && asOfH == null) ok(/No data collected/.test(s) && !hx.mayShowNumber(sec, NOW), "never looked is no data", `${tag} -> ${s}`);
    ok(!DASHES.test(s), "no em or en dash in generated copy", s);
  }
  ok(n > 600, "sweep covered the space", String(n));
}

// ---- 1c. a manual run must not turn the collector green (liveness.py) ------------
{
  const c = { readable: true, last_unattended_at: ago(72), last_any_at: ago(0.1), last_origin: "manual", passes: [] };
  const st = hx.collectorState(c, NOW);
  ok(st.kind === "down", "manual run does not mask a dead scheduler", JSON.stringify(st));
  ok(/manual run/.test(st.line), "the manual run is still shown", st.line);
  ok(hx.collectorState({ readable: false, error: "x" }, NOW).kind === "unreadable", "unreadable collector");
  ok(hx.collectorState({ readable: true, last_unattended_at: null }, NOW).kind === "never", "never-run collector");
  ok(hx.collectorState({ readable: true, last_unattended_at: ago(1) }, NOW).kind === "live", "live collector");
  ok(hx.collectorState({ readable: true, last_unattended_at: ago(7) }, NOW).kind === "late", "late collector");
}

// ---- symbols: docs/SYMBOL_ATTACKS.md -------------------------------------------------
{
  const a = hx.safeSym("U" + cp(0x202e) + "CD" + cp(0x0405));      // renders as USDC in a browser
  ok(a.bidi && a.mixed && !hasHidden(a.text) && a.text === "UCD" + cp(0x0405), "bidi override stripped AND reported", JSON.stringify(a));
  ok(hx.safeSym(cp(0x202e) + "EKOP").bidi, "second live attack string flagged");
  const c = hx.safeSym("USDC");
  ok(!c.bidi && !c.mixed && c.text === "USDC", "clean symbol passes clean");
  ok(hx.safeSym(null).unknown && hx.safeSym("").unknown, "missing symbol is unknown");
  ok(hx.safeSym(cp(0x200b, 0x200b)).unknown, "symbol of only hidden characters is unknown, not blank");
  ok(hx.esc('<img src=x onerror="1">') === "&lt;img src=x onerror=&quot;1&quot;&gt;", "html escaped");
}

// ---- numbers: unknown is never zero ----------------------------------------------------
{
  ok(hx.usd(null) === null && hx.usd(undefined) === null && hx.usd("") === null, "unmeasured is null, caller prints unknown");
  ok(hx.usd(0) === "$0", "measured zero is $0");
  ok(hx.usd(3.17e-7) === "<$0.0001", "sub-cent reading is a bound, not $0.0000");
  ok(hx.usd(-5) === null, "negative depth is a bug, not a reading");
  ok(hx.usd(58424.05) === "$58k" && hx.usd(1234.5) === "$1,235" && hx.usd(2.5e6) === "$2.50M", "scales");
  ok(hx.roundTrip(null) === null && hx.roundTrip(0) === null, "round trip unknown without depth");
  ok(Math.abs(hx.roundTrip(58424.05) - 0.8417) < 0.01, "round trip matches dashboard.round_trip", String(hx.roundTrip(58424.05)));
  ok(hx.roundTripClass(hx.roundTrip(1.43)) === "worst", "a drained pool is the worst class");
}

// ---- the browser never receives scorer output ------------------------------------------------
{
  const out = publicObs({ token: "t", symbol: "X", score: 100, grade: "A", grade_label: "clean", passed: true,
                          weights_version: 1, paper_v2_arm: "a", paper_v2_entry: true, reasons: ["r"], flags: ["move likely already happened"] });
  for (const k of ["score", "grade", "grade_label", "passed", "weights_version", "paper_v2_arm", "paper_v2_entry", "reasons", "flags"]) {
    ok(!(k in out), `publicObs never emits ${k}`);
  }
  ok(out.token === "t" && out.exit_depth_usd === null, "absent measurements leave as null, never 0");
}

// ---- 2 and 3: lint every shipped file -----------------------------------------------------
{
  const shipped = ["index.html", "honest.mjs", ...readdirSync(join(HERE, "api")).map((f) => "api/" + f)];
  for (const f of shipped) {
    const src = readFileSync(join(HERE, f), "utf8");
    ok(!hasHidden(src), `${f}: no control, bidi or zero width characters in shipped source`, hiddenAt(src));
    const dash = src.match(DASH_CTX);
    ok(!dash, `${f}: no em or en dash`, dash && dash[0]);
    ok(!/"(score|grade|grade_label|weights_version)"/.test(src.replace(/\/\/.*$/gm, "")), `${f}: score fields are never read`);
  }
  const html = readFileSync(join(HERE, "index.html"), "utf8");
  const css = html.slice(html.indexOf("<style>"), html.indexOf("</style>"));
  ok(!/text-transform\s*:\s*uppercase/i.test(css) && !/font-variant(-caps)?\s*:\s*[a-z-]*small-caps/i.test(css), "no uppercase or small caps");
  for (const m of css.matchAll(/letter-spacing\s*:\s*([^;}]+)/g)) {
    ok(parseFloat(m[1]) <= 0, "no positive letter-spacing", m[0]);
  }
  ok(/html\{font-size:106\.25%/.test(css), "root size is 17px at default settings");
  for (const m of [...css.matchAll(/font-size\s*:\s*([\d.]+)(rem|px|em|%)/g), ...html.matchAll(/style="[^"]*font-size\s*:\s*([\d.]+)(rem|px|em|%)/g)]) {
    const v = parseFloat(m[1]), u = m[2];
    const good = u === "rem" || u === "em" ? v >= 1 : u === "px" ? v >= 16 : v >= 100;
    ok(good, "no type below 1rem / 16px", m[0]);
  }
  ok(!/<small|<sup|<sub/i.test(html), "no small, sup or sub elements");
  ok(!/scoreboard|score_bands|lift/i.test(html), "the score band scoreboard is gone from the page");
}

console.log(`${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
