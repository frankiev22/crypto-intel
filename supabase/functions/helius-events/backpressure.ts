// Backpressure for the Helius receiver. PURE: no Deno, no fetch, no globals,
// so it can be run and asserted on outside the edge runtime (test_backpressure.py
// runs this exact file through node).
//
// ⛔⛔ WHY THIS EXISTS. On 2026-09-23 ~04:06Z this receiver took out the shared
// Supabase REST API. The cause was load amplification: it read `chain_watch` on
// every inbound event, that made PostgREST return 500s, the receiver passed the
// 500 straight through to Helius, **Helius retried**, and the retries multiplied
// the load that was already the problem. PostgREST then stopped answering for
// every table in the project, including pre-existing ones.
//
// Frank, 2026-09-23: *"That is a burst problem, not a capacity problem. Fix it
// with connection pooling and backpressure on our side, not a bigger plan."*
//
// ⛔ So the rule, stated before it was measured:
//
//   **A 5xx answer from this receiver is a request for MORE load at the exact
//   moment the database cannot take what it already has.** The receiver may
//   therefore never answer 5xx because a write failed. It absorbs the failure,
//   records the drop where a human and a liveness check can see it, and returns
//   200 so Helius stops.
//
// ⚠️ That trades one lost event for the whole project's REST API. A dropped
// event must be LOUD (rule 5: unknown renders as unknown, never as nothing).

/** How many consecutive congestion failures open the breaker.
 *
 * 3, because at the measured 5.55 events/sec that is roughly one second of
 * evidence: long enough not to trip on a single unlucky request, short enough
 * that we stop hitting a struggling database almost immediately. */
export const BREAKER_TRIP = 3;

/** How long the breaker stays open, in ms.
 *
 * 30s. Long enough for a free-tier PostgREST to drain its queue, short enough
 * that we lose ~166 events rather than an hour of them. */
export const BREAKER_COOLDOWN_MS = 30_000;

/** The one in-process retry on congestion, in ms, before jitter. */
export const RETRY_BASE_MS = 250;
export const RETRY_JITTER_MS = 500;

export type FailureKind = "congestion" | "privilege" | "payload" | "duplicate";

/** What kind of failure a PostgREST status code is.
 *
 * ⛔ The distinction that matters is NOT "our fault / their fault" - that was
 * the old code's framing and it is why a 403 used to return a 500. The question
 * is **can retrying possibly help**:
 *
 *  - `congestion` - transient. Retrying MIGHT help, but only later, and only
 *    once, and never by asking Helius to send it again.
 *  - `privilege`  - a missing grant or a bad key. Retrying can NEVER help; it
 *    is pure amplification with a zero success rate. Needs a human.
 *  - `payload`    - the row shape is wrong. Retrying can never help either, and
 *    Helius would retry it forever.
 *  - `duplicate`  - the signature is ALREADY STORED. Not a failure at all in any
 *    sense that matters: nothing was lost, so nothing may be reported as lost.
 */
export function classifyFailure(status: number, body = ""): FailureKind {
  if (status === 401 || status === 403) return "privilege";
  if (status === 408 || status === 429 || status >= 500) return "congestion";
  // ⛔⛔ 409 / SQLSTATE 23505 is a UNIQUE VIOLATION, which on this table means
  // the signature is ALREADY STORED. It is not a drop and it is not a defect in
  // the payload: nothing was lost, so nothing may be reported as lost.
  //
  // Found 2026-09-23 by replaying 248 real batches at the live receiver: every
  // one came back **409 duplicate key value violates unique constraint
  // "chain_events_sig_uniq"**, and each was logged as `chain_events_drop`. The
  // committed comment claimed `resolution=ignore-duplicates` made a retry a
  // no-op. It did not, because PostgREST emits ON CONFLICT against the PRIMARY
  // KEY, and the conflict here is a separate unique index on `signature`. The
  // real fix is `?on_conflict=signature` on the insert; this branch is the
  // belt-and-braces guard for when a 409 arrives anyway.
  if (status === 409 || body.includes("23505")) return "duplicate";
  return "payload";
}

