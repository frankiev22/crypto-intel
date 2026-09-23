// The Helius receiver for POOL events. Runs on Supabase, not on Frank's PC.
//
// WHY THIS EXISTS RATHER THAN REUSING site/api/helius.mjs. That receiver is
// built for WALLET-attributed whale swaps: it loops WATCHED_WALLETS and calls
// isActor(tx, wallet), so with an empty wallet list it drops every event it is
// given. Pointing pool or program addresses at it would deliver events that are
// then discarded. The two lanes want different things, so they are two
// receivers. The Vercel one is untouched.
//
// WHAT WE ARE ACTUALLY HUNTING: the decoy EMBER's creator withdrew 2,907.565
// SOL and burned the LP at 11:09:37Z on 2026-09-22. Our 24h outcome check ran
// at 11:12:10Z, 2m33s later, and reported a dead token with no idea why. A
// Withdraw as the last event on a pool is the event we want live. Three of our
// confirmed deaths (USDCAT, OWL, X7) are the same single event.
//
// READ ONLY with respect to the chain. This receives and stores. It cannot
// sign, send or move anything, and no code path that could may ever be added.
//
// THE AUTH DESIGN, and it is deliberate. Supabase function secrets cannot be
// set from anything on this disk (no CLI, no management token), so the shared
// secret is NOT stored here. What is stored is its SHA-256, which is committed
// safely: the secret is 33 characters over four character classes, all distinct,
// so the hash is not invertible. Helius echoes the plaintext in the
// Authorization header, this hashes what arrives and compares. The plaintext
// lives in .env and in Helius's own webhook config, and nowhere else.
//
// ⛔ THIS FUNCTION MUST BE DEPLOYED WITH verify_jwt: false. Its auth is the
// SHA-256 check below, not a Supabase JWT. Deployed once with verify_jwt left at
// its default of true (2026-09-23 06:10Z) and the GATEWAY then answered every
// request UNAUTHORIZED_NO_AUTH_HEADER in 0.33s before reaching a line of this
// file - which would have rejected Helius too. Caught by probing the deployed
// URL rather than trusting the deploy's 200.
//
// ⛔⛔ TEN SILENT FAILURES have been found in this receiver, every one by
// probing its OUTPUT rather than trusting a deploy. They are written up in
// docs/CHAIN_EVENTS.md section 4, with what each looked like and what caught it.
// The four that constrain this file most:
//   - the watchlist was read on EVERY event, which saturated PostgREST for the
//     whole project at 5.5 events/sec. See watchlist(): cached, and a failed
//     refresh returns NULL rather than a stale or empty list.
//   - the raw-payload cap was a module-global counter, which cannot cap anything
//     in a runtime that spins up many isolates. Measured: 1,669 rows, ZERO
//     carrying the omitted marker. See RAW_SAMPLE_ONE_IN.
//   - `resolution=ignore-duplicates` did NOT ignore duplicates, because the
//     conflict target was never named. Measured by replaying 248 real batches:
//     every one returned 409. See insertRows().
//   - `stored` reported how many rows were SENT, not how many were written, and
//     a replay that wrote nothing answered "stored: 3". See the success path.
//
// ⚠️ THIS FILE IS WHAT IS DEPLOYED. Keep them identical: a receiver whose
// committed source differs from the running one is the same bug class again.

import {
  Breaker,
  classifyFailure,
  dropLogLine,
  httpStatusFor,
  retryDelayMs,
  BREAKER_TRIP,
  BREAKER_COOLDOWN_MS,
} from "./backpressure.ts";

// ⛔⛔ BACKPRESSURE. One breaker per isolate - see backpressure.ts for why
// that is a damper and not a guarantee, and for the rule it enforces: this
// receiver may never answer 5xx because a write failed, because a 5xx makes
// Helius redeliver and a redelivery is more load at the moment load is the
// problem. That amplification is what took out the project's REST API at
// ~04:06Z on 2026-09-23.
const breaker = new Breaker();

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

// sha256 of HELIUS_WEBHOOK_SECRET. Not a secret. See the note above.
const SECRET_SHA256 = "756cc268ead6a01795f0cfd9111fd22d5b4f09b193e1597ff475bb419fe82d00";

async function sha256Hex(s: string): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

