"""Build the one file Frank opens on his phone.

Self-contained: no network, no CDN, no fonts, no build step. Open it anywhere.

It follows the project's own rendering rules, because a page that breaks them is
how five separate failures happened:
  - ⛔ an absent measurement renders as "unknown", NEVER as 0 or blank (rule 5)
  - ⛔ a symbol goes through safe_sym, which strips bidi controls but LEAVES A
    MARK, because a silently cleaned symbol is the same deception with our
    fingerprints on it (rule 2, docs/SYMBOL_ATTACKS.md)
  - ⛔ nothing is sorted by anything readable as a quality ordering by default;
    the default sort is recency (Marino, and dashboard.py enforces the same)
  - ⭐ the "what it does" line is the headline, because that is the field Frank
    asked for and the one no on-chain source has
"""
import html
import io
import json
import os
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
BIDI = {0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x2066, 0x2067, 0x2068, 0x2069,
        0x200F, 0x200E}


def script_of(ch):
    if not ch.isalpha():
        return None
    try:
        return unicodedata.name(ch).split()[0]
    except ValueError:
        return None


def safe_sym(sym):
    raw = str(sym or "")
    if not raw:
        return "unknown", []
    stripped = "".join(c for c in raw if ord(c) not in BIDI)
    flags = []
    if len(stripped) != len(raw):
        flags.append("BIDI")
    scripts = {s for s in (script_of(c) for c in stripped) if s}
    if len(scripts) > 1:
        flags.append("MIXED:" + "+".join(sorted(scripts)))
    return (stripped[:22] or "unknown"), flags


def main():
    rows = json.load(io.open(os.path.join(HERE, "dataset_allpairs.json"), encoding="utf-8"))
    try:
        stats = json.load(io.open(os.path.join(HERE, "hitrate.json"), encoding="utf-8"))
    except Exception:
        stats = {}

    slim = []
    for r in rows:
        sym, flags = safe_sym(r["ticker"])
        slim.append({
            "t": sym, "fl": flags, "ch": r.get("chain"), "a": r.get("address"),
            "nm": r.get("token_name"),
            "w": r.get("what_it_does"), "wd": r.get("what_it_does_date"),
            "wq": r.get("what_it_does_quality"),
            "c": r.get("category"), "cs": r.get("categories") or [],
            "fs": r.get("first_seen"), "ls": r.get("last_seen"),
            "n": r.get("n_mentions"),
            "f": r.get("first_reported_mcap"), "p": r.get("peak_reported_mcap"),
            "tr": r.get("reported_trajectory") or [],
            "m": r.get("all_mentions") or [],
            # ⛔ ALL PAIRS from 2026-09-23 (standing rule 18). `cl` used to be one
            # pool's liquidity; on 75 of 435 rows that understated by >= 1.5x and
            # on GP by 4.60x. `fl_` is true when the 30-pair API cap was hit, in
            # which case the figure is a FLOOR - SOL also returns 30.
            "cm": r.get("mcap_all_pairs_usd") or r.get("current_mcap_usd"),
            "cl": (r.get("liq_all_pairs_usd") if r.get("liq_all_pairs_usd") is not None
                   else r.get("current_liquidity_usd")),
            "clf": bool(r.get("liq_is_floor")),
            "np": r.get("pair_count"),
            "dp": r.get("deepest_pool_liq_usd"),
            "ux": r.get("single_pair_understates_by"),
            "qa": r.get("quote_assets") or {},
            "vs": r.get("verified_status"), "vw": r.get("verified_why"),
            "ni": r.get("n_impersonators"), "imp": r.get("impersonators") or [],
            "cv": r.get("vol24_all_pairs_usd") or r.get("current_vol24_usd"),
            "h": r.get("holders"),
            "o": r.get("outcome"), "ow": r.get("outcome_why"),
            "rc": r.get("resolution_confidence"), "rn": r.get("resolution_note"),
            "nc": r.get("n_candidates"), "lp": r.get("launchpad"),
            "mu": r.get("mult_vs_first_reported"),
        })

    payload = html.escape(json.dumps(slim, ensure_ascii=False), quote=False)
    statj = html.escape(json.dumps(stats, ensure_ascii=False), quote=False)

    doc = TEMPLATE.replace("__DATA__", payload).replace("__STATS__", statj)
    out = os.path.join(HERE, "gorilla_universe.html")
    io.open(out, "w", encoding="utf-8").write(doc)
    print("wrote", out, f"{len(doc)/1024:.0f} KB, {len(slim)} rows")


