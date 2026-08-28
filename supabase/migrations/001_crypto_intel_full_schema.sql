-- =====================================================================
-- crypto-intel: complete schema for a FRESH Supabase project.
--
-- Written for a project created with:
--   "Automatically expose new tables" = OFF
--   "Enable automatic RLS"            = ON
--
-- Because auto-expose is OFF, nothing reaches the Data API unless it is
-- granted here explicitly. The grants at the bottom are the entire public
-- surface: SELECT on the two tables the dashboard actually renders, and
-- EXECUTE on three secret-gated RPCs. No anon INSERT, UPDATE or DELETE
-- anywhere, on any table.
--
-- Secrets are NOT in this file. Run 002_bootstrap_secrets.sql (generated
-- at apply time) or call set_crypto_secret() with the config secret.
-- =====================================================================

-- ---------------------------------------------------------------- private
create schema if not exists private;
revoke all on schema private from anon, authenticated;

-- Four separate secrets, not one shared value. A leak of the cron secret
-- must not let anyone publish digests or forge whale events.
create table if not exists private.crypto_secrets (
  name        text primary key,   -- 'publish' | 'whale' | 'config' | 'cron'
  secret      text not null,
  rotated_at  timestamptz not null default now()
);

create table if not exists private.crypto_config (
  key         text primary key,
  value       text not null,
  updated_at  timestamptz not null default now()
);

create or replace function private.check_secret(p_name text, p_secret text)
returns void
language plpgsql
security definer
set search_path = private
as $$
declare v_expected text;
begin
  select secret into v_expected from private.crypto_secrets where name = p_name;
  if v_expected is null or p_secret is null or p_secret <> v_expected then
    raise exception 'rejected' using errcode = '42501';
  end if;
end;
$$;

-- ---------------------------------------------------------------- tables
create table if not exists public.crypto_digests (
  id           bigint generated always as identity primary key,
  captured_at  timestamptz not null,
  version      text        not null,
  payload      jsonb       not null,
  created_at   timestamptz not null default now()
);
create index if not exists crypto_digests_captured_at_idx
  on public.crypto_digests (captured_at desc);

create table if not exists public.crypto_whale_events (
  id           bigint generated always as identity primary key,
  wallet       text        not null,
  signature    text        not null unique,
  occurred_at  timestamptz not null,
  action       text,
  venue        text,
  usd          numeric,
  description  text        not null,
  known        boolean     not null default false,
  alerted      boolean     not null default false,
  created_at   timestamptz not null default now()
);
create index if not exists crypto_whale_events_wallet_time_idx
  on public.crypto_whale_events (wallet, occurred_at desc);
create index if not exists crypto_whale_events_alerted_idx
  on public.crypto_whale_events (alerted, occurred_at desc);

create table if not exists public.crypto_news (
  id            bigint generated always as identity primary key,
  url_key       text        not null unique,
  title_key     text        not null,
  title         text        not null,
  url           text        not null,
  outlet        text        not null,
  author        text,
  category      text,
  published_at  timestamptz not null,
  first_seen    timestamptz not null default now(),
  score         int         not null default 0,
  alert_reason  text,
  alerted       boolean     not null default false,
  also_in       text[]      not null default '{}',
  created_at    timestamptz not null default now()
);
create index if not exists crypto_news_published_idx  on public.crypto_news (published_at desc);
create index if not exists crypto_news_titlekey_idx   on public.crypto_news (title_key);
create index if not exists crypto_news_firstseen_idx  on public.crypto_news (first_seen desc);

create table if not exists public.crypto_watch_terms (
  term   text primary key,
  weight int  not null default 2,
  note   text
);

-- ------------------------------------------------------------------- RLS
-- "Enable automatic RLS" should already have switched these on. These are
-- belt-and-braces no-ops; the verification query at the bottom proves it.
alter table public.crypto_digests      enable row level security;
alter table public.crypto_whale_events enable row level security;
alter table public.crypto_news         enable row level security;
alter table public.crypto_watch_terms  enable row level security;

-- Read-only to the world, and only for what the dashboard renders. No
-- insert/update/delete policy exists, so those are denied for anon and
-- authenticated by default.
drop policy if exists "crypto_digests public read" on public.crypto_digests;
create policy "crypto_digests public read"
  on public.crypto_digests for select to anon, authenticated using (true);

drop policy if exists "crypto_news public read" on public.crypto_news;
create policy "crypto_news public read"
  on public.crypto_news for select to anon, authenticated using (true);

-- Deliberately NO policy on crypto_whale_events or crypto_watch_terms:
-- the dashboard does not render either. The digest payload carries whale
-- lines, and watch terms are read by the Edge Function via service_role.

-- ------------------------------------------------------------- functions
create or replace function public.publish_crypto_digest(
  p_secret text, p_captured_at timestamptz, p_version text, p_payload jsonb
) returns bigint
language plpgsql security definer set search_path = public, private
as $$
declare v_id bigint;
begin
  perform private.check_secret('publish', p_secret);
  insert into public.crypto_digests (captured_at, version, payload)
  values (p_captured_at, p_version, p_payload)
  returning id into v_id;
  return v_id;
