# Lovable Prompt G1: Adviesrapport genereren vanuit een aanvraag

> Kopieer deze prompt in Lovable om de "Nieuw advies" functionaliteit te bouwen: een adviesrapport-PDF genereren op basis van een afgeronde aanvraag, met een wizard-achtig dialoog voor sectie-selectie en extra opties.

---

## Achtergrond

De dossierpagina toont drie secties: **Berekeningen**, **Aanvragen** en **Adviezen**. De knop "+ Nieuw advies" is al zichtbaar maar doet nog niets. Een advies is een professioneel adviesrapport (PDF) dat wordt gegenereerd op basis van de data uit een afgeronde aanvraag.

De backend API (`POST /adviesrapport-pdf`) is al beschikbaar en accepteert een generieke sectie-structuur. De frontend moet:
1. De gebruiker laten kiezen welke aanvraag als basis dient
2. Een configuratiescherm tonen voor extra opties en sectie-selectie
3. De data uit de gekozen aanvraag omzetten naar het API-formaat
4. De PDF genereren en downloaden

---

## Stap 1: Klik op "+ Nieuw advies" — Selecteer aanvraag

Wanneer de gebruiker op "+ Nieuw advies" klikt, open een **Dialog/Sheet** (modal).

**Eerste stap in de modal: selecteer een aanvraag**

Toon een lijst van alle aanvragen die bij dit dossier horen (uit de Aanvragen-sectie op dezelfde dossierpagina). Elke aanvraag wordt als een selecteerbare kaart getoond:

```
┌─────────────────────────────────────────────┐
│  Selecteer aanvraag als basis               │
│                                             │
│  ┌─ ○ ─────────────────────────────────┐    │
│  │  🏠 Aankoop: Bestaande bouw         │    │
│  │  Laatst bewerkt: 17-2-2026 10:11    │    │
│  └─────────────────────────────────────┘    │
│                                             │
│  ┌─ ○ ─────────────────────────────────┐    │
│  │  🏠 Aanpassen: Oversluiten          │    │
│  │  Laatst bewerkt: 8-3-2026 13:05     │    │
│  └─────────────────────────────────────┘    │
│                                             │
│              [Volgende →]                   │
└─────────────────────────────────────────────┘
```

- Gebruik radio buttons (slechts één aanvraag selecteerbaar)
- Toon de aanvraagnaam en het laatst bewerkt-tijdstip
- De "Volgende" knop is pas actief als een aanvraag is geselecteerd
- Als er maar 1 aanvraag is, selecteer deze automatisch

**Let op:** Als er nog geen aanvragen zijn, toon dan een melding: "Er zijn nog geen aanvragen in dit dossier. Maak eerst een aanvraag aan." met een knop om de modal te sluiten.

---

## Stap 2: Configuratiescherm — Secties en opties

Na het selecteren van een aanvraag toont de modal een configuratiescherm. Hier kan de adviseur bepalen welke onderdelen in het adviesrapport worden opgenomen.

### Layout: twee kolommen

```
┌─────────────────────────────────────────────────────────┐
│  ← Terug          Adviesrapport samenstellen            │
│                                                         │
│  Aanvraag: Aankoop: Bestaande bouw                      │
│                                                         │
│  ┌─ SECTIES ──────────────┐  ┌─ OPTIES ──────────────┐  │
│  │                        │  │                        │  │
│  │  ☑ Samenvatting        │  │  Scenario:             │  │
│  │  ☑ Klantprofiel        │  │  [▾ Huidige situatie]  │  │
│  │  ☑ Onderpand           │  │                        │  │
│  │  ☑ Betaalbaarheid      │  │  Geldverstrekker:      │  │
│  │  ☑ Financieringsopzet  │  │  [▾ ING             ]  │  │
│  │  ☑ Hypotheekonderdelen │  │                        │  │
│  │  ☑ Fiscale aspecten    │  │  Productlijn:          │  │
│  │  ☐ Risico overlijden   │  │  [▾ Annuïtair       ]  │  │
│  │  ☐ Risico AO           │  │                        │  │
│  │  ☐ Risico werkloosheid │  │  ☑ NHG                 │  │
│  │  ☐ Pensionering        │  │                        │  │
│  │  ☑ Aandachtspunten     │  │  Adviseur:             │  │
│  │  ☑ Disclaimer          │  │  [Alex Kuijper CFP®]   │  │
│  │                        │  │                        │  │
│  │  ─────────────────     │  │  Dossiernummer:        │  │
│  │  [Alles aan] [Alles uit]  │  [HF-2026-001      ]   │  │
│  └────────────────────────┘  └────────────────────────┘  │
│                                                         │
│        [Annuleren]              [Genereer rapport →]    │
└─────────────────────────────────────────────────────────┘
```

