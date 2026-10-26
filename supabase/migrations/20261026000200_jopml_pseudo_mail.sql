-- Die interne Konto-Adresse hat das Muster <betreiber>+<benutzername>@<domain> (".invalid" lehnt Supabase ab).
-- Geprüft wird nur noch der Teil nach dem "+" – unabhängig von der Domain.
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
    if split_part(split_part(coalesce(mail, ''), '@', 1), '+', 2) is distinct from uname then raise exception 'username_mismatch'; end if;
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
revoke all on function public.jopml_ensure_profile(text, text) from public, anon;
grant execute on function public.jopml_ensure_profile(text, text) to authenticated;