end;
$$;

create or replace function public.record_whale_event(
  p_secret text, p_wallet text, p_signature text, p_occurred_at timestamptz,
  p_action text, p_venue text, p_usd numeric, p_description text,
  p_known boolean, p_min_usd numeric default 500, p_window_mins int default 10
) returns jsonb
language plpgsql security definer set search_path = public, private
as $$
declare v_id bigint; v_last timestamptz; v_suppressed int;
begin
  perform private.check_secret('whale', p_secret);

  insert into public.crypto_whale_events
    (wallet, signature, occurred_at, action, venue, usd, description, known)
  values
    (p_wallet, p_signature, p_occurred_at, p_action, p_venue, p_usd, p_description, p_known)
  on conflict (signature) do nothing
  returning id into v_id;

  if v_id is null then
    return jsonb_build_object('stored', false, 'should_alert', false, 'reason', 'duplicate signature');
  end if;
  if not p_known then
    return jsonb_build_object('stored', true, 'id', v_id, 'should_alert', false,
                              'reason', 'could not decode the action');
  end if;
  if p_usd is null or p_usd < p_min_usd then
    return jsonb_build_object('stored', true, 'id', v_id, 'should_alert', false,
                              'reason', format('below the $%s bar', p_min_usd));
  end if;

  select max(occurred_at) into v_last
    from public.crypto_whale_events
   where wallet = p_wallet and alerted
     and occurred_at > now() - make_interval(mins => p_window_mins);

  if v_last is not null then
    select count(*) into v_suppressed
      from public.crypto_whale_events
     where wallet = p_wallet and not alerted
       and occurred_at > now() - make_interval(mins => p_window_mins);
    return jsonb_build_object('stored', true, 'id', v_id, 'should_alert', false,
                              'reason', 'rate limited', 'suppressed', v_suppressed);
  end if;

  update public.crypto_whale_events set alerted = true where id = v_id;
  return jsonb_build_object('stored', true, 'id', v_id, 'should_alert', true);
end;
$$;

create or replace function public.set_crypto_config(p_secret text, p_key text, p_value text)
returns boolean
language plpgsql security definer set search_path = public, private
as $$
begin
  perform private.check_secret('config', p_secret);
  insert into private.crypto_config (key, value) values (p_key, p_value)
  on conflict (key) do update set value = excluded.value, updated_at = now();
  return true;
end;
$$;

-- Rotate/seed a named secret. Gated by the CONFIG secret, so bootstrapping
-- the first one is done with service_role (see 002_bootstrap_secrets.sql).
create or replace function public.set_crypto_secret(p_config_secret text, p_name text, p_new text)
returns boolean
language plpgsql security definer set search_path = public, private
as $$
begin
  perform private.check_secret('config', p_config_secret);
  insert into private.crypto_secrets (name, secret) values (p_name, p_new)
  on conflict (name) do update set secret = excluded.secret, rotated_at = now();
  return true;
end;
$$;

-- service_role only: the Edge Function reads config and the cron secret.
create or replace function public.read_crypto_config()
returns table(key text, value text)
language plpgsql security definer set search_path = public, private
as $$
begin
  return query select c.key, c.value from private.crypto_config c;
end;
$$;

-- ---------------------------------------------------------------- grants
-- Auto-expose is OFF, so this block IS the public API surface. Start from
-- nothing and add back only what is needed.
revoke all on all tables    in schema public from anon, authenticated;
revoke all on all functions in schema public from anon, authenticated;
revoke all on all sequences in schema public from anon, authenticated;

-- the two tables the dashboard renders, read-only
grant select on public.crypto_digests to anon, authenticated;
grant select on public.crypto_news    to anon, authenticated;

-- secret-gated write paths (the collector and the Vercel webhook)
grant execute on function public.publish_crypto_digest(text, timestamptz, text, jsonb) to anon;
grant execute on function public.record_whale_event(text,text,text,timestamptz,text,text,numeric,text,boolean,numeric,int) to anon;
grant execute on function public.set_crypto_config(text, text, text) to anon;

-- service_role only
revoke all on function public.read_crypto_config()  from public, anon, authenticated;
grant  execute on function public.read_crypto_config() to service_role;
revoke all on function public.set_crypto_secret(text,text,text) from public, anon, authenticated;
grant  execute on function public.set_crypto_secret(text,text,text) to service_role;

-- ----------------------------------------------------------- verification
-- Expect: all four tables rls=true; digests+news have exactly one SELECT
-- policy; whale_events and watch_terms have zero policies and zero grants.
select c.relname,
       c.relrowsecurity as rls,
       (select count(*) from pg_policies p
         where p.schemaname='public' and p.tablename=c.relname) as policies,
       coalesce((select string_agg(distinct g.privilege_type, ',')
                   from information_schema.role_table_grants g
                  where g.table_schema='public' and g.table_name=c.relname
                    and g.grantee='anon'), '(none)') as anon_grants
from pg_class c join pg_namespace n on n.oid=c.relnamespace
where n.nspname='public' and c.relkind='r' and c.relname like 'crypto\_%'
order by c.relname;
