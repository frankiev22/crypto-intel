"""Assemble the tracked universe: one row per ticker, keyed on contract address.

The field Frank actually asked for is **what the thing does**, in Gorilla's own
words with the date he said it, because that does not exist in any on-chain data
we hold. Everything else here supports it.

⭐ OUTCOME RULES, PRE-COMMITTED BEFORE LOOKING AT ANY RESULT (standing rule 6).
Evaluated in order, so they are mutually exclusive:

  1. no chosen contract, or confidence NONE      -> unresolved
  2. no current liquidity reading                -> unresolved
  3. current liquidity < $1,000                  -> rugged
  4. current mcap >= $1,000,000                  -> alive
  5. otherwise                                   -> faded

⛔⛔ **THE RULES ABOVE ARE BIASED AND THE BIAS IS NOT FIXABLE FROM A TICKER.**
Measured 2026-09-22, after the fact and led with rather than buried: the search
endpoints that turn a ticker into a contract **only return tokens that still have
liquidity**. A token that died is not in their results at all, so the ticker
resolves to whatever live namesake now carries that symbol.

Proof, on a contract we verified by hand the same day: EMBER. The real one is
`FLCr9vGMNQMHQ6z9nQ4FbH3sABPn3ipEAyzJF68zHTsh`, whose operator withdrew 2,907.565
SOL at 11:09:37Z leaving $20.36 of depth. It **does not appear anywhere** in the
Dexscreener results for "EMBER". The resolver instead picked
`5dvXTZ5qwgafnHtwu3Ls3QrWx1U4LQsFeCuJgkk4QEC6`, a different Solana token created
one day before the mention, with $2.1m of liquidity, and graded it HIGH confidence
and **alive**.

⭐ So `outcome` below is **not a survival statistic and must never be quoted as
one**. "rugged: 4 of 482" is an artifact of the method: dead tokens are invisible
to it by construction. The honest survival number comes from `control_cohort.py`,
which keys on **addresses from our own ledger** and therefore can see the dead.
Rows whose resolution is not HIGH or MEDIUM are marked `unverifiable` here.

⛔ "rugged" means **no exit today: under $1,000 of liquidity**. It does NOT
establish intent, and nothing in this dataset can. A token can reach that state
by an LP withdrawal, by abandonment, or by everyone leaving. Saying otherwise
would be a claim about a person we have not verified.

⚠️ Liquidity here is the reported field from the listings, which we have measured
overstating by a median 781x. It is used for a coarse alive/dead split ONLY. Any
number Frank would trade on needs `chainfields.round_trip()`, which this file
deliberately does not pretend to do for 482 tokens.
"""
import io
import json
import os
import re
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))

# Frank's taxonomy, with the evidence that assigns it. Order = priority when a
# bullet matches several, since a launchpad that routes fees is first a launchpad.
CATEGORIES = [
    ("LAUNCHPAD", r"launchpad|launcher|launch pad|deploy(?:er)? platform|token-pairing launchpad"),
    ("FEE-ROUTING", r"xmoney|x money|attach fees|fees? to (?:his|her|their|someone)|routing fees"),
    ("FLYWHEEL", r"flywheel|buyback|fees? (?:buy|feed|go (?:in)?to|are used|fund)|revenue shar|rev shar"),
    ("PAIRED", r"paired (?:with|to)|pairing|backed by|tied to|tracks the price|\bbacked\b"),
    ("NFT-LINKED", r"\bnft\b|pfp collection|\bcollection\b|eth sale"),
    ("PRODUCT", r"terminal|prediction market|messaging|analytics|liquidity layer|protocol|"
                r"\bgame\b|\bapp\b|penny stocks|loans against|dashboard|platform"),
]
EXPLAINS = re.compile(
    r"it'?s\b|its a\b|, a |, an |which is|the first|based on|lets you|allows you|"
    r"launchpad|paired|backed by|a token|a coin|meme about|after ", re.I)
TICKER_RE = re.compile(r"\$([A-Za-z][A-Za-z0-9_]{1,14})\b|\$([一-鿿]{1,8})")


def categorise(texts):
    """Multi-label from evidence. UNCATEGORISED when nothing matches, never a guess."""
    hits = []
    for name, pat in CATEGORIES:
        for t in texts:
            if re.search(pat, t, re.I):
                hits.append(name)
                break
    if not hits:
        return "ATTENTION", []  # no stated mechanism anywhere in the archive
    return hits[0], hits


def n_tickers(text):
    return len([m for m in TICKER_RE.finditer(text)])


