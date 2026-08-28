// crypto-news: poll RSS, dedupe across outlets, alert only on things that matter.
//
// Runs on Supabase, not Vercel and not Frank's desktop. Vercel Hobby cron fires
// once a day, and the desktop sleeps. pg_cron hits this every minute.
//
// No secrets are baked in. SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are
// injected by the platform; the Discord URL and CryptoPanic token live in
// private.crypto_config, which PostgREST does not expose.

const SB_URL = Deno.env.get("SUPABASE_URL")!;
const SB_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

const UA = "crypto-intel/0.1 (personal news aggregator; +https://crypto-intel-one-eta.vercel.app)";

const FEEDS = [
  { outlet: "CoinDesk", url: "https://www.coindesk.com/arc/outboundfeeds/rss/" },
  { outlet: "The Block", url: "https://www.theblock.co/rss.xml" },
  { outlet: "Decrypt", url: "https://decrypt.co/feed" },
  { outlet: "Cointelegraph", url: "https://cointelegraph.com/rss" },
];

// Genuinely major, regardless of which coin it touches.
const MAJOR: { re: RegExp; pts: number; label: string }[] = [
  { re: /\b(hacked?|hack|exploit(ed)?|breach(ed)?|drained?|stolen|theft|attacker)\b/i, pts: 4, label: "Security incident" },
  { re: /\b(rug ?pull|insolven\w+|bankrupt\w*|halts? withdrawals|depeg\w*|collapse[sd]?)\b/i, pts: 4, label: "Solvency event" },
  { re: /\b(sec|cftc|doj|fca|lawsuit|sues|sued|indict\w*|settle(s|d|ment)|subpoena|regulat\w+|sanction\w*|bans?|banned)\b/i, pts: 3, label: "Regulatory" },
  { re: /\b(lists?|listing|delists?|delisting)\b/i, pts: 3, label: "Exchange listing" },
  { re: /\b(outage|downtime|degraded|halted|paused|incident|postmortem|validators? (down|stalled))\b/i, pts: 3, label: "Protocol incident" },
  { re: /\b(approv(es|ed|al))\b/i, pts: 3, label: "Approval" },
];

// Recaps, explainers and price-chat. Never an alert.
const NOISE = /(what happened in crypto|price analysis|technical analysis|here'?s why|here's what|top \d+|weekly recap|market wrap|daily (digest|recap)|price prediction|prediction|what to know|explained|opinion|sponsored|how to)/i;

const STOP = new Set(("the a an and or of for to in on at by with from as is are was were be been will "
  + "its it this that these those new now after before amid over under into out up down more most "
  + "than then but not you your our their his her they them we us can could would should may might").split(" "));

const sb = async (path: string, init: RequestInit = {}) => {
  const r = await fetch(`${SB_URL}/rest/v1/${path}`, {
    ...init,
    headers: {
      apikey: SB_KEY, Authorization: `Bearer ${SB_KEY}`,
      "Content-Type": "application/json", "User-Agent": UA,
      ...(init.headers || {}),
    },
  });
  return r;
};

async function getConfig(): Promise<Record<string, string>> {
  // private.crypto_config is not on the REST surface. read_crypto_config is a
  // SECURITY DEFINER function granted to service_role only, so the anon key
  // that ships in the browser cannot reach any of this.
  const r = await sb("rpc/read_crypto_config", {
    method: "POST", body: JSON.stringify({}),
  });
  if (!r.ok) return {};
  const rows = await r.json();
  const out: Record<string, string> = {};
  for (const row of rows || []) out[row.key] = row.value;
  return out;
}

