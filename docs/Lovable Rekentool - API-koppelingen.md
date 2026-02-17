# Hondsrug Finance — API Technical Reference

Geëxporteerd op: 2026-02-10

---

## 1. NAT Hypotheek API (Maximale Hypotheek Berekening)

### Endpoint
```
POST https://nat-hypotheek-api.onrender.com/calculate
Content-Type: application/json
```

### Request Schema (`NatApiRequest`)

```typescript
{
  // === INKOMEN AANVRAGER ===
  hoofd_inkomen_aanvrager: number,          // Jaarinkomen
  inkomen_uit_lijfrente_aanvrager: number,   // Jaarbedrag lijfrente
  ontvangen_partneralimentatie_aanvrager: number, // Jaarbedrag
  inkomsten_uit_vermogen_aanvrager: number,  // Jaarbedrag
  huurinkomsten_aanvrager: number,           // Jaarbedrag
  te_betalen_partneralimentatie_aanvrager: number, // Jaarbedrag (UI maand × 12)

  // === INKOMEN PARTNER ===
  hoofd_inkomen_partner: number,
  inkomen_uit_lijfrente_partner: number,
  ontvangen_partneralimentatie_partner: number,
  te_betalen_partneralimentatie_partner: number,

  // === STATUS ===
  alleenstaande: "JA" | "NEE",
  ontvangt_aow: "JA" | "NEE",

  // === FINANCIËLE VERPLICHTINGEN ===
  limieten_bkr_geregistreerd: number,    // Totaal limieten (€)
  jaarlast_overige_kredieten: number,     // Maandbedrag (API doet ×12)
  studievoorschot_studielening: number,   // Maandbedrag
  erfpachtcanon_per_jaar: number,         // Maandbedrag (API doet ×12)

  // === ONDERPAND / ENERGIE ===
  energielabel: string,                   // Zie mapping hieronder
  verduurzamings_maatregelen: number,     // EBV/EBB bedrag (€)

  // === LENINGDELEN ===
  hypotheek_delen: LeningDeelApiRequest[]  // Max 10 delen
}
```

### Leningdeel Schema (`LeningDeelApiRequest`)

```typescript
{
  aflos_type: string,          // "Annuïteit" | "Lineair" | "Aflosvrij" | "Spaarhypotheek"
  org_lpt: number,             // Originele looptijd in maanden
  rest_lpt: number,            // Restant looptijd in maanden
  hoofdsom_box1: number,       // Bedrag Box 1 (min 0.01 voor lege waarden)
  hoofdsom_box3: number,       // Bedrag Box 3 (min 0.01 voor lege waarden)
  rvp: number,                 // Rentevaste periode in maanden
  inleg_overig: number,        // Inleg/overig bedrag
  werkelijke_rente: number     // Decimaal (0.05 = 5%)
}
```

### Response Schema (`NatApiResponse`)

```typescript
{
  success: boolean,
  data?: {
    scenario1: {
      annuitair: {
        max_box1: number,      // Max hypotheek Box 1 (annuïtair/GHF)
        max_box3: number,      // Max hypotheek Box 3 (annuïtair/GHF)
        ruimte_box1: number,   // Ruimte Box 1
        ruimte_box3: number    // Ruimte Box 3
      },
      niet_annuitair: {
        max_box1: number,      // Max hypotheek Box 1 (werkelijke lasten)
        max_box3: number,      // Max hypotheek Box 3 (werkelijke lasten)
        ruimte_box1: number,
        ruimte_box3: number
      }
    } | null,
    scenario2: { /* zelfde structuur als scenario1 */ } | null,
    debug: {
      toets_inkomen: number,       // Toetsinkomen
      toets_rente: number,         // Toetsrente (decimaal, bijv. 0.05)
      woonquote_box1: number,      // Woonquote Box 1 (decimaal, bijv. 0.246)
      woonquote_box3: number,      // Woonquote Box 3
      gewogen_rente: number,       // Gewogen gemiddelde rente (decimaal)
      energielabel_bonus: number,
      correctie: number,
      c26: number,
      d26: number,
      inkomen_totaal: number,
      inkomen_aanvrager: number,
      inkomen_partner: number
    } | null,
    debug_scenario2: { /* zelfde als debug */ } | null
  },
  error?: string
}
```

### Conversie-regels (UI → API)

