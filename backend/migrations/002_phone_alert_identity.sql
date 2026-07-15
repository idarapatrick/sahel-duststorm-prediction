-- Phone-only SahelWatch identity. Values use E.164 digits without the plus sign.
create table if not exists public.alert_identities (
  phone_uid varchar(15) primary key check (phone_uid ~ '^[1-9][0-9]{9,14}$'),
  country_calling_code varchar(4) not null,
  verified_at timestamptz,
  consented_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create table if not exists public.alert_subscriptions (
  id uuid primary key default gen_random_uuid(),
  phone_uid varchar(15) not null references public.alert_identities(phone_uid) on delete cascade,
  lat double precision not null check (lat between 10 and 25),
  lon double precision not null check (lon between -18 and 25),
  location_name text not null,
  threshold text not null check (threshold in ('watch','warning','alert')),
  next_refresh_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  unique(phone_uid, lat, lon)
);

create index if not exists alert_subscriptions_due
  on public.alert_subscriptions(next_refresh_at);

create table if not exists public.alert_deliveries (
  id uuid primary key default gen_random_uuid(),
  phone_uid varchar(15) references public.alert_identities(phone_uid) on delete set null,
  snapshot_id uuid references public.prediction_snapshots(id) on delete set null,
  provider_message_id text,
  status text not null,
  sent_at timestamptz not null default now()
);
