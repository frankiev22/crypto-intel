// Helius webhook -> decode -> Supabase -> Discord.
//
// This runs on Vercel, not on Frank's desktop, which is the entire point: whale
// alerts fire while that machine is off.
//
// Every secret here is a server-side env var. Nothing in this file is ever sent
// to a browser.
//   HELIUS_WEBHOOK_SECRET   shared secret Helius echoes in the Authorization header
//   DISCORD_WEBHOOK_URL     where alerts land
//   SUPABASE_URL / SUPABASE_PUBLISHABLE_KEY / CRYPTO_WHALE_SECRET
//   (whale gate only - it cannot publish digests or write config)
//   HELIUS_API_KEY          token metadata lookups
//   BIRDEYE_API_KEY         USD pricing
//   WATCHED_WALLETS         comma separated; who we attribute actions to
//   WHALE_MIN_USD           alert floor, default 500
//   WHALE_WINDOW_MINS       one message per wallet per N minutes, default 10

const SOL_MINT = "So11111111111111111111111111111111111111112";
const LAMPORTS = 1e9;

const VENUES = {
  JUPITER: "Jupiter", RAYDIUM: "Raydium", ORCA: "Orca", METEORA: "Meteora",
  PUMP_FUN: "Pump.fun", PUMP_AMM: "Pump.fun", PHOENIX: "Phoenix",
  LIFINITY: "Lifinity", OPENBOOK: "OpenBook",
};

// warm-invocation caches; harmless when the lambda is recycled
const symCache = new Map();
const pxCache = new Map();

const env = (k, d) => process.env[k] || d;

function watched() {
  return new Set((env("WATCHED_WALLETS", "") || "")
    .split(",").map(s => s.trim()).filter(Boolean));
}

async function symbolOf(mint) {
  if (!mint) return null;
  if (mint === SOL_MINT) return "SOL";
  if (symCache.has(mint)) return symCache.get(mint);
  let sym = null;
  try {
    const r = await fetch(`https://mainnet.helius-rpc.com/?api-key=${env("HELIUS_API_KEY")}`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "getAsset", params: { id: mint } }),
    });
    const d = await r.json();
    sym = d?.result?.content?.metadata?.symbol?.trim()?.slice(0, 12) || null;
  } catch { sym = null; }
  symCache.set(mint, sym);
  return sym;
}

async function priceOf(mint) {
  if (!mint) return null;
  const hit = pxCache.get(mint);
  if (hit && Date.now() - hit.at < 600000) return hit.usd;
  let usd = null;
  // Birdeye is ~1 req/sec and answers 429 above that. Retry rather than record
  // a rate limit as "no price" - a cached null silently suppresses real alerts.
  for (let i = 0; i < 3 && usd == null; i++) {
    try {
      const r = await fetch(`https://public-api.birdeye.so/defi/price?address=${mint}`, {
        headers: { "X-API-KEY": env("BIRDEYE_API_KEY", ""), "x-chain": "solana" },
      });
      if (r.ok) { const d = await r.json(); if (d?.success) usd = d?.data?.value ?? null; }
      else if (r.status === 429) await new Promise(s => setTimeout(s, 1100));
    } catch { /* retry */ }
  }
  if (usd != null) pxCache.set(mint, { usd, at: Date.now() });
  return usd;
}

const whole = (raw, dec) => {
  const n = Number(raw), d = Number(dec);
  return Number.isFinite(n) && Number.isFinite(d) ? n / 10 ** d : null;
};

function swapLegs(tx, wallet) {
  const sw = tx?.events?.swap || {};
  const gave = [], got = [];
  for (const x of sw.tokenInputs || [])
    if (x.userAccount === wallet) {
      const a = whole(x.rawTokenAmount?.tokenAmount, x.rawTokenAmount?.decimals);
      if (a) gave.push([x.mint, a]);
    }
  for (const x of sw.tokenOutputs || [])
    if (x.userAccount === wallet) {
      const a = whole(x.rawTokenAmount?.tokenAmount, x.rawTokenAmount?.decimals);
      if (a) got.push([x.mint, a]);
    }
  if (sw.nativeInput?.account === wallet) gave.push([SOL_MINT, Number(sw.nativeInput.amount) / LAMPORTS]);
  if (sw.nativeOutput?.account === wallet) got.push([SOL_MINT, Number(sw.nativeOutput.amount) / LAMPORTS]);
  return { gave, got };
}