// ---------- feed parsing ----------
const stripCdata = (s: string) => s.replace(/<!\[CDATA\[|\]\]>/g, "");
const stripTags = (s: string) => s.replace(/<[^>]*>/g, "");
function decodeEntities(s: string) {
  const named: Record<string, string> = {
    "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&apos;": "'",
    "&nbsp;": " ", "&#39;": "'", "&#8217;": "’", "&#8216;": "‘",
    "&#8220;": "“", "&#8221;": "”", "&#8211;": "–", "&#8212;": "—",
  };
  let out = s;
  for (const [k, v] of Object.entries(named)) out = out.split(k).join(v);
  return out.replace(/&#(\d+);/g, (_, d) => String.fromCodePoint(Number(d)));
}
const clean = (s: string) => decodeEntities(stripTags(stripCdata(s))).replace(/\s+/g, " ").trim();

function tagOf(item: string, name: string): string | null {
  const m = item.match(new RegExp(`<${name}[^>]*>([\\s\\S]*?)</${name}>`, "i"));
  return m ? clean(m[1]) : null;
}

function parseFeed(xml: string, outlet: string) {
  const blocks = xml.match(/<item[\s>][\s\S]*?<\/item>/gi) || [];
  const out = [];
  for (const b of blocks) {
    const title = tagOf(b, "title");
    const link = tagOf(b, "link");
    if (!title || !link) continue;
    const pub = tagOf(b, "pubDate");
    const t = pub ? Date.parse(pub) : NaN;
    out.push({
      outlet, title, url: link,
      author: tagOf(b, "dc:creator"),
      category: tagOf(b, "category"),
      published_at: new Date(Number.isFinite(t) ? t : Date.now()).toISOString(),
    });
  }
  return out;
}

// ---------- normalisation / dedupe keys ----------
function urlKey(u: string) {
  try {
    const x = new URL(u);
    return (x.host.replace(/^www\./, "") + x.pathname.replace(/\/+$/, "")).toLowerCase();
  } catch { return u.toLowerCase(); }
}
function tokens(title: string): string[] {
  return [...new Set(
    title.toLowerCase().replace(/[^a-z0-9 ]+/g, " ").split(/\s+/)
      .filter(w => w.length > 2 && !STOP.has(w)),
  )];
}
const titleKey = (title: string) => tokens(title).sort().join(" ");
function jaccard(a: string[], b: string[]) {
  const B = new Set(b);
  let inter = 0;
  for (const x of a) if (B.has(x)) inter++;
  const union = new Set([...a, ...b]).size;
  return union ? inter / union : 0;
}

// Words that appear in half of all crypto headlines. Two stories sharing only
// these are not the same story.
const COMMON = new Set(("bitcoin btc ethereum eth solana sol crypto cryptocurrency token tokens coin coins "
  + "blockchain market markets price prices trading trader traders exchange exchanges network protocol "
  + "million billion trillion users user firm company report says said could would after "
  + "amid launch launches update updates first year years week month day today").split(" "));

const distinctive = (toks: string[], extra?: Set<string>) =>
  toks.filter(t => !COMMON.has(t) && !(extra && extra.has(t)) && !/^[0-9]+$/.test(t));

// ---------- alert worthiness ----------
function assess(title: string, terms: { term: string; weight: number }[]) {
  const t = title.toLowerCase();
  let majorPts = 0; const labels: string[] = [];
  for (const m of MAJOR) if (m.re.test(title)) { majorPts += m.pts; labels.push(m.label); }
  let watchPts = 0; const hits: string[] = [];
  for (const w of terms) {
    const re = new RegExp(`(^|[^a-z0-9])${w.term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}([^a-z0-9]|$)`, "i");
    if (re.test(t)) { watchPts += w.weight; hits.push(w.term); }
  }
  const noisy = NOISE.test(title);
  const score = majorPts + watchPts - (noisy ? 6 : 0);
  // A market recap is not an alert. Something genuinely major must be present;
  // a coin Frank tracks raises it above the bar but cannot clear it alone.
  const alert = majorPts >= 3 && score >= 4;
  const reason = labels.length
    ? labels[0] + (hits.length ? ` · ${hits.slice(0, 2).join(", ")}` : "")
    : null;
  return { score, alert, reason, noisy };
}

// ---------- discord ----------
function fmt(item: any, reason: string | null, alsoIn: string[]) {
  const when = new Date(item.published_at).toUTCString()
    .replace(/^\w+, /, "").replace(" GMT", " UTC").replace(/:\d\d /, " ");
  const also = alsoIn.length ? `\nAlso: ${alsoIn.slice(0, 3).join(", ")}` : "";
  return `**${reason || "Crypto news"}**\n${item.title}\n${item.outlet} · ${when}${also}\n${item.url}`;
}

async function postDiscord(url: string, content: string) {
  const r = await fetch(`${url}?wait=true`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "User-Agent": UA },
    body: JSON.stringify({ content }),
  });
  if (!r.ok) return null;
  const m = await r.json().catch(() => ({}));
  return m?.id ?? null;
}

