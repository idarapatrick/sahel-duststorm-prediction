-- Retain a deactivated phone account for seven days after verified deletion.
-- During this grace period all sessions are revoked and no alerts are sent.

alter table public.alert_identities
  add column if not exists account_status text not null default 'active',
  add column if not exists deletion_requested_at timestamptz,
  add column if not exists deletion_scheduled_for timestamptz;

alter table public.alert_identities
  drop constraint if exists alert_identities_account_status_check;
alter table public.alert_identities
  add constraint alert_identities_account_status_check
  check (account_status in ('active','pending_deletion'));

create index if not exists alert_identities_deletion_due
  on public.alert_identities(deletion_scheduled_for)
  where account_status='pending_deletion';
