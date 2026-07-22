-- Non-destructive identity/provider transition.
-- Existing phone_uid foreign keys remain valid while Firebase becomes the
-- trusted authentication provider and Twilio becomes the alert SMS provider.

alter table public.alert_identities
  add column if not exists firebase_uid text,
  add column if not exists auth_provider text not null default 'legacy_otp';

create unique index if not exists alert_identities_firebase_uid_unique
  on public.alert_identities(firebase_uid) where firebase_uid is not null;

alter table public.alert_identities
  drop constraint if exists alert_identities_auth_provider_check;
alter table public.alert_identities
  add constraint alert_identities_auth_provider_check
  check (auth_provider in ('legacy_otp','firebase'));

create index if not exists alert_identities_auth_provider
  on public.alert_identities(auth_provider);

create table if not exists public.firebase_identity_cleanup (
  firebase_uid text primary key,
  status text not null default 'pending'
    check (status in ('pending','processing','failed','completed')),
  attempts integer not null default 0,
  available_at timestamptz not null default now(),
  last_error text,
  created_at timestamptz not null default now(),
  completed_at timestamptz
);

create index if not exists firebase_identity_cleanup_due
  on public.firebase_identity_cleanup(status,available_at)
  where status in ('pending','failed');
