# Lovable Prompt G4: Adviesrapport — resultaten opslaan + rapportgeneratie

> Dit prompt lost het kernprobleem op: het adviesrapport is leeg omdat de API-resultaten (max hypotheek, maandlasten) niet worden opgeslagen. Na deze prompt worden alle berekeningen mee-opgeslagen en correct verwerkt in het rapport.

---

## Overzicht van wijzigingen

1. **NAT-resultaten opslaan** bij haalbaarheidsberekening (stap 2)
2. **Maandlasten-resultaten opslaan** bij leningdelen-berekening (stap 4)
3. **Dialog vereenvoudigen** — klantprofiel velden, adviseur-dropdown, geen sectie-checkboxes
4. **Rapportgeneratie herschrijven** — volledige payload met alle secties en echte data
5. **Risk-scenarios API aanroepen** bij rapport generatie

---

## Deel A: API-resultaten opslaan in wizard-state

### A1. NAT-resultaten opslaan (stap 2 — Haalbaarheid)

Zoek de functie die `POST /calculate` aanroept (de haalbaarheidsberekening in stap 2). Dit is waar het toetsinkomen, de maximale hypotheek en woonquotes worden berekend.

**Na een succesvolle API-call**, sla het volledige response op in de wizard-state:

```typescript
// Na succesvolle POST /calculate response
const natResult = await response.json();

// Sla op in state — per tab/scenario index
setInvoer(prev => ({
  ...prev,
  natResultaten: {
    ...prev.natResultaten,
    [tabIndex]: natResult,  // Volledige response incl. scenario1, scenario2, debug
  },
}));
```

**Belangrijk:** Sla het **volledige** response object op, niet alleen een subset. Het bevat:
- `scenario1.annuitair.max_box1` — maximale hypotheek
- `debug.toets_inkomen` — toetsinkomen
- `debug.toets_rente` — toetsrente
- `debug.woonquote_box1` — woonquote

### A2. Maandlasten-resultaten opslaan (stap 4 — Leningdelen)

Zoek de functie die `POST /calculate/monthly-costs` aanroept. Dit is waar de bruto/netto maandlast wordt berekend.

**Na een succesvolle API-call**, sla het volledige response op:

```typescript
// Na succesvolle POST /calculate/monthly-costs response
const maandlastenResult = await response.json();

setInvoer(prev => ({
  ...prev,
  maandlastenResultaten: {
    ...prev.maandlastenResultaten,
    [scenarioIndex]: maandlastenResult,
  },
}));
```

Dit response bevat o.a.:
- `total_gross_monthly` — bruto maandlast
- `net_monthly_cost` — netto maandlast
- `tax_breakdown.marginal_rate` — marginaal belastingtarief
- `loan_parts[]` — per leningdeel: rente, aflossing, restschuld

### A3. Mee-opslaan bij "Opslaan" actie

Controleer dat bij het opslaan van de berekening (de "Opslaan" knop) ook `natResultaten` en `maandlastenResultaten` worden mee-opgeslagen in het `invoer` JSONB-veld:

```typescript
// Bij opslaan naar Supabase
const invoerPayload = {
  klantGegevens: invoer.klantGegevens,
  haalbaarheidsBerekeningen: invoer.haalbaarheidsBerekeningen,
  berekeningen: invoer.berekeningen,
  scenarios: invoer.scenarios,
  natResultaten: invoer.natResultaten,                 // NIEUW
  maandlastenResultaten: invoer.maandlastenResultaten, // NIEUW
};
```

En bij het **laden** van een bestaand dossier: herstel `natResultaten` en `maandlastenResultaten` uit de opgeslagen data (met `{}` als fallback voor oudere dossiers).

---

## Deel B: Dialog vereenvoudigen

### B1. Vervang het configuratiescherm

Het huidige configuratiescherm (stap 2 van de adviesrapport-dialog, na aanvraag-selectie) moet worden vervangen. Verwijder:
- De linkerkolom met sectie-checkboxes (secties worden automatisch bepaald)
- Geldverstrekker, productlijn, NHG velden (komen uit de aanvraag)
- Scenario dropdown (gebruik altijd het eerste scenario)

