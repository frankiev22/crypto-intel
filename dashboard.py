"""Build the dashboard: one self-contained HTML file, no build step, phone-first.

    python dashboard.py            -> data/dashboard.html

WHAT THIS IS FOR. Frank does not want a prediction and this project has none to
give. He wants to be SHOWN things he would otherwise miss, and to make the call
himself. So every section here answers "here is something happening" and none of
them answers "here is what to buy".

DESIGN RULES, enforced in code rather than remembered:

  NO SCORE, NO RANK BY EXPECTED RETURN. Sections sort by recency or by size,
  never by anything that could be read as a quality ordering. `score` is not
  displayed anywhere; it is an internal filter input and has repeatedly failed
  as a predictor.

  EVERY NUMBER CARRIES ITS SOURCE AND ITS AGE, and a stale number is styled to
  look stale rather than merely being labelled.

  UNKNOWN IS PRINTED AS "unknown". Never 0, never blank. Five separate failures
  in this repo came from an absent measurement rendering as a real value, and
  the one that reaches Frank is the one that costs money - a pool with no
  readable depth must not look like a pool with no depth.

  ROUND-TRIP COST AT $100 ON EVERY ROW. He trades $100 clips; whether a coin is
  actionable at all is decided by that number, not by anything else on the page.
"""
import html
import json
import os
import sys
import time
import datetime as dt

import safeload

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "data", "dashboard.html")
POOL_FEE = 0.0025
CLIP = 100.0


