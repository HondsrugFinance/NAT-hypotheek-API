# Lovable Prompt G5: Adviesrapport completeren — ontbrekende secties + risicoscenario's

> Dit prompt bouwt voort op G4. Het voegt 6 ontbrekende onderdelen toe: (A) extra invoervelden in de dialog, (B) sectie "Huidige situatie", (C) risicoscenario's verplicht maken met volledige API-request, (D) scenario-checks in de samenvatting, (E) relatiebeëindiging-sectie, (F) afsluiting-sectie.

---

## Overzicht van wijzigingen

1. **Dialog uitbreiden** — inklapbaar accordion met risico-analyse gegevens (type dienstverband, AOW-inkomen, nabestaandenpensioen, AO-parameters)
2. **Sectie "Huidige situatie" bouwen** — persoonsgegevens, inkomen, vermogen, verplichtingen in subsections
3. **Risk-scenarios verplicht maken** — volledige API-request met 40+ velden
4. **Scenario-checks in samenvatting** — visuele status per risicoscenario
5. **Relatiebeëindiging-sectie** — per-persoon max hypotheek na scheiding (alleen bij stel)
6. **Afsluiting-sectie** — vervangt disclaimer, met handtekening-blok

---

## Deel A: Dialog uitbreiden met risico-invoervelden

### A1. Nieuwe accordion in de dialog

Voeg onder de bestaande risicobereidheid-dropdowns (rechterkolom) een **inklapbaar accordion** toe met de titel **"Risico-analyse gegevens"**. Dit accordion is standaard **ingeklapt**.

De velden in het accordion:

**Per persoon (aanvrager + partner):**

| Veld | Type | Standaard | Tonen |
|------|------|-----------|-------|
| Type dienstverband aanvrager | Select: `Loondienst`, `Onderneming`, `ROZ (overige werkzaamheden)` | `Loondienst` | Altijd |
| Inkomen na AOW aanvrager | Getalveld (€ per jaar) | 0 | Altijd |
| Type dienstverband partner | Select: zelfde opties | `Loondienst` | Alleen bij stel |
| Inkomen na AOW partner | Getalveld (€ per jaar) | 0 | Alleen bij stel |

**Overlijden (alleen bij stel):**

| Veld | Type | Standaard | Tonen |
|------|------|-----------|-------|
| Nabestaandenpensioen bij overlijden aanvrager | Getalveld (€ per jaar) | 0 | Alleen bij stel |
| Nabestaandenpensioen bij overlijden partner | Getalveld (€ per jaar) | 0 | Alleen bij stel |
| Kind(eren) onder 18 jaar | Checkbox | Nee | Alleen bij stel |

**Arbeidsongeschiktheid:**

| Veld | Type | Standaard | Tonen |
|------|------|-----------|-------|
| AO-percentage | Select: `35`, `45`, `50`, `65`, `80`, `100` | `50` | Altijd |
| Benutting verdiencapaciteit (%) | Select: `0`, `25`, `50`, `75`, `100` | `50` | Altijd |

### A2. AdviesrapportOptions type uitbreiden

Voeg de nieuwe velden toe aan het bestaande `AdviesrapportOptions` interface (of het state-object dat de dialog opties beheert):

```typescript
// BESTAANDE velden (uit G4) — niet wijzigen:
// adviseur, datum, dossierNummer
// ervaringHypotheek, kennisHypotheekvormen, kennisFiscaleRegels, klantPrioriteit
// risicobereidheid: { pensioen, arbeidsongeschiktheid, werkloosheid, ... }

// NIEUWE velden toevoegen:
typeDienstverbandAanvrager: string;          // default: 'Loondienst'
typeDienstverbandPartner: string;            // default: 'Loondienst'
inkomenAanvragerAow: number;                 // default: 0
inkomenPartnerAow: number;                   // default: 0
nabestaandenpensioenAanvrager: number;       // default: 0
nabestaandenpensioenPartner: number;         // default: 0
heeftKindOnder18: boolean;                   // default: false
aoPercentage: number;                        // default: 50
benuttingRvc: number;                        // default: 50
```

### A3. Bepalen of er een partner is

Gebruik dezelfde logica als in G4 om te bepalen of het een stel betreft:

```typescript
const hasPartner = !!(
  klant?.naamPartner ||
  klant?.voornaamPartner ||
  klant?.achternaamPartner ||
  klant?.geboortedatumPartner
);
```

Toon de partner-specifieke velden (type dienstverband partner, inkomen partner AOW, nabestaandenpensioen, kind onder 18) alleen als `hasPartner === true`.

---

## Deel B: Sectie "Huidige situatie" toevoegen

### B1. Positie in de sectie-lijst

Voeg de sectie `current-situation` toe **na** `client-profile` en **vóór** `affordability` in de `sections[]` array.

### B2. Structuur

