"""⭐ THE BACKEND THE SITE CALLS. One question in, one answered report out.

Frank, 2026-09-23: *"Let's take everything we have been talking about and
discovered and implement it into our site in a meaningful way."*

**The wedge: connect a wallet and find out what you actually own.** Reading
Frank's wallet by hand tonight taught him that his PURR is not Hyperliquid's
token, that the thing he called "Fone" is apeonfone, and that he holds 195,771
units of a mint with no pools. He had been trading for weeks. Every portfolio
tracker showed him a green number. **None of them say "this position has no
market" or "this cap sits on $342 of real liquidity."** That is the product.

---

## ⛔ Three rules this module exists to enforce, all bought with real mistakes

1. **NEVER ONE POOL.** Every liquidity figure is summed across every pair for
   the mint (`allpairs`). Reading one pool on a token that trades across thirty
   is a 3% sample reported as the whole; it cost a full day of wrong EMBER
   analysis. Standing rule 18.
2. **HONEST NULLS.** A field that could not be checked says so, in
   `not_checked`, with a reason. It never defaults to a value that reads as a
   pass. That is the `authority_live=None` bug class: *not checked* rendering as
   *checked and fine*. Standing rule 5.
3. **PROVENANCE ON EVERY NUMBER.** Each response carries `provenance`: which
   call produced which field and when. A number with no source is not a number.

## ⛔ Read-only, totally and permanently

Nothing here signs, submits, delegates, approves or holds anything. `wallet()`
takes a **public key** and reads public chain state. There is no code path that
can move a token, and none may ever be added to this file.

## ⚠️ What the numbers are and are not

- `liq_usd` and friends come from Dexscreener, a field measured **overstating by
  a median 781x**. Summing it correctly yields a correct sum of an overstating
  field. **It is for shape: how many pools, which quote assets, is the cap
  backed at all.**
- ⭐ **The only exit number is `exit_depth`**, which quotes Jupiter across every
  venue and reports what a seller receives. When the two disagree, the quote
  wins.

## ⛔⛔ THIS API SELLS FACTS, NOT A SCORE

Frank: *"We need to seriously improve our scoring system before we can sell
it."* ⭐ **The answer is to retire it as a product, not to improve it.** Marino
is why: perfect knowledge of graduation probability still loses money, because by
the time a signal is readable it is priced. Five ranking models have been built
and retracted in this repo, and `test_scoreband.py` already fails at the AST
level if a score term reappears in any entry gate.

**What is sellable is the set of things that are checkable and that nobody
publishes:** bundled or not, liquidity real or phantom, exit depth at a stated
size, mint and freeze authority live or revoked, who else holds it and how many
other launches those same wallets top-hold. Every one of those is a fact the
reader can verify against the chain. **None of them needs a hit rate to defend,
because none of them predicts anything.**

⛔ **So no endpoint here returns a score, a grade, a rank or an expected
return, and none ever may.** Any internal score stays internal.

## ⛔ No model call on the hot path

Every number in every response is arithmetic over RPC and index reads. **If an
endpoint ever needs an LLM call to return a number, that is a design error.** A
narrative layer may be added on top, cached per contract, but it may never sit
between a question and its number.
"""
import json
import os
import time

import allpairs
import chainfields

SPL = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN22 = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
WSOL = "So11111111111111111111111111111111111111112"
UA = {"User-Agent": "Mozilla/5.0 (crypto-intel research; contact via github)"}

# ⛔ PRE-COMMITTED before any of these were run against live data (rule 6).
PHANTOM_MCAP = 1_000_000          # a cap above this...
PHANTOM_LIQ = 1_000               # ...on less than this, across ALL pairs
RESOLVE_DOMINANCE = 5.0           # the winner must hold >= 5x the runner-up
THIN_LIQ = 25_000                 # below this a token is THIN, not LIQUID
WALLET_MAX_POSITIONS = 60         # refuse to silently truncate beyond this
DUST_USD = 1.00                   # positions under this are counted, not priced

# Public reads, so cache hard. Seconds.
TTL = {"liquidity": 60, "resolve": 300, "phantom": 60, "exit_depth": 30,
       "safety": 180, "paired": 900, "wallet": 30, "mint": 900,
       "concentration": 600}

_CACHE = {}


# --------------------------------------------------------------------------
# provenance and honest nulls
# --------------------------------------------------------------------------
class Report:
    """A response that cannot lose track of where its numbers came from."""

    def __init__(self, kind, subject):
        self.out = {"kind": kind, "subject": subject, "ok": True,
                    "ts": _now_iso(), "data": {}, "provenance": [],
                    "not_checked": [], "warnings": []}

    def put(self, field, value, source, note=None):
        self.out["data"][field] = value
        self.out["provenance"].append({"field": field, "source": source,
                                       "at": _now_iso(), "note": note})
        return value

    def unchecked(self, field, why):
        """⛔ The field exists, is None, and SAYS WHY. Never a default."""
        self.out["data"].setdefault(field, None)
        self.out["not_checked"].append({"field": field, "why": why})

    def warn(self, msg):
        self.out["warnings"].append(msg)

    def fail(self, why):
        self.out["ok"] = False
        self.out["error"] = why
        return self.out

    def done(self):
        return self.out


def _now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _cached(kind, key, fn):
    ttl = TTL.get(kind, 60)
    k = (kind, key)
    hit = _CACHE.get(k)
    if hit and (time.time() - hit[0]) < ttl:
        return hit[1]
    val = fn()
    # ⛔ Never cache a failure. A network blip must not become a sticky "dead".
    if isinstance(val, dict) and val.get("ok") is False:
        return val
    _CACHE[k] = (time.time(), val)
    return val


def _is_mint(s):
    return isinstance(s, str) and 32 <= len(s) <= 44 and s.strip() == s


