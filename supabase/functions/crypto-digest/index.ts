// crypto-digest: the regime/news/whale digest, running in the cloud.
//
// Port of digest.py. Everything it needs is reachable from an Edge Function, so
// it does not matter whether Frank's desktop is on.
//
// Coverage is 27 coins but the output stays phone-sized, because breadth is
// rendered as an AGGREGATE and individual coins only earn a line when they
// actually move. Three anchors always show; the other 24 collapse into two
// breadth lines plus a movers line that is empty on a quiet day.
//
// Auth: x-cron-secret against private.crypto_config. No secrets baked in.

const SB_URL = Deno.env.get("SUPABASE_URL")!;
const SB_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const UA = "crypto-intel/0.1 (+https://crypto-intel-one-eta.vercel.app)";
const VERSION = "0.0.3";

const sb = (path: string, init: RequestInit = {}) =>
  fetch(`${SB_URL}/rest/v1/${path}`, {
    ...init,
    headers: {
      apikey: SB_KEY, Authorization: `Bearer ${SB_KEY}`,
      "Content-Type": "application/json", "User-Agent": UA,
      ...(init.headers || {}),
    },
  });

async function getConfig(): Promise<Record<string, string>> {
  const r = await sb("rpc/read_crypto_config", { method: "POST", body: "{}" });
  if (!r.ok) return {};
  const out: Record<string, string> = {};
  for (const row of (await r.json()) || []) out[row.key] = row.value;
  return out;
}

const jget = async (url: string, timeoutMs = 20000) => {
  const c = new AbortController();
  const t = setTimeout(() => c.abort(), timeoutMs);
  try {
    const r = await fetch(url, { headers: { "User-Agent": UA, Accept: "application/json" }, signal: c.signal });
    if (!r.ok) return null;
    return await r.json();
  } catch { return null; } finally { clearTimeout(t); }
};

const median = (xs: number[]) => {
  if (!xs.length) return null;
  const s = [...xs].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
};

