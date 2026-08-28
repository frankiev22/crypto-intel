"""
crypto-intel v0.0.1 - the nightly digest.

One entry point, one Discord message, four axes: regime, news, sentiment,
whales. Every axis fails independently; a dead axis is reported as dead and the
rest still ship. Nothing in the output is invented - if a number is not real it
does not appear.

    python digest.py            build and send
    python digest.py --dry      build and print, send nothing
    python digest.py --window 6h

Alert thresholds live at the top of this file. They are the product; tune them.
"""
import sys, json, os, time, datetime as dt

import config, macro, news, sentiment, wallets, notify, publish, moves, tokens

# Windows consoles default to cp1252 and die on the alert glyph. The payload
# stays unicode - only the local terminal gets downgraded.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

VERSION = "0.0.1"

# ---- alert thresholds. tune these ----
FG_GREED       = 75      # fear/greed at or above -> crowded
FG_FEAR        = 25      # at or below -> capitulation
PRICE_MOVE_PCT = 5.0     # abs 24h move on a major worth flagging
STABLE_FLOW    = 0.15    # abs 24h stablecoin supply % change worth flagging
SENT_HOT       = 0.50
SENT_COLD      = -0.50
WHALE_MIN_USD  = 500     # a move smaller than this is not a whale
WHALE_ALERT_USD= 1000    # combined size inside the window worth a ping
WINDOW_S       = 3600


def _safe(fn, *a, **kw):
    """Run an axis. Return (value, error_string)."""
    try:
        return fn(*a, **kw), None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"[:120]


