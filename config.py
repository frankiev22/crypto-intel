"""
Central config. Every key is optional - the stack degrades to free public
endpoints when a key is absent and tells you exactly what it lost.

Keys come from the .env file sitting next to this file, or from the real
environment, which wins over .env. Nothing here ever writes or logs a value.
    HELIUS_API_KEY  BIRDEYE_API_KEY  ETHERSCAN_API_KEY  ALCHEMY_API_KEY
    CRYPTO_DISCORD_WEBHOOK
"""
import os

ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

def _load_env(path=ENV_FILE):
    """Read .env into os.environ. Anything already set in the real environment
    wins. Uses python-dotenv when it is installed, otherwise a minimal parser,
    so a scheduled run under a different interpreter still picks the keys up."""
    if not os.path.exists(path):
        return
    try:
        from dotenv import load_dotenv
        load_dotenv(path, override=False)
        return
    except ImportError:
        pass
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and v and k not in os.environ:
                os.environ[k] = v

_load_env()

KEYS = {
    "helius":    ("HELIUS_API_KEY",    "Solana websockets + webhooks. Real-time wallet + pump.fun. Falls back to polling public RPC."),
    "birdeye":   ("BIRDEYE_API_KEY",   "Holder distribution and concentration. No free substitute exists."),
    "etherscan": ("ETHERSCAN_API_KEY", "ETH contract verification, holder counts, proxy detection."),
    "alchemy":   ("ALCHEMY_API_KEY",   "ETH RPC. Falls back to public endpoints with lower limits."),
}
DISCORD_WEBHOOK = os.environ.get("CRYPTO_DISCORD_WEBHOOK", "")

def key(name):
    return os.environ.get(KEYS[name][0], "")

def have(name):
    return bool(key(name))

def helius_rpc():
    k = key("helius")
    return f"https://mainnet.helius-rpc.com/?api-key={k}" if k else "https://api.mainnet-beta.solana.com"

def helius_ws():
    k = key("helius")
    return f"wss://mainnet.helius-rpc.com/?api-key={k}" if k else None

def status():
    lines, missing = [], []
    for n, (env, why) in KEYS.items():
        if have(n):
            lines.append(f"  [ok]      {n:<10} {env}")
        else:
            lines.append(f"  [missing] {n:<10} {env}  -> {why}")
            missing.append(n)
    lines.append(f"  [{'ok' if DISCORD_WEBHOOK else 'missing'}]      discord    CRYPTO_DISCORD_WEBHOOK")
    return "\n".join(lines), missing

if __name__ == "__main__":
    s, missing = status()
    print("\nCRYPTO INTEL - key status\n"); print(s)
    print(f"\n  Solana RPC in use: {'HELIUS' if have('helius') else 'public mainnet-beta (rate limited)'}")
    print(f"  {len(KEYS)-len(missing)}/{len(KEYS)} keys present\n")