# --------------------------------------------------------------------------
# 2. liquidity(mint)  - built first, because everything below depends on it
# --------------------------------------------------------------------------
def liquidity(mint):
    """⭐ Liquidity and volume summed across EVERY pair for this mint.

    ⛔ Never one pool. `deepest_pool_liq_usd` is reported beside the total so the
    size of the error a single-pool read would have made is visible, not hidden:
    on the real EMBER that is $663,260 against $2,331,895, a 3.5x understatement.

    ⚠️ `is_floor` is true when Dexscreener returned its 30-pair cap. **30 means
    "30 or more"** - SOL returns 30 too - and the pairs left out cannot be
    bounded, because the returned set is not ordered by size.
    """
    if not _is_mint(mint):
        return Report("liquidity", mint).fail(
            "that is not a contract address. Key on the address, never the "
            "ticker - tickers are not unique and are trivially cloned.")
    return _cached("liquidity", mint, lambda: _liquidity(mint))


def _liquidity(mint):
    r = Report("liquidity", mint)
    t = allpairs.token(mint)
    if not t.get("ok"):
        r.warn("the price index did not answer. This is NOT evidence the token "
               "is dead - that distinction is the `gone` bug (journal.py:974).")
        return r.fail("liquidity lookup failed: " + str(t.get("error")))

    src = "dexscreener /latest/dex/tokens (all pairs summed)"
    r.put("symbol_display", t.get("symbol_display"), src,
          "⚠️ DISPLAY ONLY. The key is the address. Check symbol_flags before "
          "rendering it: a symbol can display as a name it does not contain.")
    r.put("name_display", t.get("name_display"), src)
    r.put("symbol_flags", _symbol_flags(t.get("symbol_display")), "derived",
          "docs/SYMBOL_ATTACKS.md - bidi controls and mixed script")
    r.put("pair_count", t["pair_count"], src)
    r.put("is_floor", bool(t.get("truncated")), src,
          "true = the 30-pair API cap was hit, so every total here is a FLOOR")
    r.put("liq_usd", t["total_liq_usd"], src,
          "⚠️ reported liquidity, measured overstating by a median 781x. "
          "Shape only. The exit number is exit_depth().")
    r.put("vol24_usd", t["total_vol24_usd"], src)
    r.put("mcap_usd", t.get("mcap_usd"), src)
    r.put("price_usd", t.get("price_usd"), src, "from the deepest pool")
    r.put("venues", t.get("venues"), src)
    r.put("quote_assets", {k: round(v["liq_usd"], 2)
                           for k, v in (t.get("quote_assets") or {}).items()}, src)
    r.put("deepest_pool_liq_usd", t.get("single_pair_would_have_said"), src)
    r.put("single_pool_would_understate_by", t.get("single_pair_understates_by"), src,
          "how wrong reading one pool would have been")
    r.put("first_pool_ms", t.get("first_pair_ms"), src)
    r.put("chains", t.get("chains"), src)
    r.put("shape", allpairs.verdict(t), "derived",
          f"LIQUID >= ${THIN_LIQ:,}, THIN above $1,000, else NO_LIQUIDITY; "
          f"PHANTOM and UNKNOWN_TRUNCATED are separate answers")
    if t.get("truncated"):
        r.warn(f"{t['pair_count']} pairs is the API cap. The real total is "
               f"higher than ${t['total_liq_usd']:,.0f} by an unknown amount.")
    return r.done()


# --------------------------------------------------------------------------
# 3. phantom(mint)
# --------------------------------------------------------------------------
def phantom(mint):
    """⛔ Is this market cap backed by anything at all?

    The case that forced the rule: a mint symbol'd EMBER claiming
    **$1,314,046,208** of market cap on **$1.39** of liquidity across all three
    of its pairs. It was analysed for a full day as a real token that had died.

    ⚠️ The rule needs a COMPLETE sample. Thirty arbitrary pools summing to
    nothing says nothing about a thirty-first, and the API returns at most
    thirty, unsorted. A truncated sample therefore returns
    `verdict: UNEVALUABLE`, never `false`.
    """
    if not _is_mint(mint):
        return Report("phantom", mint).fail("that is not a contract address.")
    return _cached("phantom", mint, lambda: _phantom(mint))


def _phantom(mint):
    r = Report("phantom", mint)
    liq = liquidity(mint)
    if not liq.get("ok"):
        return r.fail(liq.get("error"))
    d = liq["data"]
    mcap, total, n = d.get("mcap_usd"), d.get("liq_usd"), d.get("pair_count")
    src = "derived from liquidity(mint), rule pre-committed in intel.py"

    r.put("rule", f"market cap > ${PHANTOM_MCAP:,} while total liquidity across "
                  f"ALL pairs < ${PHANTOM_LIQ:,}", src)
    r.put("mcap_usd", mcap, "liquidity(mint)")
    r.put("liq_all_pairs_usd", total, "liquidity(mint)")
    r.put("pair_count", n, "liquidity(mint)")

    if mcap is None or total is None:
        r.unchecked("verdict", "no market cap or no liquidity reading, so the "
                               "rule cannot be evaluated. This is not a pass.")
        return r.done()
    triggered = mcap > PHANTOM_MCAP and total < PHANTOM_LIQ
    if triggered and d.get("is_floor"):
        r.put("verdict", "UNEVALUABLE", src)
        r.warn("the pair list hit the 30-pair API cap, so the sample is "
               "incomplete and the phantom rule may not be applied to it.")
        return r.done()
    r.put("verdict", "PHANTOM" if triggered else "BACKED", src)
    if triggered:
        r.put("backing_ratio", (total / mcap) if mcap else None, "derived",
              "dollars of real liquidity per dollar of claimed cap")
        r.warn(f"⛔ ${mcap:,.0f} of claimed market cap on ${total:,.2f} of "
               f"liquidity across all {n} pairs. There is nothing behind the "
               f"cap. Do not price it, do not report a multiple on it.")
    return r.done()


# --------------------------------------------------------------------------
# 4. exit_depth(mint, size_usd)  - the only realizable number in the system
# --------------------------------------------------------------------------
def exit_depth(mint, size_usd=100, raw_qty=None):
    """⭐ What a seller actually receives, at the size actually held.

    Not "there is $500k of liquidity" but "$94 back on $100, $1,780 back on
    $2,000". Two modes:

    - `size_usd`  : buy that much and sell it straight back (`round_trip`).
    - `raw_qty`   : price the EXACT position held, in raw token units
                    (`sell_quote`). ⭐ This is the one that matters for a
                    wallet, because a round trip at $100 says nothing about
                    exiting 195,771 units.

    ⛔ Both legs are QUOTES. Nothing is executed and no wallet is involved.

    ⚠️ A failed quote is not a route answer. Only Jupiter's own error code makes
    NO_SELL_ROUTE; an outage returns QUOTE_FAILED and the caller must not read
    it as a loss.
    """
    if not _is_mint(mint):
        return Report("exit_depth", mint).fail("that is not a contract address.")
    key = f"{mint}:{raw_qty if raw_qty is not None else size_usd}"
    return _cached("exit_depth", key, lambda: _exit_depth(mint, size_usd, raw_qty))


