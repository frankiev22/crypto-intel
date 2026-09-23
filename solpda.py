"""Solana program-derived addresses, in pure stdlib.

Needed because a pool's address is often a deterministic function of the mint,
and deriving it does NOT depend on how much the pool holds. The token-account
ladder in `pooldiscovery.py` reaches the largest holders only, which is exactly
why it missed a sellable token whose vault was not in the top 100.

`find_program_address` is: sha256(seeds || program_id || "ProgramDerivedAddress")
with a bump byte appended to the seeds, counting down from 255, taking the first
result that is NOT a valid ed25519 curve point. The curve check is the fiddly
part and it is done here rather than assumed away.

⛔ Every function here is verified against addresses found INDEPENDENTLY by
`pooldiscovery`, in `test_solpda.py`. A derivation that is never checked against
a known answer is a guess.
"""
import hashlib

_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_B58_INDEX = {c: i for i, c in enumerate(_B58)}

PDA_MARKER = b"ProgramDerivedAddress"

# ed25519 field / curve constants
_P = 2 ** 255 - 19
_D = (-121665 * pow(121666, _P - 2, _P)) % _P


def b58decode(s):
    """Base58 to bytes. ⛔ Raises on a bad character rather than returning junk."""
    n = 0
    for ch in s:
        v = _B58_INDEX.get(ch)
        if v is None:
            raise ValueError("not base58: %r" % ch)
        n = n * 58 + v
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    pad = 0
    for ch in s:
        if ch != "1":
            break
        pad += 1
    return b"\x00" * pad + raw


def b58encode(raw):
    n = int.from_bytes(raw, "big")
    out = ""
    while n:
        n, r = divmod(n, 58)
        out = _B58[r] + out
    pad = 0
    for b in raw:
        if b:
            break
        pad += 1
    return "1" * pad + (out or "")


def _is_on_curve(raw):
    """True if these 32 bytes decompress to a valid ed25519 point.

    A PDA must NOT be on the curve, which is what guarantees no private key can
    exist for it. This is the check `find_program_address` loops on.
    """
    if len(raw) != 32:
        return False
    y = int.from_bytes(raw, "little")
    # named `high_bit`, not `sign`: it is the ed25519 coordinate sign bit and has
    # nothing to do with signing a transaction. test_solpda.py's AST guard bans
    # any name containing `sign`, and the guard stays absolute rather than gaining
    # an exemption for this one case.
    high_bit = (y >> 255) & 1
    y &= (1 << 255) - 1
    if y >= _P:
        return False
    # solve x^2 = (y^2 - 1) / (d*y^2 + 1)
    yy = (y * y) % _P
    u = (yy - 1) % _P
    v = (_D * yy + 1) % _P
    try:
        vinv = pow(v, _P - 2, _P)
    except ValueError:
        return False
    xx = (u * vinv) % _P
    x = pow(xx, (_P + 3) // 8, _P)
    if (x * x - xx) % _P != 0:
        x = (x * pow(2, (_P - 1) // 4, _P)) % _P
        if (x * x - xx) % _P != 0:
            return False
    if x == 0 and high_bit:
        return False
    return True


def create_program_address(seeds, program_id):
    """One candidate address, or None when it lands ON the curve."""
    h = hashlib.sha256()
    for s in seeds:
        if len(s) > 32:
            raise ValueError("seed longer than 32 bytes")
        h.update(s)
    h.update(b58decode(program_id) if isinstance(program_id, str) else program_id)
    h.update(PDA_MARKER)
    raw = h.digest()
    if _is_on_curve(raw):
        return None
    return b58encode(raw)


def find_program_address(seeds, program_id):
    """(address, bump). ⛔ Raises if no bump works, never returns a silent None."""
    for bump in range(255, -1, -1):
        got = create_program_address(list(seeds) + [bytes([bump])], program_id)
        if got is not None:
            return got, bump
    raise ValueError("no off-curve bump found")


# ---------------------------------------------------------------------------
# The derivations that are a pure function of the mint
# ---------------------------------------------------------------------------
PUMPFUN_PROGRAM = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"


def pumpfun_bonding_curve(mint):
    """The pump.fun bonding curve PDA for this mint.

    ⭐ Verified against curves that `pooldiscovery` found by an unrelated route
    (enumerating token accounts), in `test_solpda.py`.
    """
    addr, _bump = find_program_address(
        [b"bonding-curve", b58decode(mint)], PUMPFUN_PROGRAM)
    return addr


def associated_token_address(owner, mint, token_program=None):
    """The ATA, which is how a curve or pool holds the base token."""
    tok = token_program or "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
    addr, _bump = find_program_address(
        [b58decode(owner), b58decode(tok), b58decode(mint)],
        "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")
    return addr
