# Lovable Prompt D1b: PDF Samenvatting — uitbreiding met klantgegevens, teksten en disclaimer

## Doel

De backend samenvatting-pdf API is uitgebreid met nieuwe velden. De frontend moet nu:
1. Klantgegevens en onderpand meesturen
2. Per dossiertype de juiste toelichtingsteksten meesturen
3. Een highlight-box met kernuitkomsten meesturen
4. Bedrijfsgegevens en disclaimer meesturen

Alle nieuwe velden zijn optioneel — de bestaande PDF functionaliteit blijft werken.

---

## Stap 1: Tekst-templates per dossiertype

Maak een nieuw bestand `src/utils/pdfTextTemplates.ts`:

```typescript
/**
 * Tekst-templates voor de samenvatting PDF, per dossiertype.
 * Alle tekst wordt door de frontend samengesteld en naar de API gestuurd.
 * De backend is een pure renderer — bevat geen inhoudelijke tekst.
 */

// Generieke teksten die voor alle typen gelijk zijn
const TOELICHTING_INTRO = 'Dit rapport geeft een samenvatting van de berekende hypotheekmogelijkheden op basis van de door u verstrekte gegevens en de geldende hypotheeknormen.';

const TOELICHTING_ONDERDELEN = 'Het rapport bevat drie onderdelen:';

const TOELICHTING_ONDERDELEN_DETAIL = '<ul style="margin: 0; padding-left: 20px;"><li><strong>Maximaal haalbare hypotheek</strong> — een indicatie van het maximale hypotheekbedrag op basis van inkomen en financiële verplichtingen.</li><li><strong>Financieringsopzet</strong> — een overzicht van de totale financieringsbehoefte en de opbouw van de hypotheek, inclusief kosten en eventuele eigen middelen.</li><li><strong>Maandlasten</strong> — een indicatie van de verwachte bruto en netto maandlasten.</li></ul>';

const TOELICHTING_DISCLAIMER = 'De berekeningen geven een eerste inzicht in de mogelijkheden. De uiteindelijke hypotheek is afhankelijk van acceptatie door een geldverstrekker, verificatie van gegevens en de actuele rentestand.';

const HAALBAARHEID_INTRO = 'De maximale hypotheek is berekend op basis van de geldende hypotheeknormen. Hierbij wordt gekeken naar onder andere het toetsinkomen, de toetsrente, financiële verplichtingen en, voor zover relevant, het energielabel van de woning.';

const FINANCIERING_INTRO = 'Onderstaand overzicht geeft inzicht in de totale financieringsbehoefte en de voorgestelde opbouw van de hypotheek.';

const FINANCIERING_KOSTEN = 'Hierin zijn de belangrijkste kosten, eventuele eigen middelen en het benodigde hypotheekbedrag opgenomen.';

const MAANDLASTEN_INTRO = 'Onderstaand overzicht geeft een indicatie van de verwachte maandlasten per scenario.';

const MAANDLASTEN_TOELICHTING = 'De bruto maandlast bestaat uit rente en eventuele aflossing. De netto maandlast is de bruto maandlast verminderd met het geschatte fiscale voordeel op basis van de huidige fiscale regels en geeft daarmee een indicatie van de maandelijkse woonlast.';

const DISCLAIMER_TEKSTEN = [
  'De berekende maximale hypotheek, financieringsopzet en maandlasten zijn indicaties op basis van de ingevoerde gegevens en de geldende hypotheeknormen.',
  'De uiteindelijke mogelijkheden kunnen afwijken door onder andere beoordeling door een geldverstrekker, wijzigingen in rente of voorwaarden, verificatie van inkomen en verplichtingen, taxatiewaarde van de woning en wijzigingen in fiscale regelgeving.',
  'Dit rapport vormt geen bindend aanbod en geen definitief financieel advies.',
];

// Geen type-specifieke teksten meer nodig — alle teksten zijn generiek

export type DossierType =
  | 'Aankoop bestaande bouw'
  | 'Aankoop nieuwbouw - project'
  | 'Aankoop nieuwbouw - eigen beheer'
  | 'Hypotheek verhogen'
  | 'Hypotheek oversluiten'
  | 'Partner uitkopen';

export function getToelichtingTeksten(): string[] {
  return [
    TOELICHTING_INTRO,
    TOELICHTING_ONDERDELEN,
    TOELICHTING_ONDERDELEN_DETAIL,
    TOELICHTING_DISCLAIMER,
  ];
}

export function getHaalbaarheidTeksten(): string[] {
  return [
    '<strong>Indicatieve maximale hypotheek</strong>',
    'Op basis van de huidige gegevens bedraagt de maximaal haalbare hypotheek:',
  ];
}

export function getHaalbaarheidNaTeksten(): string[] {
  return [HAALBAARHEID_INTRO];
}

export function getFinancieringTeksten(): string[] {
  return [FINANCIERING_INTRO, FINANCIERING_KOSTEN];
}

export function getMaandlastenTeksten(): string[] {
  return [MAANDLASTEN_INTRO, MAANDLASTEN_TOELICHTING];
}

export function getDisclaimerTeksten(): string[] {
  return DISCLAIMER_TEKSTEN;
}
```

