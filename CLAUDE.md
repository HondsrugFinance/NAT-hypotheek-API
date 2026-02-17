# NAT Hypotheeknormen Calculator 2026

## Project Overzicht

Dit project bevat de volledige backend voor de Hondsrug Finance Rekentool:
- **Backend**: Python/FastAPI API gedeployd op Render
- **Frontend**: Lovable no-code platform
- **Bronbestand**: Excel rekensheet (Hondsrug Finance Rekensheet 2026)

### Twee calculators in één API

| Module | Endpoint | Functie |
|--------|----------|---------|
| `calculator_final.py` | `POST /calculate` | Maximale hypotheek (NAT 2026 normen) |
| `monthly_costs/` | `POST /calculate/monthly-costs` | Netto maandlasten met belastingeffecten |

---

## Projectstructuur

```
NAT-hypotheek-API/
├── app.py                      # FastAPI app, routes, CORS, auth
├── calculator_final.py         # NAT 2026 maximale hypotheek calculator
├── aow_calculator.py           # AOW-leeftijd berekening
├── pdf_generator.py            # Samenvatting PDF generatie (weasyprint)
├── config_schemas.py           # Pydantic validatie voor config bestanden
├── contract_check.py           # API response validator
├── output_contract.json        # API response schema specificatie
├── conftest.py                 # Pytest root config (sys.path)
├── pytest.ini                  # Pytest configuratie
│
├── config/                     # Configuratie JSON bestanden
│   ├── aow.json                # AOW-leeftijden tabel
│   ├── dropdowns.json          # Dropdown opties voor frontend
│   ├── energielabel.json       # Energielabel bonussen
│   ├── fiscaal.json            # Fiscale standaardwaarden
│   ├── fiscaal-frontend.json   # Fiscale parameters voor Lovable UI
│   ├── geldverstrekkers.json   # Geldverstrekkers en productlijnen
│   └── studielening.json       # Studielening correctiefactoren
│
├── monthly_costs/              # Netto maandlasten calculator (package)
│   ├── config.py               # RULES_DIR, DEFAULT_FISCAL_YEAR
│   ├── domain/
│   │   ├── calculator.py       # MortgageCalculator orchestrator
│   │   ├── loan_calc.py        # Annuïteit, lineair, aflossingsvrij
│   │   ├── tax_calc.py         # Belastingschijven, marginaal tarief
│   │   ├── ewf.py              # Eigenwoningforfait berekening
│   │   ├── hillen.py           # Wet Hillen correctie
│   │   └── partner.py          # Partner-verdeling renteaftrek
│   ├── schemas/
│   │   ├── input.py            # MonthlyCostsRequest, LoanPart, Partner
│   │   ├── output.py           # MonthlyCostsResponse, TaxBreakdown
│   │   └── rules.py            # FiscalRules, TaxBracket, EWFBand
│   ├── rules/
│   │   ├── loader.py           # JSON laden + LRU caching
│   │   ├── validator.py        # Regels validatie
│   │   ├── 2025.json           # Fiscale regels 2025
│   │   └── 2026.json           # Fiscale regels 2026
│   ├── exceptions/
│   │   ├── __init__.py         # Custom exceptions
│   │   └── handlers.py         # FastAPI exception handlers
│   └── routes/
│       └── calculate.py        # POST /calculate/monthly-costs
│
└── tests/
    └── monthly_costs/          # Tests voor maandlasten calculator
        ├── conftest.py         # Fixtures (tax brackets, EWF, Hillen)
        ├── unit/
        │   ├── test_ewf.py
        │   ├── test_hillen.py
        │   ├── test_loan_calc.py
        │   ├── test_partner.py
        │   └── test_tax_calc.py
        └── integration/
            ├── conftest.py     # TestClient fixture
            └── test_api.py
```

---

## Alle API Endpoints

### Hypotheek Berekening (NAT 2026)
```
POST /calculate
Content-Type: application/json
```

### Netto Maandlasten Berekening
```
POST /calculate/monthly-costs
Content-Type: application/json
```

### AOW-categorie
```
GET /aow-categorie?geboortedatum=YYYY-MM-DD
```

### Config Endpoints (publiek)
```
GET /config/energielabel
GET /config/studielening
GET /config/aow
GET /config/fiscaal
GET /config/fiscaal-frontend
GET /config/geldverstrekkers
GET /config/dropdowns
GET /config/versie
```

### Config Admin (API-key vereist via X-API-Key header)
```
PUT /config/{config_name}
```
Bewerkbare configs: `fiscaal-frontend`, `fiscaal`, `geldverstrekkers`

### PDF Generatie
```
POST /samenvatting-pdf
```

### Health Checks
```
GET /
GET /health
GET /health/deep
```

