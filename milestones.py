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
                out.append(r)
    out.sort(key=lambda r: r.get("crossed_ts", 0))
    return out


def is_first(milestone):
    """True only if nothing has ever crossed this milestone."""
    return not crossings(milestone)


def check_outcome(token, symbol, mult, realizable, mcap=None):
    """Evaluate every milestone this outcome crosses. Returns the NEW ones."""
    new = []
    if realizable and mult:
        for name, level in MULT_LEVELS:
            if mult >= level and claim(token, name, symbol=symbol,
                                       value=round(mult, 4), kind="multiple"):
                new.append(name)
    if mcap:
        for name, level in MCAP_LEVELS:
            if mcap >= level and claim(token, name, symbol=symbol,
                                       value=round(mcap, 2), kind="mcap"):
                new.append(name)
    return new


def stats():
    c = crossings()
    by = {}
    for r in c:
        by[r["milestone"]] = by.get(r["milestone"], 0) + 1
    return {"total": len(c), "distinct_tokens": len({r["token"] for r in c}),
            "by_milestone": by}


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