---

## Stap 2: `downloadSamenvattingPdf` uitbreiden in `src/utils/pdfDownload.ts`

Importeer de nieuwe functies en breid de payload uit:

```typescript
import {
  DossierType,
  getToelichtingTeksten,
  getHaalbaarheidTeksten,
  getHaalbaarheidNaTeksten,
  getFinancieringTeksten,
  getMaandlastenTeksten,
  getDisclaimerTeksten,
} from './pdfTextTemplates';
```

### 2a. Klantgegevens samenstellen

Voeg een helper functie toe boven `downloadSamenvattingPdf`:

```typescript
function buildKlantGegevens(invoer: AankoopInvoer) {
  const kg = invoer.klantGegevens;
  const aanvrager = {
    naam: [kg.voornaamAanvrager, kg.achternaamAanvrager].filter(Boolean).join(' '),
    geboortedatum: kg.geboortedatumAanvrager
      ? new Date(kg.geboortedatumAanvrager).toLocaleDateString('nl-NL')
      : '',
    straat: kg.straatAanvrager || '',
    postcode: kg.postcodeAanvrager || '',
    woonplaats: kg.woonplaatsAanvrager || '',
    telefoon: kg.telefoonAanvrager || '',
    email: kg.emailAanvrager || '',
  };

  let partner = null;
  if (!kg.alleenstaand) {
    partner = {
      naam: [kg.voornaamPartner, kg.achternaamPartner].filter(Boolean).join(' '),
      geboortedatum: kg.geboortedatumPartner
        ? new Date(kg.geboortedatumPartner).toLocaleDateString('nl-NL')
        : '',
      straat: kg.straatPartner || '',
      postcode: kg.postcodePartner || '',
      woonplaats: kg.woonplaatsPartner || '',
      telefoon: kg.telefoonPartner || '',
      email: kg.emailPartner || '',
    };
  }

  return { aanvrager, partner };
}
```

### 2b. Onderpand samenstellen

```typescript
function buildOnderpand(invoer: AankoopInvoer) {
  // Pak onderpand-info uit de eerste haalbaarheidsberekening
  const eerste = invoer.haalbaarheidsBerekeningen?.[0];
  if (!eerste) return null;

  const energieLabelDisplay: Record<string, string> = {
    'geen_label': '', 'E_F_G': 'E, F of G', 'C_D': 'C of D',
    'A_B': 'A of B', 'A+_A++': 'A+ of A++', 'A+++': 'A+++',
    'A++++': 'A++++', 'A++++_garantie': 'A++++ met garantie',
  };

  return {
    adres: '', // Niet beschikbaar in huidige invoer
    woz_waarde: eerste.onderpand.wozWaarde > 0 ? formatBedrag(eerste.onderpand.wozWaarde) : '',
    woningtype: '', // Komt uit de berekening, niet uit haalbaarheid
    energielabel: energieLabelDisplay[eerste.onderpand.energielabel] || '',
    ebv_ebb_bedrag: eerste.onderpand.bedragEbvEbb > 0 ? formatBedrag(eerste.onderpand.bedragEbvEbb) : '',
  };
}
```

### 2c. Dossiertype bepalen

