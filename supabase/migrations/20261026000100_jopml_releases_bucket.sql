-- Öffentlicher Download-Bucket für fertige Release-Pakete (Spiegel der GitHub-Releases, direkter Download-Link).
-- Lesen ist öffentlich (Bucket public); Schreiben geht nur mit dem service_role-Schlüssel der CI (umgeht RLS).
do $$
begin
  if to_regclass('storage.buckets') is not null then
    insert into storage.buckets (id, name, public, file_size_limit)
    values ('releases', 'releases', true, 157286400)         -- 150 MB pro Datei
    on conflict (id) do update set public = true, file_size_limit = excluded.file_size_limit;
  end if;
end $$;