### B2. Nieuwe dialog layout

Twee kolommen:

**Linkerkolom — Rapport meta:**

| Veld | Type | Standaard |
|------|------|-----------|
| Adviseur | Dropdown (uit `profiles` tabel, alle users met `role = 'adviseur'` of `role = 'admin'`) | Eigenaar van het dossier |
| Datum | Datumveld (DD-MM-YYYY) | Vandaag |
| Dossiernummer | Tekstveld | Dossiernummer van het dossier |

**Rechterkolom — Klantprofiel:**

Bovenste deel — kennis en ervaring:

| Veld | Opties | Standaard |
|------|--------|-----------|
| Ervaring met een hypotheek | "Ja", "Nee" | "Nee" |
| Kennis van hypotheekvormen | "Geen", "Beperkt", "Redelijk", "Goed" | "Redelijk" |
| Kennis van fiscale regels | "Geen", "Beperkt", "Matig", "Goed" | "Matig" |
| Klantprioriteit | "Stabiele maandlast", "Zo laag mogelijke maandlast", "Zo snel mogelijk aflossen", "Maximale flexibiliteit" | "Stabiele maandlast" |

Onderste deel — risicobereidheid (6 dropdowns):

| Risico | Opties | Standaard |
|--------|--------|-----------|
| Pensioen | "Risico aanvaarden", "Risico een beetje beperken", "Risico zoveel mogelijk beperken", "Risico niet bereid te aanvaarden" | "Risico een beetje beperken" |
| Arbeidsongeschiktheid | Zelfde opties | "Risico een beetje beperken" |
| Werkloosheid | Zelfde opties | "Risico aanvaarden" |
| Waardedaling woning | Zelfde opties | "Risico een beetje beperken" |
| Rentestijging | Zelfde opties | "Risico aanvaarden" |
| Aflopen hypotheekrenteaftrek | Zelfde opties | "Risico aanvaarden" |

### B3. Adviseur-dropdown uit Supabase

```typescript
const { data: adviseurs } = await supabase
  .from('profiles')
  .select('id, user_name, email, role')
  .in('role', ['adviseur', 'admin'])
  .order('user_name');
```

Toon `user_name` (of `email` als fallback) in de dropdown. Default = eigenaar van het dossier.

---

## Deel C: Rapportgeneratie flow herschrijven

### C1. "Genereer rapport" klik-flow

Wanneer de gebruiker op "Genereer rapport" klikt, moet het volgende gebeuren:

```
1. Lees invoer uit de geselecteerde aanvraag (Supabase)
2. Extract data: klantGegevens, berekeningen, scenarios, natResultaten, maandlastenResultaten
3. Roep POST /calculate/risk-scenarios aan (zie Deel D)
4. Bouw de adviesrapport-payload op (alle secties)
5. Stuur naar POST /adviesrapport-pdf
6. Download het PDF-bestand
```

Toon een laad-indicator ("Rapport wordt gegenereerd...") tijdens stap 3-5.

### C2. Data extractie uit aanvraag

