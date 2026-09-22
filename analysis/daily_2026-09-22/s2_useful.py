"""Section 2: is it useful? Trailing 24h ending at the run timestamp.

Union of the desktop working tree and origin/master (the runner's rows), so
both collectors count. Writes s2_results.json.
"""
import collections
import datetime as dt
import glob
import io
import json
import math
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
os.chdir(ROOT)
RUN_TS = float(sys.argv[1]) if len(sys.argv) > 1 else time.time()
T0 = RUN_TS - 86400
UNATT = ("scheduled", "runner")


def wilson(k, n, z=1.96):
    if not n:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(100 * (c - h), 2), round(100 * (c + h), 2))


def union_lines(paths):
    seen = {}
    for p in paths:
        texts = []
        try:
            texts.append(io.open(p, encoding="utf-8").read())
        except FileNotFoundError:
            pass
        r = subprocess.run(["git", "show", f"origin/master:{p.replace(os.sep, '/')}"],
                           capture_output=True)
        if r.returncode == 0:
            texts.append(r.stdout.decode("utf-8", "replace"))
        for t in texts:
            for l in t.splitlines():
                if l.strip():
                    seen[l.strip()] = 1
    out = []
    for l in seen:
        try:
            out.append(json.loads(l))
        except ValueError:
            pass
    return out


days = ["2026-09-21", "2026-09-22"]
cov = union_lines([f"data/coverage/{d}.jsonl" for d in days])
obs_all = union_lines(sorted(glob.glob("data/observations/2026-0*.jsonl")))
ms = union_lines(["data/milestones/2026-09.jsonl"])
grads = union_lines(["data/graduations/2026-09.jsonl"])
R = {"window": [T0, RUN_TS]}

