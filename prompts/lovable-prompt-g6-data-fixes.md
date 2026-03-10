# Lovable Prompt G6: Adviesrapport data-fixes — diagnose + reparatie

> Dit prompt fixt de dataflow in het adviesrapport. De huidige PDF toont € 0 voor alle bedragen en mist 5 secties. Oorzaak: de wizard-rekenresultaten (natResultaten, maandlastenResultaten, leningdelen, financiering) komen niet door in de payload. Dit prompt voegt eerst diagnostische logging toe, repareert daarna de extractie, en fixt 4 formatteerfouten.

---

## Overzicht van wijzigingen

1. **Diagnostische logging** — log de volledige `invoer` structuur + alle extractie-stappen
2. **Data-extractie robuust maken** — meerdere fallback-paden per dataveld
3. **Geboortedatum format fixen** — YYYY-MM-DD → DD-MM-YYYY
4. **AO/WW grafiek labels fixen** — fase-namen behouden
5. **Ontbrekende secties herstellen** — affordability, financing, loan-parts
6. **Alle 4 highlights in samenvatting** — hypotheek, verstrekker, maandlast, woningwaarde
7. **Relatiebeëindiging toevoegen** — alleen bij stel

---

## Stap 1: Diagnostische logging toevoegen

Voeg deze console.log statements toe **aan het begin** van de functie die het adviesrapport payload opbouwt (de functie die uiteindelijk `POST /adviesrapport-pdf` aanroept). Dit is cruciaal voor debugging:

```typescript
// ─── DIAGNOSE: log de volledige invoer structuur ───
console.log('=== ADVIESRAPPORT DIAGNOSE ===');
console.log('invoer keys:', invoer ? Object.keys(invoer) : 'INVOER IS NULL/UNDEFINED');
console.log('invoer.klantGegevens:', JSON.stringify(invoer?.klantGegevens, null, 2));
console.log('invoer.haalbaarheidsBerekeningen:', JSON.stringify(invoer?.haalbaarheidsBerekeningen, null, 2));
console.log('invoer.berekeningen:', JSON.stringify(invoer?.berekeningen, null, 2));
console.log('invoer.scenarios:', JSON.stringify(invoer?.scenarios, null, 2));
console.log('invoer.natResultaten:', JSON.stringify(invoer?.natResultaten, null, 2));
console.log('invoer.maandlastenResultaten:', JSON.stringify(invoer?.maandlastenResultaten, null, 2));

// Check ook alternatieve paden die Lovable mogelijk gebruikt
console.log('invoer.financiering:', JSON.stringify(invoer?.financiering, null, 2));
console.log('invoer.berekening:', JSON.stringify(invoer?.berekening, null, 2));
console.log('invoer.scenario:', JSON.stringify(invoer?.scenario, null, 2));
console.log('invoer.natResultaat:', JSON.stringify(invoer?.natResultaat, null, 2));
console.log('invoer.maandlastenResultaat:', JSON.stringify(invoer?.maandlastenResultaat, null, 2));
console.log('invoer.leningdelen:', JSON.stringify(invoer?.leningdelen, null, 2));
console.log('invoer.resultaat:', JSON.stringify(invoer?.resultaat, null, 2));
console.log('invoer.result:', JSON.stringify(invoer?.result, null, 2));

// Check of data direct op het aanvraag/dossier object staat (niet genest in invoer)
// als er een parent object is (bijv. `aanvraag` of `dossier`), log die ook:
// console.log('aanvraag keys:', aanvraag ? Object.keys(aanvraag) : 'N/A');
console.log('=== EINDE DIAGNOSE ===');
```

**Laat deze logging staan** zodat we in de browser console kunnen zien welke paden data bevatten.

---

## Stap 2: Robuuste data-extractie

### 2a. Helper: formatDatum

Voeg deze helper functie toe die een datum van elk formaat naar DD-MM-YYYY converteert:

```typescript
function formatDatum(datum: string | undefined | null): string {
  if (!datum) return '';
  // Als het al DD-MM-YYYY is, geef het terug
  if (/^\d{2}-\d{2}-\d{4}$/.test(datum)) return datum;
  // YYYY-MM-DD → DD-MM-YYYY
  if (/^\d{4}-\d{2}-\d{2}/.test(datum)) {
    const [y, m, d] = datum.substring(0, 10).split('-');
    return `${d}-${m}-${y}`;
  }
  return datum;
}
```

### 2b. Data extractie met meerdere fallback-paden

**Vervang** de bestaande data-extractie (de variabelen `klant`, `ber`, `fin`, `natRes`, `maandRes`, `scenario`, `leningdelen`, `hypotheekBedrag`) met deze robuuste versie:

```typescript
// ── Klantgegevens ──
const klant = invoer?.klantGegevens || invoer?.klant || {};

// ── Haalbaarheidsberekening (stap 2 data) ──
const ber =
  invoer?.haalbaarheidsBerekeningen?.[0] ||
  invoer?.haalbaarheidsBerekening ||
  invoer?.berekening ||
  invoer?.haalbaarheidInput ||
  {};

// ── Financiering (stap 4 data) ──
const fin =
  invoer?.berekeningen?.[0] ||
  invoer?.financiering ||
  invoer?.financieringInput ||
  {};

// ── Scenario (geldverstrekker + leningdelen) ──
const scenario =
  invoer?.scenarios?.[0] ||
  invoer?.scenario ||
  {};

// ── NAT resultaten (POST /calculate response) ──
const natRes =
  invoer?.natResultaten?.[0] ||
  invoer?.natResultaat ||
  invoer?.natResult ||
  invoer?.resultaat ||
  invoer?.result ||
  {};

// ── Maandlasten resultaten (POST /calculate/monthly-costs response) ──
const maandRes =
  invoer?.maandlastenResultaten?.[0] ||
  invoer?.maandlastenResultaat ||
  invoer?.maandlastenResult ||
  invoer?.monthlyCostsResult ||
  {};

console.log('Extractie resultaat:', {
  klant_keys: Object.keys(klant),
  ber_keys: Object.keys(ber),
  fin_keys: Object.keys(fin),
  scenario_keys: Object.keys(scenario),
  natRes_keys: Object.keys(natRes),
  maandRes_keys: Object.keys(maandRes),
});
```

### 2c. Leningdelen extractie

```typescript
// Leningdelen: probeer meerdere paden
const leningdelen: any[] =
  scenario?.leningdelen ||
  invoer?.leningdelen ||
  invoer?.hypotheekDelen ||
  fin?.leningdelen ||
  fin?.hypotheekDelen ||
  ber?.leningdelen ||
  [];

console.log('Leningdelen gevonden:', leningdelen.length, leningdelen);
```

### 2d. Hypotheekbedrag extractie

```typescript
// Hypotheekbedrag: probeer 5 methoden
let hypotheekBedrag = 0;

// Methode 1: financiering investering - eigen middelen
const totaalInvestering = fin?.totaalInvestering || fin?.totaal_investering || 0;
const totaalEigenMiddelen = fin?.totaalEigenMiddelen || fin?.totaal_eigen_middelen || fin?.eigenMiddelen || 0;
if (totaalInvestering > 0) {
  hypotheekBedrag = totaalInvestering - totaalEigenMiddelen;
}

// Methode 2: uit financiering direct
if (hypotheekBedrag <= 0) {
  hypotheekBedrag = fin?.hypotheekBedrag || fin?.hypotheekbedrag || fin?.hypotheek || 0;
}

// Methode 3: som van leningdelen
if (hypotheekBedrag <= 0 && leningdelen.length > 0) {
  hypotheekBedrag = leningdelen.reduce((sum: number, d: any) => {
    const box1 = d.bedragBox1 || d.hoofdsomBox1 || d.hoofdsom_box1 || d.bedrag || 0;
    const box3 = d.bedragBox3 || d.hoofdsomBox3 || d.hoofdsom_box3 || 0;
    return sum + box1 + box3;
  }, 0);
}

// Methode 4: uit NAT resultaat
if (hypotheekBedrag <= 0) {
  hypotheekBedrag = natRes?.scenario1?.annuitair?.max_box1 || 0;
}

// Methode 5: uit scenario
if (hypotheekBedrag <= 0) {
  hypotheekBedrag = scenario?.hypotheekBedrag || scenario?.hypotheekbedrag || 0;
}

console.log('hypotheekBedrag:', hypotheekBedrag, '(methode:',
  totaalInvestering > 0 ? '1:investering' :
  (fin?.hypotheekBedrag ? '2:fin.hypotheekBedrag' :
  (leningdelen.length > 0 ? '3:leningdelen' :
  (natRes?.scenario1 ? '4:natRes' : '5:scenario'))), ')');
```

