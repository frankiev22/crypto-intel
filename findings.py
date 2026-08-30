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
import json, os, re, sys, datetime as dt

import config  # loads .env
import notify

DIR = "data/findings"
SEEN = os.path.join(DIR, "_seen.json")


def _slug(s):
    """Normalise to a class token. Digits go, so severity numbers and dollar
    amounts do not each look like a brand new problem."""
    s = re.sub(r"\d+", "", str(s or "")).lower()
    return re.sub(r"[^a-z]+", "-", s).strip("-") or "unknown"


def defect_class(kind, key):
    return f"{_slug(kind)}:{_slug(key)}"


def _load_seen():
    try:
        return json.load(open(SEEN))
    except Exception:
        return {}


def _save_seen(d):
    os.makedirs(DIR, exist_ok=True)
    tmp = SEEN + ".tmp"
    json.dump(d, open(tmp, "w"), indent=1)
    os.replace(tmp, SEEN)


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
ALWAYS_PING = {"collector-zero"}


def record(kind, key, summary, detail=None, allow_discord=True, always_ping=None):
    """Append a finding. Returns (path, defect_class, pinged_bool, why)."""
    os.makedirs(DIR, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc)
    cls = defect_class(kind, key)
    path = today_path(now.strftime("%Y-%m-%d"))

    new_file = not os.path.exists(path)
    with open(path, "a", encoding="utf-8") as f:
        if new_file:
            f.write(f"# Findings {now.strftime('%Y-%m-%d')}\n\n")
        f.write(f"## {now.strftime('%H:%M:%S')} UTC · {kind} · {key}\n\n")
        f.write(f"{summary}\n\n")
        if detail:
            f.write(f"```\n{str(detail).strip()[:4000]}\n```\n\n")

    seen = _load_seen()
    first_time = cls not in seen
    if first_time:
        seen[cls] = {"first_seen": now.isoformat(timespec="seconds"),
                     "count": 1, "example": f"{kind}: {key}"}
    else:
        seen[cls]["count"] = seen[cls].get("count", 1) + 1
        seen[cls]["last_seen"] = now.isoformat(timespec="seconds")
    _save_seen(seen)

    if always_ping is None:
        always_ping = kind in ALWAYS_PING
    if not first_time and not always_ping:
        return path, cls, False, f"class already reported {seen[cls]['count']}x, file only"
    if not allow_discord:
        return path, cls, False, "discord suppressed by caller"

    if always_ping and not first_time:
        head = "**" + kind + "**" + chr(10) + str(key) + chr(10) + summary + chr(10)
        body = head + ("_Occurrence %d of this class. This class always pings: "
                       "it means the collector produced nothing._"
                       % seen[cls].get("count", 1))
    elif always_ping:
        head = "**" + kind + "**" + chr(10) + str(key) + chr(10) + summary + chr(10)
        body = head + "_This class always pings: it means the collector produced nothing._"
    else:
        head = "**New finding: " + kind + "**" + chr(10) + str(key) + chr(10) + summary + chr(10)
        body = head + ("_First time this class has appeared. Repeats go to "
                       + os.path.basename(path) + " silently._")
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
    path, cls, pinged, why = record(kind, key, summary, opt("--detail"))
    print(f"  recorded -> {path}")
    print(f"  class    -> {cls}")
    print(f"  discord  -> {why}")


if __name__ == "__main__":
    main()