def collect(window_s=WINDOW_S):
    out = {"ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "version": VERSION, "window_s": window_s, "errors": {}}

    snap, err = _safe(macro.snapshot)
    out["macro"] = snap
    if err: out["errors"]["macro"] = err

    # the RSS axis is collected continuously by the Supabase Edge Function;
    # the digest just reads what accumulated since the last one.
    ps, err = _safe(news.stored)
    if err:
        out["news"], out["news_status"] = [], err
        out["errors"]["news"] = err
    else:
        out["news"], out["news_status"] = ps[0], ps[1]

    sent, err = _safe(sentiment.read)
    out["sentiment"] = sent
    if err: out["errors"]["sentiment"] = err

    wl, mode = wallets.load_watchlist_v2()
    out["watchlist_n"], out["watchlist_mode"] = len(wl), mode
    res, err = _safe(wallets.recent_moves, list(wl), window_s, 5)
    recs, stats = (res if res else ([], {}))
    out["whales"] = [r for r in recs if (r.get("usd") or 0) >= WHALE_MIN_USD]
    out["whales_small"] = len(recs) - len(out["whales"])
    out["whale_stats"] = stats
    if err: out["errors"]["whales"] = err

    out["alerts"] = alerts(out)
    return out


def alerts(d):
    a = []
    m = d.get("macro") or {}
    if m:
        fg = m.get("fear_greed")
        if fg is not None and fg >= FG_GREED: a.append(f"Greed {fg} - crowded tape")
        if fg is not None and fg <= FG_FEAR:  a.append(f"Fear {fg} - capitulation zone")
        for sym, k in (("BTC", "btc"), ("ETH", "eth"), ("SOL", "sol")):
            ch = m.get(f"{k}_24h")
            if ch is not None and abs(ch) >= PRICE_MOVE_PCT:
                a.append(f"{sym} {ch:+.1f}% 24h")
        sc = m.get("stablecoin_chg_24h")
        if sc is not None and abs(sc) >= STABLE_FLOW:
            a.append(f"Stables {sc:+.2f}% 24h - "
                     + ("inflow" if sc > 0 else "capital leaving"))
    s = (d.get("sentiment") or {}).get("score")
    if s is not None and s >= SENT_HOT:  a.append(f"Sentiment euphoric {s:+.2f}")
    if s is not None and s <= SENT_COLD: a.append(f"Sentiment hostile {s:+.2f}")
    big = d.get("whales") or []
    total = sum(r.get("usd") or 0 for r in big)
    if total >= WHALE_ALERT_USD:
        a.append(f"{tokens.money(total)} of tracked-wallet trading in "
                 f"{d['window_s']//60}m across {len(big)} move{'s' if len(big)!=1 else ''}")
    return a


def _short(w):
    return w[:4] + ".." + w[-4:]


def _roll(moves):
    """Collapse repeats into one line with a count. A wallet firing the same
    swap six times is one fact on a phone screen, not six."""
    seen = {}
    for mv in moves:
        typ, src = mv["type"], mv["source"]
        if typ in ("UNKNOWN", "", None):
            what = f"activity on {src}" if src else "activity"
        else:
            what = f"{typ.lower()} on {src}" if src else typ.lower()
        k = f"{_short(mv['wallet'])} {what}"
        seen[k] = seen.get(k, 0) + 1
    return sorted(seen.items(), key=lambda t: -t[1])


def render(d):
    """Phone-shaped. Short lines, no tables, nothing that needs a sideways scroll."""
    L = []
    ts = dt.datetime.fromisoformat(d["ts"]).strftime("%a %d %b %H:%M UTC")
    L.append(f"**CRYPTO INTEL** v{d['version']}")
    L.append(ts)

    m = d.get("macro")
    if m:
        L.append("")
        L.append(f"**REGIME** · Fear/Greed {m['fear_greed']} ({m['fear_greed_label']})")
        L.append(f"BTC ${m['btc']:,.0f} · {m['btc_24h']:+.1f}%")
        L.append(f"ETH ${m['eth']:,.0f} · {m['eth_24h']:+.1f}%")
        L.append(f"SOL ${m['sol']:,.2f} · {m['sol_24h']:+.1f}%")
        L.append(f"BTC dom {m['btc_dominance']:.1f}% · mcap {m['mcap_change_24h']:+.1f}%")
        L.append(f"Stables ${m['stablecoin_supply']/1e9:,.0f}B · {m['stablecoin_chg_24h']:+.2f}%")
    else:
        L.append("\n**REGIME** unavailable: " + d["errors"].get("macro", "?"))

    s = d.get("sentiment") or {}
    L.append("")
    if s.get("score") is None:
        det = "; ".join(r["detail"] for r in s.get("readings", [])) or "no sources"
        L.append(f"**SENTIMENT** no data")
        L.append(f"_{det}_")
    else:
        L.append(f"**SENTIMENT** {sentiment.label(s['score'])} ({s['score']:+.2f}, n={s['n']})")
        for r in s.get("readings", []):
            L.append(f"· {r['source']}: {r['detail']}")

    L.append("")
    if d.get("news"):
        L.append(f"**NEWS** {d.get('news_status','')}")
        for p in d["news"][:4]:
            flag = (p.get("alert_reason") or "").split(" · ")[0]
            tag = f"[{flag}] " if flag else ""
            L.append(f"· {tag}{p['title'][:66]}")
            L.append(f"  _{p.get('outlet','')}_")
    else:
        L.append(f"**NEWS** none - {d.get('news_status','')}")

    L.append("")
    wn = d.get("watchlist_n", 0)
    big = d.get("whales") or []
    st = d.get("whale_stats") or {}
    mins = d["window_s"] // 60
    if not wn:
        L.append("**WHALES** watchlist empty")
    elif big:
        total = tokens.money(sum(r.get("usd") or 0 for r in big))
        L.append(f"**WHALES** {wn} tracked · {len(big)} move(s), {total} in {mins}m")
        for r in big[:4]:
            L.append("· " + moves.line(r, _short))
    else:
        L.append(f"**WHALES** {wn} tracked · nothing above "
                 f"{tokens.money(WHALE_MIN_USD)} in {mins}m")
    quiet = []
    if d.get("whales_small"):   quiet.append(f"{d['whales_small']} smaller trade(s)")
    if st.get("undecoded"):     quiet.append(f"{st['undecoded']} Helius could not decode")
    if st.get("bystander"):     quiet.append(f"{st['bystander']} where the wallet only appeared, did not act")
    if quiet:
        L.append("_also: " + "; ".join(quiet) + "_")

    if d.get("alerts"):
        L.append("")
        L.append("**ALERTS**")
        for a in d["alerts"]:
            L.append(f"⚠ {a}")

    if d.get("errors"):
        L.append("")
        L.append("_axis errors: " + ", ".join(d["errors"]) + "_")
    return "\n".join(L)


def main():
    window = WINDOW_S
    if "--window" in sys.argv:
        v = sys.argv[sys.argv.index("--window") + 1]
        window = int(v[:-1]) * (3600 if v.endswith("h") else 60) if v[-1] in "hm" else int(v)

    print(f"  building digest (window {window//60}m)...")
    d = collect(window)
    body = render(d)
    print("\n" + "-" * 46 + "\n" + body + "\n" + "-" * 46 + "\n")

    os.makedirs("data/digests", exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    json.dump(d, open(f"data/digests/{stamp}.json", "w"), indent=1)

    # --dry means PREVIEW. It must not touch the public dashboard either; this
    # check used to sit below the publish call, so every dry run shipped a real
    # digest to the site.
    if "--dry" in sys.argv:
        print("  --dry: nothing published, nothing sent."); return

    # push to Supabase for the public dashboard. Independent of Discord: if the
    # site is down Frank still gets the ping, and vice versa.
    row, pstatus = publish.publish(d)
    print(f"  supabase: {pstatus}" + (f" (row {row})" if row else ""))
    if not config.DISCORD_WEBHOOK:
        p = f"data/digests/{stamp}.txt"
        open(p, "w", encoding="utf-8").write(body)
        print(f"  CRYPTO_DISCORD_WEBHOOK unset - digest written to {p}")
        print("  paste the webhook into .env and rerun to deliver it.")
        return
    ok = notify.send(content=body)
    print(f"  sent to Discord, message id {ok}" if ok else "  Discord send FAILED - see above.")


if __name__ == "__main__":
    main()
