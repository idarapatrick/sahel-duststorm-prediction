-- Permit short-lived OTP challenges used to confirm permanent account deletion.

alter table public.otp_challenges
  drop constraint if exists otp_challenges_purpose_check;

alter table public.otp_challenges
  add constraint otp_challenges_purpose_check
  check (purpose in ('signup', 'login', 'delete'));

-- Repair names created before covered-city lookup was made deterministic.
with covered(lat, lon, name) as (
  values
    (13.51::double precision, 2.11::double precision, 'Niamey, Niger'),
    (13.06, 5.24, 'Sokoto, Nigeria'), (12.00, 8.52, 'Kano, Nigeria'),
    (11.85, 13.16, 'Maiduguri, Nigeria'), (16.97, 7.99, 'Agadez, Niger'),
    (12.13, 15.06, 'N''Djamena, Chad'), (12.64, -8.00, 'Bamako, Mali'),
    (16.77, -3.01, 'Timbuktu, Mali'), (12.36, -1.48, 'Ouagadougou, Burkina Faso'),
    (14.69, -17.44, 'Dakar, Senegal'), (18.09, -15.98, 'Nouakchott, Mauritania')
)
update public.prediction_snapshots p set location_name=c.name
from covered c where abs(p.lat-c.lat)<=0.05 and abs(p.lon-c.lon)<=0.05
  and (p.location_name is null or trim(p.location_name)='' or p.location_name='Unknown');

with covered(lat, lon, name) as (
  values
    (13.51::double precision, 2.11::double precision, 'Niamey, Niger'),
    (13.06, 5.24, 'Sokoto, Nigeria'), (12.00, 8.52, 'Kano, Nigeria'),
    (11.85, 13.16, 'Maiduguri, Nigeria'), (16.97, 7.99, 'Agadez, Niger'),
    (12.13, 15.06, 'N''Djamena, Chad'), (12.64, -8.00, 'Bamako, Mali'),
    (16.77, -3.01, 'Timbuktu, Mali'), (12.36, -1.48, 'Ouagadougou, Burkina Faso'),
    (14.69, -17.44, 'Dakar, Senegal'), (18.09, -15.98, 'Nouakchott, Mauritania')
)
update public.outbox_events e
set payload=jsonb_set(e.payload, '{location_name}', to_jsonb(c.name), true)
from covered c
where e.event_type='prediction.alert_level_changed'
  and abs((e.payload->>'lat')::double precision-c.lat)<=0.05
  and abs((e.payload->>'lon')::double precision-c.lon)<=0.05
  and coalesce(e.payload->>'location_name','Unknown')='Unknown';
