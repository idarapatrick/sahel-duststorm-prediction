-- SahelWatch durable prediction and reinforcement schema.
-- Apply to DigitalOcean Managed PostgreSQL after 001 and 002.

create table if not exists public.locations (
  id uuid primary key default gen_random_uuid(),
  lat double precision not null check (lat between 10 and 25),
  lon double precision not null check (lon between -18 and 25),
  name text not null,
  country_code char(2),
  created_at timestamptz not null default now(),
  unique (lat, lon)
);

create table if not exists public.progressive_prediction_state (
  tracking_key text primary key,
  lat double precision not null check (lat between 10 and 25),
  lon double precision not null check (lon between -18 and 25),
  target_date date not null,
  state jsonb not null,
  updated_at timestamptz not null default now()
);
create index if not exists progressive_state_active
  on public.progressive_prediction_state (target_date, updated_at desc);

create table if not exists public.environmental_observations (
  id uuid primary key default gen_random_uuid(),
  location_id uuid references public.locations(id) on delete cascade,
  observed_at timestamptz not null,
  received_at timestamptz not null default now(),
  source text not null,
  value_kind text not null check (value_kind in ('observed','forecast','satellite','missing')),
  wind_speed_ms double precision,
  wind_direction_deg double precision,
  temperature_c double precision,
  surface_pressure_hpa double precision,
  precipitation_mm double precision,
  soil_moisture double precision,
  vegetation_water_content double precision,
  aod double precision,
  raw_payload jsonb not null default '{}'::jsonb,
  unique (location_id, observed_at, source, value_kind)
);
create index if not exists environmental_observation_lookup
  on public.environmental_observations (location_id, observed_at desc);

create table if not exists public.monitoring_jobs (
  id uuid primary key default gen_random_uuid(),
  tracking_key text not null,
  lat double precision not null,
  lon double precision not null,
  target_date date not null,
  status text not null default 'pending'
    check (status in ('pending','running','completed','failed','cancelled')),
  attempts integer not null default 0,
  next_run_at timestamptz not null default now(),
  locked_at timestamptz,
  locked_by text,
  last_error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tracking_key, next_run_at)
);
create index if not exists monitoring_jobs_due
  on public.monitoring_jobs (status, next_run_at)
  where status in ('pending','failed');

create table if not exists public.model_versions (
  id text primary key,
  model_type text not null,
  artifact_sha256 char(64),
  validation_status text not null default 'training'
    check (validation_status in ('training','evaluating','validated','rejected','retired')),
  metrics jsonb not null default '{}'::jsonb,
  deployed_at timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists public.outbox_events (
  id uuid primary key default gen_random_uuid(),
  event_type text not null,
  aggregate_id text not null,
  payload jsonb not null,
  status text not null default 'pending'
    check (status in ('pending','processing','delivered','failed')),
  attempts integer not null default 0,
  available_at timestamptz not null default now(),
  processed_at timestamptz,
  last_error text,
  created_at timestamptz not null default now()
);
create index if not exists outbox_events_due
  on public.outbox_events (status, available_at)
  where status in ('pending','failed');

-- Called once daily by the deployment scheduler. Keeping cleanup explicit
-- avoids relying on user traffic to enforce the 90-day product contract.
create or replace function public.purge_sahelwatch_expired_data()
returns void language plpgsql as $$
begin
  delete from public.prediction_snapshots where recorded_at < now() - interval '90 days';
  delete from public.progressive_prediction_state where updated_at < now() - interval '90 days';
  delete from public.environmental_observations where received_at < now() - interval '90 days';
  delete from public.outbox_events
    where status = 'delivered' and processed_at < now() - interval '90 days';
end;
$$;
