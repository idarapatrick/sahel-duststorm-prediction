-- Add auditable environmental evidence and immutable prediction revisions.

create table if not exists public.environmental_evidence (
  id uuid primary key,
  location_id uuid not null references public.locations(id) on delete cascade,
  variable_name text not null,
  value double precision,
  unit text,
  provider text not null,
  evidence_kind text not null
    check (evidence_kind in (
      'observation', 'analysis', 'forecast',
      'delayed_observation', 'fallback', 'missing'
    )),
  measured_at timestamptz,
  available_at timestamptz not null,
  availability_is_estimated boolean not null default true,
  retrieved_at timestamptz not null default now(),
  forecast_issued_at timestamptz,
  forecast_target_at timestamptz,
  quality_status text not null default 'valid'
    check (quality_status in ('valid', 'degraded', 'stale', 'missing', 'invalid')),
  is_fallback boolean not null default false,
  source_age_seconds bigint,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  check (
    evidence_kind <> 'forecast'
    or forecast_target_at is not null
  )
);

create index if not exists environmental_evidence_location_available
  on public.environmental_evidence(location_id, variable_name, available_at desc);

create index if not exists environmental_evidence_retention
  on public.environmental_evidence(retrieved_at);

create unique index if not exists environmental_evidence_natural_identity
  on public.environmental_evidence(
    location_id,
    variable_name,
    provider,
    evidence_kind,
    (coalesce(measured_at, '-infinity'::timestamptz)),
    (coalesce(forecast_issued_at, '-infinity'::timestamptz)),
    (coalesce(forecast_target_at, '-infinity'::timestamptz)),
    available_at
  );

alter table public.prediction_snapshots
  add column if not exists revision_number integer,
  add column if not exists revision_reason text,
  add column if not exists evidence_fingerprint char(64),
  add column if not exists observed_fraction double precision,
  add column if not exists forecast_fraction double precision,
  add column if not exists input_completeness double precision;

with numbered as (
  select id,
         row_number() over (
           partition by round(lat::numeric, 3), round(lon::numeric, 3), target_date
           order by recorded_at, id
         ) as revision_number
  from public.prediction_snapshots
)
update public.prediction_snapshots p
set revision_number = numbered.revision_number
from numbered
where p.id = numbered.id and p.revision_number is null;

alter table public.prediction_snapshots
  alter column revision_number set default 1;

create unique index if not exists prediction_snapshot_revision_identity
  on public.prediction_snapshots(
    round(lat::numeric, 3),
    round(lon::numeric, 3),
    target_date,
    revision_number
  );

create unique index if not exists prediction_snapshot_evidence_dedup
  on public.prediction_snapshots(
    round(lat::numeric, 3),
    round(lon::numeric, 3),
    target_date,
    evidence_fingerprint
  )
  where evidence_fingerprint is not null;

create table if not exists public.prediction_evidence_links (
  snapshot_id uuid not null
    references public.prediction_snapshots(id) on delete cascade,
  evidence_id uuid not null
    references public.environmental_evidence(id) on delete restrict,
  model_feature text not null,
  feature_position integer,
  primary key(snapshot_id, evidence_id, model_feature)
);

create index if not exists prediction_evidence_links_evidence
  on public.prediction_evidence_links(evidence_id);

create table if not exists public.prediction_outcomes (
  id uuid primary key,
  location_id uuid not null references public.locations(id) on delete cascade,
  target_date date not null,
  dust_event boolean not null,
  label_value double precision,
  provider text not null,
  measured_at timestamptz,
  available_at timestamptz not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique(location_id, target_date, provider)
);

create table if not exists public.validation_runs (
  id uuid primary key,
  model_version text not null,
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  status text not null default 'running'
    check (status in ('running', 'completed', 'failed')),
  configuration jsonb not null,
  metrics jsonb,
  error_message text
);

create table if not exists public.validation_predictions (
  id uuid primary key,
  validation_run_id uuid not null
    references public.validation_runs(id) on delete cascade,
  location_id uuid not null references public.locations(id) on delete cascade,
  target_date date not null,
  issued_at timestamptz not null,
  lead_hours double precision not null,
  probability double precision not null,
  predicted_event boolean not null,
  outcome_event boolean not null,
  season text,
  fallback_used boolean not null default false,
  evidence_completeness double precision,
  metadata jsonb not null default '{}'::jsonb
);

create index if not exists validation_prediction_slices
  on public.validation_predictions(
    validation_run_id, target_date, location_id, lead_hours
  );

create or replace function public.purge_sahelwatch_expired_data()
returns void language plpgsql as $$
begin
  delete from public.prediction_snapshots
    where recorded_at < now() - interval '90 days';
  delete from public.progressive_prediction_state
    where updated_at < now() - interval '90 days';
  delete from public.environmental_observations
    where received_at < now() - interval '90 days';
  delete from public.environmental_evidence
    where retrieved_at < now() - interval '90 days'
      and not exists (
        select 1 from public.prediction_evidence_links link
        where link.evidence_id = environmental_evidence.id
      );
  delete from public.prediction_response_cache
    where expires_at < now() - interval '1 day';
  delete from public.api_rate_limits
    where window_started_at < now() - interval '2 days';
  delete from public.otp_challenges
    where created_at < now() - interval '7 days';
  delete from public.user_sessions
    where expires_at < now() - interval '7 days';
  delete from public.outbox_events
    where status = 'delivered' and processed_at < now() - interval '90 days';
end;
$$;
