"""
Where scheduled sessions put things Frank needs to know.

The old instruction told cron sessions to call SendUserMessage. That tool does
not exist in the cron sandbox, so every finding for two days went nowhere except
a transcript nobody reads. This replaces it with two sinks that do exist:

  1. A daily markdown file at data/findings/YYYY-MM-DD.md. Everything lands
     here, always. This is the record.
  2. Discord, but ONLY the first time a given DEFECT CLASS is seen. Frank
     explicitly rejected hourly pings and they must not creep back.

"Defect class" is the point. A scanner hit on FOO and a scanner hit on BAR are
the same class (scanner-hit) and ping once; a ConnectionError and a RateLimit
error are different classes and each ping once. The class deliberately strips
digits so "scored 92" and "scored 87" collapse together.

    from findings import record
    record("scanner-hit", "APOSHLD", "scored 92", "liq $87k, 24h vol $42k, 0.1h old")
    record("collector-error", "ConnectionError", "collect.py died on the solana pass")

    python findings.py --kind collector-error --key ConnectionError \
        --summary "collect.py died" --detail "traceback ..."
    python findings.py --today          # print today's file
    python findings.py --classes        # what has already pinged
"""
import hashlib, json, os, re, sys, time, unicodedata, datetime as dt

import config  # loads .env
import notify

import safeload

DIR = "data/findings"
SEEN = os.path.join(DIR, "_seen.json")


# How many distinct raw keys may share one slug before that is a bug signal.
# A dedupe key colliding is not a rare edge: _slug collapsed 181 distinct
# non-ASCII symbols across 255 tokens into the single bucket "unknown", and
# that bucket swallowed the best outcome of 2026-08-30 - a 56.5x, alive, with
# liquidity up 658% - which never pinged because something else had already
# claimed "unknown" days earlier.
# Discord budget per rolling hour.
#
# The 85 threshold fires 3-9 hits a pass and one hour on 2026-09-01 sent twelve
# pings. Frank rejected hourly noise explicitly and it crept back. Fixing
# _slug makes this worse, not better: names that were silently absorbed into
# the "unknown" bucket now each announce themselves.
#
# So routine findings share an hourly budget and the rest go to the file, which
# is where the full record has always lived. ALWAYS_PING classes ignore the
# budget entirely - a collector that produced nothing, or a dedupe key that is
# eating alerts, must never be rate-limited into silence.
PING_BUDGET_PER_HOUR = 4
BUDGET_FILE = os.path.join(DIR, "_ping_budget.json")


def _budget_spend(lane="routine", significance=None):
    """(allowed, spent, remaining) for this LANE in the current rolling hour.

    Two rules beyond the count:

    - Lanes are independent. A flood of scanner hits cannot exhaust the lane a
      confirmed outcome arrives in.
    - Inside a lane, a finding MORE significant than anything already sent this
      hour is allowed even when the count is spent. This is how "rank by value,
      not arrival time" survives in a streaming system where earlier pings
      cannot be recalled: a 6x can always break through a wall of 1.1x, but a
      second 6x cannot.
    """
    now = time.time()
    try:
        with open(BUDGET_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        data = {}
    # Migrate the old flat list of timestamps into the routine lane.
    if isinstance(data, list):
        data = {"routine": [[t, None] for t in data]}
    if not isinstance(data, dict):
        data = {}

    cap = LANE_BUDGET.get(lane, LANE_BUDGET["routine"])
    entries = [e for e in data.get(lane, [])
               if isinstance(e, (list, tuple)) and len(e) == 2 and now - e[0] < 3600]
    spent = len(entries)

    allowed = spent < cap
    if not allowed and significance is not None:
        best = max((e[1] for e in entries if e[1] is not None), default=None)
        if best is None or significance > best:
            allowed = True   # more valuable than anything already sent

    if not allowed:
        data[lane] = entries
        _save_budget(data)
        return False, spent, 0

    entries.append([now, significance])
    data[lane] = entries
    _save_budget(data)
    return True, len(entries), max(0, cap - len(entries))


def _save_budget(data):
    os.makedirs(DIR, exist_ok=True)
    try:
        tmp = BUDGET_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, BUDGET_FILE)
    except OSError:
        pass