De sectie gebruikt `subsections[]`. Elke subsection kan `rows`, `columns`, `tables` en `list_items` bevatten. Bouw de subsections als volgt:

```typescript
// === Huidige situatie ===

const currentSitSubsections: any[] = [];

// ── B2a. Persoonsgegevens ──
if (hasPartner) {
  // Twee-koloms layout
  currentSitSubsections.push({
    subtitle: 'Persoonsgegevens',
    columns: [
      {
        title: aanvragerNaam,
        rows: [
          { label: 'Naam', value: aanvragerNaam },
          { label: 'Geboortedatum', value: klant.geboortedatumAanvrager || '' },
          ...(klant.adres || klant.straat ? [{
            label: 'Adres',
            value: klant.adres || klant.straat || ''
          }] : []),
          ...(klant.postcode || klant.woonplaats ? [{
            label: 'Postcode en plaats',
            value: `${klant.postcode || ''} ${klant.woonplaats || ''}`.trim()
          }] : []),
          ...(klant.telefoonnummer || klant.telefoonAanvrager ? [{
            label: 'Telefoon',
            value: klant.telefoonnummer || klant.telefoonAanvrager || ''
          }] : []),
          ...(klant.email || klant.emailAanvrager ? [{
            label: 'E-mail',
            value: klant.email || klant.emailAanvrager || ''
          }] : []),
        ],
      },
      {
        title: partnerNaam,
        rows: [
          { label: 'Naam', value: partnerNaam },
          { label: 'Geboortedatum', value: klant.geboortedatumPartner || '' },
          ...(klant.adresPartner || klant.adres || klant.straat ? [{
            label: 'Adres',
            value: klant.adresPartner || klant.adres || klant.straat || ''
          }] : []),
          ...(klant.postcodePartner || klant.postcode || klant.woonplaats ? [{
            label: 'Postcode en plaats',
            value: `${klant.postcodePartner || klant.postcode || ''} ${klant.woonplaatsPartner || klant.woonplaats || ''}`.trim()
          }] : []),
          ...(klant.telefoonPartner ? [{
            label: 'Telefoon',
            value: klant.telefoonPartner
          }] : []),
          ...(klant.emailPartner ? [{
            label: 'E-mail',
            value: klant.emailPartner
          }] : []),
        ],
      },
    ],
  });
} else {
  // Enkele kolom
  currentSitSubsections.push({
    subtitle: 'Persoonsgegevens',
    rows: [
      { label: 'Naam', value: aanvragerNaam },
      { label: 'Geboortedatum', value: klant.geboortedatumAanvrager || '' },
      ...(klant.adres || klant.straat ? [{
        label: 'Adres', value: klant.adres || klant.straat || ''
      }] : []),
      ...(klant.postcode || klant.woonplaats ? [{
        label: 'Postcode en plaats',
        value: `${klant.postcode || ''} ${klant.woonplaats || ''}`.trim()
      }] : []),
      ...(klant.telefoonnummer ? [{
        label: 'Telefoon', value: klant.telefoonnummer
      }] : []),
      ...(klant.email ? [{
        label: 'E-mail', value: klant.email
      }] : []),
    ],
  });
}

// ── B2b. Gezinssituatie ──
const gezinRows: any[] = [
  { label: 'Burgerlijke staat',
    value: klant.burgerlijkeStaat || (hasPartner ? 'Samenwonend' : 'Alleenstaand') },
];
currentSitSubsections.push({ subtitle: 'Gezinssituatie', rows: gezinRows });

// ── B2c. Inkomen ──
const ink = ber?.inkomenGegevens;
if (ink) {
  const buildIncomeTable = (
    hoofdinkomen: number,
    typeDienstverband: string,
    overig: { lijfrente?: number; huur?: number; alimentatie?: number; vermogen?: number }
  ) => {
    const rows: string[][] = [];
    if (hoofdinkomen > 0) {
      rows.push([typeDienstverband, formatBedrag(hoofdinkomen)]);
    }
    if (overig.lijfrente && overig.lijfrente > 0) {
      rows.push(['Lijfrente', formatBedrag(overig.lijfrente)]);
    }
    if (overig.alimentatie && overig.alimentatie > 0) {
      rows.push(['Partneralimentatie', formatBedrag(overig.alimentatie)]);
    }
    if (overig.huur && overig.huur > 0) {
      rows.push(['Huurinkomsten', formatBedrag(overig.huur)]);
    }
    if (overig.vermogen && overig.vermogen > 0) {
      rows.push(['Inkomsten uit vermogen', formatBedrag(overig.vermogen)]);
    }
    const totaal = (hoofdinkomen || 0)
      + (overig.lijfrente || 0)
      + (overig.alimentatie || 0)
      + (overig.huur || 0)
      + (overig.vermogen || 0);
    return {
      headers: ['Type', 'Bedrag'],
      rows,
      totals: ['Totaal', formatBedrag(totaal)],
    };
  };

  if (hasPartner) {
    currentSitSubsections.push({
      subtitle: 'Inkomen',
      columns: [
        {
          title: aanvragerNaam,
          tables: [buildIncomeTable(
            ink.hoofdinkomenAanvrager || 0,
            options.typeDienstverbandAanvrager,
            {
              lijfrente: ink.lijfrenteAanvrager,
              alimentatie: ink.partneralimentatieOntvangenAanvrager,
              huur: ink.huurinkomstenAanvrager || ink.huurinkomsten,
              vermogen: ink.inkomstenUitVermogenAanvrager || ink.inkomstenUitVermogen,
            }
          )],
        },
        {
          title: partnerNaam,
          tables: [buildIncomeTable(
            ink.hoofdinkomenPartner || 0,
            options.typeDienstverbandPartner,
            {
              lijfrente: ink.lijfrentePartner,
              alimentatie: ink.partneralimentatieOntvangenPartner,
              huur: ink.huurinkomstenPartner,
              vermogen: ink.inkomstenUitVermogenPartner,
            }
          )],
        },
      ],
    });
  } else {
    currentSitSubsections.push({
      subtitle: 'Inkomen',
      tables: [buildIncomeTable(
        ink.hoofdinkomenAanvrager || 0,
        options.typeDienstverbandAanvrager,
        {
          lijfrente: ink.lijfrenteAanvrager,
          alimentatie: ink.partneralimentatieOntvangenAanvrager,
          huur: ink.huurinkomsten,
          vermogen: ink.inkomstenUitVermogen,
        }
      )],
    });
  }
}

// ── B2d. Inkomen na AOW ──
if (options.inkomenAanvragerAow > 0 || options.inkomenPartnerAow > 0) {
  if (hasPartner) {
    currentSitSubsections.push({
      subtitle: 'Inkomen na AOW',
      columns: [
        {
          title: aanvragerNaam,
          tables: [{
            headers: ['Type', 'Bedrag'],
            rows: [['Inkomen na AOW', formatBedrag(options.inkomenAanvragerAow)]],
            totals: ['Totaal', formatBedrag(options.inkomenAanvragerAow)],
          }],
        },
        {
          title: partnerNaam,
          tables: [{
            headers: ['Type', 'Bedrag'],
            rows: [['Inkomen na AOW', formatBedrag(options.inkomenPartnerAow)]],
            totals: ['Totaal', formatBedrag(options.inkomenPartnerAow)],
          }],
        },
      ],
    });
  } else {
    currentSitSubsections.push({
      subtitle: 'Inkomen na AOW',
      tables: [{
        headers: ['Type', 'Bedrag'],
        rows: [['Inkomen na AOW', formatBedrag(options.inkomenAanvragerAow)]],
        totals: ['Totaal', formatBedrag(options.inkomenAanvragerAow)],
      }],
    });
  }
}

// ── B2e. Vermogen ──
const vermogenRows: any[] = [];
if ((fin?.eigenGeld || 0) > 0) {
  vermogenRows.push({ label: 'Spaargeld', value: formatBedrag(fin.eigenGeld) });
}
if ((fin?.schenking || 0) > 0) {
  vermogenRows.push({ label: 'Schenking', value: formatBedrag(fin.schenking) });
}
if ((fin?.verkoop || 0) > 0) {
  vermogenRows.push({ label: 'Verkoopopbrengst', value: formatBedrag(fin.verkoop) });
}
if (vermogenRows.length > 0) {
  const totaalVermogen = (fin?.eigenGeld || 0) + (fin?.schenking || 0) + (fin?.verkoop || 0);
  vermogenRows.push({ label: 'Totaal', value: formatBedrag(totaalVermogen), bold: true });
  currentSitSubsections.push({ subtitle: 'Vermogen', rows: vermogenRows });
}

// ── B2f. Verplichtingen ──
const verplRows: any[] = [];
const verpl = ber?.verplichtingen;
if ((verpl?.limietenBkr || 0) > 0) {
  verplRows.push({
    label: `Doorlopend krediet (limiet ${formatBedrag(verpl.limietenBkr)})`,
    value: '',
  });
}
if ((verpl?.studielening || 0) > 0) {
  verplRows.push({ label: 'Studielening', value: `${formatBedrag(verpl.studielening)} p/m` });
}
if ((verpl?.erfpacht || 0) > 0) {
  verplRows.push({ label: 'Erfpacht', value: `${formatBedrag(verpl.erfpacht)} p/m` });
}
if ((verpl?.overigeKredieten || 0) > 0) {
  verplRows.push({ label: 'Overige kredieten', value: `${formatBedrag(verpl.overigeKredieten)} p/m` });
}
if (verplRows.length > 0) {
  currentSitSubsections.push({ subtitle: 'Verplichtingen', rows: verplRows });
}

// ── Sectie toevoegen ──
sections.push({
  id: 'current-situation',
  title: 'Huidige situatie',
  visible: currentSitSubsections.length > 0,
  subsections: currentSitSubsections,
});
```