```typescript
// Aanvraag data uit Supabase
const invoer = aanvraag.data;  // Het invoer JSONB-veld

// Klantgegevens
const klant = invoer.klantGegevens || {};
const hasPartner = !klant.alleenstaand;
const aanvragerNaam = klant.naamAanvrager || '';
const partnerNaam = klant.naamPartner || '';

// Berekening data
const ber = invoer.haalbaarheidsBerekeningen?.[0] || {};
const fin = invoer.berekeningen?.[0] || {};
const scenario = invoer.scenarios?.[0] || {};

// API-resultaten (opgeslagen in Deel A)
const natRes = invoer.natResultaten?.[0] || invoer.natResultaten?.['0'] || {};
const maandRes = invoer.maandlastenResultaten?.[0] || invoer.maandlastenResultaten?.['0'] || {};

// Geldverstrekker, productlijn, NHG uit scenario of aanvraag
const geldverstrekker = scenario?.geldverstrekker || invoer?.geldverstrekker || '';
const productlijn = scenario?.productlijn || invoer?.productlijn || '';
const nhg = scenario?.nhg || invoer?.nhgToepassen || fin?.nhgKosten > 0 || false;

// Leningdelen
const leningdelen = scenario?.leningdelen || [];

// Hypotheekbedrag berekenen
let hypotheekBedrag = 0;
if (fin?.totaalInvestering && fin?.totaalEigenMiddelen) {
  hypotheekBedrag = fin.totaalInvestering - fin.totaalEigenMiddelen;
}
if (hypotheekBedrag === 0 && leningdelen.length > 0) {
  hypotheekBedrag = leningdelen.reduce((sum, deel) =>
    sum + (deel.bedragBox1 || deel.hoofdsomBox1 || deel.bedrag || 0)
        + (deel.bedragBox3 || deel.hoofdsomBox3 || 0), 0);
}
```

### C3. Payload opbouwen — alle secties

Bouw de volledige payload op voor `POST /adviesrapport-pdf`. Gebruik `formatBedrag()` voor alle bedragen (de API verwacht geformateerde strings).

```typescript
const payload = {
  meta: {
    title: 'Adviesrapport Hypotheek',
    date: options.datum,
    dossierNumber: options.dossierNummer,
    advisor: options.adviseur,
    customerName: hasPartner
      ? `${aanvragerNaam} en ${partnerNaam}`
      : aanvragerNaam,
    propertyAddress: fin?.adres || klant?.adres || '',
  },
  bedrijf: {
    naam: 'Hondsrug Finance',
    email: 'Info@hondsrugfinance.nl',
    telefoon: '+31 88 400 2700',
    kvk: 'KVK 93276699',
  },
  sections: [],
};
```

### C4. Sectie 1 — Samenvatting (`id: "summary"`)

```typescript
sections.push({
  id: 'summary',
  title: 'Samenvatting advies',
  visible: true,
  narratives: [
    `U wilt een hypotheek afsluiten voor ${invoer.dossierType || 'aankoop bestaande woning'}.`,
    'Op basis van uw financiële situatie, uw wensen en de geldende leennormen hebben wij beoordeeld dat de geadviseerde financiering passend is binnen uw situatie.',
    ...(nhg ? ['De hypotheek wordt aangevraagd met Nationale Hypotheek Garantie.'] : []),
  ],
  highlights: [
    {
      label: 'Hypotheekbedrag',
      value: formatBedrag(hypotheekBedrag),
      note: [geldverstrekker, productlijn].filter(Boolean).join(' — '),
    },
    {
      label: 'Hypotheekverstrekker',
      value: geldverstrekker || '-',
      note: productlijn || '',
    },
    {
      label: 'Bruto maandlast',
      value: formatBedrag(maandRes?.total_gross_monthly || 0),
      note: `Netto ${formatBedrag(maandRes?.net_monthly_cost || 0)}`,
    },
    {
      label: 'Woningwaarde',
      value: formatBedrag(fin?.wozWaarde || fin?.aankoopsom || 0),
      note: '',
    },
  ],
  // advice_text wordt later toegevoegd via buildAdviceText()
  advice_text: buildAdviceText(invoer, options, natRes, maandRes, hypotheekBedrag, hasPartner),
  mortgage_summary: leningdelen.map((deel, i) => ({
    label: `Leningdeel ${i + 1}`,
    value: formatBedrag((deel.bedragBox1 || 0) + (deel.bedragBox3 || 0)),
  })),
});
```

### C5. Sectie 2 — Klantprofiel (`id: "client-profile"`)

