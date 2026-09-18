"""
Milestone crossings, with uniqueness by construction.

WHY THIS EXISTS. On 2026-09-01 two passes an hour apart each announced "the
first realizable 3x+ on record" about different tokens. Both were wrong: 82
realizable 3x outcomes were already on record, the earliest on 2026-08-21.

The cause was not a race and not a lost write. There was no milestone state at
all. "First" was prose, re-derived by each session from whatever it happened to
be looking at, and two sessions reached the same wrong conclusion independently.
A convention that every writer must check history before claiming a first is a
convention that will be broken, because it depends on every future caller
remembering.

So a claim here is a FILE CREATED WITH O_EXCL. The operating system decides who
was first. Two concurrent passes cannot both win, not because they cooperate,
but because the second open() fails. Nothing has to remember anything.

    if milestones.claim(token, "realizable_3x", mult=4.11, symbol="NORMIE"):
        ...this really is the first time. Announce it.
    else:
        ...someone got here first. Stay quiet.

Deliberately NOT SQLite: journal.py documents that this mount fails POSIX file
locking with disk I/O errors. O_CREAT|O_EXCL is a different primitive - a single
atomic directory operation, no locking - and it works here. Verified with
concurrent processes.

Deliberately NOT Supabase-first: the crypto tables are write-only to the anon
key and no DDL credential exists on disk, so a real UNIQUE constraint in
Postgres cannot be created from here. The claim files ARE the constraint; the
ledger mirrors them for querying and can be replayed into a table later.
"""
import hashlib, json, os, re, time, glob, datetime as dt
import liveness

BASE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(BASE, "data", "milestones")
CLAIMS = os.path.join(DIR, "claims")

# Market-cap milestones Frank asked for, plus the outcome milestones that
# produced the false "first" claims. Ordered so crossing 1M also records 200k
# and 100k if they were never seen - a token can cross several between checks.
MCAP_LEVELS = [("mcap_100k", 100_000), ("mcap_200k", 200_000),
               ("mcap_1m", 1_000_000), ("mcap_5m", 5_000_000)]
MULT_LEVELS = [("realizable_2x", 2.0), ("realizable_3x", 3.0),
               ("realizable_10x", 10.0)]


def _safe(s):
    """Filesystem-safe, collision-free key part. Base58 addresses pass through
    unchanged; anything else keeps a readable stub plus a digest, so two
    different tokens can never share a claim file."""
    s = str(s or "")
    clean = re.sub(r"[^A-Za-z0-9_.-]", "", s)[:44]
    if clean == s:
        return clean
    return f"{clean[:16]}-{hashlib.blake2b(s.encode('utf-8'), digest_size=4).hexdigest()}"


def _claim_path(token, milestone):
    os.makedirs(CLAIMS, exist_ok=True)
    return os.path.join(CLAIMS, f"{_safe(token)}__{_safe(milestone)}.json")


def _ledger_path():
    os.makedirs(DIR, exist_ok=True)
    return os.path.join(DIR, dt.datetime.now(dt.timezone.utc).strftime("%Y-%m") + ".jsonl")


