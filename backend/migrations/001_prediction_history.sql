-- SahelWatch prediction archive. Run once in Supabase/PostgreSQL.
create table if not exists public.prediction_snapshots (
  id uuid primary key,
  lat double precision not null check (lat between 10 and 25),
  lon double precision not null check (lon between -18 and 25),
  location_name text not null,
  target_date date not null,
  recorded_at timestamptz not null default now(),
  probability double precision not null check (probability between 0 and 1),
  alert_level text not null check (alert_level in ('clear', 'watch', 'warning', 'alert')),
  dust_event boolean not null,
  data_source text not null,
  model_version text,
  metadata jsonb not null default '{}'::jsonb
);

create index if not exists prediction_snapshot_lookup
  on public.prediction_snapshots (target_date, lat, lon);
create index if not exists prediction_snapshot_retention
  on public.prediction_snapshots (recorded_at);

-- Schedule daily through Supabase Cron/pg_cron in production.
create or replace function public.purge_expired_prediction_snapshots()
returns void language sql security definer as $$
  delete from public.prediction_snapshots where recorded_at < now() - interval '90 days';
$$;
