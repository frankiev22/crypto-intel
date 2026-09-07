"""The validated fraud detectors, and their confidence intervals as they move.

READ `FRAUD_DETECTION.md` FIRST. Nothing here filters anything. These are
measurements reported with counts, and the point of this module is that the
interval is quoted every time, so the point estimate can never be cited alone.

D1 - SILENCE. `liq/fdv >= 0.95 AND sells_h1 == 0 AND buys_h1 >= 10`.
     The supply IS the pool, and nobody has ever sold into it.

     **OUT OF SAMPLE.** Derived 2026-09-05 from three pools whose reserves were
     pulled by hand. `exit_depth_usd` only began being stored afterwards, so
     100% of the labelled set was observed AFTER the rule existed - the
     detector has never touched this data. That is why it held when four
     retrospective findings did not.

D2 - MAGNITUDE + INACTIVITY. `liq >= $1,000,000 AND txns_h1 <= 5`.

     **IN SAMPLE. Derived 2026-09-07 from the very rows it is scored on, and
     therefore NOT VALIDATED.** Reported separately and must never be quoted as
     though it carried D1's evidence. Its honest status is "a hypothesis with a
     promising in-sample fit"; it needs forward data before it means anything.

     It deliberately does NOT use `age_hours`. A magnitude gate keyed on age
     shipped and was withdrawn the same day on 2026-09-05, because `age_hours`
     is PAIR age from `pairCreatedAt` - a new pool for an established token
     looks exactly like a new token. D2 uses only size and transaction count,
     which mean the same thing regardless of how old the pair is.

WHY TWO DETECTORS AND NOT ONE LOOSER ONE. Measured 2026-09-07, zero overlap:
23 rows caught by D1 only, 14 by D2 only, 0 by both. They are distinct
mechanisms - D1 finds pools with real buying and no exit, D2 finds pools with
enormous reported size and no activity at all. Merging them by weakening either
conjunction costs everything:

    liq/fdv >= 0.95 alone      precision  22.65%   (140 false positives)
    sells==0 & buys>=10 alone  precision  76.67%
    D1, both together          precision 100.00%   (0 false positives)

    liq >= $1M alone           precision  90.00%   (2 false positives)
    txns_h1 <= 5 alone         precision  26.23%   (45 false positives)
    D2, both together          precision 100.00%   (0 false positives)

GROUND TRUTH is `exit_depth_usd / liq`, from reserves recorded at observation
time. Below `FAKE_RATIO` a pool cannot be left at anything like its reported
size. Every feature above uses only NON-RESERVE fields, so no detector is
scored against its own input.
"""
import math
import os

FAKE_RATIO = float(os.environ.get("CRYPTO_FAKE_RATIO", "0.10"))
D2_MIN_LIQ = float(os.environ.get("CRYPTO_D2_MIN_LIQ", "1000000"))
D2_MAX_TXNS = int(os.environ.get("CRYPTO_D2_MAX_TXNS", "5"))
MIN_N = int(os.environ.get("CRYPTO_DETECTOR_MIN_N", "30"))


def _f(o, k):
    v = o.get(k)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def wilson(k, n, z=1.96):
    if not n:
        return (0.0, 100.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * max(0.0, c - m), 100 * min(1.0, c + m))


def d1(o):
    liq, fdv = _f(o, "liq"), _f(o, "fdv")
    return bool(liq and fdv and liq / fdv >= 0.95
                and (_f(o, "sells_h1") or 0) == 0
                and (_f(o, "buys_h1") or 0) >= 10)


def d2(o):
    return bool((_f(o, "liq") or 0) >= D2_MIN_LIQ
                and (_f(o, "txns_h1") or 0) <= D2_MAX_TXNS)


def labelled(observations):
    """Rows where ground truth exists: a measured depth AND a reported liq."""
    out = []
    for o in observations:
        d, l = _f(o, "exit_depth_usd"), _f(o, "liq")
        if d is not None and l and l > 0:
            out.append((o, d / l))
    return out


def score(rows, rule):
    tp = fp = fn = tn = 0
    for o, ratio in rows:
        p, t = bool(rule(o)), ratio < FAKE_RATIO
        if p and t:
            tp += 1
        elif p and not t:
            fp += 1
        elif t:
            fn += 1
        else:
            tn += 1
    pl, ph = wilson(tp, tp + fp)
    rl, rh = wilson(tp, tp + fn)
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "flagged": tp + fp, "positives": tp + fn,
            "precision": (100.0 * tp / (tp + fp)) if (tp + fp) else None,
            "precision_lo": pl, "precision_hi": ph,
            "recall": (100.0 * tp / (tp + fn)) if (tp + fn) else None,
            "recall_lo": rl, "recall_hi": rh,
            "conclusive": (tp + fp) >= MIN_N}


def report(observations=None):
    if observations is None:
        import journal
        observations = journal.observations()
    rows = labelled(observations)
    out = {"labelled_n": len(rows),
           "one_sided": sum(1 for _, x in rows if x < FAKE_RATIO),
           "D1": score(rows, d1), "D2": score(rows, d2),
           "D1_or_D2": score(rows, lambda o: d1(o) or d2(o))}
    out["overlap"] = sum(1 for o, _ in rows if d1(o) and d2(o))
    return out


def line(r=None):
    """The daily line. Quotes n and the interval for every figure."""
    r = r or report()
    n = r["labelled_n"]
    ls = [f"labelled n={n:,}, one-sided {r['one_sided']} "
          f"({100.0 * r['one_sided'] / max(1, n):.2f}%)"]
    for k, note in (("D1", "out of sample"),
                    ("D2", "IN SAMPLE - not validated"),
                    ("D1_or_D2", "union")):
        s = r[k]
        if s["precision"] is None:
            ls.append(f"  {k:<9} no flags yet ({note})")
            continue
        ls.append(f"  {k:<9} flagged={s['flagged']:>3}  "
                  f"precision {s['precision']:.2f}% "
                  f"[{s['precision_lo']:.1f}, {s['precision_hi']:.1f}]  "
                  f"recall {s['recall']:.2f}% "
                  f"[{s['recall_lo']:.1f}, {s['recall_hi']:.1f}]  ({note})")
    ls.append(f"  overlap D1&D2 = {r['overlap']}"
              + ("  -> distinct mechanisms" if r["overlap"] == 0 else ""))
    return "\n".join(ls)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(line())
