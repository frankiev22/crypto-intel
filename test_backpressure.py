"""The Helius receiver's backpressure, EXECUTED rather than read.

⛔⛔ WHY THIS FILE EXISTS. The receiver at `supabase/functions/helius-events/` is
a Deno edge function and there is no Deno on this disk, so until 2026-09-23 not
one line of it had ever been executed by a test. Every fix to it - eight silent
failures and counting - was verified by reading the source or by trusting a
deploy's 200. That is precisely the habit standing rule 16 exists to break, and
it cost the project's REST API at ~04:06Z that morning.

⭐ So the part that carries the load rule, `backpressure.ts`, is deliberately
PURE: no Deno, no fetch, no module globals. Node's type stripping imports and
runs it unchanged, and `test_backpressure.mjs` asserts on its behaviour. This
file runs that harness and adds the source-level invariants that can only be
checked against `index.ts`, which cannot be imported without Deno.

⚠️ A missing node is a FAILURE here, not a skip. A check that quietly does not
run is worse than one that is obviously broken.
"""
import io
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FN = os.path.join(HERE, "supabase", "functions", "helius-events")
INDEX = os.path.join(FN, "index.ts")
PURE = os.path.join(FN, "backpressure.ts")
HARNESS = os.path.join(HERE, "test_backpressure.mjs")

PASS = [0]
FAILS = []


def t(name, ok, detail=""):
    if ok:
        PASS[0] += 1
        print("  PASS  " + name + (("  [" + detail + "]") if detail else ""))
    else:
        FAILS.append(name + (("  [" + detail + "]") if detail else ""))
        print("  FAIL  " + name + (("  [" + detail + "]") if detail else ""))


def head(title):
    print("=" * 72)
    print(title)
    print("=" * 72)


src = io.open(INDEX, encoding="utf-8").read()
pure = io.open(PURE, encoding="utf-8").read()

head("1. ⛔ the receiver's pure module RUNS, in node, and passes its own suite")

node = shutil.which("node")
t("⛔⛔ node is available, so the ONLY executable test of the receiver can "
  "actually run - a silent skip here would put us straight back to verifying "
  "this file by reading it",
  bool(node), node or "NOT FOUND")

if node:
    p = subprocess.run([node, HARNESS], cwd=HERE, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120)
    out = (p.stdout or "") + (p.stderr or "")
    m = re.search(r"(\d+)/(\d+) passed", out)
    t("⭐ the harness ran to completion and reported a count",
      bool(m), (out.strip().splitlines() or ["no output"])[-1][:160])
    if m:
        t("⛔ every backpressure assertion passed",
          p.returncode == 0 and m.group(1) == m.group(2),
          m.group(0) + " rc=" + str(p.returncode))
        if p.returncode != 0:
            for line in out.splitlines():
                if line.startswith("  FAIL") or line.startswith("  - "):
                    print("      " + line.strip()[:200])

head("2. ⛔⛔ the invariant that caused the outage, checked in index.ts itself")

# The old code: `ourFault = res.status === 401 || res.status === 403 || >= 500`
# then `{ status: ourFault ? 500 : 200 }`. A 500 asks Helius to redeliver, and a
# redelivery is more load at the moment load is the problem.
t("⛔⛔ the receiver NEVER answers 5xx from the insert path - a 5xx makes "
  "Helius redeliver, and that amplification is what took out PostgREST for the "
  "whole project",
  "status: 500" not in src and "ourFault" not in src,
  "status: 500 present" if "status: 500" in src else "clean")
t("⭐ every write-failure response goes through httpStatusFor(), so the rule "
  "lives in ONE place that a test can assert on",
  src.count("httpStatusFor(") >= 3, str(src.count("httpStatusFor(")))

head("3. ⭐ the breaker is consulted BEFORE the database is touched")

# ⚠️ Anchored on the actual insert URL, not on the string "insertRows": the
# header comment now names insertRows() too, and anchoring on a name that also
# appears in prose made this assertion measure the wrong thing - it reported
# "insert at 2944", which was a position inside a COMMENT.
ins = src.index("/rest/v1/chain_events?on_conflict=signature")
t("⛔ `breaker.isOpen` is checked before the insert call appears in the file - "
  "backpressure that runs after the write is not backpressure",
  "breaker.isOpen(" in src and src.index("breaker.isOpen(") < ins,
  "isOpen at %d, insert at %d" % (src.index("breaker.isOpen("), ins))