SLUG_COLLISION_LIMIT = 5
_guarding = False


def _slug(s):
    """Normalise to a class token, WITHOUT collapsing non-ASCII to nothing.

    The old version ran re.sub(r"[^a-z]+", "-", ...) and returned "unknown" for
    any name with no Latin letters. Every coin in the Justin Sun / Jing Tian
    narrative is Chinese-named, so the four biggest movers of 2026-08-30 all
    deduped against each other and against 177 unrelated tokens.

    Chosen fix: NFKC-normalise, keep whatever ASCII skeleton exists, and append
    a short BLAKE2b digest of the normalised original whenever it contained
    non-ASCII.

      - NOT transliteration: that needs a third-party package, and this
        codebase is deliberately stdlib-only. The hosted runner has no pip
        install step, and adding one to alert on a Chinese ticker is a bad
        trade.
      - NOT the contract address: the slug's job is repeat-suppression by
        defect CLASS, and callers pass the symbol on purpose. Hashing the
        symbol keeps that meaning while making distinct names distinct.
      - Digits still go, so "scored 92" and "scored 87" still collapse.

    Pure-ASCII keys slug EXACTLY as before, so the existing _seen.json history
    stays valid and nothing re-pings on deploy.
    """
    raw = unicodedata.normalize("NFKC", str(s or ""))
    stripped = re.sub(r"\d+", "", raw).lower()
    ascii_part = re.sub(r"[^a-z]+", "-", stripped).strip("-")
    if all(ord(c) < 128 for c in raw):
        return ascii_part or "unknown"
    # Non-ASCII present: make it distinct and stable across runs and machines.
    # hashlib, not hash(), because PYTHONHASHSEED randomises the builtin.
    digest = hashlib.blake2b(raw.encode("utf-8"), digest_size=3).hexdigest()
    return f"{ascii_part}-{digest}" if ascii_part else f"u-{digest}"


def defect_class(kind, key):
    return f"{_slug(kind)}:{_slug(key)}"


def _collision_guard(cls, seen):
    """One slug covering many distinct raw keys means the slug function is
    losing information, and everything after the first key goes silent.

    This fires ONCE per class. It is deliberately a ping and not a log line:
    the failure it detects is itself a failure to ping, so writing it to the
    file the alerts were already not reaching would be circular.
    """
    global _guarding
    if _guarding:
        return
    meta = seen.get(cls) or {}
    keys = meta.get("keys") or []
    if len(keys) <= SLUG_COLLISION_LIMIT or meta.get("collision_reported"):
        return
    _guarding = True
    try:
        meta["collision_reported"] = True
        _save_seen(seen)
        sample = ", ".join(keys[:8])
        record("slug-collision", cls,
               f"{len(keys)} distinct keys share the dedupe slug {cls!r}",
               f"Everything after the first is suppressed and never pings. "
               f"Sample keys: {sample}. Check findings._slug - it is dropping "
               f"the characters that make these distinct.",
               always_ping=True)
    finally:
        _guarding = False


def _load_seen():
    """Absent -> {}. Present-but-unreadable -> safeload.LoadFailed, NOT {}.

    This used to be a bare `except: return {}` feeding an atomic write, which
    made any transient read failure permanently delete all 852 dedup entries.
    See safeload.py for why absent and unreadable must not answer alike.
    """
    return safeload.load_json(SEEN)


def _save_seen(d):
    # allow_empty stays False: this file is only ever added to, so an empty
    # write is always a bug, never an intention.
    safeload.save_json(SEEN, d)


def today_path(day=None):
    day = day or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    return os.path.join(DIR, f"{day}.md")