```typescript
function getDossierType(invoer: AankoopInvoer, wijzigingBerekeningen?: WijzigingBerekening[]): DossierType {
  // Als er wijziging-berekeningen zijn, bepaal type uit de eerste
  if (wijzigingBerekeningen && wijzigingBerekeningen.length > 0) {
    const type = wijzigingBerekeningen[0].aanpassingType;
    if (type === 'verhogen') return 'Hypotheek verhogen';
    if (type === 'oversluiten') return 'Hypotheek oversluiten';
    if (type === 'uitkopen') return 'Partner uitkopen';
  }

  // Anders: aankoop-type uit de eerste berekening
  if (invoer.berekeningen && invoer.berekeningen.length > 0) {
    const wt = invoer.berekeningen[0].woningType;
    if (wt === 'nieuwbouw_project') return 'Aankoop nieuwbouw - project';
    if (wt === 'nieuwbouw_eigen_beheer') return 'Aankoop nieuwbouw - eigen beheer';
    return 'Aankoop bestaande bouw';
  }

  return 'Aankoop bestaande bouw'; // fallback
}
```

### 2d. Maximaal haalbaar bedrag bepalen

```typescript
function getMaxHypotheekBedrag(natResultaten: (NatResultaat | null)[]): string {
  // Neem het hoogste maximale hypotheekbedrag over alle scenario's
  let max = 0;
  for (const r of natResultaten) {
    if (r) {
      max = Math.max(max, r.maxHypAnnuitairBox1 || 0, r.maxHypNietAnnuitairBox1 || 0);
    }
  }
  return max > 0 ? formatBedrag(max) : '';
}
```

### 2e. Payload samenstellen

Pas de `downloadSamenvattingPdf` functie aan. Vervang het bestaande `payload` object:

```typescript
export async function downloadSamenvattingPdf(
  invoer: AankoopInvoer,
  scenarios: Scenario[],
  maandlastenResultaten: MaandlastenResultaat[],
  natResultaten: (NatResultaat | null)[],
  apiRenteaftrek?: Record<string, number>,
  wijzigingBerekeningen?: WijzigingBerekening[],
) {
  // Klantnaam: bij partner met zelfde achternaam → "Harry en Harriëtte Slinger"
  // Bij verschillende achternamen → "Harry Slinger en Harriëtte de Vries"
  const kg = invoer.klantGegevens;
  let klantNaam: string;
  if (kg.alleenstaand) {
    klantNaam = [kg.voornaamAanvrager, kg.achternaamAanvrager].filter(Boolean).join(' ');
  } else if (kg.achternaamPartner && kg.achternaamPartner !== kg.achternaamAanvrager) {
    klantNaam = [
      [kg.voornaamAanvrager, kg.achternaamAanvrager].filter(Boolean).join(' '),
      'en',
      [kg.voornaamPartner, kg.achternaamPartner].filter(Boolean).join(' '),
    ].join(' ');
  } else {
    klantNaam = [
      kg.voornaamAanvrager,
      'en',
      kg.voornaamPartner,
      kg.achternaamAanvrager,
    ].filter(Boolean).join(' ');
  }

  const dossierType = getDossierType(invoer, wijzigingBerekeningen);
  const maxHypotheek = getMaxHypotheekBedrag(natResultaten);

  // Netto maandlast: neem het laatste scenario (typisch het "definitieve" scenario)
  const maandlastenData = buildMaandlastenData(scenarios, maandlastenResultaten, apiRenteaftrek);
  const laatsteNetto = maandlastenData.length > 0
    ? maandlastenData[maandlastenData.length - 1].netto
    : '';

  const payload = {
    // Bestaande velden
    klant_naam: klantNaam || '',
    datum: new Date().toLocaleDateString('nl-NL', { day: '2-digit', month: '2-digit', year: 'numeric' }),
    haalbaarheid: buildHaalbaarheidData(invoer, natResultaten),
    financiering: buildFinancieringData(invoer, wijzigingBerekeningen),
    maandlasten: maandlastenData,

    // Nieuwe velden
    dossier_type: dossierType,
    bedrijf: {
      naam: 'Hondsrug Finance',
      email: 'Info@hondsrugfinance.nl',
      telefoon: '+31 88 400 2700',
      kvk: 'KVK 93276699',
    },
    klant_gegevens: buildKlantGegevens(invoer),
    onderpand: buildOnderpand(invoer),
    toelichting: {
      paragrafen: getToelichtingTeksten(),
    },
    haalbaarheid_tekst: {
      paragrafen: [
        ...getHaalbaarheidTeksten(),
      ],
      highlight: maxHypotheek ? {
        label: 'Maximaal haalbaar',
        waarde: maxHypotheek,
        toelichting: 'Dit bedrag is berekend volgens de geldende hypotheeknormen en vormt een indicatie van de maximale leencapaciteit.',
      } : undefined,
    },
    financiering_tekst: {
      paragrafen: getFinancieringTeksten(),
    },
    maandlasten_tekst: {
      paragrafen: getMaandlastenTeksten(),
      highlight: laatsteNetto ? {
        label: 'Verwachte netto maandlast',
        waarde: laatsteNetto,
        toelichting: 'Deze maandlast vormt een indicatie van de uiteindelijke maandelijkse woonlast.',
      } : undefined,
    },
    disclaimer: getDisclaimerTeksten(),
  };

  // ... rest van de functie (fetch + download) blijft ongewijzigd
```