// ---------------------------------------------------------------- macro
async function macro(coins: any[]) {
  const ids = coins.map(c => c.coin_id).join(",");
  const [fng, glob, mkt, tvl, stb, dex, solStb] = await Promise.all([
    jget("https://api.alternative.me/fng/?limit=1"),
    jget("https://api.coingecko.com/api/v3/global"),
    jget(`https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids=${ids}&order=market_cap_desc&per_page=250`, 25000),
    jget("https://api.llama.fi/v2/chains"),
    jget("https://stablecoins.llama.fi/stablecoins?includePrices=true", 25000),
    jget("https://api.llama.fi/overview/dexs/solana?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true", 25000),
    jget("https://stablecoins.llama.fi/stablecoincharts/Solana?stablecoin=1", 25000),
  ]);
  const missing: string[] = [];
  if (!fng) missing.push("fear/greed"); if (!glob) missing.push("global");
  if (!mkt) missing.push("markets");    if (!tvl) missing.push("tvl");
  if (!stb) missing.push("stablecoins");

  const f = fng?.data?.[0];
  const g = glob?.data;

  // price map keyed by CoinGecko id
  const px: Record<string, any> = {};
  for (const c of mkt || []) {
    px[c.id] = { symbol: (c.symbol || "").toUpperCase(), price: c.current_price,
                 chg: c.price_change_percentage_24h, vol: c.total_volume, mcap: c.market_cap };
  }

  let stbTotal = 0, stbPrev = 0;
  for (const a of stb?.peggedAssets || []) {
    stbTotal += a?.circulating?.peggedUSD || 0;
    stbPrev  += a?.circulatingPrevDay?.peggedUSD || 0;
  }
  const chains: Record<string, number> = {};
  for (const c of tvl || []) chains[c.name] = c.tvl;

  // Solana stablecoin float - money actually sitting on the chain Frank trades
  let solStbNow: number | null = null, solStbChg: number | null = null;
  if (Array.isArray(solStb) && solStb.length) {
    const sum = (p: any) => Object.values(p?.totalCirculatingUSD || {}).reduce((a: number, b: any) => a + Number(b || 0), 0);
    solStbNow = sum(solStb[solStb.length - 1]);
    const prev = sum(solStb[Math.max(0, solStb.length - 2)]);
    solStbChg = prev ? ((solStbNow - prev) / prev) * 100 : null;
  }

  // trenches heat: how much is actually trading on Solana, and how much of it
  // is pump.fun's own AMM
  let dexTotal: number | null = null, dexChg: number | null = null, pumpShare: number | null = null, pumpVol: number | null = null;
  if (dex) {
    dexTotal = dex.total24h ?? null;
    dexChg = dex.change_1d ?? null;
    // DefiLlama splits the pump.fun family across three protocols:
    // "pump.fun" (bonding curve, $76M), "PumpSwap" (the AMM, $713M) and
    // "pump.fun Mobile App" ($8M). .find() returned the FIRST match and
    // reported $76M / 3%, understating the venue by roughly 10x. Sum the family.
    const fam = (dex.protocols || []).filter((p: any) => /pumpswap|pump\.fun/i.test(p?.name || ""));
    pumpVol = fam.length ? fam.reduce((s: number, p: any) => s + (p.total24h || 0), 0) : null;
    if (pumpVol && dexTotal) pumpShare = (pumpVol / dexTotal) * 100;
  }

  return {
    ok: missing.length === 0, missing,
    fear_greed: f ? Number(f.value) : null,
    fear_greed_label: f?.value_classification ?? null,
    btc_dominance: g?.market_cap_percentage?.btc ?? null,
    mcap_change_24h: g?.market_cap_change_percentage_24h_usd ?? null,
    total_mcap_usd: g?.total_market_cap?.usd ?? null,
    prices: px,
    btc: px["bitcoin"]?.price ?? null,  btc_24h: px["bitcoin"]?.chg ?? null,
    eth: px["ethereum"]?.price ?? null, eth_24h: px["ethereum"]?.chg ?? null,
    sol: px["solana"]?.price ?? null,   sol_24h: px["solana"]?.chg ?? null,
    eth_tvl: chains["Ethereum"] ?? null, sol_tvl: chains["Solana"] ?? null,
    stablecoin_supply: stbTotal || null,
    stablecoin_chg_24h: stbPrev ? ((stbTotal - stbPrev) / stbPrev) * 100 : null,
    solana_stablecoins: solStbNow, solana_stablecoins_chg: solStbChg,
    sol_dex_vol_24h: dexTotal, sol_dex_vol_chg: dexChg,
    pumpswap_vol_24h: pumpVol, pumpswap_share_pct: pumpShare,
  };
}

// tier summaries + movers
function breadth(m: any, coins: any[], moverPct: number) {
  const byTier: Record<string, any[]> = { major: [], solana: [] };
  const movers: any[] = [];
  for (const c of coins) {
    if (c.tier === "anchor") continue;
    const p = m.prices?.[c.coin_id];
    if (!p || p.chg == null) continue;
    byTier[c.tier]?.push({ symbol: c.symbol, chg: p.chg });
    if (Math.abs(p.chg) >= moverPct) movers.push({ symbol: c.symbol, chg: p.chg });
  }
  movers.sort((a, b) => Math.abs(b.chg) - Math.abs(a.chg));
  const sum = (rows: any[]) => rows.length ? {
    n: rows.length, up: rows.filter(r => r.chg > 0).length,
    median: median(rows.map(r => r.chg)),
  } : null;
  return { majors: sum(byTier.major), solana: sum(byTier.solana), movers, mover_pct: moverPct };
}

// ------------------------------------------------------------- formatting
function money(usd: number | null) {
  if (usd == null) return null;
  const a = Math.abs(usd);
  if (a >= 1e9) return `$${(usd / 1e9).toFixed(1)}B`;
  if (a >= 1e6) return `$${(usd / 1e6).toFixed(0)}M`;
  if (a >= 1e3) return `$${(usd / 1e3).toFixed(1)}k`;
  if (a >= 1) return `$${Math.round(usd).toLocaleString("en-US")}`;
  return `$${usd.toFixed(2)}`;
}
const pct = (v: number | null) => v == null ? "?" : `${v >= 0 ? "+" : ""}${v.toFixed(1)}%`;
const shortAddr = (a: string) => !a ? "" : (a.length <= 12 ? a : `${a.slice(0, 4)}..${a.slice(-4)}`);