**Positie:** Voeg deze sectie in de `sections[]` array toe **direct na** de `client-profile` sectie en **vóór** de `affordability` sectie.

---

## Deel C: Risk-scenarios verplicht maken + volledige request

### C1. Risk-scenarios is niet meer optioneel

In G4 was Deel D gemarkeerd als "optioneel". **Verwijder die optionaliteit.** De risk-scenarios API moet **altijd** worden aangeroepen als onderdeel van de rapportgeneratie-flow. Wrap het in een try/catch zodat het rapport nog steeds gegenereerd wordt als de API faalt.

### C2. Inkomens-helper functie

Voeg deze helper-functie toe. Het routeert het hoofdinkomen naar het juiste veld (loondienst, onderneming, of ROZ) op basis van het type dienstverband uit de dialog:

```typescript
function mapInkomenVerdeling(
  hoofdinkomen: number,
  typeDienstverband: string,
  overigInkomen: {
    lijfrente?: number;
    huur?: number;
    alimentatie?: number;
    vermogen?: number;
  }
) {
  const overig =
    (overigInkomen.lijfrente || 0) +
    (overigInkomen.huur || 0) +
    (overigInkomen.alimentatie || 0) +
    (overigInkomen.vermogen || 0);

  return {
    loondienst: typeDienstverband === 'Loondienst' ? hoofdinkomen : 0,
    onderneming: typeDienstverband === 'Onderneming' ? hoofdinkomen : 0,
    roz: typeDienstverband.startsWith('ROZ') ? hoofdinkomen : 0,
    overig,
  };
}
```

