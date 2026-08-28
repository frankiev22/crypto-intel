"""
pump.fun launch watcher - pre-bonding visibility.

Every launch is a transaction against one program. Reading that program's
signatures shows the mint before it reaches any aggregator.

Public RPC works for this but is rate limited; Helius websockets make it
genuinely instant. Structure is the same either way.
"""
import time
import config, sources as S

PROGRAM = S.PUMP_FUN_PROGRAM

def _rpc(method, params):
    return S._post(config.helius_rpc(), {"jsonrpc":"2.0","id":1,"method":method,"params":params})

def recent_launches(limit=200, with_stats=False):
    """NOTE: most pump.fun transactions FAIL - failed buys, slippage, lost races.
    Observed roughly 90% error rate. Use a high limit or you will get an empty
    list and think the feed is broken. The failure ratio is itself a congestion
    signal: a spike means everyone is fighting over the same launches."""
    r = _rpc("getSignaturesForAddress", [PROGRAM, {"limit": limit}]).get("result", [])
    ok = [{"sig": x["signature"], "slot": x.get("slot"),
           "time": x.get("blockTime"), "err": None} for x in r if not x.get("err")]
    if with_stats:
        n = len(r)
        return ok, {"total": n, "failed": n - len(ok),
                    "fail_rate": (n - len(ok)) / n if n else 0}
    return ok

def poll(interval=10, on_new=None):
    print(f"  watching pump.fun program via "
          f"{'Helius' if config.have('helius') else 'public RPC (rate limited)'}")
    seen = set()
    while True:
        try:
            for L in recent_launches():
                if L["sig"] in seen: continue
                seen.add(L["sig"])
                age = time.time() - (L["time"] or 0)
                if age < interval * 3:
                    print(f"  new tx {L['sig'][:20]}... slot {L['slot']} ({age:.0f}s ago)")
                    if on_new: on_new(L)
        except Exception as e:
            print(f"  poll error: {e}")
        time.sleep(interval)
