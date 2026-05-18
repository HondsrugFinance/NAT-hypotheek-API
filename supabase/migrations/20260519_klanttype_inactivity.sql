-- ============================================================
-- C4.2 stap 3: klanttype + inactivity tracking
-- Datum: 2026-05-19
-- ============================================================
-- Achtergrond: Fastlane API heeft een "Nieuwe klant ja/nee" filter.
-- Bij Ja: alleen producten beschikbaar voor nieuwe klanten (~44 met rates)
-- Bij Nee: alles incl. bestaande-klant-only/uitgefaseerde (~88 met rates)
--
-- We scrapen BEIDE en bewaren met klanttype-tag. Het verschil = inactieve
-- of bestaande-klant-only producten. Lookup endpoint kan filteren.

-- ===================
-- 1. hypotheekrentes uitbreiden met klanttype
-- ===================
ALTER TABLE public.hypotheekrentes
    ADD COLUMN IF NOT EXISTS klanttype TEXT NOT NULL DEFAULT 'nieuw'
    CHECK (klanttype IN ('nieuw', 'bestaand'));

-- Oude UNIQUE constraint vervangen door één met klanttype erbij
ALTER TABLE public.hypotheekrentes
    DROP CONSTRAINT IF EXISTS hypotheekrentes_geldverstrekker_productlijn_aflosvorm_renteva_key;

-- Find en drop alle bestaande UNIQUE constraints op deze kolommen-combinatie
DO $$
DECLARE
    constraint_name TEXT;
BEGIN
    FOR constraint_name IN
        SELECT conname FROM pg_constraint
        WHERE conrelid = 'public.hypotheekrentes'::regclass
          AND contype = 'u'
    LOOP
        EXECUTE 'ALTER TABLE public.hypotheekrentes DROP CONSTRAINT IF EXISTS ' || quote_ident(constraint_name);
    END LOOP;
END $$;

ALTER TABLE public.hypotheekrentes
    ADD CONSTRAINT hypotheekrentes_unique_per_klanttype
    UNIQUE (geldverstrekker, productlijn, aflosvorm, rentevaste_periode, peildatum, klanttype);

-- Index voor snelle lookup met klanttype filter
CREATE INDEX IF NOT EXISTS idx_rentes_lookup_klanttype
    ON public.hypotheekrentes (geldverstrekker, productlijn, aflosvorm, klanttype, peildatum DESC);


-- ===================
-- 2. scraper_inactivity_tracking
-- ===================
-- Track per product wanneer het laatst actief was voor nieuwe klanten.
-- Bijgewerkt elke scrape-run. Bron voor admin-notificaties.
CREATE TABLE IF NOT EXISTS public.scraper_inactivity_tracking (
    id                       UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    geldverstrekker          TEXT NOT NULL,
    productlijn              TEXT NOT NULL,
    hb_raw_name              TEXT,                            -- Originele naam uit Fastlane (incl. raw varianten)
    status                   TEXT NOT NULL CHECK (status IN (
        'actief',                  -- beschikbaar voor nieuwe klanten
        'alleen_bestaand',         -- alleen in 'bestaand' scrape (uitgefaseerd voor nieuw)
        'nieuw_in_hb',             -- nieuw product in HB, nog niet in onze config
        'verdwenen'                -- niet meer in beide scrapes
    )),
    first_seen_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_active_at      TIMESTAMPTZ,                     -- laatste keer in 'nieuw' scrape
    last_seen_bestaand_at    TIMESTAMPTZ,                     -- laatste keer in 'bestaand' scrape
    last_updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reported_at              TIMESTAMPTZ,                     -- wanneer admin notificatie ontving
    notitie                  TEXT,
    UNIQUE (geldverstrekker, productlijn)
);

CREATE INDEX IF NOT EXISTS idx_inactivity_status
    ON public.scraper_inactivity_tracking (status, last_updated_at DESC);

-- RLS
ALTER TABLE public.scraper_inactivity_tracking ENABLE ROW LEVEL SECURITY;

CREATE POLICY "scraper_inactivity_service_role_all"
    ON public.scraper_inactivity_tracking
    FOR ALL
    USING (auth.jwt() ->> 'role' = 'service_role')
    WITH CHECK (auth.jwt() ->> 'role' = 'service_role');

-- Authenticated admins mogen lezen (voor admin dashboard)
CREATE POLICY "scraper_inactivity_admin_select"
    ON public.scraper_inactivity_tracking
    FOR SELECT
    TO authenticated
    USING ((auth.jwt() -> 'app_metadata' ->> 'role') = 'admin');
