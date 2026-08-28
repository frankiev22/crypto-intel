"""
Sentiment axis.

0.0.1 derives sentiment from CryptoPanic vote counts only. The point of this
file is the SHAPE, not the cleverness: a source is a function taking symbols and
returning a Reading, and Reddit or Farcaster drop into SOURCES later without the
digest changing at all.

A source that has no data returns score=None. It never returns 0.0, because a
fabricated neutral and a real neutral are different facts and the digest says so.
"""
import news

# a Reading is: dict(source, ok, score, n, detail)
#   score  -1.0 hostile .. +1.0 euphoric, or None when there is nothing to read
#   n      how many items the score rests on


def _reading(source, ok, score, n, detail):
    return {"source": source, "ok": ok, "score": score, "n": n, "detail": detail}


def cryptopanic_source(symbols=("BTC", "ETH", "SOL")):
    ps, status = news.posts(symbols)
    if not ps:
        return _reading("cryptopanic", False, None, 0, status)
    pos = sum(p["positive"] + p["liked"] for p in ps)
    neg = sum(p["negative"] + p["disliked"] for p in ps)
    tot = pos + neg
    if tot == 0:
        return _reading("cryptopanic", True, None, len(ps), f"{len(ps)} posts, zero votes cast")
    return _reading("cryptopanic", True, (pos - neg) / tot, len(ps),
                    f"{len(ps)} posts, {pos} up / {neg} down")


# Add reddit_source / farcaster_source here. Same signature, same Reading.
SOURCES = [cryptopanic_source]


def read(symbols=("BTC", "ETH", "SOL")):
    """Every source, plus a blended score over the ones that actually reported."""
    readings = [fn(symbols) for fn in SOURCES]
    live = [r for r in readings if r["score"] is not None]
    if not live:
        return {"score": None, "n": 0, "readings": readings}
    n = sum(r["n"] for r in live)
    blended = sum(r["score"] * r["n"] for r in live) / n if n else None
    return {"score": blended, "n": n, "readings": readings}


def label(score):
    if score is None:      return "no data"
    if score >=  0.50:     return "euphoric"
    if score >=  0.15:     return "positive"
    if score > -0.15:      return "mixed"
    if score > -0.50:      return "negative"
    return "hostile"