| UI Veld | API Veld | Conversie |
|---------|----------|-----------|
| `partneralimentatieBetalen` (maand) | `te_betalen_partneralimentatie_aanvrager` | × 12 |
| `rentepercentage` (5.0) | `werkelijke_rente` | ÷ 100 (→ 0.05) |
| `alleenstaand` (boolean) | `alleenstaande` | true → "JA", false → "NEE" |
| `ontvangtAow` (boolean) | `ontvangt_aow` | true → "JA", false → "NEE" |
| Lege bedragen (0) | `hoofdsom_box1/box3` | → 0.01 (minimum) |

### Conversie-regels (API → UI)

| API Veld | UI Veld | Conversie |
|----------|---------|-----------|
| `toets_rente` (0.05) | `toetsrente` | × 100 (→ 5.0%) |
| `woonquote_box1` (0.246) | `woonquoteBox1` | × 100 (→ 24.6%) |
| `gewogen_rente` (0.04) | `gewogenGemiddeldeWerkelijkeRente` | × 100 |

### Energielabel Mapping

| UI Waarde | API Waarde |
|-----------|------------|
| `geen_label` | `"Geen (geldig) Label"` |
| `E_F_G` | `"E,F,G"` |
| `C_D` | `"C,D"` |
| `A_B` | `"A,B"` |
| `A+_A++` | `"A+,A++"` |
| `A+++` | `"A+++"` |
| `A++++` | `"A++++"` |
| `A++++_garantie` | `"A++++ met garantie"` |

### Aflostype Mapping

| UI Waarde | API Waarde |
|-----------|------------|
| `annuiteit` | `"Annuïteit"` |
| `lineair` | `"Lineair"` |
| `aflossingsvrij` | `"Aflosvrij"` |
| `spaarhypotheek` | `"Spaarhypotheek"` |

### Excel Cell Mapping (NAT-sheet 2026)

De API repliceert de berekeningen uit het werkblad "in- en uitvoervelden":

**Input Cellen:**
| Cel | Beschrijving |
|-----|-------------|
| E11 | Hoofdinkomen aanvrager |
| F11 | Hoofdinkomen partner |
| E12 | Alleenstaand (JA/NEE) |
| E13 | Ontvangt AOW (JA/NEE) |
| E14 | Inkomen uit lijfrente |
| E15 | Ontvangen partneralimentatie |
| E16 | Inkomsten uit vermogen |
| E17 | Huurinkomsten |
| E18 | Te betalen partneralimentatie |
| E38 | Energielabel |
| E39 | Bedrag EBV |
| E42 | BKR limieten |
| E43 | Niet-BKR limieten |
| E44 | Studielening (maand) |
| E45 | Erfpachtcanon (maand) |
| E46 | Overige kredieten (maand) |
| D51 | Marktwaarde onderpand |
| I12-I21 | Aflostype per leningdeel |
| J12-J21 | Originele looptijd (mnd) |
| K12-K21 | Restant looptijd (mnd) |
| L12-L21 | Hoofdsom Box 1 |
| M12-M21 | Hoofdsom Box 3 |
| N12-N21 | Rentevaste periode (mnd) |
| O12-O21 | Inleg/overig |
| P12-P21 | Werkelijke rente (%) |

**Output Cellen (Golden Test References):**
| Cel | Beschrijving |
|-----|-------------|
| R35 (M25) | Toetsinkomen |
| R29 (M26) | Toetsrente |
| R30 (M27) | Woonquote Box 1 |
| R31 (M28) | Woonquote Box 3 |
| R43 (M40) | Max Hyp Annuïtair Box 1 |
| R44 (M41) | Max Hyp Annuïtair Box 3 |
| R49 (M47) | Max Hyp Werkelijk Box 1 |
| R50 (M48) | Max Hyp Werkelijk Box 3 |

---

## 2. Monthly Costs API (Maandlasten & Renteaftrek)

### Endpoint
```
POST https://mortgage-monthly-costs.onrender.com/calculate/monthly-costs
Content-Type: application/json
```

### Request Schema (`MonthlyCostsRequest`)

```typescript
{
  fiscal_year: number,             // Altijd 2026
  woz_value: number,               // WOZ-waarde (€)
  loan_parts: LoanPart[],          // Leningdelen
  partners: Partner[],             // 1 of 2 partners
  partner_distribution?: {
    method: "optimize"             // Optioneel: optimaliseer verdeling
  }
}
```

