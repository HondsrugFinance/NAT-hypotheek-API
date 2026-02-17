-- =============================================================================
-- Stap 7: Rollen-systeem RBAC
-- Voer dit script uit in Supabase SQL Editor (Lovable Cloud → SQL Editor)
--
-- BELANGRIJK: Voer eerst het pre-check script hieronder uit om de huidige
-- policy-namen te zien. Pas daarna de DROP-statements aan als nodig.
-- =============================================================================

-- =============================================================================
-- 0. PRE-CHECK: Bekijk huidige policies (voer dit EERST apart uit)
-- =============================================================================
-- Kopieer en voer dit blok EERST uit om de exacte policy-namen te zien:
--
-- SELECT schemaname, tablename, policyname, cmd
-- FROM pg_policies
-- WHERE tablename IN ('dossiers', 'aanvragen', 'profiles')
-- ORDER BY tablename, cmd;
--

-- =============================================================================
-- 1. Role kolom toevoegen aan profiles
-- =============================================================================
-- Default = 'adviseur', zodat bestaande gebruikers automatisch adviseur worden
ALTER TABLE public.profiles
  ADD COLUMN role TEXT NOT NULL DEFAULT 'adviseur'
  CHECK (role IN ('admin', 'adviseur', 'viewer'));

-- =============================================================================
-- 2. Alex als admin instellen
-- =============================================================================
UPDATE public.profiles
SET role = 'admin'
WHERE user_id = (
  SELECT id FROM auth.users WHERE email = 'alex@hondsrugfinance.nl'
);

-- =============================================================================
-- 3. Helper functie: haal rol op van huidige ingelogde gebruiker
-- SECURITY DEFINER: omzeilt RLS, voorkomt recursie bij gebruik in policies
-- =============================================================================
CREATE OR REPLACE FUNCTION public.get_user_role()
RETURNS TEXT
LANGUAGE sql
SECURITY DEFINER
STABLE
AS $$
  SELECT role FROM public.profiles WHERE user_id = auth.uid();
$$;

-- =============================================================================
-- 4. RLS policies op DOSSIERS vervangen
-- =============================================================================

-- Oude policies verwijderen (exacte namen uit pre-check 2026-02-17)
DROP POLICY IF EXISTS "Authenticated users can view all dossiers" ON public.dossiers;
DROP POLICY IF EXISTS "Authenticated users can insert dossiers" ON public.dossiers;
DROP POLICY IF EXISTS "Owners can update their dossiers" ON public.dossiers;
DROP POLICY IF EXISTS "Owners can delete their dossiers" ON public.dossiers;

-- SELECT: alle ingelogde gebruikers mogen alle dossiers lezen
CREATE POLICY "dossiers_select_all_authenticated"
  ON public.dossiers FOR SELECT
  TO authenticated
  USING (true);

-- INSERT: alleen admin en adviseur, en alleen met eigen owner_id
CREATE POLICY "dossiers_insert_admin_adviseur"
  ON public.dossiers FOR INSERT
  TO authenticated
  WITH CHECK (
    public.get_user_role() IN ('admin', 'adviseur')
    AND owner_id = auth.uid()
  );

-- UPDATE: eigen dossiers voor adviseur, alle dossiers voor admin
CREATE POLICY "dossiers_update_owner_or_admin"
  ON public.dossiers FOR UPDATE
  TO authenticated
  USING (
    owner_id = auth.uid()
    OR public.get_user_role() = 'admin'
  );

-- DELETE: eigen dossiers voor adviseur, alle dossiers voor admin
CREATE POLICY "dossiers_delete_owner_or_admin"
  ON public.dossiers FOR DELETE
  TO authenticated
  USING (
    owner_id = auth.uid()
    OR public.get_user_role() = 'admin'
  );

-- =============================================================================
-- 5. RLS policies op AANVRAGEN vervangen
-- =============================================================================

