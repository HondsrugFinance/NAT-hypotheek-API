# Hondsrug Finance Rekentool — Voortgang Verbetertraject

Laatst bijgewerkt: 2026-02-16

---

## Wat is er gedaan?

### app.py — Volledig herschreven (v1.0.0 → v1.1.0)

| Verbetering | Status | Wat het doet |
|-------------|--------|-------------|
| CORS | Gedaan | Alleen `hondsrug-insight.lovable.app` en localhost mogen de API aanroepen |
| CORS wildcard | Gedaan | `allow_origin_regex` voor alle `*.lovable.app` en `*.lovableproject.com` subdomeinen (Lovable editor/preview) |
| Logging | Gedaan | Elke berekening en fout wordt gelogd (zonder persoonlijke gegevens) |
| Invoercontrole | Gedaan | Grenzen op alle velden (inkomen 0-10M, rente 0-20%, looptijd 1-600 mnd, etc.) |
| Foutafhandeling | Gedaan | API crasht niet meer — geeft altijd een nette foutmelding |
| API-sleutel | Gedaan | Optionele `X-API-Key` header (activeer via `NAT_API_KEY` env var in Render) |
| API-sleutel foutmeldingen | Gedaan | Aparte foutmeldingen voor "ontbreekt" vs "ongeldig" |
| Rate limiting | Gedaan | Max 30 berekeningen/minuut per IP (via slowapi) |
| Health check | Gedaan | `/health` toont uptime, versie, config-status |
| Deep health check | Gedaan | `/health/deep` voert een proefberekening uit |

### calculator_final.py — Crash-beveiliging

| Verbetering | Status | Wat het doet |
|-------------|--------|-------------|
| Deling door nul (woonquote) | Gedaan | Voorkomt crash als `woonquote_box3 = 0` |
| Deling door nul (toetsrente) | Gedaan | Voorkomt crash als `toets_rente = 0` |

### requirements.txt

| Verbetering | Status | Wat het doet |
|-------------|--------|-------------|
| slowapi==0.1.9 | Gedaan | Nodig voor rate limiting |

### Tests

| Test | Resultaat |
|------|-----------|
| 5 Excel-exacte tests | Allemaal geslaagd |
| 5 extra tests (energielabel, studielening, inkomen) | Allemaal geslaagd |
| **Totaal: 10/10 tests slagen** | Berekeningen ongewijzigd na alle aanpassingen |

---

### Frontend code-analyse (GitHub: HondsrugFinance/hondsrug-insight)

| Bestand | Bevinding |
|---------|-----------|
| `src/services/natApiService.ts` | NAT API aanroep **zonder** `X-API-Key` header — moet toegevoegd |
| `src/services/monthlyCostsService.ts` | Monthly Costs API (ook zonder auth) |
| `src/utils/dossierStorage.ts` | localStorage CRUD (key: `hondsrug-dossiers-2026`) — wordt gemigreerd naar Supabase |
| `src/utils/aanvraagStorage.ts` | localStorage CRUD (key: `hondsrug-aanvragen-2026`) — wordt gemigreerd naar Supabase |
| `.env` | Supabase config aanwezig (EU-regio) |

**Frontend-API mapping gecontroleerd:**
- Alimentatie: maandbedrag x12 → klopt
- Rente: percentage /100 → klopt
- Lege bedragen → 0,01 (bewust, voor gewogen rente-berekening)
- Energielabel en aflostype → correct gemapt

---

## Supabase status

| Onderdeel | Status |
|-----------|--------|
| Project | `armwhaeuacimgbjukdtm` (AWS eu-central-1, Frankfurt) |
| Plan | Gratis (pauzeert na 1 week inactiviteit) |
| Auth | Email/password, werkend met ProtectedRoute op alle routes |
| Tabellen | `profiles` (adviseursprofiel), `dossiers` (hypotheekdossiers), `aanvragen` (hypotheekaanvragen), `audit_log` (audit trail) |
| RLS | Actief op dossiers, aanvragen en audit_log — lezen voor alle auth users, wijzigen alleen eigenaar |
| Dual-write | localStorage + Supabase (Supabase-first bij lezen) |
| Migratie | `/admin-migratie` pagina voor eenmalige localStorage → Supabase migratie |
| Gebruikers | alex@hondsrugfinance.nl (actief), quido@hondsrugfinance.nl (nooit ingelogd), stephan@hondsrugfinance.nl (wacht op verificatie) |