// Helius transaction types that mean liquidity moved. The first two are the
// ones that kill a token; the rest are context.
const REMOVE = new Set([
  "WITHDRAW", "WITHDRAW_LIQUIDITY", "REMOVE_LIQUIDITY", "BURN", "BURN_NFT",
  "CLOSE_POSITION", "WITHDRAW_GEM",
]);
const ADD = new Set(["ADD_LIQUIDITY", "DEPOSIT", "OPEN_POSITION"]);
const CREATE = new Set(["CREATE_POOL", "INIT_POOL", "TOKEN_MINT", "CREATE"]);
const SWAPS = new Set(["SWAP", "SWAP_EXACT_OUT"]);

// A transfer at or above this many lamports is large enough to report on its
// own, whatever Helius called the transaction. 50 SOL.
const LARGE_LAMPORTS = 50 * 1e9;

// ---------------------------------------------------------------------------
// THE STORAGE BUDGET, and it binds harder than the credit budget.
//
// The free-tier Supabase database is 500 MB TOTAL, shared with everything else
// already in the project. Measured from our own delivered rows:
//
//   18 addresses, 5.55 events/sec, full raw at ~2 KB ->    982 MB/DAY
//   4 addresses,  0.09 events/sec, full raw at ~2 KB ->    496 MB/month
//   4 addresses,  0.09 events/sec, metadata only     ->     73 MB/month
//
// So at the set actually registered, this table would have consumed the whole
// database in under twelve hours, and even the four addresses the credit budget
// allows would fill it inside a month. Storing every swap's full payload is not
// affordable at any watchlist size worth having.
//
// WHAT IS KEPT: the full payload for the four classifications that are actual
// EVENTS, because they are rare and we want everything about them. SWAP and
// OTHER rows are still written with all their metadata (a few hundred bytes) -
// the denominator matters, and OTHER is 89% of delivered traffic and is where a
// Meteora liquidity operation hides. Their raw payload is kept for a bounded
// SAMPLE per hour so the classifier can still be improved against real traffic.
//
// An omitted payload is NEVER a null that could read as "there was nothing".
// It is an explicit marker saying what was dropped and why (standing rule 5),
// and the sample is bounded and says so (standing rule 15).
const EVENTS = new Set([
  "POOL_CREATE", "LIQUIDITY_ADD", "LIQUIDITY_REMOVE", "LARGE_TRANSFER",
]);
// ⛔⛔ THE PER-HOUR COUNTER DID NOT WORK AND THE DATABASE PROVED IT.
// Measured 2026-09-23 13:56Z on the live table: 1,669 rows, **0 carrying the
// omitted marker**, 1,669 full payloads, average raw 6,114 bytes. The cap was a
// module-global counter, and a Supabase edge function runs in MANY isolates that
// are created and recycled constantly. Each fresh isolate starts at
// `sampleHour = -1` and hands out another 20, so the "20 per hour" was really
// "20 per isolate per hour" and the effective rate was ~100%.
//
// ⭐ The fix is to hold no state at all. Sampling is now DETERMINISTIC on the
// signature, so every isolate independently reaches the same answer for the same
// transaction and the rate is exactly what it says regardless of how many
// isolates exist. It is also reproducible: anyone can recompute which rows
// should have been kept.
//
// ⛔ PRE-COMMITTED RATE, and the arithmetic behind it, measured not guessed:
//   - a row WITH raw costs 9,429 bytes all-in (heap + TOAST + indexes),
//     measured by pg_total_relation_size / count on 2026-09-23. My documented
//     estimate was 2 KB, so it is 4.7x worse than CHAIN_EVENTS.md said.
//   - a row WITHOUT raw costs ~1.2 KB.
//   - the free database is 500 MB TOTAL and 150 MB is already in use.
// At 1 in 50, the 6 addresses in data/chain_watch.json (0.0396 events/sec =
// 3,421 rows/day) cost about 4.7 MB/day instead of 32 MB/day, which is the
// difference between filling the remaining headroom in 11 days and in 74.
const RAW_SAMPLE_ONE_IN = 50;

// FNV-1a over the signature. Small, dependency free, and stable across isolates,
// deploys and machines, which a counter is not.
function sampleHash(sig: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < sig.length; i++) {
    h ^= sig.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h;
}

