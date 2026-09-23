"""Tests for the on-chain pool ladder and its wiring into intel.liquidity.

⛔ Two of these exist because the NEGATIVE CONTROL caught real bugs before the
sample ran, and a test is the only thing that stops them coming back:

  1. `_pools_from` counted ANY program-owned account as a pool, so the phantom
     EMBER's eight pump.fun FEE accounts graded as pools. The pre-commit says a
     pool is a KNOWN AMM program. That cost nothing because a control caught it;
     on the sample it would have graded almost every mint as having a pool.
  2. Fetching vaults for those fee accounts took 12 SECONDS PER CALL, because
     each one owns token accounts across thousands of mints. 120 mints would
     have been hours.

Run: python test_pooldiscovery.py
"""
import ast
import io
import os
import sys

import pooldiscovery as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
FAILED = []
PASSED = 0


def check(label, cond, detail=""):
    global PASSED
    if cond:
        PASSED += 1
        print("  ok   %s" % label)
    else:
        FAILED.append(label)
        print("  FAIL %s  %s" % (label, detail))


print("\n--- base58, because rung 2 decodes owners by hand ---")
# The system program is 32 zero bytes and encodes to 32 '1' characters.
check("32 zero bytes encode to the system program",
      pd.b58encode(b"\x00" * 32) == pd.SYSTEM_PROGRAM,
      pd.b58encode(b"\x00" * 32))
check("a known 32-byte key round-trips through the encoder",
      pd.b58encode(bytes([
          6, 221, 246, 225, 215, 101, 161, 147, 217, 203, 225, 70, 206, 235,
          121, 172, 28, 180, 133, 237, 95, 91, 55, 145, 58, 140, 245, 133,
          126, 255, 0, 169])) == pd.TOKEN_PROGRAM,
      pd.b58encode(bytes([6, 221, 246, 225, 215, 101, 161, 147, 217, 203, 225,
                          70, 206, 235, 121, 172, 28, 180, 133, 237, 95, 91,
                          55, 145, 58, 140, 245, 133, 126, 255, 0, 169])))

print("\n--- the maps, and the bug a control caught ---")
check("⛔ AMM_OWNERS and NOT_POOLS are disjoint",
      not (set(pd.AMM_OWNERS) & set(pd.NOT_POOLS)),
      str(set(pd.AMM_OWNERS) & set(pd.NOT_POOLS)))
check("⛔ the pump.fun FEE program is listed as NOT a pool",
      pd.NOT_POOLS.get("pfeeUxB6jkeY1Hxd7CsFCAjcbHA9rWtchMGdZ6VojVZ")
      == "pumpfun_fee_program")
check("the fee program is NOT in the AMM map",
      "pfeeUxB6jkeY1Hxd7CsFCAjcbHA9rWtchMGdZ6VojVZ" not in pd.AMM_OWNERS)
check("the Raydium v4 shared authority is known and skipped",
      "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1" in pd.SHARED_AUTHORITIES)
src = io.open(os.path.join(ROOT, "pooldiscovery.py"), encoding="utf-8").read()
check("⛔ only a KNOWN AMM program becomes a pool, in the source",
      "if prog not in AMM_OWNERS:" in src)
check("⛔ an excluded owner is RECORDED, not dropped (rule 15)",
      "excluded_owners" in src and "unknown_programs" in src)

print("\n--- the verdict bands, exactly as pre-committed ---")


def v(qmax, pools=1, unvalued=0):
    return pd._verdict({"pools": [{}] * pools, "quote_usd_max": qmax,
                        "unvalued_vaults": unvalued})


check("no pool -> NO_POOL_FOUND", v(0, pools=0) == "NO_POOL_FOUND", v(0, 0))
check("$100 -> POOL_QUOTE_100", v(100.0) == "POOL_QUOTE_100", v(100.0))
check("$99.99 -> POOL_QUOTE_10", v(99.99) == "POOL_QUOTE_10", v(99.99))
check("$10 -> POOL_QUOTE_10", v(10.0) == "POOL_QUOTE_10", v(10.0))
check("$9.99 -> POOL_QUOTE_DUST", v(9.99) == "POOL_QUOTE_DUST", v(9.99))
check("⛔ a pool we could not VALUE is its own bucket, never DUST",
      v(0.0, unvalued=2) == "POOL_QUOTE_UNVALUED", v(0.0, unvalued=2))
check("⛔ and a valued zero is DUST, not UNVALUED",
      v(0.0, unvalued=0) == "POOL_QUOTE_DUST", v(0.0))

print("\n--- quote_value: what counts as an exit and what does not ---")
MINT = "So11111111111111111111111111111111111111112"  # stand-in base mint
SOL = "So11111111111111111111111111111111111111112"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
base = "9n4nbM75f5Ui33ZbPYXn59EwSgE8CGsHtAeTH5YFeJ9A"

usd, valued, unvalued = pd.quote_value(
    [{"mint": base, "amount": 10 ** 18, "decimals": 6, "ui": 1e12},
     {"mint": SOL, "amount": 2 * 10 ** 9, "decimals": 9, "ui": 2.0}],
    base, 100.0)