```typescript
sections.push({
  id: 'client-profile',
  title: 'Klantprofiel',
  visible: true,
  rows: [
    { label: 'Aanvrager', value: aanvragerNaam },
    { label: 'Geboortedatum', value: klant.geboortedatumAanvrager || '' },
    ...(hasPartner ? [
      { label: '', value: '' },
      { label: 'Partner', value: partnerNaam },
      { label: 'Geboortedatum', value: klant.geboortedatumPartner || '' },
    ] : []),
    { label: '', value: '' },
    { label: 'Doel', value: invoer.dossierType || 'Aankoop bestaande woning' },
    { label: 'Ervaring met een hypotheek', value: options.ervaringHypotheek },
    { label: 'Kennis van hypotheekvormen', value: options.kennisHypotheekvormen },
    { label: 'Kennis van fiscale regels', value: options.kennisFiscaleRegels },
    { label: 'Klantprioriteit', value: options.klantPrioriteit },
  ],
  tables: [{
    headers: ['Financiële risico\'s', 'Risicobereidheid'],
    rows: [
      ['Pensioen', options.risicobereidheid.pensioen],
      ['Arbeidsongeschiktheid', options.risicobereidheid.arbeidsongeschiktheid],
      ['Werkloosheid', options.risicobereidheid.werkloosheid],
      ['Waardedaling woning', options.risicobereidheid.waardedalingWoning],
      ['Rentestijging', options.risicobereidheid.rentestijging],
      ['Aflopen hypotheekrenteaftrek', options.risicobereidheid.aflopenRenteaftrek],
    ],
  }],
});
```

### C6. Sectie 3 — Betaalbaarheid (`id: "affordability"`)

```typescript
const maxHypotheek = natRes?.scenario1?.annuitair?.max_box1 || 0;

sections.push({
  id: 'affordability',
  title: 'Betaalbaarheid',
  visible: maxHypotheek > 0 || (maandRes?.total_gross_monthly || 0) > 0,
  narratives: maxHypotheek > 0 ? [
    `Op basis van het toetsinkomen van ${formatBedrag(natRes?.debug?.toets_inkomen || 0)} ` +
    `en een toetsrente van ${((natRes?.debug?.toets_rente || 0) * 100).toFixed(3)}% ` +
    `is de maximale hypotheek ${formatBedrag(maxHypotheek)}.`,
  ] : [],
  rows: [
    ...(natRes?.debug?.toets_inkomen ? [
      { label: 'Toetsinkomen', value: formatBedrag(natRes.debug.toets_inkomen) },
    ] : []),
    ...(natRes?.debug?.toets_rente ? [
      { label: 'Toetsrente', value: `${(natRes.debug.toets_rente * 100).toFixed(3)}%` },
    ] : []),
    ...(natRes?.debug?.woonquote_box1 ? [
      { label: 'Woonquote', value: `${(natRes.debug.woonquote_box1 * 100).toFixed(1)}%` },
    ] : []),
    ...(maxHypotheek > 0 ? [
      { label: 'Maximale hypotheek', value: formatBedrag(maxHypotheek) },
    ] : []),
    { label: '', value: '' },
    { label: 'Geadviseerd hypotheekbedrag', value: formatBedrag(hypotheekBedrag), bold: true },
    ...(maandRes?.total_gross_monthly ? [
      { label: 'Bruto maandlast', value: formatBedrag(maandRes.total_gross_monthly) },
    ] : []),
    ...(maandRes?.net_monthly_cost ? [
      { label: 'Netto maandlast', value: formatBedrag(maandRes.net_monthly_cost), bold: true },
    ] : []),
  ],
});
```

### C7. Sectie 4 — Financieringsopzet (`id: "financing"`)

