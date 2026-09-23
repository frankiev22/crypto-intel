"""Turn 49 scraped daily recaps into one row per (date, ticker) mention.

⛔ Three things in the raw text will corrupt this if ignored, and each is
handled explicitly below:

1. **Every post QUOTES the previous day's post.** The quoted block is the prior
   recap in full, so parsing the whole innerText double-counts roughly half the
   archive and back-dates mentions by a day. Cut at the `Quote` marker.
2. **A cashtag renders on its own line.** X links `$COCO`, so innerText gives
   "- \n$COCO\n ran to $4.6m...". Bullets must be re-joined across lines or every
   ticker ends up in a bullet with no text.
3. **`$4.6m` is money, `$COCO` is a ticker.** A naive dollar-word pattern reads "4" as a
   ticker. The ticker pattern therefore requires a leading letter, and CJK
   tickers (牛马, 牛来) need their own pattern or they vanish silently.

Output is one JSON of posts -> bullets -> {tickers, mcaps, text}, plus a flat
mentions list. No network, no chain reads. Those come next.
"""
import io
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))

MONTHS = {m: i + 1 for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"])}

HEAD_RE = re.compile(r"What you missed[^,\n]*,\s*([A-Z][a-z]+)\s+(\d{1,2})")
TS_TAIL_RE = re.compile(r"^\d{1,2}:\d{2}\s*(AM|PM)\b.*\d{4}\s*$", re.I)
TICKER_RE = re.compile(r"\$([A-Za-z][A-Za-z0-9_]{1,14})\b")
CJK_RE = re.compile(r"\$([一-鿿]{1,8})")
MONEY_RE = re.compile(r"\$(\d+(?:\.\d+)?)\s*([mkb])\b", re.I)
MULT = {"k": 1e3, "m": 1e6, "b": 1e9}


def content_date(text, posted_iso):
    """The post's own headline date, NOT the posting timestamp.

    Posts go up around 01:00-03:00 UTC covering the previous day, so using the
    posting timestamp shifts every row one day late.
    """
    m = HEAD_RE.search(text)
    if not m:
        return None
    mon, day = MONTHS.get(m.group(1)), int(m.group(2))
    if not mon:  # "Sept 1st" / "Sep 1st" / "Aug 4th" abbreviations
        pre = m.group(1).lower().rstrip('.')
        for name, num in MONTHS.items():
            if name.lower().startswith(pre) or pre.startswith(name.lower()[:3]):
                mon = num
                break
    if not mon:
        return None
    year = int(posted_iso[:4])
    # a January post quoting a December day would need a rollback; none here
    return f"{year:04d}-{mon:02d}-{day:02d}"


def body_only(text):
    """Drop the quoted previous post and the trailing timestamp line."""
    for marker in ("\nQuote\n", "\nQuote Post\n"):
        i = text.find(marker)
        if i >= 0:
            text = text[:i]
    lines = [L for L in text.split("\n") if not TS_TAIL_RE.match(L.strip())]
    return "\n".join(lines)


def bullets(body):
    """Re-join wrapped bullets. A bullet starts at a line beginning with '-'."""
    out, cur = [], None
    for raw in body.split("\n"):
        L = raw.rstrip()
        s = L.strip()
        if not s:
            continue
        if s.startswith("-") and not re.match(r"^-\s*\d+(\.\d+)?%", s):
            if cur:
                out.append(cur)
            cur = s.lstrip("-").strip()
        elif cur is not None:
            cur = (cur + " " + s).strip()
    if cur:
        out.append(cur)
    return [re.sub(r"\s{2,}", " ", b) for b in out if b]


def tickers_in(s):
    found = []
    for m in TICKER_RE.finditer(s):
        t = m.group(1)
        if t.lower() in ("m", "k", "b"):
            continue
        if t.upper() not in found:
            found.append(t.upper())
    for m in CJK_RE.finditer(s):
        if m.group(1) not in found:
            found.append(m.group(1))
    return found


def mcaps_in(s):
    return [round(float(v) * MULT[u.lower()]) for v, u in MONEY_RE.findall(s)]


def main():
    posts = json.load(io.open(os.path.join(HERE, "posts_raw.json"), encoding="utf-8"))
    out, mentions = [], []
    for p in posts:
        body = body_only(p["text"])
        d = content_date(body, p["dt"])
        bs = []
        for b in bullets(body):
            tk = tickers_in(b)
            bs.append({"text": b, "tickers": tk, "mcaps": mcaps_in(b)})
            for t in tk:
                mentions.append({"ticker": t, "date": d, "posted": p["dt"],
                                 "post_id": p["id"], "text": b,
                                 "mcaps": mcaps_in(b)})
        out.append({"post_id": p["id"], "posted": p["dt"], "date": d,
                    "n_bullets": len(bs), "bullets": bs})

    json.dump(out, io.open(os.path.join(HERE, "posts_parsed.json"), "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)
    json.dump(mentions, io.open(os.path.join(HERE, "mentions.json"), "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)

    from collections import Counter
    c = Counter(m["ticker"] for m in mentions)
    dates = sorted({p["date"] for p in out if p["date"]})
    lines = [
        f"posts parsed        {len(out)}",
        f"content dates       {dates[0]} .. {dates[-1]}  ({len(dates)} distinct)",
        f"posts with no date  {sum(1 for p in out if not p['date'])}",
        f"bullets             {sum(p['n_bullets'] for p in out)}",
        f"ticker mentions     {len(mentions)}",
        f"distinct tickers    {len(c)}",
        "",
        "most mentioned:",
    ]
    for t, n in c.most_common(30):
        lines.append(f"  {t:14s} {n}")
    lines.append("")
    lines.append("mentioned once: %d" % sum(1 for t, n in c.items() if n == 1))
    io.open(os.path.join(HERE, "parse_report.txt"), "w", encoding="utf-8").write("\n".join(lines))
    print("\n".join(lines[:12]))
    print("... full report in parse_report.txt")


if __name__ == "__main__":
    main()