### Linkerkolom: Sectie-selectie (checkboxen)

Toon de volgende secties als checkboxes. Standaard aan (`☑`) of uit (`☐`) zoals aangegeven:

| Sectie | ID | Standaard |
|--------|----|-----------|
| Samenvatting | `summary` | ☑ Aan |
| Klantprofiel | `client-profile` | ☑ Aan |
| Onderpand | `property` | ☑ Aan |
| Betaalbaarheid | `affordability` | ☑ Aan |
| Financieringsopzet | `financing` | ☑ Aan |
| Hypotheekonderdelen | `loan-parts` | ☑ Aan |
| Fiscale aspecten | `tax` | ☑ Aan |
| Risico bij overlijden | `risk-death` | ☐ Uit |
| Risico bij arbeidsongeschiktheid | `risk-disability` | ☐ Uit |
| Risico bij werkloosheid | `risk-unemployment` | ☐ Uit |
| Pensionering | `retirement` | ☐ Uit |
| Aandachtspunten | `attention-points` | ☑ Aan |
| Disclaimer | `disclaimer` | ☑ Aan |

Voeg onderaan de lijst twee tekstlinks toe: "Alles aan" en "Alles uit" om snel alle checkboxes te togglen.

### Rechterkolom: Opties

| Veld | Type | Standaard | Toelichting |
|------|------|-----------|-------------|
| Scenario | Dropdown | Eerste scenario uit de aanvraag | Welk scenario (tab) als uitgangspunt — toon de scenario-namen uit `invoer.haalbaarheidsBerekeningen[].naam` |
| Geldverstrekker | Tekstveld | Leeg of uit scenario | Naam van de geldverstrekker (bijv. "ING") |
| Productlijn | Tekstveld | Leeg of uit scenario | Productnaam (bijv. "Annuïtair Hypotheek") |
| NHG | Checkbox | Uit berekening | Of NHG wordt toegepast |
| Adviseur | Tekstveld | Naam van ingelogde gebruiker | Naam die op het rapport komt |
| Dossiernummer | Tekstveld | Dossiernummer van het dossier | Kan handmatig worden aangepast |

---

## Stap 3: Data-mapping — Aanvraag → API payload

Wanneer de gebruiker op "Genereer rapport" klikt, moet de frontend de data uit de geselecteerde aanvraag omzetten naar het API-formaat voor `POST /adviesrapport-pdf`.

### API formaat (PdfReport structuur)

```typescript
interface AdviesrapportPayload {
  meta: {
    title: string;          // "Adviesrapport Hypotheek"
    date: string;           // Vandaag, format "DD-MM-YYYY"
    dossierNumber: string;  // Uit opties-kolom
    advisor: string;        // Uit opties-kolom
    customerName: string;   // Klantnaam uit dossier
    propertyAddress: string; // Adres onderpand (als beschikbaar)
  };
  bedrijf: {
    naam: string;           // "Hondsrug Finance"
    email: string;          // "Info@hondsrugfinance.nl"
    telefoon: string;       // "+31 88 400 2700"
    kvk: string;            // "KVK 93276699"
  };
  sections: Section[];      // Array van secties (zie onder)
}

interface Section {
  id: string;
  title: string;
  visible: boolean;          // Uit de sectie-checkboxes
  narratives?: string[];     // Verhaalteksten
  rows?: Row[];              // Label-value paren
  tables?: Table[];          // Tabellen (bv. leningdelen)
  highlights?: Highlight[];  // Uitgelichte waarden
}

interface Row {
  label: string;
  value: string;
  bold?: boolean;
}

interface Table {
  headers: string[];
  rows: string[][];
}

interface Highlight {
  label: string;
  value: string;
  note?: string;
}
```