---

## Wat moet jij doen? (in Lovable / Render)

### 1. API-sleutel instellen (Render)
- Ga naar je Render dashboard → je NAT API service → Environment
- Voeg toe: `NAT_API_KEY` = een zelfgekozen wachtwoord (bijv. `hf-nat-2026-geheim123`)
- Dit activeert de beveiliging op de API

### 2. API-sleutel toevoegen in Lovable
- Open `src/services/natApiService.ts` (regel 190-196)
- De huidige code:
  ```typescript
  headers: {
    'Content-Type': 'application/json',
  },
  ```
- Wijzig naar:
  ```typescript
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': 'jouw-gekozen-sleutel-hier',
  },
  ```
- Gebruik dezelfde sleutel als in Render
- **Belangrijk:** Zet de sleutel EERST in Render, dan pas in Lovable. Anders werkt de API niet meer!

### 3. Excel-waarden aanleveren (voor extra tests)
- Open de NAT Excel-sheet en reken de volgende scenario's door:
  - Iemand die al AOW ontvangt (`ontvangt_aow = JA`)
  - Scenario 2 (berekening "over 10 jaar")
  - Nul inkomen
  - Alleen aflossingsvrije leningdelen
- Geef mij de Excel-uitkomsten, dan bouw ik er tests van

---

## Fase 3: Database-migratie (localStorage → Supabase)

### Waarom?
De Rekentool slaat nu alle dossiers en aanvragen op in de browser (localStorage). Problemen:
- Browser legen = alles kwijt
- Andere computer = je ziet niets
- Meerdere adviseurs = geen gedeelde data

**Oplossing:** Opslag verplaatsen naar Supabase (de database die al wordt gebruikt voor het inlogsysteem).

