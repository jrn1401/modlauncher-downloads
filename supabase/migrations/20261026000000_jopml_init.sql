-- JOPML v1.1 – Nutzerdaten in Supabase: anonym, verschlüsselt, nur über geprüfte Funktionen erreichbar.
--
-- Prinzipien
--  * Pseudonym statt Klarname: Das Konto hat nur einen frei gewählten Benutzernamen (intern als Pseudo-E-Mail
--    <name>@users.jopml.invalid in Supabase Auth). E-Mail und Anzeigename sind freiwillig.
--  * Alle persönlichen Profilfelder (Anzeigename, E-Mail, Einstellungen) liegen NUR verschlüsselt in `data_enc`
--    (pgcrypto pgp_sym_encrypt, AES-256). Der Schlüssel liegt im Supabase Vault (Secret 'jopml_data_key'), nicht in der Tabelle.
--  * Row Level Security ist aktiv und es gibt absichtlich KEINE Policies: Weder `anon` noch `authenticated` dürfen die Tabellen
--    direkt lesen oder schreiben. Zugriff gibt es nur über die SECURITY-DEFINER-Funktionen unten, die immer auth.uid() verwenden.
--  * Löschen eines Kontos löscht das Profil (ON DELETE CASCADE) und die KI-Zähler.
--  EHRLICH: Wer das Supabase-Projekt administriert, hat technisch Zugriff auf den Vault-Schlüssel und damit auf die Klartextdaten.
--  "Absolut sicher" gibt es nicht; dies ist Verschlüsselung im Ruhezustand + Zugriffskontrolle, keine Ende-zu-Ende-Verschlüsselung.

create schema if not exists extensions;
create extension if not exists pgcrypto with schema extensions;

-- Schlüssel einmalig im Vault anlegen (zufällig, 256 Bit). Läuft nur, wenn das Vault-Schema existiert und noch kein Schlüssel da ist.
do $$
begin
  if to_regnamespace('vault') is not null
     and not exists (select 1 from vault.decrypted_secrets where name = 'jopml_data_key') then
    perform vault.create_secret(encode(extensions.gen_random_bytes(32), 'hex'), 'jopml_data_key',
                                'JOPML: key for encrypting profile data');
  end if;
end $$;

