-- ============================================================================
-- Live pool events from Helius, received by the helius-events edge function.
--
-- WHY THIS EXISTS: the decoy EMBER's creator withdrew 2,907.565 SOL and burned
-- the LP at 11:09:37Z on 2026-09-22, and our 24h outcome check ran at 11:12:10Z,
-- two minutes and thirty-three seconds too late. Three of our confirmed deaths
-- (USDCAT, OWL, X7) are the same single event: one Withdraw, last on the pool.
--
-- This runs on Supabase, not on Frank's desktop, which is the entire point: his
-- machine is on most of the time but not always, and the desktop collector has
-- already died silently for four days when a reboot lost its drive mount.
--
-- Applied 2026-09-23 as three migrations: chain_events_receiver,
-- chain_events_grants, chain_watch_sync_rpc. Recorded here as one file.
-- ============================================================================

create table if not exists public.chain_events (
  id               bigserial primary key,
  received_at      timestamptz not null default now(),
  signature        text not null,
  slot             bigint,
  block_time       timestamptz,
  tx_type          text,
  source           text,
  description      text,
  fee_payer        text,
  watched          text[],          -- which of OUR addresses this touched
  native_transfers jsonb,
  token_transfers  jsonb,
  account_data     jsonb,
  classification   text,            -- what WE decided this is
  raw              jsonb,
  constraint chain_events_sig_uniq unique (signature)
);

create index if not exists chain_events_block_time_idx
  on public.chain_events (block_time desc);
create index if not exists chain_events_class_idx
  on public.chain_events (classification, block_time desc);
create index if not exists chain_events_watched_idx
  on public.chain_events using gin (watched);

comment on table public.chain_events is
  'Live Helius webhook events on watched AMM pools. Written by the helius-events edge function. Append-only: nothing here is ever updated or deleted (standing rule 8).';
comment on column public.chain_events.classification is
  'POOL_CREATE / LIQUIDITY_ADD / LIQUIDITY_REMOVE / LARGE_TRANSFER / SWAP / OTHER. Derived by the receiver from the Helius type plus the transfer directions. OTHER is honest: it means we saw it and did not recognise it, never that nothing happened.';
comment on column public.chain_events.watched is
  'Which of our registered addresses appear in this transaction. NULL means the watchlist could not be read, which is not the same as an empty match. Empty means Helius delivered something we did not ask for, which is itself worth seeing.';

-- The anon key can read but never write. Writes come only from the edge
-- function, which uses the service role and never leaves the server.
alter table public.chain_events enable row level security;
drop policy if exists chain_events_read on public.chain_events;
create policy chain_events_read on public.chain_events for select using (true);

-- A registry of what we are watching and why, so the address list is not
-- knowledge that lives only inside a Helius dashboard.
create table if not exists public.chain_watch (
  address      text primary key,
  kind         text not null,       -- pool | program | wallet | mint
  label        text,
  mint         text,
  dex          text,
  liq_usd_at_registration numeric,
  webhook_id   text,
  registered_at timestamptz not null default now(),
  active       boolean not null default true
);
alter table public.chain_watch enable row level security;
drop policy if exists chain_watch_read on public.chain_watch;
create policy chain_watch_read on public.chain_watch for select using (true);

-- ---------------------------------------------------------------------------
-- The grants, and they were the FIRST silent failure here.
--
-- Both tables were created with no grant to service_role, so the edge
-- function's REST calls came back 401 "permission denied" - and the receiver
-- answered Helius with HTTP 200 regardless, so every inbound event would have
-- been dropped with nothing alarming. Found by probing the receiver's OUTPUT,
-- not its deployment status. Standing rule 16.
--
-- INSERT and SELECT only, deliberately. No UPDATE and no DELETE: the table is
-- append-only. A repeated signature is dropped by ON CONFLICT DO NOTHING
-- (Prefer: resolution=ignore-duplicates), never allowed to overwrite a row.
-- The receiver originally asked for merge-duplicates, which is an UPSERT, and
-- PostgREST correctly refused it with "GRANT UPDATE ON public.chain_events".
-- The fix was the weaker verb, not the wider grant.
-- ---------------------------------------------------------------------------
grant select, insert on public.chain_events to service_role;
grant usage, select on sequence public.chain_events_id_seq to service_role;
grant select on public.chain_watch to service_role;

-- anon stays closed on both tables. The site reads these through its own
-- server-side path, and chain_watch names the pools we watch, which is not
-- public information.

-- ---------------------------------------------------------------------------
-- The watchlist has to be readable and writable by something that runs
-- unattended and holds no service-role key. Nothing on disk has one: the repo's
-- .env carries only SUPABASE_PUBLISHABLE_KEY, and anon has no grant on these
-- tables on purpose. So the watchlist moves through a secret-gated RPC, the
-- same pattern record_observations and record_whale_event already use.
--
-- Passing no rows makes this a plain read, which is what heliushook.py needs to
-- keep the Helius webhook and the receiver agreeing on ONE list. They must
-- agree: an address on the webhook but not in chain_watch produces events that
-- cannot be attributed, and the reverse produces a pool nobody is watching.
-- ---------------------------------------------------------------------------
create or replace function public.chain_watch_sync(p_secret text, p_rows jsonb default null)
returns jsonb
language plpgsql
security definer
set search_path to 'public', 'private'
as $fn$
declare v_added int := 0;
begin
  perform private.check_secret('whale', p_secret);

  if p_rows is not null and jsonb_typeof(p_rows) = 'array' then
    with ins as (
      insert into public.chain_watch (address, kind, label, mint, dex, liq_usd_at_registration, webhook_id)
      select
        r->>'address',
        coalesce(r->>'kind', 'pool'),
        r->>'label',
        r->>'mint',
        r->>'dex',
        nullif(r->>'liq_usd', '')::numeric,
        r->>'webhook_id'
      from jsonb_array_elements(p_rows) r
      where coalesce(r->>'address', '') <> ''
      on conflict (address) do update
        set label = coalesce(excluded.label, public.chain_watch.label),
            mint = coalesce(excluded.mint, public.chain_watch.mint),
            dex = coalesce(excluded.dex, public.chain_watch.dex),
            webhook_id = coalesce(excluded.webhook_id, public.chain_watch.webhook_id),
            active = true
      returning 1
    )
    select count(*) into v_added from ins;
  end if;

  return jsonb_build_object(
    'upserted', v_added,
    'active', (select count(*) from public.chain_watch where active),
    'addresses', coalesce((
      select jsonb_agg(address order by address)
      from public.chain_watch where active
    ), '[]'::jsonb)
  );
end;
$fn$;

revoke all on function public.chain_watch_sync(text, jsonb) from public;
grant execute on function public.chain_watch_sync(text, jsonb) to anon, authenticated, service_role;