t("⭐ and when it is open the response says how long the cooldown has left, "
  "rather than refusing without a reason",
  "cooldown_ms_remaining" in src)
t("⛔ a skipped insert is RECORDED, not silently swallowed",
  "recordSkip(" in src and "recordDrop(" in src)

head("4. ⛔ a drop is logged where a human can find it, every time")

t("⛔ every drop path writes the dropLogLine marker",
  src.count("dropLogLine(") >= 3, str(src.count("dropLogLine(")))
t("⭐ the marker has its own searchable event name",
  "chain_events_drop" in pure)
t("⛔ a PRIVILEGE failure is called out separately in the response, because it "
  "means EVERY event is being lost until a grant is fixed",
  "PRIVILEGE FAILURE" in src)

head("4b. ⛔⛔ a DUPLICATE is not a drop, and the conflict target is named")

# Found 2026-09-23 by replaying 248 real batches at the live receiver: every one
# returned 409 "duplicate key value violates unique constraint
# chain_events_sig_uniq" and every one was logged as a dropped event. The
# committed comment asserted the opposite. `Prefer: resolution=ignore-duplicates`
# does nothing on its own here, because PostgREST emits ON CONFLICT against the
# PRIMARY KEY and the conflict is a separate unique index over `signature`.
t("⛔⛔ the insert NAMES the conflict target (`on_conflict=signature`), so "
  "ignore-duplicates actually applies - without it a batch containing one "
  "already-stored signature failed atomically and took every genuinely NEW "
  "event in it down as well",
  "chain_events?on_conflict=signature" in src,
  "present" if "chain_events?on_conflict=signature" in src else "MISSING")
t("⛔ and a duplicate answers ok:true with `already_stored`, never a drop - "
  "reporting held data as lost manufactures a false alarm",
  'already_stored' in src and 'kind === "duplicate"' in src)
t("⭐ the duplicate branch records a SUCCESS on the breaker, because the "
  "database answered and is not congested",
  src.count("recordSuccess()") >= 4, str(src.count("recordSuccess()")))

head("4c. ⛔ `stored` means WRITTEN, and an unknown count is null")

t("⛔ the success path reads PostgREST's own Content-Range rather than "
  "reporting how many rows it SENT - with on_conflict working those are "
  "different numbers, and a replay reported `stored: 3` while writing nothing",
  'res.headers.get("content-range")' in src and "submitted: rows.length" in src)
t("⛔ and an unparseable header gives NULL with the reason attached, never 0 "
  "and never rows.length (standing rule 5)",
  "stored_unknown_why" in src and "inserted === null" in src)
t("⭐ count=exact is asked for, or the header would never arrive",
  "count=exact" in src)

head("5. ⛔ retrying is bounded, and only where it can possibly help")

t("⛔ only congestion is retried in process - a 401/403/400 retried has a zero "
  "success rate and is pure load",
  'if (kind === "congestion")' in src, "guard present"
  if 'if (kind === "congestion")' in src else "MISSING")
# Counted on `await insertRows()`, which is a CALL. `src.count("insertRows()")`
# also matched the declaration and a mention in a comment, so it drifted the
# moment that comment was written.
calls = src.count("await insertRows()")
t("⭐ exactly TWO calls to the insert - the first attempt and the single "
  "congestion retry, with no loop",
  calls == 2 and "while" not in src[ins - 600:ins],
  "await insertRows() appears %d times" % calls)

head("6. ⚠️ the per-isolate limit is stated, not hidden")

t("⚠️ the pure module says out loud that a per-isolate breaker is a damper "
  "and not a guarantee - the same trap the raw-payload sampler fell into, where "
  "a module-global counter could not enforce a global budget",
  "damper" in pure and "PER-ISOLATE" in pure)
t("⛔ and the self-check publishes the counters labelled as a floor",
  "backpressure: breaker.snapshot(" in src and "FLOOR" in src)

head("7. ⭐ nothing here can sign, send or move anything")

for bad in ("signTransaction", "sendTransaction", "Keypair", "secretKey",
            "setAuthority", "privateKey"):
    t("⛔ the receiver contains no `%s`" % bad, bad not in src and bad not in pure)

print("=" * 72)
print("%d/%d passed" % (PASS[0], PASS[0] + len(FAILS)))
if FAILS:
    print("\nFAILED:")
    for f in FAILS:
        print("  - " + f)
    sys.exit(1)