// --------------------------------------------------------------- alerts
const FG_GREED = 75, FG_FEAR = 25, PRICE_MOVE_PCT = 5.0, STABLE_FLOW = 0.15, WHALE_ALERT_USD = 1000;

function buildAlerts(m: any, b: any, whaleTotal: number, whaleCount: number) {
  const a: { key: string; text: string }[] = [];
  if (m.fear_greed != null && m.fear_greed >= FG_GREED) a.push({ key: "greed", text: `Greed ${m.fear_greed} - crowded tape` });
  if (m.fear_greed != null && m.fear_greed <= FG_FEAR)  a.push({ key: "fear",  text: `Fear ${m.fear_greed} - capitulation zone` });
  for (const [sym, v] of [["BTC", m.btc_24h], ["ETH", m.eth_24h], ["SOL", m.sol_24h]] as [string, number | null][]) {
    if (v != null && Math.abs(v) >= PRICE_MOVE_PCT) a.push({ key: `move:${sym}:${v >= 0 ? "up" : "down"}`, text: `${sym} ${pct(v)} 24h` });
  }
  const sc = m.stablecoin_chg_24h;
  if (sc != null && Math.abs(sc) >= STABLE_FLOW) {
    a.push({ key: `stables:${sc > 0 ? "in" : "out"}`, text: `Stables ${sc >= 0 ? "+" : ""}${sc.toFixed(2)}% 24h - ${sc > 0 ? "inflow" : "capital leaving"}` });
  }
  // trenches heat: a big swing in Solana DEX volume changes whether the
  // scanner is fishing in a busy pond or an empty one
  if (m.sol_dex_vol_chg != null && Math.abs(m.sol_dex_vol_chg) >= 30) {
    a.push({ key: `dexvol:${m.sol_dex_vol_chg > 0 ? "up" : "down"}`,
             text: `Solana DEX volume ${pct(m.sol_dex_vol_chg)} 24h - trenches ${m.sol_dex_vol_chg > 0 ? "heating up" : "going quiet"}` });
  }
  if (b.solana && b.solana.median != null && Math.abs(b.solana.median) >= 6) {
    a.push({ key: `solbreadth:${b.solana.median > 0 ? "up" : "down"}`,
             text: `Solana ecosystem median ${pct(b.solana.median)} across ${b.solana.n} names` });
  }
  if (whaleTotal >= WHALE_ALERT_USD) {
    a.push({ key: "whales", text: `${money(whaleTotal)} of tracked-wallet trading across ${whaleCount} move${whaleCount === 1 ? "" : "s"}` });
  }
  return a;
}

