-- =============================================================================
-- Migratie: Document Processing V2 — 3-stappen extractie
-- Datum: 2026-03-26
-- =============================================================================

-- 1. document_extractions — Stap 1: volledige ruwe tekst per document
--    "Vertel me alles" — doorzoekbaar, chatbot, archief
CREATE TABLE IF NOT EXISTS public.document_extractions (
  id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  dossier_id      UUID NOT NULL REFERENCES public.dossiers(id) ON DELETE CASCADE,
  document_id     UUID NOT NULL REFERENCES public.documents(id) ON DELETE CASCADE,
  document_type   TEXT,
  persoon         TEXT DEFAULT 'gezamenlijk'
    CHECK (persoon IN ('aanvrager', 'partner', 'gezamenlijk')),

  -- Classificatie (uit stap 1)
  classification  JSONB NOT NULL DEFAULT '{}'::jsonb,
  -- Volledige ruwe extractie (alles wat Claude ziet)
  raw_text        TEXT,
  raw_data        JSONB NOT NULL DEFAULT '{}'::jsonb,

  -- Meta
  input_method    TEXT NOT NULL DEFAULT 'vision'
    CHECK (input_method IN ('pdf_text', 'vision', 'azure_di')),
  confidence      REAL CHECK (confidence >= 0 AND confidence <= 1),
  warnings        JSONB DEFAULT '[]'::jsonb,
  duration_ms     INTEGER,

  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_doc_extractions_dossier ON public.document_extractions(dossier_id);
CREATE INDEX idx_doc_extractions_document ON public.document_extractions(document_id);
CREATE INDEX idx_doc_extractions_type ON public.document_extractions(document_type);

CREATE TRIGGER trg_doc_extractions_updated
  BEFORE UPDATE ON public.document_extractions
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.document_extractions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "doc_extractions_select" ON public.document_extractions FOR SELECT TO authenticated USING (true);
CREATE POLICY "doc_extractions_insert" ON public.document_extractions FOR INSERT TO authenticated
  WITH CHECK (public.get_user_role() IN ('admin', 'adviseur'));
CREATE POLICY "doc_extractions_update" ON public.document_extractions FOR UPDATE TO authenticated
  USING (dossier_id IN (SELECT id FROM public.dossiers WHERE owner_id = auth.uid()) OR public.get_user_role() = 'admin');
CREATE POLICY "doc_extractions_delete" ON public.document_extractions FOR DELETE TO authenticated
  USING (dossier_id IN (SELECT id FROM public.dossiers WHERE owner_id = auth.uid()) OR public.get_user_role() = 'admin');


-- 2. extracted_fields — Stap 2: gestructureerde velden per document
--    Vaste veldnamen, klaar om naar aanvraag te importeren
CREATE TABLE IF NOT EXISTS public.extracted_fields (
  id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  dossier_id      UUID NOT NULL REFERENCES public.dossiers(id) ON DELETE CASCADE,
  document_id     UUID NOT NULL REFERENCES public.documents(id) ON DELETE CASCADE,
  extraction_id   UUID REFERENCES public.document_extractions(id) ON DELETE CASCADE,
  persoon         TEXT DEFAULT 'gezamenlijk'
    CHECK (persoon IN ('aanvrager', 'partner', 'gezamenlijk')),

  -- Sectie in de aanvraag (matcht met frontend)
  sectie          TEXT NOT NULL,
  -- Gestructureerde velden met vaste namen
  fields          JSONB NOT NULL DEFAULT '{}'::jsonb,
  -- Confidence per veld (optioneel)
  field_confidence JSONB DEFAULT '{}'::jsonb,

  -- Review status
  status          TEXT NOT NULL DEFAULT 'pending_review'
    CHECK (status IN ('pending_review', 'accepted', 'rejected', 'superseded', 'imported')),
  reviewed_by     UUID REFERENCES auth.users(id),
  reviewed_at     TIMESTAMPTZ,
  imported_at     TIMESTAMPTZ,

  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_extracted_fields_dossier ON public.extracted_fields(dossier_id);
CREATE INDEX idx_extracted_fields_document ON public.extracted_fields(document_id);
CREATE INDEX idx_extracted_fields_status ON public.extracted_fields(status);
CREATE INDEX idx_extracted_fields_sectie ON public.extracted_fields(dossier_id, sectie, persoon);

CREATE TRIGGER trg_extracted_fields_updated
  BEFORE UPDATE ON public.extracted_fields
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.extracted_fields ENABLE ROW LEVEL SECURITY;
CREATE POLICY "extracted_fields_select" ON public.extracted_fields FOR SELECT TO authenticated USING (true);
CREATE POLICY "extracted_fields_insert" ON public.extracted_fields FOR INSERT TO authenticated
  WITH CHECK (public.get_user_role() IN ('admin', 'adviseur'));
CREATE POLICY "extracted_fields_update" ON public.extracted_fields FOR UPDATE TO authenticated
  USING (dossier_id IN (SELECT id FROM public.dossiers WHERE owner_id = auth.uid()) OR public.get_user_role() = 'admin');
CREATE POLICY "extracted_fields_delete" ON public.extracted_fields FOR DELETE TO authenticated
  USING (dossier_id IN (SELECT id FROM public.dossiers WHERE owner_id = auth.uid()) OR public.get_user_role() = 'admin');


-- 3. dossier_analysis — Stap 3: dossier-brede analyse
--    Inconsistenties, suggesties, compleetheid
CREATE TABLE IF NOT EXISTS public.dossier_analysis (
  id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  dossier_id      UUID NOT NULL REFERENCES public.dossiers(id) ON DELETE CASCADE,

  -- Analyse resultaat
  compleetheid    JSONB NOT NULL DEFAULT '{}'::jsonb,
  inconsistenties JSONB DEFAULT '[]'::jsonb,
  suggesties      JSONB DEFAULT '[]'::jsonb,
  ontbrekende_documenten JSONB DEFAULT '[]'::jsonb,
  samenvatting    TEXT,

  -- Inkomensvergelijking
  inkomen_analyse JSONB DEFAULT '{}'::jsonb,

  -- Versie (wordt bij elk nieuw document overschreven)
  documenten_verwerkt INTEGER DEFAULT 0,
  confidence      REAL CHECK (confidence >= 0 AND confidence <= 1),
  duration_ms     INTEGER,

  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_dossier_analysis_dossier ON public.dossier_analysis(dossier_id);

CREATE TRIGGER trg_dossier_analysis_updated
  BEFORE UPDATE ON public.dossier_analysis
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.dossier_analysis ENABLE ROW LEVEL SECURITY;
CREATE POLICY "dossier_analysis_select" ON public.dossier_analysis FOR SELECT TO authenticated USING (true);
CREATE POLICY "dossier_analysis_insert" ON public.dossier_analysis FOR INSERT TO authenticated
  WITH CHECK (public.get_user_role() IN ('admin', 'adviseur'));
CREATE POLICY "dossier_analysis_update" ON public.dossier_analysis FOR UPDATE TO authenticated
  USING (dossier_id IN (SELECT id FROM public.dossiers WHERE owner_id = auth.uid()) OR public.get_user_role() = 'admin');
CREATE POLICY "dossier_analysis_delete" ON public.dossier_analysis FOR DELETE TO authenticated
  USING (dossier_id IN (SELECT id FROM public.dossiers WHERE owner_id = auth.uid()) OR public.get_user_role() = 'admin');