### 2e. Inkomengegevens extractie

```typescript
// Inkomengegevens: probeer meerdere paden
const ink =
  ber?.inkomenGegevens ||
  ber?.inkomen ||
  invoer?.inkomenGegevens ||
  invoer?.inkomen ||
  klant?.inkomen ||
  {};

// Inkomen aanvrager — probeer meerdere veldnamen
const hoofdinkomenAanvrager =
  ink?.hoofdinkomenAanvrager ||
  ink?.hoofd_inkomen_aanvrager ||
  ink?.inkomenAanvrager ||
  klant?.hoofdinkomenAanvrager ||
  ber?.hoofd_inkomen_aanvrager ||
  0;

const hoofdinkomenPartner =
  ink?.hoofdinkomenPartner ||
  ink?.hoofd_inkomen_partner ||
  ink?.inkomenPartner ||
  klant?.hoofdinkomenPartner ||
  ber?.hoofd_inkomen_partner ||
  0;

console.log('Inkomens:', { hoofdinkomenAanvrager, hoofdinkomenPartner });
```

### 2f. Maandlasten extractie

```typescript
// Maandlasten
const brutoMaandlast =
  maandRes?.total_gross_monthly ||
  maandRes?.brutoMaandlast ||
  maandRes?.totalGrossMonthly ||
  0;

const nettoMaandlast =
  maandRes?.net_monthly_cost ||
  maandRes?.nettoMaandlast ||
  maandRes?.netMonthlyCost ||
  0;

console.log('Maandlasten:', { brutoMaandlast, nettoMaandlast });
```

### 2g. Geldverstrekker + productlijn + onderpand

```typescript
const geldverstrekker =
  scenario?.geldverstrekker ||
  invoer?.geldverstrekker ||
  fin?.geldverstrekker ||
  '';

const productlijn =
  scenario?.productlijn ||
  invoer?.productlijn ||
  fin?.productlijn ||
  '';

const nhg =
  scenario?.nhg ||
  invoer?.nhg ||
  fin?.nhg ||
  false;

const woningwaarde =
  ber?.onderpand?.woningwaarde ||
  ber?.onderpand?.koopsom ||
  fin?.woningwaarde ||
  fin?.koopsom ||
  klant?.woningwaarde ||
  0;

const energielabel =
  ber?.onderpand?.energielabel ||
  invoer?.energielabel ||
  'Geen (geldig) Label';

console.log('Geldverstrekker:', geldverstrekker, 'Woningwaarde:', woningwaarde);
```

---

## Stap 3: Geboortedatum overal formatteren

Overal waar een geboortedatum wordt weergegeven, gebruik `formatDatum()`:

```typescript
// In klantprofiel sectie:
{ label: 'Geboortedatum', value: formatDatum(klant.geboortedatumAanvrager || klant.geboortedatum) }

// In huidige situatie sectie:
{ label: 'Geboortedatum', value: formatDatum(klant.geboortedatumAanvrager) }
{ label: 'Geboortedatum', value: formatDatum(klant.geboortedatumPartner) }
```

Zoek in de bestaande code ALLE plekken waar `klant.geboortedatumAanvrager` of `klant.geboortedatumPartner` als waarde wordt doorgegeven en wrap ze in `formatDatum()`.

---

