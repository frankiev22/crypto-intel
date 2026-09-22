"""Section 3: does score predict SURVIVAL independent of early peak?

Method and decision rule pre-committed in PRECOMMIT.md before this ran.
Writes s3_results.json.
"""
import collections
import datetime as dt
import glob
import io
import json
import math
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
os.chdir(ROOT)

START = dt.datetime(2026, 9, 7, tzinfo=dt.timezone.utc).timestamp()
END_OBS = dt.datetime(2026, 9, 21, 11, 0, tzinfo=dt.timezone.utc).timestamp()


def union(paths):
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


def wilson(k, n, z=1.96):
    if not n:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(100 * (c - h), 1), round(100 * (c + h), 1))


days = sorted({p[-16:-6] for p in glob.glob("data/observations/2026-09-*.jsonl")})
obs = union([f"data/observations/{d}.jsonl" for d in days if d >= "2026-09-07"])
outs = union([f"data/outcomes/{d}.jsonl" for d in
              sorted({p[-16:-6] for p in glob.glob("data/outcomes/2026-09-*.jsonl")})
              if d >= "2026-09-07"])
print(f"observation rows {len(obs)}, outcome rows {len(outs)}")

first = {}
for o in obs:
    t, ts = o.get("token"), o.get("ts") or 0
    if not t or o.get("score") is None or not (START <= ts <= END_OBS) or not o.get("pair"):
        continue
    if t not in first or ts < first[t]["ts"]:
        first[t] = o

by_pair = collections.defaultdict(dict)
for o in outs:
    p, h = o.get("pair"), o.get("horizon_h")
    if p and h in (1, 6, 24):
        prev = by_pair[p].get(h)
        if prev is None or (o.get("checked_ts") or 0) < (prev.get("checked_ts") or 0):
            by_pair[p][h] = o


def label(o24):
    if o24 is None:
        return "no_24h"
    s, d = o24.get("status"), o24.get("exit_depth_usd")
    if s == "gone":
        return "unknown"
    if s in ("dead", "rugged"):
        return "died"
    if s == "alive":
        if d is None:
            return "unknown"
        return "survived" if d >= 1000 else "died"
    return "unknown"


units = []
for t, o in first.items():
    oc = by_pair.get(o["pair"], {})
    lab = label(oc.get(24))
    early = [oc[h]["mult"] for h in (1, 6) if oc.get(h) and oc[h].get("mult") is not None]
    pk = max(early) if early else None
    stratum = ("no_early" if pk is None else "lt1" if pk < 1 else "1to2" if pk < 2 else "ge2")
    units.append({"token": t, "score": o["score"], "grade": o.get("grade"),
                  "high": o["score"] >= 70, "label": lab, "peak": pk, "stratum": stratum,
                  "venue": o.get("venue_type"), "ts": o["ts"]})
print(f"contracts with a scored first observation: {len(units)}")

R = {"n_contracts": len(units)}
lab_by_arm = collections.Counter((u["high"], u["label"]) for u in units)
R["labels_by_arm"] = {("high" if k[0] else "low") + ":" + k[1]: v for k, v in lab_by_arm.items()}
for arm in (True, False):
    tot = sum(v for (a, _), v in lab_by_arm.items() if a == arm)
    unk = sum(v for (a, l), v in lab_by_arm.items() if a == arm and l in ("unknown", "no_24h"))
    R[f"unknown_share_{'high' if arm else 'low'}"] = (unk, tot, round(100 * unk / tot, 1) if tot else None)

lab = [u for u in units if u["label"] in ("survived", "died")]


def rate(us):
    k = sum(1 for u in us if u["label"] == "survived")
    return k, len(us), (round(100 * k / len(us), 2) if us else None), wilson(k, len(us))


R["crude"] = {"high": rate([u for u in lab if u["high"]]),
              "low": rate([u for u in lab if not u["high"]])}

strata = {}
num = den = 0.0
P = Q = PR = PSQS = QS = 0.0  # Robins-Breslow-Greenland
eligible = 0
direction_ok = True
for s in ("lt1", "1to2", "ge2", "no_early"):
    us = [u for u in lab if u["stratum"] == s]
    hi = [u for u in us if u["high"]]
    lo = [u for u in us if not u["high"]]
    a = sum(1 for u in hi if u["label"] == "survived")
    b = len(hi) - a
    c = sum(1 for u in lo if u["label"] == "survived")
    d = len(lo) - c
    strata[s] = {"high": rate(hi), "low": rate(lo)}
    if s == "no_early":
        continue
    n = a + b + c + d
    if n == 0:
        continue
    num += a * d / n
    den += b * c / n
    Pi, Qi, Ri, Si = (a + d) / n, (b + c) / n, a * d / n, b * c / n
    P += Pi * Ri
    PSQS += Pi * Si + Qi * Ri
    Q += Qi * Si
    if len(hi) >= 30 and len(lo) >= 30:
        eligible += 1
        if not (a / len(hi) > c / len(lo)):
            direction_ok = False
R["strata"] = strata
if num > 0 and den > 0:
    OR = num / den
    R_sum, S_sum = num, den
    var = P / (2 * R_sum ** 2) + PSQS / (2 * R_sum * S_sum) + Q / (2 * S_sum ** 2)
    se = math.sqrt(var)
    R["mh_or"] = round(OR, 3)
    R["mh_ci"] = (round(math.exp(math.log(OR) - 1.96 * se), 3),
                  round(math.exp(math.log(OR) + 1.96 * se), 3))
else:
    R["mh_or"], R["mh_ci"] = None, None
R["eligible_strata"] = eligible
R["direction_holds_in_every_eligible_stratum"] = direction_ok
if eligible < 2:
    R["verdict"] = "INSUFFICIENT"
elif R["mh_ci"] and R["mh_ci"][0] > 1 and direction_ok:
    R["verdict"] = "CONFIRMED"
else:
    R["verdict"] = "NOT SUPPORTED"

# sensitivity only: grade, 09-17 onward
g = [u for u in lab if u["grade"] is not None]
R["sensitivity_grade"] = {"grade_ge70": rate([u for u in g if u["grade"] >= 70]),
                          "grade_lt70": rate([u for u in g if u["grade"] < 70])}
R["score_values"] = collections.Counter(u["score"] for u in units).most_common(8)
R["venue_by_label"] = {f"{k[0]}:{k[1]}": v for k, v in collections.Counter((u["venue"], u["label"]) for u in units).items()}

json.dump(R, io.open(os.path.join(HERE, "s3_results.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1, default=str)
print(json.dumps(R, indent=1, default=str))