# LIMIT OF THE O_EXCL CLAIM, measured 2026-09-04. The lock is per FILESYSTEM.
# Two runners on two machines each create the file successfully and git has to
# arbitrate at merge time - `worthless` realizable_2x was claimed at 13:06:57Z
# locally and 18:36:45Z on the hosted runner. The rule when that happens is the
# EARLIEST crossing wins, because a claim records who crossed first, not who
# wrote first. Within one runner the guarantee still holds.
def claim(token, milestone, **meta):
    """Atomically claim (token, milestone). True ONLY for the first caller.

    Idempotent: a repeat call returns False and changes nothing, so a pass that
    is retried, or two passes running concurrently, cannot double-announce.
    """
    if not token or not milestone:
        return False
    path = _claim_path(token, milestone)
    row = {"token": token, "milestone": milestone,
           "crossed_ts": int(time.time()),
           "crossed_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           **meta}
    try:
        # The whole design is this one call. O_EXCL means the create fails if
        # the file exists, atomically, so exactly one racer proceeds.
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    except OSError:
        return False
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(row, f)
    except OSError:
        return False
    try:
        with open(_ledger_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(row, separators=(",", ":")) + "\n")
    except OSError:
        pass          # the claim file is the constraint; the ledger is a copy
    # Liveness, by family. Only reached on a genuine first claim, and there is
    # no backfill path in the code any more - a replay must never beat, because
    # a replay is not a detection. That is the whole mcap lesson.
    fam = ("mcap" if str(milestone).startswith("mcap")
           else "realizable" if str(milestone).startswith("realizable")
           else "graduated" if str(milestone) == "graduated" else None)
    if fam:
        liveness.beat(f"milestone.{fam}", detail=f"{milestone} {token}")
    return True


def claimed(token, milestone):
    return os.path.exists(_claim_path(token, milestone))


def crossings(milestone=None):
    """Every crossing on record, newest last. Read this before saying 'first'."""
    out = []
    for fp in sorted(glob.glob(os.path.join(DIR, "*.jsonl"))):
        for line in open(fp, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if milestone is None or r.get("milestone") == milestone:
                # Provenance, every read. A caller that forgets to ask still
                # gets told which rows are replay.
                r["provenance"] = ("backfill"
                                   if r.get("crossed_ts", 0) <= BACKFILL_EPOCH
                                   else "live")
                out.append(r)
    out.sort(key=lambda r: r.get("crossed_ts", 0))
    return out


# ---------------------------------------------------------------------------
# BACKFILL IS NOT DETECTION.
#
# This module was created 2026-09-02 04:28Z and its first act was to replay
# history. 1,465 claim files were written in that ONE MINUTE - every mcap
# crossing on record among them (574 x 100k, 403 x 200k, 225 x 1m, 127 x 5m).
# Those are a reconstruction from stored observations, not events this system
# noticed as they happened.
#
# It is worse than "old". The mcap tiers never fired at all: the call site in
# journal.record_outcome passed mcap=None from the day the module shipped until
# 2026-09-07. So 100% of the mcap record is replay, and none of it is evidence
# that the tracker has ever worked. Read as live signal it would say the
# opposite of the truth.
#
# Recorded HERE, on read, rather than by rewriting the ledger - the same reason
# journal.outcomes() annotates instead of editing. Nothing is ever deleted, and
# a row's meaning can change as we learn how it was produced.
#
# MEASURED BOUNDARY, not a guess. Backfilled claims carry crossed_ts from
# 2026-08-21 03:38:47Z to 2026-09-02 04:06:40Z. The first claim written after
# that minute crossed at 2026-09-02 06:06:35Z. A two-hour gap separates them,
# so a timestamp cutoff placed inside the gap is exact.
BACKFILL_EPOCH = int(dt.datetime(2026, 9, 2, 5, 0,
                                 tzinfo=dt.timezone.utc).timestamp())


def live_crossings(milestone=None):
    """Crossings this system DETECTED as they happened. The citable set.

    Everything else is replay and must never be quoted as a detection, the way
    journal.verified_outcomes() excludes pre-epoch wins.
    """
    return [r for r in crossings(milestone) if r.get("provenance") == "live"]


def is_first(milestone):
    """True only if nothing has ever crossed this milestone."""
    return not crossings(milestone)


def check_outcome(token, symbol, mult, realizable, mcap=None, **at_crossing):
    """Evaluate every milestone this outcome crosses. Returns the NEW ones.

    `at_crossing` is what the SAME check measured - exit depth, whether the
    quote side was seen, the realizable verdict, the pool priced - and is
    written onto every claim it makes. A crossing that cannot be verified from
    its own row sends the reader to a join, and the join found a depth read up
    to 16.7 hours stale (site/api/feed.mjs, 2026-09-18).
    """
    new = []
    if realizable and mult:
        for name, level in MULT_LEVELS:
            if mult >= level and claim(token, name, symbol=symbol,
                                       value=round(mult, 4), kind="multiple",
                                       **at_crossing):
                new.append(name)
    if mcap:
        for name, level in MCAP_LEVELS:
            if mcap >= level and claim(token, name, symbol=symbol,
                                       value=round(mcap, 2), kind="mcap",
                                       **at_crossing):
                new.append(name)
    return new


def stats():
    c = crossings()
    by = {}
    for r in c:
        by[r["milestone"]] = by.get(r["milestone"], 0) + 1
    live = [r for r in c if r.get("provenance") == "live"]
    by_live = {}
    for r in live:
        by_live[r["milestone"]] = by_live.get(r["milestone"], 0) + 1
    return {"total": len(c), "distinct_tokens": len({r["token"] for r in c}),
            "by_milestone": by,
            # The number that means something. "total" includes the 2026-09-02
            # backfill and will overstate every tier it touched.
            "live": len(live), "by_milestone_live": by_live,
            "backfill": len(c) - len(live)}


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    s = stats()
    print(f"\n  MILESTONES  {s['total']} crossings, {s['distinct_tokens']} tokens")
    for k, v in sorted(s["by_milestone"].items()):
        first = crossings(k)[0] if crossings(k) else None
        print(f"    {k:<16} {v:>5}   first: {first['crossed_at'] if first else '-'}"
              f" {str(first.get('symbol')) if first else ''}")
    print()
