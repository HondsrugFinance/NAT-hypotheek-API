-- Email intake log — track verwerkte emails om duplicaten te voorkomen
CREATE TABLE IF NOT EXISTS public.email_intake_log (
    id                UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    message_id        TEXT NOT NULL,
    sender_email      TEXT NOT NULL,
    subject           TEXT,
    dossier_id        UUID REFERENCES public.dossiers(id),
    status            TEXT NOT NULL DEFAULT 'processed'
        CHECK (status IN ('processed', 'unmatched', 'error', 'skipped')),
    attachments_count INTEGER DEFAULT 0,
    error_message     TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Uniek op message_id om dubbele verwerking te voorkomen
CREATE UNIQUE INDEX IF NOT EXISTS idx_email_intake_log_message_id
    ON public.email_intake_log(message_id);

-- Zoeken op afzender
CREATE INDEX IF NOT EXISTS idx_email_intake_log_sender
    ON public.email_intake_log(sender_email);

-- Zoeken op dossier
CREATE INDEX IF NOT EXISTS idx_email_intake_log_dossier
    ON public.email_intake_log(dossier_id);

-- RLS: service role heeft volledige toegang
ALTER TABLE public.email_intake_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access" ON public.email_intake_log
    FOR ALL USING (auth.role() = 'service_role');
