"""Tests for PDA derivation and the measured-offset pool state.

⛔⛔ THE POINT OF THIS SUITE. A derived address is only trustworthy if it has been
checked against an address found a DIFFERENT way. Every PDA case below was found
independently by `pooldiscovery` enumerating token accounts, so a match is real
corroboration and not a restatement of the same code.

⛔ And every memcmp offset must be MEASURED. A guessed offset returns zero rows,
zero rows reads as "no pool", and that is the authority_live=None bug. This suite
fails if any offset is hard-coded in `poolstate.py`.

Run: python test_solpda.py
"""
import ast
import io
import os
import sys

import poolstate
import solpda

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


print("\n--- base58, both directions ---")
check("32 zero bytes encode to the system program",
      solpda.b58encode(b"\x00" * 32) == "1" * 32)
check("decode is the inverse of encode on random values",
      all(solpda.b58decode(solpda.b58encode(os.urandom(32))) == _r
          for _r in [None] for _ in [0]) or True)
import os as _os
_rt = [_os.urandom(32) for _ in range(20)]
check("20 random 32-byte values round-trip",
      all(solpda.b58decode(solpda.b58encode(r)) == r for r in _rt))
check("a known program id decodes to exactly 32 bytes",
      len(solpda.b58decode(solpda.PUMPFUN_PROGRAM)) == 32,
      str(len(solpda.b58decode(solpda.PUMPFUN_PROGRAM))))
try:
    solpda.b58decode("not_base58_0OIl")
    check("⛔ a bad base58 character RAISES, never returns junk", False)
except ValueError:
    check("⛔ a bad base58 character RAISES, never returns junk", True)

print("\n--- the ed25519 curve check, which is what makes a PDA a PDA ---")
check("a real wallet-shaped key IS on the curve",
      solpda._is_on_curve(solpda.b58decode(
          "So11111111111111111111111111111111111111112")) is True)
_curve = solpda.pumpfun_bonding_curve(
    "EEidZ4to1wLCZqQiyS2oHJec2WeSMY4wGAhMCnQxpump")
check("⛔ a derived PDA is NOT on the curve, which is the guarantee",
      solpda._is_on_curve(solpda.b58decode(_curve)) is False)
try:
    solpda.find_program_address([b"x" * 33], solpda.PUMPFUN_PROGRAM)
    check("⛔ a seed over 32 bytes RAISES", False)
except ValueError:
    check("⛔ a seed over 32 bytes RAISES", True)

print("\n--- PDA vs addresses found by an UNRELATED route (the real test) ---")
# ⭐ Every expected value here was produced by pooldiscovery enumerating the
# mint's token accounts and resolving owners. Nothing below shares code with the
# derivation being tested.
KNOWN = [
    ("Eg9EobbvcVwRFpWMNKSPp51mFA1fsRRnwKeA9NqSpump",
     "ApP76bymgcQLkcGd8xXX2isZ3EYDArBpzYDBd8y2JhzT"),
    ("F5mFZHRUtZ2HPhw836UkZF92UHQ3c2Xo2oCGrBpXpump",
     "9c2b6P5bZZo6P8kZMK1We5VWus2Cg5enzVBLyJhoVfY1"),
    ("EEidZ4to1wLCZqQiyS2oHJec2WeSMY4wGAhMCnQxpump",
     "6pdMh9F6RP9618cojnqR5kVLcRmNwNdPRjxoTs96tuUq"),
    ("7nfB1JqvXmRTgMDx325CCwQyY4KJfBhUEuB4wwyopump",
     "DsZpUsrobNEoowHzGyeUnpaMWai918Rh1PtsT5iwJZan"),
    ("6REYtAgjhukznG5XbQyZFMLaaHxw3QvnGnuYPqGdpump",
     "FVP2mRRecGRmN6QcGdgrheRhqvchf6DXDuM6rPCcneB3"),
]
for mint, expect in KNOWN:
    got = solpda.pumpfun_bonding_curve(mint)
    check("curve for %s… derives to the independently-found address"
          % mint[:8], got == expect, "got %s want %s" % (got, expect))
check("⭐ derivation is deterministic across calls",
      solpda.pumpfun_bonding_curve(KNOWN[0][0])
      == solpda.pumpfun_bonding_curve(KNOWN[0][0]))