### Rate Limiting
| Endpoint | Limiet |
|----------|--------|
| `POST /calculate` | 30/minuut |
| `PUT /config/*` | 5/minuut |
| `POST /samenvatting-pdf` | 10/minuut |

---

## Monthly Costs API — Request/Response

### Request: MonthlyCostsRequest

```json
{
  "fiscal_year": 2026,
  "woz_value": 400000,
  "loan_parts": [
    {
      "id": "hoofdlening",
      "principal": 300000,
      "interest_rate": 4.5,
      "term_years": 30,
      "loan_type": "annuity",
      "box": 1
    }
  ],
  "partners": [
    {
      "id": "aanvrager",
      "taxable_income": 60000,
      "age": 35,
      "is_aow": false
    }
  ],
  "partner_distribution": {
    "method": "optimize"
  },
  "month_number": 1,
  "include_ewf": true,
  "include_hillen": true
}
```

**Velden:**

| Veld | Type | Verplicht | Beschrijving |
|------|------|-----------|--------------|
| `fiscal_year` | int (2020-2050) | Ja | Fiscaal jaar voor regels |
| `woz_value` | Decimal (>0) | Ja | WOZ-waarde woning |
| `loan_parts` | list[LoanPart] | Ja | Leningdelen (1+) |
| `partners` | list[Partner] | Ja | Partners (1-2) |
| `partner_distribution` | object | Nee | Verdeling bij 2 partners |
| `month_number` | int | Nee (default: 1) | Maandnummer berekening |
| `include_ewf` | bool | Nee (default: true) | EWF meenemen |
| `include_hillen` | bool | Nee (default: true) | Wet Hillen toepassen |

**LoanPart:**

| Veld | Type | Beschrijving |
|------|------|--------------|
| `id` | string | Uniek ID |
| `principal` | Decimal (>0) | Hoofdsom in euro's |
| `interest_rate` | Decimal (0-20) | Jarrente als percentage (4.5 = 4,5%) |
| `term_years` | int (1-50) | Looptijd in jaren |
| `loan_type` | enum | `"annuity"`, `"linear"`, `"interest_only"` |
| `box` | enum | `1` (eigen woning) of `3` (belegging) |

**Partner:**

| Veld | Type | Beschrijving |
|------|------|--------------|
| `id` | string | Uniek ID |
| `taxable_income` | Decimal (>=0) | Belastbaar jaarinkomen box 1 |
| `age` | int (18-120) | Leeftijd |
| `is_aow` | bool | AOW-leeftijd bereikt |

**PartnerDistribution:**

| Veld | Type | Beschrijving |
|------|------|--------------|
| `method` | enum | `"fixed_percent"`, `"fixed_amount"`, `"optimize"` |
| `parameter` | Decimal | Percentage (0-100) of bedrag (alleen bij fixed) |

### Response: MonthlyCostsResponse

```json
{
  "fiscal_year": 2026,
  "month_number": 1,
  "woz_value": 400000,
  "loan_parts": [
    {
      "loan_part_id": "hoofdlening",
      "loan_type": "annuity",
      "box": 1,
      "principal": 300000,
      "remaining_principal": 299478.75,
      "interest_payment": 1125.00,
      "principal_payment": 521.25,
      "gross_payment": 1646.25
    }
  ],
  "total_gross_monthly": 1646.25,
  "total_interest_monthly": 1125.00,
  "total_principal_monthly": 521.25,
  "total_interest_box1_monthly": 1125.00,
  "total_interest_box3_monthly": 0,
  "tax_breakdown": {
    "ewf_annual": 1400.00,
    "ewf_monthly": 116.67,
    "total_interest_box1_annual": 13500.00,
    "total_interest_box1_monthly": 1125.00,
    "marginal_rate": 0.3756,
    "effective_deduction_rate": 0.3756,
    "interest_deduction_annual": 5071.08,
    "interest_deduction_monthly": 422.59,
    "hillen_applicable": false,
    "hillen_deduction_annual": 0,
    "hillen_benefit_monthly": 0,
    "net_ewf_addition_annual": 1400.00,
    "ewf_tax_monthly": 43.82,
    "total_tax_benefit_monthly": 422.59,
    "total_tax_cost_monthly": 43.82,
    "net_tax_effect_monthly": 378.77
  },
  "partner_results": null,
  "net_monthly_cost": 1267.48,
  "disclaimer": "..."
}
```

### Berekeningen in de monthly_costs module