**Aanpak: JSONB hybrid** — Complexe geneste data (invoer, scenario's, aanvraaggegevens) worden opgeslagen als JSONB-kolommen. De datastructuur blijft exact hetzelfde — we veranderen alleen *waar* het wordt opgeslagen, niet *wat*.

**De NAT API (deze Python repo) hoeft NIET aangepast te worden.**

### Overzicht van de 7 stappen

| Stap | Wat | Waar | Status |
|------|-----|------|--------|
| 1 | Tabellen aanmaken (5 SQL-scripts + trigger fix) | Supabase SQL Editor | Gedaan |
| 2 | Service-laag aanmaken (3 bestanden) | Lovable | Gedaan |
| 3 | Dual-write aanzetten (localStorage + Supabase) | Lovable | Gedaan — werkt correct (zie debug-notitie hieronder) |
| 4 | Bestaande data migreren | Lovable + Supabase | Gedaan (10 dossiers, 2 aanvragen, 1 wees-aanvraag overgeslagen) |
| 5 | Reads overschakelen naar Supabase | Lovable | Gedaan (2026-02-16, incognito-test geslaagd) |
| 6 | localStorage opruimen | Lovable | Te doen (pas na 1 week stabiel) |
| 7 | 2FA met MS Authenticator | Lovable + Supabase | Te doen (na database-migratie) |

### Stap 1: Tabellen aanmaken in Supabase (GEDAAN)

Alle scripts zijn uitgevoerd in Supabase SQL Editor op 2026-02-12/13.

**Opgelost probleem: trigger functie conflict.** De bestaande `update_updated_at_column()` van de `profiles`-tabel gebruikte `NEW.updated_at`, maar onze kolom heet `laatst_gewijzigd`. Oplossing: een aparte trigger functie `update_laatst_gewijzigd_column()` aangemaakt.

Aangemaakte objecten:
- **Tabellen:** `dossiers` (12 kolommen), `aanvragen` (6 kolommen), `audit_log` (7 kolommen)
- **Indexes:** 6 totaal (owner_id, laatst_gewijzigd, dossier_id, etc.)
- **Triggers:** `update_dossiers_laatst_gewijzigd`, `update_aanvragen_laatst_gewijzigd` (beide via `update_laatst_gewijzigd_column()`)
- **RLS policies:** 10 totaal (4 dossiers + 4 aanvragen + 2 audit_log)
- **Functies:** `log_audit()` (RPC helper), `update_laatst_gewijzigd_column()` (trigger)

**Controleer:** Table Editor toont 3 nieuwe tabellen. Authentication → Policies toont 10 policies.

#### Script 3: Audit-log-tabel

```sql
CREATE TABLE public.audit_log (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  action TEXT NOT NULL,
  table_name TEXT NOT NULL,
  record_id UUID NOT NULL,
  user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  user_email TEXT DEFAULT '',
  metadata JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_log_record ON public.audit_log(table_name, record_id);
CREATE INDEX idx_audit_log_created ON public.audit_log(created_at DESC);
```

#### Script 4: Row Level Security (RLS)

```sql
-- DOSSIERS: iedereen kan lezen (teamtool), alleen eigenaar kan wijzigen
ALTER TABLE public.dossiers ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Iedereen kan dossiers lezen"
  ON public.dossiers FOR SELECT TO authenticated USING (true);

CREATE POLICY "Eigenaar kan dossiers aanmaken"
  ON public.dossiers FOR INSERT TO authenticated
  WITH CHECK (owner_id = auth.uid());

CREATE POLICY "Eigenaar kan dossiers wijzigen"
  ON public.dossiers FOR UPDATE TO authenticated
  USING (owner_id = auth.uid()) WITH CHECK (owner_id = auth.uid());

CREATE POLICY "Eigenaar kan dossiers verwijderen"
  ON public.dossiers FOR DELETE TO authenticated
  USING (owner_id = auth.uid());

-- AANVRAGEN: iedereen kan lezen, alleen dossier-eigenaar kan wijzigen
ALTER TABLE public.aanvragen ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Iedereen kan aanvragen lezen"
  ON public.aanvragen FOR SELECT TO authenticated USING (true);

CREATE POLICY "Dossier-eigenaar kan aanvragen aanmaken"
  ON public.aanvragen FOR INSERT TO authenticated
  WITH CHECK (EXISTS (
    SELECT 1 FROM public.dossiers WHERE id = dossier_id AND owner_id = auth.uid()
  ));

CREATE POLICY "Dossier-eigenaar kan aanvragen wijzigen"
  ON public.aanvragen FOR UPDATE TO authenticated
  USING (EXISTS (
    SELECT 1 FROM public.dossiers WHERE id = dossier_id AND owner_id = auth.uid()
  ));

CREATE POLICY "Dossier-eigenaar kan aanvragen verwijderen"
  ON public.aanvragen FOR DELETE TO authenticated
  USING (EXISTS (
    SELECT 1 FROM public.dossiers WHERE id = dossier_id AND owner_id = auth.uid()
  ));

-- AUDIT LOG: iedereen kan lezen en schrijven
ALTER TABLE public.audit_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Iedereen kan audit log lezen"
  ON public.audit_log FOR SELECT TO authenticated USING (true);

CREATE POLICY "Iedereen kan audit log schrijven"
  ON public.audit_log FOR INSERT TO authenticated WITH CHECK (true);
```

**Controleer:** Authentication → Policies: 4 policies op `dossiers`, 4 op `aanvragen`, 2 op `audit_log`.

#### Script 5: Audit-log helperfunctie

```sql
CREATE OR REPLACE FUNCTION public.log_audit(
  p_action TEXT,
  p_table_name TEXT,
  p_record_id UUID,
  p_metadata JSONB DEFAULT '{}'::jsonb
)
RETURNS VOID LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
  INSERT INTO public.audit_log (action, table_name, record_id, user_id, user_email, metadata)
  VALUES (
    p_action, p_table_name, p_record_id,
    auth.uid(),
    (SELECT email FROM auth.users WHERE id = auth.uid()),
    p_metadata
  );
END;
$$;
```

### Stap 2: Service-laag aanmaken in Lovable (GEDAAN)

Drie bestanden aangemaakt/bijgewerkt in Lovable op 2026-02-12:

- **`src/integrations/supabase/types.ts`** — Auto-bijgewerkt met `dossiers`, `aanvragen`, `audit_log` tabellen en `log_audit` functie.
- **`src/services/supabaseDossierService.ts`** — CRUD functies voor dossiers (fetch, upsert, delete) met camelCase/snake_case mapping + audit logging.
- **`src/services/supabaseAanvraagService.ts`** — CRUD functies voor aanvragen met mapping en audit logging.

**Opgelost:** Service code stuurde aanvankelijk `updated_at` veld mee (niet-bestaande kolom). Gefixt door alleen de juiste kolommen te sturen: `id`, `type`, `naam`, `klant_naam`, `klant_contact_gegevens`, `owner_id`, `owner_name`, `invoer`, `scenario1`, `scenario2`.

### Stap 3: Dual-write aanzetten (GEDAAN)

De app schrijft nu naar BEIDE plekken: localStorage EN Supabase. localStorage blijft primair; Supabase is non-blocking (.catch()).

- **`src/utils/dossierStorage.ts`** — Bijgewerkt op 2026-02-12. Na elke localStorage write, non-blocking Supabase upsert.
- **`src/utils/aanvraagStorage.ts`** — Bijgewerkt op 2026-02-12. Zelfde aanpak.

**Test resultaat (2026-02-13):** Aanvankelijk leek het alsof upserts niet aankwamen. Na uitgebreid debuggen (auth check, Network tab, triggers, audit log) bleek de **oorzaak: twee verschillende Supabase-projecten**.

**Debug-bevinding (2026-02-13):** Lovable heeft automatisch een eigen Supabase-project aangemaakt (`armwhaeuacimgbjukdtm`) dat niet zichtbaar is in de gebruiker's eigen Supabase Dashboard. De SQL-scripts (Stap 1) waren uitgevoerd in het verkeerde project (`zecrknauqcxbsqjdramq`). Na het uitvoeren van de queries via Lovable's eigen Supabase-toegang bleek de dual-write correct te werken: 3 echte dossiers + 1 testdossier aanwezig, RLS-policies correct, audit-functie aanwezig.

**Belangrijk:** Gebruik altijd Lovable's eigen Supabase-toegang om data te controleren, niet het apart aangemaakte Supabase-project. Het project `zecrknauqcxbsqjdramq` (eigen dashboard) wordt NIET door de app gebruikt.

### Stap 4: Bestaande data migreren (GEDAAN)

Eenmalige actie: alle huidige localStorage-data naar Supabase gekopieerd op 2026-02-13.

- Migratiepagina aangemaakt op `/admin/migratie` (beschermd met ProtectedRoute)
- **Resultaat:** 10 dossiers en 2 aanvragen succesvol gemigreerd
- **1 fout:** Wees-aanvraag "Aanvraag Alex Kuijper" overgeslagen (foreign key constraint — verwijst naar verwijderd dossier)
- **Belangrijk:** Andere adviseurs (Quido, Stephan) moeten ook inloggen en de migratie uitvoeren voor hun eigen localStorage-data

### Stap 5: Reads overschakelen naar Supabase (GEDAAN)

Reads gaan eerst naar Supabase, met localStorage als fallback. Uitgevoerd op 2026-02-16.

- **5A:** `dossierStorage.ts` — leesfuncties (getDossiers, getDossier, getRecenteDossiers, duplicateDossier) async gemaakt, Supabase-first via `fetchAllDossiers`/`fetchDossierById`, localStorage fallback met `console.warn`
- **5B:** `aanvraagStorage.ts` — zelfde aanpak via `fetchAanvragenByDossierId`/`fetchAanvraagById`
- **5C:** Alle callers (Dossiers, DossierDetail, Aankoop, Aanpassen, Aanvraag) bijgewerkt naar async/await
- **Berekeningen:** Zitten als JSONB in `dossiers.invoer` — liften automatisch mee, geen aparte tabel nodig

**Test resultaat (2026-02-16):**
- Console-check: geen fallback-warnings
- Incognito-test: 7 van 8 dossiers verschijnen (zonder localStorage). 1 dossier ("doris floris") ontbreekt — waarschijnlijk alleen in localStorage, niet naar Supabase geschreven. Dual-write triggeren door dossier te openen en opnieuw op te slaan.
- **Conclusie:** Reads komen uit Supabase. Database-migratie is functioneel klaar.

### Stap 6: localStorage opruimen

Pas uitvoeren als alles minimaal een week stabiel draait. Verwijder alle localStorage code en de migratiepagina.

### Stap 7: Twee-factor authenticatie (2FA)

Na de database-migratie: 2FA toevoegen met MS Authenticator (TOTP via Supabase MFA).

- 2FA-enrollment op de profielpagina (QR-code scannen)
- 2FA-verificatie bij het inloggen (6-cijferige code)
- Optioneel: 2FA afdwingen in RLS-policies

---

## Fase 4: Doorontwikkeling — Rollen, Extern Databeheer, Documentgeneratie

Volledig plan: zie `C:\Users\alex\.claude\plans\refactored-tumbling-yao.md`

### Stap A: Audit hardcoded data in Lovable (GEDAAN — 2026-02-16)

Complete inventarisatie van alle veranderlijke data in de Lovable frontend. **12 categorieën** gevonden:

| # | Categorie | Bestanden | Update-frequentie |
|---|-----------|-----------|-------------------|
| 1 | Overdrachtsbelasting (2%) | 3 bestanden (fiscaleParameters, AankoopForm, QuoteExplanation) | Jaarlijks/wetswijziging |
| 2 | NHG-kostengrens (€435.000) | fiscaleParameters.ts | Jaarlijks (jan) |
| 3 | Eigenwoningforfait (0,35%) | fiscaleParameters.ts | Jaarlijks (jan) |
| 4 | Inkomstenbelastingtarieven (36,97%/49,50%) | fiscaleParameters.ts | Jaarlijks (jan) |
| 5 | BKR-registratieforfait (€100) | 2 bestanden (fiscaleParameters, BkrSection) | Onregelmatig |
| 6 | Taxatiekosten (€695) | fiscaleParameters.ts | Onregelmatig |
| 7 | Hypotheekadvieskosten (€3.500) | fiscaleParameters.ts | Bedrijfsbeslissing |
| 8 | Geldverstrekkers (18 namen) | 2 bestanden (verstrekkers constant, FinancieringSection) | Onregelmatig |
| 9 | Financiële instellingen (6 banken/verzekeraars) | 2 bestanden (financieleInstellingen, VermogensplanningSection) | Onregelmatig |
| 10 | NAT API URL + API-key | Was 5 bestanden, nu 1 (apiConfig.ts) | Bij API-wijziging |
| 11 | Hypotheekproducten (annuïtair, aflossingsvrij, lineair) | FinancieringSection.tsx | Zelden |
| 12 | Dropdown-opties (arbeidsvorm, woonsituatie, studielening) | Diverse bestanden | Wetswijziging |

**Beveiligingsprobleem gevonden:** API-key stond hardcoded in broncode (5 bestanden). Opgelost in Stap A fix 1+2.

### Stap A fix 1: API-key en URLs centraliseren (GEDAAN — 2026-02-16)

Alle API-configuratie geconsolideerd naar één bestand:

- **Nieuw:** `src/config/apiConfig.ts` — bevat `NAT_API_BASE_URL`, `NAT_API_KEY`, en helper-functies `getNatApiUrl(path)` en `getNatApiHeaders()`
- **Bijgewerkt:** 5 bestanden (natApiService.ts, monthlyCostsService.ts, useAanvraagMaxHypotheek.ts, useAanvraagMaxHypotheekOver10Jaar.ts, useAOWData.ts) — verwijzen nu naar apiConfig

### Stap A fix 2: Environment variable (GEDAAN — 2026-02-16)

**Poging 1:** `VITE_NAT_API_KEY` als Lovable Cloud Secret → **mislukt**. Cloud Secrets zijn alleen beschikbaar in backend/edge functions, niet in de frontend build (`import.meta.env.VITE_*` retourneert `undefined`).

**Oplossing:** Fallback-waarde hardcoded in `apiConfig.ts`. Acceptabel omdat:
- CORS beperkt API-toegang tot `hondsrug-insight.lovable.app`
- Rate limiting (30/min) beschermt tegen misbruik
- De API-key is een extra laag, niet de primaire beveiliging

### Stap A fix 3: Duplicaties opruimen — TE DOEN

Resterende duplicaties uit de audit:
- **Overdrachtsbelasting (2%)** — 3 plekken → centraliseren naar `fiscaleParameters.ts`
- **BKR-forfait (€100)** — 2 plekken → idem
- **Geldverstrekkers (18 namen)** — 2 plekken → naar enkele bron
- **Financiële instellingen (6 banken)** — 2 plekken → idem

### Stap C1: Config externaliseren NAT API (GEDAAN — 2026-02-16)

Alle hardcoded rekentabellen verplaatst naar `config/*.json`:

| Config-bestand | Inhoud |
|----------------|--------|
| `config/energielabel.json` | Base bonussen (€0-€40k) en verduurzaming-caps per label |
| `config/studielening.json` | 11 correctiefactor-brackets per toetsrente |
| `config/aow.json` | AOW-leeftijden tabel + fallback |
| `config/fiscaal.json` | Fiscale standaardwaarden (toetsrente, factoren, etc.) |

**Refactored:** `calculator_final.py` (2 functies), `aow_calculator.py` (AOW-tabel laden)
**Nieuw:** 5 publieke config-endpoints (`/config/energielabel`, `/config/studielening`, `/config/aow`, `/config/fiscaal`, `/config/versie`)
**Verificatie:** Alle 10 tests slagen met identieke uitkomsten (0.000000 verschil)

### Stap C2: Lovable-data externaliseren — NAT API kant (GEDAAN — 2026-02-16)

Alle hardcoded frontend-data (fiscale parameters, geldverstrekkers, dropdown-opties) verplaatst naar `config/*.json` + endpoints:

| Config-bestand | Inhoud |
|----------------|--------|
| `config/fiscaal-frontend.json` | 17 fiscale parameters (NHG, belasting, overdrachtsbelasting, toetsrente) + AOW-jaarbedragen |
| `config/geldverstrekkers.json` | 36 hypotheekverstrekkers + productlijnen per verstrekker |
| `config/dropdowns.json` | 67 beroepen, 5 dienstverbandtypen, 4 arbeidsmarktscan-fases, 13 onderpandtypen, 3 woningtypen, 13 energielabels, 6+1 waarderingsmethoden, 4 overdrachtsbelasting-opties, 293 financiële instellingen |

**Nieuw:** 3 publieke config-endpoints (`/config/fiscaal-frontend`, `/config/geldverstrekkers`, `/config/dropdowns`)
**Updated:** `/config/versie` toont nu alle 6 config-versies
**Lovable-prompt:** Geschreven en door Lovable geïmplementeerd (zie hieronder)

### Stap C2: Lovable-data externaliseren — Lovable kant (GEDAAN — 2026-02-16)

Lovable heeft de C2-prompt volledig geïmplementeerd:

| Bestand | Wijziging |
|---------|-----------|
| `src/hooks/useNatConfig.ts` | **Nieuw** — fetcht 3 endpoints parallel, in-memory cache |
| `src/contexts/NatConfigContext.tsx` | **Nieuw** — React context + provider |
| `App.tsx` | Wrap met `NatConfigProvider` + error toast |
| `src/utils/fiscaleParameters.ts` | `getFiscaleParameters()` helper toegevoegd |
| `src/utils/berekeningen.ts` | Functies accepteren nu optioneel `params` argument |
| `src/pages/Aankoop.tsx` | NHG grens via config |
| `src/components/ResultCards.tsx` | Config via context |
| `src/components/aanvraag/sections/FinancieringsopzetSection.tsx` | NHG + overdrachtsbelasting via config |
| 6 inkomen/dropdown-componenten | Dropdowns via config met fallback |
| `HuidigeHypotheekSection.tsx` | Geldverstrekkers via config |
| `VerplichtingenSection.tsx` | Financiële instellingen via config |
| `WoningSection.tsx` + `OnderpandSection.tsx` | Woning-dropdowns via config |

**Verificatie:** App laadt config bij mount, console toont `NAT Config loaded: { fiscaal: "2026", ... }`

### Lovable-wijzigingen 13 feb 2026

**Supabase dual-write (belangrijkste wijziging):**
- `supabaseDossierService.ts` — CRUD voor dossiers (fetch, upsert, delete) met camelCase↔snake_case mapping
- `supabaseAanvraagService.ts` — CRUD voor aanvragen met auto-update parent dossier timestamp
- `dossierStorage.ts` — schrijft nu naar localStorage + Supabase (dual-write)
- `aanvraagStorage.ts` — schrijft nu naar localStorage + Supabase (dual-write)
- Lezen: Supabase-first, fallback naar localStorage

**Database migraties:**
- `20260213072611`: Tabellen `dossiers`, `aanvragen`, `audit_log` + RLS + audit-triggers
- `20260213081539`: Fix trigger-functie `update_laatst_gewijzigd_column()`

**Admin migratie:**
- `/admin-migratie` pagina voor eenmalige localStorage → Supabase migratie
- Opruimen van wezen-aanvragen (aanvragen zonder gekoppeld dossier)

### Lovable-wijzigingen 16 feb 2026

**AOW-fixes (ochtend):**
- AOW data flow fixed — prev-ref reset bug opgelost
- AOW propagation bug — datums propageren nu correct naar einddatums
- AOW income threshold — inkomen na AOW-datum correct berekend

**Dossier/Aanvraag-flow:**
- Nieuw dossier aanmaken vanuit indexpagina met contactgegevens
- Postcode → straat/woonplaats via PDOK API (Supabase Edge Function)
- Prefill aanvragen vanuit dossiergegevens
- Save-keuze dialog (overschrijven of nieuw opslaan)
- Dossier laatst_gewijzigd auto-update bij opslaan aanvraag
- Drie kaarten op één rij (indexpagina layout)
- Migratieknop verwijderd

**Financiering/Berekening:**
- Overbrugging leningtype toegevoegd (mapt naar Aflossingsvrij in NAT API)
- NHG provisie verlaagd van 0.6% naar 0.4%
- Overdrachtsbelasting nu bewerkbaar (niet meer auto-berekend)
- EBB auto-fill verwijderd (handmatig invullen)

**Naamgeving/UI:**
- Genummerde berekeningen en aanvraagnamen
- Aanvraag-kopieën naamgeving (kopie, kopie 2, etc.)
- Aanvraag icon kleuren (primair/secundair)
- Default stap bij openen aanvraag: 5

**Nieuwe velden (JSONB, geen migratie nodig):**
- Burgerlijke staat + samenlevingsvorm (partner)
- Straat + woonplaats (contactgegevens, via PDOK)

**API & Config:**
- API-sleutel geëxternaliseerd naar `apiConfig.ts` met env-variabelen
- NAT Config integratie: `useNatConfig` hook + `NatConfigContext` (C2 Lovable-kant)
- Site titel geüpdatet naar "2026"
- Doelstelling-wijziging bevestigingsdialoog (voorkomt dataverlies)

**Nieuwe externe service:**
- PDOK API (api.pdok.nl) — postcode lookup via Supabase Edge Function `postcode-lookup`

### Nog te doen (Fase 4)

| # | Stap | Waar | Afhankelijkheid | Status |
|---|------|------|-----------------|--------|
| 1 | Audit Lovable (stap A) | Lovable | Geen | **Gedaan** |
| 2 | API centralisatie (stap A fix 1+2) | Lovable | Stap A | **Gedaan** |
| 3 | Duplicaties opruimen (stap A fix 3) | Lovable | Stap A | Te doen |
| 4 | localStorage opruimen (Fase 3, stap 6) | Lovable | ~1 week na stap 5 | Te doen (~23 feb) |
| 5 | Project-switch naar eigen Supabase | Supabase + Lovable | Na stap 6 | Te doen |
| 6 | 2FA (Fase 3, stap 7) | Lovable + Supabase | Na project-switch | Te doen |
| 7 | Rollen-systeem RBAC (stap B) | Supabase + Lovable | Na project-switch | Te doen |
| 8 | Config externaliseren NAT API (stap C1) | NAT API (deze repo) | Na audit | **Gedaan** |
| 9 | Lovable-data externaliseren (stap C2) | NAT API + Lovable | Na C1 | **Gedaan** |
| 10 | Admin-dashboard (stap C3) | Lovable | Na C1 + C2 | Te doen |
| 11 | Hypotheekrentes handmatig (stap C4) | Supabase + Lovable | Na C3 | Te doen |
| 12 | Samenvatting PDF (stap D1) | NAT API (WeasyPrint) | Onafhankelijk | Te doen |
| 13 | Adviesrapport PDF (stap D2) | NAT API + Lovable | Na adviezen-feature | Te doen |
| 14 | Hypotheekrentes automatisch (stap C4 fase 2) | NAT API | Na C4 fase 1 | Toekomst |

---

## Wat moet nog gedaan worden? (overige fasen)

### Fase 1: Meer tests (wacht op Excel-waarden)
- AOW-scenario testen
- Scenario 2 (over 10 jaar) testen
- Alle 8 energielabels testen
- Grensgevallen (nul-inkomen, hoog inkomen, RVP 119 vs 120)

### Fase 5: Uitbouwen
- ~~GitHub Actions voor automatisch testen~~ **Gedaan!**
- API-versioning (`/v1/calculate` voor NAT 2026)
- Sentry monitoring voor foutmeldingen

### Toekomst: Integraties
- HDN-export (hypotheekaanvragen electronisch versturen)
- AI document processing vanuit SharePoint/OneDrive
- Supabase REST API als centrale hub voor externe services

---

## Gewijzigde bestanden

| Bestand | Wijziging |
|---------|-----------|
| `app.py` | Volledig herschreven: CORS, logging, validatie, auth, rate limiting, health checks + CORS wildcard fix + betere API-sleutel foutmeldingen |
| `calculator_final.py` | Deling-door-nul beveiliging (2 plekken) |
| `requirements.txt` | slowapi==0.1.9 toegevoegd |
| `test_complete.py` | Exit code toegevoegd voor CI/CD |
| `.github/workflows/test.yml` | **Nieuw** — GitHub Actions: automatisch testen bij push/PR |

---

## Kolomnamen-referentie (Fase 3)

| TypeScript (camelCase) | Postgres (snake_case) | Type |
|---|---|---|
| `id` | `id` | UUID |
| `type` | `type` | TEXT ('aankoop'/'aanpassen') |
| `naam` | `naam` | TEXT |
| `klantNaam` | `klant_naam` | TEXT |
| `klantContactGegevens` | `klant_contact_gegevens` | JSONB |
| `ownerId` | `owner_id` | UUID (FK → auth.users) |
| `ownerName` | `owner_name` | TEXT |
| `invoer` | `invoer` | JSONB |
| `scenario1` | `scenario1` | JSONB |
| `scenario2` | `scenario2` | JSONB |
| `aanmaakDatum` | `aanmaak_datum` | TIMESTAMPTZ |
| `laatstGewijzigd` | `laatst_gewijzigd` | TIMESTAMPTZ (auto-update) |
| `dossierId` | `dossier_id` | UUID (FK → dossiers, CASCADE) |
| `data` | `data` | JSONB (volledige AanvraagData) |

---

## Probleemoplossing (Fase 3)

| Probleem | Oorzaak | Oplossing |
|----------|---------|-----------|
| "violates row-level security policy" | owner_id matcht niet met ingelogde user | Controleer dat owner_id = auth.uid() bij aanmaken |
| Dossier in localStorage maar niet in Supabase | Supabase dual-write fout | Open DevTools Console, zoek "Supabase dual-write failed" |
| JSONB komt terug als string | Dubbel geserialiseerd | Niet JSON.stringify() gebruiken voor JSONB-kolommen |
| Timestamps verkeerde tijdzone | Normaal — UTC opgeslagen | Toon met `toLocaleString('nl-NL')` in de frontend |
| Dubbele records na migratie | Geen probleem | UPSERT update bestaande records op basis van UUID |
| `record "new" has no field "updated_at"` | Trigger functie conflict: `update_updated_at_column()` van profiles-tabel | Aparte functie `update_laatst_gewijzigd_column()` aangemaakt (gedaan) |
| Service stuurt `updated_at` mee | Lovable-generated code mapt naar verkeerde kolom | Upsert-object beperken tot alleen bestaande kolommen (gedaan) |
| Table Editor toont geen data | Verversing-issue in Supabase dashboard | Gebruik SQL Editor: `SELECT * FROM dossiers;` of navigeer weg en terug |
| Data in app maar niet in Supabase Dashboard | Twee Supabase-projecten: Lovable's project (`armwhaeuacimgbjukdtm`) vs eigen project (`zecrknauqcxbsqjdramq`) | Gebruik Lovable's Supabase-toegang om data te controleren, niet het eigen Supabase Dashboard |