### C3. Leeftijd-helper

Voeg een leeftijd-helper toe voor het schatten van arbeidsverleden:

```typescript
function berekenLeeftijd(geboortedatum: string): number {
  if (!geboortedatum) return 35;
  // geboortedatum is DD-MM-YYYY of YYYY-MM-DD
  let date: Date;
  if (geboortedatum.includes('-') && geboortedatum.indexOf('-') === 2) {
    // DD-MM-YYYY
    const [d, m, y] = geboortedatum.split('-');
    date = new Date(Number(y), Number(m) - 1, Number(d));
  } else {
    date = new Date(geboortedatum);
  }
  const today = new Date();
  let age = today.getFullYear() - date.getFullYear();
  const monthDiff = today.getMonth() - date.getMonth();
  if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < date.getDate())) {
    age--;
  }
  return age;
}
```

### C4. Volledige risk-scenarios request

**Vervang** de bestaande risk-scenarios request (uit G4 Deel D1) met deze uitgebreide versie. Alle nieuwe velden komen uit de dialog-opties (Deel A) en de bestaande wizard data:

```typescript
// Bouw inkomensverdeling per persoon
const inkomenAanvrager = mapInkomenVerdeling(
  ink?.hoofdinkomenAanvrager || 0,
  options.typeDienstverbandAanvrager,
  {
    lijfrente: ink?.lijfrenteAanvrager,
    huur: ink?.huurinkomstenAanvrager || ink?.huurinkomsten,
    alimentatie: ink?.partneralimentatieOntvangenAanvrager,
    vermogen: ink?.inkomstenUitVermogenAanvrager || ink?.inkomstenUitVermogen,
  }
);

const inkomenPartner = hasPartner
  ? mapInkomenVerdeling(
      ink?.hoofdinkomenPartner || 0,
      options.typeDienstverbandPartner,
      {
        lijfrente: ink?.lijfrentePartner,
        huur: ink?.huurinkomstenPartner,
        alimentatie: ink?.partneralimentatieOntvangenPartner,
        vermogen: ink?.inkomstenUitVermogenPartner,
      }
    )
  : { loondienst: 0, onderneming: 0, roz: 0, overig: 0 };

// Totaal inkomen per persoon (voor risk-scenarios huidig inkomen)
const totalInkomenAanvrager =
  (ink?.hoofdinkomenAanvrager || 0) +
  (ink?.lijfrenteAanvrager || 0) +
  (ink?.huurinkomstenAanvrager || ink?.huurinkomsten || 0) +
  (ink?.partneralimentatieOntvangenAanvrager || 0) +
  (ink?.inkomstenUitVermogenAanvrager || ink?.inkomstenUitVermogen || 0);

const totalInkomenPartner = hasPartner
  ? (ink?.hoofdinkomenPartner || 0) +
    (ink?.lijfrentePartner || 0) +
    (ink?.huurinkomstenPartner || 0) +
    (ink?.partneralimentatieOntvangenPartner || 0) +
    (ink?.inkomstenUitVermogenPartner || 0)
  : 0;

const leeftijdAanvrager = berekenLeeftijd(klant.geboortedatumAanvrager);
const leeftijdPartner = hasPartner ? berekenLeeftijd(klant.geboortedatumPartner) : 0;

const riskScenariosRequest = {
  // Hypotheekdelen (zelfde mapping als G4)
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

  // Persoons- en inkomengegevens
  ingangsdatum_hypotheek: new Date().toISOString().split('T')[0],
  geboortedatum_aanvrager: klant.geboortedatumAanvrager,
  inkomen_aanvrager_huidig: totalInkomenAanvrager,
  inkomen_aanvrager_aow: options.inkomenAanvragerAow || 0,
  alleenstaande: hasPartner ? 'NEE' : 'JA',
  geboortedatum_partner: hasPartner ? klant.geboortedatumPartner : undefined,
  inkomen_partner_huidig: totalInkomenPartner,
  inkomen_partner_aow: options.inkomenPartnerAow || 0,

  // Overlijden
  nabestaandenpensioen_bij_overlijden_aanvrager: options.nabestaandenpensioenAanvrager || 0,
  nabestaandenpensioen_bij_overlijden_partner: options.nabestaandenpensioenPartner || 0,
  heeft_kind_onder_18: options.heeftKindOnder18 || false,

  // Inkomensverdeling per persoon (NIEUW — nodig voor AO/WW berekeningen)
  inkomen_loondienst_aanvrager: inkomenAanvrager.loondienst,
  inkomen_onderneming_aanvrager: inkomenAanvrager.onderneming,
  inkomen_roz_aanvrager: inkomenAanvrager.roz,
  inkomen_overig_aanvrager: inkomenAanvrager.overig,
  inkomen_loondienst_partner: inkomenPartner.loondienst,
  inkomen_onderneming_partner: inkomenPartner.onderneming,
  inkomen_roz_partner: inkomenPartner.roz,
  inkomen_overig_partner: inkomenPartner.overig,

  // AO parameters (NIEUW)
  ao_percentage: options.aoPercentage || 50,
  benutting_rvc_percentage: options.benuttingRvc || 50,

  // Arbeidsverleden (geschat vanuit leeftijd)
  arbeidsverleden_jaren_totaal_aanvrager: Math.max(0, leeftijdAanvrager - 18),
  arbeidsverleden_jaren_totaal_partner: hasPartner ? Math.max(0, leeftijdPartner - 18) : 0,

  // Uit NAT resultaat
  toetsrente: natRes?.debug?.toets_rente || 0.05,
  geadviseerd_hypotheekbedrag: hypotheekBedrag,

  // Uit haalbaarheid
  energielabel: ber?.onderpand?.energielabel || 'Geen (geldig) Label',
  verduurzamings_maatregelen: ber?.onderpand?.ebvEbb || 0,
  limieten_bkr_geregistreerd: ber?.verplichtingen?.limietenBkr || 0,
  studievoorschot_studielening: ber?.verplichtingen?.studielening || 0,
  erfpachtcanon_per_jaar: ber?.verplichtingen?.erfpacht || 0,
  jaarlast_overige_kredieten: ber?.verplichtingen?.overigeKredieten || 0,
};
```

