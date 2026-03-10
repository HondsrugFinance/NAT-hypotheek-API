# Lovable Prompt G7: Risk-secties herstellen + API-fouten fixen

> Na G6 zijn de bedragen en financiering correct (€ 414.300, leningdelen, kosten). Maar de **risico-secties ontbreken** (pensioen, overlijden, AO, WW, relatiebeëindiging). Console toont: risk-scenarios **422**, /calculate **403**. Dit prompt fixt de 3 oorzaken: verkeerde veldnamen, ontbrekende rente-conversie, en missende API-key.

---

## Overzicht problemen en fixes

| Probleem | Oorzaak | Fix |
|----------|---------|-----|
| Risk-scenarios 422 | `werkelijke_rente` krijgt 2.8 i.p.v. 0.028 + `aflos_type` krijgt "annuiteit" i.p.v. "Annuïteit" | Rente /100, aflosvorm mapping |
| /calculate 403 | API-key header ontbreekt | `getApiHeaders()` toevoegen |
| Risico-secties weg | 422 → riskData = null → secties niet gebouwd | Volgt uit fix hierboven |
| Scenario checks weg | Afhankelijk van riskData | Volgt uit fix hierboven |
| Geldverstrekker mist | Niet opgeslagen in invoer | Fix: extraheren uit scenario of dossier |
| Maandlasten missen | natResultaten/maandlastenResultaten niet in invoer | Fix: live API-call |

---

## Stap 1: Aflosvorm mapping helper

De backend API verwacht exacte aflosvorm-namen. Lovable slaat ze op in lowercase. Voeg deze mapping helper toe:

```typescript
function mapAflosvorm(lovableAflosvorm: string): string {
  const mapping: Record<string, string> = {
    'annuiteit': 'Annuïteit',
    'annuïteit': 'Annuïteit',
    'lineair': 'Lineair',
    'aflossingsvrij': 'Aflosvrij',
    'aflosvrij': 'Aflosvrij',
    'spaarhypotheek': 'Spaarhypotheek',
    'spaar': 'Spaarhypotheek',
  };
  return mapping[lovableAflosvorm?.toLowerCase()] || 'Annuïteit';
}
```

**Let op:** "overbrugging" is GEEN geldig aflostype voor de API. Overbruggingskredieten moeten worden **uitgefilterd** in de risk-scenarios en relatiebeëindiging calls (zie stap 3).

---

## Stap 2: Leningdelen mapping fixen

De console output laat zien dat leningdelen staan op `invoer._dossierScenario1.leningDelen` (met hoofdletter D). De veldnamen in Lovable zijn anders dan wat de API verwacht.

### 2a. Leningdelen extractie

**Vervang** de bestaande leningdelen extractie met:

```typescript
// Leningdelen uit het eerste scenario
const dossierScenario = invoer?._dossierScenario1 || invoer?._dossierScenario || {};
const rawLeningdelen: any[] =
  dossierScenario?.leningDelen ||     // Lovable standaard pad
  dossierScenario?.leningdelen ||     // alternatief
  scenario?.leningdelen ||            // fallback
  invoer?.leningdelen ||              // fallback
  [];

console.log('Raw leningdelen:', rawLeningdelen);
```

### 2b. API-formaat mapping

Maak een helper die Lovable leningdelen omzet naar het API-formaat:

```typescript
function mapLeningdeelVoorApi(deel: any) {
  // Rente: Lovable slaat op als percentage (bijv. 4.1), API verwacht decimaal (0.041)
  const rentePercentage = deel.rentepercentage || deel.rente || deel.werkelijkeRente || 5;
  const renteDecimaal = rentePercentage > 1 ? rentePercentage / 100 : rentePercentage;

  return {
    aflos_type: mapAflosvorm(deel.aflossingsvorm || deel.aflos_type || 'annuiteit'),
    org_lpt: deel.origineleLooptijd || deel.looptijd || deel.org_lpt || 360,
    rest_lpt: deel.restantLooptijd || deel.restLooptijd || deel.rest_lpt || deel.origineleLooptijd || 360,
    hoofdsom_box1: deel.bedrag || deel.bedragBox1 || deel.hoofdsomBox1 || 0,
    hoofdsom_box3: deel.bedragBox3 || deel.hoofdsomBox3 || 0,
    rvp: deel.rentevastePeriode || deel.rvp || 120,
    werkelijke_rente: renteDecimaal,
    inleg_overig: deel.inleg || deel.inlegOverig || 0,
  };
}
```

