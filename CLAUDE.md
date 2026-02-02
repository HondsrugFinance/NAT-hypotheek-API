# NAT Hypotheeknormen Calculator 2026

## Project Overzicht

Dit project bevat een NAT hypotheekcalculator met:
- **Backend**: Python/FastAPI API gedeployd op Render
- **Frontend**: Lovable no-code platform
- **Bronbestand**: Excel rekensheet (Hondsrug Finance Rekensheet 2026)

## API Endpoints

### Hypotheek Berekening
```
POST https://nat-hypotheek-api.onrender.com/calculate
Content-Type: application/json
```

### AOW-categorie Berekening
```
GET https://nat-hypotheek-api.onrender.com/aow-categorie?geboortedatum=YYYY-MM-DD
```

**Response:**
```json
{
  "categorie": "BINNEN_10_JAAR",
  "aow_datum": "2032-06-15",
  "jaren_tot_aow": 6.3
}
```

**Categorieën:**
| Categorie | Betekenis | UI Actie |
|-----------|-----------|----------|
| `AOW_BEREIKT` | Klant heeft AOW-leeftijd al bereikt | Toggle "Ontvangt AOW" = AAN |
| `BINNEN_10_JAAR` | Klant bereikt AOW binnen 10 jaar | Waarschuwing tonen, toggle = UIT |
| `MEER_DAN_10_JAAR` | Klant bereikt AOW over >10 jaar | Geen actie, toggle = UIT |

---

## Lovable UI Specificaties

### Leningdelen Sectie

#### Layout (horizontaal per leningdeel)
| Aflosvorm | Looptijd (orig) | Looptijd (rest) | Bedrag Box 1 | Bedrag Box 3 | RVP (mnd) | Rente | Inleg/overig |
|-----------|-----------------|-----------------|--------------|--------------|-----------|-------|--------------|

#### Totalen Rij (alleen tonen bij 2+ leningdelen)

**Velden:**
- Totaal Looptijd origineel (gewogen)
- Totaal Looptijd restant (gewogen)
- Totaal Box 1
- Totaal Box 3
- Gewogen werkelijke rente

**Berekeningen:**

```
Totaal Box 1 = Σ hoofdsom_box1
Totaal Box 3 = Σ hoofdsom_box3

Gewogen looptijd origineel = (Σ (bedrag × org_lpt)) / totaal_bedrag
Gewogen looptijd restant = (Σ (bedrag × rest_lpt)) / totaal_bedrag

Gewogen werkelijke rente = (Σ (bedrag × rest_lpt × rente)) / (Σ (bedrag × rest_lpt))
```

**Voorbeeld:**
```
Deel 1: €120.000, org_lpt=360, rest_lpt=360, rente=4%
Deel 2: €100.000, org_lpt=360, rest_lpt=200, rente=2%

Gewogen looptijd orig = (120k×360 + 100k×360) / 220k = 360
Gewogen looptijd rest = (120k×360 + 100k×200) / 220k = 287

Gewogen rente:
- Teller: 120k×360×0.04 + 100k×200×0.02 = 1.728.000 + 400.000 = 2.128.000
- Noemer: 120k×360 + 100k×200 = 43.200.000 + 20.000.000 = 63.200.000
- Resultaat: 2.128.000 / 63.200.000 = 3,367%
```

---

## API Veldmapping

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
- "Geen (geldig) Label"
- "E,F,G"
- "C,D"
- "A,B"
- "A+,A++"
- "A+++"
- "A++++"
- "A++++ met garantie"

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

**Aflosvorm opties:** "Annuïteit", "Lineair", "Aflosvrij", "Spaar"

**Inleg/overig:** Alleen actief wanneer aflosvorm = "Spaar"

---

## API Response Structuur

```json
{
  "scenario1": {
    "annuitair": {
      "max_box1": 326250.28,
      "max_box3": 302010.67,
      "ruimte_box1": 106250.28,
      "ruimte_box3": 82010.67
    },
    "niet_annuitair": {
      "max_box1": 326250.28,
      "max_box3": 302010.67,
      "ruimte_box1": 106250.28,
      "ruimte_box3": 82010.67
    }
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

### Debug Waarden Mapping

| UI Veld                  | API Path              | Format              |
|--------------------------|-----------------------|---------------------|
| Toetsinkomen             | debug.toets_inkomen   | € xxx.xxx           |
| Toetsrente               | debug.toets_rente     | x,xxx% (×100, 3 dec)|
| Woonquote Box 1          | debug.woonquote_box1  | xx,x% (×100, 1 dec) |
| Woonquote Box 3          | debug.woonquote_box3  | xx,x% (×100, 1 dec) |
| Gewogen werkelijke rente | Client-side berekening| x,xxx% (3 dec)      |

**Let op:** De "Gewogen werkelijke rente" in de UI moet CLIENT-SIDE berekend worden met de formule hierboven (gewogen op bedrag × resterende looptijd), niet uit de API.

---

## Voorbeeld API Request

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
    },
    {
      "aflos_type": "Annuïteit",
      "org_lpt": 360,
      "rest_lpt": 200,
      "hoofdsom_box1": 100000,
      "hoofdsom_box3": 0,
      "rvp": 60,
      "inleg_overig": 0,
      "werkelijke_rente": 0.02
    }
  ]
}
```