function isActor(tx, wallet) {
  if (tx.feePayer === wallet) return true;
  const { gave, got } = swapLegs(tx, wallet);
  if (gave.length || got.length) return true;
  for (const x of tx.tokenTransfers || [])
    if (x.fromUserAccount === wallet || x.toUserAccount === wallet) return true;
  for (const x of tx.nativeTransfers || [])
    if (x.fromUserAccount === wallet || x.toUserAccount === wallet) return true;
  return false;
}

async function amountStr(mint, amt) {
  const sym = await symbolOf(mint);
  const n = amt >= 1000 ? amt.toLocaleString("en-US", { maximumFractionDigits: 0 })
          : amt >= 1 ? amt.toFixed(2)
          : String(Number(amt.toFixed(4)));
  return sym ? `${n} ${sym}` : `${n} of an unnamed token`;
}

async function usdOf(legs) {
  for (const [mint, amt] of legs)
    if (mint === SOL_MINT) { const p = await priceOf(mint); if (p != null) return p * amt; }
  for (const [mint, amt] of legs) { const p = await priceOf(mint); if (p != null) return p * amt; }
  return null;
}

function money(usd) {
  if (usd == null) return null;
  const a = Math.abs(usd);
  if (a >= 1e6) return `$${(usd / 1e6).toFixed(1)}M`;
  if (a >= 1e3) return `$${(usd / 1e3).toFixed(1)}k`;
  if (a >= 1) return `$${Math.round(usd).toLocaleString("en-US")}`;
  return `$${usd.toFixed(2)}`;
}

// Mirrors moves.py. Returns null when the wallet was only mentioned.
async function describe(tx, wallet) {
  if (!isActor(tx, wallet)) return null;
  const base = {
    wallet, ts: tx.timestamp || 0, sig: tx.signature || "",
    venue: VENUES[tx.source] || null, usd: null, known: false, action: null,
    text: "made a transaction we could not decode",
  };
  const { gave, got } = swapLegs(tx, wallet);

  if (gave.length && got.length) {
    const soldSol = gave.some(([m]) => m === SOL_MINT);
    const usd = (await usdOf(soldSol ? gave : got)) ?? (await usdOf(soldSol ? got : gave));
    const action = soldSol ? "bought" : "sold";
    const subject = soldSol ? got[0] : gave[0];
    const counter = soldSol ? gave[0] : got[0];
    return { ...base, known: true, action, usd,
             text: `${action} ${await amountStr(...subject)} for ${await amountStr(...counter)}` };
  }
  if (gave.length || got.length) {
    const legs = got.length ? got : gave;
    const action = got.length ? "received" : "sent";
    return { ...base, known: true, action, usd: await usdOf(legs),
             text: `${action} ${await amountStr(...legs[0])}` };
  }

  const net = new Map();
  const bump = (m, v) => net.set(m, (net.get(m) || 0) + v);
  for (const x of tx.tokenTransfers || []) {
    const a = Number(x.tokenAmount);
    if (!Number.isFinite(a)) continue;
    if (x.toUserAccount === wallet) bump(x.mint, a);
    else if (x.fromUserAccount === wallet) bump(x.mint, -a);
  }
  for (const x of tx.nativeTransfers || []) {
    const a = Number(x.amount) / LAMPORTS;
    if (x.toUserAccount === wallet) bump(SOL_MINT, a);
    else if (x.fromUserAccount === wallet) bump(SOL_MINT, -a);
  }
  let best = null;
  for (const [m, v] of net) {
    if (Math.abs(v) < 1e-9) continue;
    const p = await priceOf(m);
    const val = p == null ? 0 : Math.abs(v) * p;
    if (!best || val > best.val) best = { mint: m, delta: v, val };
  }
  if (best) {
    const action = best.delta > 0 ? "received" : "sent";
    const p = await priceOf(best.mint);
    return { ...base, known: true, action,
             usd: p == null ? null : Math.abs(best.delta) * p,
             text: `${action} ${await amountStr(best.mint, Math.abs(best.delta))}` };
  }
  return base;
}