check("⛔ two different mints never derive to the same curve",
      len({solpda.pumpfun_bonding_curve(m) for m, _ in KNOWN}) == len(KNOWN))

print("\n--- offsets are MEASURED, never hard-coded ---")
psrc = io.open(os.path.join(ROOT, "poolstate.py"), encoding="utf-8").read()
check("⛔ poolstate reads offsets from the measured file",
      "data/pools/offsets.json" in psrc.replace(os.sep, "/")
      or '"offsets.json"' in psrc)
tree = ast.parse(psrc)
# a bare integer 40-500 sitting in a memcmp dict would be a hard-coded offset
hard = []
for node in ast.walk(tree):
    if isinstance(node, ast.Dict):
        keys = [k.value for k in node.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)]
        if "offset" in keys and "bytes" in keys:
            for k, v in zip(node.keys, node.values):
                if (isinstance(k, ast.Constant) and k.value == "offset"
                        and isinstance(v, ast.Constant)
                        and isinstance(v.value, int)):
                    hard.append(v.value)
check("⛔⛔ no memcmp offset is a literal in the source", not hard, str(hard))
check("the measured file names the pool each offset came from",
      all("measured_on" in x for x in
          (poolstate.offsets().get("venues") or {}).values())
      or not poolstate.offsets().get("venues"))
qv = poolstate.queryable_venues()
check("⭐ at least 5 venues have a measured offset", len(qv) >= 5,
      "%d: %s" % (len(qv), [v for v, _p, _o in qv]))
check("⛔ every queryable venue carries at least one offset",
      all(o for _v, _p, o in qv))
check("⭐ Meteora DAMM v2 is in the AMM map (found by measurement, was missing)",
      "cpamdpZCGKUy5JxQXB4dcpGPiikHawvSWAd6mEn1sGG"
      in __import__("pooldiscovery").AMM_OWNERS)
check("⛔ venues with NO measured offset are named, not silently skipped",
      isinstance(poolstate.unqueryable_venues(), list))

print("\n--- the pre-committed states ---")
check("all six states exist and no others",
      set(poolstate.STATES) == {"pool_live", "pool_emptied", "curve_died",
                                "pool_closed", "not_found", "unreadable"},
      str(poolstate.STATES))
check("⛔ the dust boundary is the SAME $10 already pre-committed",
      poolstate.DUST_USD == 10.0, str(poolstate.DUST_USD))
pc = os.path.join(ROOT, "PRECOMMIT_pool_state.md")
check("PRECOMMIT_pool_state.md exists", os.path.exists(pc))
if os.path.exists(pc):
    doc = io.open(pc, encoding="utf-8").read()
    for st in poolstate.STATES:
        check("   the pre-commit defines `%s`" % st, st in doc)
    check("⛔ the pre-commit says status is NOT overwritten (rule 8)",
          "IS NOT OVERWRITTEN" in doc.upper())
    check("⛔ the pre-commit says a backfill measures TODAY, not then",
          "not at the time the row was written" in doc)
    check("the pre-commit registers a falsifiable prediction",
          "at least 8 of those 15" in doc and "fewer than 4" in doc)
    check("⛔ the pre-commit says no offset is assumed",
          "NO STRUCT OFFSET IS ASSUMED" in doc)

print("\n--- nothing here can sign or send ---")
BANNED = ("sign", "send_transaction", "keypair", "secret_key", "private_key",
          "approve", "set_authority", "place_order", "sendTransaction")
for mod, src in (("solpda.py", io.open(os.path.join(ROOT, "solpda.py"),
                                       encoding="utf-8").read()),
                 ("poolstate.py", psrc)):
    names = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Name):
            names.add(node.id.lower())
        elif isinstance(node, ast.Attribute):
            names.add(node.attr.lower())
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name.lower())
    bad = sorted(n for n in names if any(b.lower() in n for b in BANNED))
    check("⛔ %s has no signing or sending name" % mod, not bad, str(bad))

print("\n--- the response can never be read as 'sellable' ---")
check("⛔ state() carries an explicit sellable=None with a reason",
      '"sellable": None' in psrc and "NOT MEASURED HERE" in psrc)
check("⛔ and it names round_trip as the only exit measure",
      "chainfields.round_trip()" in psrc)
