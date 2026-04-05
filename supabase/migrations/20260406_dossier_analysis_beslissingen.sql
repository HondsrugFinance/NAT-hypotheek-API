-- =============================================================================
-- Dossier analysis: beslissingen kolom (gelaagd import v2)
-- =============================================================================
-- Keuzemomenten geïdentificeerd door AI-analyse (stap 3).
-- Bijv. welk inkomen (WGV vs IBL), welke geldverstrekker, doelstelling.
-- Frontend toont deze als checkvragen aan de adviseur.

ALTER TABLE public.dossier_analysis
  ADD COLUMN IF NOT EXISTS beslissingen JSONB NOT NULL DEFAULT '[]'::jsonb;

COMMENT ON COLUMN public.dossier_analysis.beslissingen IS
  'AI-geïdentificeerde keuzemomenten — adviseur beantwoordt deze bij prefill';