async function recordEvent(rec) {
  const r = await fetch(`${env("SUPABASE_URL")}/rest/v1/rpc/record_whale_event`, {
    method: "POST",
    headers: {
      apikey: env("SUPABASE_PUBLISHABLE_KEY"),
      Authorization: `Bearer ${env("SUPABASE_PUBLISHABLE_KEY")}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      p_secret: env("CRYPTO_WHALE_SECRET"),
      p_wallet: rec.wallet,
      p_signature: rec.sig,
      p_occurred_at: new Date((rec.ts || Math.floor(Date.now() / 1000)) * 1000).toISOString(),
      p_action: rec.action,
      p_venue: rec.venue,
      p_usd: rec.usd,
      p_description: rec.text,
      p_known: rec.known,
      p_min_usd: Number(env("WHALE_MIN_USD", "500")),
      p_window_mins: Number(env("WHALE_WINDOW_MINS", "10")),
    }),
  });
  if (!r.ok) return { stored: false, should_alert: false, reason: `supabase HTTP ${r.status}` };
  return await r.json();
}

const shortAddr = a => (!a || a.length <= 12) ? a : `${a.slice(0, 4)}…${a.slice(-4)}`;

// What this wallet has actually done before. Activity only for now: realized
// win rate arrives with the PnL-ranked watchlist. Saying "12 prior decoded
// moves" is honest; implying a win rate we do not compute would not be.
async function walletRecord(wallet) {
  try {
    const r = await fetch(
      `${env("SUPABASE_URL")}/rest/v1/crypto_whale_events?select=usd,alerted&wallet=eq.${wallet}&limit=200`,
      { headers: { apikey: env("SUPABASE_PUBLISHABLE_KEY"),
                   Authorization: `Bearer ${env("SUPABASE_PUBLISHABLE_KEY")}` } });
    if (!r.ok) return null;
    const rows = await r.json();
    if (!rows.length) return "first decoded move we have seen from this wallet";
    const biggest = Math.max(...rows.map(x => Number(x.usd) || 0));
    const alerted = rows.filter(x => x.alerted).length;
    return `${rows.length} prior decoded moves, ${alerted} alerted, biggest ${money(biggest)}`
         + " - win rate not yet computed";
  } catch { return null; }
}

async function postDiscord(rec) {
  const url = env("DISCORD_WEBHOOK_URL");
  if (!url) return null;
  const m = money(rec.usd);
  const where = rec.venue ? ` on ${rec.venue}` : "";
  const track = await walletRecord(rec.wallet);
  const content =
    `**Whale move**\n${shortAddr(rec.wallet)} ${rec.text}${where}` +
    (m ? `\n**${m}**` : "") +
    (track ? `\n_${track}_` : "") +
    (rec.sig ? `\n<https://solscan.io/tx/${rec.sig}>` : "");
  const r = await fetch(`${url}?wait=true`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "User-Agent": "crypto-intel/0.0.1" },
    body: JSON.stringify({ content }),
  });
  if (!r.ok) return null;
  const msg = await r.json().catch(() => ({}));
  return msg.id || null;
}

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ error: "POST only" });

  const expected = env("HELIUS_WEBHOOK_SECRET");
  const got = req.headers.authorization || "";
  if (!expected || got !== expected) return res.status(401).json({ error: "unauthorized" });

  let body = req.body;
  if (typeof body === "string") { try { body = JSON.parse(body); } catch { body = null; } }
  const txs = Array.isArray(body) ? body : (Array.isArray(body?.transactions) ? body.transactions : null);
  if (!txs) return res.status(400).json({ error: "expected an array of transactions" });

  const wallets = watched();
  const out = [];
  for (const tx of txs.slice(0, 40)) {
    // which watched wallet actually did this?
    let actor = null;
    for (const w of wallets) if (isActor(tx, w)) { actor = w; break; }
    if (!actor) { out.push({ sig: tx.signature, skipped: "no watched wallet acted" }); continue; }

    const rec = await describe(tx, actor);
    if (!rec) { out.push({ sig: tx.signature, skipped: "bystander" }); continue; }

    // Do NOT persist noise. These wallets can fire hundreds of undecodable
    // transactions a minute; writing every one would put ~650k rows a day into
    // a database that also holds real data, for zero information.
    const floor = Number(env("WHALE_STORE_USD", "100"));
    if (!rec.known || (rec.usd != null && rec.usd < floor)) {
      out.push({ sig: rec.sig, wallet: shortAddr(actor), skipped: "below store floor",
                 known: rec.known, usd: rec.usd });
      continue;
    }
    const r = await recordEvent(rec);
    let messageId = null;
    if (r.should_alert) messageId = await postDiscord(rec);
    out.push({ sig: rec.sig, wallet: shortAddr(actor), text: rec.text, usd: rec.usd,
               known: rec.known, ...r, messageId });
  }
  return res.status(200).json({ received: txs.length, results: out });
}