function keepRaw(classification: string, signature: string): boolean {
  if (EVENTS.has(classification)) return true;
  if (!signature) return false;
  return sampleHash(signature) % RAW_SAMPLE_ONE_IN === 0;
}

function classify(tx: any, watched: string[] | null): string {
  const t = String(tx?.type ?? "").toUpperCase();
  if (REMOVE.has(t)) return "LIQUIDITY_REMOVE";
  if (CREATE.has(t)) return "POOL_CREATE";
  if (ADD.has(t)) return "LIQUIDITY_ADD";

  // Helius often labels a liquidity pull as a plain TRANSFER. So the type is
  // not trusted on its own: a large native transfer OUT of an address we watch
  // is treated as a removal regardless of what it was called. Missing a drain
  // because it was mislabelled is the expensive error; a false LIQUIDITY_REMOVE
  // is cheap and visible.
  //
  // watched === null means the watchlist could not be read. This check is then
  // SKIPPED rather than silently answered no, and the row carries watched=null
  // so the gap is visible rather than looking like a clean negative.
  if (watched) {
    const w = new Set(watched);
    let outOfWatched = 0;
    for (const n of tx?.nativeTransfers ?? []) {
      const amt = Number(n?.amount ?? 0);
      if (!Number.isFinite(amt)) continue;
      if (w.has(n?.fromUserAccount)) outOfWatched += amt;
    }
    if (outOfWatched >= LARGE_LAMPORTS) return "LIQUIDITY_REMOVE";
  }
  if (SWAPS.has(t)) return "SWAP";

  for (const n of tx?.nativeTransfers ?? []) {
    if (Number(n?.amount ?? 0) >= LARGE_LAMPORTS) return "LARGE_TRANSFER";
  }
  // OTHER is honest. It means we saw it and did not recognise it. It never
  // means nothing happened, and it is stored exactly like everything else so
  // the classifier can be improved against real traffic rather than guesses.
  return "OTHER";
}

function touched(tx: any, watch: Set<string>): string[] {
  const hit = new Set<string>();
  const look = (a: unknown) => {
    if (typeof a === "string" && watch.has(a)) hit.add(a);
  };
  look(tx?.feePayer);
  for (const a of tx?.accountData ?? []) look(a?.account);
  for (const n of tx?.nativeTransfers ?? []) {
    look(n?.fromUserAccount);
    look(n?.toUserAccount);
  }
  for (const n of tx?.tokenTransfers ?? []) {
    look(n?.fromUserAccount);
    look(n?.toUserAccount);
    look(n?.fromTokenAccount);
    look(n?.toTokenAccount);
    look(n?.mint);
  }
  for (const i of tx?.instructions ?? []) {
    look(i?.programId);
    for (const a of i?.accounts ?? []) look(a);
    for (const inner of i?.innerInstructions ?? []) {
      look(inner?.programId);
      for (const a of inner?.accounts ?? []) look(a);
    }
  }
  return [...hit];
}

// The watchlist, cached in the instance.
//
// The FOURTH failure found by measurement: the first version read chain_watch on
// every inbound event. At the 5.5 events/sec this actually delivers that is 11
// PostgREST requests a second on a free-tier project, and it saturated the API
// so thoroughly that chain_watch_sync timed out four times in a row from a
// laptop. The list changes a few times a day; reading it thousands of times an
// hour to learn the same answer is the bug.
//
// The cache is deliberately short and it is NEVER kept past a failure: a failed
// refresh returns null so the gap is visible, rather than serving a stale list
// that looks healthy.
const WATCH_TTL_MS = 60_000;
let watchCache: { at: number; set: Set<string> } | null = null;

// null means COULD NOT READ, which is not the same as "watching nothing".
async function watchlist(force = false): Promise<Set<string> | null> {
  if (!force && watchCache && Date.now() - watchCache.at < WATCH_TTL_MS) {
    return watchCache.set;
  }
  try {
    // Bounded, for the same reason the probe reads are: an unbounded read here
    // blocks the EVENT path, not just a diagnostic. 6s, then null.
    const r = await fetch(
      `${SUPABASE_URL}/rest/v1/chain_watch?select=address&active=is.true`,
      {
        headers: { apikey: SERVICE_KEY, Authorization: `Bearer ${SERVICE_KEY}` },
        signal: AbortSignal.timeout(6_000),
      },
    );
    if (!r.ok) {
      console.error("watchlist read failed", r.status, (await r.text()).slice(0, 200));
      return null;
    }
    const rows = await r.json();
    const set = new Set<string>((rows ?? []).map((x: any) => x.address));
    watchCache = { at: Date.now(), set };
    return set;
  } catch (e) {
    console.error("watchlist read threw", String(e).slice(0, 200));
    return null;
  }
}

