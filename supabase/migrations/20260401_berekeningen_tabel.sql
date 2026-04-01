-- =============================================================================
-- MIGRATIE: Berekeningen als aparte tabel (dossier = container)
-- =============================================================================
-- Doel: dossiers bevat alleen klantgegevens + metadata.
-- Berekeningen (aankoop/aanpassen) worden kinderen van een dossier,
-- net als aanvragen en adviezen dat al zijn.
-- =============================================================================

-- STAP 1: Berekeningen tabel aanmaken
-- Structuur volgt het patroon van aanvragen (dossier_id FK, eigen data)
CREATE TABLE IF NOT EXISTS public.berekeningen (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  dossier_id UUID NOT NULL REFERENCES public.dossiers(id) ON DELETE CASCADE,
  type TEXT NOT NULL CHECK (type IN ('aankoop', 'aanpassen')),
  naam TEXT NOT NULL DEFAULT '',
  invoer JSONB NOT NULL DEFAULT '{}'::jsonb,
  scenario1 JSONB NOT NULL DEFAULT '{}'::jsonb,
  scenario2 JSONB NOT NULL DEFAULT '{}'::jsonb,
  owner_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  aanmaak_datum TIMESTAMPTZ NOT NULL DEFAULT now(),
  laatst_gewijzigd TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index op dossier_id (meest voorkomende query)
CREATE INDEX IF NOT EXISTS idx_berekeningen_dossier_id
  ON public.berekeningen(dossier_id);

-- Auto-update laatst_gewijzigd
CREATE TRIGGER update_berekeningen_laatst_gewijzigd
  BEFORE UPDATE ON public.berekeningen
  FOR EACH ROW EXECUTE FUNCTION public.update_laatst_gewijzigd_column();

-- RLS: zelfde patroon als aanvragen
ALTER TABLE public.berekeningen ENABLE ROW LEVEL SECURITY;

CREATE POLICY "berekeningen_select_all_authenticated"
  ON public.berekeningen FOR SELECT TO authenticated USING (true);

CREATE POLICY "berekeningen_insert_admin_adviseur"
  ON public.berekeningen FOR INSERT TO authenticated
  WITH CHECK (
    public.get_user_role() IN ('admin', 'adviseur')
    AND dossier_id IN (SELECT id FROM public.dossiers WHERE owner_id = auth.uid())
  );

CREATE POLICY "berekeningen_update_owner_or_admin"
  ON public.berekeningen FOR UPDATE TO authenticated
  USING (
    dossier_id IN (SELECT id FROM public.dossiers WHERE owner_id = auth.uid())
    OR public.get_user_role() = 'admin'
  );

CREATE POLICY "berekeningen_delete_owner_or_admin"
  ON public.berekeningen FOR DELETE TO authenticated
  USING (
    dossier_id IN (SELECT id FROM public.dossiers WHERE owner_id = auth.uid())
    OR public.get_user_role() = 'admin'
  );

-- Service role mag altijd (voor backend/webhooks)
CREATE POLICY "berekeningen_service_role_all"
  ON public.berekeningen FOR ALL
  USING (auth.jwt() ->> 'role' = 'service_role');


-- =============================================================================
-- STAP 2: Bestaande data migreren van dossiers naar berekeningen
-- =============================================================================
-- Voor elk dossier met niet-lege invoer: maak een berekening-rij aan.
-- De berekening krijgt een NIEUW UUID (niet het dossier-ID hergebruiken).
-- dossier_id verwijst naar het oorspronkelijke dossier.

INSERT INTO public.berekeningen (dossier_id, type, naam, invoer, scenario1, scenario2, owner_id, aanmaak_datum, laatst_gewijzigd)
SELECT
  d.id AS dossier_id,
  d.type,
  d.naam,
  d.invoer,
  d.scenario1,
  d.scenario2,
  d.owner_id,
  d.aanmaak_datum,
  d.laatst_gewijzigd
FROM public.dossiers d
WHERE d.invoer != '{}'::jsonb
   OR d.scenario1 != '{}'::jsonb;


-- =============================================================================
-- STAP 3: invoer/scenario1/scenario2 nullable maken in dossiers
-- =============================================================================
-- We verwijderen ze NIET (backward compat voor adviesrapport V2 en andere lezers)
-- maar maken ze nullable zodat nieuwe dossiers ze niet meer hoeven te vullen.

ALTER TABLE public.dossiers
  ALTER COLUMN invoer DROP NOT NULL,
  ALTER COLUMN scenario1 DROP NOT NULL,
  ALTER COLUMN scenario2 DROP NOT NULL;

-- Default wijzigen naar NULL voor nieuwe dossiers
ALTER TABLE public.dossiers
  ALTER COLUMN invoer SET DEFAULT NULL,
  ALTER COLUMN scenario1 SET DEFAULT NULL,
  ALTER COLUMN scenario2 SET DEFAULT NULL;


-- =============================================================================
-- STAP 4: type kolom nullable maken in dossiers
-- =============================================================================
-- type ('aankoop'/'aanpassen') hoort bij de berekening, niet bij het dossier.
-- Een dossier kan zowel aankoop- als aanpassen-berekeningen bevatten.
-- Bestaande waarden blijven staan (niet NULL zetten), maar nieuwe dossiers
-- hoeven geen type meer te hebben.

ALTER TABLE public.dossiers
  ALTER COLUMN type DROP NOT NULL;
