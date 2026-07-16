-- Durable, independently claimed reinforcement jobs.
-- Only one active worker job may exist for a location/target pair.

alter table public.monitoring_jobs
  add column if not exists completed_at timestamptz;

alter table public.monitoring_jobs
  add column if not exists last_snapshot_id uuid
    references public.prediction_snapshots(id) on delete set null;

with duplicate_active_jobs as (
  select id, row_number() over (
    partition by tracking_key order by created_at, id
  ) as position
  from public.monitoring_jobs
  where status in ('pending','running','failed')
)
update public.monitoring_jobs
set status='cancelled', completed_at=now(),
    last_error='Cancelled by migration 005: duplicate active tracking key',
    updated_at=now()
where id in (select id from duplicate_active_jobs where position > 1);

create unique index if not exists monitoring_jobs_one_active_tracking_key
  on public.monitoring_jobs (tracking_key)
  where status in ('pending','running','failed');

create index if not exists monitoring_jobs_stale_lock
  on public.monitoring_jobs (locked_at)
  where status = 'running';

create unique index if not exists outbox_events_threshold_dedup
  on public.outbox_events (event_type, aggregate_id)
  where event_type = 'prediction.alert_level_changed';