def _exit_depth(mint, size_usd, raw_qty):
    r = Report("exit_depth", mint)
    if raw_qty is not None:
        q = chainfields.sell_quote(mint, int(raw_qty))
        src = "jupiter quote (sell the exact position). NOTHING EXECUTED."
        r.put("mode", "position", src)
        r.put("raw_qty", int(raw_qty), src)
        r.put("verdict", q.get("verdict"), src)
        r.put("usd_out", q.get("usd_out"), src)
        r.put("price_impact_pct", q.get("price_impact_pct"), src)
        r.put("venues", q.get("venues"), src)
        if q.get("verdict") == "QUOTE_FAILED":
            r.unchecked("usd_out", "the quote API did not answer. ⛔ This is NOT "
                                   "a total loss and must never be shown as $0.")
        elif q.get("verdict") == "NO_SELL_ROUTE":
            r.warn("⛔ NO SELL ROUTE. This position cannot be sold at any size "
                   "right now. That is an answer, not an error.")
        if q.get("error"):
            r.put("error", q["error"], src)
        return r.done()

    q = chainfields.round_trip(mint, size_usd)
    src = f"jupiter round trip at ${size_usd} (buy then sell back). NOTHING EXECUTED."
    r.put("mode", "round_trip", src)
    r.put("probe_usd", size_usd, src)
    r.put("verdict", q.get("verdict"), src,
          "TRADEABLE <10% cost, COSTLY 10-50%, TOTAL_LOSS >50%, "
          "NO_SELL_ROUTE / NO_BUY_ROUTE are answers")
    r.put("usd_back", q.get("usd_back"), src)
    r.put("cost_pct", q.get("rt_cost_pct"), src)
    r.put("price_impact_pct", q.get("price_impact_pct"), src)
    r.put("venues", q.get("venues"), src)
    if q.get("verdict") is None:
        r.unchecked("usd_back", f"no quote could be obtained ({q.get('error')}). "
                                f"⛔ Unknown, not zero and not a loss.")
    if q.get("error"):
        r.put("error", q["error"], src)
    return r.done()


# --------------------------------------------------------------------------
# 1. resolve(ticker)
# --------------------------------------------------------------------------
def resolve(ticker, since=None, chain=None, max_candidates=25):
    """⭐ Every mint wearing this ticker, which one is real, and who the fakes are.

    **This single function would have saved the entire day.** There are 16
    distinct mints symbol'd EMBER, two of them both named "embercurve" on
    Solana, and the one analysed all day was a phantom holding $1.39.

    ⛔ PRE-COMMITTED RULE, written here before it was run:

      1. Candidates are every mint whose symbol equals the ticker, from two
         independent searches (Dexscreener and Jupiter).
      2. Each is measured with all-pairs liquidity. Never one pool.
      3. ⭐ If `since` is given (the date the ticker was first talked about),
         candidates whose FIRST POOL POSTDATES it are rejected. This is the rule
         that got EMBER right when a hand-check got it wrong: the phantom's
         first pool was twelve days after the mention.
      4. Phantoms can never win, but are still listed.
      5. The winner is the highest total liquidity, and is only called RESOLVED
         if it holds >= RESOLVE_DOMINANCE x the runner-up. Otherwise AMBIGUOUS
         and **nothing is called real**.

    ⚠️ RESOLVED means "this is the mint that ticker most likely denotes today".
    It is not a claim that any particular person meant it.
    """
    if not isinstance(ticker, str) or not ticker.strip():
        return Report("resolve", ticker).fail("no ticker given")
    key = f"{ticker.upper()}:{since}:{chain}"
    return _cached("resolve", key,
                   lambda: _resolve(ticker.strip(), since, chain, max_candidates))


def _search_candidates(ticker):
    seen = {}
    st, b = chainfields._get(
        "https://api.dexscreener.com/latest/dex/search?q=" + ticker,
        headers=UA, timeout=25)
    for p in ((b or {}).get("pairs") or []) if isinstance(b, dict) else []:
        bt = p.get("baseToken") or {}
        if (bt.get("symbol") or "").upper() != ticker.upper():
            continue
        seen.setdefault((p.get("chainId"), bt.get("address")),
                        {"chain": p.get("chainId"), "mint": bt.get("address"),
                         "name": bt.get("name"), "symbol": bt.get("symbol"),
                         "seen_in": ["dexscreener"]})
    time.sleep(0.3)
    st, b = chainfields._get(
        "https://lite-api.jup.ag/tokens/v2/search?query=" + ticker,
        headers=UA, timeout=25)
    for t in (b if isinstance(b, list) else []):
        if (t.get("symbol") or "").upper() != ticker.upper():
            continue
        k = ("solana", t.get("id"))
        if k in seen:
            seen[k]["seen_in"].append("jupiter")
        else:
            seen[k] = {"chain": "solana", "mint": t.get("id"),
                       "name": t.get("name"), "symbol": t.get("symbol"),
                       "seen_in": ["jupiter"]}
    return [v for v in seen.values() if v["mint"]]


