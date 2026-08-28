"""
Turn one Helius transaction into a sentence a human can act on, or admit we
cannot.

Two rules, both learned the hard way from the first version of this:

1. ATTRIBUTION. A wallet showing up in a transaction is not the same as the
   wallet DOING something. getSignaturesForAddress returns every transaction an
   address is merely mentioned in, which for routing and fee accounts is
   thousands a day. If the watched wallet is not an actor we return None and it
   never reaches Frank.

2. NO RAW ENUMS. Helius `type` and `source` are API constants. "UNKNOWN" and
   "PUMP_AMM" are not English. Either we can say what happened and how big it
   was, or we say we could not decode it. We never dress a constant up as
   meaning.
"""
import tokens

SOL_MINT = "So11111111111111111111111111111111111111112"
LAMPORTS = 1e9

# Raw Helius `source` -> the name a person would use. Anything absent is
# deliberately rendered as no venue at all rather than as its constant.
VENUES = {
    "JUPITER": "Jupiter", "RAYDIUM": "Raydium", "ORCA": "Orca",
    "METEORA": "Meteora", "PUMP_FUN": "Pump.fun", "PUMP_AMM": "Pump.fun",
    "PHOENIX": "Phoenix", "LIFINITY": "Lifinity", "OPENBOOK": "OpenBook",
    "ALDRIN": "Aldrin", "SABER": "Saber", "SERUM": "Serum",
}


def venue(src):
    return VENUES.get(src or "")


def _swap_legs(tx, wallet):
    """What the wallet put in and got out of a swap, in whole-token units."""
    sw = (tx.get("events") or {}).get("swap") or {}
    gave, got = [], []
    for x in sw.get("tokenInputs") or []:
        if x.get("userAccount") == wallet:
            r = x.get("rawTokenAmount") or {}
            amt = _whole(r.get("tokenAmount"), r.get("decimals"))
            if amt: gave.append((x.get("mint"), amt))
    for x in sw.get("tokenOutputs") or []:
        if x.get("userAccount") == wallet:
            r = x.get("rawTokenAmount") or {}
            amt = _whole(r.get("tokenAmount"), r.get("decimals"))
            if amt: got.append((x.get("mint"), amt))
    ni, no = sw.get("nativeInput"), sw.get("nativeOutput")
    if isinstance(ni, dict) and ni.get("account") == wallet:
        gave.append((SOL_MINT, float(ni.get("amount") or 0) / LAMPORTS))
    if isinstance(no, dict) and no.get("account") == wallet:
        got.append((SOL_MINT, float(no.get("amount") or 0) / LAMPORTS))
    return gave, got


def _whole(raw, decimals):
    try:
        return float(raw) / (10 ** int(decimals))
    except (TypeError, ValueError):
        return None


def is_actor(tx, wallet):
    """Did this wallet actually do anything, or is it just named in the logs?"""
    if tx.get("feePayer") == wallet:
        return True
    gave, got = _swap_legs(tx, wallet)
    if gave or got:
        return True
    for x in tx.get("tokenTransfers") or []:
        if wallet in (x.get("fromUserAccount"), x.get("toUserAccount")):
            return True
    for x in tx.get("nativeTransfers") or []:
        if wallet in (x.get("fromUserAccount"), x.get("toUserAccount")):
            return True
    return False


def _amount_str(mint, amt):
    sym = tokens.symbol(mint)
    if amt >= 1000:   n = f"{amt:,.0f}"
    elif amt >= 1:    n = f"{amt:,.2f}"
    else:             n = f"{amt:.4f}".rstrip("0").rstrip(".")
    return f"{n} {sym}" if sym else n + " of an unnamed token"


def _usd_of(legs):
    """Value a side of the trade. The SOL leg is priced far more reliably than a
    minutes-old memecoin, so prefer it."""
    for mint, amt in legs:
        if mint == SOL_MINT:
            v = tokens.usd_value(mint, amt)
            if v is not None:
                return v
    for mint, amt in legs:
        v = tokens.usd_value(mint, amt)
        if v is not None:
            return v
    return None


def describe(tx, wallet):
    """One transaction -> a record, or None when the wallet was a bystander.

    The record always carries `known`. When it is False the text says so in
    plain words and the caller can decide to drop it."""
    if not is_actor(tx, wallet):
        return None

    base = {"wallet": wallet, "ts": tx.get("timestamp") or 0,
            "sig": tx.get("signature") or "", "venue": venue(tx.get("source")),
            "usd": None, "known": False, "action": None}

    gave, got = _swap_legs(tx, wallet)
    if gave and got:
        sold_sol = any(m == SOL_MINT for m, _ in gave)
        usd = _usd_of(gave if sold_sol else got) or _usd_of(got if sold_sol else gave)
        action = "bought" if sold_sol else "sold"
        subject = got[0] if sold_sol else gave[0]
        counter = gave[0] if sold_sol else got[0]
        base.update(known=True, action=action, usd=usd,
                    text=f"{action} {_amount_str(*subject)} for {_amount_str(*counter)}")
        return base

    # a one-sided swap leg still tells us size and direction
    if gave or got:
        legs = got or gave
        action = "received" if got else "sent"
        base.update(known=True, action=action, usd=_usd_of(legs),
                    text=f"{action} {_amount_str(*legs[0])}")
        return base

    net = {}
    for x in tx.get("tokenTransfers") or []:
        amt = x.get("tokenAmount")
        if amt is None:
            continue
        if x.get("toUserAccount") == wallet:
            net[x.get("mint")] = net.get(x.get("mint"), 0) + float(amt)
        elif x.get("fromUserAccount") == wallet:
            net[x.get("mint")] = net.get(x.get("mint"), 0) - float(amt)
    for x in tx.get("nativeTransfers") or []:
        amt = float(x.get("amount") or 0) / LAMPORTS
        if x.get("toUserAccount") == wallet:
            net[SOL_MINT] = net.get(SOL_MINT, 0) + amt
        elif x.get("fromUserAccount") == wallet:
            net[SOL_MINT] = net.get(SOL_MINT, 0) - amt
    net = {m: v for m, v in net.items() if abs(v) > 1e-9}
    if net:
        mint, delta = max(net.items(), key=lambda kv: abs(tokens.usd_value(kv[0], abs(kv[1])) or 0))
        action = "received" if delta > 0 else "sent"
        base.update(known=True, action=action,
                    usd=tokens.usd_value(mint, abs(delta)),
                    text=f"{action} {_amount_str(mint, abs(delta))}")
        return base

    base["text"] = "made a transaction we could not decode"
    return base


def line(rec, short_addr):
    """One phone-width line. Size leads, because size is the signal."""
    money = tokens.money(rec.get("usd"))
    where = f" on {rec['venue']}" if rec.get("venue") else ""
    head = f"{short_addr(rec['wallet'])} {rec['text']}{where}"
    return f"{head} · {money}" if money else head
