-- ============================================================
-- C4.2: scraper_credentials tabel voor auto token-refresh
-- Datum: 2026-05-18
-- ============================================================
-- Eén rij per bron. Bij token-expiry (403) doet de scraper een
-- Playwright login, slaat de nieuwe token hier op, en retried.
-- Overleeft Render redeploys (env vars zouden statisch zijn).

CREATE TABLE IF NOT EXISTS public.scraper_credentials (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    bron            TEXT NOT NULL UNIQUE,            -- 'fastlane'
    auth_token      TEXT NOT NULL,
    user_hash       TEXT,
    refreshed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    refresh_count   INTEGER NOT NULL DEFAULT 1,
    last_used_at    TIMESTAMPTZ DEFAULT NOW(),
    last_403_at     TIMESTAMPTZ,
    notes           TEXT
);

CREATE INDEX IF NOT EXISTS idx_scraper_credentials_bron
    ON public.scraper_credentials (bron);

-- RLS: alleen service role
ALTER TABLE public.scraper_credentials ENABLE ROW LEVEL SECURITY;

CREATE POLICY "scraper_credentials_service_role_all"
    ON public.scraper_credentials
    FOR ALL
    USING (auth.jwt() ->> 'role' = 'service_role')
    WITH CHECK (auth.jwt() ->> 'role' = 'service_role');