def _resolve(ticker, since, chain, max_candidates):
    r = Report("resolve", ticker)
    src_rule = "pre-committed rule in intel.resolve()"
    r.put("rule", {"dominance_required": RESOLVE_DOMINANCE,
                   "since": since, "chain": chain,
                   "phantoms_cannot_win": True,
                   "date_rule": "a candidate whose first pool postdates `since` "
                                "is rejected"}, src_rule)

    cands = _search_candidates(ticker)
    r.put("n_candidates_found", len(cands), "dexscreener search + jupiter search")
    if chain:
        cands = [c for c in cands if c["chain"] == chain]
    if not cands:
        r.put("status", "NONE_FOUND", src_rule)
        r.put("winner", None, src_rule)
        r.put("candidates", [], src_rule)
        return r.done()

    since_ms = None
    if since:
        try:
            since_ms = int(time.mktime(time.strptime(str(since)[:10], "%Y-%m-%d"))) * 1000
        except (ValueError, OverflowError):
            r.warn(f"could not parse since={since!r}; the date rule was NOT applied")

    rows, truncated = [], False
    if len(cands) > max_candidates:
        truncated = True
        cands = cands[:max_candidates]
    for c in cands:
        t = allpairs.token(c["mint"])
        time.sleep(0.25)
        liq = t.get("total_liq_usd") if t.get("ok") else None
        first = t.get("first_pair_ms")
        rejected = None
        if not t.get("ok"):
            rejected = "measurement failed, so it is UNKNOWN and cannot win"
        elif t.get("phantom"):
            rejected = "PHANTOM: a claimed cap with no liquidity behind it"
        elif since_ms and first and first > since_ms:
            rejected = (f"its first pool ({_ms(first)}) postdates {since}, so it "
                        f"did not exist when the ticker was used")
        rows.append({**c, "liq_all_pairs_usd": liq,
                     "pair_count": t.get("pair_count"),
                     "is_floor": bool(t.get("truncated")),
                     "mcap_usd": t.get("mcap_usd"),
                     "price_usd": t.get("price_usd"),
                     "first_pool": _ms(first),
                     "phantom": bool(t.get("phantom")),
                     "shape": allpairs.verdict(t),
                     "rejected_because": rejected,
                     "eligible": rejected is None})
    rows.sort(key=lambda x: -((x["liq_all_pairs_usd"] or 0) if x["eligible"] else -1))
    if truncated:
        r.warn(f"more than {max_candidates} mints wear this ticker; only the "
               f"first {max_candidates} were measured. ⛔ The winner below is "
               f"the best of a PARTIAL set.")

    elig = [x for x in rows if x["eligible"] and (x["liq_all_pairs_usd"] or 0) > 0]
    src = "all-pairs liquidity on every candidate"
    if not elig:
        r.put("status", "NO_ELIGIBLE_CANDIDATE", src)
        r.put("winner", None, src)
    else:
        top = elig[0]
        runner = elig[1]["liq_all_pairs_usd"] if len(elig) > 1 else 0.0
        ratio = (top["liq_all_pairs_usd"] / runner) if runner else None
        r.put("dominance_ratio", round(ratio, 2) if ratio else None, src,
              "winner's liquidity divided by the runner-up's")
        if runner and ratio < RESOLVE_DOMINANCE:
            r.put("status", "AMBIGUOUS", src)
            r.put("winner", None, src)
            r.warn(f"⛔ {len(elig)} live mints wear ${ticker} and the largest "
                   f"leads the next by only {ratio:.1f}x, under the "
                   f"{RESOLVE_DOMINANCE}x bar. Nothing is called real. "
                   f"Key on the contract address.")
        else:
            r.put("status", "RESOLVED", src)
            r.put("winner", top, src)
    r.put("impersonators", [x for x in rows if x is not (elig[0] if elig else None)], src,
          "every OTHER live mint wearing this ticker")
    r.put("n_impersonators", max(0, len(rows) - 1), src)
    r.put("candidates", rows, src)
    return r.done()


def _ms(ms):
    if not ms:
        return None
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ms / 1000))


# --------------------------------------------------------------------------
# mint account state, shared by safety() and paired()
# --------------------------------------------------------------------------
def mint_account(mint):
    return _cached("mint", mint, lambda: _mint_account(mint))


def _mint_account(mint):
    res, err = chainfields._rpc("getAccountInfo", [mint, {"encoding": "jsonParsed"}])
    v = (res or {}).get("value") if res else None
    if not v:
        return {"ok": False, "error": err or "no account"}
    i = v["data"]["parsed"]["info"]
    dec = i.get("decimals") or 0
    out = {"ok": True,
           "program": "Token-2022" if v.get("owner") == TOKEN22 else "SPL",
           "decimals": dec,
           "supply_raw": int(i.get("supply") or 0),
           "supply": float(i.get("supply") or 0) / (10 ** dec) if dec >= 0 else None,
           "mint_authority": i.get("mintAuthority"),
           "freeze_authority": i.get("freezeAuthority"),
           "extensions": [e.get("extension") for e in (i.get("extensions") or [])],
           "transfer_fee_bps": None, "fee_config_authority": None,
           "withdraw_withheld_authority": None, "withheld_raw": None,
           "name": None, "symbol": None}
    for e in (i.get("extensions") or []):
        st = e.get("state") or {}
        if e.get("extension") == "transferFeeConfig":
            out["transfer_fee_bps"] = (st.get("newerTransferFee") or {}).get(
                "transferFeeBasisPoints")
            out["fee_config_authority"] = st.get("transferFeeConfigAuthority")
            out["withdraw_withheld_authority"] = st.get("withdrawWithheldAuthority")
            try:
                out["withheld_raw"] = int(st.get("withheldAmount"))
            except (TypeError, ValueError):
                out["withheld_raw"] = None
        elif e.get("extension") == "tokenMetadata":
            out["name"] = st.get("name")
            out["symbol"] = st.get("symbol")
    return out


# --------------------------------------------------------------------------
# 5. safety(mint) and bundle_check(mint)
# --------------------------------------------------------------------------
def safety(mint):
    """⭐ `check.py` published. One contract in, one verdict out.

    This is the project's one characterised component, and the numbers travel
    with it: **D1 precision 97.3% [86.2, 99.5], recall 50.0% [38.7, 61.3],
    n=37 flagged, out of sample. D2 is IN SAMPLE and unvalidated.**

    ⛔ NOT FLAGGED means "neither of two frauds was detected". D1 misses half. It
    says nothing whatever about whether the price goes up.
    """
    if not _is_mint(mint):
        return Report("safety", mint).fail("that is not a contract address.")
    return _cached("safety", mint, lambda: _safety(mint))