**Kritieke conversie:** `rentepercentage: 2.8` → `werkelijke_rente: 0.028`. Dit was de oorzaak van de 422 error (API valideert `werkelijke_rente <= 0.20`).

---

## Stap 3: Risk-scenarios request fixen

**Vervang** de bestaande risk-scenarios request opbouw met deze versie die de correcte mapping gebruikt:

```typescript
// Filter overbruggingskredieten uit (niet geldig voor risk-scenarios)
const leningdelenVoorApi = rawLeningdelen
  .filter((d: any) => {
    const aflosvorm = (d.aflossingsvorm || d.aflos_type || '').toLowerCase();
    return aflosvorm !== 'overbrugging';
  })
  .map(mapLeningdeelVoorApi);

console.log('Leningdelen voor API:', leningdelenVoorApi);

// Hypotheekbedrag = som van gefilterde leningdelen (excl. overbrugging)
// Herbereken zodat het consistent is met wat de risk-scenarios API ziet
const hypotheekBedragVoorRisico = leningdelenVoorApi.reduce(
  (sum: number, d: any) => sum + (d.hoofdsom_box1 || 0) + (d.hoofdsom_box3 || 0), 0
);

const riskScenariosRequest = {
  hypotheek_delen: leningdelenVoorApi.length > 0
    ? leningdelenVoorApi
    : [{
        aflos_type: 'Annuïteit',
        org_lpt: 360,
        rest_lpt: 360,
        hoofdsom_box1: hypotheekBedrag,
        hoofdsom_box3: 0,
        rvp: 120,
        werkelijke_rente: 0.05,
        inleg_overig: 0,
      }],

  ingangsdatum_hypotheek: new Date().toISOString().split('T')[0],
  geboortedatum_aanvrager: klant.geboortedatumAanvrager,
  inkomen_aanvrager_huidig: hoofdinkomenAanvrager,
  inkomen_aanvrager_aow: options.inkomenAanvragerAow || 0,
  alleenstaande: hasPartner ? 'NEE' : 'JA',
  geboortedatum_partner: hasPartner ? klant.geboortedatumPartner : undefined,
  inkomen_partner_huidig: hasPartner ? hoofdinkomenPartner : 0,
  inkomen_partner_aow: hasPartner ? (options.inkomenPartnerAow || 0) : 0,

  // Overlijden
  nabestaandenpensioen_bij_overlijden_aanvrager: options.nabestaandenpensioenAanvrager || 0,
  nabestaandenpensioen_bij_overlijden_partner: options.nabestaandenpensioenPartner || 0,
  heeft_kind_onder_18: options.heeftKindOnder18 || false,

  // Inkomensverdeling
  inkomen_loondienst_aanvrager: (options.typeDienstverbandAanvrager || 'Loondienst') === 'Loondienst' ? hoofdinkomenAanvrager : 0,
  inkomen_onderneming_aanvrager: (options.typeDienstverbandAanvrager || '') === 'Onderneming' ? hoofdinkomenAanvrager : 0,
  inkomen_roz_aanvrager: (options.typeDienstverbandAanvrager || '').startsWith('ROZ') ? hoofdinkomenAanvrager : 0,
  inkomen_overig_aanvrager: 0,
  inkomen_loondienst_partner: hasPartner && (options.typeDienstverbandPartner || 'Loondienst') === 'Loondienst' ? hoofdinkomenPartner : 0,
  inkomen_onderneming_partner: hasPartner && (options.typeDienstverbandPartner || '') === 'Onderneming' ? hoofdinkomenPartner : 0,
  inkomen_roz_partner: hasPartner && (options.typeDienstverbandPartner || '').startsWith('ROZ') ? hoofdinkomenPartner : 0,
  inkomen_overig_partner: 0,

  // AO parameters
  ao_percentage: options.aoPercentage || 50,
  benutting_rvc_percentage: options.benuttingRvc || 50,

  // Arbeidsverleden (geschat)
  arbeidsverleden_jaren_totaal_aanvrager: Math.max(0, berekenLeeftijd(klant.geboortedatumAanvrager) - 18),
  arbeidsverleden_jaren_totaal_partner: hasPartner ? Math.max(0, berekenLeeftijd(klant.geboortedatumPartner) - 18) : 0,

  // Berekening
  toetsrente: 0.05,
  geadviseerd_hypotheekbedrag: hypotheekBedragVoorRisico || hypotheekBedrag,
};

console.log('Risk-scenarios request:', JSON.stringify(riskScenariosRequest, null, 2));
```

