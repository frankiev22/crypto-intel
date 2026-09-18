"""Exit depth AT the crossing, recovered for crossings claimed before it was stored.

Run: python crossingdepth.py        (idempotent - appends only what is missing)

⛔ WHY. mcap and multiple milestones are claimed inside journal.record_outcome(),
on the horizon re-check, and that same call measures exit depth. Until
2026-09-18 the depth went into the outcome row and NOT onto the claim, so the
site could only verify a crossing by joining the latest scanner observation -
which was 7.8 to 16.7 hours older than the crossing on every one of the 12 it
checked. It verified 0 of 12, correctly: a depth read before a crossing blesses
nothing (standing rule 4).

⭐ THE MEASUREMENT WAS NEVER LOST, ONLY UNLINKED. record_outcome() sets
`checked_ts = int(time.time())`, appends the outcome row, and claims the
milestone in the same call, so the claim's `crossed_ts` lands 0-2 seconds after
the row it came from. Measured over every live crossing on 2026-09-18:

    09-09 onward   926 of 926 join to exactly one outcome row, delta 0-2s
                   (one at 5s), and no crossing has two candidate rows at the
                   claiming second - so there is nothing to choose between
    09-02 .. 09-08 643 of 814 do NOT join. Those predate the mcap=None fix
                   (journal.py, 2026-09-07): they were never claimed at a real
                   measurement, so there is no depth to recover. They are
                   counted here and left alone.

JOIN_WINDOW_S is the only parameter and it is not a threshold on the data: it is
the width of one function call. The recovered row records its own delta, so a
reader can see it is 0-2s rather than take it on trust.

⛔ Forward, from 2026-09-18, the claim carries these fields itself
(milestones.check_outcome(**at_crossing)). This file is only for the past, and it
is append-only: a key already present is never rewritten (standing rule 8).
"""
import collections
import glob
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
MS_DIR = os.path.join(BASE, "data", "milestones")
OUT_DIR = os.path.join(BASE, "data", "outcomes")
RECOVERED = os.path.join(BASE, "data", "milestones", "depth_at_crossing.jsonl")

# milestones.py BACKFILL_EPOCH, 2026-09-02 05:00Z. Anything at or before it is a
# replay of history, not a detection, and has no crossing-time measurement.
BACKFILL_EPOCH = 1788325200
JOIN_WINDOW_S = 5


def _jsonl(pattern):
    for f in sorted(glob.glob(pattern)):
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except ValueError:
                    continue


def _key(token, milestone):
    return f"{token}|{milestone}"


def recover(ms_dir=None, out_dir=None, dest=None, write=True):
    """Returns a report dict. Appends recovered rows to `dest` unless write=False."""
    ms_dir, out_dir, dest = ms_dir or MS_DIR, out_dir or OUT_DIR, dest or RECOVERED
    claims = [r for r in _jsonl(os.path.join(ms_dir, "*.jsonl"))
              if r.get("kind") in ("mcap", "multiple")
              and (r.get("crossed_ts") or 0) > BACKFILL_EPOCH]
    by_tok = collections.defaultdict(list)
    for o in _jsonl(os.path.join(out_dir, "*.jsonl")):
        if o.get("token") and o.get("checked_ts") is not None:
            by_tok[o["token"]].append(o)
    have = set()
    if os.path.exists(dest):
        have = {_key(r.get("token"), r.get("milestone")) for r in _jsonl(dest)}

    rep = collections.Counter()
    rows = []
    for c in claims:
        if "exit_depth_at_crossing" in c:
            rep["carries_it_already"] += 1          # a forward claim
            continue
        k = _key(c["token"], c["milestone"])
        if k in have:
            rep["already_recovered"] += 1
            continue
        cand = [o for o in by_tok.get(c["token"], [])
                if 0 <= c["crossed_ts"] - o["checked_ts"] <= JOIN_WINDOW_S]
        if not cand:
            rep["no_measurement_at_crossing"] += 1
            continue
        top = max(o["checked_ts"] for o in cand)
        at = [o for o in cand if o["checked_ts"] == top]
        vals = {(o.get("exit_depth_usd"), o.get("depth_unmeasured"),
                 o.get("realizable"), o.get("exit_pair")) for o in at}
        if len(vals) != 1:
            # Two rows in the claiming second that disagree. We cannot know which
            # one made the claim, so we do not pick. None observed 2026-09-18.
            rep["ambiguous"] += 1
            continue
        o = at[0]
        rows.append({"token": c["token"], "milestone": c["milestone"],
                     "crossed_ts": c["crossed_ts"],
                     "exit_depth_at_crossing": o.get("exit_depth_usd"),
                     "depth_unmeasured_at_crossing": o.get("depth_unmeasured"),
                     "realizable_at_crossing": o.get("realizable"),
                     "exit_pair_at_crossing": o.get("exit_pair"),
                     "horizon_h": o.get("horizon_h"),
                     "outcome_checked_ts": o["checked_ts"],
                     "delta_s": c["crossed_ts"] - o["checked_ts"],
                     "provenance": "recovered"})
        rep["recovered"] += 1
    if write and rows:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "a", encoding="utf-8", newline="\n") as f:
            for r in rows:
                f.write(json.dumps(r, separators=(",", ":")) + "\n")
    rep["claims_considered"] = len(claims)
    rep["deltas"] = dict(collections.Counter(r["delta_s"] for r in rows))
    return dict(rep)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print(json.dumps(recover(), indent=1))