## Stap 4: AO/WW grafiek labels fixen

De AO-secties tonen "aanvrager aanvrager aanvrager" als grafiek-labels. Dit komt doordat de `naam` van elk scenario (bijv. `"AO aanvrager — loondoorbetaling"`) wordt afgekapt door een regex die alles na de eerste spatie verwijdert.

### Fix: labels voor vergelijk_fasen chart_data

Zoek de code die `chart_data` opbouwt voor de AO-secties. De `labels[]` array wordt waarschijnlijk zo gebouwd:

```typescript
// FOUT (huidige code, stript de fasenaam):
labels: aoScenarios.map(s => s.naam.replace(/^AO /, '').replace(/ .*$/, ''))

// FIX — gebruik een betere regex die alleen het prefix verwijdert:
labels: aoScenarios
  .filter(s => s.naam?.toLowerCase().includes(personLabel.toLowerCase()))
  .map(s => {
    // Verwijder "AO aanvrager — " of "AO partner — " prefix, behoud de rest
    return s.naam
      .replace(/^AO\s+(aanvrager|partner)\s*[—–-]\s*/i, '')
      .trim() || s.naam;
  })
```

Doe hetzelfde voor de **WW-secties**:

```typescript
// WW labels
labels: wwScenarios
  .filter(s => s.naam?.toLowerCase().includes(personLabel.toLowerCase()))
  .map(s => {
    return s.naam
      .replace(/^(Werkloosheid|Na WW)\s+(aanvrager|partner)\s*[—–-]?\s*/i, '')
      .trim() || s.naam;
  })
```

**Als de labels leeg zijn na het strippen, gebruik dan de volledige naam.**

### Alternatieve fix (als je de huidige regex niet kunt vinden)

Zoek naar `chart_data` met `type: 'vergelijk_fasen'` in de AO-sectie code. De `labels` array moet de fase-namen bevatten, niet "aanvrager" herhaald. Goede labels zijn:

- AO: `["Loondoorbetaling", "WGA loongerelateerd", "WGA loonaanvulling"]`
- WW: `["Werkloosheid", "Na WW"]`

Hardcode deze labels als de dynamische extractie niet werkt:

```typescript
// AO chart labels hardcoded als fallback
const aoLabels = ['Loondoorbetaling', 'WGA loongerelateerd', 'WGA loonaanvulling'];

// WW chart labels hardcoded als fallback
const wwLabels = ['Werkloosheid', 'Na WW'];
```

---

## Stap 5: Alle 4 highlights in samenvatting

De summary sectie toont nu slechts 1 highlight (HYPOTHEEKBEDRAG € 0). Vervang de `highlights` array in de summary sectie met:

```typescript
highlights: [
  {
    label: 'Hypotheekbedrag',
    value: formatBedrag(hypotheekBedrag),
    note: geldverstrekker || undefined,
  },
  ...(geldverstrekker ? [{
    label: 'Hypotheekverstrekker',
    value: geldverstrekker,
    note: productlijn || undefined,
  }] : []),
  ...(nettoMaandlast > 0 ? [{
    label: 'Netto maandlast',
    value: formatBedrag(nettoMaandlast),
    note: `Bruto: ${formatBedrag(brutoMaandlast)}`,
  }] : []),
  ...(woningwaarde > 0 ? [{
    label: 'Woningwaarde',
    value: formatBedrag(woningwaarde),
    note: nhg ? 'NHG' : undefined,
  }] : []),
],
```

**Let op:** als `hypotheekBedrag` 0 is én er geen maandlasten zijn, toon dan in elk geval het hypotheekbedrag-highlight. Zo kan de adviseur zien dat er data ontbreekt.

---

## Stap 6: Ontbrekende secties herstellen

### 6a. Betaalbaarheid (affordability)

Deze sectie ontbreekt. Voeg hem toe na `client-profile` en `current-situation`, vóór `financing`:

```typescript
// Betaalbaarheid sectie
const toetsinkomen = natRes?.debug?.toets_inkomen || 0;
const toetsrente = natRes?.debug?.toets_rente || 0;
const woonquoteBox1 = natRes?.debug?.woonquote_box1 || 0;
const maxHypotheek = natRes?.scenario1?.annuitair?.max_box1 || 0;

const affordabilityRows: any[] = [];
if (toetsinkomen > 0) {
  affordabilityRows.push({ label: 'Toetsinkomen', value: formatBedrag(toetsinkomen) });
}
if (toetsrente > 0) {
  affordabilityRows.push({ label: 'Toetsrente', value: `${(toetsrente * 100).toFixed(3)}%` });
}
if (woonquoteBox1 > 0) {
  affordabilityRows.push({ label: 'Woonquote', value: `${(woonquoteBox1 * 100).toFixed(1)}%` });
}
if (maxHypotheek > 0) {
  affordabilityRows.push({ label: 'Maximale hypotheek', value: formatBedrag(maxHypotheek), bold: true });
}
if (hypotheekBedrag > 0) {
  affordabilityRows.push({ label: 'Geadviseerd hypotheekbedrag', value: formatBedrag(hypotheekBedrag), bold: true });
}

if (affordabilityRows.length > 0) {
  sections.push({
    id: 'affordability',
    title: 'Betaalbaarheid',
    visible: true,
    narratives: [
      `Op basis van een toetsinkomen van ${toetsinkomen > 0 ? formatBedrag(toetsinkomen) : 'het opgegeven inkomen'} `
      + `en de geldende leennormen ${new Date().getFullYear()} `
      + `is de maximale hypotheek ${maxHypotheek > 0 ? formatBedrag(maxHypotheek) : 'berekend'}.`
      + (hypotheekBedrag > 0 && maxHypotheek > 0
        ? ` Het geadviseerde hypotheekbedrag van ${formatBedrag(hypotheekBedrag)} valt ${hypotheekBedrag <= maxHypotheek ? 'binnen' : 'boven'} de maximale leencapaciteit.`
        : ''),
    ],
    rows: affordabilityRows,
  });
}
```

### 6b. Financieringsopzet (financing)

```typescript
const financingRows: any[] = [];

// Investering
const koopsom = fin?.koopsom || fin?.aankoopbedrag || woningwaarde || 0;
if (koopsom > 0) {
  financingRows.push({ label: 'Koopsom / aankoopbedrag', value: formatBedrag(koopsom) });
}

const verbouwing = fin?.verbouwing || fin?.verbouwingskosten || 0;
if (verbouwing > 0) {
  financingRows.push({ label: 'Verbouwing', value: formatBedrag(verbouwing) });
}

const koperskosten = fin?.koperskosten || fin?.bijkomendeKosten || fin?.kosten_koper || 0;
if (koperskosten > 0) {
  financingRows.push({ label: 'Kosten koper', value: formatBedrag(koperskosten) });
}

if (totaalInvestering > 0) {
  financingRows.push({ label: 'Totaal investering', value: formatBedrag(totaalInvestering), bold: true });
  financingRows.push({ label: '', value: '', spacer: true }); // visuele scheiding
}

// Eigen middelen
const eigenGeld = fin?.eigenGeld || fin?.eigen_geld || fin?.spaargeld || 0;
if (eigenGeld > 0) {
  financingRows.push({ label: 'Eigen geld', value: formatBedrag(eigenGeld) });
}

const schenking = fin?.schenking || 0;
if (schenking > 0) {
  financingRows.push({ label: 'Schenking', value: formatBedrag(schenking) });
}

if (totaalEigenMiddelen > 0) {
  financingRows.push({ label: 'Totaal eigen middelen', value: formatBedrag(totaalEigenMiddelen), bold: true });
  financingRows.push({ label: '', value: '', spacer: true });
}

if (hypotheekBedrag > 0) {
  financingRows.push({ label: 'Benodigd hypotheekbedrag', value: formatBedrag(hypotheekBedrag), bold: true });
}

if (financingRows.length > 0) {
  sections.push({
    id: 'financing',
    title: 'Financieringsopzet',
    visible: true,
    rows: financingRows,
  });
}
```

