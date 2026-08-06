-- Durable account-security notifications shared across signed-in devices.

create table if not exists public.account_notifications (
  id uuid primary key default gen_random_uuid(),
  phone_uid varchar(15) not null references public.alert_identities(phone_uid) on delete cascade,
  event_type text not null check (event_type in ('account.created','account.login')),
  title text not null,
  message text not null,
  device_label text,
  location_name text,
  session_token_hash char(64) references public.user_sessions(token_hash) on delete set null,
  acknowledged_at timestamptz,
  reported_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists account_notifications_feed
  on public.account_notifications(phone_uid, created_at desc);
