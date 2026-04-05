-- =============================================================================
-- Import cache: check_vragen kolom toevoegen (gelaagd import systeem)
-- =============================================================================
-- Slaat checkvragen op voor onzekere velden (inkomen keuze, geldverstrekker, etc.)
-- Frontend toont deze als keuzevragen aan de adviseur vóór prefill.

ALTER TABLE public.import_cache
  ADD COLUMN IF NOT EXISTS check_vragen JSONB NOT NULL DEFAULT '[]'::jsonb;

COMMENT ON COLUMN public.import_cache.check_vragen IS
  'Checkvragen voor onzekere velden — adviseur beantwoordt deze vóór prefill';