// ---------- main ----------
Deno.serve(async (req: Request) => {
  const cfg = await getConfig();
  const expected = cfg["cron_secret"];
  const got = req.headers.get("x-cron-secret") || "";
  if (!expected || got !== expected) {
    return new Response(JSON.stringify({ error: "unauthorized" }), {
      status: 401, headers: { "Content-Type": "application/json" },
    });
  }

  const params = new URL(req.url).searchParams;
  const dry = params.get("dry") === "1";
  const forceAlert = params.get("force_alert") === "1";

  // how many rows exist? first run backfills without paging anyone
  const cnt = await sb("crypto_news?select=id&limit=1", { headers: { Prefer: "count=exact" } });
  const range = cnt.headers.get("content-range") || "";
  const existing = Number((range.split("/")[1] ?? "0")) || 0;
  const firstRun = existing === 0;

  const termsRes = await sb("crypto_watch_terms?select=term,weight");
  const terms = termsRes.ok ? await termsRes.json() : [];

  // recent items for the soft (cross-outlet) dedupe
  const since = new Date(Date.now() - 24 * 3600 * 1000).toISOString();
  const recentRes = await sb(
    `crypto_news?select=id,title,title_key,url_key,outlet,also_in,alerted&first_seen=gte.${since}&limit=500`,
  );
  const recent = recentRes.ok ? await recentRes.json() : [];
  const recentTokens = recent.map((r: any) => ({ row: r, toks: (r.title_key || "").split(" ").filter(Boolean) }));
  const seenUrlKeys = new Set(recent.map((r: any) => r.url_key));

  const feedReport: any[] = [];
  const fresh: any[] = [];

  for (const f of FEEDS) {
    const headers: Record<string, string> = { "User-Agent": UA, Accept: "application/rss+xml, application/xml, text/xml" };
    // conditional GET: be a polite client at 60s intervals
    const et = cfg[`etag:${f.outlet}`]; const lm = cfg[`lastmod:${f.outlet}`];
    if (et) headers["If-None-Match"] = et;
    if (lm) headers["If-Modified-Since"] = lm;
    try {
      const r = await fetch(f.url, { headers });
      if (r.status === 304) { feedReport.push({ outlet: f.outlet, status: 304, items: 0 }); continue; }
      if (r.status === 429) { feedReport.push({ outlet: f.outlet, status: 429, note: "rate limited, skipped" }); continue; }
      if (!r.ok) { feedReport.push({ outlet: f.outlet, status: r.status }); continue; }
      const newEt = r.headers.get("etag"); const newLm = r.headers.get("last-modified");
      if (newEt) await sb("rpc/write_crypto_config", { method: "POST", body: JSON.stringify({ p_key: `etag:${f.outlet}`, p_value: newEt }) });
      if (newLm) await sb("rpc/write_crypto_config", { method: "POST", body: JSON.stringify({ p_key: `lastmod:${f.outlet}`, p_value: newLm }) });
      const items = parseFeed(await r.text(), f.outlet);
      feedReport.push({ outlet: f.outlet, status: 200, items: items.length });
      fresh.push(...items);
    } catch (e) {
      feedReport.push({ outlet: f.outlet, error: String(e).slice(0, 100) });
    }
  }

  // CryptoPanic activates the moment a token appears, and stays silent until then.
  const cpToken = (cfg["cryptopanic_token"] || "").trim();
  let cpNote = "no token, skipped";
  if (cpToken) {
    for (const base of ["https://cryptopanic.com/api/developer/v2/posts/", "https://cryptopanic.com/api/v1/posts/"]) {
      try {
        const r = await fetch(`${base}?auth_token=${cpToken}&public=true&currencies=BTC,ETH,SOL`, { headers: { "User-Agent": UA } });
        const txt = await r.text();
        if (!txt.trim().startsWith("{")) continue;
        const d = JSON.parse(txt);
        if (Array.isArray(d?.results)) {
          for (const p of d.results) {
            if (!p.title || !p.url) continue;
            fresh.push({
              outlet: "CryptoPanic", title: p.title, url: p.url, author: null,
              category: p.kind ?? null,
              published_at: new Date(p.published_at || p.created_at || Date.now()).toISOString(),
            });
          }
          cpNote = `ok, ${d.results.length} posts`;
          break;
        }
      } catch { /* try next */ }
    }
    if (cpNote === "no token, skipped") cpNote = "token set but the API did not return JSON";
  }

  // ---------- dedupe + persist ----------
  const inserted: any[] = [];
  const dupes: any[] = [];
  const batchKeys = new Set<string>();
  const batchTokens: { toks: string[]; outlet: string }[] = [];

  fresh.sort((a, b) => Date.parse(b.published_at) - Date.parse(a.published_at));

  for (const it of fresh) {
    const uk = urlKey(it.url);
    if (seenUrlKeys.has(uk) || batchKeys.has(uk)) { dupes.push({ t: it.title, why: "same url" }); continue; }

    const toks = tokens(it.title);
    // same story from another outlet?
    let dupOf: any = null;
    for (const r of recentTokens) if (jaccard(toks, r.toks) >= 0.6) { dupOf = r.row; break; }
    if (!dupOf) for (const b of batchTokens) if (jaccard(toks, b.toks) >= 0.6) { dupOf = { outlet: b.outlet, syntheticBatch: true }; break; }

    if (dupOf) {
      dupes.push({ t: it.title, why: `same story as ${dupOf.outlet}` });
      if (dupOf.id) {
        const also = new Set([...(dupOf.also_in || []), it.outlet]);
        await sb(`crypto_news?id=eq.${dupOf.id}`, {
          method: "PATCH", body: JSON.stringify({ also_in: [...also] }),
        });
      }
      continue;
    }

    const a = assess(it.title, terms);
    batchKeys.add(uk); batchTokens.push({ toks, outlet: it.outlet });
    inserted.push({
      url_key: uk, title_key: toks.sort().join(" "), title: it.title, url: it.url,
      outlet: it.outlet, author: it.author, category: it.category,
      published_at: it.published_at, score: a.score, alert_reason: a.reason,
      alerted: false, _alert: a.alert,
    });
  }

  let stored = 0;
  if (inserted.length && !dry) {
    const rows = inserted.map(({ _alert, ...r }) => r);
    // on_conflict=url_key is load-bearing. Without it PostgREST resolves
    // conflicts against the PRIMARY KEY, which is a generated identity and so
    // never collides, meaning a duplicate url_key escaped as a hard 23505 and
    // failed the WHOLE batch. Cointelegraph republishes its daily recap at a
    // permanent URL, so once that row aged out of the 24h dedupe window it
    // looked new again and silently killed every poll for 30 hours.
    const opts = {
      method: "POST",
      headers: { Prefer: "return=representation,resolution=ignore-duplicates" },
    };
    const r = await sb("crypto_news?on_conflict=url_key", { ...opts, body: JSON.stringify(rows) });
    if (r.ok) {
      stored = (await r.json()).length;
    } else {
      // Belt and braces: never let one poisoned row zero out a whole poll again.
      feedReport.push({ batchInsertError: (await r.text()).slice(0, 200), fallback: "per-row" });
      for (const row of rows) {
        const rr = await sb("crypto_news?on_conflict=url_key", { ...opts, body: JSON.stringify([row]) });
        if (rr.ok) stored += (await rr.json()).length;
      }
    }
  }

  // ---------- alert ----------
  const webhook = cfg["discord_webhook_url"];
  const MAX_PER_RUN = 3;
  const FRESH_MINS = 180;
  const alerts: any[] = [];
  const entitySuppressed: string[] = [];
  const suppressedFirstRun = firstRun ? inserted.filter(i => i._alert).length : 0;
  if ((!firstRun || forceAlert) && webhook && !dry) {
    // One alert per subject per 12 hours. Four outlets covering the same
    // exploit share a distinctive entity ("coldcard", "mantra") even when the
    // headlines are worded so differently that token overlap misses them.
    const since12 = new Date(Date.now() - 12 * 3600 * 1000).toISOString();
    const prevRes = await sb(`crypto_news?select=title_key&alerted=is.true&first_seen=gte.${since12}&limit=200`);
    const prev = prevRes.ok ? await prevRes.json() : [];
    // Words marked weight 0 in crypto_watch_terms are event vocabulary, never a
    // subject. Tuning this is a SQL update, not a redeploy.
    const noEntity = new Set<string>(
      terms.filter((t: any) => Number(t.weight) === 0).map((t: any) => String(t.term).toLowerCase()),
    );
    const spent = new Set<string>();
    for (const pr of prev) for (const d of distinctive((pr.title_key || "").split(" ").filter(Boolean), noEntity)) spent.add(d);

    const candidates = inserted
      .filter(i => i._alert)
      .filter(i => forceAlert || Date.now() - Date.parse(i.published_at) < FRESH_MINS * 60000)
      .sort((a, b) => b.score - a.score);
    const chosen: any[] = [];
    for (const c of candidates) {
      const ents = distinctive(c.title_key.split(" ").filter(Boolean), noEntity);
      const clash = ents.find(e => spent.has(e));
      if (clash) { entitySuppressed.push(`${c.title} :: already alerted on "${clash}"`); continue; }
      for (const e of ents) spent.add(e);
      chosen.push(c);
      if (chosen.length >= MAX_PER_RUN) break;
    }
    for (const c of chosen) {
      const id = await postDiscord(webhook, fmt(c, c.alert_reason, []));
      if (id) {
        await sb(`crypto_news?url_key=eq.${encodeURIComponent(c.url_key)}`, {
          method: "PATCH", body: JSON.stringify({ alerted: true }),
        });
        alerts.push({ title: c.title, reason: c.alert_reason, score: c.score, messageId: id });
      }
    }
  }

  return new Response(JSON.stringify({
    firstRun, backfillNotAlerted: suppressedFirstRun,
    feeds: feedReport, cryptopanic: cpNote,
    seen: fresh.length, newAfterDedupe: inserted.length, stored,
    duplicatesSuppressed: dupes.length,
    duplicateExamples: dupes.slice(0, 6),
    entitySuppressed,
    alertsSent: alerts,
    wouldAlert: inserted.filter(i => i._alert).map(i => ({ t: i.title, r: i.alert_reason, s: i.score })),
  }, null, 1), { headers: { "Content-Type": "application/json" } });
});