/** ⛔ The HTTP status this receiver answers Helius with. ALWAYS 200 on a write
 * failure, for every kind, because Helius retries a non-2xx and a retry is more
 * load. The kinds differ in how loudly they are recorded, not in the status.
 *
 * Kept as its own function so a test can assert the invariant directly rather
 * than reading the handler and hoping. */
export function httpStatusFor(_kind: FailureKind | "breaker_open"): number {
  return 200;
}

/** Consecutive-failure breaker. One instance per isolate.
 *
 * ⚠️ PER-ISOLATE, and that limit is real: Supabase runs many isolates and each
 * starts with its own counter, so this cannot enforce a global request budget.
 * That is the same trap the raw-payload sampler fell into this morning, and the
 * answer there was to go stateless. Here per-isolate is still worth having:
 * every isolate that sees congestion independently stops sending, so aggregate
 * load falls roughly in proportion to how widely the failure is being seen.
 * ⛔ It is a damper, not a guarantee, and it is not to be described as one. */
export class Breaker {
  consecutive = 0;
  openedAt: number | null = null;
  /** Total inserts this isolate skipped without attempting. A FLOOR: another
   * isolate's skips are invisible here. */
  skipped = 0;
  /** Events this isolate dropped, by kind. Also a floor, same reason. */
  dropped: Record<string, number> = {};

  /** True when no insert should be attempted at all. */
  isOpen(now: number): boolean {
    if (this.openedAt === null) return false;
    if (now - this.openedAt >= BREAKER_COOLDOWN_MS) {
      // Cooldown served. Close it and let exactly one attempt through; if that
      // attempt fails the count is still at the trip level, so it re-opens at
      // once rather than after another three.
      this.openedAt = null;
      return false;
    }
    return true;
  }

  cooldownRemainingMs(now: number): number {
    if (this.openedAt === null) return 0;
    return Math.max(0, BREAKER_COOLDOWN_MS - (now - this.openedAt));
  }

  /** Record a congestion failure. Opens the breaker at BREAKER_TRIP. */
  recordCongestion(now: number): void {
    this.consecutive += 1;
    if (this.consecutive >= BREAKER_TRIP && this.openedAt === null) {
      this.openedAt = now;
    }
  }

  /** Record a successful insert. One success is enough to close the breaker:
   * the database answering is the only evidence that matters. */
  recordSuccess(): void {
    this.consecutive = 0;
    this.openedAt = null;
  }

  recordDrop(kind: string, n: number): void {
    this.dropped[kind] = (this.dropped[kind] ?? 0) + n;
  }

  recordSkip(n: number): void {
    this.skipped += n;
  }

  /** What the GET self-check publishes. ⚠️ Every number here is a FLOOR and
   * says so in its own key name, because a GET may land on an isolate that
   * served no POSTs at all and would then report a truthful zero about itself
   * and a false zero about the receiver. */
  snapshot(now: number) {
    return {
      breaker_open: this.isOpen(now),
      breaker_cooldown_ms_remaining: this.cooldownRemainingMs(now),
      consecutive_congestion_failures: this.consecutive,
      dropped_this_isolate_floor: { ...this.dropped },
      skipped_this_isolate_floor: this.skipped,
      per_isolate_warning:
        "these counts are for THIS isolate only and are a floor, never a total. " +
        "The durable record of a drop is the console.error line, which Supabase " +
        "collects across isolates.",
    };
  }
}

/** The jittered delay before the single in-process retry. Deterministic when a
 * random source is injected, so a test can assert the bound. */
export function retryDelayMs(rand: () => number = Math.random): number {
  return RETRY_BASE_MS + Math.floor(rand() * RETRY_JITTER_MS);
}

/** The one line that is the durable record of a dropped event.
 *
 * ⛔ It must carry the count and at least one signature, because "some events
 * were dropped" is not a fact anyone can act on. */
export function dropLogLine(
  kind: FailureKind | "breaker_open",
  n: number,
  firstSignature: string | null,
  detail: string,
): string {
  return JSON.stringify({
    event: "chain_events_drop",
    kind,
    dropped: n,
    first_signature: firstSignature ?? "unknown",
    detail: detail.slice(0, 300),
  });
}