// --------------------------------------------------------------- render
function render(d: any) {
  const L: string[] = [];
  const m = d.macro, b = d.breadth;
  L.push(`**CRYPTO INTEL** v${d.version}`);
  L.push(new Date(d.ts).toUTCString().replace(/^\w+, /, "").replace(" GMT", " UTC"));

  if (m && m.btc != null) {
    L.push("");
    L.push(`**REGIME** · Fear/Greed ${m.fear_greed ?? "?"} (${m.fear_greed_label ?? "?"})`);
    L.push(`BTC $${Math.round(m.btc).toLocaleString("en-US")} · ${pct(m.btc_24h)}`);
    L.push(`ETH $${Math.round(m.eth).toLocaleString("en-US")} · ${pct(m.eth_24h)}`);
    L.push(`SOL $${m.sol?.toFixed(2)} · ${pct(m.sol_24h)}`);
    if (m.btc_dominance != null) L.push(`BTC dom ${m.btc_dominance.toFixed(1)}% · mcap ${pct(m.mcap_change_24h)}`);
    // breadth, not a wall of tickers
    if (b?.majors) L.push(`Majors ${b.majors.up}/${b.majors.n} up · median ${pct(b.majors.median)}`);
    if (b?.solana) L.push(`Solana ${b.solana.up}/${b.solana.n} up · median ${pct(b.solana.median)}`);
    if (m.stablecoin_supply) {
      const solPart = m.solana_stablecoins ? ` · SOL ${money(m.solana_stablecoins)}` : "";
      L.push(`Stables ${money(m.stablecoin_supply)} · ${m.stablecoin_chg_24h >= 0 ? "+" : ""}${m.stablecoin_chg_24h?.toFixed(2)}%${solPart}`);
    }
  } else {
    L.push("\n**REGIME** unavailable: " + (m?.missing || []).join(", "));
  }

  // individual coins only earn a line when they actually move
  if (b?.movers?.length) {
    L.push("");
    L.push(`**MOVERS** (over ${b.mover_pct}%)`);
    L.push(b.movers.slice(0, 6).map((x: any) => `${x.symbol} ${pct(x.chg)}`).join(" · "));
  }

  if (m?.sol_dex_vol_24h) {
    L.push("");
    L.push("**TRENCHES**");
    L.push(`Solana DEX ${money(m.sol_dex_vol_24h)}/24h · ${pct(m.sol_dex_vol_chg)}`);
    if (m.pumpswap_vol_24h) {
      L.push(`PumpSwap ${money(m.pumpswap_vol_24h)} · ${m.pumpswap_share_pct?.toFixed(0)}% of chain volume`);
    }
  }

  L.push("");
  const w = d.whales || [];
  if (w.length) {
    L.push(`**WHALES** ${d.watchlist_n} tracked · ${w.length} move(s), ${money(d.whale_total)} in ${d.window_mins}m`);
    for (const x of w.slice(0, 3)) {
      const where = x.venue ? ` on ${x.venue}` : "";
      L.push(`· ${shortAddr(x.wallet)} ${x.description}${where}${x.usd != null ? ` · ${money(Number(x.usd))}` : ""}`);
    }
  } else {
    L.push(`**WHALES** ${d.watchlist_n} tracked · nothing above ${money(d.whale_min_usd)} in ${d.window_mins}m`);
  }

  L.push("");
  if ((d.news || []).length) {
    L.push(`**NEWS** ${d.news.length} in 24h`);
    for (const n of d.news.slice(0, 3)) {
      const flag = n.alert_reason ? `[${String(n.alert_reason).split(" · ")[0]}] ` : "";
      L.push(`· ${flag}${String(n.title).slice(0, 66)}`);
    }
  } else {
    L.push("**NEWS** nothing stored in the last 24h");
  }

  if ((d.alerts || []).length) {
    L.push("");
    L.push("**ALERTS**");
    for (const a of d.alerts) L.push(`⚠ ${a.text}`);
  }
  return L.join("\n");
}

async function postDiscord(url: string, content: string) {
  const r = await fetch(`${url}?wait=true`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "User-Agent": UA },
    body: JSON.stringify({ content: content.slice(0, 1900) }),
  });
  if (!r.ok) return null;
  return (await r.json().catch(() => ({})))?.id ?? null;
}