### LoanPart Schema

```typescript
{
  id: string,                      // Uniek ID
  principal: number,               // Hoofdsom (€)
  interest_rate: number,           // Rente als decimaal (0.05 = 5%)
  term_years: number,              // Looptijd in jaren
  loan_type: "annuity" | "linear" | "interest_only",
  box: 1 | 3                      // Fiscale box
}
```

### Partner Schema

```typescript
{
  id: string,                      // Uniek ID
  taxable_income: number,          // Belastbaar inkomen (€/jaar)
  age: number,                     // Leeftijd (min 18)
  is_aow: boolean                  // AOW-gerechtigd
}
```

### Response Schema (`MonthlyCostsResponse`)

```typescript
{
  total_gross_monthly: string,     // Bruto maandlast (string, bijv. "1234.56")
  net_monthly_cost: string,        // Netto maandlast
  tax_breakdown: {
    interest_deduction_monthly: string,    // Renteaftrek per maand
    ewf_tax_monthly: string,               // Eigenwoningforfait belasting
    hillen_benefit_monthly: string,        // Hillen-voordeel
    total_tax_benefit_monthly: string,     // Totaal belastingvoordeel
    net_tax_effect_monthly: string         // Netto belastingeffect (getoond als "Renteaftrek" in UI)
  }
}
```

### Conversie-regels (UI → API)

| UI Concept | API Veld | Conversie |
|-----------|----------|-----------|
| Aflosvorm `annuiteit` | `loan_type` | → `"annuity"` |
| Aflosvorm `lineair` | `loan_type` | → `"linear"` |
| Aflosvorm `aflossingsvrij` | `loan_type` | → `"interest_only"` |
| Aflosvorm `spaarhypotheek` | `loan_type` | → `"annuity"` (behandeld als annuïteit) |
| Leningdeel met Box 3 bedrag | Twee `loan_parts` | Gesplitst in Box 1 + Box 3 deel |
| Rente (5.0%) | `interest_rate` | ÷ 100 (→ 0.05) |
| Looptijd (360 mnd) | `term_years` | ÷ 12 (→ 30) |
| Geen geboortedatum | `age` | Default: 30 |

### WOZ-waarde Fallback Volgorde
1. Handmatig ingevoerde WOZ-waarde
2. Aankoopsom woning (alleen bij Aankoop-flow)
3. Marktwaarde uit haalbaarheidsberekening
4. Benodigde hypotheek (laatste fallback)

### Inkomen Berekening voor Partners
```
belastbaar_inkomen = hoofdinkomen 
                   + inkomen_uit_lijfrente 
                   + ontvangen_partneralimentatie 
                   - (betaalde_partneralimentatie_maand × 12)
```

---

## 3. Postcode Lookup API (Edge Function)

### Endpoint
```
POST {SUPABASE_URL}/functions/v1/postcode-lookup
Content-Type: application/json
Authorization: Bearer {SUPABASE_ANON_KEY}
```

### Request
```typescript
{ postcode: string, huisnummer: string }
```

### Response
```typescript
{
  straat: string,
  woonplaats: string,
  gemeente: string,
  provincie: string
}
```

---

## 4. Fiscale Parameters 2026 (Lokaal)

| Parameter | Waarde |
|-----------|--------|
| NHG-grens | € 470.000 |
| NHG-provisie | 0,6% |
| Belastingtarief Box 1 | 36,97% |
| Belastingtarief Box 1 (hoog) | 49,5% |
| Grens hoog tarief | € 76.817 |
| AOW-leeftijd | 67 jaar, 0 maanden |
| Overdrachtsbelasting woning | 2% |
| Overdrachtsbelasting overig | 10,6% |
| Startersvrijstelling grens | € 525.000 |
| Startersvrijstelling max leeftijd | 35 jaar |
| Standaard looptijd | 30 jaar (360 maanden) |
| Toetsrente | 5,0% |

### AOW-leeftijd Tabel
| Geboren tot | AOW-leeftijd |
|-------------|-------------|
| 31-12-1960 | 67 jaar, 0 maanden |
| 30-09-1964 | 67 jaar, 3 maanden |
| Later | 67 jaar, 3 maanden (geschat) |