| Component | Beschrijving |
|-----------|--------------|
| **EWF** | Eigenwoningforfait op basis van WOZ-waarde en staffeltabel |
| **Renteaftrek** | Hypotheekrente aftrek box 1, gemaximeerd op effectief tarief |
| **Wet Hillen** | Correctie als EWF > aftrekbare rente (afbouwpercentage per jaar) |
| **Partner-verdeling** | Optimale verdeling renteaftrek over 2 partners |
| **Leningberekening** | Annuïteit, lineair of aflossingsvrij per maand |

### Fiscale regels per jaar

De regels staan in `monthly_costs/rules/{jaar}.json` en bevatten:
- `tax_brackets_box1` — belastingschijven
- `tax_brackets_box1_aow` — schijven voor AOW-gerechtigden
- `max_mortgage_interest_deduction_rate` — max aftrekpercentage
- `ewf_table` — eigenwoningforfait staffel
- `hillen` — Wet Hillen configuratie (enabled + afbouwpercentage)

---

## NAT Hypotheek API — Request/Response

### Voorbeeld Request

```json
{
  "hoofd_inkomen_aanvrager": 80000,
  "hoofd_inkomen_partner": 0,
  "alleenstaande": "JA",
  "ontvangt_aow": "NEE",
  "energielabel": "Geen (geldig) Label",
  "verduurzamings_maatregelen": 0,
  "limieten_bkr_geregistreerd": 0,
  "studievoorschot_studielening": 0,
  "erfpachtcanon_per_jaar": 0,
  "jaarlast_overige_kredieten": 0,
  "hypotheek_delen": [
    {
      "aflos_type": "Annuïteit",
      "org_lpt": 360,
      "rest_lpt": 360,
      "hoofdsom_box1": 120000,
      "hoofdsom_box3": 0,
      "rvp": 120,
      "inleg_overig": 0,
      "werkelijke_rente": 0.04
    }
  ]
}
```

### Response Structuur

```json
{
  "scenario1": {
    "annuitair": {
      "max_box1": 326250.28,
      "max_box3": 302010.67,
      "ruimte_box1": 106250.28,
      "ruimte_box3": 82010.67
    },
    "niet_annuitair": { ... }
  },
  "scenario2": null,
  "debug": {
    "toets_inkomen": 80000,
    "toets_rente": 0.04316,
    "woonquote_box1": 0.263,
    "woonquote_box3": 0.203,
    "gewogen_rente": 0.04316,
    "inkomen_totaal": 80000
  }
}
```

---

## API Veldmapping (NAT → Lovable)

### Inkomen Velden

| UI Veld (Aanvrager)              | API Veld                                |
|----------------------------------|-----------------------------------------|
| Hoofdinkomen aanvrager           | hoofd_inkomen_aanvrager                 |
| Inkomen uit lijfrente            | inkomen_uit_lijfrente_aanvrager         |
| Partneralimentatie ontvangen     | ontvangen_partneralimentatie_aanvrager  |
| Inkomsten uit vermogen           | inkomsten_uit_vermogen_aanvrager        |
| Huurinkomsten                    | huurinkomsten_aanvrager                 |
| Partneralimentatie betalen       | te_betalen_partneralimentatie_aanvrager |

| UI Veld (Partner)                | API Veld                                |
|----------------------------------|-----------------------------------------|
| Hoofdinkomen partner             | hoofd_inkomen_partner                   |
| Inkomen uit lijfrente            | inkomen_uit_lijfrente_partner           |
| Partneralimentatie ontvangen     | ontvangen_partneralimentatie_partner    |
| Partneralimentatie betalen       | te_betalen_partneralimentatie_partner   |

| UI Veld (Overig)                 | API Veld                                |
|----------------------------------|-----------------------------------------|
| Ontvangt AOW toggle              | ontvangt_aow = "JA" of "NEE"            |
| Alleenstaande                    | alleenstaande = "JA" of "NEE"           |

### Financiële Verplichtingen

| UI Veld                    | API Veld                      | Conversie           |
|----------------------------|-------------------------------|---------------------|
| Limieten (totaal)          | limieten_bkr_geregistreerd    | Direct              |
| Maandlast leningen         | jaarlast_overige_kredieten    | NIET ×12 (API doet dit)|
| Studielening (maandlast)   | studievoorschot_studielening  | Direct              |
| Erfpachtcanon (per maand)  | erfpachtcanon_per_jaar        | NIET ×12 (API doet dit)|

**BELANGRIJK:** De API vermenigvuldigt erfpacht en jaarlast intern met 12. Lovable moet maandbedragen DIRECT doorsturen zonder conversie.

### Onderpand

| UI Veld           | API Veld                  |
|-------------------|---------------------------|
| Energielabel      | energielabel              |
| EBV/EBB bedrag    | verduurzamings_maatregelen|