### C5. API-call met try/catch

Vervang de bestaande risk-scenarios call met deze versie die altijd wordt uitgevoerd:

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
  } else {
    console.warn('Risk-scenarios API fout:', riskResponse.status);
  }
} catch (error) {
  console.warn('Risk-scenarios API niet bereikbaar:', error);
}
```

### C6. Risk-secties bouwen (bestaande G4 code behouden)

De code uit G4 Deel D2 (pensioen, overlijden, AO, WW secties) blijft ongewijzigd. Maar **wrap het in een `if (riskData)`** check:

```typescript
if (riskData?.scenarios) {
  const aowScenarios = riskData.scenarios.filter((s: any) => s.categorie === 'aow');
  const overlijdenScenarios = riskData.scenarios.filter((s: any) => s.categorie === 'overlijden');
  const aoScenarios = riskData.scenarios.filter((s: any) => s.categorie === 'ao');
  const wwScenarios = riskData.scenarios.filter((s: any) => s.categorie === 'werkloosheid');

  // Pensioen-sectie (G4 code — ongewijzigd)
  if (aowScenarios.length > 0) {
    // ... bestaande G4 code voor retirement sectie ...
  }

  // Overlijden-sectie (G4 code — ongewijzigd)
  if (overlijdenScenarios.length > 0) {
    // ... bestaande G4 code voor risk-death sectie ...
  }

  // AO-sectie (G4 code — ongewijzigd)
  if (aoScenarios.length > 0) {
    // ... bestaande G4 code voor risk-disability sectie ...
  }

  // WW-sectie (G4 code — ongewijzigd)
  if (wwScenarios.length > 0) {
    // ... bestaande G4 code voor risk-unemployment sectie ...
  }
}
```

---

## Deel D: Scenario-checks in samenvatting

### D1. Scenario-checks afleiden van risk-scenarios response

Na het aanroepen van de risk-scenarios API en het bouwen van de risk-secties, bouw je de `scenario_checks` array af te leiden van de resultaten:

```typescript
const scenarioChecks: Array<{ label: string; status: string }> = [];

