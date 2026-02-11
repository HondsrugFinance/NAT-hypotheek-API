# Hondsrug Finance Rekentool — Voortgang Verbetertraject

Laatst bijgewerkt: 2026-02-11

---

## Wat is er gedaan?

### app.py — Volledig herschreven (v1.0.0 → v1.1.0)

| Verbetering | Status | Wat het doet |
|-------------|--------|-------------|
| CORS | Gedaan | Alleen `hondsrug-insight.lovable.app` en localhost mogen de API aanroepen |
| Logging | Gedaan | Elke berekening en fout wordt gelogd (zonder persoonlijke gegevens) |
| Invoercontrole | Gedaan | Grenzen op alle velden (inkomen 0-10M, rente 0-20%, looptijd 1-600 mnd, etc.) |
| Foutafhandeling | Gedaan | API crasht niet meer — geeft altijd een nette foutmelding |
| API-sleutel | Gedaan | Optionele `X-API-Key` header (activeer via `NAT_API_KEY` env var in Render) |
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
| `src/utils/dossierStorage.ts` | localStorage CRUD (key: `hondsrug-dossiers-2026`) — moet naar Supabase |
| `src/utils/aanvraagStorage.ts` | localStorage CRUD (key: `hondsrug-aanvragen-2026`) — moet naar Supabase |
| `.env` | Supabase config aanwezig (EU-regio) |

**Frontend-API mapping gecontroleerd:**
- Alimentatie: maandbedrag ×12 → klopt
- Rente: percentage /100 → klopt
- Lege bedragen → €0,01 (bewust, voor gewogen rente-berekening)
- Energielabel en aflostype → correct gemapt

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

## Wat moet nog gedaan worden?

### Fase 1: Meer tests (wacht op Excel-waarden van jou)
- AOW-scenario testen
- Scenario 2 (over 10 jaar) testen
- Alle 8 energielabels testen
- Grensgevallen (nul-inkomen, hoog inkomen, RVP 119 vs 120)

### Fase 3: Database
- Supabase tabellen aanmaken (advisors, dossiers, berekeningen, aanvragen, audit_log)
- Row Level Security instellen (elke adviseur ziet alleen eigen dossiers)
- In Lovable: localStorage vervangen door Supabase-opslag
- Migratiestrategie: eerst dubbel opslaan, dan overschakelen

### Fase 5: Uitbouwen
- ~~GitHub Actions voor automatisch testen~~ **Gedaan!**
- API-versioning (`/v1/calculate` voor NAT 2026)
- Sentry monitoring voor foutmeldingen

---

## Gewijzigde bestanden

| Bestand | Wijziging |
|---------|-----------|
| `app.py` | Volledig herschreven: CORS, logging, validatie, auth, rate limiting, health checks |
| `calculator_final.py` | Deling-door-nul beveiliging (2 plekken) |
| `requirements.txt` | slowapi==0.1.9 toegevoegd |
| `test_complete.py` | Exit code toegevoegd voor CI/CD |
| `.github/workflows/test.yml` | **Nieuw** — GitHub Actions: automatisch testen bij push/PR |