// ----------------------------------------------------------------- main
Deno.serve(async (req: Request) => {
  const cfg = await getConfig();
  const expected = cfg["cron_secret"];
  if (!expected || (req.headers.get("x-cron-secret") || "") !== expected) {
    return new Response(JSON.stringify({ error: "unauthorized" }), {
      status: 401, headers: { "Content-Type": "application/json" },
    });
  }
  const params = new URL(req.url).searchParams;
  const dry = params.get("dry") === "1";
  const forcePost = params.get("post") === "1";

  const windowMins = Number(cfg["digest_window_mins"] || "60");
  const whaleMin = Number(cfg["digest_whale_min_usd"] || "500");
  const briefingHour = Number(cfg["digest_briefing_hour_utc"] || "13");
  const moverPct = Number(cfg["digest_mover_pct"] || "7");
  const sinceIso = new Date(Date.now() - windowMins * 60000).toISOString();

  const coinsRes = await sb("crypto_tracked_coins?select=coin_id,symbol,tier&active=is.true");
  const coins = coinsRes.ok ? await coinsRes.json() : [];

  const [m, newsRes, whaleRes, wlRes, prevRes] = await Promise.all([
    macro(coins),
    sb(`crypto_news?select=title,url,outlet,published_at,alert_reason&published_at=gte.${encodeURIComponent(new Date(Date.now() - 86400000).toISOString())}&order=published_at.desc&limit=6`),
    sb(`crypto_whale_events?select=wallet,occurred_at,action,venue,usd,description&known=is.true&usd=gte.${whaleMin}&occurred_at=gte.${encodeURIComponent(sinceIso)}&order=usd.desc&limit=10`),
    sb("crypto_watchlist?select=wallet&active=is.true"),
    sb("crypto_digests?select=captured_at,payload&order=captured_at.desc&limit=1"),
  ]);

  const news = newsRes.ok ? await newsRes.json() : [];
  const whales = whaleRes.ok ? await whaleRes.json() : [];
  const watchlist = wlRes.ok ? await wlRes.json() : [];
  const prev = prevRes.ok ? (await prevRes.json())[0] : null;

  const b = breadth(m, coins, moverPct);
  const whaleTotal = whales.reduce((s: number, x: any) => s + (Number(x.usd) || 0), 0);
  const alerts = buildAlerts(m, b, whaleTotal, whales.length);

  const d = {
    ts: new Date().toISOString(), version: VERSION, source: "edge",
    window_mins: windowMins, whale_min_usd: whaleMin,
    macro: m, breadth: b, news, whales, alerts,
    coins_tracked: coins.length,
    watchlist_n: watchlist.length, whale_total: whaleTotal,
    errors: m.ok ? {} : { macro: `missing: ${m.missing.join(", ")}` },
  };
  const body = render(d);

  let published: any = null;
  if (!dry) {
    const r = await sb("crypto_digests", {
      method: "POST", headers: { Prefer: "return=representation" },
      body: JSON.stringify({ captured_at: d.ts, version: VERSION, payload: d }),
    });
    published = r.ok ? (await r.json())[0]?.id : `HTTP ${r.status}: ${(await r.text()).slice(0, 120)}`;
  }

  const prevKeys = new Set<string>((prev?.payload?.alerts || []).map((a: any) => a.key ?? a));
  const newAlerts = alerts.filter(a => !prevKeys.has(a.key));
  const today = d.ts.slice(0, 10);
  const briefingDue = cfg["last_briefing_date"] !== today
    && new Date(d.ts).getUTCHours() >= briefingHour;

  let reason: string | null = null;
  if (forcePost) reason = "forced";
  else if (newAlerts.length) reason = `new alert condition: ${newAlerts.map(a => a.key).join(", ")}`;
  else if (briefingDue) reason = "daily briefing";

  let messageId: string | null = null;
  const webhook = cfg["discord_webhook_url"];
  if (reason && webhook && !dry) {
    const header = reason === "daily briefing" ? "" : `_${newAlerts.map(a => a.text).join(" · ")}_\n\n`;
    messageId = await postDiscord(webhook, header + body);
    if (messageId && (briefingDue || forcePost)) {
      await sb("rpc/write_crypto_config", {
        method: "POST", body: JSON.stringify({ p_key: "last_briefing_date", p_value: today }),
      });
    }
  }

  return new Response(JSON.stringify({
    ok: true, dry, version: VERSION,
    coins_tracked: coins.length, macro_ok: m.ok, macro_missing: m.missing,
    prices_returned: Object.keys(m.prices || {}).length,
    breadth: { majors: b.majors, solana: b.solana, movers: b.movers.length },
    trenches: { sol_dex_vol_24h: m.sol_dex_vol_24h, chg: m.sol_dex_vol_chg,
                pumpswap_share_pct: m.pumpswap_share_pct },
    news: news.length, whales: whales.length,
    alerts: alerts.map(a => a.key),
    new_alert_conditions: newAlerts.map(a => a.key),
    published_row: published,
    discord: reason ? { posted: !!messageId, reason, messageId } : { posted: false, reason: "no new condition, briefing already sent" },
    body,
  }, null, 1), { headers: { "Content-Type": "application/json" } });
});