# Classes that must ping EVERY time, not just the first.
#
# Repeat suppression is right for noise and wrong for silence. On 2026-08-30
# collector-error:timeouterror had fired SIX times since 08-24 and pinged once,
# because the class was already in _seen.json. Every one of those was an hour
# with zero observations. The one condition that means "we collected nothing"
# was the one configured not to tell anyone.
#
# A component that cannot tell "found nothing" from "did not look" must fail
# loudly, every time, on the channel Frank actually reads.
ALWAYS_PING = {"collector-zero", "slug-collision"}

# SEPARATE BUDGETS PER LANE. Measured 2026-09-06 across every finding ever
# recorded: scanner-hit is 484 classes and 645 fires (59.2% of all traffic),
# outcome-x is 225 classes and 358 fires (32.9%). They shared one 4-per-hour
# budget, and because the scan stage runs before the outcome stage, routine
# scanner hits consumed the quota first and outcomes lost on ARRIVAL ORDER -
# the worst possible tiebreak.
#
# The cost was exact. On 2026-09-05 the system produced its first three clean,
# non-quarantined, realizable 3x+ outcomes - POOD 6.39x, FLORK 5.49x,
# CBULLNEO 3.43x - and NONE of them reached Frank. The validation layer worked
# and the notification layer threw the results away.
#
# So a lane cannot starve another lane. Routine noise stays rationed; the lanes
# that carry meaning do not compete with it.
LANES = {
    "scanner-hit": "routine",
    "outcome": "outcome",
    "milestone": "outcome",
    "lookup-outage": "health",
    "collector-error": "health",
    "horizon-drift": "health",
    "reporting-path": "health",
    # A feed going quiet is a collection failure, not a market event. It belongs
    # in the health lane so it gets duration escalation - a source that has been
    # dead for two days must ping louder, not go silent because the class is
    # already in _seen.json. Keyed per OUTLET so four independent feeds cannot
    # collapse into one suppressed alert.
    "news-stale": "health",
    # The detector's own shelf life. The template pools share depth/liq to five
    # decimals, which is one operator running one script; when that constant
    # moves, recall falls and nothing else would say so.
    "detector-drift": "health",
    "correction": "outcome",
}
LANE_BUDGET = {
    "routine": int(os.environ.get("CRYPTO_BUDGET_ROUTINE", "4")),
    "outcome": int(os.environ.get("CRYPTO_BUDGET_OUTCOME", "12")),
    "health": int(os.environ.get("CRYPTO_BUDGET_HEALTH", "6")),
}

# A finding carrying at least this much significance is never rationed. For an
# outcome the significance IS the multiple, so a confirmed 3x always pings.
SIGNIFICANCE_ALWAYS = float(os.environ.get("CRYPTO_SIGNIFICANCE_ALWAYS", "3.0"))


def lane_of(kind):
    k = (kind or "").strip().lower()
    if k in LANES:
        return LANES[k]
    # outcome-3x, outcome-10x, outcome-anything
    for prefix, lane in LANES.items():
        if k.startswith(prefix):
            return lane
    return "routine"

# DEDUPLICATION SUPPRESSES REPETITION. IT MUST NEVER SUPPRESS DURATION.
#
# Measured 2026-09-05: Dexscreener's 168h lookups were on their second day of
# failure - 0% resolution twice, 1-6% for most of the day - and the whole
# two-day outage produced ONE ping, because the class was already in _seen.json
# and the 4-per-hour budget swallowed the rest. A defect that persists is a
# different and worse event than a defect that repeats, and the machinery could
# not tell them apart.
#
# So: once a class has been firing for longer than ESCALATE_AFTER_H, it
# re-alerts on its own schedule, bypassing both first-time suppression and the
# hourly budget, and it says how long it has been going and how many times.
# The interval does not shrink - the escalation is in the wording and in the
# fact that it arrives at all, not in volume.
ESCALATE_AFTER_H = float(os.environ.get("CRYPTO_ESCALATE_AFTER_H", "6"))
RE_ALERT_EVERY_H = float(os.environ.get("CRYPTO_RE_ALERT_EVERY_H", "6"))