if (riskData?.scenarios) {
  // Pensionering
  const aowScenarios = riskData.scenarios.filter((s: any) => s.categorie === 'aow');
  if (aowScenarios.length > 0) {
    const worstAow = Math.min(...aowScenarios.map((s: any) => s.max_hypotheek_annuitair));
    scenarioChecks.push({
      label: 'Pensionering',
      status: worstAow >= hypotheekBedrag ? 'ok' : 'warning',
    });
  }

  // Overlijden (alleen bij stel)
  const overlijdenScenarios = riskData.scenarios.filter((s: any) => s.categorie === 'overlijden');
  if (overlijdenScenarios.length > 0) {
    scenarioChecks.push({
      label: 'Overlijden',
      status: overlijdenScenarios.some((s: any) => s.tekort > 0) ? 'warning' : 'ok',
    });
  }

  // Arbeidsongeschiktheid
  const aoScenarios = riskData.scenarios.filter((s: any) => s.categorie === 'ao');
  if (aoScenarios.length > 0) {
    scenarioChecks.push({
      label: 'Arbeidsongeschiktheid',
      status: aoScenarios.some((s: any) => s.tekort > 0) ? 'warning' : 'ok',
    });
  }

  // Werkloosheid
  const wwScenarios = riskData.scenarios.filter((s: any) => s.categorie === 'werkloosheid');
  if (wwScenarios.length > 0) {
    scenarioChecks.push({
      label: 'Werkloosheid',
      status: wwScenarios.some((s: any) => s.tekort > 0) ? 'warning' : 'ok',
    });
  }
}
```

### D2. Toevoegen aan summary sectie

Voeg `scenario_checks` toe aan de bestaande summary sectie (uit G4). Zoek de plek waar de summary sectie wordt opgebouwd en voeg het veld toe:

```typescript
// In de summary sectie (uit G4 Deel C4), voeg toe:
sections[0].scenario_checks = scenarioChecks;
// OF bij het bouwen van de summary sectie:
{
  id: 'summary',
  title: 'Samenvatting advies',
  visible: true,
  narratives: [...],       // bestaand uit G4
  highlights: [...],       // bestaand uit G4
  advice_text: [...],      // bestaand uit G4
  mortgage_summary: [...], // bestaand uit G4
  scenario_checks: scenarioChecks,  // NIEUW
}
```

**Let op:** De `scenario_checks` worden pas berekend ná de risk-scenarios API-call. Bouw dus eerst de risk-scenarios, bereken de checks, en voeg ze dan toe aan de summary. Dit kan betekenen dat je de summary sectie eerst als variabele opbouwt en pas later aan `sections[]` toevoegt, of dat je de sectie achteraf muteert.

---

## Deel E: Relatiebeëindiging-sectie (alleen bij stel)

### E1. Twee extra NAT-berekeningen

Bij een stel moeten we berekenen wat de maximale hypotheek per persoon apart is. Dit doe je met 2 extra `POST /calculate` calls:

```typescript
if (hasPartner) {
  let maxHypotheekAanvragerAlleen = 0;
  let maxHypotheekPartnerAlleen = 0;

  try {
    // Aanvrager alleen
    const natAanvragerAlleen = await fetch(
      'https://nat-hypotheek-api.onrender.com/calculate',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          hoofd_inkomen_aanvrager: ink?.hoofdinkomenAanvrager || 0,
          hoofd_inkomen_partner: 0,
          alleenstaande: 'JA',
          ontvangt_aow: 'NEE',
          energielabel: ber?.onderpand?.energielabel || 'Geen (geldig) Label',
          verduurzamings_maatregelen: ber?.onderpand?.ebvEbb || 0,
          limieten_bkr_geregistreerd: ber?.verplichtingen?.limietenBkr || 0,
          studievoorschot_studielening: ber?.verplichtingen?.studielening || 0,
          erfpachtcanon_per_jaar: ber?.verplichtingen?.erfpacht || 0,
          jaarlast_overige_kredieten: ber?.verplichtingen?.overigeKredieten || 0,
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
        }),
      }
    );
    const resAanvrager = await natAanvragerAlleen.json();
    maxHypotheekAanvragerAlleen = resAanvrager?.scenario1?.annuitair?.max_box1 || 0;

    // Partner alleen
    const natPartnerAlleen = await fetch(
      'https://nat-hypotheek-api.onrender.com/calculate',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          hoofd_inkomen_aanvrager: ink?.hoofdinkomenPartner || 0,
          hoofd_inkomen_partner: 0,
          alleenstaande: 'JA',
          ontvangt_aow: 'NEE',
          energielabel: ber?.onderpand?.energielabel || 'Geen (geldig) Label',
          verduurzamings_maatregelen: ber?.onderpand?.ebvEbb || 0,
          limieten_bkr_geregistreerd: 0,
          studievoorschot_studielening: 0,
          erfpachtcanon_per_jaar: 0,
          jaarlast_overige_kredieten: 0,
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
        }),
      }
    );
    const resPartner = await natPartnerAlleen.json();
    maxHypotheekPartnerAlleen = resPartner?.scenario1?.annuitair?.max_box1 || 0;
  } catch (error) {
    console.warn('Relatiebeëindiging berekening mislukt:', error);
  }