```typescript
sections.push({
  id: 'financing',
  title: 'Financieringsopzet',
  visible: hypotheekBedrag > 0,
  subsections: [
    {
      subtitle: 'Investering',
      rows: [
        ...(fin?.aankoopsom ? [{ label: 'Aankoopsom', value: formatBedrag(fin.aankoopsom) }] : []),
        ...(fin?.verbouwing ? [{ label: 'Verbouwing', value: formatBedrag(fin.verbouwing) }] : []),
        ...(fin?.totaalInvestering ? [
          { label: 'Totaal investering', value: formatBedrag(fin.totaalInvestering), bold: true },
        ] : []),
      ],
    },
    {
      subtitle: 'Kosten',
      rows: [
        ...(fin?.advieskosten ? [{ label: 'Advieskosten', value: formatBedrag(fin.advieskosten) }] : []),
        ...(fin?.notariskosten ? [{ label: 'Notariskosten', value: formatBedrag(fin.notariskosten) }] : []),
        ...(fin?.taxatiekosten ? [{ label: 'Taxatiekosten', value: formatBedrag(fin.taxatiekosten) }] : []),
        ...(fin?.nhgKosten ? [{ label: 'NHG-kosten', value: formatBedrag(fin.nhgKosten) }] : []),
        ...(fin?.overdrachtsbelasting ? [
          { label: 'Overdrachtsbelasting', value: formatBedrag(fin.overdrachtsbelasting) },
        ] : []),
      ],
    },
    {
      subtitle: 'Financiering',
      rows: [
        { label: 'Benodigd hypotheekbedrag', value: formatBedrag(hypotheekBedrag), bold: true },
        ...(fin?.totaalEigenMiddelen ? [
          { label: 'Eigen middelen', value: formatBedrag(fin.totaalEigenMiddelen) },
        ] : []),
      ],
    },
  ],
});
```

### C8. Sectie 5 — Hypotheekonderdelen (`id: "loan-parts"`)

```typescript
const aflosvormLabels = {
  'Annuïteit': 'Annuïtair', 'annuiteit': 'Annuïtair',
  'Lineair': 'Lineair', 'lineair': 'Lineair',
  'Aflosvrij': 'Aflossingsvrij', 'aflossingsvrij': 'Aflossingsvrij',
  'Spaar': 'Spaarhypotheek', 'spaarhypotheek': 'Spaarhypotheek',
};

sections.push({
  id: 'loan-parts',
  title: 'Hypotheekonderdelen',
  visible: leningdelen.length > 0,
  rows: [
    ...(geldverstrekker ? [{ label: 'Geldverstrekker', value: geldverstrekker }] : []),
    ...(productlijn ? [{ label: 'Productlijn', value: productlijn }] : []),
    ...(nhg ? [{ label: 'NHG', value: 'Ja' }] : []),
  ],
  tables: [{
    headers: ['#', 'Bedrag', 'Aflosvorm', 'Rente', 'Looptijd', 'RVP'],
    rows: leningdelen.map((deel, i) => [
      `${i + 1}`,
      formatBedrag((deel.bedragBox1 || deel.hoofdsomBox1 || 0) + (deel.bedragBox3 || deel.hoofdsomBox3 || 0)),
      aflosvormLabels[deel.aflossingsvorm || deel.aflos_type || 'Annuïteit'] || deel.aflossingsvorm || '',
      `${((deel.rente || deel.werkelijkeRente || 0) * 100).toFixed(2)}%`,
      `${Math.round((deel.looptijd || deel.org_lpt || 360) / 12)} jaar`,
      `${Math.round((deel.rvp || 120) / 12)} jaar`,
    ]),
    ...(leningdelen.length > 1 ? {
      totals: [
        'Totaal',
        formatBedrag(hypotheekBedrag),
        '', '', '', '',
      ],
    } : {}),
  }],
});
```

### C9. Sectie 6 — Aandachtspunten (`id: "attention-points"`)

```typescript
const aandachtspunten = [];
if (nhg) aandachtspunten.push('De hypotheek wordt aangevraagd met NHG. De NHG-voorwaarden moeten worden nageleefd.');
if (hypotheekBedrag > maxHypotheek && maxHypotheek > 0) {
  aandachtspunten.push('Het geadviseerde hypotheekbedrag overschrijdt de maximale hypotheek op basis van inkomen.');
}
// Voeg meer aandachtspunten toe op basis van beschikbare data

sections.push({
  id: 'attention-points',
  title: 'Aandachtspunten',
  visible: aandachtspunten.length > 0,
  narratives: aandachtspunten,
});
```

### C10. Sectie 7 — Disclaimer (`id: "disclaimer"`)