### Maak een nieuw bestand `src/utils/adviesrapportBuilder.ts`

Dit bestand bevat de functie die de aanvraag-data omzet naar het API-formaat. Structuur:

```typescript
import { formatBedrag } from '@/utils/berekeningen';

interface AdviesrapportOptions {
  selectedSections: string[];  // IDs van aangevinkte secties
  scenarioIndex: number;       // Welk scenario als basis
  geldverstrekker: string;
  productlijn: string;
  nhg: boolean;
  adviseur: string;
  dossierNummer: string;
}

export function buildAdviesrapportPayload(
  invoer: any,          // AankoopInvoer of AanpassenInvoer
  scenarios: any[],     // Scenario-array
  natResultaten: any[], // NAT API resultaten
  maandlastenResultaten: any[], // Maandlasten API resultaten
  options: AdviesrapportOptions
) {
  const klant = invoer.klantGegevens;
  const hasPartner = !klant.alleenstaand;
  const idx = options.scenarioIndex;
  const ber = invoer.haalbaarheidsBerekeningen?.[idx];
  const fin = invoer.berekeningen?.[idx];
  const scenario = scenarios?.[idx];
  const natRes = natResultaten?.[idx];
  const maandRes = maandlastenResultaten?.[idx];

  // Klantnaam samenstellen
  const aanvragerNaam = `${klant.voornaamAanvrager || ''} ${klant.achternaamAanvrager || ''}`.trim();
  const partnerNaam = hasPartner
    ? `${klant.voornaamPartner || ''} ${klant.achternaamPartner || ''}`.trim()
    : '';
  const customerName = hasPartner && partnerNaam
    ? `${aanvragerNaam} en ${partnerNaam}`
    : aanvragerNaam;

  const sections = [];

  // --- Samenvatting sectie ---
  if (options.selectedSections.includes('summary')) {
    const hypotheekBedrag = fin
      ? (fin.totaalInvestering || 0) - (fin.totaalEigenMiddelen || 0)
      : 0;

    sections.push({
      id: 'summary',
      title: 'Samenvatting advies',
      visible: true,
      narratives: [
        `U wilt een hypotheek afsluiten voor ${invoer.dossierType || 'aankoop bestaande woning'}.`,
        'Op basis van uw financiële situatie, uw wensen en de geldende leennormen hebben wij beoordeeld dat de geadviseerde financiering passend is binnen uw situatie.',
        ...(options.nhg ? ['De hypotheek wordt aangevraagd met Nationale Hypotheek Garantie.'] : []),
      ],
      highlights: [
        {
          label: 'Hypotheekbedrag',
          value: formatBedrag(hypotheekBedrag),
          note: `${options.geldverstrekker || ''} — ${options.productlijn || ''}`.trim().replace(/^—\s*$/, ''),
        },
        ...(maandRes ? [{
          label: 'Netto maandlast',
          value: formatBedrag(maandRes.net_monthly_cost || maandRes.nettoMaandlast || 0),
        }] : []),
      ],
      rows: [
        ...(maandRes ? [
          { label: 'Bruto maandlast', value: formatBedrag(maandRes.total_gross_monthly || maandRes.brutoMaandlast || 0) },
          { label: 'Netto maandlast', value: formatBedrag(maandRes.net_monthly_cost || maandRes.nettoMaandlast || 0), bold: true },
        ] : []),
        ...(fin ? [
          { label: 'Eigen inbreng', value: formatBedrag(fin.totaalEigenMiddelen || fin.eigenGeld || 0) },
        ] : []),
      ],
    });
  }

  // --- Klantprofiel sectie ---
  if (options.selectedSections.includes('client-profile')) {
    const rows = [
      { label: 'Aanvrager — Naam', value: aanvragerNaam },
      { label: 'Aanvrager — Geboortedatum', value: klant.geboortedatumAanvrager || '' },
    ];

    // Adres
    const adresAanvrager = [
      klant.straat || klant.straatAanvrager || '',
      klant.postcode || klant.postcodeAanvrager || '',
      klant.woonplaats || klant.woonplaatsAanvrager || '',
    ].filter(Boolean).join(', ');
    if (adresAanvrager) {
      rows.push({ label: 'Aanvrager — Adres', value: adresAanvrager });
    }
    if (klant.telefoonnummer || klant.telefoonAanvrager) {
      rows.push({ label: 'Aanvrager — Telefoon', value: klant.telefoonnummer || klant.telefoonAanvrager || '' });
    }
    if (klant.email || klant.emailAanvrager) {
      rows.push({ label: 'Aanvrager — E-mail', value: klant.email || klant.emailAanvrager || '' });
    }

    // Partner
    if (hasPartner) {
      rows.push({ label: '', value: '' }); // Separator
      rows.push({ label: 'Partner — Naam', value: partnerNaam });
      if (klant.geboortedatumPartner) {
        rows.push({ label: 'Partner — Geboortedatum', value: klant.geboortedatumPartner });
      }
    }

    // Inkomen
    if (ber?.inkomenGegevens) {
      rows.push({ label: '', value: '' }); // Separator
      rows.push({ label: 'Bruto jaarinkomen aanvrager', value: formatBedrag(ber.inkomenGegevens.hoofdinkomenAanvrager || 0) });
      if (hasPartner) {
        rows.push({ label: 'Bruto jaarinkomen partner', value: formatBedrag(ber.inkomenGegevens.hoofdinkomenPartner || 0) });
      }
      const totaalInkomen = (ber.inkomenGegevens.hoofdinkomenAanvrager || 0) + (ber.inkomenGegevens.hoofdinkomenPartner || 0);
      rows.push({ label: 'Totaal huishoudinkomen', value: formatBedrag(totaalInkomen), bold: true });
    }

    sections.push({
      id: 'client-profile',
      title: 'Klantprofiel',
      visible: true,
      narratives: hasPartner ? [] : ['Aanvraag zonder partner.'],
      rows,
    });
  }

  // --- Onderpand sectie ---
  if (options.selectedSections.includes('property')) {
    const wozWaarde = fin?.wozWaarde || ber?.onderpand?.wozWaarde || 0;
    const hypotheekBedrag = fin
      ? (fin.totaalInvestering || 0) - (fin.totaalEigenMiddelen || 0)
      : 0;
    const ltv = wozWaarde > 0 ? ((hypotheekBedrag / wozWaarde) * 100).toFixed(1) + '%' : '';

    const rows = [];
    // Adres onderpand als beschikbaar
    if (fin?.adresOnderpand) {
      rows.push({ label: 'Adres', value: fin.adresOnderpand });
    }
    rows.push({ label: 'Marktwaarde', value: formatBedrag(wozWaarde) });
    if (ber?.onderpand?.energielabel && ber.onderpand.energielabel !== 'geen_label') {
      rows.push({ label: 'Energielabel', value: ber.onderpand.energielabel });
    }
    if (ltv) {
      rows.push({ label: 'Loan-to-Value', value: ltv });
    }

    sections.push({
      id: 'property',
      title: 'Onderpand',
      visible: true,
      narratives: [],
      rows,
    });
  }

  // --- Betaalbaarheid sectie ---
  if (options.selectedSections.includes('affordability')) {
    const rows = [];
    if (natRes?.debug?.toets_inkomen) {
      rows.push({ label: 'Toetsinkomen', value: formatBedrag(natRes.debug.toets_inkomen) });
    }
    if (natRes?.scenario1?.annuitair?.max_box1) {
      rows.push({ label: 'Maximale hypotheek', value: formatBedrag(natRes.scenario1.annuitair.max_box1) });
    }
    const hypotheekBedrag = fin
      ? (fin.totaalInvestering || 0) - (fin.totaalEigenMiddelen || 0)
      : 0;
    if (hypotheekBedrag > 0) {
      rows.push({ label: 'Geadviseerd hypotheekbedrag', value: formatBedrag(hypotheekBedrag), bold: true });
    }
    if (maandRes) {
      rows.push({ label: 'Bruto maandlast', value: formatBedrag(maandRes.total_gross_monthly || maandRes.brutoMaandlast || 0) });
      if (maandRes.tax_breakdown?.net_tax_effect_monthly || maandRes.renteaftrek) {
        rows.push({ label: 'Fiscaal voordeel', value: formatBedrag(maandRes.tax_breakdown?.net_tax_effect_monthly || maandRes.renteaftrek || 0) });
      }
      rows.push({ label: 'Netto maandlast', value: formatBedrag(maandRes.net_monthly_cost || maandRes.nettoMaandlast || 0), bold: true });
    }

    sections.push({
      id: 'affordability',
      title: 'Betaalbaarheid',
      visible: true,
      narratives: [
        'De maximale hypotheek is beoordeeld op basis van de geldende leennormen, het toetsinkomen en uw financiële verplichtingen.',
        'De geadviseerde maandlasten zijn getoetst aan uw situatie en passen binnen de gehanteerde normen.',
      ],
      rows,
    });
  }

  // --- Financieringsopzet sectie ---
  if (options.selectedSections.includes('financing') && fin) {
    const rows = [];

    // Kosten
    if (fin.aankoopsom || fin.koopsomWoning) {
      rows.push({ label: 'Koopsom', value: formatBedrag(fin.aankoopsom || fin.koopsomWoning || 0) });
    }
    if (fin.overdrachtsbelasting || fin.kostenKoper) {
      rows.push({ label: 'Overdrachtsbelasting', value: formatBedrag(fin.overdrachtsbelasting || fin.kostenKoper || 0) });
    }
    if (fin.taxatiekosten) {
      rows.push({ label: 'Taxatiekosten', value: formatBedrag(fin.taxatiekosten) });
    }
    if (fin.adviesBemiddeling) {
      rows.push({ label: 'Advies- en bemiddelingskosten', value: formatBedrag(fin.adviesBemiddeling) });
    }
    if (fin.hypotheekakte) {
      rows.push({ label: 'Notariskosten', value: formatBedrag(fin.hypotheekakte) });
    }
    if (options.nhg && fin.nhgKosten) {
      rows.push({ label: 'NHG-borgtochtprovisie', value: formatBedrag(fin.nhgKosten) });
    }

    const totaalInvestering = fin.totaalInvestering || 0;
    rows.push({ label: 'Totale investering', value: formatBedrag(totaalInvestering), bold: true });
    rows.push({ label: '', value: '' }); // Separator

    // Eigen middelen
    if (fin.eigenGeld) {
      rows.push({ label: 'Eigen spaargeld', value: formatBedrag(fin.eigenGeld) });
    }
    if (fin.schenking) {
      rows.push({ label: 'Schenking', value: formatBedrag(fin.schenking) });
    }
    const totaalEigenMiddelen = fin.totaalEigenMiddelen || 0;
    if (totaalEigenMiddelen > 0) {
      rows.push({ label: 'Totaal eigen middelen', value: formatBedrag(totaalEigenMiddelen), bold: true });
      rows.push({ label: '', value: '' }); // Separator
    }

    const hypotheekBedrag = totaalInvestering - totaalEigenMiddelen;
    rows.push({ label: 'Benodigd hypotheekbedrag', value: formatBedrag(hypotheekBedrag), bold: true });

    sections.push({
      id: 'financing',
      title: 'Financieringsopzet',
      visible: true,
      narratives: [],
      rows,
    });
  }

  // --- Hypotheekonderdelen sectie ---
  if (options.selectedSections.includes('loan-parts') && scenario) {
    const leningdelen = scenario.leningdelen || scenario.hypotheekdelen || [];

    sections.push({
      id: 'loan-parts',
      title: 'Hypotheekonderdelen',
      visible: true,
      narratives: [],
      rows: [
        ...(options.geldverstrekker ? [{ label: 'Geldverstrekker', value: options.geldverstrekker }] : []),
        ...(options.productlijn ? [{ label: 'Productlijn', value: options.productlijn }] : []),
      ],
      tables: leningdelen.length > 0 ? [{
        headers: ['Leningdeel', 'Bedrag', 'Aflosvorm', 'Rente', 'RVP', 'Looptijd', 'Box'],
        rows: leningdelen.map((deel: any, i: number) => {
          const bedrag = (deel.bedragBox1 || deel.hoofdsomBox1 || 0) + (deel.bedragBox3 || deel.hoofdsomBox3 || 0);
          const looptijdMaanden = deel.looptijdOrigineel || deel.org_lpt || 360;
          const rvpMaanden = deel.rvp || 120;
          const box = (deel.bedragBox3 || deel.hoofdsomBox3 || 0) > 0 ? 'box 3' : 'box 1';

          return [
            `Deel ${i + 1}`,
            formatBedrag(bedrag),
            deel.aflossingsvorm || deel.aflos_type || 'Annuïteit',
            `${((deel.rentepercentage || deel.werkelijke_rente || 0) * (deel.rentepercentage && deel.rentepercentage < 1 ? 100 : 1)).toFixed(2).replace('.', ',')}%`,
            `${Math.round(rvpMaanden / 12)} jaar`,
            `${Math.round(looptijdMaanden / 12)} jaar`,
            box,
          ];
        }),
      }] : [],
    });
  }

  // --- Fiscale aspecten sectie ---
  if (options.selectedSections.includes('tax')) {
    sections.push({
      id: 'tax',
      title: 'Fiscale aspecten',
      visible: true,
      narratives: [
        'De leningdelen die kwalificeren als eigenwoningschuld vallen in box 1. De betaalde hypotheekrente kan fiscaal aftrekbaar zijn, voor zover aan de wettelijke voorwaarden wordt voldaan.',
      ],
      rows: [
        { label: 'Fiscale kwalificatie', value: 'Eigenwoningschuld (box 1)' },
      ],
    });
  }

  // --- Risico bij overlijden ---
  if (options.selectedSections.includes('risk-death')) {
    sections.push({
      id: 'risk-death',
      title: 'Risico bij overlijden',
      visible: true,
      narratives: hasPartner
        ? [
            'Bij overlijden van één van de partners kan het huishoudinkomen dalen. Dit kan gevolgen hebben voor de betaalbaarheid van de hypotheeklasten.',
            'Het is van belang dat de nabestaande de hypotheeklasten kan blijven dragen.',
          ]
        : [
            'Bij overlijden ontstaat geen financieel risico voor een partner, maar het blijft van belang dat eventuele nabestaanden of erfgenamen zich bewust zijn van de gevolgen voor de woningfinanciering.',
          ],
    });
  }

  // --- Risico bij arbeidsongeschiktheid ---
  if (options.selectedSections.includes('risk-disability')) {
    sections.push({
      id: 'risk-disability',
      title: 'Risico bij arbeidsongeschiktheid',
      visible: true,
      narratives: [
        'Wanneer u arbeidsongeschikt raakt, kan uw inkomen dalen. Hierdoor kan het lastiger worden om de hypotheeklasten te blijven betalen.',
        'In dit rapport is geen afzonderlijke productoplossing voor arbeidsongeschiktheid opgenomen. Het doel van dit onderdeel is bewustwording van dit risico.',
      ],
    });
  }

  // --- Risico bij werkloosheid ---
  if (options.selectedSections.includes('risk-unemployment')) {
    sections.push({
      id: 'risk-unemployment',
      title: 'Risico bij werkloosheid',
      visible: true,
      narratives: [
        'Bij werkloosheid kan uw inkomen tijdelijk lager zijn. Hierdoor kunnen de maandlasten moeilijker betaalbaar worden.',
        'Het is daarom belangrijk om voldoende financiële reserves aan te houden om een periode van inkomensdaling op te kunnen vangen.',
      ],
    });
  }

  // --- Pensionering ---
  if (options.selectedSections.includes('retirement')) {
    sections.push({
      id: 'retirement',
      title: 'Pensionering',
      visible: true,
      narratives: [
        'Wij hebben gekeken naar uw verwachte inkomenssituatie na pensionering op basis van de bij ons bekende pensioeninformatie.',
      ],
    });
  }

  // --- Aandachtspunten ---
  if (options.selectedSections.includes('attention-points')) {
    sections.push({
      id: 'attention-points',
      title: 'Aandachtspunten',
      visible: true,
      narratives: [
        'Na afloop van de rentevaste periode kan de rente wijzigen, waardoor de maandlasten kunnen stijgen of dalen.',
        'Veranderingen in uw persoonlijke of financiële situatie kunnen invloed hebben op de betaalbaarheid van de hypotheek.',
      ],
    });
  }

  // --- Disclaimer ---
  if (options.selectedSections.includes('disclaimer')) {
    sections.push({
      id: 'disclaimer',
      title: 'Disclaimer',
      visible: true,
      narratives: [
        'Dit adviesrapport is opgesteld op basis van de door u verstrekte informatie. Wij gaan ervan uit dat deze gegevens juist en volledig zijn.',
        'Het advies is een momentopname en gebaseerd op de huidige wet- en regelgeving en de op het moment van opstellen bekende uitgangspunten.',
        'De definitieve acceptatie van de hypotheek is afhankelijk van de beoordeling door de geldverstrekker.',
      ],
    });
  }

  return {
    meta: {
      title: 'Adviesrapport Hypotheek',
      date: new Date().toLocaleDateString('nl-NL', { day: '2-digit', month: '2-digit', year: 'numeric' }),
      dossierNumber: options.dossierNummer,
      advisor: options.adviseur,
      customerName,
      propertyAddress: '', // Kan later worden ingevuld
    },
    bedrijf: {
      naam: 'Hondsrug Finance',
      email: 'Info@hondsrugfinance.nl',
      telefoon: '+31 88 400 2700',
      kvk: 'KVK 93276699',
    },
    sections,
  };
}
```