# ---- coverage hours
hours = {h: set() for h in range(24)}
for c in cov:
    ts = c.get("ts") or 0
    if not (T0 <= ts <= RUN_TS) or c.get("origin") not in UNATT:
        continue
    b = int((ts - T0) // 3600)
    if 0 <= b < 24:
        hours[b].add((c.get("kind"), str(c.get("stage"))))
scan_h = sum(1 for h in hours.values()
             if any(k in ("pass_complete", "pass_short") and s in ("scan", "full") for k, s in h))
out_h = {st: sum(1 for h in hours.values()
                 if any(k in ("pass_complete", "pass_short") and s in (st, "full") for k, s in h))
         for st in ("1", "6", "24", "168", "graduations", "universe", "market")}
aborted = collections.Counter(str(c.get("stage")) for c in cov
                              if c.get("kind") == "aborted_pass" and T0 <= (c.get("ts") or 0) <= RUN_TS)
R["coverage"] = {"hours_with_unattended_scan": scan_h, "hours_by_stage": out_h,
                 "aborted_by_stage": dict(aborted)}

# ---- observations
obs = [o for o in obs_all if T0 <= (o.get("ts") or 0) <= RUN_TS and o.get("token")]
by = collections.defaultdict(list)
for o in obs:
    by[o["token"]].append(o)
passed = {t for t, rs in by.items() if any(r.get("passed") for r in rs)}
g100 = {t for t, rs in by.items() if any(r.get("grade") == 100 for r in rs)}
s100 = {t for t, rs in by.items() if any(r.get("score") == 100 for r in rs)}
R["observations"] = {"rows": len(obs), "contracts": len(by), "passed_filter": len(passed),
                     "grade_100": len(g100), "score_100": len(s100)}

# ---- graduation coverage: ledger graduations in window, seen by our journal ever
ever = {o.get("token") for o in obs_all if o.get("token")}
gw = {g["mint"] for g in grads if g.get("mint") and T0 <= (g.get("block_time") or 0) <= RUN_TS}
seen_g = gw & ever
R["graduation_coverage"] = {"graduations": len(gw), "in_journal": len(seen_g),
                            "pct": round(100 * len(seen_g) / len(gw), 2) if gw else None,
                            "wilson": wilson(len(seen_g), len(gw))}

# ---- launch alerts reconstructed from scan passes
scan_passes = [c for c in cov if c.get("kind") in ("pass_complete", "pass_short")
               and str(c.get("stage")) in ("scan", "full") and T0 <= (c.get("ts") or 0) <= RUN_TS]
R["launch_alerts"] = {"scan_passes": len(scan_passes),
                      "passes_with_alert": sum(1 for c in scan_passes
                                               if ((c.get("progress") or {}).get("passed") or c.get("passed") or 0) > 0),
                      "contracts_alerted": len(passed)}

# ---- findings recorded in window
kinds = collections.Counter()
fkeys = collections.defaultdict(set)
for d in days:
    p = f"data/findings/{d}.md"
    txt = []
    try:
        txt.append(io.open(p, encoding="utf-8").read())
    except FileNotFoundError:
        pass
    r = subprocess.run(["git", "show", f"origin/master:{p}"], capture_output=True)
    if r.returncode == 0:
        txt.append(r.stdout.decode("utf-8", "replace"))
    blocks = {}
    for t in txt:
        for m in re.finditer(r"(?m)^## (\d\d:\d\d:\d\d) UTC . ([a-z0-9-]+) . (.+)$", t):
            ts = dt.datetime.strptime(d + " " + m.group(1), "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=dt.timezone.utc).timestamp()
            blocks[(ts, m.group(2), m.group(3).strip())] = 1
    for ts, k, key in blocks:
        if T0 <= ts <= RUN_TS:
            kinds[k] += 1
            fkeys[key].add(ts)
R["findings"] = dict(kinds)

# ---- the miss count: liquidity-gated $1M / $5M crossings with no prior alert
first_pass_ts = {}
for t, rs in by.items():
    pass
for o in obs_all:
    if o.get("passed") and o.get("token"):
        t = o["token"]
        first_pass_ts[t] = min(first_pass_ts.get(t, 9e18), o.get("ts") or 9e18)
cross = [m for m in ms if m.get("milestone") in ("mcap_1m", "mcap_5m")
         and T0 <= (m.get("crossed_ts") or 0) <= RUN_TS]
gated = [m for m in cross if m.get("realizable_at_crossing") is True]
first_cross = {}
for m in gated:
    k = (m["token"], m["milestone"])
    if k not in first_cross or m["crossed_ts"] < first_cross[k]["crossed_ts"]:
        first_cross[k] = m
miss, hit = [], []
for (tok, mil), m in first_cross.items():
    alerted = first_pass_ts.get(tok, 9e18) < m["crossed_ts"]
    found = any(ts < m["crossed_ts"] for ts in fkeys.get(tok, ()))
    (hit if (alerted or found) else miss).append(
        {"token": tok, "milestone": mil, "symbol": m.get("symbol"),
         "crossed_at": m.get("crossed_at"), "depth": m.get("exit_depth_at_crossing"),
         "launch_alert": alerted, "finding": found})
R["crossings"] = {"raw_rows": len(cross), "raw_contracts": len({m["token"] for m in cross}),
                  "gated_rows": len(gated), "gated_contract_milestones": len(first_cross),
                  "phantom_share_pct": round(100 * (1 - len(gated) / len(cross)), 1) if cross else None,
                  "alerted_before_crossing": len(hit), "MISSED": len(miss),
                  "missed": sorted(miss, key=lambda x: -(x["depth"] or 0))}

# ---- universe side: >= $1M tokens admitted in the window that our journal never saw
u = json.load(io.open("data/universe/members.json", encoding="utf-8"))["tokens"]
newu = [v for v in u.values() if T0 <= (v.get("first_seen_ts") or 0) <= RUN_TS
        and v.get("status") == "member"]
unseen = [v for v in newu if v["token"] not in ever]
R["universe"] = {"new_members_in_window": len(newu), "never_in_journal": len(unseen),
                 "pct": round(100 * len(unseen) / len(newu), 1) if newu else None,
                 "wilson": wilson(len(unseen), len(newu)),
                 "launchpads_of_unseen": dict(collections.Counter(v.get("launchpad") for v in unseen))}

json.dump(R, io.open(os.path.join(HERE, "s2_results.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1, default=str)
print(json.dumps({k: v for k, v in R.items() if k != "crossings"}, indent=1, default=str))
c = R["crossings"]
print(json.dumps({k: v for k, v in c.items() if k != "missed"}, indent=1))
for m in c["missed"][:15]:
    print(f"  MISSED {m['milestone']:8} {str(m['symbol'])[:10]:10} {m['token']}  "
          f"depth ${m['depth'] or 0:,.0f}  at {str(m['crossed_at'])[:16]}")

# ---- appended after the first run: the split of the unseen universe, and what alerted contracts became
def bk(v):
    return (v.get("last") or {}).get("cap_backing_pct")


def now_cap(v):
    return (v.get("last") or {}).get("mcap_usd") or 0


R["universe"]["unseen_backing_under_1pct"] = sum(1 for v in unseen if bk(v) is not None and bk(v) < 1.0)
R["universe"]["unseen_now_under_10k"] = sum(1 for v in unseen if now_cap(v) < 10000)
real = [v for v in unseen if bk(v) is not None and bk(v) >= 1.0 and now_cap(v) >= 1e6
        and ((v.get("last") or {}).get("holders") or 0) >= 500]
R["universe"]["unseen_still_real"] = len(real)
R["universe"]["unseen_still_real_list"] = [
    {"token": v["token"], "symbol": v.get("symbol"), "name": v.get("name"),
     "mcap": now_cap(v), "backing_pct": bk(v), "holders": (v.get("last") or {}).get("holders"),
     "launchpad": v.get("launchpad")} for v in sorted(real, key=lambda v: -now_cap(v))]
outs = union_lines(["data/outcomes/2026-09-21.jsonl", "data/outcomes/2026-09-22.jsonl"])
winners = {o["token"] for o in outs if o.get("realizable") and (o.get("mult") or 0) >= 2
           and T0 <= (o.get("checked_ts") or 0) <= RUN_TS and o.get("token")}
R["alerts_vs_mattered"] = {
    "alerted_contracts": len(passed),
    "alerted_then_gated_1m_crossing": len({k[0] for k in first_cross} & passed),
    "alerted_then_gate_passing_2x": len(winners & passed),
    "gate_passing_2x_contracts": len(winners),
    "gate_passing_2x_never_alerted": len(winners - passed),
    "liveness_findings_all_one_stale_line": kinds.get("liveness", 0),
    "findings_total": sum(kinds.values())}
json.dump(R, io.open(os.path.join(HERE, "s2_results.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1, default=str)
print(json.dumps({k: R[k] for k in ("universe", "alerts_vs_mattered")}, indent=1, default=str))
