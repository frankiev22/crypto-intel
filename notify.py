"""Discord output. No-ops loudly when the webhook is unset."""
import json, urllib.request, config
import evidence

def send(content=None, embeds=None):
    if not config.DISCORD_WEBHOOK:
        print("[notify] CRYPTO_DISCORD_WEBHOOK unset - would have sent:")
        if content: print("  " + content[:400])
        if embeds:  print(f"  + {len(embeds)} embed(s)")
        return False
    body = {}
    if content: body["content"] = content[:1900]
    if embeds:  body["embeds"] = embeds[:10]
    # Discord sits behind Cloudflare, which rejects urllib's default agent with
    # error 1010. The User-Agent is not optional. ?wait=true makes Discord hand
    # back the created message so callers can verify delivery instead of
    # trusting a bare 2xx.
    req = urllib.request.Request(config.DISCORD_WEBHOOK + "?wait=true",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json",
                     "User-Agent": "DiscordBot (crypto-intel, 0.0.1)"}, method="POST")
    try:
        r = urllib.request.urlopen(req, timeout=15)
        msg = json.loads(r.read().decode("utf-8", "ignore") or "{}")
        return msg.get("id") or True
    except Exception as e:
        print(f"[notify] failed: {e}"); return False

def candidate_embed(r):
    warn = ("\n**WARN** " + "; ".join(r["flags"])) if r.get("flags") else ""
    # Every alert carries its own track record: what this score band has
    # actually returned. Thin samples say so rather than looking authoritative.
    # The GRADE is shown, never the raw score: a 100 beside a live mint authority
    # is the most dangerous line this system can send. Band history is a record
    # of SCORE bands, so it is shown only where grade and score agree.
    g, label = r.get("grade", 0), r.get("grade_label")
    _h = evidence.band_line(r.get("score")) if g == r.get("score") else None
    hist = ("\n_" + _h + "_") if _h else ""
    trap = bool(label) and label.startswith("TRAP")
    title = (f"{r['name']} - TRAP, mint/freeze authority live" if trap
             else f"{r['name']} - grade {g} of 100" + (f" ({label})" if label else ""))
    return {"title": title,
            "url": r.get("url",""),
            "color": 0xe74c3c if trap else (0x2ecc71 if g >= 85 else 0xf1c40f),
            "description": f"liq **${r['liq']:,.0f}** · 24h vol **${r['v24']:,.0f}** · "
                           f"{r['age_h']:.1f}h old · 1h **{r['chg_h1']:+.1f}%**\n"
                           f"{', '.join(r.get('reasons',[]))}{warn}{hist}",
            "footer": {"text": r.get("addr","")[:44]}}
