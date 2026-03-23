-- =============================================================================
-- Migratie: Automatisering Fundament (Fase 1)
-- Datum: 2026-03-23
-- Doel: Nieuwe tabellen voor document management, communicatie, taken en
--       statuslogging. Plus dossiernummer auto-increment op dossiers.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. Dossiers uitbreiden: dossiernummer + status + SharePoint + contact
-- ---------------------------------------------------------------------------

-- Functie: genereer dossiernummer in formaat "2026-0001"
CREATE OR REPLACE FUNCTION public.generate_dossiernummer()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
  jaar TEXT;
  volgnr INT;
BEGIN
  jaar := to_char(now(), 'YYYY');
  SELECT COALESCE(MAX(
    CAST(split_part(dossiernummer, '-', 2) AS INT)
  ), 0) + 1 INTO volgnr
  FROM public.dossiers
  WHERE dossiernummer LIKE jaar || '-%';

  NEW.dossiernummer := jaar || '-' || lpad(volgnr::text, 4, '0');
  RETURN NEW;
END;
$$;

-- Nieuwe kolommen
ALTER TABLE public.dossiers
  ADD COLUMN IF NOT EXISTS dossiernummer TEXT UNIQUE,
  ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'orientatie'
    CHECK (status IN (
      'orientatie', 'documenten_verzamelen', 'berekening',
      'aanvraag', 'offerte', 'passeren', 'nazorg', 'afgerond'
    )),
  ADD COLUMN IF NOT EXISTS sharepoint_url TEXT,
  ADD COLUMN IF NOT EXISTS klant_email TEXT,
  ADD COLUMN IF NOT EXISTS klant_telefoon TEXT;

-- Auto-genereer dossiernummer bij INSERT (alleen als het leeg is)
CREATE TRIGGER trg_generate_dossiernummer
  BEFORE INSERT ON public.dossiers
  FOR EACH ROW
  WHEN (NEW.dossiernummer IS NULL)
  EXECUTE FUNCTION public.generate_dossiernummer();

CREATE INDEX IF NOT EXISTS idx_dossiers_status ON public.dossiers(status);
CREATE INDEX IF NOT EXISTS idx_dossiers_klant_email ON public.dossiers(klant_email);
CREATE INDEX IF NOT EXISTS idx_dossiers_dossiernummer ON public.dossiers(dossiernummer);

-- Optioneel: bestaande dossiers nummeren (op volgorde van aanmaakdatum)
-- Uncomment als je bestaande dossiers wilt nummeren:
-- WITH numbered AS (
--   SELECT id, ROW_NUMBER() OVER (ORDER BY aanmaak_datum) AS rn
--   FROM public.dossiers WHERE dossiernummer IS NULL
-- )
-- UPDATE public.dossiers d SET dossiernummer = '2026-' || lpad(n.rn::text, 4, '0')
-- FROM numbered n WHERE d.id = n.id;


-- ---------------------------------------------------------------------------
-- 2. Documents tabel — registry van alle documenten per dossier
-- ---------------------------------------------------------------------------

CREATE TABLE public.documents (
  id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  dossier_id      UUID NOT NULL REFERENCES public.dossiers(id) ON DELETE CASCADE,
  bestandsnaam    TEXT NOT NULL,
  document_type   TEXT,
  categorie       TEXT NOT NULL DEFAULT 'Overig'
    CHECK (categorie IN ('Identificatie', 'Inkomen', 'Woning', 'Financieel', 'Overig')),
  sharepoint_pad  TEXT,
  bron            TEXT NOT NULL DEFAULT 'upload'
    CHECK (bron IN ('email', 'upload', 'whatsapp', 'api')),
  status          TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'classified', 'extracted', 'reviewed')),
  persoon         TEXT DEFAULT 'gezamenlijk'
    CHECK (persoon IN ('aanvrager', 'partner', 'gezamenlijk')),
  geldigheid_maanden INTEGER,
  verloopdatum    DATE,
  mime_type       TEXT,
  bestandsgrootte INTEGER,
  uploaded_by     UUID REFERENCES auth.users(id),
  uploaded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  processed_at    TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_documents_dossier_id ON public.documents(dossier_id);