def _f(x, d=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


def usd(v, unknown="unknown"):
    """A MEASURED zero and an UNMEASURED value must never look alike.

    None renders "unknown" in italics; a real zero renders "$0". Printing
    "$0.0000" for both is how an absent reading gets read as a real one, which
    is the failure class that has cost this project five separate findings.

    There is a third case, and it bit on the first build: a measured value too
    small to survive four decimals also printed "$0.0000". That is the same
    collision wearing a different hat - it reads as an exact zero AND carries
    four digits of precision the number does not have. Anything under a
    hundredth of a cent renders as a BOUND, "<$0.0001", so it cannot be
    mistaken for either a measurement or a zero.
    """
    v = _f(v)
    if v is None:
        return unknown
    if v == 0:
        return "$0"
    if 0 < v < 0.0001:
        return "&lt;$0.0001"
    if v < 0:
        return "unknown"          # negative depth is not a reading, it is a bug
    if v >= 1_000_000:
        return f"${v/1_000_000:,.2f}M"
    if v >= 1000:
        return f"${v:,.0f}"
    if v >= 1:
        return f"${v:,.2f}"
    return f"${v:.4f}"


def round_trip(depth):
    """Cost to enter and leave at $100, or None when depth is unmeasured."""
    d = _f(depth)
    if d is None or d <= 0:
        return None
    return 100.0 * ((CLIP / (d + CLIP)) * 2 + 2 * POOL_FEE)


def rt_html(depth):
    rt = round_trip(depth)
    if rt is None:
        return '<span class="unk">unknown</span>'
    cls = "good" if rt < 2 else "ok" if rt < 5 else "bad" if rt < 20 else "worst"
    return f'<span class="rt {cls}">{rt:.1f}%</span>'


def ago(ts):
    t = _f(ts)
    if not t:
        return "unknown"
    h = (time.time() - t) / 3600.0
    if h < 1:
        return f"{h*60:.0f} min ago"
    if h < 48:
        return f"{h:.1f}h ago"
    return f"{h/24:.1f}d ago"


def stale_class(ts, warn_h=6):
    t = _f(ts)
    if not t:
        return "stale"
    return "stale" if (time.time() - t) / 3600.0 > warn_h else ""


def addr(a):
    a = str(a or "")
    if not a:
        return '<span class="unk">unknown</span>'
    return (f'<button class="ca" data-a="{html.escape(a)}" title="copy contract">'
            f'{html.escape(a[:6])}…{html.escape(a[-4:])}</button>')


# --------------------------------------------------------------------------
def gather():
    import journal
    import clusters
    import detector
    import milestones
    import watchlist

    obs = journal.observations()
    now = time.time()
    data = {"built": now, "warnings": []}

    # newest observation per contract, for enrichment
    latest = {}
    for o in obs:
        t = o.get("token")
        if not t:
            continue
        if t not in latest or (o.get("ts") or 0) > (latest[t].get("ts") or 0):
            latest[t] = o
    data["latest"] = latest

    # 1. narrative clusters
    try:
        data["clusters"] = clusters.find(obs, window_h=24, min_members=3)
    except Exception as e:
        data["clusters"] = []
        data["warnings"].append(f"clusters failed: {type(e).__name__}")

    # 2. graduated (live only - the backfill is not a detection) + approaching
    grad = []
    try:
        for c in milestones.live_crossings("graduated"):
            if (c.get("crossed_ts") or 0) > now - 7 * 86400:
                grad.append(c)
        grad.sort(key=lambda c: -(c.get("crossed_ts") or 0))
    except Exception as e:
        data["warnings"].append(f"graduated failed: {type(e).__name__}")
    data["graduated"] = grad
    try:
        st = watchlist._load()
        appr = sorted(st.values(), key=lambda m: -(m.get("last_fdv") or 0))
        data["approaching"] = appr[:25]
        data["band"] = (watchlist.BAND_LO, watchlist.BAND_HI)
    except Exception as e:
        data["approaching"], data["band"] = [], (45000, 69000)
        data["warnings"].append(f"watchlist failed: {type(e).__name__}")

    # 3. fraud flags, last 48h
    flags = []
    try:
        for o in obs:
            if (o.get("ts") or 0) < now - 48 * 3600:
                continue
            d1, d2 = detector.d1(o), detector.d2(o)
            if d1 or d2:
                flags.append({"o": o, "d1": d1, "d2": d2})
        seen, uniq = set(), []
        for f in sorted(flags, key=lambda f: -(f["o"].get("ts") or 0)):
            k = f["o"].get("token")
            if k in seen:
                continue
            seen.add(k)
            uniq.append(f)
        data["flags"] = uniq[:40]
        data["detector"] = detector.report(obs)
    except Exception as e:
        data["flags"], data["detector"] = [], None
        data["warnings"].append(f"detector failed: {type(e).__name__}")

    # 4. movers - verified outcomes only, gated
    try:
        vo = journal.verified_outcomes()
        mv = [r for r in vo if _f(r.get("mult")) and _f(r.get("mult")) >= 2.0]
        mv.sort(key=lambda r: -(r.get("checked_ts") or 0))
        data["movers"] = mv[:25]
        data["verified_n"] = len(vo)
    except Exception as e:
        data["movers"], data["verified_n"] = [], 0
        data["warnings"].append(f"movers failed: {type(e).__name__}")
    return data


# --------------------------------------------------------------------------
CSS = """
:root{--bg:#0f1115;--card:#171a21;--line:#252a34;--fg:#e6e8ec;--dim:#9aa3b2;
--good:#3fb950;--ok:#d29922;--bad:#f85149;--worst:#ff6b6b;--accent:#58a6ff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",sans-serif;
padding:16px;max-width:900px;margin:0 auto}
h1{font-size:22px;margin:0 0 4px}
h2{font-size:19px;margin:30px 0 4px;padding-top:14px;border-top:1px solid var(--line)}
.sub{color:var(--dim);font-size:15px;margin:0 0 12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:13px 14px;margin:10px 0}
.chead{display:flex;flex-wrap:wrap;gap:8px;align-items:baseline;margin-bottom:8px}
.root{font-size:18px;font-weight:600}
.tag{font-size:14px;color:var(--dim);background:#1e222b;border:1px solid var(--line);
border-radius:20px;padding:1px 10px}
.tag.warn{color:#ffb86b;border-color:#4a3b23}
.row{display:flex;flex-wrap:wrap;gap:6px 14px;align-items:baseline;
padding:8px 0;border-top:1px solid var(--line)}
.row:first-of-type{border-top:none}
.sym{font-weight:600;min-width:112px}
.k{color:var(--dim);font-size:14px}
.v{font-size:15px}
.unk{color:var(--dim);font-style:italic}
.rt{font-weight:600}
.rt.good{color:var(--good)}.rt.ok{color:var(--ok)}
.rt.bad{color:var(--bad)}.rt.worst{color:var(--worst)}
.stale{opacity:.55}
.ca{font:inherit;font-size:14px;background:#1e222b;color:var(--accent);
border:1px solid var(--line);border-radius:6px;padding:2px 8px;cursor:pointer}
.ca:active{background:#2a2f3a}
.note{color:var(--dim);font-size:14px;margin:8px 0 0}
.empty{color:var(--dim);padding:10px 0}
.warn{background:#2a1f1f;border:1px solid #5a2d2d;border-radius:8px;
padding:10px 12px;margin:12px 0;font-size:15px}
footer{color:var(--dim);font-size:14px;margin:34px 0 60px;
border-top:1px solid var(--line);padding-top:12px}
"""

JS = """
document.addEventListener('click',function(e){
  var b=e.target.closest('.ca'); if(!b) return;
  var a=b.getAttribute('data-a'), old=b.textContent;
  var done=function(){b.textContent='copied';setTimeout(function(){b.textContent=old},1200)};
  if(navigator.clipboard&&navigator.clipboard.writeText){
    navigator.clipboard.writeText(a).then(done,function(){window.prompt('Contract address',a)});
  } else { window.prompt('Contract address',a); }
});
"""


def coin_row(sym, contract, depth, mcap=None, liq=None, ts=None, extra=""):
    return f"""<div class="row {stale_class(ts)}">
  <span class="sym">{html.escape(str(sym or 'unknown')[:22])}</span>
  {addr(contract)}
  <span><span class="k">mcap</span> <span class="v">{usd(mcap)}</span></span>
  <span><span class="k">liq</span> <span class="v">{usd(liq)}</span></span>
  <span><span class="k">exit depth</span> <span class="v">{usd(depth)}</span></span>
  <span><span class="k">$100 round trip</span> {rt_html(depth)}</span>
  <span class="k">{ago(ts)}</span>{extra}
</div>"""


def render(d):
    now = d["built"]
    latest = d["latest"]
    P = []
    P.append(f"""<h1>crypto-intel · what's happening</h1>
<p class="sub">Built {dt.datetime.fromtimestamp(now, dt.timezone.utc):%Y-%m-%d %H:%M} UTC ·
things you might not have seen. <strong>Not recommendations.</strong>
This system has no validated way to predict price and five attempts have been retracted.
Every row shows what a $100 round trip costs, because that decides whether a coin is
actionable at all.</p>""")
    for w in d["warnings"]:
        P.append(f'<div class="warn">section failed to build: {html.escape(w)}</div>')

    # 1 CLUSTERS
    # Split by NAME VARIETY, not by size. Several different names riffing on one
    # root is a story (the 景甜 wave had 6 names across 11 contracts); one name
    # minted many times is a spam flood. Both are shown - the split is so Frank
    # can tell them apart at a glance, which is the whole job. Neither list is
    # ordered by anything that could be read as quality.
    narr = [c for c in d["clusters"] if c["variants"] >= 2]
    swarms = [c for c in d["clusters"] if c["variants"] < 2]
    P.append('<h2>1 &middot; Narrative clusters, last 24h</h2>')
    P.append('<p class="sub">Several coins named off one story inside one window. '
             '<strong>Different names sharing a root</strong> is what a breaking '
             'narrative looks like &mdash; the 2026-08-27 Jing Tian wave was 6 names '
             'across 11 contracts. One name minted over and over is spam, listed '
             'separately below. Size is descriptive only: it does <em>not</em> predict '
             'winners, and in our own data clusters of 10+ produced zero.</p>')
    if not narr:
        P.append('<p class="empty">No multi-name narrative clusters in the last 24h. '
                 'That is a real answer, not a gap &mdash; most days do not have one.</p>')
    for c in narr[:12]:
        tags = [f'<span class="tag">{c["size"]} contracts</span>',
                f'<span class="tag">{c["variants"]} distinct names</span>',
                (f'<span class="tag warn">no pool with liquidity yet</span>'
                 if c["funded"] == 0 else
                 f'<span class="tag">{c["funded"]} with liquidity</span>'),
                f'<span class="tag">over {c["span_h"]:.1f}h</span>']
        if c["swarm"]:
            tags.append('<span class="tag warn">also looks like a mint swarm</span>')
        P.append('<div class="card"><div class="chead">'
                 f'<span class="root">{html.escape(c["root"])}</span>{"".join(tags)}'
                 f'<span class="k">first seen {ago(c["first_seen"])}</span></div>')
        for m in c["members"][:14]:
            cur = latest.get(m.get("token"), m)
            P.append(coin_row(m.get("symbol"), m.get("token"),
                              cur.get("exit_depth_usd"), cur.get("fdv"),
                              cur.get("liq"), cur.get("ts")))
        if c["size"] > 14:
            P.append(f'<p class="note">&hellip;and {c["size"]-14} more contracts on this root.</p>')
        P.append('</div>')

    if swarms:
        P.append('<div class="card"><div class="chead">'
                 '<span class="root">Single-name mint swarms</span>'
                 f'<span class="tag warn">{len(swarms)} roots</span></div>'
                 '<p class="note">One name, many contracts. Almost always automated '
                 'mint spam rather than a story. Listed so they are visible and out '
                 'of the way &mdash; expand only if something looks familiar.</p>')
        for c in swarms[:14]:
            sym = html.escape(str(c["members"][0].get("symbol"))[:22])
            P.append(f'<div class="row {stale_class(c["last_seen"])}">'
                     f'<span class="sym">{sym}</span>'
                     f'<span><span class="k">contracts</span> <span class="v">{c["size"]}</span></span>'
                     f'<span><span class="k">with liquidity</span> <span class="v">{c["funded"]}</span></span>'
                     f'<span><span class="k">over</span> <span class="v">{c["span_h"]:.1f}h</span></span>'
                     f'<span class="k">{ago(c["first_seen"])}</span></div>')
        if len(swarms) > 14:
            P.append(f'<p class="note">&hellip;and {len(swarms)-14} more.</p>')
        P.append('</div>')

    # 2 GRADUATED + APPROACHING
    P.append('<h2>2 · Graduated, and approaching</h2>')
    lo, hi = d["band"]
    # "Graduated" here means the WATCHLIST MILESTONE - a contract we were
    # already tracking in the approach band that later crossed, with a before
    # and an after. It is NOT the per-row venue flag, which only ever meant
    # "has a two-sided pool" and was renamed has_amm_pool on 2026-09-10 for
    # exactly that reason: 95% of the AMM contracts we have seen were never
    # observed on a curve at all, so the flag could not have witnessed a
    # graduation. Only these milestone crossings did.
    P.append('<p class="sub">Graduated = a contract tracked in the approach band that '
             'later crossed, observed by us. Not a venue label. '
             'Post-graduation is the one door still open &mdash; launch sniping '
             'is closed (>50% of tokens are taken in the genesis block, sub-400ms). '
             f'Approaching = FDV between {usd(lo)} and {usd(hi)}. Newest first.</p>')
    if d["graduated"]:
        P.append('<div class="card"><div class="chead"><span class="root">Graduated</span>'
                 f'<span class="tag">{len(d["graduated"])} in 7 days</span></div>')
        for g in d["graduated"][:12]:
            cur = latest.get(g.get("token"), {})
            P.append(coin_row(g.get("symbol"), g.get("token"),
                              cur.get("exit_depth_usd"), cur.get("fdv") or g.get("value"),
                              cur.get("liq"), g.get("crossed_ts")))
        P.append('</div>')
    else:
        P.append('<p class="empty">No live graduations recorded in the last 7 days. '
                 '(The 1,329 historical mcap crossings are a one-off backfill, not '
                 'detections, and are excluded.)</p>')
    if d["approaching"]:
        P.append('<div class="card"><div class="chead"><span class="root">Approaching</span>'
                 f'<span class="tag">{len(d["approaching"])} on the watchlist</span></div>')
        for m in d["approaching"][:15]:
            P.append(coin_row(m.get("symbol"), m.get("contract"),
                              m.get("last_depth"), m.get("last_fdv"),
                              m.get("added_liq"), m.get("last_ts") or m.get("added_ts")))
        P.append('</div>')

    # 3 FRAUD FLAGS
    P.append('<h2>3 · Fraud flags, last 48h</h2>')
    det = d["detector"] or {}
    d1 = (det.get("D1") or {})
    if d1.get("precision") is not None:
        P.append(f'<p class="sub">D1 precision {d1["precision"]:.1f}% '
                 f'[{d1["precision_lo"]:.0f}, {d1["precision_hi"]:.0f}] at n={d1["flagged"]}, '
                 f'recall {d1["recall"]:.0f}% — <strong>it misses about half</strong>. '
                 'Not flagged is not a safety signal. D2 is in-sample and unvalidated. '
                 'Most flags so far sit on one venue, which is still being tested.</p>')
    if not d["flags"]:
        P.append('<p class="empty">Nothing flagged in the last 48h.</p>')
    else:
        P.append('<div class="card">')
        for f in d["flags"][:25]:
            o = f["o"]
            which = " + ".join([x for x in ("D1" if f["d1"] else "", "D2" if f["d2"] else "") if x])
            P.append(coin_row(o.get("symbol"), o.get("token"), o.get("exit_depth_usd"),
                              o.get("fdv"), o.get("liq"), o.get("ts"),
                              extra=f'<span class="tag warn">{which}</span>'))
        P.append('</div>')

    # 4 MOVERS
    P.append('<h2>4 · Verified movers</h2>')
    P.append(f'<p class="sub">Outcomes that passed every integrity check — pair identity, '
             f'measured depth, sell-side, source agreement. {d["verified_n"]} verified '
             'outcomes exist in total; everything before 2026-09-07 is excluded as '
             'unverifiable. <strong>These are past moves, not forecasts.</strong> '
             'Newest first, never ranked by size.</p>')
    if not d["movers"]:
        P.append('<p class="empty">No verified 2x+ outcomes yet.</p>')
    else:
        P.append('<div class="card">')
        for r in d["movers"][:20]:
            mult = _f(r.get("mult"))
            el = _f(r.get("actual_elapsed_h"))
            extra = (f'<span class="tag">{mult:.2f}x in '
                     f'{("%.1fh" % el) if el else "unknown"}</span>')
            P.append(coin_row(r.get("symbol"), r.get("pair"), r.get("exit_depth_usd"),
                              None, r.get("liq"), r.get("checked_ts"), extra=extra))
        P.append('</div>')
        P.append('<p class="note">Contract shown for movers is the <em>pair</em> address, '
                 'which is what the outcome was measured against.</p>')

    P.append(f"""<footer>
Sources: pool data from Dexscreener, reserves and holder data from Solana RPC via Helius,
discovery from GeckoTerminal. Exit depth is the <em>quote side only</em> — what you could
actually be paid in — not reported liquidity, which counts both sides and on flagged pools
has been measured overstating by ~780x. Round trip assumes constant-product impact both
ways plus a 0.25% pool fee each way; pump.fun's AMM charges nearer 1%, so those cost more
than shown. Dimmed rows are over 6 hours old. Nothing here is a recommendation to buy
anything.
</footer>""")

    return (f"<!doctype html><html lang=en><head><meta charset=utf-8>"
            f"<meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>crypto-intel dashboard</title><style>{CSS}</style></head>"
            f"<body>{''.join(P)}<script>{JS}</script></body></html>")


def build(path=OUT):
    d = gather()
    htm = render(d)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Atomic: the dashboard is the thing Frank keeps open, and a half-written
    # page renders as a broken one rather than a stale one.
    safeload.save_text(path, htm)
    return path, d


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p, d = build()
    print(f"  wrote {p}  ({os.path.getsize(p):,} bytes)")
    print(f"  clusters {len(d['clusters'])}  graduated {len(d['graduated'])}  "
          f"approaching {len(d['approaching'])}  flags {len(d['flags'])}  "
          f"movers {len(d['movers'])}")
    for w in d["warnings"]:
        print(f"  WARNING: {w}")
