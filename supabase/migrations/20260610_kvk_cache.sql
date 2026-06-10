-- ============================================================
-- Woningcheck: KVK details-cache
-- Datum: 2026-06-10
-- ============================================================
-- Doel: opgehaalde KVK-inschrijvingdetails (EUR 0,04/call) hergebruiken.
-- Bij een adrescheck zoekt de backend eerst hier op kvk_nummer +
-- vestigingsnummer; een hit betekent geen nieuwe betaalde KVK-call.

CREATE TABLE IF NOT EXISTS kvk_cache (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    kvk_nummer      TEXT NOT NULL,
    -- Lege string i.p.v. NULL: anders telt de UNIQUE-constraint NULLs als verschillend.
    vestigingsnummer TEXT NOT NULL DEFAULT '',
    naam            TEXT,                          -- snelle herkenning bij debuggen
    details         JSONB NOT NULL,                -- volledige details-payload zoals teruggegeven aan frontend
    opgehaald_door  TEXT,                          -- origin/adviseur die de eerste call deed (optioneel)
    opgehaald_op    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (kvk_nummer, vestigingsnummer)
);

CREATE INDEX IF NOT EXISTS idx_kvk_cache_lookup
    ON kvk_cache (kvk_nummer, vestigingsnummer);

-- opgehaald_op altijd op NOW() zetten, ook bij upsert (merge-duplicates).
CREATE OR REPLACE FUNCTION set_kvk_cache_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.opgehaald_op = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_kvk_cache_timestamp ON kvk_cache;
CREATE TRIGGER trg_kvk_cache_timestamp
    BEFORE INSERT OR UPDATE ON kvk_cache
    FOR EACH ROW
    EXECUTE FUNCTION set_kvk_cache_timestamp();

-- RLS: lezen mag iedere ingelogde gebruiker; schrijven alleen de backend (service_role).
ALTER TABLE kvk_cache ENABLE ROW LEVEL SECURITY;

CREATE POLICY "kvk_cache_select"
    ON kvk_cache FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "kvk_cache_insert"
    ON kvk_cache FOR INSERT
    TO authenticated
    WITH CHECK (auth.jwt() ->> 'role' = 'service_role');

CREATE POLICY "kvk_cache_update"
    ON kvk_cache FOR UPDATE
    TO authenticated
    USING (auth.jwt() ->> 'role' = 'service_role');