def _safety(mint):
    import check
    r = Report("safety", mint)
    try:
        a = check.analyse(mint)
    except Exception as e:
        return r.fail(f"the safety check could not run ({type(e).__name__})")
    src = "check.analyse() - D1/D2, authorities, concentration, live round trip"
    for f in ("verdict", "symbol", "reasons", "refusals", "warnings",
              "pair_count", "liq_usd_all_pairs", "exit_depth_all_pairs_usd",
              "mcap_usd", "phantom", "pairs_truncated", "quote_assets",
              "d1", "d2", "authorities", "concentration",
              "realizable", "realizable_usd_back", "realizable_cost_pct",
              "max_size_5pct", "round_trip_pct"):
        r.put(f, a.get(f), src)
    r.put("detector_performance",
          {"d1": {"precision": "97.3% [86.2, 99.5]", "recall": "50.0% [38.7, 61.3]",
                  "n_flagged": 37, "out_of_sample": True},
           "d2": {"status": "IN SAMPLE and unvalidated"}},
          "FRAUD_DETECTION.md")
    # ⛔ The things this verdict does NOT cover, in words, every time.
    r.unchecked("fake_volume", "not checked by this verdict. The validated "
                               "volume rule (M1/M2) FAILED: it flags 96.7% of "
                               "sellable tokens against 90.0% of unsellable.")
    r.unchecked("bundles_insiders", "not checked here. Call bundle_check(), and "
                                    "read its warning: it is UNVALIDATED.")
    if a.get("verdict") == "not flagged":
        r.warn("'not flagged' means two specific frauds were not detected, on a "
               "detector that misses half of what it looks for. It is not a "
               "clean bill of health and it is not a reason to buy.")
    return r.done()


def bundle_check(mint, n_buyers=20):
    """⚠️ Who bought first, and were they funded from the same place.

    ⛔⛔ **LEAD WITH THIS: `check.py` is NOT a bundle checker and never was.**
    The relay asked for "the thing the Stonk fee backlash is about" and pointed
    at `check.py`; the honest answer is that our validated component does not do
    this. What we have instead is `devwallet`, and:

    ⛔ **It is UNVALIDATED. On n=4 it did not separate good tokens from bad**
    (`docs/DEV_WALLET.md` §5). It is published here because a first-buyer
    funding graph is genuinely informative to look at, **not** because it has a
    measured hit rate. It has none. Do not gate a decision on it.

    ⚠️ It is also slow and RPC-heavy, so it is never called from `wallet()`.
    """
    if not _is_mint(mint):
        return Report("bundle_check", mint).fail("that is not a contract address.")
    r = Report("bundle_check", mint)
    r.put("status_of_this_check", "UNVALIDATED",
          "docs/DEV_WALLET.md §5",
          "on n=4 it did NOT separate good from bad. No hit rate exists. "
          "check.py, our one characterised component, does not check bundles.")
    try:
        import devwallet
    except Exception as e:
        return r.fail(f"devwallet unavailable ({type(e).__name__})")
    try:
        ov = devwallet.buyer_funding_overlap(mint, n=n_buyers)
        r.put("first_buyer_funding_overlap", ov,
              "devwallet.buyer_funding_overlap() - Helius transaction history",
              "wallets among the first buyers that share a funding source")
    except Exception as e:
        r.unchecked("first_buyer_funding_overlap",
                    f"the funding walk failed ({type(e).__name__}). Unknown, "
                    f"not 'clean'.")
    try:
        dep = devwallet.deployer(mint)
        r.put("deployer", dep, "devwallet.deployer()")
    except Exception as e:
        r.unchecked("deployer", f"could not be read ({type(e).__name__})")
    r.warn("A shared funding source is not proof of anything. It is a question "
           "to ask, and this system has never shown it answers one.")
    return r.done()



# --------------------------------------------------------------------------
# concentration(mint) - sybil-adjusted, and the recurrence finding
# --------------------------------------------------------------------------
def concentration(mint, deep=True, max_walk=10):
    """⭐⭐ Who actually holds this, with pool vaults out and sybils collapsed.

    Frank: *"nobody should ever be able to buy more than 1%-2% of a coin that
    early on... Not sure how we could police that."* A per-wallet cap stops only
    the lazy version, so this reports **effective** concentration: wallets that
    share a funding source are collapsed into one holder.

    ⛔⛔ **And running it produced a better answer than the one it was built for.**
    On real tokens the top holders are not fresh sybil wallets at all; they carry
    3,000+ signatures each. Two pump.fun graduations picked at random share
    **three** of their top-10 holders. So the headline field is `recurrence`:
    how many OTHER launches each top holder also top-holds.

    ⭐ Base rate, measured over 60 consecutive graduations: **9.1% [6.8, 12.0]**
    of 474 distinct top-10 wallets appear in more than one, and the **median
    token has 20% of its top 10 recurring**. A token at 80% is a different
    animal, and that is a fact the reader can check.

    ⛔ It predicts nothing and must never be turned into a score.
    """
    if not _is_mint(mint):
        return Report("concentration", mint).fail("that is not a contract address.")
    return _cached("concentration", f"{mint}:{deep}:{max_walk}",
                   lambda: _concentration(mint, deep, max_walk))


def _concentration(mint, deep, max_walk):
    import concentration as CN
    r = Report("concentration", mint)
    liq = liquidity(mint)
    first_pool = liq["data"].get("first_pool_ms") if liq.get("ok") else None
    try:
        a = CN.analyse(mint, first_pool_ms=first_pool, deep=deep, max_walk=max_walk)
    except Exception as e:
        return r.fail(f"concentration could not be measured ({type(e).__name__})")
    if a.get("error"):
        return r.fail(a["error"])

    src = "getTokenLargestAccounts + getMultipleAccounts, pool vaults excluded"
    for f in ("supply", "n_wallets_seen", "n_pool_vaults_excluded",
              "pool_vault_pct", "raw_top1_pct", "raw_top10_pct", "raw_top20_pct",
              "wallets_over_1pct", "wallets_over_2pct", "wallets"):
        r.put(f, a.get(f), src)
    r.put("is_partial", a.get("is_partial"), src, a.get("partial_why"))

    fsrc = "keyless funding walk (getSignaturesForAddress + getTransaction)"
    for f in ("n_fresh_wallets", "n_established_wallets", "fresh_rule",
              "clusters", "n_clusters", "effective_top1_pct",
              "effective_top10_pct", "sybil_uplift_pct", "walked"):
        if f in a:
            r.put(f, a.get(f), fsrc)

    rsrc = ("append-only holder registry data/holders/*.jsonl, seeded from 60 "
            "consecutive graduations measured 2026-09-23")
    for f in ("recurrence_registry_mints", "n_top10_seen_in_other_launches",
              "top10_recurring_share_pct", "recurring_holders"):
        r.put(f, a.get(f), rsrc)
    r.put("recurrence_base_rate",
          {"wallets_in_more_than_one_launch": "9.1% [6.8, 12.0] of 474",
           "median_token_top10_recurring_pct": 20.0, "n_mints": 60,
           "measured": "2026-09-23"}, "analysis/holder_recurrence/measure.py")
    r.put("recurrence_note", a.get("recurrence_note"), rsrc)

    for n in (a.get("not_checked") or []):
        r.unchecked(n["field"], n["why"])
    for w in (a.get("warnings") or []):
        r.warn(w)
    r.warn("⛔ This describes the present and predicts nothing. Do not rank "
           "tokens by it and do not turn it into a score.")
    return r.done()