**Let op:** De exacte veldnamen in de `invoer` (bijv. `aankoopsom` vs `koopsomWoning`, `eigenGeld` vs `spaargeld`) hangen af van de huidige types in de Lovable codebase. Pas de veldnamen aan zodat ze overeenkomen met de bestaande `AankoopInvoer` / `AanpassenInvoer` types. Gebruik de bestaande `formatBedrag` functie voor bedragnotatie.

---

## Stap 4: PDF download functie

Voeg de download-functie toe (kan in hetzelfde bestand of in `pdfDownload.ts`):

```typescript
import { API_BASE_URL, getApiHeaders } from '@/config/apiConfig';

export async function downloadAdviesrapportPdf(payload: any): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/adviesrapport-pdf`, {
    method: 'POST',
    headers: {
      ...getApiHeaders(),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`PDF generatie mislukt: ${response.status} — ${errorText}`);
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;

  // Bestandsnaam: "Adviesrapport - Klantnaam.pdf"
  const klantnaam = payload.meta?.customerName || 'Klant';
  a.download = `Adviesrapport - ${klantnaam}.pdf`;

  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
```

**API endpoint:** `POST https://nat-hypotheek-api.onrender.com/adviesrapport-pdf`

Dit endpoint is al beschikbaar, heeft geen API-key nodig, en retourneert `application/pdf` bytes.

---

## Stap 5: Component bouwen — AdviesrapportDialog

Maak een nieuw component `AdviesrapportDialog.tsx` (of vergelijkbare naam) dat de twee-stappen wizard bevat:

1. **Stap 1:** Aanvraag selecteren (lijst van aanvragen uit het dossier)
2. **Stap 2:** Secties en opties configureren + "Genereer rapport" knop

**Props:**

```typescript
interface AdviesrapportDialogProps {
  open: boolean;
  onClose: () => void;
  dossierId: string;
  dossierNummer: string;
  aanvragen: Aanvraag[];   // Lijst van aanvragen bij dit dossier
  userName: string;         // Naam van ingelogde gebruiker (voor adviseur-veld)
}
```

**Gedrag bij klikken op "Genereer rapport":**

1. Toon een loading state op de knop ("Rapport genereren..." met spinner)
2. Laad de volledige invoer-data van de geselecteerde aanvraag uit Supabase (als dit niet al geladen is)
3. Roep `buildAdviesrapportPayload()` aan met de invoer-data en de gekozen opties
4. Roep `downloadAdviesrapportPdf()` aan met de payload
5. Bij succes: toon een success-toast ("Adviesrapport gedownload") en sluit de modal
6. Bij fout: toon een error-toast met de foutmelding, houd de modal open

---

## Stap 6: Integratie op dossierpagina

Zoek het component dat de dossierpagina rendert (waar de "Adviezen" sectie met de "+ Nieuw advies" knop staat).

1. Importeer het `AdviesrapportDialog` component
2. Voeg state toe voor de dialog: `const [adviesDialogOpen, setAdviesDialogOpen] = useState(false);`
3. Koppel de "+ Nieuw advies" knop aan `setAdviesDialogOpen(true)`
4. Render het dialog component met de juiste props (dossierId, aanvragen-lijst, etc.)

**Let op:** De aanvragen-lijst is al beschikbaar op de dossierpagina (ze worden getoond in de "Aanvragen" sectie). Hergebruik dezelfde data-bron.

---

## Stap 7: Opgeslagen adviezen tonen (optioneel, maar aanbevolen)

Na het succesvol genereren van een adviesrapport, sla een record op in Supabase zodat het advies in de "Adviezen" lijst verschijnt:

```typescript
// Supabase tabel: adviezen (of advices)
{
  id: uuid,
  dossier_id: uuid,          // Link naar dossier
  aanvraag_id: uuid,         // Link naar bronaaanvraag
  naam: string,              // Bijv. "Adviesrapport - 8-3-2026"
  aangemaakt_op: timestamp,
  aangemaakt_door: string,   // Adviseur naam
  opties: jsonb,             // De gekozen opties (secties, scenario, etc.)
}
```

Dit maakt het mogelijk om:
- Eerder gegenereerde adviezen te zien in de lijst
- Een advies opnieuw te genereren met dezelfde instellingen
- Te zien wanneer en door wie een advies is gemaakt

**Als deze stap te veel werk is**, sla dit dan over en toon voorlopig alleen de melding "Nog geen adviezen" totdat een advies wordt gegenereerd. De PDF download werkt dan wel, maar er wordt geen historie bijgehouden.

---

## Verificatie

| # | Check | Verwacht resultaat |
|---|-------|--------------------|
| 1 | Klik "+ Nieuw advies" op dossierpagina | Modal opent met aanvraag-selectie |
| 2 | Geen aanvragen in dossier | Melding "Maak eerst een aanvraag aan" |
| 3 | Selecteer aanvraag → Volgende | Configuratiescherm verschijnt |
| 4 | Sectie-checkboxes werken | Aan/uit toggle, "Alles aan"/"Alles uit" werkt |
| 5 | Opties-velden invulbaar | Geldverstrekker, productlijn, adviseur, dossiernummer |
| 6 | Scenario-dropdown toont alle scenario's | Scenario-namen uit de aanvraag |
| 7 | Klik "Genereer rapport" | Loading spinner, PDF wordt gedownload |
| 8 | PDF openen | Professioneel rapport met correcte klantnaam, secties en data |
| 9 | Uitgeschakelde secties niet in PDF | Alleen aangevinkte secties verschijnen |
| 10 | Fout bij API-aanroep | Error-toast met foutmelding, modal blijft open |
| 11 | Terug-knop in stap 2 | Gaat terug naar aanvraag-selectie |
| 12 | Annuleren sluit modal | Geen download, modal gesloten |

---

## Samenvatting

| Onderdeel | Wijziging |
|-----------|-----------|
| **Nieuw:** `src/utils/adviesrapportBuilder.ts` | Data-mapping: aanvraag → API payload |
| **Nieuw:** `AdviesrapportDialog.tsx` component | Twee-stappen wizard (selectie + configuratie) |
| **Wijzig:** Dossierpagina component | "+ Nieuw advies" knop koppelen aan dialog |
| **Optioneel:** Supabase tabel `adviezen` | Historie van gegenereerde adviezen |
| **Hergebruik:** `pdfDownload.ts` patronen | Download-logica (fetch → blob → download) |
| **Hergebruik:** `formatBedrag` functie | Bedragnotatie in de payload |

**Risico:** Laag. Er worden geen bestaande functies gewijzigd — alleen nieuwe componenten toegevoegd en de "+ Nieuw advies" knop gekoppeld.

**API endpoint:** `POST https://nat-hypotheek-api.onrender.com/adviesrapport-pdf` — al beschikbaar en getest.