check("⛔ the pool's own BASE token is not quote side", usd == 200.0, usd)
check("the SOL vault is valued at the run's one price",
      valued and valued[0]["asset"] == "SOL" and valued[0]["usd"] == 200.0,
      str(valued))

usd, valued, unvalued = pd.quote_value(
    [{"mint": "CzLTZppPdZtTjyq3WGpHLstoc3GLhu7zH5Zg6xUa6Gv5", "amount": 5,
      "decimals": 0, "ui": 5.0}], base, 100.0)
check("⛔ an asset we do not price is COUNTED with usd None, never 0 (rule 5)",
      usd == 0.0 and len(unvalued) == 1 and unvalued[0]["usd"] is None,
      str(unvalued))

usd, valued, unvalued = pd.quote_value(
    [{"mint": SOL, "amount": 10 ** 9, "decimals": 9, "ui": 1.0}], base, None)
check("⛔ no SOL price makes the vault UNVALUED, not zero dollars",
      usd == 0.0 and unvalued and unvalued[0]["why"] == "no_sol_price",
      str(unvalued))

usd, valued, unvalued = pd.quote_value(
    [{"mint": USDC, "amount": 7 * 10 ** 6, "decimals": 6, "ui": 7.0}],
    base, None)
check("a USDC vault does not need a SOL price", usd == 7.0, usd)

print("\n--- the floor, which is the whole point ---")
check("⛔ the module says in words that absence is a floor",
      "absence_is_a_floor" in src and "NOT that" in src)
check("⛔ a 429 becomes an ERROR, never an empty result (rule 16)",
      "http_429_exhausted" in src and 'return None, "http_%d" % e.code' in src)
check("a failed getMultipleAccounts chunk is recorded, not treated as absent",
      'errs.append(err or "empty")' in src)

print("\n--- nothing here can sign, send or hold a key ---")
BANNED = ("sign", "send_transaction", "keypair", "secret_key", "private_key",
          "approve", "delegate_authority", "set_authority", "place_order",
          "sendTransaction", "signTransaction")
tree = ast.parse(src)
names = set()
for node in ast.walk(tree):
    if isinstance(node, ast.Name):
        names.add(node.id.lower())
    elif isinstance(node, ast.Attribute):
        names.add(node.attr.lower())
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        names.add(node.name.lower())
bad = sorted(n for n in names if any(b.lower() in n for b in BANNED))
check("⛔ no signing / sending / key name anywhere in the module", not bad,
      str(bad))
check("⛔ and no private key is read from anywhere",
      "PRIVATE" not in src.upper().replace("PRIVATE_KEY_NEVER", ""))

print("\n--- the pre-commit exists and the code matches it ---")
pc = os.path.join(ROOT, "PRECOMMIT_pool_discovery.md")
check("PRECOMMIT_pool_discovery.md exists", os.path.exists(pc))
if os.path.exists(pc):
    doc = io.open(pc, encoding="utf-8").read()
    check("the pre-commit states N_SAMPLE = 120", "N_SAMPLE = 120" in doc)
    check("the pre-commit fixes the top-100 rung-2 bound",
          "top 100" in doc.lower())
    check("⛔ the pre-commit states the asymmetry",
          "asymmetry" in doc.lower() and "FLOOR" in doc)
    check("the pre-commit registers a falsifiable prediction",
          "15% and 45%" in doc and "Under 5%" in doc)
    check("⛔ the pre-commit names the tautology in my first attempt",
          "tautolog" in doc.lower())
    check("every valued asset in the code is named in the pre-commit",
          all(n in doc for n, _ in pd.VALUED.values()),
          str([n for n, _ in pd.VALUED.values() if n not in doc]))

print("\n--- wired into intel.liquidity, which is the permanent part ---")
isrc = io.open(os.path.join(ROOT, "intel.py"), encoding="utf-8").read()
check("⛔ intel has an on-chain fallback function",
      "def _liquidity_from_chain(" in isrc)
check("⛔ it fires when the indexer LOOKUP FAILED",
      'if (not t.get("ok")) or t.get("pair_count") == 0:' in isrc)
check("⛔ and when the indexer answered NO PAIRS (pair_count 0)",
      't.get("pair_count") == 0' in isrc)
check("the fallback is reached BEFORE the indexer fields are read",
      isrc.index("_liquidity_from_chain(r, mint, t)")
      < isrc.index('src = "dexscreener /latest/dex/tokens'))
check("⛔ indexer-only fields come back UNKNOWN, never 0",
      'r.unchecked(k, "the indexer did not answer' in isrc)
check("⛔ the response says WHICH SOURCE answered",
      '"source_that_answered"' in isrc)
check("⛔ the response carries absence_is_a_floor",
      '"absence_is_a_floor", True' in isrc)
check("⛔ it says discovered reserves are not an exit price",
      "never an exit price" in isrc)
itree = ast.parse(isrc)
fns = {n.name for n in ast.walk(itree)
       if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
check("_liquidity_from_chain is a real function, not only a comment",
      "_liquidity_from_chain" in fns)

print("\n%d passed, %d failed" % (PASSED, len(FAILED)))
if FAILED:
    for f in FAILED:
        print("  FAILED:", f)
sys.exit(1 if FAILED else 0)