**Energielabel waarden:**
`"Geen (geldig) Label"`, `"E,F,G"`, `"C,D"`, `"A,B"`, `"A+,A++"`, `"A+++"`, `"A++++"`, `"A++++ met garantie"`

### Hypotheekdelen

| UI Veld                    | API Veld        | Type   | Default |
|----------------------------|-----------------|--------|---------|
| Aflosvorm                  | aflos_type      | string | "Annuïteit" |
| Looptijd origineel (mnd)   | org_lpt         | number | 360     |
| Looptijd restant (mnd)     | rest_lpt        | number | 360     |
| Bedrag Box 1               | hoofdsom_box1   | number | 0       |
| Bedrag Box 3               | hoofdsom_box3   | number | 0       |
| RVP (maanden)              | rvp             | number | 120     |
| Rente (decimaal)           | werkelijke_rente| number | 0.05    |
| Inleg/overig               | inleg_overig    | number | 0       |

**Aflosvorm opties:** `"Annuïteit"`, `"Lineair"`, `"Aflosvrij"`, `"Spaar"`

### Debug Waarden Mapping

| UI Veld                  | API Path              | Format              |
|--------------------------|-----------------------|---------------------|
| Toetsinkomen             | debug.toets_inkomen   | € xxx.xxx           |
| Toetsrente               | debug.toets_rente     | x,xxx% (×100, 3 dec)|
| Woonquote Box 1          | debug.woonquote_box1  | xx,x% (×100, 1 dec) |
| Woonquote Box 3          | debug.woonquote_box3  | xx,x% (×100, 1 dec) |
| Gewogen werkelijke rente | Client-side berekening| x,xxx% (3 dec)      |

**Let op:** De "Gewogen werkelijke rente" in de UI moet CLIENT-SIDE berekend worden (gewogen op bedrag × resterende looptijd), niet uit de API.

---

## Lovable UI Specificaties

### Leningdelen Totalen Rij (alleen bij 2+ leningdelen)

```
Gewogen looptijd origineel = (Σ (bedrag × org_lpt)) / totaal_bedrag
Gewogen looptijd restant   = (Σ (bedrag × rest_lpt)) / totaal_bedrag
Gewogen werkelijke rente   = (Σ (bedrag × rest_lpt × rente)) / (Σ (bedrag × rest_lpt))
```

### Percentage Weergave

| Veld | Decimalen | Voorbeeld |
|------|-----------|-----------|
| Toetsrente | 3 | 4,316% |
| Gewogen werkelijke rente | 3 | 3,367% |
| Woonquotes | 1 | 26,3% |
| Totaal rij rente | 2 | 3,37% |

---

## AOW-leeftijd Tabel

| Geboren t/m | AOW-leeftijd |
|-------------|--------------|
| 31-12-1960 | 67 jaar |
| 30-09-1964 | 67 jaar + 3 maanden |
| Na 30-09-1964 | 67 + 3 mnd (geschat) |

**Bron:** https://www.rijksoverheid.nl/onderwerpen/algemene-ouderdomswet-aow/aow-leeftijd

**Jaarlijkse update:** Check in november voor nieuwe AOW-leeftijden en update `aow_calculator.py`.

**AOW-categorie response:**
```json
{
  "categorie": "BINNEN_10_JAAR",
  "aow_datum": "2032-06-15",
  "jaren_tot_aow": 6.3
}
```

| Categorie | Betekenis | UI Actie |
|-----------|-----------|----------|
| `AOW_BEREIKT` | Klant heeft AOW-leeftijd bereikt | Toggle "Ontvangt AOW" = AAN |
| `BINNEN_10_JAAR` | Klant bereikt AOW binnen 10 jaar | Waarschuwing tonen, toggle = UIT |
| `MEER_DAN_10_JAAR` | Klant bereikt AOW over >10 jaar | Geen actie, toggle = UIT |

---

## Tests

```bash
# Unit tests monthly costs (44 tests)
pytest tests/monthly_costs/unit/ -v

# Integration tests (vereist weasyprint)
pytest tests/monthly_costs/integration/ -v

# Alle tests
pytest tests/ -v
```

---

## Deployment

- **GitHub:** https://github.com/HondsrugFinance/NAT-hypotheek-API
- **Render URL:** https://nat-hypotheek-api.onrender.com
- **Auto-deploy:** bij push naar `main` branch
- **Python versie:** 3.12+

### Dependencies

Belangrijkste packages (zie `requirements.txt`):
- `fastapi`, `uvicorn` — Web framework
- `pydantic` — Data validatie
- `weasyprint` — PDF generatie
- `slowapi` — Rate limiting

De `monthly_costs/` module heeft **geen extra dependencies** — gebruikt alleen `decimal` (stdlib), `pydantic` en `fastapi`.
