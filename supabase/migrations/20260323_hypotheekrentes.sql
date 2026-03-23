-- ============================================================
-- C4: Hypotheekrentes tabellen
-- Datum: 2026-03-23
-- ============================================================

-- ===================
-- 1. hypotheekrentes
-- ===================
-- Eén rij = één regel uit een tarievenblad:
--   geldverstrekker × productlijn × aflosvorm × rentevaste_periode
-- De LTV-staffel zit als JSONB in één kolom (matcht hoe banken het presenteren).
--
-- Voorbeeld ltv_staffel:
--   {"NHG": 3.96, "55": 4.14, "65": 4.16, "70": 4.17, "80": 4.19, "90": 4.22, "100": 4.24}
-- Keys zijn drempelwaarden: "55" = ≤55%, "100" = ≤100%, "106plus" = >106%

CREATE TABLE IF NOT EXISTS hypotheekrentes (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    geldverstrekker TEXT NOT NULL,
    productlijn     TEXT NOT NULL,
    aflosvorm       TEXT NOT NULL CHECK (aflosvorm IN ('annuitair', 'lineair', 'aflossingsvrij')),
    rentevaste_periode INTEGER NOT NULL,          -- jaren, 0 = variabel
    ltv_staffel     JSONB NOT NULL DEFAULT '{}',  -- {"NHG": 3.96, "55": 4.14, ...}
    peildatum       DATE NOT NULL DEFAULT CURRENT_DATE,
    bron            TEXT NOT NULL DEFAULT 'handmatig' CHECK (bron IN ('handmatig', 'api', 'scraper')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Unieke combinatie: per peildatum maar één tarief per product/aflosvorm/periode
    UNIQUE (geldverstrekker, productlijn, aflosvorm, rentevaste_periode, peildatum)
);

-- Index voor snelle lookups vanuit formulier
CREATE INDEX IF NOT EXISTS idx_rentes_lookup
    ON hypotheekrentes (geldverstrekker, productlijn, aflosvorm, peildatum DESC);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_hypotheekrentes_updated_at
    BEFORE UPDATE ON hypotheekrentes
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- RLS
ALTER TABLE hypotheekrentes ENABLE ROW LEVEL SECURITY;

-- Lezen: iedereen (authenticated)
CREATE POLICY "hypotheekrentes_select"
    ON hypotheekrentes FOR SELECT
    TO authenticated
    USING (true);

-- Schrijven: alleen service_role (backend) of admin users
-- Pas de admin-check aan op je eigen auth-structuur
CREATE POLICY "hypotheekrentes_insert"
    ON hypotheekrentes FOR INSERT
    TO authenticated
    WITH CHECK (
        auth.jwt() ->> 'role' = 'service_role'
        OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'admin'
    );

CREATE POLICY "hypotheekrentes_update"
    ON hypotheekrentes FOR UPDATE
    TO authenticated
    USING (
        auth.jwt() ->> 'role' = 'service_role'
        OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'admin'
    );

CREATE POLICY "hypotheekrentes_delete"
    ON hypotheekrentes FOR DELETE
    TO authenticated
    USING (
        auth.jwt() ->> 'role' = 'service_role'
        OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'admin'
    );


-- ===================
-- 2. rente_kortingen
-- ===================
-- Per geldverstrekker de kortingen/opslagen bovenop het basistarief.
-- Elke bank heeft eigen kortingstypen (energielabel, betaalrekening, etc.)
--
-- Voorbeeld:
--   ING | Hypotheek | energielabel | {"A++++": -0.20, "A": -0.20, "B": -0.12, "C": -0.06, "D": -0.03}
--   ING | Hypotheek | betaalrekening | {"ja": -0.25, "nee": 0}
--   ABN AMRO | Budget Hypotheek | duurzaamheid | {"A": -0.15, "B": -0.10}

CREATE TABLE IF NOT EXISTS rente_kortingen (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    geldverstrekker TEXT NOT NULL,
    productlijn     TEXT NOT NULL,
    korting_type    TEXT NOT NULL,                 -- 'energielabel', 'betaalrekening', 'duurzaamheid', etc.
    staffel         JSONB NOT NULL DEFAULT '{}',  -- {"A++++": -0.20, "B": -0.12, ...}
    omschrijving    TEXT,                          -- Vrije toelichting, bijv. "Actieve Betaalrekening Korting"
    peildatum       DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (geldverstrekker, productlijn, korting_type, peildatum)
);

CREATE INDEX IF NOT EXISTS idx_kortingen_lookup
    ON rente_kortingen (geldverstrekker, productlijn, peildatum DESC);

CREATE TRIGGER trg_rente_kortingen_updated_at
    BEFORE UPDATE ON rente_kortingen
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- RLS (zelfde als hypotheekrentes)
ALTER TABLE rente_kortingen ENABLE ROW LEVEL SECURITY;

CREATE POLICY "rente_kortingen_select"
    ON rente_kortingen FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "rente_kortingen_insert"
    ON rente_kortingen FOR INSERT
    TO authenticated
    WITH CHECK (
        auth.jwt() ->> 'role' = 'service_role'
        OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'admin'
    );

CREATE POLICY "rente_kortingen_update"
    ON rente_kortingen FOR UPDATE
    TO authenticated
    USING (
        auth.jwt() ->> 'role' = 'service_role'
        OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'admin'
    );

CREATE POLICY "rente_kortingen_delete"
    ON rente_kortingen FOR DELETE
    TO authenticated
    USING (
        auth.jwt() ->> 'role' = 'service_role'
        OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'admin'
    );
