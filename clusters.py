"""Narrative clusters: many tokens named off one story, inside one window.

THE IDEA. When something breaks, you do not get one coin. You get a dozen named
after phrases from the same post within the hour. The launches ARE the viral
signal, and they are already in our journal - nothing has ever grouped them.

THE CASE THAT PROVES IT. 2026-08-27, Justin Sun's "My Girlfriend Jing Tian"
essay. Our scanner logged 我的女友景甜 - literally the post's title - at 12:05
that day, then again at 13:05, 15:05, 16:05, each a DIFFERENT contract. Over the
next day: 我的男友孙宇晨, 孙宇晨VS景甜, 景甜孩子的妈妈, 景甜妈妈, 女友景甜, 景甜,
孙宇晨. Four of the top five movers that week were that one narrative, and
孙宇晨 reached 61.33x at 203M mcap on $134,237 of liquidity - genuinely sellable.
We caught every one and surfaced none.

NON-ASCII IS THE POINT, NOT AN EDGE CASE. The biggest wave in the record is
Chinese. Chinese has no spaces, so word splitting finds nothing; the shared root
is a SUBSTRING - 景甜 inside 我的女友景甜 and 景甜孩子的妈妈 and 孙宇晨VS景甜.
CJK runs are therefore expanded into character n-grams. A tokeniser that assumes
spaces would have missed the single best example this project has.

WHAT THIS IS NOT. Cluster size does NOT predict winners. Measured 2026-08-30:
the hit rate falls monotonically as clusters grow, and clusters of 10 or more
produced ZERO winners across 418 tokens - those are mass-mint spam swarms.

That does not matter, because this does not rank or predict. It says "a story is
happening and here are the coins from it", and Frank decides. Size is shown
because it is descriptive, and swarms are LABELLED so he can tell a narrative
from a spam flood. Size is never presented as quality.
"""
import os
import re
import time
import unicodedata
from collections import defaultdict

WINDOW_H = float(os.environ.get("CRYPTO_CLUSTER_WINDOW_H", "24"))
MIN_MEMBERS = int(os.environ.get("CRYPTO_CLUSTER_MIN", "3"))
# Above this size a cluster MIGHT be a mint swarm rather than a story. Size
# alone is not enough to say which, and getting it wrong matters: the 景甜 wave
# had 11 members and was the best narrative in the record, so a pure size rule
# labels the single best case as spam.
#
# The discriminator that actually separates them, from our own data:
#   spam swarm   many contracts, ONE repeated symbol, minted in minutes,
#                usually no liquidity   (Grokstreet: 11 contracts, 1 symbol, 0.0h)
#   narrative    several DIFFERENT symbols riffing on one root, over hours,
#                with funded pools      (景甜: 11 contracts, 4+ symbols, 16h)
# So a swarm needs size AND near-zero name variety. Shown either way, never
# hidden, and size is never presented as quality.
SWARM_AT = int(os.environ.get("CRYPTO_CLUSTER_SWARM", "10"))
SWARM_MAX_VARIANTS = int(os.environ.get("CRYPTO_CLUSTER_SWARM_VARIANTS", "2"))
CJK_MIN, CJK_MAX = 2, 5          # n-gram length for CJK runs
LATIN_MIN = 4                    # shortest latin root worth grouping on

# Roots so generic that grouping on them says nothing about a narrative. These
# are suffixes and memes that recur across unrelated launches every single day.
STOP = {
    "coin", "token", "inu", "moon", "elon", "trump", "pepe", "doge", "shib",
    "solana", "sol", "bonk", "cat", "dog", "baby", "safe", "meme", "meta",
    "official", "the", "and", "for", "with", "this", "that", "you", "your",
    "new", "test", "first", "best", "king", "queen", "lord", "god", "wif",
    "girl", "boy", "man", "woman", "usd", "usdt", "usdc", "btc", "eth",
}


def _is_cjk(ch):
    o = ord(ch)
    return (0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF
            or 0x3040 <= o <= 0x30FF or 0xAC00 <= o <= 0xD7AF)


def normalise(s):
    """Strip emoji, punctuation and accents; keep letters, digits and CJK.

    Deliberately NOT ascii-only. `findings.py::_slug` used to collapse non-ASCII
    names to nothing, which erased the entire Chinese wave from any grouping.
    """
    s = unicodedata.normalize("NFKC", str(s or ""))
    out = []
    for ch in s:
        if _is_cjk(ch):
            out.append(ch)
        elif ch.isalnum():
            out.append(ch.lower())
        else:
            out.append(" ")
    return re.sub(r"\s+", " ", "".join(out)).strip()