---

## Stap 3: Haalbaarheid intro-tekst NA de highlight box

De `getHaalbaarheidNaTeksten()` bevat de uitleg over toetsrente etc. Deze tekst komt ná de highlight box maar vóór de cards. Pas de `haalbaarheid_tekst` samenstelling aan als je deze tekst wilt tonen:

De teksten staan in `pdfTextTemplates.ts` en kunnen per type berekening worden aangepast door nieuwe entries toe te voegen aan `CONTEXT_TEKSTEN` of `SCENARIO_TEKSTEN`.

---

## Stap 4: Inkomensverificatie sterretjes en uitgangspunten

### 4a. Inkomens-verificatiestatus

Bij het klikken op "Stuur samenvatting" selecteert de gebruiker per inkomen een verificatiestatus:
- **Aanname** — het inkomen is een aanname
- **Berekend** — het inkomen is zo correct mogelijk berekend
- **Geverifieerd** — het inkomen is geverifieerd op basis van officiële documenten

Deze status wordt per persoon meegegeven (aanvrager + eventueel partner).

### 4b. Sterretjes logica

In de haalbaarheid-cards staat achter het label "Aanvrager" en "Partner" een `*` of `**`:

```typescript
// Bepaal sterretjes op basis van verificatiestatus
function getInkomenSterretjes(
  statusAanvrager: 'aanname' | 'berekend' | 'geverifieerd',
  statusPartner?: 'aanname' | 'berekend' | 'geverifieerd',
): { aanvragerSterretje: string; partnerSterretje: string } {
  const aanvragerSterretje = '*';

  // Partner krijgt * als status gelijk is aan aanvrager, anders **
  let partnerSterretje = '';
  if (statusPartner) {
    partnerSterretje = statusPartner === statusAanvrager ? '*' : '**';
  }

  return { aanvragerSterretje, partnerSterretje };
}
```

In `buildHaalbaarheidData` wordt het sterretje aan het label toegevoegd:

```typescript
// In de inkomen_items array:
inkomen_items: [
  { label: `Aanvrager${sterretjes.aanvragerSterretje}`, waarde: '€ 80.000', is_totaal: false },
  { label: `Partner${sterretjes.partnerSterretje}`, waarde: '€ 35.000', is_totaal: false },
  { label: 'Totaal inkomen', waarde: '€ 115.000', is_totaal: true },
],
```

### 4c. Voetnoten samenstellen

De voetnoten verschijnen onder alle haalbaarheid-cards. De tekst per status:

```typescript
const VOETNOOT_TEKSTEN: Record<string, string> = {
  aanname: 'Het inkomen is gebaseerd op een aanname en is niet geverifieerd aan de hand van documenten.',
  berekend: 'Het getoonde inkomen betreft een zo correct mogelijk berekend inkomen op basis van de beschikbare gegevens.',
  geverifieerd: 'Het inkomen is gebaseerd op geverifieerde gegevens aan de hand van officiële documenten.',
};

function buildHaalbaarheidVoetnoten(
  statusAanvrager: string,
  statusPartner?: string,
): string[] {
  const voetnoten: string[] = [];

  // Altijd * voetnoot voor aanvrager
  voetnoten.push(`* ${VOETNOOT_TEKSTEN[statusAanvrager]}`);

  // ** voetnoot alleen als partner een andere status heeft
  if (statusPartner && statusPartner !== statusAanvrager) {
    voetnoten.push(`** ${VOETNOOT_TEKSTEN[statusPartner]}`);
  }

  return voetnoten;
}
```

### 4d. Uitgangspunt in highlight boxes

De gebruiker selecteert bij "Stuur samenvatting" welk scenario het uitgangspunt is. Dit scenario wordt getoond in de groene highlight boxes.