# --------------------------------------------------------------------------
# 6. paired(mint)
# --------------------------------------------------------------------------
def paired(mint):
    """⭐ What is this token denominated in, and what does the tax actually do.

    The verified mechanic (`docs/ASSET_PAIRED_TOKENS.md`): a "pair" is the **AMM
    pool's quote asset** being a tokenized or bridged version of the named asset.
    ⛔ **There is no oracle anywhere.** Raydium CPMM/CLMM and Meteora DLMM read
    no price feed, so the link is (a) denomination, making the USD price
    `pool ratio x quote asset USD`, and (b) rewards paid in that same asset.

    ⛔⛔ **And the reward stream is REDISTRIBUTION, not yield.** It is funded by
    other traders' transfer tax. The same tax is your entry cost and your exit
    cost. A token taxing 300 bps charges you 3% in and 3% out.

    ⚠️ What this CANNOT tell you: whether a given holder has actually been paid.
    The distributor pays thousands of wallets in batches, and confirming that a
    specific wallet received anything needs that wallet's own history. The field
    says so rather than implying an APR.
    """
    if not _is_mint(mint):
        return Report("paired", mint).fail("that is not a contract address.")
    return _cached("paired", mint, lambda: _paired(mint))


def _paired(mint):
    r = Report("paired", mint)
    liq = liquidity(mint)
    if not liq.get("ok"):
        return r.fail(liq.get("error"))
    qa = liq["data"].get("quote_assets") or {}
    src = "liquidity(mint) - the quote asset of every pool, by liquidity"
    r.put("quote_assets", qa, src,
          "what the pools are DENOMINATED in. No oracle is involved anywhere.")
    others = {k: v for k, v in qa.items() if k not in ("SOL", "WSOL", "USDC", "USDT")}
    r.put("paired_to", list(others.keys())[:5], "derived",
          "quote assets that are not SOL or a dollar stablecoin")
    r.put("is_asset_paired", bool(others), "derived")

    mi = mint_account(mint)
    if not mi.get("ok"):
        r.unchecked("transfer_fee_bps",
                    f"the mint account could not be read ({mi.get('error')}). "
                    f"⛔ Unknown, not 'no tax'.")
        return r.done()
    msrc = "getAccountInfo on the mint (Token-2022 extensions)"
    r.put("token_program", mi["program"], msrc)
    r.put("transfer_fee_bps", mi.get("transfer_fee_bps"), msrc,
          "⛔ charged on EVERY transfer, so it is your entry cost AND your exit cost")
    bps = mi.get("transfer_fee_bps")
    if bps:
        r.put("tax_pct", bps / 100.0, "derived")
        r.put("round_trip_tax_pct", 2 * bps / 100.0, "derived",
              "in plus out, before any slippage or venue fee")
    fca = mi.get("fee_config_authority")
    r.put("fee_can_be_changed", bool(fca), msrc,
          "⛔ a LIVE transferFeeConfigAuthority means the tax can be raised "
          "AFTER you buy" if fca else
          "null authority: the rate is fixed and cannot be changed")
    r.put("fee_config_authority", fca, msrc)
    r.put("withdraw_withheld_authority", mi.get("withdraw_withheld_authority"), msrc,
          "the account that can harvest the withheld tax out of the mint")
    wh, sup, dec = mi.get("withheld_raw"), mi.get("supply_raw"), mi.get("decimals")
    if wh is not None and sup:
        r.put("withheld_tokens", wh / (10 ** dec) if dec else wh, msrc,
              "tax collected in the mint and not yet harvested")
        r.put("withheld_pct_of_supply", round(100.0 * wh / sup, 4), "derived")
        px = liq["data"].get("price_usd")
        r.put("withheld_usd", round((wh / (10 ** dec)) * px, 2)
              if (px and dec is not None) else None, "derived",
              "⚠️ valued at the reported price, which overstates")
    else:
        r.unchecked("withheld_tokens", "no transfer-fee extension on this mint, "
                                       "or the withheld amount could not be read")
    r.unchecked("holder_has_been_paid",
                "⛔ NOT CHECKED and not checkable from the mint. The distributor "
                "pays thousands of wallets in batches; confirming a specific "
                "holder was paid needs that wallet's own transaction history. "
                "No APR is published here because none was measured.")
    if bps:
        r.warn("⛔ The reward stream is funded by other traders' transfer tax. "
               "It is REDISTRIBUTION, not yield, and the same tax is charged on "
               "your way in and on your way out.")
    return r.done()


# --------------------------------------------------------------------------
# 7. wallet(pubkey)  - the headline feature
# --------------------------------------------------------------------------
def wallet(pubkey, price_all=False, max_positions=WALLET_MAX_POSITIONS):
    """⭐⭐ Read a wallet and say what is actually in it. READ-ONLY.

    This is the script run by hand on Frank's wallet tonight, productised. It
    takes a **public key**. It cannot sign, move, approve or custody anything,
    and no code path that could may ever be added.

    For every position it answers the four questions no portfolio tracker asks:

      - **is there a market at all** (all-pairs liquidity, never one pool)
      - **is the cap backed** (the phantom rule)
      - ⭐ **what do YOU get for selling what YOU hold** - the exact raw
        quantity, not a $100 probe
      - **what is it paired to, and is it taxed**

    ⚠️ Cost control, stated rather than hidden: every position costs one
    all-pairs call, and every priced position costs a Jupiter quote on top, and
    Jupiter is capped at 55/min process-wide. Positions under $1 of reported
    value are listed but NOT quoted unless `price_all=True`, and each one says
    so in `not_checked` rather than showing a blank.
    """
    if not _is_mint(pubkey):
        return Report("wallet", pubkey).fail(
            "that is not a Solana address. This endpoint takes a PUBLIC KEY and "
            "reads public state; it never signs anything.")
    key = f"{pubkey}:{price_all}"
    return _cached("wallet", key, lambda: _wallet(pubkey, price_all, max_positions))


