-- =====================================================================
-- crypto-intel 002: the LIVE store the site reads (milestone 1, 2026-09-19)
--
-- Project: rxofejxostyqlgjlzqmk (crypto). ⛔ Never apply to any other project.
--
-- Same pattern as 001, deliberately:
--   * writes ONLY through one secret-gated SECURITY DEFINER function,
--     live_publish(), callable by anon with the 'live' secret;
--   * reads ONLY on the four tables below, which hold nothing the public site
--     does not already publish. Nothing else in the project gains a grant.
--
-- These tables are a CACHE of the latest state, upserted, never the record.
-- The append-only record stays where it is (data/ in git, every pass), so
-- "nothing is ever deleted" holds: nothing here deletes, and nothing here is
-- the only copy. ~5,000 rows in total; far inside the free tier's 500 MB.
--
-- The 'live' secret is NOT in this file. It is inserted at apply time from
-- CRYPTO_LIVE_SECRET (never printed, never committed).
-- =====================================================================

-- One row per tracked token: membership, the gate, the safety verdict.
create table if not exists public.live_tokens (
  mint               text primary key,
  symbol             text,
  name               text,
  class              text,
  status             text not null,                 -- member | refused | candidate
  gate_verdict       text,
  gate_cost_pct      numeric,
  gate_at            timestamptz,
  safety_level       text,                          -- DANGER | WARN | NO FLAGS | UNKNOWN
  safety_reasons     jsonb,
  safety_not_checked jsonb,
  safety_rule        text,
  safety_at          timestamptz,
  ticker_contracts   int,
  from_graduation    boolean,
  trending           jsonb,
  first_seen_at      timestamptz,
  admitted_at        timestamptz,
  below_floor_since  timestamptz,
  failing_since      timestamptz,
  updated_at         timestamptz not null default now(),
  updated_by         text not null                  -- the path that wrote it
);

-- The latest market reading of each token, PER PATH. Two paths that disagree
-- is a data-quality signal we never had, so both readings are kept side by side.
create table if not exists public.live_ticks (
  path             text not null,
  mint             text not null,
  price_usd        numeric,
  mcap_usd         numeric,
  fdv_usd          numeric,
  liquidity_usd    numeric,
  cap_backing_pct  numeric,
  change_5m        numeric,
  change_1h        numeric,
  change_6h        numeric,
  change_24h       numeric,
  volume_1h        numeric,
  volume_24h       numeric,
  buys_h1          int,
  sells_h1         int,
  d1               boolean,
  source           text,
  observed_at      timestamptz not null,
  primary key (path, mint)
);
create index if not exists live_ticks_mint_idx on public.live_ticks (mint, observed_at desc);

-- Trending lists as each path last saw them. A shrinking list leaves old ranks
-- behind; readers keep only rows at the newest observed_at per (path, list).
create table if not exists public.live_trending (
  path         text not null,
  list         text not null,
  rank         int  not null,
  mint         text not null,
  symbol       text,
  paid         boolean not null default false,
  observed_at  timestamptz not null,
  primary key (path, list, rank)
);

-- ⭐ Every collection path, alive or not. The page renders this, so a silent
-- death is impossible: a path that stops writing ages here in plain sight.
create table if not exists public.live_paths (
  path             text primary key,
  host             text,
  kind             text,
  interval_s       int,
  last_ok_at       timestamptz,
  last_attempt_at  timestamptz,
  last_error       text,
  last_error_at    timestamptz,
  rows_last        int,
  detail           jsonb
);

alter table public.live_tokens   enable row level security;
alter table public.live_ticks    enable row level security;
alter table public.live_trending enable row level security;
alter table public.live_paths    enable row level security;

drop policy if exists "live_tokens public read"   on public.live_tokens;
drop policy if exists "live_ticks public read"    on public.live_ticks;
drop policy if exists "live_trending public read" on public.live_trending;
drop policy if exists "live_paths public read"    on public.live_paths;
create policy "live_tokens public read"   on public.live_tokens   for select to anon, authenticated using (true);
create policy "live_ticks public read"    on public.live_ticks    for select to anon, authenticated using (true);
create policy "live_trending public read" on public.live_trending for select to anon, authenticated using (true);
create policy "live_paths public read"    on public.live_paths    for select to anon, authenticated using (true);