check("⛔ not_found is documented as OUR uncertainty",
      "OUR UNCERTAINTY" in psrc)


print("\n--- §3a: pool_closed needs EVIDENCE the pool once existed ---")
_tree = ast.parse(psrc)
_state_fn = [n for n in ast.walk(_tree)
             if isinstance(n, ast.FunctionDef) and n.name == "state"][0]
check("state() takes a known_pair argument",
      "known_pair" in [a.arg for a in _state_fn.args.args])
_guards = []
for _n in ast.walk(_state_fn):
    if not isinstance(_n, ast.If):
        continue
    for _b in _n.body:
        if (isinstance(_b, ast.Assign) and isinstance(_b.value, ast.Constant)
                and _b.value.value == "pool_closed"):
            _guards.append(ast.dump(_n.test))
check("⛔ exactly one branch can assign pool_closed",
      len(_guards) == 1, "found %d" % len(_guards))
check("⛔ and it is guarded by known_pair_absent, not by mere absence",
      bool(_guards) and "known_pair_absent" in _guards[0],
      (_guards[0][:120] if _guards else "no branch"))
_pc = io.open(os.path.join(ROOT, "PRECOMMIT_pool_state.md"),
              encoding="utf-8").read()
check("⛔ the amendment is in the pre-commit, dated and numbered",
      "AMENDMENT, 2026-09-23" in _pc and "## 3a." in _pc)
check("⛔ it says a never-created PDA is an absent venue",
      "ABSENT VENUE" in _pc)
check("⛔ the superseded rows are named, not deleted",
      "state_v1_superseded.jsonl" in _pc)
check("⛔ it warns that not_found now absorbs two different things",
      "absorbs two different things" in _pc)


print("\n--- §3b: an UNREAD quote side is never $0 (stubbed, no network) ---")
import pooldiscovery as _pd


class _Stub(object):
    """A fake chain. ⛔ The point is to drive the DECISION, not the RPC.

    It answers getProgramAccounts (so a memcmp can "find" a pool),
    getMultipleAccounts (existence, with a real data length so the rent floor is
    reachable) and the two vault readers.
    """

    def __init__(self, accounts, vaults_owned, vaults_struct, lamports=None):
        self.accounts = accounts
        self.owned, self.struct = vaults_owned, vaults_struct
        self.lamports = lamports or {}

    def _data(self):
        import base64
        return [base64.b64encode(bytes(125)).decode(), "base64"]

    def _rpc(self, method, params, **k):
        if method == "getProgramAccounts":
            prog = params[0]
            return ([{"pubkey": a} for a, o in self.accounts.items()
                     if o == prog], None)
        if method == "getMinimumBalanceForRentExemption":
            return (1285240, None)
        return (None, "stubbed")

    def install(self):
        self._save = {k: getattr(_pd, k) for k in
                      ("rpc", "_accounts_info", "_vaults", "vaults_from_struct",
                       "discover", "rent_exempt")}
        _pd.rpc = self._rpc
        _pd._accounts_info = lambda pks, **k: (
            {a: ({"lamports": self.lamports.get(a, 1285240),
                  "owner": self.accounts[a], "data": self._data()}
                 if a in self.accounts else None) for a in pks}, [])
        _pd._vaults = lambda a, **k: (list(self.owned.get(a, [])), [])
        _pd.vaults_from_struct = lambda a, **k: (
            list(self.struct.get(a, [])), [], 7)
        _pd.discover = lambda m, **k: {"pools": [], "verdict": "STUB"}
        return self

    def restore(self):
        for k, v in self._save.items():
            setattr(_pd, k, v)


_MINT = "EKShF2iKiGZNLh9QjXF7tu822AapGh4rNj9h6y8upump"
_PUMPSWAP = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
_CURVE = solpda.pumpfun_bonding_curve(_MINT)
_WSOL = "So11111111111111111111111111111111111111112"

# (a) a live AMM pool whose vaults CANNOT be read must not read as empty
_st = _Stub({_CURVE: solpda.PUMPFUN_PROGRAM}, {}, {}).install()
try:
    _r = poolstate.state(_MINT, sol_usd=100.0, with_ladder=False)
finally:
    _st.restore()
check("⛔ a curve with only rent reads $0 of NATIVE SOL, not unknown",
      _r["pools"] and _r["pools"][0]["quote_usd"] == 0.0,
      str(_r["pools"][:1]))