```

### E2. Sectie bouwen

```typescript
  // Maximale hypotheek uit de huidige (gezamenlijke) berekening
  const maxHypotheekHuidig = natRes?.scenario1?.annuitair?.max_box1 || hypotheekBedrag;

  if (maxHypotheekAanvragerAlleen > 0 || maxHypotheekPartnerAlleen > 0) {
    sections.push({
      id: 'risk-relationship',
      title: 'Relatiebeëindiging',
      visible: true,
      narratives: [
        'Bij relatiebeëindiging valt het inkomen van de partner weg. '
        + 'Er is geen recht op nabestaandenpensioen.',
      ],
      columns: [
        {
          title: `${aanvragerNaam} alleen`,
          rows: [
            { label: 'Resterend inkomen', value: formatBedrag(totalInkomenAanvrager), bold: true },
            { label: `Inkomen ${aanvragerNaam}`, value: formatBedrag(totalInkomenAanvrager), sub: true },
            { label: 'Maximale hypotheek', value: formatBedrag(maxHypotheekAanvragerAlleen), sub: true },
          ],
          chart_data: {
            type: 'overlijden_vergelijk',
            huidig_max_hypotheek: maxHypotheekHuidig,
            max_hypotheek_na_overlijden: maxHypotheekAanvragerAlleen,
            geadviseerd_hypotheekbedrag: hypotheekBedrag,
            label_bar1: 'Huidig',
            label_bar2: 'Na scheiding',
          },
        },
        {
          title: `${partnerNaam} alleen`,
          rows: [
            { label: 'Resterend inkomen', value: formatBedrag(totalInkomenPartner), bold: true },
            { label: `Inkomen ${partnerNaam}`, value: formatBedrag(totalInkomenPartner), sub: true },
            { label: 'Maximale hypotheek', value: formatBedrag(maxHypotheekPartnerAlleen), sub: true },
          ],
          chart_data: {
            type: 'overlijden_vergelijk',
            huidig_max_hypotheek: maxHypotheekHuidig,
            max_hypotheek_na_overlijden: maxHypotheekPartnerAlleen,
            geadviseerd_hypotheekbedrag: hypotheekBedrag,
            label_bar1: 'Huidig',
            label_bar2: 'Na scheiding',
          },
        },
      ],
      advisor_note: 'Bij relatiebeëindiging moet de hypotheek door één inkomen '
        + 'gedragen worden. Partneralimentatie kan het inkomen '
        + 'aanvullen maar is niet gegarandeerd op lange termijn.',
    });

    // Voeg relatiebeëindiging toe aan scenario_checks
    const hasRelatieTekort =
      maxHypotheekAanvragerAlleen < hypotheekBedrag ||
      maxHypotheekPartnerAlleen < hypotheekBedrag;
    scenarioChecks.push({
      label: 'Relatiebeëindiging',
      status: hasRelatieTekort ? 'warning' : 'ok',
    });
  }
} // einde if (hasPartner)
```

**Let op positie:** De relatiebeëindiging-sectie komt ná de WW-sectie en vóór attention-points.

---

## Deel F: Afsluiting-sectie (vervangt disclaimer)

### F1. Verwijder de oude disclaimer-sectie

De `disclaimer` sectie uit G4 (Deel C10) moet worden **vervangen** door een `closing` sectie. Verwijder de oude sectie met `id: 'disclaimer'`.

### F2. Voeg closing-sectie toe

Voeg aan het einde van de `sections[]` array (na attention-points) de volgende sectie toe:

```typescript
sections.push({
  id: 'closing',
  title: 'Afsluiting',
  visible: true,
  narratives: [
    'Dit Persoonlijk Hypotheekadvies en de bijbehorende berekeningen '
    + 'zijn uitsluitend bedoeld als advies. Dit advies is geen aanbod '
    + 'voor het aangaan van een overeenkomst, u kunt hieraan geen rechten '
    + 'ontlenen. De berekeningen zijn gebaseerd op de persoonlijke en '
    + 'financiële gegevens die u ons heeft gegeven.',
    'Dit hypotheekadvies is gebaseerd op de gegevens die wij van u '
    + 'hebben ontvangen en op de relevante (fiscale) wet- en regelgeving '
    + 'die nu geldt. Van een totaal fiscaal advies is geen sprake. '
    + 'Daarvoor verwijzen wij u naar een fiscaal adviseur. Hondsrug '
    + 'Finance aanvaardt geen aansprakelijkheid voor eventuele toekomstige '
    + 'wijzigingen in de fiscale wet- en regelgeving.',
  ],
});
```

De backend template herkent `id: "closing"` en rendert automatisch een handtekeningblok met datum (`meta.date`), adviseur (`meta.advisor`) en bedrijfsnaam (`bedrijf.naam`).

---

## Deel G: Volledige sectie-volgorde

Na alle wijzigingen is de volgorde van secties in de `sections[]` array:

```
1. summary              — G4 (+ scenario_checks uit Deel D)
2. client-profile        — G4 (ongewijzigd)
3. current-situation     — NIEUW (Deel B)
4. affordability         — G4 (ongewijzigd)
5. financing             — G4 (ongewijzigd)
6. loan-parts            — G4 (ongewijzigd)
7. retirement            — G4 Deel D (nu verplicht via Deel C)
8. risk-death            — G4 Deel D (nu verplicht via Deel C)
9. risk-disability       — G4 Deel D (nu verplicht via Deel C)
10. risk-unemployment    — G4 Deel D (nu verplicht via Deel C)
11. risk-relationship    — NIEUW (Deel E, alleen bij stel)
12. attention-points     — G4 (ongewijzigd)
13. closing              — NIEUW (Deel F, vervangt disclaimer)
```

---

## Verificatie

| # | Check | Verwacht resultaat |
|---|-------|--------------------|
| 1 | Open adviesrapport dialog | Bestaande velden (adviseur, datum, klantprofiel, risicobereidheid) zichtbaar |
| 2 | Klik op accordion "Risico-analyse gegevens" | Velden klappen open: type dienstverband, AOW-inkomen, AO%, etc. |
| 3 | Alleenstaand dossier: partner-velden | Niet zichtbaar (geen nabestaandenpensioen, partner dienstverband, kind <18) |
| 4 | Stel dossier: partner-velden | Alle velden zichtbaar (incl. nabestaandenpensioen, kind <18) |
| 5 | Genereer rapport (alleenstaand) | PDF wordt gegenereerd, geen 500 error |
| 6 | PDF bevat "Huidige situatie" sectie | Persoonsgegevens, inkomen-tabel, vermogen, verplichtingen |
| 7 | PDF samenvatting bevat scenario-checks | Gekleurde blokjes (groen/rood) per risicoscenario |
| 8 | PDF bevat pensioen-sectie | Met SVG grafiek en max hypotheek rows |
| 9 | PDF bevat AO-sectie | Met fasen (loondoorbetaling, WGA, etc.) en SVG grafiek |
| 10 | PDF bevat WW-sectie | Met per-jaar breakdown en SVG grafiek |
| 11 | Genereer rapport (stel) | PDF bevat overlijden-sectie met 2 kolommen + grafieken |
| 12 | PDF bevat relatiebeëindiging (stel) | 2 kolommen (aanvrager/partner alleen) met max hypotheek + grafiek |
| 13 | PDF alleenstaand: geen relatiebeëindiging | Sectie niet aanwezig |
| 14 | PDF bevat "Afsluiting" | Disclaimertekst + datum + adviseur handtekening-blok |
| 15 | PDF bevat GEEN "Disclaimer" sectie | Oude disclaimer is vervangen door closing |
| 16 | Risk-scenarios API faalt → rapport toch gegenereerd | Basissecties aanwezig, risico-secties ontbreken, geen crash |

---

## Samenvatting wijzigingen

| Onderdeel | Wijziging |
|-----------|-----------|
| Dialog UI | Inklapbaar accordion "Risico-analyse gegevens" met 6-10 extra velden |
| `AdviesrapportOptions` type | 9 nieuwe velden (dienstverband, AOW-inkomen, nabestaandenpensioen, AO%, RVC%, kind <18) |
| Helper functies | `mapInkomenVerdeling()` + `berekenLeeftijd()` |
| Risk-scenarios request | Uitgebreid van ~15 naar ~40 velden (inkomensverdeling, AO-params, overlijden-velden) |
| Risk-scenarios flow | Van "optioneel" naar standaard (met try/catch fallback) |
| Nieuwe sectie: `current-situation` | Subsections met persoonsgegevens, inkomen, vermogen, verplichtingen |
| Nieuwe sectie: `risk-relationship` | Per-persoon max hypotheek na scheiding (2 extra `/calculate` calls) |
| Nieuwe sectie: `closing` | Vaste disclaimer + handtekeningblok (vervangt `disclaimer` sectie) |
| Samenvatting uitbreiding | `scenario_checks[]` afgeleid van risk-scenarios response |

**Risico:** Medium. Drie extra API-calls (risk-scenarios + 2× calculate voor relatiebeëindiging) kunnen de generatietijd verlengen. Door try/catch wrappers blijft het rapport werkend als een call faalt.