// ⛔ EVERY PROBE READ IS BOUNDED. The probe had no timeout, so when the database
// stopped answering on 2026-09-23 at ~04:06Z the probe hung for the caller's full
// timeout and told us nothing. A diagnostic that cannot answer while the thing it
// diagnoses is broken is worse than useless - it is the case you built it for.
// Each read gets 6s and a failure reports itself instead of hanging.
const PROBE_TIMEOUT_MS = 6_000;

function probeHeaders(extra: Record<string, string> = {}) {
  return {
    apikey: SERVICE_KEY,
    Authorization: `Bearer ${SERVICE_KEY}`,
    ...extra,
  };
}

Deno.serve(async (req) => {
  if (req.method === "GET") {
    // A liveness probe that answers the only question worth asking: have rows
    // ACTUALLY landed. Not "is the function deployed".
    let latest: unknown = null;
    let readErr: string | null = null;
    try {
      const r = await fetch(
        `${SUPABASE_URL}/rest/v1/chain_events` +
        `?select=id,received_at,block_time,classification,tx_type,source,watched` +
        `&order=received_at.desc&limit=5`,
        { headers: probeHeaders(), signal: AbortSignal.timeout(PROBE_TIMEOUT_MS) },
      );
      if (r.ok) {
        latest = await r.json();
      } else {
        readErr = `${r.status} ${(await r.text()).slice(0, 160)}`;
      }
    } catch (e) {
      // null, not [], so an unreadable table never renders as an empty one.
      readErr = `read failed: ${String(e).slice(0, 160)}`;
    }
    let range = "";
    try {
      const c = await fetch(
        `${SUPABASE_URL}/rest/v1/chain_events?select=id&limit=1`,
        {
          method: "GET",
          headers: probeHeaders({ Prefer: "count=exact", Range: "0-0" }),
          signal: AbortSignal.timeout(PROBE_TIMEOUT_MS),
        },
      );
      range = c.headers.get("content-range") ?? "";
    } catch (e) {
      readErr = readErr ?? `count failed: ${String(e).slice(0, 160)}`;
    }

    // THE OUTPUT ASSERTION FOR THE STORAGE BUDGET, answered here rather than by
    // a SQL query someone has to remember to run.
    //
    // Deploying the budget is not evidence that it WORKS. What proves it is a
    // count of rows that actually carry the omitted marker, against a count of
    // rows that kept a full payload. Before this, that answer needed a hand-run
    // query against the database - a manual step, and therefore not an answer.
    //
    // ⚠️ A count that could not be read comes back null, never 0. A 0 here would
    // read as "the budget is not dropping anything", which is exactly the
    // authority_live=None shape: not measured looking like measured.
    async function countWhere(filter: string): Promise<number | null> {
      try {
        const res = await fetch(
          `${SUPABASE_URL}/rest/v1/chain_events?select=id&limit=1&${filter}`,
          {
            headers: probeHeaders({ Prefer: "count=exact", Range: "0-0" }),
            signal: AbortSignal.timeout(PROBE_TIMEOUT_MS),
          },
        );
        const cr = res.headers.get("content-range") ?? "";
        if (!res.ok || !cr.includes("/")) return null;
        const n = Number(cr.split("/")[1]);
        return Number.isFinite(n) ? n : null;
      } catch (_e) {
        return null;
      }
    }
    const rawOmitted = await countWhere("raw->>omitted=eq.true");
    const rawFull = await countWhere("raw->>omitted=is.null");

    const watch = await watchlist(true);   // the probe never trusts the cache
    return Response.json({
      ok: true,
      receiver: "helius-events",
      read_only: true,
      note: "POST only, from Helius, with the shared secret in Authorization.",
      rows_total: range.includes("/") ? range.split("/")[1] : "unknown",
      // ⚠️ This is the count of ACTIVE ROWS IN `chain_watch`, which is our
      // attribution list. It is NOT what Helius delivers - that is the webhook's
      // own accountAddresses, which this function cannot read. The two diverged:
      // measured 2026-09-23 14:45Z at 20 here against 6 registered, because
      // chain_watch_sync could only ever ACTIVATE and never deactivate.
      watching_chain_watch_active: watch ? watch.size : null,
      watching_note: "attribution list, NOT the delivery list. Helius delivers "
        + "the webhook's own accountAddresses; compare with heliushook."
        + "hook_addresses().",
      // null, not 0, when the list could not be read. Standing rule 5.
      watching: watch ? watch.size : null,
      watchlist_read: watch ? "ok" : "FAILED",
      read_error: readErr,
      raw_sample_one_in: RAW_SAMPLE_ONE_IN,
      raw_note: "raw is omitted with an explicit marker, never nulled",
      // null means the count could not be read, NOT that there are none.
      raw_omitted_rows: rawOmitted,
      raw_full_rows: rawFull,
      storage_budget_working: (rawOmitted === null || rawFull === null)
        ? "unknown - count unreadable"
        : (rawOmitted > 0 ? "yes - rows carry the omitted marker" : "NOT OBSERVED YET"),
      // ⭐ MEASURED 2026-09-23 13:56Z, not estimated any more:
      // pg_total_relation_size / count over 1,669 live rows.
      bytes_per_row: 9429,
      bytes_per_row_note: "MEASURED 2026-09-23 on 1,669 rows: 9,429 bytes all-in "
        + "(heap 805 + TOAST + indexes), avg raw payload 6,114. The 2 KB figure "
        + "in CHAIN_EVENTS.md was an estimate and was 4.7x too low. A row with "
        + "raw omitted costs about 1.2 KB.",
      // ⚠️ PER-ISOLATE AND A FLOOR. A GET may land on an isolate that served
      // no POSTs, which would then report a truthful zero about itself and a
      // false zero about the receiver. The durable cross-isolate record of a
      // drop is the `chain_events_drop` console.error line.
      backpressure: breaker.snapshot(Date.now()),
      backpressure_rule: "never 5xx on a write failure; one in-process retry on "
        + "congestion, then drop with a logged marker; the breaker opens after "
        + `${BREAKER_TRIP} consecutive congestion failures for ${BREAKER_COOLDOWN_MS}ms`,
      newest_rows: latest,
    });
  }
  if (req.method !== "POST") {
    return Response.json(
      { ok: false, error: "this receiver accepts POST from Helius only" },
      { status: 405 },
    );
  }
  // The shared secret. Helius echoes whatever authHeader the webhook was
  // registered with. A mismatch is rejected before the body is parsed.
  if (SECRET_SHA256 && !SECRET_SHA256.startsWith("__")) {
    const got = req.headers.get("authorization") ?? "";
    if ((await sha256Hex(got)) !== SECRET_SHA256) {
      return Response.json({ ok: false, error: "unauthorized" }, { status: 401 });
    }
  }

  let body: any;
  try {
    body = await req.json();
  } catch {
    return Response.json({ ok: false, error: "bad json" }, { status: 400 });
  }
  const txs = Array.isArray(body) ? body : [body];
  const watch = await watchlist();

  const rows = txs.filter(Boolean).map((tx: any) => {
    const hit = watch ? touched(tx, watch) : null;
    const cls = classify(tx, hit);
    // The transfer arrays are most of a swap's bytes, so they follow the same
    // rule as raw. Dropping raw while keeping them would have saved little.
    const full = keepRaw(cls, String(tx?.signature ?? ""));
    return {
      signature: String(tx?.signature ?? ""),
      slot: tx?.slot ?? null,
      block_time: tx?.timestamp
        ? new Date(Number(tx.timestamp) * 1000).toISOString()
        : null,
      tx_type: tx?.type ?? null,
      source: tx?.source ?? null,
      // Kept even when the arrays are dropped, so a null array is never read as
      // "nothing moved": the description is Helius's own sentence about the tx.
      description: (tx?.description ?? "").slice(0, 2000) || null,
      fee_payer: tx?.feePayer ?? null,
      watched: hit,
      native_transfers: full ? (tx?.nativeTransfers ?? null) : null,
      token_transfers: full ? (tx?.tokenTransfers ?? null) : null,
      account_data: null, // large and mostly noise; raw keeps everything
      classification: cls,
      raw: full ? tx : {
        omitted: true,
        why: "storage budget: see THE STORAGE BUDGET in the receiver",
        classification: cls,
        raw_sample_one_in: RAW_SAMPLE_ONE_IN,
        sampling: "deterministic on the signature, so isolate count cannot "
          + "defeat it - the per-hour counter did, at 1,669 rows and 0 omitted",
      },
    };
  }).filter((r: any) => r.signature);

  if (!rows.length) {
    return Response.json({ ok: true, stored: 0, note: "no signatures in payload" });
  }

  // ⛔⛔ THE BREAKER IS CHECKED BEFORE THE DATABASE IS TOUCHED AT ALL. That is
  // the whole point of backpressure: when the database has told us three times
  // in a row that it cannot take a write, the next thing we do must not be
  // another write. See backpressure.ts.
  const nowMs = Date.now();
  if (breaker.isOpen(nowMs)) {
    breaker.recordSkip(rows.length);
    breaker.recordDrop("breaker_open", rows.length);
    console.error(dropLogLine(
      "breaker_open", rows.length, rows[0]?.signature ?? null,
      `breaker open, ${breaker.cooldownRemainingMs(nowMs)}ms of cooldown left`));
    return Response.json({
      ok: false,
      stored: 0,
      dropped: rows.length,
      reason: "breaker_open",
      cooldown_ms_remaining: breaker.cooldownRemainingMs(nowMs),
      note: "the database was failing writes, so this receiver stopped sending "
        + "them. These events are LOST, deliberately, and the loss is logged as "
        + "chain_events_drop. Answering 200 so Helius does not retry: a retry "
        + "would be more load at the moment load is the problem.",
    }, { status: httpStatusFor("breaker_open") });
  }

  // ⛔⛔ `on_conflict=signature` IS LOAD-BEARING AND WAS MISSING, and the
  // committed comment asserted the opposite. Measured 2026-09-23 by replaying
  // 248 real batches at the live receiver: **every one returned 409 duplicate
  // key value violates unique constraint "chain_events_sig_uniq"**, and each was
  // logged as a dropped event. `Prefer: resolution=ignore-duplicates` alone does
  // nothing here, because PostgREST emits ON CONFLICT against the table's
  // PRIMARY KEY (`id`) and the conflict is on a separate unique index over
  // `signature`. Naming the target makes it a real ON CONFLICT (signature) DO
  // NOTHING.
  //
  // ⛔ The consequence while it was missing was not cosmetic: a POST of an
  // array is ONE statement, so a single already-stored signature failed the
  // whole batch and took every genuinely new event in it down as well.
  //
  // ignore-duplicates, NOT merge-duplicates. merge is an UPSERT, so PostgREST
  // demands UPDATE on the table, and this table is append-only (standing rule 8)
  // so it has INSERT and SELECT and nothing else. The first version asked for
  // merge, got 403 "GRANT UPDATE ON public.chain_events", and the correct fix is
  // the weaker verb rather than the wider grant: a repeated signature should be
  // dropped, never allowed to overwrite what we already recorded.
  async function insertRows(): Promise<Response> {
    return await fetch(`${SUPABASE_URL}/rest/v1/chain_events?on_conflict=signature`, {
      method: "POST",
      headers: {
        apikey: SERVICE_KEY,
        Authorization: `Bearer ${SERVICE_KEY}`,
        "Content-Type": "application/json",
        // count=exact so the response carries how many rows were ACTUALLY
        // inserted. Without it the receiver could only report how many it SENT,
        // which is a different number the moment on_conflict starts working.
        Prefer: "resolution=ignore-duplicates,return=minimal,count=exact",
      },
      body: JSON.stringify(rows),
    });
  }

  let res: Response;
  try {
    res = await insertRows();
  } catch (e) {
    // A thrown fetch is congestion by any other name: the gateway did not
    // answer. Treated identically, including the breaker count.
    breaker.recordCongestion(Date.now());
    breaker.recordDrop("congestion", rows.length);
    console.error(dropLogLine("congestion", rows.length,
      rows[0]?.signature ?? null, `insert threw: ${String(e)}`));
    return Response.json({
      ok: false, stored: 0, dropped: rows.length, reason: "insert_threw",
      detail: String(e).slice(0, 300),
    }, { status: httpStatusFor("congestion") });
  }

  if (res.ok) {
    breaker.recordSuccess();
    // ⛔ `stored` used to be `rows.length`, which is how many rows were SENT,
    // not how many were written. With on_conflict working those two numbers are
    // routinely different - a replay of already-stored signatures reported
    // "stored: 3" while writing nothing at all. So the real count is read from
    // PostgREST's own Content-Range, and if that header is absent the answer is
    // NULL with the reason attached, never a guess (standing rule 5).
    const cr = res.headers.get("content-range") ?? "";
    const parsed = cr.includes("/") ? Number(cr.split("/")[1]) : NaN;
    const inserted = Number.isFinite(parsed) ? parsed : null;
    return Response.json({
      ok: true,
      submitted: rows.length,
      stored: inserted,
      stored_unknown_why: inserted === null
        ? "PostgREST returned no parseable Content-Range, so how many of these "
          + "rows were new is NOT KNOWN. It is null rather than 0 or "
          + `${rows.length}: content-range was ${JSON.stringify(cr)}`
        : null,
      already_stored: inserted === null ? null : rows.length - inserted,
    });
  }

  let detail = (await res.text()).slice(0, 400);
  let kind = classifyFailure(res.status, detail);

  // ⛔ A duplicate is NOT a loss. The signature is already in the table, so
  // reporting it as dropped would manufacture a false alarm about data we hold.
  if (kind === "duplicate") {
    breaker.recordSuccess();   // the database answered; it is not congested
    return Response.json({
      ok: true, stored: 0, already_stored: rows.length, error: res.status,
      note: "every signature in this batch is already stored, so nothing was "
        + "written and nothing was lost. Not counted as a drop.",
    });
  }

  // ⭐ ONE in-process retry, and only for congestion. Our own retry is strictly
  // cheaper than a Helius redelivery: it does not multiply across the whole
  // webhook, it is bounded at one, and it is jittered so a burst of isolates
  // does not retry in lockstep. ⛔ A privilege or payload failure is NOT retried
  // at all, because retrying it has a zero success rate and is pure load.
  if (kind === "congestion") {
    await new Promise((r) => setTimeout(r, retryDelayMs()));
    try {
      const again = await insertRows();
      if (again.ok) {
        breaker.recordSuccess();
        const cr2 = again.headers.get("content-range") ?? "";
        const p2 = cr2.includes("/") ? Number(cr2.split("/")[1]) : NaN;
        return Response.json({
          ok: true, submitted: rows.length,
          stored: Number.isFinite(p2) ? p2 : null, retried: true,
          first_error: res.status,
        });
      }
      detail = (await again.text()).slice(0, 400);
      kind = classifyFailure(again.status, detail);
      if (kind === "duplicate") {
        breaker.recordSuccess();
        return Response.json({
          ok: true, stored: 0, already_stored: rows.length,
          note: "already stored; not a drop", retried: true,
        });
      }
    } catch (e) {
      detail = `retry threw: ${String(e).slice(0, 300)}`;
    }
    breaker.recordCongestion(Date.now());
  }

  // ⛔⛔ 200, ALWAYS, for every kind of write failure. The old code answered
  // 500 for 401/403/5xx so that "the event is not lost", and that is exactly how
  // a struggling database became an outage: the 500 asked Helius to send it
  // again. One lost event is cheaper than the project's REST API.
  //
  // ⚠️ So the loss is real and it is recorded LOUDLY rather than swallowed. A
  // privilege failure in particular means EVERY event is being lost until a
  // human fixes a grant, which is why it gets its own kind in the log line.
  breaker.recordDrop(kind, rows.length);
  console.error(dropLogLine(kind, rows.length, rows[0]?.signature ?? null,
    `${res.status} ${detail}`));
  return Response.json({
    ok: false,
    stored: 0,
    dropped: rows.length,
    error: res.status,
    kind,
    detail,
    note: kind === "privilege"
      ? "PRIVILEGE FAILURE: every event is being lost until a grant or key is "
        + "fixed. Retrying cannot help, so Helius is told 200 rather than asked "
        + "to redeliver. Look for chain_events_drop in the function logs."
      : "answered 200 so Helius does not retry; the drop is logged as "
        + "chain_events_drop",
  }, { status: httpStatusFor(kind) });
});