-- Oude policies verwijderen (exacte namen uit pre-check 2026-02-17)
DROP POLICY IF EXISTS "Authenticated users can view all aanvragen" ON public.aanvragen;
DROP POLICY IF EXISTS "Authenticated users can insert aanvragen" ON public.aanvragen;
DROP POLICY IF EXISTS "Authenticated users can update aanvragen" ON public.aanvragen;
DROP POLICY IF EXISTS "Authenticated users can delete aanvragen" ON public.aanvragen;

-- SELECT: alle ingelogde gebruikers mogen alle aanvragen lezen
CREATE POLICY "aanvragen_select_all_authenticated"
  ON public.aanvragen FOR SELECT
  TO authenticated
  USING (true);

-- INSERT: alleen admin en adviseur, alleen bij eigen dossiers
CREATE POLICY "aanvragen_insert_admin_adviseur"
  ON public.aanvragen FOR INSERT
  TO authenticated
  WITH CHECK (
    public.get_user_role() IN ('admin', 'adviseur')
    AND dossier_id IN (SELECT id FROM public.dossiers WHERE owner_id = auth.uid())
  );

-- UPDATE: eigen aanvragen voor adviseur, alle aanvragen voor admin
CREATE POLICY "aanvragen_update_owner_or_admin"
  ON public.aanvragen FOR UPDATE
  TO authenticated
  USING (
    dossier_id IN (SELECT id FROM public.dossiers WHERE owner_id = auth.uid())
    OR public.get_user_role() = 'admin'
  );

-- DELETE: eigen aanvragen voor adviseur, alle aanvragen voor admin
CREATE POLICY "aanvragen_delete_owner_or_admin"
  ON public.aanvragen FOR DELETE
  TO authenticated
  USING (
    dossier_id IN (SELECT id FROM public.dossiers WHERE owner_id = auth.uid())
    OR public.get_user_role() = 'admin'
  );

-- =============================================================================
-- 6. RLS policies op PROFILES vervangen
-- =============================================================================

-- Oude policies verwijderen (exacte namen uit pre-check 2026-02-17)
DROP POLICY IF EXISTS "Authenticated users can view all profiles" ON public.profiles;
DROP POLICY IF EXISTS "Users can update their own profile" ON public.profiles;
DROP POLICY IF EXISTS "Users can insert their own profile" ON public.profiles;

-- SELECT: alle ingelogde gebruikers mogen alle profielen lezen
-- (nodig voor dossier-eigenaar weergave en teamoverzicht)
CREATE POLICY "profiles_select_all_authenticated"
  ON public.profiles FOR SELECT
  TO authenticated
  USING (true);

-- INSERT: gebruikers kunnen alleen hun eigen profiel aanmaken
CREATE POLICY "profiles_insert_own"
  ON public.profiles FOR INSERT
  TO authenticated
  WITH CHECK (user_id = auth.uid());

-- UPDATE eigen profiel: iedereen mag eigen profiel-data wijzigen,
-- maar NIET de role kolom (afgedwongen via get_user_role check)
CREATE POLICY "profiles_update_own_no_role_change"
  ON public.profiles FOR UPDATE
  TO authenticated
  USING (user_id = auth.uid())
  WITH CHECK (
    user_id = auth.uid()
    AND (
      -- Role moet gelijk blijven aan huidige role (via SECURITY DEFINER, geen recursie)
      role = public.get_user_role()
    )
  );

-- UPDATE door admin: mag ALLE profielen wijzigen inclusief role
CREATE POLICY "profiles_update_admin_all"
  ON public.profiles FOR UPDATE
  TO authenticated
  USING (public.get_user_role() = 'admin');

-- =============================================================================
-- 7. Verificatie
-- =============================================================================

-- Check dat Alex admin is en alle gebruikers hun rol hebben
SELECT p.naam, u.email, p.role
FROM public.profiles p
JOIN auth.users u ON u.id = p.user_id
ORDER BY p.role, p.naam;