def _parse_ts(v):
    try:
        return dt.datetime.fromisoformat(v)
    except (TypeError, ValueError):
        return None


def _duration_escalation(entry, now):
    """(should_ping, hours_running, nth_escalation) for a class that persists."""
    first = _parse_ts(entry.get("first_seen"))
    if not first:
        return False, 0.0, 0
    if first.tzinfo is None:
        first = first.replace(tzinfo=dt.timezone.utc)
    running = (now - first).total_seconds() / 3600.0
    if running < ESCALATE_AFTER_H:
        return False, running, 0
    last = _parse_ts(entry.get("last_escalated"))
    if last is not None:
        if last.tzinfo is None:
            last = last.replace(tzinfo=dt.timezone.utc)
        if (now - last).total_seconds() / 3600.0 < RE_ALERT_EVERY_H:
            return False, running, entry.get("escalations", 0)
    return True, running, entry.get("escalations", 0) + 1


def record(kind, key, summary, detail=None, allow_discord=True, always_ping=None,
           significance=None):
    """Append a finding. Returns (path, defect_class, pinged_bool, why)."""
    os.makedirs(DIR, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc)
    cls = defect_class(kind, key)
    path = today_path(now.strftime("%Y-%m-%d"))

    new_file = not os.path.exists(path)
    with open(path, "a", encoding="utf-8") as f:
        if new_file:
            # STATE THE TIMEZONE IN THE FILE. The filename, the header and every
            # entry here are UTC. A daily summary written against ET counted
            # CWINK's 6h ping (2026-09-07 13:17 UTC) and its 24h ping
            # (2026-09-08 05:36 UTC) as two separate clean wins.
            f.write(f"# Findings {now.strftime('%Y-%m-%d')} (UTC)" + chr(10) + chr(10))
            f.write("All timestamps in this file, and the filename, are UTC. "
                    "Count wins by CONTRACT ADDRESS, not by entry: one token "
                    "pings once per horizon and each ping says which." + chr(10) + chr(10))
        f.write(f"## {now.strftime('%H:%M:%S')} UTC · {kind} · {key}\n\n")
        f.write(f"{summary}\n\n")
        if detail:
            f.write(f"```\n{str(detail).strip()[:4000]}\n```\n\n")

    # A dedup file we cannot read must not be overwritten, and a finding must
    # not be silently swallowed because the dedup state is unavailable. So an
    # unreadable file degrades to "report it, write nothing" - noisy, not lossy.
    seen, seen_ok = {}, True
    try:
        seen = _load_seen()
    except safeload.LoadFailed as e:
        seen_ok = False
        print(f"  findings: dedup state unreadable, NOT writing it - {e}")
    first_time = cls not in seen
    if first_time:
        seen[cls] = {"first_seen": now.isoformat(timespec="seconds"),
                     "count": 1, "example": f"{kind}: {key}",
                     "keys": [str(key)]}
    else:
        seen[cls]["count"] = seen[cls].get("count", 1) + 1
        seen[cls]["last_seen"] = now.isoformat(timespec="seconds")
        ks = seen[cls].setdefault("keys", [])
        if str(key) not in ks and len(ks) < 64:
            ks.append(str(key))
    if seen_ok:
        _save_seen(seen)
        # A dedupe key that collides is a defect, not traffic. Say so once.
        _collision_guard(cls, seen)

    if always_ping is None:
        # A verified outcome big enough to matter is not routine traffic. This
        # is the positive-side twin of the duration escalation below: suppress
        # repetition, never suppress significance.
        always_ping = (kind in ALWAYS_PING
                       or (significance is not None
                           and significance >= SIGNIFICANCE_ALWAYS))

    # A class that has been failing for hours escalates on duration, whatever
    # the dedupe and budget rules would otherwise do with it.
    escalate, running_h, nth = (False, 0.0, 0)
    if not first_time:
        escalate, running_h, nth = _duration_escalation(seen[cls], now)
        if escalate:
            seen[cls]["last_escalated"] = now.isoformat(timespec="seconds")
            seen[cls]["escalations"] = nth
            _save_seen(seen)

    if not seen_ok:
        always_ping = True            # cannot dedupe -> must not suppress
    if seen_ok and not first_time and not always_ping and not escalate:
        return path, cls, False, f"class already reported {seen[cls]['count']}x, file only"
    if not allow_discord:
        return path, cls, False, "discord suppressed by caller"

    # Routine findings share an hourly budget; critical classes and anything
    # escalating on duration bypass it.
    lane = lane_of(kind)
    if not always_ping and not escalate:
        ok_budget, spent, left = _budget_spend(lane, significance)
        if not ok_budget:
            return (path, cls, False,
                    f"{lane} lane budget spent ({spent}/{LANE_BUDGET.get(lane)}), "
                    f"file only - full record is in {os.path.basename(path)}")

    if escalate:
        hrs = int(running_h)
        head = ("**STILL FAILING: " + kind + "**" + chr(10) + str(key) + chr(10)
                + summary + chr(10))
        body = head + ("_This is not a repeat, it is a duration. The class has "
                       "been failing for %dh %dm across %d occurrences, first "
                       "seen %s. Escalation %d; the next one follows in %gh if "
                       "it is still failing._"
                       % (hrs, int((running_h - hrs) * 60),
                          seen[cls].get("count", 1),
                          seen[cls].get("first_seen", "?"), nth,
                          RE_ALERT_EVERY_H))
    elif always_ping and not first_time:
        head = "**" + kind + "**" + chr(10) + str(key) + chr(10) + summary + chr(10)
        body = head + ("_Occurrence %d. This class always pings - every "
                       "occurrence matters._" % seen[cls].get("count", 1))
    elif always_ping:
        head = "**" + kind + "**" + chr(10) + str(key) + chr(10) + summary + chr(10)
        body = head + "_This class always pings - every occurrence matters._"
    else:
        head = "**New finding: " + kind + "**" + chr(10) + str(key) + chr(10) + summary + chr(10)
        body = head + ("_First time this class has appeared. Repeats go to "
                       + os.path.basename(path) + " silently._")
    # A significant finding's DETAIL is the part worth reading - the contract
    # address, the exit depth, the real elapsed time. Sending only the summary
    # put all of that in a file nobody opens.
    if significance is not None and detail:
        body = body + chr(10) + chr(10) + "```" + chr(10) + str(detail)[:1200] + chr(10) + "```"
    ok = notify.send(content=body)
    return path, cls, bool(ok), ("pinged Discord" if ok else "Discord send failed, file written")


def main():
    a = sys.argv[1:]
    if "--today" in a:
        p = today_path()
        print(open(p, encoding="utf-8").read() if os.path.exists(p) else f"(nothing in {p})")
        return
    if "--classes" in a:
        seen = _load_seen()
        if not seen:
            print("(no defect classes recorded yet)"); return
        for cls, meta in sorted(seen.items()):
            print(f"  {cls:<40} x{meta.get('count',1):<4} first {meta.get('first_seen','?')}")
        return

    def opt(name, default=None):
        return a[a.index(name) + 1] if name in a and a.index(name) + 1 < len(a) else default

    kind, key, summary = opt("--kind"), opt("--key"), opt("--summary")
    if not (kind and key and summary):
        print(__doc__); sys.exit(2)
    sig = opt("--significance")
    try:
        sig = float(sig) if sig is not None else None
    except ValueError:
        sig = None
    path, cls, pinged, why = record(kind, key, summary, opt("--detail"),
                                    significance=sig)
    print(f"  recorded -> {path}")
    print(f"  class    -> {cls}")
    print(f"  lane     -> {lane_of(kind)}")
    print(f"  discord  -> {why}")


if __name__ == "__main__":
    main()