-- ---------------------------------------------------------------- Tabellen
create table if not exists public.jopml_profiles (
  user_id    uuid primary key references auth.users (id) on delete cascade,
  username   text check (username is null or username ~ '^[a-z0-9_.-]{3,24}$'),
  data_enc   bytea not null,                       -- verschlüsseltes JSON: display_name, email, settings
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create unique index if not exists jopml_profiles_username_key on public.jopml_profiles (lower(username)) where username is not null;

create table if not exists public.jopml_ai_usage (
  user_id uuid not null references auth.users (id) on delete cascade,
  day     date not null default current_date,
  hits    integer not null default 0,
  primary key (user_id, day)
);
create table if not exists public.jopml_ai_global (
  day  date primary key default current_date,
  hits integer not null default 0
);

alter table public.jopml_profiles  enable row level security;
alter table public.jopml_ai_usage  enable row level security;
alter table public.jopml_ai_global enable row level security;
-- bewusst keine Policies -> kein Direktzugriff für anon/authenticated
revoke all on public.jopml_profiles, public.jopml_ai_usage, public.jopml_ai_global from anon, authenticated, public;

-- ---------------------------------------------------------------- interne Hilfsfunktionen
create or replace function public.jopml_key() returns text
language sql security definer set search_path = '' as $$
  select decrypted_secret from vault.decrypted_secrets where name = 'jopml_data_key' limit 1
$$;

create or replace function public.jopml_decode(p_row public.jopml_profiles) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare k text := public.jopml_key(); d jsonb;
begin
  if k is null then raise exception 'encryption key missing'; end if;
  d := extensions.pgp_sym_decrypt(p_row.data_enc, k)::jsonb;
  return jsonb_build_object('username', p_row.username,
                            'display_name', coalesce(d->>'display_name', ''),
                            'email', coalesce(d->>'email', ''),
                            'settings', coalesce(d->'settings', '{}'::jsonb));
end $$;

-- ---------------------------------------------------------------- öffentliche Funktionen (nur eingeloggte Nutzer)
-- Profil anlegen (falls neu) und zurückgeben.
create or replace function public.jopml_ensure_profile(p_username text default null, p_display_name text default null)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := auth.uid();
  k text := public.jopml_key();
  mail text; row public.jopml_profiles; uname text; disp text;
begin
  if uid is null then raise exception 'not_authenticated'; end if;
  if k is null then raise exception 'encryption key missing'; end if;
  select * into row from public.jopml_profiles where user_id = uid;
  if found then return public.jopml_decode(row); end if;

  select lower(email) into mail from auth.users where id = uid;
  uname := nullif(lower(btrim(coalesce(p_username, ''))), '');
  if uname is not null then
    if uname !~ '^[a-z0-9_.-]{3,24}$' then raise exception 'invalid_username'; end if;
    if mail is distinct from uname || '@users.jopml.invalid' then raise exception 'username_mismatch'; end if;
    if exists (select 1 from public.jopml_profiles where lower(username) = uname) then raise exception 'username_taken'; end if;
  end if;
  disp := left(coalesce(nullif(btrim(p_display_name), ''), uname,
               nullif(auth.jwt() -> 'user_metadata' ->> 'full_name', ''), 'User'), 40);

  insert into public.jopml_profiles (user_id, username, data_enc)
  values (uid, uname, extensions.pgp_sym_encrypt(
            jsonb_build_object('display_name', disp, 'email', '', 'settings', '{}'::jsonb)::text, k))
  returning * into row;
  return public.jopml_decode(row);
end $$;

create or replace function public.jopml_get_profile() returns jsonb
language plpgsql security definer set search_path = '' as $$
declare row public.jopml_profiles;
begin
  if auth.uid() is null then raise exception 'not_authenticated'; end if;
  select * into row from public.jopml_profiles where user_id = auth.uid();
  if not found then return null; end if;
  return public.jopml_decode(row);
end $$;

-- Teilweise aktualisieren: p darf display_name, email (leer = löschen) und settings (wird zusammengeführt) enthalten.
create or replace function public.jopml_save_profile(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := auth.uid();
  k text := public.jopml_key();
  row public.jopml_profiles; cur jsonb; setts jsonb; allowed text[] :=
    array['appearance_mode','accent','colors','language','dl_limit_kbps','cpu_priority','cpu_cores','ram_limit_mb','icon_bg'];
  key text;
begin
  if uid is null then raise exception 'not_authenticated'; end if;
  if jsonb_typeof(p) is distinct from 'object' then raise exception 'invalid_payload'; end if;
  select * into row from public.jopml_profiles where user_id = uid for update;
  if not found then raise exception 'no_profile'; end if;
  cur := extensions.pgp_sym_decrypt(row.data_enc, k)::jsonb;

  if p ? 'display_name' then
    if jsonb_typeof(p->'display_name') <> 'string' then raise exception 'invalid_display_name'; end if;
    cur := jsonb_set(cur, '{display_name}', to_jsonb(left(btrim(p->>'display_name'), 40)));
  end if;
  if p ? 'email' then
    if jsonb_typeof(p->'email') <> 'string' or length(p->>'email') > 254
       or (p->>'email' <> '' and p->>'email' !~ '^[^@\s]+@[^@\s]+\.[^@\s]+$') then raise exception 'invalid_email'; end if;
    cur := jsonb_set(cur, '{email}', to_jsonb(p->>'email'));
  end if;
  if p ? 'settings' then
    if jsonb_typeof(p->'settings') <> 'object' or length((p->'settings')::text) > 8000 then raise exception 'invalid_settings'; end if;
    setts := coalesce(cur->'settings', '{}'::jsonb);
    for key in select jsonb_object_keys(p->'settings') loop
      if key = any (allowed) then setts := jsonb_set(setts, array[key], p->'settings'->key); end if;   -- unbekannte Schlüssel werden verworfen
    end loop;
    cur := jsonb_set(cur, '{settings}', setts);
  end if;

  update public.jopml_profiles set data_enc = extensions.pgp_sym_encrypt(cur::text, k), updated_at = now()
   where user_id = uid returning * into row;
  return public.jopml_decode(row);
end $$;

-- Konto endgültig löschen (Profil + KI-Zähler gehen per CASCADE mit).
create or replace function public.jopml_delete_account() returns boolean
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null then raise exception 'not_authenticated'; end if;
  delete from auth.users where id = auth.uid();
  return true;
end $$;

-- KI-Kontingent (nur Edge Function mit service_role): zählt hoch und wirft 'rate_limited', wenn das Limit erreicht ist.
create or replace function public.jopml_ai_hit(p_user uuid, p_user_limit integer default 60, p_global_limit integer default 2000)
returns integer language plpgsql security definer set search_path = '' as $$
declare u integer; g integer;
begin
  insert into public.jopml_ai_global as t (day, hits) values (current_date, 1)
    on conflict (day) do update set hits = t.hits + 1 returning hits into g;
  if g > p_global_limit then raise exception 'rate_limited_global'; end if;
  insert into public.jopml_ai_usage as t (user_id, day, hits) values (p_user, current_date, 1)
    on conflict (user_id, day) do update set hits = t.hits + 1 returning hits into u;
  if u > p_user_limit then raise exception 'rate_limited'; end if;
  return p_user_limit - u;
end $$;

-- ---------------------------------------------------------------- Rechte
revoke all on function public.jopml_key() from public, anon, authenticated;
revoke all on function public.jopml_decode(public.jopml_profiles) from public, anon, authenticated;
revoke all on function public.jopml_ai_hit(uuid, integer, integer) from public, anon, authenticated;
revoke all on function public.jopml_ensure_profile(text, text) from public, anon;
revoke all on function public.jopml_get_profile() from public, anon;
revoke all on function public.jopml_save_profile(jsonb) from public, anon;
revoke all on function public.jopml_delete_account() from public, anon;
grant execute on function public.jopml_ensure_profile(text, text) to authenticated;
grant execute on function public.jopml_get_profile() to authenticated;
grant execute on function public.jopml_save_profile(jsonb) to authenticated;
grant execute on function public.jopml_delete_account() to authenticated;
grant execute on function public.jopml_ai_hit(uuid, integer, integer) to service_role;
