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
// FIVE SILENT FAILURES WERE FOUND HERE BY PROBING THE OUTPUT, and the handling
// of all five is now part of the contract:
//   1. service_role had no grant on either table, so the watchlist read came
//      back 401 and watchlist() returned an EMPTY SET. Empty is indistinguishable
//      from "we watch nothing", which is the authority_live=None shape: not
//      checked reading as checked. It now returns null on failure and the
//      failure is reported in every response.
//   2. The insert came back 403 while this returned HTTP 200, so Helius would
//      have marked delivery successful and dropped the event. A privilege or
//      server error now returns 500 so Helius RETRIES and its own error counter
//      rises. Only a payload error returns 200, because retrying that forever
//      helps nobody.
//   3. The insert asked for merge-duplicates, which is an UPSERT and therefore
//      wants UPDATE on an append-only table. See the note at the insert: the fix
//      was the weaker verb, not the wider grant.
//   4. The watchlist was read on EVERY event, which at the measured 5.5
//      events/sec saturated PostgREST for the whole project. See watchlist().
//   5. It stored the FULL raw payload of every event, which at the 18 addresses
//      actually registered is 982 MB a day into a 500 MB database. See the
//      storage budget below.
//
// AND A SIXTH THAT WAS NOT IN THE CODE. This header said "TWO SILENT FAILURES"
// for two deploys after items 3 and 4 existed, because the patches that were
// meant to add them used a replace() with no assert and silently matched
// nothing. The behaviour was right and the committed description was wrong,
// which is the same class of error: a change nobody verified landed.
//
// AND A SEVENTH, 2026-09-23: the GET probe had no timeout, so when the database
// stopped answering at ~04:06Z the probe hung instead of reporting. Every read
// is now bounded and a failed read says so. See PROBE_TIMEOUT_MS.

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
const RAW_SAMPLE_PER_HOUR = 20;   // raw payloads kept for SWAP / OTHER
let sampleHour = -1;
let sampleKept = 0;

function keepRaw(classification: string): boolean {
  if (EVENTS.has(classification)) return true;
  const hour = Math.floor(Date.now() / 3_600_000);
  if (hour !== sampleHour) {
    sampleHour = hour;
    sampleKept = 0;
  }
  if (sampleKept < RAW_SAMPLE_PER_HOUR) {
    sampleKept += 1;
    return true;
  }
  return false;
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
      // null, not 0, when the list could not be read. Standing rule 5.
      watching: watch ? watch.size : null,
      watchlist_read: watch ? "ok" : "FAILED",
      read_error: readErr,
      raw_sample_kept_this_hour: sampleKept,
      raw_sample_per_hour: RAW_SAMPLE_PER_HOUR,
      raw_note: "raw is omitted with an explicit marker, never nulled",
      // null means the count could not be read, NOT that there are none.
      raw_omitted_rows: rawOmitted,
      raw_full_rows: rawFull,
      storage_budget_working: (rawOmitted === null || rawFull === null)
        ? "unknown - count unreadable"
        : (rawOmitted > 0 ? "yes - rows carry the omitted marker" : "NOT OBSERVED YET"),
      // ⛔ Still not answered here, and it is the figure every capacity number in
      // docs/CHAIN_EVENTS.md section 3 rests on: bytes per row. It needs
      // pg_total_relation_size, which PostgREST cannot reach without an RPC, so
      // it stays ESTIMATED at 2 KB and labelled as such until one exists.
      bytes_per_row: null,
      bytes_per_row_note: "ESTIMATED at 2 KB, never measured - needs an RPC over pg_total_relation_size",
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
    const full = keepRaw(cls);
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
        raw_sample_per_hour: RAW_SAMPLE_PER_HOUR,
      },
    };
  }).filter((r: any) => r.signature);

  if (!rows.length) {
    return Response.json({ ok: true, stored: 0, note: "no signatures in payload" });
  }

  // Helius retries on a non-2xx, so the insert is idempotent: the unique
  // constraint on signature plus ignore-duplicates makes a retry a no-op.
  //
  // ignore-duplicates, NOT merge-duplicates. merge is an UPSERT, so PostgREST
  // demands UPDATE on the table, and this table is append-only (standing rule 8)
  // so it has INSERT and SELECT and nothing else. The first version asked for
  // merge, got 403 "GRANT UPDATE ON public.chain_events", and the correct fix is
  // the weaker verb rather than the wider grant: a repeated signature should be
  // dropped, never allowed to overwrite what we already recorded.
  const res = await fetch(`${SUPABASE_URL}/rest/v1/chain_events`, {
    method: "POST",
    headers: {
      apikey: SERVICE_KEY,
      Authorization: `Bearer ${SERVICE_KEY}`,
      "Content-Type": "application/json",
      Prefer: "resolution=ignore-duplicates,return=minimal",
    },
    body: JSON.stringify(rows),
  });
  if (!res.ok) {
    const detail = (await res.text()).slice(0, 400);
    console.error("insert failed", res.status, detail);
    // A privilege, auth or server error is OUR bug and is fixable, so answer
    // with a 500: Helius retries, its error counter rises, and the event is not
    // lost. A payload error (400/409/422) would retry forever, so it gets a 200
    // and the detail is returned for whoever is looking.
    const ourFault = res.status === 401 || res.status === 403 || res.status >= 500;
    return Response.json(
      { ok: false, stored: 0, error: res.status, detail },
      { status: ourFault ? 500 : 200 },
    );
  }
  return Response.json({ ok: true, stored: rows.length });
});