def _token_accounts(pubkey):
    rows, errs = [], []
    for prog in (SPL, TOKEN22):
        res, err = chainfields._rpc(
            "getTokenAccountsByOwner",
            [pubkey, {"programId": prog}, {"encoding": "jsonParsed"}])
        if res is None:
            errs.append(f"{'SPL' if prog == SPL else 'Token-2022'}: {err}")
            continue
        for a in (res.get("value") or []):
            info = (((a.get("account") or {}).get("data") or {})
                    .get("parsed") or {}).get("info") or {}
            amt = info.get("tokenAmount") or {}
            raw = int(amt.get("amount") or 0)
            if raw <= 0:
                continue
            rows.append({"mint": info.get("mint"), "raw": raw,
                         "decimals": amt.get("decimals"),
                         "ui": amt.get("uiAmount"),
                         "program": "SPL" if prog == SPL else "Token-2022",
                         "token_account": a.get("pubkey")})
    return rows, errs


def _wallet(pubkey, price_all, max_positions):
    r = Report("wallet", pubkey)
    r.put("read_only", True, "intel.wallet()",
          "a public key was read. Nothing was signed, moved or approved.")

    accounts, errs = _token_accounts(pubkey)
    if errs and not accounts:
        return r.fail("could not read token accounts: " + "; ".join(errs))
    for e in errs:
        r.warn(f"⛔ one token program could not be read ({e}), so this wallet "
               f"view is INCOMPLETE. Positions may be missing.")

    bal, berr = chainfields._rpc("getBalance", [pubkey])
    if bal is not None:
        r.put("sol_balance", (bal.get("value") or 0) / 1e9, "getBalance")
    else:
        r.unchecked("sol_balance", f"getBalance failed ({berr})")

    r.put("n_token_accounts", len(accounts), "getTokenAccountsByOwner (SPL + Token-2022)")
    if len(accounts) > max_positions:
        r.warn(f"⛔ this wallet holds {len(accounts)} positions and only "
               f"{max_positions} were measured. The rest are listed unmeasured "
               f"rather than dropped - standing rule 15, a truncated sample must "
               f"record WHAT it missed.")

    positions, skipped = [], []
    for i, a in enumerate(accounts):
        if i >= max_positions:
            skipped.append(a["mint"])
            continue
        positions.append(_position(a, price_all))

    priced = [p for p in positions if isinstance(p.get("you_get_usd"), (int, float))]
    total = round(sum(p["you_get_usd"] for p in priced), 2) if priced else None
    r.put("positions", positions, "per-position, see each row's own provenance")
    r.put("unmeasured_mints", skipped, "truncation record")
    r.put("n_positions_measured", len(positions), "derived")
    r.put("n_positions_priced", len(priced), "derived")
    r.put("realizable_total_usd", total, "sum of live Jupiter sell quotes",
          "⭐ what the wallet is worth IF SOLD NOW, position by position, at the "
          "exact size held. ⚠️ Positions that could not be quoted are NOT in "
          "this total and are listed in not_checked.")
    if len(priced) < len(positions):
        r.unchecked("realizable_total_usd_complete",
                    f"{len(positions) - len(priced)} of {len(positions)} "
                    f"positions have no sell quote, so the total above is a "
                    f"FLOOR over the quoted ones only, never the wallet's value.")

    flags = {"no_market": [p["mint"] for p in positions if p.get("shape") in
                           ("NO_LIQUIDITY", "PHANTOM") or p.get("pair_count") == 0],
             "phantom": [p["mint"] for p in positions if p.get("phantom") == "PHANTOM"],
             "cannot_sell": [p["mint"] for p in positions
                             if p.get("sell_verdict") == "NO_SELL_ROUTE"],
             "taxed": [p["mint"] for p in positions if p.get("transfer_fee_bps")],
             "tax_can_be_raised": [p["mint"] for p in positions
                                   if p.get("fee_can_be_changed")],
             "ticker_collision": [p["mint"] for p in positions
                                  if p.get("symbol_flags")]}
    r.put("flags", flags, "derived from the per-position checks",
          "the four questions a portfolio tracker never asks")
    if flags["cannot_sell"]:
        r.warn(f"⛔ {len(flags['cannot_sell'])} position(s) have NO SELL ROUTE "
               f"right now. A green number in a portfolio app does not mean a "
               f"market exists.")
    if flags["phantom"]:
        r.warn(f"⛔ {len(flags['phantom'])} position(s) sit on a market cap with "
               f"effectively no liquidity behind it.")
    return r.done()


