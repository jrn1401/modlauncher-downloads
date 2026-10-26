\set ON_ERROR_STOP off
insert into auth.users(id,email) values ('11111111-1111-1111-1111-111111111111','alice@users.jopml.invalid'),('22222222-2222-2222-2222-222222222222','bob@users.jopml.invalid'),('33333333-3333-3333-3333-333333333333','g@gmail.com');
-- als Alice
set role authenticated; set request.jwt.claim.sub = '11111111-1111-1111-1111-111111111111';
select 'ensure' t, public.jopml_ensure_profile('alice','Alice A');
select 'username_mismatch (soll Fehler)' t; select public.jopml_ensure_profile('bob','x') where false;
select 'save' t, public.jopml_save_profile('{"email":"a@b.de","settings":{"accent":"#fff","evil":"x","language":"de"}}'::jsonb);
select 'get' t, public.jopml_get_profile();
select 'bad email (soll Fehler)'; select public.jopml_save_profile('{"email":"nomail"}'::jsonb);
select 'direkter Tabellenzugriff (soll Fehler)'; select * from public.jopml_profiles;
select 'key lesen (soll Fehler)'; select public.jopml_key();
select 'ai_hit als user (soll Fehler)'; select public.jopml_ai_hit('11111111-1111-1111-1111-111111111111');
reset role;
-- Daten im Klartext suchen: darf nicht auffindbar sein
select 'cipher enthält Klartext?' t, position('a@b.de'::bytea in data_enc) > 0 as leak from public.jopml_profiles;
select 'username_taken' t;
set role authenticated; set request.jwt.claim.sub = '22222222-2222-2222-2222-222222222222';
select public.jopml_ensure_profile('alice','x');
select public.jopml_ensure_profile('bob','Bob');
select 'bob sieht nur sich' t, public.jopml_get_profile();
-- Google: kein Username
set request.jwt.claim.sub = '33333333-3333-3333-3333-333333333333'; set request.jwt.claims = '{"user_metadata":{"full_name":"Gina Google"}}';
select 'google' t, public.jopml_ensure_profile(null,null);
-- Löschen
select 'delete' t, public.jopml_delete_account();
reset role;
select 'nach delete' t, count(*) from public.jopml_profiles;
-- anon
set role anon; reset request.jwt.claim.sub; select 'anon get (soll Fehler)'; select public.jopml_get_profile();
reset role;
-- AI-Limit (service_role)
set role service_role;
select 'ai1' t, public.jopml_ai_hit('11111111-1111-1111-1111-111111111111', 2, 100);
select 'ai2' t, public.jopml_ai_hit('11111111-1111-1111-1111-111111111111', 2, 100);
select 'ai3 (soll rate_limited)'; select public.jopml_ai_hit('11111111-1111-1111-1111-111111111111', 2, 100);
reset role;