---

## Lovable Chat Instructies

### Instructie: Gewogen Rente Fix

```
Fix de berekening van de gewogen werkelijke rente.

De correcte formule weegt op bedrag × resterende looptijd:

Gewogen werkelijke rente =
    (Σ (hoofdsom × resterende_looptijd × werkelijke_rente))
    /
    (Σ (hoofdsom × resterende_looptijd))

Toepassen op:
1. Totaal rij onder Leningdelen (kolom Rente): toon met 2 decimalen
2. Toetsinkomen & Woonquote sectie (Gewogen werkelijke rente): toon met 3 decimalen
```

### Instructie: Totalen Rij Leningdelen

```
Voeg een totalen sectie toe onder de leningdelen die ALLEEN zichtbaar is
wanneer er 2 of meer leningdelen zijn.

Toon:
| Looptijd orig | Looptijd rest | Totaal Box 1 | Totaal Box 3 | Gem. rente |
|---------------|---------------|--------------|--------------|------------|
| [gewogen]     | [gewogen]     | € [som]      | € [som]      | [x,xx] %   |

Berekeningen:
- Looptijden: gewogen gemiddelde op basis van bedrag
- Rente: gewogen gemiddelde op basis van bedrag × resterende looptijd
```

### Instructie: Decimalen Percentages

```
Pas de weergave van percentages aan:

- Toetsrente: 3 decimalen, bijv. "4,316%"
- Gewogen werkelijke rente: 3 decimalen, bijv. "3,367%"
- Woonquotes: 1 decimaal, bijv. "26,3%"
- Totaal rij rente: 2 decimalen, bijv. "3,37%"
```

---

## AOW-leeftijd Tabel

De AOW-leeftijd wordt officieel vastgesteld door de Rijksoverheid (5 jaar vooruit).

| Geboren t/m | AOW-leeftijd |
|-------------|--------------|
| 31-12-1960 | 67 jaar |
| 30-09-1964 | 67 jaar + 3 maanden |
| Na 30-09-1964 | 67 + 3 mnd (geschat) |

**Bron:** https://www.rijksoverheid.nl/onderwerpen/algemene-ouderdomswet-aow/aow-leeftijd

**Jaarlijkse update:** Check in november voor nieuwe AOW-leeftijden en update `aow_calculator.py`.

---

## Lovable AOW Instructie

```
Voeg AOW-leeftijd controle toe aan de Rekentool:

1. Maak een AOW_TABEL constante met deze regels:
   - Geboren t/m 31-12-1960: AOW op 67 jaar
   - Geboren t/m 30-09-1964: AOW op 67 jaar + 3 maanden
   - Geboren na 30-09-1964: AOW op 67 jaar + 3 maanden (geschat)

2. Maak functie bepaalAOWCategorie(geboortedatum) die returnt:
   - "AOW_BEREIKT" als AOW-datum <= vandaag
   - "BINNEN_10_JAAR" als AOW-datum binnen 10 jaar
   - "MEER_DAN_10_JAAR" als AOW-datum > 10 jaar

3. Stap 1 "Klant": Bij wijziging geboortedatum:
   - Als categorie = "BINNEN_10_JAAR": toon oranje waarschuwing
     "⚠️ Deze klant bereikt binnen 10 jaar de AOW-gerechtigde leeftijd"
     direct achter/onder het geboortedatum veld
   - Anders: verberg waarschuwing

4. Stap 2 "Haalbaarheid": Bij laden van de stap:
   - Als aanvrager OF partner categorie = "AOW_BEREIKT":
     zet toggle "Ontvangt AOW" default op AAN
   - Anders: zet toggle default op UIT
```

---

## Bestanden

| Bestand | Beschrijving |
|---------|--------------|
| calculator_final.py | Hoofdcalculator met NAT 2026 logica |
| app.py | FastAPI wrapper voor de calculator |
| aow_calculator.py | AOW-leeftijd berekening en categorie bepaling |
| output_contract.json | API response schema specificatie |
| contract_check.py | Validator voor API responses |

## GitHub Repository

https://github.com/HondsrugFinance/NAT-hypotheek-API

## Render Deployment

- URL: https://nat-hypotheek-api.onrender.com
- Auto-deploy bij push naar main branch