-- --------------------------------------------------------------- the writer
-- payload: {"host","kind","interval_s","detail",
--           "tokens":[...], "ticks":[...], "trending":{"<list>":[...]}, "error"}
-- A token's safety verdict is only replaced by a NEWER one, so a slow path
-- can never overwrite a fresher verdict written by a fast one.
create or replace function public.live_publish(p_secret text, p_path text, p_payload jsonb)
returns jsonb
language plpgsql security definer set search_path = public, private
as $$
declare
  v_now timestamptz := now();
  v_tokens int := 0; v_ticks int := 0; v_trend int := 0;
  v_list text; v_rows jsonb;
begin
  perform private.check_secret('live', p_secret);
  if p_path is null or length(p_path) > 40 then
    raise exception 'bad path' using errcode = '22023';
  end if;

  if p_payload ? 'tokens' then
    insert into public.live_tokens as t
      (mint, symbol, name, class, status, gate_verdict, gate_cost_pct, gate_at,
       safety_level, safety_reasons, safety_not_checked, safety_rule, safety_at,
       ticker_contracts, from_graduation, trending, first_seen_at, admitted_at,
       below_floor_since, failing_since, updated_at, updated_by)
    select x.mint, x.symbol, x.name, x.class, x.status, x.gate_verdict, x.gate_cost_pct, x.gate_at,
           x.safety_level, x.safety_reasons, x.safety_not_checked, x.safety_rule, x.safety_at,
           x.ticker_contracts, x.from_graduation, x.trending, x.first_seen_at, x.admitted_at,
           x.below_floor_since, x.failing_since, v_now, p_path
    from jsonb_to_recordset(p_payload->'tokens') as x(
      mint text, symbol text, name text, class text, status text, gate_verdict text,
      gate_cost_pct numeric, gate_at timestamptz, safety_level text, safety_reasons jsonb,
      safety_not_checked jsonb, safety_rule text, safety_at timestamptz, ticker_contracts int,
      from_graduation boolean, trending jsonb, first_seen_at timestamptz, admitted_at timestamptz,
      below_floor_since timestamptz, failing_since timestamptz)
    where x.mint is not null and x.status is not null
    on conflict (mint) do update set
      symbol = excluded.symbol, name = excluded.name, class = excluded.class,
      status = excluded.status, gate_verdict = excluded.gate_verdict,
      gate_cost_pct = excluded.gate_cost_pct, gate_at = excluded.gate_at,
      safety_level       = case when excluded.safety_at >= coalesce(t.safety_at, '-infinity') then excluded.safety_level       else t.safety_level end,
      safety_reasons     = case when excluded.safety_at >= coalesce(t.safety_at, '-infinity') then excluded.safety_reasons     else t.safety_reasons end,
      safety_not_checked = case when excluded.safety_at >= coalesce(t.safety_at, '-infinity') then excluded.safety_not_checked else t.safety_not_checked end,
      safety_rule        = case when excluded.safety_at >= coalesce(t.safety_at, '-infinity') then excluded.safety_rule        else t.safety_rule end,
      safety_at          = greatest(excluded.safety_at, t.safety_at),
      ticker_contracts = excluded.ticker_contracts, from_graduation = excluded.from_graduation,
      trending = excluded.trending, first_seen_at = excluded.first_seen_at,
      admitted_at = excluded.admitted_at, below_floor_since = excluded.below_floor_since,
      failing_since = excluded.failing_since, updated_at = v_now, updated_by = p_path;
    get diagnostics v_tokens = row_count;
  end if;

  if p_payload ? 'ticks' then
    insert into public.live_ticks as k
      (path, mint, price_usd, mcap_usd, fdv_usd, liquidity_usd, cap_backing_pct,
       change_5m, change_1h, change_6h, change_24h, volume_1h, volume_24h,
       buys_h1, sells_h1, d1, source, observed_at)
    select p_path, x.mint, x.price_usd, x.mcap_usd, x.fdv_usd, x.liquidity_usd, x.cap_backing_pct,
           x.change_5m, x.change_1h, x.change_6h, x.change_24h, x.volume_1h, x.volume_24h,
           x.buys_h1, x.sells_h1, x.d1, x.source, coalesce(x.observed_at, v_now)
    from jsonb_to_recordset(p_payload->'ticks') as x(
      mint text, price_usd numeric, mcap_usd numeric, fdv_usd numeric, liquidity_usd numeric,
      cap_backing_pct numeric, change_5m numeric, change_1h numeric, change_6h numeric,
      change_24h numeric, volume_1h numeric, volume_24h numeric, buys_h1 int, sells_h1 int,
      d1 boolean, source text, observed_at timestamptz)
    where x.mint is not null
    on conflict (path, mint) do update set
      price_usd = excluded.price_usd, mcap_usd = excluded.mcap_usd, fdv_usd = excluded.fdv_usd,
      liquidity_usd = excluded.liquidity_usd, cap_backing_pct = excluded.cap_backing_pct,
      change_5m = excluded.change_5m, change_1h = excluded.change_1h, change_6h = excluded.change_6h,
      change_24h = excluded.change_24h, volume_1h = excluded.volume_1h, volume_24h = excluded.volume_24h,
      -- a tick without pair data must not erase the last D1 reading
      buys_h1 = coalesce(excluded.buys_h1, k.buys_h1), sells_h1 = coalesce(excluded.sells_h1, k.sells_h1),
      d1 = coalesce(excluded.d1, k.d1), source = excluded.source, observed_at = excluded.observed_at
    where excluded.observed_at >= k.observed_at;
    get diagnostics v_ticks = row_count;
  end if;

  if p_payload ? 'trending' then
    for v_list, v_rows in select * from jsonb_each(p_payload->'trending') loop
      insert into public.live_trending as r (path, list, rank, mint, symbol, paid, observed_at)
      select p_path, v_list, x.rank, x.mint, x.symbol, coalesce(x.paid, false), v_now
      from jsonb_to_recordset(v_rows) as x(rank int, mint text, symbol text, paid boolean)
      where x.mint is not null and x.rank is not null
      on conflict (path, list, rank) do update set
        mint = excluded.mint, symbol = excluded.symbol, paid = excluded.paid, observed_at = excluded.observed_at;
      v_trend := v_trend + (select count(*) from jsonb_array_elements(v_rows));
    end loop;
  end if;

  insert into public.live_paths as p
    (path, host, kind, interval_s, last_ok_at, last_attempt_at, last_error, last_error_at, rows_last, detail)
  values (p_path, p_payload->>'host', p_payload->>'kind', (p_payload->>'interval_s')::int,
          case when p_payload ? 'error' then null else v_now end, v_now,
          p_payload->>'error', case when p_payload ? 'error' then v_now else null end,
          v_tokens + v_ticks + v_trend, p_payload->'detail')
  on conflict (path) do update set
    host = excluded.host, kind = excluded.kind, interval_s = excluded.interval_s,
    last_ok_at = coalesce(excluded.last_ok_at, p.last_ok_at), last_attempt_at = v_now,
    last_error = coalesce(excluded.last_error, p.last_error),
    last_error_at = coalesce(excluded.last_error_at, p.last_error_at),
    rows_last = excluded.rows_last, detail = excluded.detail;

  return jsonb_build_object('tokens', v_tokens, 'ticks', v_ticks, 'trending', v_trend, 'at', v_now);
end;
$$;

revoke all on function public.live_publish(text, text, jsonb) from public;
grant execute on function public.live_publish(text, text, jsonb) to anon;

grant select on public.live_tokens, public.live_ticks, public.live_trending, public.live_paths
  to anon, authenticated;