### 6c. Leningdelen (loan-parts)

```typescript
if (leningdelen.length > 0) {
  const leningdelenRows = leningdelen.map((deel: any, i: number) => {
    const bedrag = (deel.bedragBox1 || deel.hoofdsomBox1 || deel.hoofdsom_box1 || deel.bedrag || 0)
      + (deel.bedragBox3 || deel.hoofdsomBox3 || deel.hoofdsom_box3 || 0);
    const aflosvorm = deel.aflossingsvorm || deel.aflos_type || deel.aflosvorm || 'Annuïteit';
    const rente = deel.rente || deel.werkelijkeRente || deel.werkelijke_rente || 0;
    const renteStr = typeof rente === 'number' && rente < 1
      ? `${(rente * 100).toFixed(2)}%`
      : `${Number(rente).toFixed(2)}%`;
    const looptijd = deel.looptijd || deel.org_lpt || 360;
    const looptijdJaar = Math.round(looptijd / 12);
    const rvp = deel.rvp || 120;
    const rvpJaar = Math.round(rvp / 12);

    return [
      `Deel ${i + 1}`,
      formatBedrag(bedrag),
      aflosvorm,
      renteStr,
      `${looptijdJaar} jaar`,
      `${rvpJaar} jaar`,
    ];
  });

  sections.push({
    id: 'loan-parts',
    title: 'Leningdelen',
    visible: true,
    tables: [{
      headers: ['Leningdeel', 'Bedrag', 'Aflosvorm', 'Rente', 'Looptijd', 'RVP'],
      rows: leningdelenRows,
    }],
    ...(brutoMaandlast > 0 || nettoMaandlast > 0 ? {
      rows: [
        ...(brutoMaandlast > 0 ? [{ label: 'Bruto maandlast', value: formatBedrag(brutoMaandlast) }] : []),
        ...(nettoMaandlast > 0 ? [{ label: 'Netto maandlast', value: formatBedrag(nettoMaandlast), bold: true }] : []),
      ]
    } : {}),
  });
}
```

### 6d. Positie van secties

Zorg dat de volgorde correct is. Na alle secties zijn opgebouwd:

```
1. summary
2. client-profile
3. current-situation
4. affordability        ← NIEUW (stap 6a)
5. financing            ← NIEUW (stap 6b)
6. loan-parts           ← NIEUW (stap 6c)
7. retirement
8. risk-death
9. risk-disability
10. risk-unemployment
11. risk-relationship   (alleen stel)
12. attention-points
13. closing
```

---

## Stap 7: Risk-scenarios request repareren

Het `geadviseerd_hypotheekbedrag` veld in de risk-scenarios request is 0 omdat `hypotheekBedrag` 0 was. Na de fix in stap 2d wordt dit automatisch opgelost. Maar controleer ook dat de `hypotheek_delen` correct doorstromen:

```typescript
// In de risk-scenarios request, vervang de hypotheek_delen mapping met:
hypotheek_delen: leningdelen.length > 0
  ? leningdelen.map((deel: any) => ({
      aflos_type: deel.aflossingsvorm || deel.aflos_type || deel.aflosvorm || 'Annuïteit',
      org_lpt: deel.looptijd || deel.org_lpt || 360,
      rest_lpt: deel.restLooptijd || deel.rest_lpt || deel.looptijd || deel.org_lpt || 360,
      hoofdsom_box1: deel.bedragBox1 || deel.hoofdsomBox1 || deel.hoofdsom_box1 || deel.bedrag || 0,
      hoofdsom_box3: deel.bedragBox3 || deel.hoofdsomBox3 || deel.hoofdsom_box3 || 0,
      rvp: deel.rvp || 120,
      werkelijke_rente: deel.rente || deel.werkelijkeRente || deel.werkelijke_rente || 0.05,
      inleg_overig: deel.inlegOverig || deel.inleg_overig || 0,
    }))
  : [{
      // Fallback: 1 standaard leningdeel gebaseerd op hypotheekbedrag
      aflos_type: 'Annuïteit',
      org_lpt: 360,
      rest_lpt: 360,
      hoofdsom_box1: hypotheekBedrag,
      hoofdsom_box3: 0,
      rvp: 120,
      werkelijke_rente: 0.05,
      inleg_overig: 0,
    }],
```