CREATE INDEX idx_documents_status ON public.documents(status);

CREATE TRIGGER trg_documents_updated_at
  BEFORE UPDATE ON public.documents
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY;

CREATE POLICY "documents_select_all_authenticated"
  ON public.documents FOR SELECT TO authenticated USING (true);

CREATE POLICY "documents_insert_admin_adviseur"
  ON public.documents FOR INSERT TO authenticated
  WITH CHECK (public.get_user_role() IN ('admin', 'adviseur'));

CREATE POLICY "documents_update_owner_or_admin"
  ON public.documents FOR UPDATE TO authenticated
  USING (dossier_id IN (SELECT id FROM public.dossiers WHERE owner_id = auth.uid())
    OR public.get_user_role() = 'admin');

CREATE POLICY "documents_delete_owner_or_admin"
  ON public.documents FOR DELETE TO authenticated
  USING (dossier_id IN (SELECT id FROM public.dossiers WHERE owner_id = auth.uid())
    OR public.get_user_role() = 'admin');


-- ---------------------------------------------------------------------------
-- 3. Extracted Data tabel — AI-geëxtraheerde vergaarbak
-- ---------------------------------------------------------------------------

CREATE TABLE public.extracted_data (
  id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  dossier_id      UUID NOT NULL REFERENCES public.dossiers(id) ON DELETE CASCADE,
  document_id     UUID NOT NULL REFERENCES public.documents(id) ON DELETE CASCADE,
  extract_type    TEXT NOT NULL,
  persoon         TEXT DEFAULT 'gezamenlijk'
    CHECK (persoon IN ('aanvrager', 'partner', 'gezamenlijk')),
  raw_values      JSONB NOT NULL DEFAULT '{}'::jsonb,
  computed_values JSONB NOT NULL DEFAULT '{}'::jsonb,
  confidence      REAL CHECK (confidence >= 0 AND confidence <= 1),
  status          TEXT NOT NULL DEFAULT 'pending_review'
    CHECK (status IN ('pending_review', 'accepted', 'rejected', 'superseded')),
  reviewed_by     UUID REFERENCES auth.users(id),
  reviewed_at     TIMESTAMPTZ,
  notes           TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_extracted_data_dossier_id ON public.extracted_data(dossier_id);
CREATE INDEX idx_extracted_data_document_id ON public.extracted_data(document_id);
CREATE INDEX idx_extracted_data_status ON public.extracted_data(status);

CREATE TRIGGER trg_extracted_data_updated_at
  BEFORE UPDATE ON public.extracted_data
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.extracted_data ENABLE ROW LEVEL SECURITY;

CREATE POLICY "extracted_data_select_all_authenticated"
  ON public.extracted_data FOR SELECT TO authenticated USING (true);

CREATE POLICY "extracted_data_insert_admin_adviseur"
  ON public.extracted_data FOR INSERT TO authenticated
  WITH CHECK (public.get_user_role() IN ('admin', 'adviseur'));

CREATE POLICY "extracted_data_update_owner_or_admin"
  ON public.extracted_data FOR UPDATE TO authenticated
  USING (dossier_id IN (SELECT id FROM public.dossiers WHERE owner_id = auth.uid())
    OR public.get_user_role() = 'admin');

CREATE POLICY "extracted_data_delete_owner_or_admin"
  ON public.extracted_data FOR DELETE TO authenticated
  USING (dossier_id IN (SELECT id FROM public.dossiers WHERE owner_id = auth.uid())
    OR public.get_user_role() = 'admin');


-- ---------------------------------------------------------------------------
-- 4. Communications tabel — alle contactmomenten (append-only log)
-- ---------------------------------------------------------------------------

CREATE TABLE public.communications (
  id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  dossier_id      UUID NOT NULL REFERENCES public.dossiers(id) ON DELETE CASCADE,
  type            TEXT NOT NULL
    CHECK (type IN ('email_in', 'email_out', 'whatsapp_in', 'whatsapp_out',
                    'telefoon', 'face_to_face', 'notitie')),
  onderwerp       TEXT,
  inhoud          TEXT,
  van             TEXT,
  aan             TEXT,
  extern_id       TEXT,
  bijlagen        JSONB DEFAULT '[]'::jsonb,
  adviseur_id     UUID REFERENCES auth.users(id),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_communications_dossier_id ON public.communications(dossier_id);
CREATE INDEX idx_communications_extern_id ON public.communications(extern_id);

ALTER TABLE public.communications ENABLE ROW LEVEL SECURITY;

CREATE POLICY "communications_select_all_authenticated"
  ON public.communications FOR SELECT TO authenticated USING (true);

CREATE POLICY "communications_insert_admin_adviseur"
  ON public.communications FOR INSERT TO authenticated
  WITH CHECK (public.get_user_role() IN ('admin', 'adviseur'));

CREATE POLICY "communications_delete_admin_only"
  ON public.communications FOR DELETE TO authenticated
  USING (public.get_user_role() = 'admin');


-- ---------------------------------------------------------------------------
-- 5. Tasks tabel — taken per dossier
-- ---------------------------------------------------------------------------

CREATE TABLE public.tasks (
  id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  dossier_id      UUID NOT NULL REFERENCES public.dossiers(id) ON DELETE CASCADE,
  titel           TEXT NOT NULL,
  beschrijving    TEXT,
  status          TEXT NOT NULL DEFAULT 'open'
    CHECK (status IN ('open', 'in_progress', 'done')),
  prioriteit      TEXT NOT NULL DEFAULT 'medium'
    CHECK (prioriteit IN ('low', 'medium', 'high', 'urgent')),
  toegewezen_aan  UUID REFERENCES auth.users(id),
  deadline        DATE,
  created_by      UUID REFERENCES auth.users(id),
  completed_at    TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_tasks_dossier_id ON public.tasks(dossier_id);
CREATE INDEX idx_tasks_status ON public.tasks(status);
CREATE INDEX idx_tasks_toegewezen_aan ON public.tasks(toegewezen_aan);

CREATE TRIGGER trg_tasks_updated_at
  BEFORE UPDATE ON public.tasks
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.tasks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "tasks_select_all_authenticated"
  ON public.tasks FOR SELECT TO authenticated USING (true);

CREATE POLICY "tasks_insert_admin_adviseur"
  ON public.tasks FOR INSERT TO authenticated
  WITH CHECK (public.get_user_role() IN ('admin', 'adviseur'));

CREATE POLICY "tasks_update_all_authenticated"
  ON public.tasks FOR UPDATE TO authenticated USING (true);

CREATE POLICY "tasks_delete_owner_or_admin"
  ON public.tasks FOR DELETE TO authenticated
  USING (created_by = auth.uid() OR public.get_user_role() = 'admin');


-- ---------------------------------------------------------------------------
-- 6. Dossier Status Log — immutable statuswijzigingen
-- ---------------------------------------------------------------------------

CREATE TABLE public.dossier_status_log (
  id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  dossier_id      UUID NOT NULL REFERENCES public.dossiers(id) ON DELETE CASCADE,
  oude_status     TEXT,
  nieuwe_status   TEXT NOT NULL,
  reden           TEXT,
  gewijzigd_door  UUID REFERENCES auth.users(id),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_dossier_status_log_dossier_id ON public.dossier_status_log(dossier_id);

ALTER TABLE public.dossier_status_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "dossier_status_log_select_all_authenticated"
  ON public.dossier_status_log FOR SELECT TO authenticated USING (true);

CREATE POLICY "dossier_status_log_insert_admin_adviseur"
  ON public.dossier_status_log FOR INSERT TO authenticated
  WITH CHECK (public.get_user_role() IN ('admin', 'adviseur'));


-- ---------------------------------------------------------------------------
-- 7. Automatische status-log trigger op dossiers
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.log_dossier_status_change()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
  IF OLD.status IS DISTINCT FROM NEW.status THEN
    INSERT INTO public.dossier_status_log (dossier_id, oude_status, nieuwe_status, gewijzigd_door)
    VALUES (NEW.id, OLD.status, NEW.status, auth.uid());
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_dossier_status_change
  AFTER UPDATE ON public.dossiers
  FOR EACH ROW EXECUTE FUNCTION public.log_dossier_status_change();