def best_explanation(ms):
    """Earliest mention that actually explains, preferring bullets about one token."""
    scored = []
    for i, m in enumerate(ms):
        t = m["text"]
        s = 0
        if EXPLAINS.search(t):
            s += 10
        nt = n_tickers(t)
        if nt <= 1:
            s += 6
        elif nt <= 3:
            s += 2
        else:
            s -= 4              # a list of tickers is not an explanation
        s += min(len(t), 220) / 60.0
        s -= i * 0.35           # prefer the first time he explains it
        scored.append((s, i, m))
    scored.sort(key=lambda x: (-x[0], x[1]))
    top = scored[0][2]
    return top, ("list" if n_tickers(top["text"]) > 3 else
                 ("explained" if EXPLAINS.search(top["text"]) else "thin"))


def outcome(chosen, conf, peak):
    if not chosen or conf == "NONE":
        return "unresolved", "no contract resolved"
    if conf not in ("HIGH", "MEDIUM"):
        # ⛔ several live namesakes; the one he meant may be dead and therefore
        # absent from every search result. Scoring this row would invent a fact.
        return "unverifiable", "several live tokens carry this ticker"
    liq = chosen.get("liquidity")
    if liq is None:
        return "unresolved", "no liquidity reading"
    if liq < 1000:
        return "rugged", f"liquidity ${liq:,.0f}, no exit"
    mc = chosen.get("mcap") or 0
    if mc >= 1_000_000:
        return "alive", f"mcap ${mc:,.0f}, liquidity ${liq:,.0f}"
    return "faded", f"mcap ${mc:,.0f} against a reported peak of ${peak:,.0f}" if peak \
        else f"mcap ${mc:,.0f}"


def main():
    mentions = json.load(io.open(os.path.join(HERE, "mentions.json"), encoding="utf-8"))
    resolved = {r["ticker"]: r for r in
                json.load(io.open(os.path.join(HERE, "resolved.json"), encoding="utf-8"))}

    by = {}
    for m in mentions:
        by.setdefault(m["ticker"], []).append(m)
    for t in by:
        by[t].sort(key=lambda m: (m["date"] or "", m["posted"]))

    rows = []
    for t, ms in sorted(by.items()):
        r = resolved.get(t) or {"confidence": "NONE", "chosen": None,
                                "n_candidates": 0, "why": "not attempted"}
        ch = r.get("chosen")
        expl, quality = best_explanation(ms)
        primary, all_cats = categorise([m["text"] for m in ms])

        traj = []
        for m in ms:
            for v in (m["mcaps"] or []):
                traj.append({"date": m["date"], "mcap": v})
        peak = max([x["mcap"] for x in traj], default=None)
        first_mcap = traj[0]["mcap"] if traj else None

        lab, why = outcome(ch, r.get("confidence"), peak)
        cur_mc = (ch or {}).get("mcap")
        rows.append({
            "ticker": t,
            "chain": (ch or {}).get("chain"),
            "address": (ch or {}).get("address"),
            "token_name": (ch or {}).get("name"),
            "resolution_confidence": r.get("confidence"),
            "resolution_note": r.get("why"),
            "n_candidates": r.get("n_candidates"),
            "other_candidates": r.get("others") or [],
            "rejected_newer_than_mention": r.get("rejected_newer") or [],
            "symbol_flags": (ch or {}).get("symbol_flags"),
            "what_it_does": expl["text"],
            "what_it_does_date": expl["date"],
            "what_it_does_quality": quality,
            "category": primary,
            "categories": all_cats,
            "first_seen": ms[0]["date"],
            "last_seen": ms[-1]["date"],
            "n_mentions": len(ms),
            "first_reported_mcap": first_mcap,
            "peak_reported_mcap": peak,
            "reported_trajectory": traj,
            "all_mentions": [{"date": m["date"], "text": m["text"]} for m in ms],
            "current_price_usd": (ch or {}).get("price"),
            "current_mcap_usd": cur_mc,
            "current_liquidity_usd": (ch or {}).get("liquidity"),
            "current_vol24_usd": (ch or {}).get("vol24"),
            "holders": (ch or {}).get("holders"),
            "launchpad": (ch or {}).get("launchpad"),
            "jup_verified": (ch or {}).get("verified"),
            "audit": (ch or {}).get("audit"),
            "outcome": lab,
            "namesake_risk": (r.get("confidence") not in ("HIGH",)),
            "outcome_why": why,
            "mult_vs_first_reported": (round(cur_mc / first_mcap, 4)
                                       if (cur_mc and first_mcap) else None),
        })

    json.dump(rows, io.open(os.path.join(HERE, "dataset.json"), "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)

    oc, cc, rc = Counter(r["outcome"] for r in rows), \
        Counter(r["category"] for r in rows), \
        Counter(r["resolution_confidence"] for r in rows)
    print("rows", len(rows))
    print("outcome   ", dict(oc))
    print("category  ", dict(cc))
    print("confidence", dict(rc))
    print("explanation quality", dict(Counter(r["what_it_does_quality"] for r in rows)))


if __name__ == "__main__":
    main()