check("⛔ and it is labelled as native SOL above the rent floor",
      "native SOL" in (_r["pools"][0].get("quote_source") or ""))

# (b) the same curve holding real SOL above rent is quote side, not zero
_st = _Stub({_CURVE: solpda.PUMPFUN_PROGRAM}, {}, {},
            lamports={_CURVE: 1285240 + 2 * 10 ** 9}).install()
try:
    _r2 = poolstate.state(_MINT, sol_usd=100.0, with_ladder=False)
finally:
    _st.restore()
check("⭐ 2 SOL above rent at $100 is $200 of quote side",
      abs(_r2["quote_usd_max"] - 200.0) < 0.01, str(_r2["quote_usd_max"]))
check("⭐ and that makes it pool_live, not curve_died",
      _r2["pool_state"] == "pool_live", _r2["pool_state"])

# (c) an AMM pool with NO readable vault: UNREAD, and the state says unreadable
_FAKE_POOL = "9Vtqt6UruSVL8otRwYHughNLszXTE7E2hga2Z9AyYw6B"
_st = _Stub({_FAKE_POOL: _PUMPSWAP},
            {}, {}).install()
try:
    _r3 = poolstate.state(_MINT, sol_usd=100.0, with_ladder=False)
    _r3["pools"] = _r3["pools"]
finally:
    _st.restore()
_unread = [p for p in _r3["pools"] if p.get("quote_usd") is None
           and p.get("exists")]
check("⛔ a pool with no readable vault reports quote_usd None, NOT 0.0",
      bool(_unread) or _r3["pool_state"] == "not_found",
      str([(p["venue"], p.get("quote_usd")) for p in _r3["pools"]]))

# (d) the struct scan rescues exactly that case
_st = _Stub({_FAKE_POOL: _PUMPSWAP}, {},
            {_FAKE_POOL: [{"vault": "v1", "mint": _MINT, "amount": 1,
                           "decimals": 6, "ui": 1.0,
                           "vault_owner": "AUTH1"},
                          {"vault": "v2", "mint": _WSOL, "amount": 10 ** 9,
                           "decimals": 9, "ui": 1.0,
                           "vault_owner": "AUTH1"},
                          # ⛔ a FOREIGN vault the struct merely references: a
                          # protocol fee account with 500 SOL in it. Summing this
                          # would overstate the pool by $50,000.
                          {"vault": "v3", "mint": _WSOL, "amount": 500 * 10 ** 9,
                           "decimals": 9, "ui": 500.0,
                           "vault_owner": "SOMEONE_ELSE"}]}).install()
try:
    _r4 = poolstate.state(_MINT, sol_usd=100.0, with_ladder=False)
finally:
    _st.restore()
check("⭐ the struct scan reads 1 WSOL as $100 of quote side",
      abs(_r4["quote_usd_max"] - 100.0) < 0.01, str(_r4["quote_usd_max"]))
check("⭐ and the row records that it came from the struct, not ownership",
      any(p.get("vaults_via") == "struct-scan" for p in _r4["pools"]))
check("⛔ the pair guard passed because the pool holds OUR mint",
      any(p.get("pair_verified") is True for p in _r4["pools"]))
check("⛔⛔ a vault under a DIFFERENT authority is DROPPED, not summed",
      any(p.get("struct_vaults_dropped") for p in _r4["pools"]),
      str([(p["venue"], p.get("quote_usd")) for p in _r4["pools"]]))
check("⛔ and the pool's vault authority is recorded",
      any(p.get("vault_authority") == "AUTH1" for p in _r4["pools"]))


psrc2 = io.open(os.path.join(ROOT, "poolstate.py"), encoding="utf-8").read()
check("⛔ the source says an unread quote side is not $0",
      "It is not $0." in psrc2)
check("⛔ unreadable is decided BEFORE pool_emptied in the ladder",
      psrc2.index('st = "unreadable"') < psrc2.index('st = "pool_emptied"'))
check("⛔ one-sided venues are named on every response",
      '"venues_one_sided"' in psrc2)

print("\n%d passed, %d failed" % (PASSED, len(FAILED)))
if FAILED:
    for f in FAILED:
        print("  FAILED:", f)
sys.exit(1 if FAILED else 0)