### 3b. API-call

De risk-scenarios call zelf was correct (geen API-key nodig). Zorg dat de try/catch behouden blijft:

```typescript
let riskData: any = null;

try {
  const riskResponse = await fetch(
    'https://nat-hypotheek-api.onrender.com/calculate/risk-scenarios',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(riskScenariosRequest),
    }
  );

  if (riskResponse.ok) {
    riskData = await riskResponse.json();
    console.log('Risk-scenarios response OK:', riskData?.scenarios?.length, 'scenarios');
  } else {
    const errorText = await riskResponse.text();
    console.error('Risk-scenarios API fout:', riskResponse.status, errorText);
  }
} catch (error) {
  console.error('Risk-scenarios API niet bereikbaar:', error);
}
```

**Let op de `console.error` met `errorText`** — dit geeft nu de exacte validatiefout weer als het nog steeds faalt.

---

## Stap 4: Relatiebeëindiging /calculate calls fixen

De `/calculate` endpoint vereist een `X-API-Key` header. Gebruik dezelfde `getApiHeaders()` functie (of vergelijkbaar patroon) die de frontend al gebruikt voor reguliere berekeningen.

### 4a. Zoek de bestaande API-key helper

Zoek in de codebase naar de functie die de API-key header meestuurt bij `/calculate` calls. Dit is waarschijnlijk iets als:

```typescript
// Zoek naar een van deze patronen in de bestaande code:
// getApiHeaders()
// { 'X-API-Key': ... }
// apiKey
// API_KEY
```

### 4b. Gebruik dezelfde headers bij relatiebeëindiging calls

Vervang de relatiebeëindiging fetch calls (de 2 `POST /calculate` calls voor aanvrager-alleen en partner-alleen) zodat ze dezelfde headers gebruiken:

```typescript
if (hasPartner) {
  let maxHypotheekAanvragerAlleen = 0;
  let maxHypotheekPartnerAlleen = 0;

  // Leningdelen voor /calculate (excl. overbrugging), met correcte API-veldnamen
  const leningdelenVoorCalculate = rawLeningdelen
    .filter((d: any) => (d.aflossingsvorm || '').toLowerCase() !== 'overbrugging')
    .map((deel: any) => {
      const rentePercentage = deel.rentepercentage || 5;
      const renteDecimaal = rentePercentage > 1 ? rentePercentage / 100 : rentePercentage;
      return {
        aflos_type: mapAflosvorm(deel.aflossingsvorm || 'annuiteit'),
        org_lpt: deel.origineleLooptijd || 360,
        rest_lpt: deel.restantLooptijd || 360,
        hoofdsom_box1: deel.bedrag || 0,
        hoofdsom_box3: deel.bedragBox3 || 0,
        rvp: deel.rentevastePeriode || 120,
        werkelijke_rente: renteDecimaal,
        inleg_overig: deel.inleg || 0,
      };
    });

  try {
    // Haal de API headers op (met X-API-Key)
    const apiHeaders = getApiHeaders();  // ← gebruik de bestaande helper!

    // Aanvrager alleen
    const resAanvrager = await fetch(
      'https://nat-hypotheek-api.onrender.com/calculate',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...apiHeaders,  // bevat X-API-Key
        },
        body: JSON.stringify({
          hoofd_inkomen_aanvrager: hoofdinkomenAanvrager,
          hoofd_inkomen_partner: 0,
          alleenstaande: 'JA',
          ontvangt_aow: 'NEE',
          energielabel: 'Geen (geldig) Label',
          verduurzamings_maatregelen: 0,
          limieten_bkr_geregistreerd: 0,
          studievoorschot_studielening: 0,
          erfpachtcanon_per_jaar: 0,
          jaarlast_overige_kredieten: 0,
          hypotheek_delen: leningdelenVoorCalculate,
        }),
      }
    );

    if (resAanvrager.ok) {
      const dataAanvrager = await resAanvrager.json();
      maxHypotheekAanvragerAlleen = dataAanvrager?.scenario1?.annuitair?.max_box1 || 0;
    } else {
      console.error('Calculate aanvrager-alleen:', resAanvrager.status, await resAanvrager.text());
    }

    // Partner alleen
    const resPartner = await fetch(
      'https://nat-hypotheek-api.onrender.com/calculate',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...apiHeaders,
        },
        body: JSON.stringify({
          hoofd_inkomen_aanvrager: hoofdinkomenPartner,
          hoofd_inkomen_partner: 0,
          alleenstaande: 'JA',
          ontvangt_aow: 'NEE',
          energielabel: 'Geen (geldig) Label',
          verduurzamings_maatregelen: 0,
          limieten_bkr_geregistreerd: 0,
          studievoorschot_studielening: 0,
          erfpachtcanon_per_jaar: 0,
          jaarlast_overige_kredieten: 0,
          hypotheek_delen: leningdelenVoorCalculate,
        }),
      }
    );

    if (resPartner.ok) {
      const dataPartner = await resPartner.json();
      maxHypotheekPartnerAlleen = dataPartner?.scenario1?.annuitair?.max_box1 || 0;
    } else {
      console.error('Calculate partner-alleen:', resPartner.status, await resPartner.text());
    }
  } catch (error) {
    console.error('Relatiebeëindiging berekening mislukt:', error);
  }

  // Bouw relatiebeëindiging sectie (alleen als er resultaten zijn)
  // ... bestaande code uit G5 Deel E2 ...
}
```

**Belangrijk:** Als de functie `getApiHeaders()` niet bestaat in jouw codebase, zoek dan naar hoe de bestaande `POST /calculate` calls (in de wizard stappen) de API-key header meesturen. Gebruik exact hetzelfde patroon. Mogelijke varianten:

```typescript
// Variant 1: functie
const headers = getApiHeaders();

// Variant 2: direct uit env/config
const headers = { 'X-API-Key': import.meta.env.VITE_API_KEY };

// Variant 3: uit Supabase config
const headers = { 'X-API-Key': apiKey };
```

---

## Stap 5: Leningdelen weergave fixen

### 5a. Aflosvorm capitalisatie in PDF

De leningdelen tabel in de PDF toont "overbrugging" (kleine letter). Gebruik `mapAflosvorm` ook voor de weergave, of maak een aparte display-helper:

```typescript
function displayAflosvorm(aflosvorm: string): string {
  const mapping: Record<string, string> = {
    'annuiteit': 'Annuïtair',
    'annuïteit': 'Annuïtair',
    'lineair': 'Lineair',
    'aflossingsvrij': 'Aflossingsvrij',
    'aflosvrij': 'Aflossingsvrij',
    'spaarhypotheek': 'Spaarhypotheek',
    'overbrugging': 'Overbrugging',
  };
  return mapping[aflosvorm?.toLowerCase()] || aflosvorm;
}
```

Gebruik `displayAflosvorm(deel.aflossingsvorm)` in de leningdelen tabel rows.

### 5b. Rente weergave

De rente staat al als percentage in Lovable (2.8, 4.1, 4.3). Gebruik het direct voor weergave:

```typescript
// In de leningdelen tabel:
const renteStr = `${Number(deel.rentepercentage || 0).toFixed(2).replace('.', ',')}%`;
// Resultaat: "2,80%", "4,10%", "4,30%"
```

---

## Stap 6: Geldverstrekker + maandlasten

### 6a. Geldverstrekker

De geldverstrekker staat niet in de `invoer` JSONB. Probeer deze extra paden:

```typescript
const geldverstrekker =
  dossierScenario?.geldverstrekker ||
  invoer?.geldverstrekker ||
  scenario?.geldverstrekker ||
  '';

// Als het nog steeds leeg is, check of het op het dossier/aanvraag niveau staat
// console.log('Dossier scenario keys:', Object.keys(dossierScenario));
```

Als de geldverstrekker niet in `invoer` zit, moet het in een apart Supabase-veld op het dossier staan. Log `Object.keys(dossierScenario)` om te zien of het er is.

### 6b. Maandlasten live ophalen

De `maandlastenResultaten` zijn niet opgeslagen in invoer. Je kunt ze **live berekenen** met een `POST /calculate/monthly-costs` call:

```typescript
let brutoMaandlast = 0;
let nettoMaandlast = 0;

if (leningdelenVoorApi.length > 0 && woningwaarde > 0) {
  try {
    const monthlyCostsRequest = {
      fiscal_year: new Date().getFullYear(),
      woz_value: woningwaarde,
      loan_parts: leningdelenVoorApi
        .filter(d => d.aflos_type !== 'Overbrugging')  // excl. overbrugging
        .map((d, i) => ({
          id: `deel_${i + 1}`,
          principal: (d.hoofdsom_box1 || 0) + (d.hoofdsom_box3 || 0),
          interest_rate: d.werkelijke_rente * 100,  // API verwacht percentage
          term_years: Math.round((d.org_lpt || 360) / 12),
          loan_type: d.aflos_type === 'Annuïteit' ? 'annuity'
            : d.aflos_type === 'Lineair' ? 'linear'
            : 'interest_only',
          box: d.hoofdsom_box3 > 0 ? 3 : 1,
        })),
      partners: [
        {
          id: 'aanvrager',
          taxable_income: hoofdinkomenAanvrager,
          age: berekenLeeftijd(klant.geboortedatumAanvrager),
          is_aow: false,
        },
        ...(hasPartner ? [{
          id: 'partner',
          taxable_income: hoofdinkomenPartner,
          age: berekenLeeftijd(klant.geboortedatumPartner),
          is_aow: false,
        }] : []),
      ],
      partner_distribution: hasPartner ? { method: 'optimize' } : undefined,
    };

    const mcResponse = await fetch(
      'https://nat-hypotheek-api.onrender.com/calculate/monthly-costs',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(monthlyCostsRequest),
      }
    );

    if (mcResponse.ok) {
      const mcData = await mcResponse.json();
      brutoMaandlast = mcData?.total_gross_monthly || 0;
      nettoMaandlast = mcData?.net_monthly_cost || 0;
      console.log('Maandlasten:', { brutoMaandlast, nettoMaandlast });
    } else {
      console.error('Monthly-costs API:', mcResponse.status, await mcResponse.text());
    }
  } catch (error) {
    console.error('Monthly-costs API fout:', error);
  }
}
```

### 6c. Maandlast highlight toevoegen

Na het ophalen van de maandlasten, update de highlights in de summary:

```typescript
// In de highlights array van de summary sectie, voeg toe:
...(nettoMaandlast > 0 ? [{
  label: 'Netto maandlast',
  value: formatBedrag(Math.round(nettoMaandlast)),
  note: brutoMaandlast > 0 ? `Bruto: ${formatBedrag(Math.round(brutoMaandlast))}` : undefined,
}] : []),
```

Voeg ook de maandlasten toe aan de leningdelen sectie (onder de tabel):

```typescript
// In de loan-parts sectie, voeg rows toe:
...(brutoMaandlast > 0 || nettoMaandlast > 0 ? {
  rows: [
    ...(brutoMaandlast > 0 ? [{ label: 'Bruto maandlast', value: formatBedrag(Math.round(brutoMaandlast)) }] : []),
    ...(nettoMaandlast > 0 ? [{ label: 'Netto maandlast', value: formatBedrag(Math.round(nettoMaandlast)), bold: true }] : []),
  ],
} : {}),
```

---

## Stap 7: Samenvatting — eigen inbreng fixen

