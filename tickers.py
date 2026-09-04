"""Ticker collision, and the difference between reuse and impersonation.

WHY. On 2026-09-01 the instruction was to score down any token reusing an
existing ticker. Measured on our own data 2026-09-04, that is wrong, and the
scale is the reason: 58.1% of the 16,748 tokens we have observed share a symbol
with another token, across 2,338 colliding symbols. Case-insensitively it is
63.8%. `sol` alone is 92 contracts, `solana` 77, `$1` 50. 127 symbols have more
than one contract that scored 100. Collision is the normal state of the stream,
not a defect in a token.

It also does not predict failure. Best realizable multiple by variant count,
entry liq > $8,000, FULL denominator - every entry counted, no realizable later
outcome scored as the 0x it was:

    unique  n=302  5.6% >= 2x      4-9  n=397  3.8% >= 2x
    2-3     n=243  4.9% >= 2x      10+  n=318  3.8% >= 2x

Restricted instead to tokens that HAVE a realizable later outcome - the
denominator that produced the reported "4-9 is the sweet spot" - it inverts:

    unique  n=42  40.5%  [27.0%, 55.5%]      4-9  n=34  44.1%  [28.9%, 60.5%]
    2-3     n=32  37.5%  [22.9%, 54.7%]      10+  n=38  31.6%  [19.1%, 47.5%]

Every interval overlaps every other. The sweet spot is not distinguishable from
noise, and the ordering flips with the denominator. So: no penalty, and no
bonus either. The count is RECORDED as a feature and scored by nothing until
something measurable turns up.

IMPERSONATION IS A DIFFERENT THING and is kept separate. Reusing "moon" is
crowd behaviour. A right-to-left override that renders a token as `Alokau` when
its bytes say otherwise, or a token calling itself USDT, is an attempt to be
mistaken for something specific. That is detected here structurally - control
characters and incumbent names - never by variant count.
"""
import json, os, unicodedata

BASE = os.path.dirname(os.path.abspath(__file__))
IDX = os.path.join(BASE, "data", "tickers", "index.json")

# Bidi controls and invisibles. `‮` (U+202E) is the one that produced a token
# rendering as an existing name spelled backwards.
BIDI = {"\u202a", "\u202b", "\u202c", "\u202d", "\u202e",
        "\u2066", "\u2067", "\u2068", "\u2069",
        "\u200e", "\u200f", "\u200b", "\u200c", "\u200d", "\ufeff"}

# Names a new launch has no business claiming. Not a blocklist - a flag.
INCUMBENTS = {
    "usdt", "usdc", "dai", "busd", "usde", "tether", "circle",
    "btc", "bitcoin", "eth", "ethereum", "sol", "solana", "bnb", "xrp",
    "ada", "doge", "avax", "dot", "link", "matic", "trx", "ton",
    "jup", "jito", "jto", "pyth", "ray", "orca", "bonk", "wif", "pump",
    "anthropic", "claude", "openai", "chatgpt", "nvidia", "tesla", "apple",
}


def _load():
    try:
        with open(IDX, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save(idx):
    os.makedirs(os.path.dirname(IDX), exist_ok=True)
    tmp = IDX + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(idx, f, separators=(",", ":"))
        os.replace(tmp, IDX)
    except OSError:
        pass


def key(symbol):
    """Fold a symbol to the form two tokens collide on."""
    s = unicodedata.normalize("NFKC", (symbol or "")).strip()
    s = "".join(c for c in s if c not in BIDI)
    return s.casefold()


def rebuild(observations):
    """Build the symbol -> contracts index from the observation journal."""
    idx = {}
    for o in observations:
        k = key(o.get("symbol"))
        t = o.get("token")
        if not k or not t:
            continue
        idx.setdefault(k, [])
        if t not in idx[k]:
            idx[k].append(t)
    _save(idx)
    return idx


def note(symbol, token, idx=None):
    """Record a sighting and return how many contracts now share the symbol."""
    own = idx is None
    idx = _load() if own else idx
    k = key(symbol)
    if k and token:
        idx.setdefault(k, [])
        if token not in idx[k]:
            idx[k].append(token)
    if own:
        _save(idx)
    return len(idx.get(k, [])) or 1


def variants(symbol, idx=None):
    idx = _load() if idx is None else idx
    return len(idx.get(key(symbol), [])) or 1


def impersonation(symbol):
    """Structural flags, in order of how hard they are to explain away.

    Returns a list, possibly empty. Never a score.
    """
    raw = symbol or ""
    out = []
    if any(c in BIDI for c in raw):
        out.append("bidi_control_character")
    norm = unicodedata.normalize("NFKC", raw).strip()
    stripped = "".join(c for c in norm if c not in BIDI).casefold()
    alnum = "".join(c for c in stripped if c.isalnum())
    if alnum and alnum in INCUMBENTS:
        out.append(f"claims_incumbent_name:{alnum}")
    # A displayed name that changes when the invisibles are removed is lying
    # about what it is, whatever it resolves to.
    if stripped != norm.casefold():
        out.append("renders_differently_than_it_reads")
    return out
