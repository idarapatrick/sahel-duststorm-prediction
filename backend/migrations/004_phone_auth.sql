-- Verified phone accounts, OTP challenges, device records and revocable sessions.

alter table public.alert_identities
  add column if not exists preferred_lat double precision,
  add column if not exists preferred_lon double precision,
  add column if not exists preferred_location_name text,
  add column if not exists updated_at timestamptz not null default now();

create table if not exists public.otp_challenges (
  id uuid primary key default gen_random_uuid(),
  phone_uid varchar(15) not null,
  purpose text not null check (purpose in ('signup','login')),
  code_hash char(64) not null,
  expires_at timestamptz not null,
  attempts integer not null default 0,
  consumed_at timestamptz,
  requested_ip_hash char(64),
  device_id uuid,
  created_at timestamptz not null default now()
);
create index if not exists otp_phone_recent on public.otp_challenges(phone_uid, created_at desc);

create table if not exists public.user_sessions (
  token_hash char(64) primary key,
  phone_uid varchar(15) not null references public.alert_identities(phone_uid) on delete cascade,
  device_id uuid,
  ip_hash char(64),
  expires_at timestamptz not null,
  revoked_at timestamptz,
  created_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now()
);
create index if not exists active_user_sessions on public.user_sessions(phone_uid, expires_at)
  where revoked_at is null;

create table if not exists public.known_devices (
  device_id uuid primary key,
  phone_uid varchar(15) references public.alert_identities(phone_uid) on delete set null,
  first_ip_hash char(64),
  last_ip_hash char(64),
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now()
);

create table if not exists public.sms_messages (
  id uuid primary key default gen_random_uuid(),
  phone_uid varchar(15),
  category text not null check (category in ('otp','alert','broadcast')),
  provider text not null default 'africastalking',
  provider_message_id text,
  status text not null,
  error_code text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.alert_identities
  drop constraint if exists alert_identity_preferred_location_bounds;
alter table public.alert_identities
  add constraint alert_identity_preferred_location_bounds check (
    (preferred_lat is null and preferred_lon is null) or
    (preferred_lat between 10 and 25 and preferred_lon between -18 and 25)
  );