def _position(a, price_all):
    """One holding, answered. Every unknown says why it is unknown."""
    mint = a["mint"]
    p = {"mint": mint, "raw": a["raw"], "ui_amount": a["ui"],
         "decimals": a["decimals"], "token_program": a["program"],
         "symbol": None, "name": None,
         "pair_count": None, "liq_all_pairs_usd": None, "liq_is_floor": None,
         "shape": None, "mcap_usd": None, "price_usd": None,
         "phantom": None, "paired_to": None, "quote_assets": None,
         "transfer_fee_bps": None, "fee_can_be_changed": None,
         "you_get_usd": None, "sell_verdict": None, "price_impact_pct": None,
         "reported_value_usd": None, "symbol_flags": None,
         "not_checked": [], "provenance": []}

    def prov(field, source):
        p["provenance"].append({"field": field, "source": source})

    def nope(field, why):
        p["not_checked"].append({"field": field, "why": why})

    t = allpairs.token(mint)
    if t.get("ok"):
        p["pair_count"] = t["pair_count"]
        p["liq_all_pairs_usd"] = t["total_liq_usd"]
        p["liq_is_floor"] = bool(t.get("truncated"))
        p["mcap_usd"] = t.get("mcap_usd")
        p["price_usd"] = t.get("price_usd")
        p["shape"] = allpairs.verdict(t)
        qa = {k: round(v["liq_usd"], 2)
              for k, v in list((t.get("quote_assets") or {}).items())[:6]}
        p["quote_assets"] = qa
        p["paired_to"] = [k for k in qa if k not in ("SOL", "WSOL", "USDC", "USDT")][:4]
        p["symbol"] = t.get("symbol_display")
        p["name"] = t.get("name_display")
        prov("symbol", "dexscreener baseToken. ⚠️ DISPLAY ONLY - the key is the "
                       "address, and this string is attacker-controlled.")
        prov("liq_all_pairs_usd", "dexscreener all pairs, summed")
        if t.get("phantom"):
            p["phantom"] = "PHANTOM"
        elif t.get("mcap_usd") and t["total_liq_usd"] is not None:
            p["phantom"] = ("UNEVALUABLE" if (t.get("truncated")
                                              and t["total_liq_usd"] < PHANTOM_LIQ)
                            else "BACKED")
        if p["price_usd"] is not None and a["ui"] is not None:
            p["reported_value_usd"] = round(p["price_usd"] * a["ui"], 2)
            prov("reported_value_usd", "reported price x holding. ⚠️ NOT an exit price.")
    else:
        nope("liq_all_pairs_usd",
             "the price index did not answer. ⛔ This is NOT evidence the token "
             "is dead.")

    mi = mint_account(mint)
    if mi.get("ok"):
        # ⛔ Do NOT overwrite the display symbol here. Only Token-2022 mints
        # carry metadata in the mint account, so assigning it unconditionally
        # blanked the name of every plain SPL token - including USDC and SOL.
        # The on-chain string is kept separately and compared below.
        p["transfer_fee_bps"] = mi.get("transfer_fee_bps")
        p["fee_can_be_changed"] = bool(mi.get("fee_config_authority"))
        p["mint_authority"] = mi.get("mint_authority")
        p["freeze_authority"] = mi.get("freeze_authority")
        prov("transfer_fee_bps", "getAccountInfo, Token-2022 extensions")
        # ⭐ Two independent sources for the same string, so a disagreement is
        # itself a finding rather than an invisible overwrite.
        onchain_sym = mi.get("symbol")
        if onchain_sym:
            p["symbol_onchain"] = onchain_sym
            if p["symbol"] and onchain_sym != p["symbol"]:
                p["symbol_disagrees"] = True
                nope("symbol", f"the index says {p['symbol']!r} and the mint's own "
                               f"metadata says {onchain_sym!r}. ⛔ They disagree; "
                               f"trust neither and key on the address.")
        bad = (_symbol_flags(p.get("symbol")) or []) + (_symbol_flags(onchain_sym) or [])
        if bad:
            p["symbol_flags"] = sorted(set(bad))
    else:
        nope("transfer_fee_bps", f"mint account unreadable ({mi.get('error')})")
        nope("freeze_authority", "mint account unreadable. ⛔ Unknown, not revoked.")

    # ⭐ The number that matters: sell THIS position, not a $100 probe.
    worth_quoting = price_all or (p["reported_value_usd"] is None
                                  or p["reported_value_usd"] >= DUST_USD)
    if not worth_quoting:
        nope("you_get_usd",
             f"reported value under ${DUST_USD:.2f}; not quoted to stay inside "
             f"the Jupiter rate cap. Pass price_all=true to quote it.")
        return p
    q = chainfields.sell_quote(mint, a["raw"])
    p["sell_verdict"] = q.get("verdict")
    p["price_impact_pct"] = q.get("price_impact_pct")
    p["sell_venues"] = q.get("venues")
    prov("you_get_usd", "live jupiter sell quote for the EXACT position held. "
                        "NOTHING EXECUTED.")
    if q.get("verdict") == "QUOTED":
        p["you_get_usd"] = q.get("usd_out")
        rv = p["reported_value_usd"]
        if rv and p["you_get_usd"] is not None and rv > 0:
            p["reported_vs_realizable"] = round(rv / max(p["you_get_usd"], 1e-9), 2)
    elif q.get("verdict") == "NO_SELL_ROUTE":
        nope("you_get_usd", "⛔ NO SELL ROUTE. There is no market for this "
                            "position at any size right now. That is an answer.")
    else:
        nope("you_get_usd", f"the quote API did not answer ({q.get('verdict')}). "
                            f"⛔ Unknown, NOT zero and NOT a loss.")
    return p


BIDI = {0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x2066, 0x2067, 0x2068, 0x2069,
        0x200E, 0x200F, 0x200B, 0x200C, 0x200D, 0xFEFF}
CYRILLIC = set(range(0x0400, 0x0500))


def _symbol_flags(sym):
    """⛔ A ticker can render as a name it does not contain. docs/SYMBOL_ATTACKS.md.

    112 contracts in our corpus carry a text-direction override in the symbol;
    one renders as "USDC" and claimed the highest liquidity of 2026-09-18 with
    zero sells. 48 more mix Cyrillic into Latin. `html.escape()` does NOT
    neutralise either.
    """
    flags = []
    codes = [ord(c) for c in (sym or "")]
    if any(c in BIDI for c in codes):
        flags.append("bidi_control: this symbol can render as a DIFFERENT name")
    if any(c in CYRILLIC for c in codes) and any(c < 0x0250 for c in codes):
        flags.append("mixed_script: Cyrillic characters inside a Latin symbol")
    return flags or None


# --------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        print("usage: python intel.py <endpoint> <arg> [arg]")
        print("  endpoints: liquidity resolve phantom exit_depth safety "
              "concentration bundle_check paired wallet")
        raise SystemExit(0)
    fn = {"liquidity": liquidity, "resolve": resolve, "phantom": phantom,
          "exit_depth": exit_depth, "safety": safety, "concentration": concentration,
          "bundle_check": bundle_check, "paired": paired, "wallet": wallet}[args[0]]
    rest = []
    for x in args[1:]:
        try:
            rest.append(int(x))
        except ValueError:
            rest.append(x)
    print(json.dumps(fn(*rest), indent=1, default=str))
