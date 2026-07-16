-- Complete the alert delivery, operational health and rate-limit schema.

alter table public.outbox_events drop constraint if exists outbox_events_status_check;
alter table public.outbox_events add constraint outbox_events_status_check
  check (status in ('pending','processing','delivered','failed','dead_letter'));

alter table public.alert_deliveries
  add column if not exists outbox_event_id uuid
    references public.outbox_events(id) on delete set null,
  add column if not exists error_code text,
  add column if not exists updated_at timestamptz not null default now();

create unique index if not exists alert_delivery_once_per_recipient
  on public.alert_deliveries(outbox_event_id, phone_uid)
  where outbox_event_id is not null and phone_uid is not null;

create table if not exists public.worker_heartbeats (
  worker_name text primary key,
  worker_id text not null,
  status text not null,
  metadata jsonb not null default '{}'::jsonb,
  heartbeat_at timestamptz not null default now()
);

create table if not exists public.api_rate_limits (
  bucket_key char(64) not null,
  action text not null,
  window_started_at timestamptz not null,
  request_count integer not null default 1,
  primary key(bucket_key, action, window_started_at)
);
create index if not exists api_rate_limits_expiry
  on public.api_rate_limits(window_started_at);

create index if not exists outbox_event_recent_notifications
  on public.outbox_events(created_at desc, event_type);

create or replace function public.purge_sahelwatch_expired_data()
returns void language plpgsql as $$
begin
  delete from public.prediction_snapshots where recorded_at < now() - interval '90 days';
  delete from public.progressive_prediction_state where updated_at < now() - interval '90 days';
  delete from public.environmental_observations where received_at < now() - interval '90 days';
  delete from public.prediction_response_cache where expires_at < now() - interval '1 day';
  delete from public.api_rate_limits where window_started_at < now() - interval '2 days';
  delete from public.otp_challenges where created_at < now() - interval '7 days';
  delete from public.user_sessions where expires_at < now() - interval '7 days';
  delete from public.outbox_events
    where status = 'delivered' and processed_at < now() - interval '90 days';
end;
$$;
