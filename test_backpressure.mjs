// Runs the receiver's REAL backpressure module (not a copy of it) and asserts on
// its behaviour. Driven by test_backpressure.py so run_tests.py covers it.
//
// ⛔ WHY A NODE TEST AT ALL. The receiver is a Deno edge function and there is no
// Deno on this disk, so until now nothing in this repo could execute a single
// line of it: every "fix" to that file was verified by reading it. That is the
// exact habit standing rule 16 exists to break. backpressure.ts is deliberately
// pure - no Deno, no fetch, no globals - so node's type stripping can import and
// run it unchanged.
import {
  Breaker,
  classifyFailure,
  dropLogLine,
  httpStatusFor,
  retryDelayMs,
  BREAKER_TRIP,
  BREAKER_COOLDOWN_MS,
  RETRY_BASE_MS,
  RETRY_JITTER_MS,
} from "./supabase/functions/helius-events/backpressure.ts";

let pass = 0;
const fails = [];
function t(name, ok, detail = "") {
  if (ok) {
    pass += 1;
    console.log("  PASS  " + name + (detail ? "  [" + detail + "]" : ""));
  } else {
    fails.push(name + (detail ? "  [" + detail + "]" : ""));
    console.log("  FAIL  " + name + (detail ? "  [" + detail + "]" : ""));
  }
}

console.log("=".repeat(72));
console.log("1. the invariant the outage was caused by: NEVER 5xx on a write failure");
console.log("=".repeat(72));

for (const k of ["congestion", "privilege", "payload", "duplicate", "breaker_open"]) {
  t("⛔ httpStatusFor(" + k + ") is 200, so Helius does not redeliver",
    httpStatusFor(k) === 200, String(httpStatusFor(k)));
}

console.log("=".repeat(72));
console.log("2. classification asks 'can retrying help', not 'whose fault is it'");
console.log("=".repeat(72));

t("⛔ 403 is a PRIVILEGE failure, not congestion - the old code called it ours "
  + "and answered 500, and a 403 retried forever is pure amplification",
  classifyFailure(403) === "privilege", classifyFailure(403));
t("⛔ 401 is a privilege failure too", classifyFailure(401) === "privilege");
for (const s of [500, 502, 503, 504, 599]) {
  t("⭐ " + s + " is congestion", classifyFailure(s) === "congestion");
}
t("⭐ 429 is congestion (rate limited IS the burst problem)",
  classifyFailure(429) === "congestion");
t("⭐ 408 is congestion", classifyFailure(408) === "congestion");
for (const s of [400, 422]) {
  t("⭐ " + s + " is a payload failure - retrying a bad row can never work",
    classifyFailure(s) === "payload", classifyFailure(s));
}

// ⛔⛔ FOUND BY REPLAYING 248 REAL BATCHES AT THE LIVE RECEIVER, 2026-09-23.
// Every one came back 409 "duplicate key value violates unique constraint
// chain_events_sig_uniq", and every one was logged as chain_events_drop. The
// committed comment claimed `resolution=ignore-duplicates` made a retry a no-op.
// It did not: PostgREST emits ON CONFLICT against the PRIMARY KEY and the
// conflict is a separate unique index on `signature`. The insert now names the
// target with `?on_conflict=signature`, and this classification is the guard.
t("⛔⛔ 409 is a DUPLICATE, not a payload failure - the signature is already "
  + "stored, so nothing was lost and nothing may be reported as lost",
  classifyFailure(409) === "duplicate", classifyFailure(409));
t("⛔ and SQLSTATE 23505 in the body is a duplicate whatever the status says",
  classifyFailure(400, '{\"code\":\"23505\",\"message\":\"duplicate key\"}')
  === "duplicate");
t("⭐ a plain 400 with no 23505 is still a payload failure",
  classifyFailure(400, '{\"code\":\"22P02\"}') === "payload");
t("⛔ a 5xx that happens to mention 23505 is still CONGESTION - the database "
  + "being unwell outranks the body text",
  classifyFailure(503, "23505") === "congestion");

console.log("=".repeat(72));
console.log("3. the breaker: it OPENS, it SKIPS the database entirely, it CLOSES");
console.log("=".repeat(72));

{
  const b = new Breaker();
  const t0 = 1_000_000;
  t("⭐ a fresh breaker is closed", b.isOpen(t0) === false);
  for (let i = 1; i < BREAKER_TRIP; i++) {
    b.recordCongestion(t0);
    t("⭐ still closed after " + i + " of " + BREAKER_TRIP
      + " congestion failures - it does not trip on one unlucky request",
      b.isOpen(t0) === false);
  }
  b.recordCongestion(t0);
  t("⛔ OPEN at exactly " + BREAKER_TRIP + " consecutive congestion failures",
    b.isOpen(t0) === true);
  t("⭐ and it reports how long is left, so the answer is never a bare refusal",
    b.cooldownRemainingMs(t0) === BREAKER_COOLDOWN_MS,
    String(b.cooldownRemainingMs(t0)));
  t("⭐ still open one ms before the cooldown expires",
    b.isOpen(t0 + BREAKER_COOLDOWN_MS - 1) === true);
  t("⭐ closed the moment the cooldown is served",
    b.isOpen(t0 + BREAKER_COOLDOWN_MS) === false);
}

