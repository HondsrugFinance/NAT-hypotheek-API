-- =============================================================================
-- Migratie: Document Processing Pipeline
-- Datum: 2026-03-26
-- =============================================================================

-- Documents tabel uitbreiden voor OCR en classificatie resultaten
ALTER TABLE public.documents
  ADD COLUMN IF NOT EXISTS ocr_text TEXT,
  ADD COLUMN IF NOT EXISTS ocr_page_count INTEGER,
  ADD COLUMN IF NOT EXISTS classification_confidence REAL,
  ADD COLUMN IF NOT EXISTS classification_reasoning TEXT,
  ADD COLUMN IF NOT EXISTS processing_error TEXT,
  ADD COLUMN IF NOT EXISTS processing_duration_ms INTEGER,
  ADD COLUMN IF NOT EXISTS original_bestandsnaam TEXT;

-- Status uitbreiden met 'processing' en 'error'
ALTER TABLE public.documents DROP CONSTRAINT IF EXISTS documents_status_check;
ALTER TABLE public.documents
  ADD CONSTRAINT documents_status_check
  CHECK (status IN ('pending', 'processing', 'classified', 'extracted', 'reviewed', 'error'));

-- Index voor snelle lookup op extract_type + persoon (priority resolution)
CREATE INDEX IF NOT EXISTS idx_extracted_data_type_persoon
  ON public.extracted_data(dossier_id, extract_type, persoon);