---

## Stap 8: Secties alleen tonen als er data is

Sommige secties moeten `visible: false` krijgen als er geen data is:

```typescript
// Na het opbouwen van alle secties, filter de lege:
const finalSections = sections.filter(s => {
  if (!s.visible) return false;
  // Check of de sectie inhoud heeft
  const hasContent =
    (s.rows && s.rows.length > 0) ||
    (s.tables && s.tables.length > 0) ||
    (s.narratives && s.narratives.length > 0) ||
    (s.highlights && s.highlights.length > 0) ||
    (s.columns && s.columns.length > 0) ||
    (s.subsections && s.subsections.length > 0) ||
    (s.list_items && s.list_items.length > 0);
  return hasContent;
});
```

Gebruik `finalSections` (in plaats van `sections`) bij het verzenden naar de API.

---

## Verificatie

Na het plakken van deze prompt, genereer het rapport opnieuw en check:

| # | Check | Verwacht |
|---|-------|----------|
| 1 | Open browser console (F12) | `=== ADVIESRAPPORT DIAGNOSE ===` logging zichtbaar |
| 2 | Check welke `invoer` keys data bevatten | Noteer welke paden WEL en NIET werken |
| 3 | `hypotheekBedrag` in console | > 0 (met methode-indicatie) |
| 4 | PDF samenvatting | Hypotheekbedrag > € 0, meerdere highlights |
| 5 | PDF klantprofiel geboortedatum | DD-MM-YYYY format (bijv. 01-02-1968) |
| 6 | PDF huidige situatie geboortedatum | DD-MM-YYYY format |
| 7 | PDF betaalbaarheid sectie | Toetsinkomen, toetsrente, max hypotheek |
| 8 | PDF financieringsopzet sectie | Investering, eigen middelen, hypotheekbedrag |
| 9 | PDF leningdelen sectie | Tabel met bedragen, aflosvorm, rente |
| 10 | AO grafiek labels | "Loondoorbetaling", "WGA loongerelateerd", etc. (NIET "aanvrager aanvrager aanvrager") |
| 11 | WW grafiek labels | "Werkloosheid", "Na WW" (NIET "Werkloosheid Na") |
| 12 | Scenario checks samenvatting | Klopt met werkelijke bedragen |
| 13 | Pensioen AOW partner | Max hypotheek > € 0 |

**BELANGRIJK:** Na het genereren, kopieer de volledige console output (vanaf `=== ADVIESRAPPORT DIAGNOSE ===`) en stuur dit naar mij. Op basis daarvan kan ik zien welke paden werken en welke niet, en een gerichte vervolgfix schrijven.

---

## Samenvatting wijzigingen

| Onderdeel | Wijziging |
|-----------|-----------|
| Diagnostische logging | `console.log` op alle data-extractiepunten |
| Data-extractie | Meerdere fallback-paden per dataveld (5+ methoden voor hypotheekBedrag) |
| `formatDatum()` helper | Converteert YYYY-MM-DD → DD-MM-YYYY |
| Geboortedatum weergave | Alle plekken gewrapt in `formatDatum()` |
| AO/WW grafiek labels | Fase-namen behouden (loondoorbetaling, WGA, etc.) |
| Summary highlights | 4 highlights (hypotheek, verstrekker, maandlast, woningwaarde) |
| Nieuwe sectie: affordability | Toetsinkomen, toetsrente, woonquote, max hypotheek |
| Nieuwe sectie: financing | Investering, kosten, eigen middelen |
| Nieuwe sectie: loan-parts | Leningdelen tabel + maandlasten |
| Risk-scenarios request | Fallback leningdeel als `leningdelen` leeg is |
| Lege secties filter | Secties zonder inhoud worden niet getoond |