De samenvatting toont "Eigen inbreng € 0" als los row. Dit is uit `mortgage_summary`. Vervang dit met correcte data:

```typescript
// mortgage_summary rows: alleen tonen als er waarden zijn
const mortgageSummary: any[] = [];

// Leningdelen als rows
rawLeningdelen.forEach((deel: any, i: number) => {
  const bedrag = (deel.bedrag || 0) + (deel.bedragBox3 || 0);
  if (bedrag > 0) {
    mortgageSummary.push({
      label: `Leningdeel ${i + 1}`,
      value: formatBedrag(bedrag),
    });
  }
});

// Eigen inbreng alleen tonen als > 0
const eigenInbreng = fin?.eigenGeld || fin?.eigen_geld || 0;
if (eigenInbreng > 0) {
  mortgageSummary.push({
    label: 'Eigen inbreng',
    value: formatBedrag(eigenInbreng),
  });
}
```

---

## Stap 8: AO/WW grafiek labels (herhaling uit G6)

Als de AO grafiek labels nog steeds "aanvrager aanvrager aanvrager" tonen, zoek dan de code die `chart_data.labels` opbouwt voor `type: 'vergelijk_fasen'` en vervang de label-extractie:

```typescript
// AO labels: verwijder prefix, behoud fasenaam
.map((s: any) => {
  // "AO aanvrager — loondoorbetaling" → "Loondoorbetaling"
  const label = s.naam
    .replace(/^AO\s+(aanvrager|partner)\s*[—–-]\s*/i, '')
    .trim();
  // Eerste letter hoofdletter
  return label.charAt(0).toUpperCase() + label.slice(1) || s.naam;
})

// WW labels: idem
.map((s: any) => {
  const label = s.naam
    .replace(/^(Werkloosheid|Na WW)\s+(aanvrager|partner)\s*[—–-]?\s*/i, '')
    .trim();
  return label || s.naam;
})
```

---

## Verificatie

| # | Check | Verwacht |
|---|-------|----------|
| 1 | Console: `Risk-scenarios request:` | Correct JSON met `werkelijke_rente` < 0.20 |
| 2 | Console: `Risk-scenarios response OK:` | Aantal scenarios > 0 |
| 3 | Console: geen 422 of 403 errors | Clean |
| 4 | PDF: Pensioen sectie | Met SVG grafiek en max hypotheek |
| 5 | PDF: Overlijden sectie (stel) | 2 kolommen met grafieken |
| 6 | PDF: AO sectie | Fase-labels (Loondoorbetaling, WGA, etc.) |
| 7 | PDF: WW sectie | Per-persoon met grafiek |
| 8 | PDF: Relatiebeëindiging (stel) | 2 kolommen met max hypotheek |
| 9 | PDF: Scenario checks in samenvatting | Gekleurde bolletjes per risico |
| 10 | PDF: Samenvatting highlights | Hypotheek + woningwaarde + maandlast |
| 11 | PDF: Leningdelen aflosvorm | "Aflossingsvrij" (niet "aflossingsvrij") |
| 12 | PDF: Eigen inbreng | Niet getoond als € 0 |

**Na het genereren:** check de console output. Als er nog errors zijn, kopieer de foutmelding (vooral de `errorText` bij 422) en stuur die naar mij.

---

## Samenvatting wijzigingen

| Onderdeel | Wijziging |
|-----------|-----------|
| `mapAflosvorm()` | Lovable lowercase → API format (annuiteit → Annuïteit) |
| `mapLeningdeelVoorApi()` | Rente /100 + correcte veldnamen |
| `displayAflosvorm()` | Capitalisatie voor PDF weergave |
| Risk-scenarios request | Overbrugging uitgefilterd, rente als decimaal, correcte veldnamen |
| Relatiebeëindiging calls | `getApiHeaders()` met X-API-Key, overbrugging gefilterd |
| Leningdelen extractie | `_dossierScenario1.leningDelen` pad |
| Maandlasten | Live `POST /calculate/monthly-costs` call |
| Samenvatting | Eigen inbreng alleen als > 0, leningdelen als rows |
| AO/WW labels | Prefix strippen, fasenaam behouden |