TEMPLATE = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Gorilla Archive</title>
<style>
:root{
  --bg:#0d1117; --panel:#161b22; --line:#30363d; --fg:#e6edf3; --dim:#8b949e;
  --alive:#3fb950; --faded:#d29922; --rugged:#f85149; --unres:#6e7681;
  --accent:#58a6ff;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
 font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
 padding:0 16px 64px;-webkit-text-size-adjust:100%}
header{position:sticky;top:0;background:var(--bg);padding:14px 0 10px;z-index:5;
 border-bottom:1px solid var(--line)}
h1{font-size:19px;margin:0 0 2px}
.sub{color:var(--dim);font-size:12px;margin-bottom:10px}
.warn{background:#3d1d1d;border:1px solid #6b2b2b;border-radius:8px;padding:10px 12px;
 font-size:12.5px;color:#ffc9c9;margin:10px 0}
input[type=search]{width:100%;padding:10px 12px;border-radius:8px;border:1px solid var(--line);
 background:var(--panel);color:var(--fg);font-size:16px;margin-bottom:8px}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px}
.chip{border:1px solid var(--line);background:var(--panel);color:var(--dim);
 padding:5px 10px;border-radius:999px;font-size:12px;cursor:pointer;user-select:none}
.chip.on{background:var(--accent);color:#04121f;border-color:var(--accent);font-weight:600}
.chip.o-alive.on{background:var(--alive);border-color:var(--alive)}
.chip.o-faded.on{background:var(--faded);border-color:var(--faded)}
.chip.o-rugged.on{background:var(--rugged);border-color:var(--rugged)}
.chip.o-unresolved.on{background:var(--unres);border-color:var(--unres);color:#fff}
.chip.o-unverifiable.on{background:#6b2b2b;border-color:#6b2b2b;color:#ffc9c9}
select{background:var(--panel);color:var(--fg);border:1px solid var(--line);
 border-radius:8px;padding:8px;font-size:14px}
.count{color:var(--dim);font-size:12px;margin:8px 0}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;
 padding:12px;margin-bottom:10px}
.top{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}
.tk{font-weight:700;font-size:17px}
.badge{font-size:10.5px;padding:2px 7px;border-radius:999px;border:1px solid var(--line);
 color:var(--dim);white-space:nowrap}
.b-alive{color:var(--alive);border-color:var(--alive)}
.b-faded{color:var(--faded);border-color:var(--faded)}
.b-rugged{color:var(--rugged);border-color:var(--rugged)}
.b-unresolved{color:var(--unres);border-color:var(--unres)}
.b-unverifiable{color:#ffb4b4;border-color:#6b2b2b}
.b-cat{color:var(--accent);border-color:var(--accent)}
.b-bad{color:#ffb4b4;border-color:#6b2b2b;background:#3d1d1d}
.what{margin:9px 0 6px;font-size:14.5px}
.what .d{color:var(--dim);font-size:11.5px;display:block;margin-top:3px}
.arc{display:flex;align-items:center;gap:8px;flex-wrap:wrap;font-size:12px;
 color:var(--dim);margin:8px 0}
.arc b{color:var(--fg);font-weight:600}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(104px,1fr));gap:6px 10px;
 font-size:12px;color:var(--dim);margin-top:8px;border-top:1px solid var(--line);padding-top:8px}
.grid div b{display:block;color:var(--fg);font-size:13px;font-weight:600}
.addr{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11px;
 color:var(--dim);word-break:break-all;margin-top:8px;cursor:pointer}
.addr:active{color:var(--accent)}
details{margin-top:8px}
summary{cursor:pointer;color:var(--accent);font-size:12.5px}
details p{font-size:12.5px;color:var(--dim);margin:6px 0 0;border-left:2px solid var(--line);
 padding-left:9px}
details p b{color:var(--fg)}
svg.spark{vertical-align:middle}
.stats{background:var(--panel);border:1px solid var(--line);border-radius:10px;
 padding:12px;margin:10px 0;font-size:13px}
.stats table{width:100%;border-collapse:collapse;font-size:12.5px;margin-top:6px}
.stats td{padding:3px 0;color:var(--dim)}
.stats td:last-child{text-align:right;color:var(--fg);font-variant-numeric:tabular-nums}
@media(min-width:760px){body{max-width:1000px;margin:0 auto}}
</style></head><body>
<header>
  <h1>Gorilla Archive</h1>
  <div class="sub">49 daily recaps, 2026-08-04 to 2026-09-21. <span id="n"></span></div>
  <input type="search" id="q" placeholder="search ticker, description, address">
  <div class="chips" id="cats"></div>
  <div class="chips" id="outs"></div>
  <select id="sort">
    <option value="fs">newest call first</option>
    <option value="fso">oldest call first</option>
    <option value="n">most mentioned</option>
    <option value="p">biggest reported peak</option>
    <option value="cm">biggest today</option>
  </select>
</header>

<div class="warn">
  <b>Read this before you use any number on this page.</b>
  <br><br>
  <b>1. These are a third party's claims, dated, not our measurement.</b> Every
  mcap figure is what Gorilla said on the day he said it. We quoted him verbatim
  and checked nothing about the figures themselves.
  <br><br>
  <b>2. The contract may not be the one he meant.</b> He posts tickers, not
  addresses, and 437 of these tickers are worn by more than one live token &mdash;
  <b>1,874 impersonators are named on the cards below</b>. The services that turn a
  ticker into an address preferentially list tokens that still have liquidity, so a
  token that died tends to be invisible to them and the ticker resolves to whatever
  living namesake carries that symbol now. Measured strength of that effect:
  <b>86.4% [73.3, 93.6] of 44 index-absent tokens failed a live $100 round trip</b>.
  Rows marked <b>contract uncertain</b> are the ones we refuse to score at all.
  <br><br>
  <b>2b. Correction, 23 Sept: this page previously cited EMBER as proof that the
  lookup picks the wrong contract. That was backwards and is withdrawn.</b> The
  resolver was right. It chose <code>5dvXTZ5q&hellip;</code>, which holds
  <b>$2.33m across 30 pools</b> and sells $2,000 at 1.30% &mdash; and its first pool
  predates Gorilla's mention by a day. The contract analysed by hand instead,
  <code>FLCr9vGM&hellip;</code>, is a <b>phantom</b>: 3 pools, <b>$1.39</b> of total
  liquidity behind a <b>$1.31 billion</b> claimed cap, first pool twelve days
  <i>after</i> the mention. A hand-check on chain is not automatically better than
  a rule; it can be on chain on the wrong account.
  <br><br>
  <b>3. So the alive / faded badges describe the token carrying that ticker today,
  not the outcome of his call.</b> They are not a track record and there is no hit
  rate on this page, because one cannot honestly be computed from tickers.
  <br><br>
  <b>4. Liquidity shown is the listings' reported field</b>, which we have measured
  overstating by a median 781x. It is a coarse alive-or-dead split and <b>not an
  exit price</b>. Nothing here is a recommendation to buy anything.
  <br><br>
  <b>5. Liquidity is now summed across EVERY pool for the mint, not read from one.</b>
  Reading one pool on a token that trades across thirty is a 3% sample reported as
  the whole; it understated 75 of 435 rows here by 1.5x or more, and GP by 4.60x.
  <b>A figure marked &ldquo;floor&rdquo; hit the 30-pool API cap</b> &mdash; SOL
  returns 30 too, so 30 means &ldquo;30 or more&rdquo; and the real total is higher.
</div>

<div class="stats" id="stats"></div>
<div class="count" id="count"></div>
<div id="list"></div>

<script id="data" type="application/json">__DATA__</script>
<script id="stat" type="application/json">__STATS__</script>
<script>
const D = JSON.parse(document.getElementById('data').textContent);
const S = JSON.parse(document.getElementById('stat').textContent);
const CATS = [...new Set(D.map(r=>r.c))].sort();
const OUTS = ['alive','faded','rugged','unverifiable','unresolved'];
const selC = new Set(), selO = new Set();

// ⛔ unknown is "unknown". Never 0, never blank. (standing rule 5)
function usd(v){
  if (v===null||v===undefined||v==='') return '<i style="opacity:.6">unknown</i>';
  const n = Number(v); if (!isFinite(n)) return '<i style="opacity:.6">unknown</i>';
  if (n>=1e9) return '$'+(n/1e9).toFixed(2)+'b';
  if (n>=1e6) return '$'+(n/1e6).toFixed(2)+'m';
  if (n>=1e3) return '$'+(n/1e3).toFixed(1)+'k';
  return '$'+n.toFixed(2);
}
function num(v){
  if (v===null||v===undefined) return '<i style="opacity:.6">unknown</i>';
  return Number(v).toLocaleString();
}
function esc(s){const d=document.createElement('div');d.textContent=s==null?'':s;return d.innerHTML}

function spark(tr){
  if (!tr || tr.length<2) return '';
  const v = tr.map(x=>x.mcap), mx=Math.max(...v), mn=Math.min(...v);
  const W=90,H=22, span=(mx-mn)||1;
  const pts = v.map((y,i)=>[ (i/(v.length-1))*W, H-((y-mn)/span)*(H-3)-1.5 ]);
  const up = v[v.length-1] >= v[0];
  return '<svg class="spark" width="'+W+'" height="'+H+'" viewBox="0 0 '+W+' '+H+'">'+
    '<polyline fill="none" stroke="'+(up?'#3fb950':'#f85149')+'" stroke-width="1.6" points="'+
    pts.map(p=>p[0].toFixed(1)+','+p[1].toFixed(1)).join(' ')+'"/></svg>';
}

function card(r){
  const flags = (r.fl||[]).map(f=>'<span class="badge b-bad">&#9940; '+esc(f)+'</span>').join('');
  const lowres = (r.rc==='LOW'||r.rc==='NONE')
    ? '<span class="badge b-bad" title="'+esc(r.rn||'')+'">contract uncertain: '+esc(r.rc)+
      (r.nc?(' of '+r.nc+' candidates'):'')+'</span>' : '';
  const arc = (r.tr&&r.tr.length)
    ? r.tr.map(x=>'<b>'+usd(x.mcap)+'</b> <span>'+esc((x.date||'').slice(5))+'</span>').join(' &rarr; ')
    : '<i style="opacity:.6">no figure quoted</i>';
  const hist = (r.m||[]).map(m=>'<p><b>'+esc(m.date)+'</b> &mdash; '+esc(m.text)+'</p>').join('');
  const qual = r.wq==='list'
    ? ' <span class="badge b-bad" title="this bullet listed several tokens, so it is a mention, not an explanation">mention only</span>'
    : (r.wq==='thin' ? ' <span class="badge">thin</span>' : '');
  return '<div class="card">'+
    '<div class="top"><span class="tk">'+esc(r.t)+'</span>'+
      '<span class="badge b-cat">'+esc(r.c)+'</span>'+
      '<span class="badge b-'+r.o+'">'+r.o+'</span>'+
      (r.ch?'<span class="badge">'+esc(r.ch)+'</span>':'')+
      (r.lp?'<span class="badge">'+esc(r.lp)+'</span>':'')+
      flags+lowres+
    '</div>'+
    '<div class="what">'+esc(r.w)+qual+
      '<span class="d">Gorilla, '+esc(r.wd||'undated')+
      (r.nm?(' &middot; '+esc(r.nm)):'')+'</span></div>'+
    '<div class="arc">'+spark(r.tr)+' '+arc+'</div>'+
    '<div class="grid">'+
      '<div>mcap today<b>'+usd(r.cm)+'</b></div>'+
      '<div>liq, ALL pools<b>'+usd(r.cl)+(r.clf?' <span style="opacity:.65;font-weight:400">floor</span>':'')+'</b></div>'+
      '<div>24h volume<b>'+usd(r.cv)+'</b></div>'+
      '<div>pools<b>'+(r.np==null?'?':r.np)+(r.clf?'+':'')+'</b></div>'+
      '<div>holders<b>'+num(r.h)+'</b></div>'+
      '<div>called<b>'+esc(r.fs)+'</b></div>'+
      '<div>mentions<b>'+r.n+'</b></div>'+
      '<div>same ticker<b>'+((r.ni||0)?((r.ni)+' other'+(r.ni>1?'s':'')):'unique')+'</b></div>'+
    '</div>'+
    (r.ux&&r.ux>=1.5?('<div class="d" style="margin-top:4px">&#9888; reading one pool would have shown '+usd(r.dp)+', '+r.ux+'x too low</div>'):'')+
    (r.qa&&Object.keys(r.qa).length>1?('<div class="d" style="margin-top:4px">paired against '+Object.keys(r.qa).slice(0,5).map(k=>esc(k)+' '+usd(r.qa[k])).join(' &middot; ')+'</div>'):'')+
    ((r.imp&&r.imp.length)?('<details><summary>'+r.imp.length+' other token'+(r.imp.length>1?'s':'')+' wearing $'+esc(r.t)+'</summary><div class="d">'+r.imp.map(x=>esc((x&&(x.chain||x.ch))||'?')+' '+esc((x&&(x.address||x.a))||JSON.stringify(x))).join('<br>')+'</div></details>'):'')+
    (r.a?'<div class="addr" onclick="navigator.clipboard&&navigator.clipboard.writeText(this.dataset.a)" data-a="'+esc(r.a)+'">'+esc(r.a)+' <span style="opacity:.6">(tap to copy)</span></div>':
         '<div class="addr"><i>no contract resolved</i></div>')+
    (hist?('<details><summary>every mention ('+(r.m||[]).length+')</summary>'+hist+'</details>'):'');
}

function render(){
  const q = document.getElementById('q').value.trim().toLowerCase();
  let rows = D.filter(r=>{
    if (selC.size && !selC.has(r.c)) return false;
    if (selO.size && !selO.has(r.o)) return false;
    if (q){
      const hay = (r.t+' '+(r.w||'')+' '+(r.a||'')+' '+(r.nm||'')).toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
  const s = document.getElementById('sort').value;
  const by = {
    fs:(a,b)=>(b.fs||'').localeCompare(a.fs||''),
    fso:(a,b)=>(a.fs||'').localeCompare(b.fs||''),
    n:(a,b)=>b.n-a.n,
    p:(a,b)=>(b.p||0)-(a.p||0),
    cm:(a,b)=>(b.cm||0)-(a.cm||0),
  }[s];
  rows.sort(by);
  document.getElementById('count').textContent = rows.length+' of '+D.length+' tokens';
  document.getElementById('list').innerHTML = rows.map(card).join('');
}

function chips(el, items, set, cls){
  el.innerHTML = items.map(i=>'<span class="chip '+(cls||'')+(cls?(' '+cls+i):'')+'" data-v="'+i+'">'+i+'</span>').join('');
  el.querySelectorAll('.chip').forEach(c=>c.onclick=()=>{
    const v=c.dataset.v;
    if(set.has(v)){set.delete(v);c.classList.remove('on')}else{set.add(v);c.classList.add('on')}
    render();
  });
}
chips(document.getElementById('cats'), CATS, selC, '');
chips(document.getElementById('outs'), OUTS, selO, 'o-');
document.getElementById('q').oninput = render;
document.getElementById('sort').onchange = render;
document.getElementById('n').textContent = D.length+' tokens he called.';

if (S && S.arms){
  let h = '<b>What can and cannot be measured here</b><table>';
  for (const a of S.arms){
    h += '<tr><td>'+esc(a.label)+'</td><td>'+esc(a.value)+'</td></tr>';
  }
  h += '</table>';
  if (S.note) h += '<div style="color:var(--dim);font-size:11.5px;margin-top:8px">'+esc(S.note)+'</div>';
  document.getElementById('stats').innerHTML = h;
} else { document.getElementById('stats').style.display='none'; }
render();
</script>
</body></html>
"""

if __name__ == "__main__":
    main()