```typescript
sections.push({
  id: 'disclaimer',
  title: 'Disclaimer',
  visible: true,
  narratives: [
    'Dit adviesrapport is opgesteld op basis van de door u aangeleverde gegevens en de op het moment van advisering geldende wet- en regelgeving. ' +
    'Aan dit rapport kunnen geen rechten worden ontleend. De uiteindelijke hypotheekofferte wordt opgesteld door de geldverstrekker.',
  ],
});
```

### C11. API-call en PDF download

```typescript
// Stuur naar backend
const response = await fetch('https://nat-hypotheek-api.onrender.com/adviesrapport-pdf', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(payload),
});

if (!response.ok) {
  toast.error('Fout bij genereren adviesrapport');
  return;
}

// Download PDF
const blob = await response.blob();
const url = URL.createObjectURL(blob);
const a = document.createElement('a');
a.href = url;
a.download = `Adviesrapport - ${payload.meta.customerName}.pdf`;
a.click();
URL.revokeObjectURL(url);

toast.success('Adviesrapport gegenereerd!');
```

---

## Deel D: Risk-scenarios API (optioneel, voor latere uitbreiding)

> **Dit deel is optioneel.** Als je eerst een werkend rapport wilt met de basissecties (samenvatting, klantprofiel, betaalbaarheid, financieringsopzet, leningdelen), skip dan Deel D en voeg het later toe.

### D1. Risk-scenarios aanroepen

Bij "Genereer rapport", roep `POST /calculate/risk-scenarios` aan met data uit de opgeslagen aanvraag:

```typescript
const riskScenariosRequest = {
  hypotheek_delen: leningdelen.map(deel => ({
    aflos_type: deel.aflossingsvorm || deel.aflos_type || 'Annuïteit',
    org_lpt: deel.looptijd || deel.org_lpt || 360,
    rest_lpt: deel.restLooptijd || deel.rest_lpt || deel.looptijd || 360,
    hoofdsom_box1: deel.bedragBox1 || deel.hoofdsomBox1 || 0,
    hoofdsom_box3: deel.bedragBox3 || deel.hoofdsomBox3 || 0,
    rvp: deel.rvp || 120,
    werkelijke_rente: deel.rente || deel.werkelijkeRente || 0.05,
    inleg_overig: deel.inlegOverig || 0,
  })),
  ingangsdatum_hypotheek: new Date().toISOString().split('T')[0],
  geboortedatum_aanvrager: klant.geboortedatumAanvrager,
  inkomen_aanvrager_huidig: ber?.inkomenGegevens?.hoofdinkomenAanvrager || 0,
  inkomen_aanvrager_aow: 0,  // AOW-inkomen (indien bekend)
  alleenstaande: hasPartner ? 'NEE' : 'JA',
  geboortedatum_partner: hasPartner ? klant.geboortedatumPartner : null,
  inkomen_partner_huidig: hasPartner ? (ber?.inkomenGegevens?.hoofdinkomenPartner || 0) : 0,
  inkomen_partner_aow: 0,
  toetsrente: natRes?.debug?.toets_rente || 0.05,
  geadviseerd_hypotheekbedrag: hypotheekBedrag,
  energielabel: ber?.onderpand?.energielabel || 'Geen (geldig) Label',
  verduurzamings_maatregelen: ber?.onderpand?.ebvEbb || 0,
  limieten_bkr_geregistreerd: ber?.verplichtingen?.limietenBkr || 0,
  studievoorschot_studielening: ber?.verplichtingen?.studielening || 0,
  erfpachtcanon_per_jaar: ber?.verplichtingen?.erfpacht || 0,
  jaarlast_overige_kredieten: ber?.verplichtingen?.overigeKredieten || 0,
};

const riskResponse = await fetch('https://nat-hypotheek-api.onrender.com/calculate/risk-scenarios', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(riskScenariosRequest),
});

const riskData = await riskResponse.json();
```

### D2. Risk-secties toevoegen aan payload

Filter de scenario's per categorie en bouw secties:

