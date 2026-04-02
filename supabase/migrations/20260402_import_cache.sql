-- =============================================================================
-- Import cache: Claude smart mapping resultaat per dossier + context
-- =============================================================================
-- Eén row per (dossier_id, context). Wordt automatisch gevuld na
-- documentverwerking. Frontend leest hieruit (instant, geen Claude call).

CREATE TABLE IF NOT EXISTS public.import_cache (
  id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  dossier_id      UUID NOT NULL REFERENCES public.dossiers(id) ON DELETE CASCADE,
  context         TEXT NOT NULL CHECK (context IN ('berekening', 'aanvraag')),
  merged_data     JSONB NOT NULL DEFAULT '{}'::jsonb,
  velden          JSONB NOT NULL DEFAULT '[]'::jsonb,
  groups          JSONB NOT NULL DEFAULT '[]'::jsonb,
  samenvatting    JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

  UNIQUE (dossier_id, context)
);

CREATE INDEX idx_import_cache_dossier ON public.import_cache(dossier_id);

-- Auto-update updated_at
CREATE TRIGGER update_import_cache_updated_at
  BEFORE UPDATE ON public.import_cache
  FOR EACH ROW EXECUTE FUNCTION public.update_laatst_gewijzigd_column();

-- RLS
ALTER TABLE public.import_cache ENABLE ROW LEVEL SECURITY;

CREATE POLICY "import_cache_select" ON public.import_cache
  FOR SELECT TO authenticated USING (true);

CREATE POLICY "import_cache_service_role" ON public.import_cache
  FOR ALL USING (auth.jwt() ->> 'role' = 'service_role');
