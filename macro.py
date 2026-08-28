"""
Regime dashboard. Answers one question before you look at any individual token:
is this an environment where degen plays work, or is liquidity leaving?

A great memecoin filter in a risk-off tape still loses money.
"""
import sources as S, datetime as dt

def stablecoin_supply():
    d = S._get("https://stablecoins.llama.fi/stablecoins?includePrices=true")
    tot = pct = 0.0
    for a in d.get("peggedAssets", []):
        cur  = (a.get("circulating") or {}).get("peggedUSD") or 0
        prev = (a.get("circulatingPrevDay") or {}).get("peggedUSD") or 0
        tot += cur; pct += prev
    chg = ((tot - pct) / pct * 100) if pct else 0
    return tot, chg

def snapshot():
    fg, fg_label = S.fear_greed()
    g   = S.global_market()
    px  = S.prices()
    tvl = S.chain_tvl()
    stb, stb_chg = stablecoin_supply()
    return dict(ts=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                fear_greed=fg, fear_greed_label=fg_label, **g,
                btc=px["bitcoin"]["usd"], btc_24h=px["bitcoin"]["usd_24h_change"],
                eth=px["ethereum"]["usd"], eth_24h=px["ethereum"]["usd_24h_change"],
                sol=px["solana"]["usd"], sol_24h=px["solana"]["usd_24h_change"],
                eth_tvl=tvl.get("Ethereum",0), sol_tvl=tvl.get("Solana",0),
                stablecoin_supply=stb, stablecoin_chg_24h=stb_chg)

def read(s):
    """Plain-language regime call. Not advice - a description of conditions."""
    notes = []
    if s["fear_greed"] >= 75:   notes.append("Greed is extended. Crowded tape, worse entries, sharper flushes.")
    elif s["fear_greed"] <= 25: notes.append("Fear. Historically better entries, but catching knives is its own problem.")
    if s["btc_dominance"] > 58:
        notes.append(f"BTC dominance {s['btc_dominance']:.1f}% is high. Money is sitting in majors, "
                     "not rotating down the risk curve. Harder environment for small caps.")
    else:
        notes.append(f"BTC dominance {s['btc_dominance']:.1f}%. Rotation into alts is more plausible here.")
    if s["stablecoin_chg_24h"] > 0.15:
        notes.append(f"Stablecoin supply +{s['stablecoin_chg_24h']:.2f}% in 24h. Fresh money entering.")
    elif s["stablecoin_chg_24h"] < -0.15:
        notes.append(f"Stablecoin supply {s['stablecoin_chg_24h']:.2f}% in 24h. Capital leaving.")
    else:
        notes.append("Stablecoin supply flat. No meaningful inflow either way.")
    if s["sol_24h"] > s["btc_24h"] + 2:
        notes.append("SOL outperforming BTC materially. Risk appetite present on that chain.")
    return notes

if __name__ == "__main__":
    s = snapshot()
    print(f"\n  REGIME  {s['ts']}\n")
    print(f"  BTC {s['btc']:>10,.0f}  {s['btc_24h']:+6.2f}%      dominance {s['btc_dominance']:.1f}%")
    print(f"  ETH {s['eth']:>10,.0f}  {s['eth_24h']:+6.2f}%      TVL {s['eth_tvl']/1e9:.1f}B")
    print(f"  SOL {s['sol']:>10,.2f}  {s['sol_24h']:+6.2f}%      TVL {s['sol_tvl']/1e9:.1f}B")
    print(f"\n  Total mcap  {s['total_mcap_usd']/1e12:.2f}T   24h {s['mcap_change_24h']:+.2f}%")
    print(f"  Stablecoins {s['stablecoin_supply']/1e9:.1f}B   24h {s['stablecoin_chg_24h']:+.2f}%")
    print(f"  Fear/Greed  {s['fear_greed']} ({s['fear_greed_label']})\n")
    for n in read(s): print(f"  - {n}")
    print()