```typescript
const aowScenarios = riskData.scenarios.filter(s => s.categorie === 'aow');
const overlijdenScenarios = riskData.scenarios.filter(s => s.categorie === 'overlijden');
const aoScenarios = riskData.scenarios.filter(s => s.categorie === 'ao');
const wwScenarios = riskData.scenarios.filter(s => s.categorie === 'ww');
```

**Pensioen-sectie** (`id: "retirement"`):

```typescript
if (aowScenarios.length > 0) {
  const pensionRows = aowScenarios.map(s => ({
    label: s.naam,
    value: `Max hypotheek: ${formatBedrag(s.max_hypotheek_annuitair)}`,
  }));

  // Chart data voor SVG grafiek (backend genereert de SVG)
  const chartData = {
    type: 'pensioen',
    jaren: aowScenarios.map(s => ({
      jaar: s.naam,
      max_hypotheek: s.max_hypotheek_annuitair,
      restschuld: s.max_hypotheek_annuitair < hypotheekBedrag
        ? hypotheekBedrag - s.max_hypotheek_annuitair
        : 0,
    })),
    geadviseerd_hypotheekbedrag: hypotheekBedrag,
  };

  sections.push({
    id: 'retirement',
    title: 'Pensioen',
    visible: true,
    narratives: [
      aowScenarios[0].max_hypotheek_annuitair >= hypotheekBedrag
        ? 'Na pensionering blijft de maximale hypotheek boven het geadviseerde hypotheekbedrag.'
        : `Na pensionering daalt de maximale hypotheek onder het geadviseerde bedrag. Er is een tekort van ${formatBedrag(hypotheekBedrag - aowScenarios[0].max_hypotheek_annuitair)}.`,
    ],
    rows: pensionRows,
    chart_data: chartData,
  });
}
```

**Overlijden-sectie** (`id: "risk-death"`, alleen bij stel):

```typescript
if (overlijdenScenarios.length > 0) {
  sections.push({
    id: 'risk-death',
    title: 'Overlijden',
    visible: true,
    columns: overlijdenScenarios.map(s => ({
      title: `Bij overlijden ${s.van_toepassing_op === 'aanvrager' ? aanvragerNaam : partnerNaam}`,
      rows: [
        { label: 'Inkomen nabestaande', value: formatBedrag(s.inkomen_aanvrager + s.inkomen_partner) },
        { label: 'Max hypotheek', value: formatBedrag(s.max_hypotheek_annuitair) },
        ...(s.tekort > 0 ? [{ label: 'Tekort', value: formatBedrag(s.tekort), bold: true }] : []),
      ],
      chart_data: {
        type: 'overlijden_vergelijk',
        huidig_max_hypotheek: natRes?.scenario1?.annuitair?.max_box1 || hypotheekBedrag,
        max_hypotheek_na_overlijden: s.max_hypotheek_annuitair,
        geadviseerd_hypotheekbedrag: hypotheekBedrag,
        label_bar1: 'Huidige situatie',
        label_bar2: `Na overlijden`,
      },
    })),
  });
}
```

**AO-sectie** (`id: "risk-disability"`):

```typescript
if (aoScenarios.length > 0) {
  // Groepeer per persoon
  const aanvragerAO = aoScenarios.filter(s => s.van_toepassing_op === 'aanvrager');
  const partnerAO = aoScenarios.filter(s => s.van_toepassing_op === 'partner');

  const buildAOColumn = (scenarios, naam) => ({
    title: `Arbeidsongeschiktheid ${naam}`,
    rows: scenarios.map(s => ({
      label: s.naam,
      value: formatBedrag(s.max_hypotheek_annuitair),
    })),
    chart_data: {
      type: 'vergelijk_fasen',
      fasen: scenarios.map(s => ({
        label: s.naam.replace(/^AO /, '').replace(/ .*$/, ''),
        max_hypotheek: s.max_hypotheek_annuitair,
      })),
      geadviseerd_hypotheekbedrag: hypotheekBedrag,
    },
  });

  sections.push({
    id: 'risk-disability',
    title: 'Arbeidsongeschiktheid',
    visible: true,
    columns: [
      ...(aanvragerAO.length > 0 ? [buildAOColumn(aanvragerAO, aanvragerNaam)] : []),
      ...(partnerAO.length > 0 ? [buildAOColumn(partnerAO, partnerNaam)] : []),
    ],
  });
}
```

