-- APPLIED 2026-10-10 via the Supabase MCP (migration "harden_rls_and_grants"); kept for the record and rollback.
-- Note: routes_id_land_unique is a constraint, so it was dropped with ALTER TABLE ... DROP CONSTRAINT.
-- Covers issue #50 (RLS performance + grants) and the "stop serving the data to
-- anonymous callers" recommendation from docs/data-sources.md (#48).
--
-- Prepared 2026-10-10 from a read-only inspection of the live project:
--   * routes / stages: policy "public read ..." TO public USING (true)  -> anyone with
--     the publishable key (it is in index.html) can read every row without logging in
--   * user_state / user_preferences: own-row policies written as auth.uid() = user_id
--     (re-evaluated per row; advisor lint 0003) and applying to role public
--   * anon AND authenticated hold ALL privileges (incl. TRUNCATE, which bypasses RLS)
--     on all four tables. The REST API cannot issue TRUNCATE, so this is defence in depth.
--   * routes has two identical unique indexes (routes_pkey, routes_id_land_unique);
--     stages_route_id_land_fkey is backed by routes_pkey, so the duplicate is safe to drop.
--
-- What the app needs (verified in index.html): after login every request runs as the
-- `authenticated` role (reads routes/stages; reads+writes the user's own user_state rows
-- and user_preferences row). Nothing reads data before login. The scrapers use the
-- service_role key, which bypasses RLS and grants.
--
-- Effects: logged-out visitors (and anyone holding just the publishable key) get an
-- empty result, not the dataset. Logged-in users see no difference.
--
-- KEEPALIVE: the scheduled workflow (.github/workflows/supabase-keepalive.yml) queries
-- /rest/v1/routes with the anon key and expects HTTP 200. This migration keeps anon's
-- SELECT *privilege* (it just returns an empty array under RLS), so the check still gets
-- 200 and still proves the database is awake. Do NOT revoke SELECT from anon.

-- ===================== 0. PRE-FLIGHT (read-only; expect the "before" state) ==========
-- select policyname, cmd, roles from pg_policies where schemaname='public' order by tablename, policyname;
-- select grantee, table_name, string_agg(privilege_type, ',') from information_schema.role_table_grants
--   where table_schema='public' and grantee in ('anon','authenticated') group by 1,2 order by 2,1;

-- ===================== 1. MIGRATION (single transaction) ============================
begin;

-- 1a. routes / stages: authenticated users only
drop policy if exists "public read routes" on public.routes;
create policy "authenticated read routes" on public.routes
  for select to authenticated using (true);

drop policy if exists "public read stages" on public.stages;
create policy "authenticated read stages" on public.stages
  for select to authenticated using (true);

-- 1b. user_state: own rows, evaluated once per query ((select auth.uid())), authenticated only
drop policy if exists "own state select" on public.user_state;
drop policy if exists "own state insert" on public.user_state;
drop policy if exists "own state update" on public.user_state;
drop policy if exists "own state delete" on public.user_state;

create policy "own state select" on public.user_state
  for select to authenticated using ((select auth.uid()) = user_id);
create policy "own state insert" on public.user_state
  for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "own state update" on public.user_state
  for update to authenticated using ((select auth.uid()) = user_id)
                              with check ((select auth.uid()) = user_id);
create policy "own state delete" on public.user_state
  for delete to authenticated using ((select auth.uid()) = user_id);

-- 1c. user_preferences: same treatment (no delete policy today; keep it that way)
drop policy if exists "own prefs select" on public.user_preferences;
drop policy if exists "own prefs insert" on public.user_preferences;
drop policy if exists "own prefs update" on public.user_preferences;

create policy "own prefs select" on public.user_preferences
  for select to authenticated using ((select auth.uid()) = user_id);
create policy "own prefs insert" on public.user_preferences
  for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "own prefs update" on public.user_preferences
  for update to authenticated using ((select auth.uid()) = user_id)
                              with check ((select auth.uid()) = user_id);

-- 1d. duplicate index (advisor lint 0009); the FK uses routes_pkey, so this is safe
alter table public.routes drop constraint if exists routes_id_land_unique;

-- 1e. grants: least privilege
--   routes / stages are read-only from the API for everyone (scrapers use service_role)
revoke insert, update, delete, truncate, references, trigger on public.routes, public.stages from anon, authenticated;
--   anon keeps SELECT only on routes/stages (see KEEPALIVE note); it needs nothing on user tables
revoke all on public.user_state, public.user_preferences from anon;
--   authenticated: no TRUNCATE/REFERENCES/TRIGGER anywhere; user_preferences has no delete policy
revoke truncate, references, trigger on public.user_state, public.user_preferences from authenticated;
revoke delete on public.user_preferences from authenticated;

commit;

-- ===================== 2. VERIFY (read-only) =======================================
-- Expect: routes/stages have only "authenticated read ..."; user tables have 4 / 3 policies, all TO authenticated.
-- select tablename, policyname, cmd, roles from pg_policies where schemaname='public' order by 1,2;
-- Expect: no index routes_id_land_unique.
-- select indexname from pg_indexes where schemaname='public' and tablename='routes';
-- Expect: anon -> SELECT on routes/stages only; authenticated -> SELECT on routes/stages, SELECT/INSERT/UPDATE(/DELETE) on user tables.
-- select grantee, table_name, string_agg(privilege_type, ',' order by privilege_type) from information_schema.role_table_grants
--   where table_schema='public' and grantee in ('anon','authenticated') group by 1,2 order by 2,1;
-- Then re-run the advisors (security + performance): the 7 auth_rls_initplan and the duplicate_index lints should be gone.
--
-- Black-box check from a terminal (replace KEY with the publishable key):
--   curl -s -H "apikey: KEY" "https://<project>.supabase.co/rest/v1/routes?select=id&limit=1"   # expect []  (HTTP 200)
-- and in the app: log in, load a route, tick a stage, reload -> data and progress still there.

-- ===================== 3. ROLLBACK (restores the previous behaviour) ================
-- begin;
-- drop policy if exists "authenticated read routes" on public.routes;
-- drop policy if exists "authenticated read stages" on public.stages;
-- create policy "public read routes" on public.routes for select to public using (true);
-- create policy "public read stages" on public.stages for select to public using (true);
-- -- user-table policies: re-create the originals (auth.uid() = user_id, role public) if needed:
-- drop policy if exists "own state select" on public.user_state;  drop policy if exists "own state insert" on public.user_state;
-- drop policy if exists "own state update" on public.user_state;  drop policy if exists "own state delete" on public.user_state;
-- create policy "own state select" on public.user_state for select using (auth.uid() = user_id);
-- create policy "own state insert" on public.user_state for insert with check (auth.uid() = user_id);
-- create policy "own state update" on public.user_state for update using (auth.uid() = user_id) with check (auth.uid() = user_id);
-- create policy "own state delete" on public.user_state for delete using (auth.uid() = user_id);
-- drop policy if exists "own prefs select" on public.user_preferences; drop policy if exists "own prefs insert" on public.user_preferences;
-- drop policy if exists "own prefs update" on public.user_preferences;
-- create policy "own prefs select" on public.user_preferences for select using (auth.uid() = user_id);
-- create policy "own prefs insert" on public.user_preferences for insert with check (auth.uid() = user_id);
-- create policy "own prefs update" on public.user_preferences for update using (auth.uid() = user_id);
-- alter table public.routes add constraint routes_id_land_unique unique (id, land);
-- grant all on public.routes, public.stages, public.user_state, public.user_preferences to anon, authenticated;
-- commit;