```typescript
// Scenario-naam meegeven als uitgangspunt in de highlight box
const gekozenScenario = scenarios[gekozenScenarioIndex];

// In de payload:
haalbaarheid_tekst: {
  paragrafen: [...getHaalbaarheidTeksten()],
  highlight: maxHypotheek ? {
    label: 'Maximaal haalbaar',
    waarde: maxHypotheek,
    toelichting: 'Dit bedrag is berekend volgens de geldende hypotheeknormen en vormt een indicatie van de maximale leencapaciteit.',
    uitgangspunt: gekozenScenario.naam,  // bijv. "Toekomstige situatie"
  } : undefined,
},
maandlasten_tekst: {
  paragrafen: getMaandlastenTeksten(),
  highlight: laatsteNetto ? {
    label: 'Verwachte netto maandlast',
    waarde: laatsteNetto,
    toelichting: 'Deze maandlast vormt een indicatie van de uiteindelijke maandelijkse woonlast.',
    uitgangspunt: gekozenScenario.naam,
  } : undefined,
},

// Voetnoten meegeven
haalbaarheid_voetnoten: buildHaalbaarheidVoetnoten(statusAanvrager, statusPartner),
```

### 4e. Payload uitbreiding

De `downloadSamenvattingPdf` functie krijgt twee nieuwe parameters:

```typescript
export async function downloadSamenvattingPdf(
  invoer: AankoopInvoer,
  scenarios: Scenario[],
  maandlastenResultaten: MaandlastenResultaat[],
  natResultaten: (NatResultaat | null)[],
  apiRenteaftrek?: Record<string, number>,
  wijzigingBerekeningen?: WijzigingBerekening[],
  // Nieuw:
  inkomenStatus?: {
    aanvrager: 'aanname' | 'berekend' | 'geverifieerd';
    partner?: 'aanname' | 'berekend' | 'geverifieerd';
  },
  gekozenScenarioIndex?: number,  // index van het gekozen scenario (default: laatste)
) {
```

---

## Samenvatting nieuwe API velden

| Veld | Type | Beschrijving |
|------|------|-------------|
| `dossier_type` | string | "Aankoop bestaande bouw", "Partner uitkopen", etc. |
| `bedrijf` | object | `{ naam, email, telefoon, kvk }` |
| `klant_gegevens` | object | `{ aanvrager: { naam, geboortedatum, straat, postcode, woonplaats, telefoon, email }, partner: { naam, geboortedatum, straat, postcode, woonplaats, telefoon, email } \| null }` |
| `onderpand` | object | `{ adres, woz_waarde, woningtype, energielabel, ebv_ebb_bedrag }` |
| `toelichting` | object | `{ paragrafen: string[] }` — HTML toegestaan |
| `haalbaarheid_tekst` | object | `{ paragrafen: string[], highlight?: { label, waarde, toelichting, uitgangspunt? } }` |
| `financiering_tekst` | object | `{ paragrafen: string[] }` |
| `maandlasten_tekst` | object | `{ paragrafen: string[], highlight?: { label, waarde, toelichting, uitgangspunt? } }` |
| `haalbaarheid_voetnoten` | string[] | Voetnoten onder haalbaarheid-cards (`* ...`, `** ...`) |
| `disclaimer` | string[] | Lijst van disclaimer-paragrafen |

Alle velden zijn optioneel. Als een veld ontbreekt, wordt de bijbehorende sectie in de PDF overgeslagen.

---

## Belangrijk

- Alle tekst bevat HTML (`<strong>`, `<br>`, `<span>`) en wordt door de backend gerenderd met `| safe`
- De `bedrijf` gegevens worden getoond in de header van pagina 1 (logo + bedrijfsinfo rechts)
- Het `dossier_type` wordt niet in de PDF getoond, maar bepaalt welke teksten worden samengesteld
- De highlight boxes tonen de kernuitkomsten (maximale hypotheek en netto maandlast) prominent
- Scenario-namen (`haalbaarheid[].naam`, `financiering[].naam`, `maandlasten[].naam`) worden al correct doorgestuurd en direct als card-titel gebruikt
- De `uitgangspunt` in highlight boxes toont het gekozen scenario (bijv. "Toekomstige situatie")
- Inkomens-sterretjes (`*`/`**`) worden in het label van de inkomen_items meegegeven (bijv. `"Aanvrager*"`)
- Voetnoten (`haalbaarheid_voetnoten`) bevatten de verklaring van `*` en `**` en worden direct onder de haalbaarheid-cards getoond