**WW-sectie** (`id: "risk-unemployment"`):

Zelfde structuur als AO, maar met WW-scenarios:

```typescript
if (wwScenarios.length > 0) {
  const aanvragerWW = wwScenarios.filter(s => s.van_toepassing_op === 'aanvrager');
  const partnerWW = wwScenarios.filter(s => s.van_toepassing_op === 'partner');

  const buildWWColumn = (scenarios, naam) => ({
    title: `Werkloosheid ${naam}`,
    rows: scenarios.map(s => ({
      label: s.naam,
      value: formatBedrag(s.max_hypotheek_annuitair),
    })),
    chart_data: {
      type: 'vergelijk_fasen',
      fasen: scenarios.map(s => ({
        label: s.naam.replace(/^WW /, '').replace(/ .*$/, ''),
        max_hypotheek: s.max_hypotheek_annuitair,
      })),
      geadviseerd_hypotheekbedrag: hypotheekBedrag,
    },
  });

  sections.push({
    id: 'risk-unemployment',
    title: 'Werkloosheid',
    visible: true,
    columns: [
      ...(aanvragerWW.length > 0 ? [buildWWColumn(aanvragerWW, aanvragerNaam)] : []),
      ...(partnerWW.length > 0 ? [buildWWColumn(partnerWW, partnerNaam)] : []),
    ],
  });
}
```

---

## Deel E: Debug verwijderen

Na succesvolle test: verwijder de `console.log('=== ADVIESRAPPORT DATA DEBUG ===')` uit het vorige prompt (G3).

---

## Verificatie

| # | Check | Verwacht resultaat |
|---|-------|--------------------|
| 1 | Vul stap 2 (Haalbaarheid) in en bereken | NAT-resultaten worden opgeslagen in state |
| 2 | Vul stap 4 (Leningdelen) in en bereken | Maandlasten worden opgeslagen in state |
| 3 | Klik "Opslaan" → heropen dossier | natResultaten en maandlastenResultaten zijn bewaard |
| 4 | Open "Nieuw advies" dialog | Geen sectie-checkboxes, wel klantprofiel + risicobereidheid |
| 5 | Adviseur-dropdown | Toont alle adviseurs uit profiles tabel |
| 6 | Klik "Genereer rapport" | Laad-indicator, dan PDF download |
| 7 | Samenvatting in PDF | Hypotheekbedrag, geldverstrekker, bruto/netto maandlast gevuld |
| 8 | Klantprofiel in PDF | Kennis/ervaring + risicobereidheid-tabel |
| 9 | Betaalbaarheid in PDF | Toetsinkomen, max hypotheek, maandlasten |
| 10 | Financieringsopzet in PDF | Aankoopsom, kosten, eigen middelen |
| 11 | Hypotheekonderdelen in PDF | Leningdelen tabel met bedragen, rente, looptijd |
| 12 | (Optioneel) Risicosecties | Pensioen, overlijden, AO, WW met grafieken |

---

## Samenvatting

| Onderdeel | Wijziging |
|-----------|-----------|
| Wizard stap 2 | NAT-resultaten opslaan na `/calculate` call |
| Wizard stap 4 | Maandlasten opslaan na `/calculate/monthly-costs` call |
| Opslaan-functie | `natResultaten` + `maandlastenResultaten` mee in JSONB |
| Laden-functie | `natResultaten` + `maandlastenResultaten` herstellen |
| Dialog (stap 2) | Vereenvoudigd: meta + klantprofiel, geen checkboxes |
| Rapportgeneratie | Complete payload met 7+ secties, echte data, PDF download |
| Risk-scenarios (optioneel) | `POST /calculate/risk-scenarios` aanroepen + secties bouwen |