{
  // ⛔ The re-open case. After a served cooldown exactly one attempt goes
  // through; if the database is STILL failing, it must re-open immediately
  // rather than granting another BREAKER_TRIP free attempts.
  const b = new Breaker();
  const t0 = 2_000_000;
  for (let i = 0; i < BREAKER_TRIP; i++) b.recordCongestion(t0);
  const later = t0 + BREAKER_COOLDOWN_MS;
  t("⭐ cooldown served, so one attempt is allowed", b.isOpen(later) === false);
  b.recordCongestion(later);
  t("⛔⛔ and one further failure RE-OPENS it at once, not after another "
    + BREAKER_TRIP, b.isOpen(later) === true,
    "consecutive=" + b.consecutive);
}

{
  const b = new Breaker();
  const t0 = 3_000_000;
  for (let i = 0; i < BREAKER_TRIP; i++) b.recordCongestion(t0);
  t("⭐ open", b.isOpen(t0) === true);
  b.recordSuccess();
  t("⭐⭐ ONE successful insert closes it - the database answering is the only "
    + "evidence that matters", b.isOpen(t0) === false);
  t("⭐ and the consecutive count resets with it", b.consecutive === 0);
}

console.log("=".repeat(72));
console.log("4. a drop is LOUD and carries a signature, never a bare count");
console.log("=".repeat(72));

{
  const line = dropLogLine("congestion", 7, "5ig1abc", "503 upstream");
  const o = JSON.parse(line);
  t("⭐ the drop line is parseable JSON with its own event name",
    o.event === "chain_events_drop", o.event);
  t("⛔ it carries the COUNT", o.dropped === 7, String(o.dropped));
  t("⛔ and at least one SIGNATURE - 'some events were dropped' is not actionable",
    o.first_signature === "5ig1abc", o.first_signature);
  t("⭐ a missing signature renders as 'unknown', never as null or empty "
    + "(standing rule 5)",
    JSON.parse(dropLogLine("payload", 1, null, "x")).first_signature === "unknown");
  t("⭐ the detail is bounded so a huge PostgREST body cannot flood the log",
    JSON.parse(dropLogLine("payload", 1, "s", "y".repeat(5000)))
      .detail.length === 300);
}

console.log("=".repeat(72));
console.log("5. the retry is bounded and jittered, so isolates do not lockstep");
console.log("=".repeat(72));

t("⭐ the floor is RETRY_BASE_MS", retryDelayMs(() => 0) === RETRY_BASE_MS,
  String(retryDelayMs(() => 0)));
t("⭐ the ceiling is base + jitter",
  retryDelayMs(() => 0.9999) === RETRY_BASE_MS + RETRY_JITTER_MS - 1,
  String(retryDelayMs(() => 0.9999)));
{
  const seen = new Set();
  for (let i = 0; i < 200; i++) seen.add(retryDelayMs());
  t("⛔ and it is actually jittered, not a constant - 200 draws give many "
    + "distinct delays", seen.size > 50, "distinct=" + seen.size);
}

console.log("=".repeat(72));
console.log("6. the per-isolate counters say OUT LOUD that they are a floor");
console.log("=".repeat(72));

{
  const b = new Breaker();
  b.recordDrop("congestion", 4);
  b.recordDrop("congestion", 2);
  b.recordSkip(9);
  const snap = b.snapshot(4_000_000);
  t("⭐ drops accumulate by kind",
    snap.dropped_this_isolate_floor.congestion === 6,
    JSON.stringify(snap.dropped_this_isolate_floor));
  t("⭐ skips accumulate", snap.skipped_this_isolate_floor === 9);
  t("⛔⛔ every counter key says 'floor' IN ITS NAME, because a GET can land on "
    + "an isolate that served no POSTs and would report a false zero",
    Object.keys(snap).filter((k) => k.includes("this_isolate")).length === 2
    && Object.keys(snap).filter((k) => k.includes("this_isolate"))
      .every((k) => k.endsWith("_floor")),
    Object.keys(snap).join(","));
  t("⛔ and the snapshot carries the warning in words, not just in key names",
    /floor, never a total/.test(snap.per_isolate_warning));
}

console.log("=".repeat(72));
console.log(pass + "/" + (pass + fails.length) + " passed");
if (fails.length) {
  console.log("\nFAILED:");
  for (const f of fails) console.log("  - " + f);
  process.exit(1);
}