def roots(symbol):
    """Candidate shared roots for one token name. Set of strings."""
    n = normalise(symbol)
    if not n:
        return set()
    out = set()
    for chunk in n.split(" "):
        if not chunk:
            continue
        # split each chunk into CJK runs and latin/digit runs
        runs, cur, cur_cjk = [], "", None
        for ch in chunk:
            c = _is_cjk(ch)
            if cur and c != cur_cjk:
                runs.append((cur, cur_cjk))
                cur = ""
            cur += ch
            cur_cjk = c
        if cur:
            runs.append((cur, cur_cjk))
        for run, is_cjk in runs:
            if is_cjk:
                # every contiguous substring - the shared root of 我的女友景甜
                # and 景甜孩子的妈妈 is 景甜, which no word-splitter finds.
                for L in range(CJK_MIN, min(CJK_MAX, len(run)) + 1):
                    for i in range(len(run) - L + 1):
                        out.add(run[i:i + L])
            else:
                if len(run) >= LATIN_MIN and run not in STOP and not run.isdigit():
                    out.add(run)
    return out


def find(observations, window_h=None, min_members=None, now=None, end=None):
    """Clusters inside the window. Returns a list, biggest first.

    Each cluster: root, size, members (one per contract, first sighting),
    first_seen/last_seen epoch seconds, and `swarm` when it is large enough to
    be a mint flood rather than a story.
    """
    window_h = WINDOW_H if window_h is None else window_h
    min_members = MIN_MEMBERS if min_members is None else min_members
    end = time.time() if end is None else end
    start = end - window_h * 3600

    # one row per contract: its earliest sighting in the window
    first = {}
    for o in observations:
        ts = o.get("ts") or 0
        if not (start <= ts <= end):
            continue
        tok = o.get("token")
        if not tok or not o.get("symbol"):
            continue
        prev = first.get(tok)
        if prev is None or ts < prev["ts"]:
            first[tok] = o

    by_root = defaultdict(list)
    for tok, o in first.items():
        for r in roots(o.get("symbol")):
            by_root[r].append(o)

    cands = []
    for root, members in by_root.items():
        if len(members) < min_members:
            continue
        cands.append({"root": root, "members": members,
                      "toks": frozenset(m["token"] for m in members)})

    # Collapse overlaps. 景甜 and 我的女友景甜 describe the same event; keep the
    # root covering the most contracts, and on a tie the longer (more specific)
    # string. Then drop any candidate whose members are a subset of a kept one.
    cands.sort(key=lambda c: (-len(c["toks"]), -len(c["root"])))
    kept = []
    for c in cands:
        if any(c["toks"] <= k["toks"] for k in kept):
            continue
        kept.append(c)

    out = []
    for c in kept:
        ms = sorted(c["members"], key=lambda m: m.get("ts") or 0)
        variants = len({normalise(m.get("symbol")) for m in ms})
        funded = sum(1 for m in ms if (m.get("liq") or 0) > 0)
        out.append({
            "root": c["root"],
            "size": len(ms),
            "variants": variants,
            "funded": funded,
            "first_seen": ms[0].get("ts"),
            "last_seen": ms[-1].get("ts"),
            "span_h": round(((ms[-1].get("ts") or 0) - (ms[0].get("ts") or 0)) / 3600.0, 2),
            "swarm": len(ms) >= SWARM_AT and variants <= SWARM_MAX_VARIANTS,
            "members": ms,
        })
    out.sort(key=lambda c: (-c["size"], -(c["last_seen"] or 0)))
    return out


def line(cs, limit=8):
    ls = [f"narrative clusters: {len(cs)}"]
    for c in cs[:limit]:
        syms = ", ".join(sorted({str(m.get("symbol"))[:14] for m in c["members"]})[:4])
        ls.append(f"  {c['root'][:16]:<18} {c['size']:>3} tokens, {c['variants']:>2} names, "
                  f"{c['funded']:>2} funded, over {c['span_h']:>5.1f}h"
                  + ("  [LIKELY SPAM SWARM]" if c["swarm"] else "")
                  + f"   {syms}")
    return "\n".join(ls)


if __name__ == "__main__":
    import sys
    import journal
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cs = find(journal.observations())
    print(line(cs, limit=15))
