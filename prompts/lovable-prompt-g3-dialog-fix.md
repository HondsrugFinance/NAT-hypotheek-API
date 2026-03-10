# Lovable Prompt G3: Adviesrapport dialog vereenvoudigen + data-mapping fixen

> Dit prompt vervangt de huidige "Adviesrapport samenstellen" dialog. De sectie-checkboxes en hypotheek-velden worden verwijderd (deze komen uit de aanvraag), en er worden invoervelden toegevoegd voor de "zachte" klantprofielgegevens die niet uit de aanvraag komen.

---

## Probleem

De huidige dialog heeft drie problemen:
1. **Sectie-selectie is overbodig** — welke secties in het rapport komen wordt automatisch bepaald, niet door de adviseur
2. **Hypotheek-velden zijn overbodig** — geldverstrekker, productlijn en NHG komen al uit de aanvraag-data
3. **Zachte info ontbreekt** — er zijn geen invoervelden voor klantprofiel (ervaring, kennis, risicobereidheid, prioriteit)
4. **Rapport is leeg** — de data-mapping vindt de berekeningen niet in de aanvraag-data, waardoor bedragen op € 0 staan

---

## Stap 1: Dialog layout vervangen

Vervang het huidige configuratiescherm (stap 2 van de dialog, na aanvraag-selectie) volledig. Verwijder de linkerkolom met sectie-checkboxes. Verwijder ook geldverstrekker, productlijn en NHG (deze worden uit de aanvraag gehaald).

### Nieuwe layout: twee kolommen

```
┌─────────────────────────────────────────────────────────┐
│  ← Terug          Adviesrapport samenstellen            │
│                                                         │
│  Aanvraag: Aankoop: Bestaande bouw                      │
│                                                         │
│  ┌─ RAPPORT ────────────────┐  ┌─ KLANTPROFIEL ───────┐ │
│  │                          │  │                       │ │
│  │  Adviseur:               │  │  Ervaring hypotheek:  │ │
│  │  [▾ Alex Kuijper CFP® ]  │  │  [▾ Nee            ]  │ │
│  │                          │  │                       │ │
│  │  Datum:                  │  │  Kennis hypotheek-    │ │
│  │  [📅 10-03-2026       ]  │  │  vormen:              │ │
│  │                          │  │  [▾ Redelijk       ]  │ │
│  │  Dossiernummer:          │  │                       │ │
│  │  [HF-2026-001         ]  │  │  Kennis fiscale       │ │
│  │                          │  │  regels:              │ │
│  └──────────────────────────┘  │  [▾ Matig          ]  │ │
│                                │                       │ │
│                                │  Klantprioriteit:     │ │
│                                │  [▾ Stabiele        ] │ │
│                                │     maandlast         │ │
│                                │                       │ │
│                                │  ── Risicobereidheid ─│ │
│                                │                       │ │
│                                │  Pensioen:            │ │
│                                │  [▾ Een beetje bep. ]  │ │
│                                │                       │ │
│                                │  Arbeidsongeschikth.: │ │
│                                │  [▾ Een beetje bep. ]  │ │
│                                │                       │ │
│                                │  Werkloosheid:        │ │
│                                │  [▾ Risico aanvaard.] │ │
│                                │                       │ │
│                                │  Waardedaling woning: │ │
│                                │  [▾ Een beetje bep. ]  │ │
│                                │                       │ │
│                                │  Rentestijging:       │ │
│                                │  [▾ Risico aanvaard.] │ │
│                                │                       │ │
│                                │  Aflopen renteaftrek: │ │
│                                │  [▾ Risico aanvaard.] │ │
│                                └───────────────────────┘ │
│                                                         │
│        [Annuleren]              [Genereer rapport →]    │
└─────────────────────────────────────────────────────────┘
```

### Linkerkolom: Rapport meta (vereenvoudigd)

Alleen de velden die NIET uit de aanvraag komen:

| Veld | Type | Standaard | Toelichting |
|------|------|-----------|-------------|
| Adviseur | Dropdown | Eigenaar van het dossier (`owner_name`) | Keuze uit alle gebruikers met een account. Haal de lijst op uit de `profiles` tabel in Supabase (alle gebruikers met `role = 'adviseur'` of `role = 'admin'`). Toon de naam, default de eigenaar van het dossier. |
| Datum | Datumveld | Vandaag | Wordt gebruikt als datum in het adviesrapport (`meta.date`). Format: DD-MM-YYYY. |
| Dossiernummer | Tekstveld | Dossiernummer van het dossier | Kan handmatig worden aangepast |

**Verwijderd** (komt uit de aanvraag-data):
- ~~Geldverstrekker~~ → wordt uit de aanvraag gehaald (zie stap 3)
- ~~Productlijn~~ → wordt uit de aanvraag gehaald
- ~~NHG~~ → wordt uit de aanvraag gehaald
- ~~Scenario dropdown~~ → gebruik altijd het eerste scenario

### Rechterkolom: Klantprofiel (NIEUW)

Deze gegevens worden NIET uit de aanvraag gehaald — de adviseur vult ze in per adviesrapport.

**Bovenste deel — kennis en ervaring:**

| Veld | Type | Opties | Standaard |
|------|------|--------|-----------|
| Ervaring met een hypotheek | Dropdown | "Ja", "Nee" | "Nee" |
| Kennis van hypotheekvormen | Dropdown | "Geen", "Beperkt", "Redelijk", "Goed" | "Redelijk" |
| Kennis van fiscale regels | Dropdown | "Geen", "Beperkt", "Matig", "Goed" | "Matig" |
| Klantprioriteit | Dropdown | "Stabiele maandlast", "Zo laag mogelijke maandlast", "Zo snel mogelijk aflossen", "Maximale flexibiliteit" | "Stabiele maandlast" |

**Onderste deel — risicobereidheid per risico:**

Toon een subkopje "Risicobereidheid" met 6 dropdown-rijen:

| Risico | Opties | Standaard |
|--------|--------|-----------|
| Pensioen | "Risico aanvaarden", "Risico een beetje beperken", "Risico zoveel mogelijk beperken", "Risico niet bereid te aanvaarden" | "Risico een beetje beperken" |
| Arbeidsongeschiktheid | Zelfde opties | "Risico een beetje beperken" |
| Werkloosheid | Zelfde opties | "Risico aanvaarden" |
| Waardedaling woning | Zelfde opties | "Risico een beetje beperken" |
| Rentestijging | Zelfde opties | "Risico aanvaarden" |
| Aflopen hypotheekrenteaftrek | Zelfde opties | "Risico aanvaarden" |

---

## Stap 2: AdviesrapportOptions type aanpassen

Vervang het huidige options-type:

```typescript
interface AdviesrapportOptions {
  // Rapport meta
  adviseur: string;
  datum: string;             // "DD-MM-YYYY"
  dossierNummer: string;

  // Klantprofiel (zachte info)
  ervaringHypotheek: string;          // "Ja" | "Nee"
  kennisHypotheekvormen: string;      // "Geen" | "Beperkt" | "Redelijk" | "Goed"
  kennisFiscaleRegels: string;        // "Geen" | "Beperkt" | "Matig" | "Goed"
  klantPrioriteit: string;            // "Stabiele maandlast" | etc.
  risicobereidheid: {
    pensioen: string;
    arbeidsongeschiktheid: string;
    werkloosheid: string;
    waardedalingWoning: string;
    rentestijging: string;
    aflopenRenteaftrek: string;
  };
}
```

**Verwijderd uit options** (wordt nu uit de aanvraag-data gehaald):
- ~~`geldverstrekker`~~
- ~~`productlijn`~~
- ~~`nhg`~~
- ~~`selectedSections`~~
- ~~`scenarioIndex`~~

---

## Stap 3: Data-mapping fixen — aanvraag data correct lezen

### 3a. Geldverstrekker, productlijn en NHG uit aanvraag halen

Deze velden zitten in de aanvraag-data, niet meer in de dialog opties. Haal ze uit het scenario of de berekening:

```typescript
// Geldverstrekker en productlijn uit scenario/aanvraag
const geldverstrekker = scenario?.geldverstrekker
  || invoer?.geldverstrekker
  || '';
const productlijn = scenario?.productlijn
  || invoer?.productlijn
  || '';
const nhg = scenario?.nhg
  || invoer?.nhgToepassen
  || fin?.nhgKosten > 0
  || false;
```

### 3b. Console.log de aanvraag data (tijdelijk)

Voeg **tijdelijk** een console.log toe in `buildAdviesrapportPayload`, direct na het begin van de functie:

```typescript
export function buildAdviesrapportPayload(invoer: any, ...) {
  console.log('=== ADVIESRAPPORT DATA DEBUG ===');
  console.log('invoer keys:', Object.keys(invoer || {}));
  console.log('invoer.klantGegevens:', invoer?.klantGegevens);
  console.log('invoer.haalbaarheidsBerekeningen:', invoer?.haalbaarheidsBerekeningen);
  console.log('invoer.berekeningen:', invoer?.berekeningen);
  console.log('invoer.scenarios:', invoer?.scenarios);
  console.log('scenarios param:', scenarios);
  console.log('natResultaten param:', natResultaten);
  console.log('maandlastenResultaten param:', maandlastenResultaten);
  // ...rest van de functie
}
```

Open de browser DevTools (F12 → Console) en genereer een rapport. Kijk welke velden `undefined` zijn.

### 3c. Alternatieve data-paden

De data kan op meerdere plekken zitten, afhankelijk van hoe de aanvraag is opgeslagen. Pas de data-extractie aan zodat het meerdere paden probeert:

```typescript
// Scenario/berekening data — probeer meerdere paden
const ber = invoer?.haalbaarheidsBerekeningen?.[0]
  || invoer?.berekening
  || invoer?.data?.haalbaarheidsBerekeningen?.[0]
  || {};

const fin = invoer?.berekeningen?.[0]
  || invoer?.financiering
  || invoer?.data?.berekeningen?.[0]
  || {};

const scenario = invoer?.scenarios?.[0]
  || scenarios?.[0]
  || invoer?.data?.scenarios?.[0]
  || {};

// NAT resultaten — probeer meerdere paden
const natRes = natResultaten?.[0]
  || invoer?.natResultaten?.[0]
  || invoer?.haalbaarheidsBerekeningen?.[0]?.natResultaten
  || ber?.natResultaten
  || {};

// Maandlasten resultaten — probeer meerdere paden
const maandRes = maandlastenResultaten?.[0]
  || invoer?.maandlastenResultaten?.[0]
  || {};
```

### 3d. Hypotheekbedrag berekenen met fallbacks

```typescript
// Hypotheekbedrag — meerdere berekeningsmethoden
let hypotheekBedrag = 0;

// Methode 1: uit financieringsopzet
if (fin?.totaalInvestering && fin?.totaalEigenMiddelen) {
  hypotheekBedrag = (fin.totaalInvestering || 0) - (fin.totaalEigenMiddelen || 0);
}

// Methode 2: som van leningdelen
if (hypotheekBedrag === 0 && scenario?.leningdelen) {
  hypotheekBedrag = scenario.leningdelen.reduce((sum: number, deel: any) => {
    return sum + (deel.bedragBox1 || deel.hoofdsomBox1 || deel.bedrag || 0)
               + (deel.bedragBox3 || deel.hoofdsomBox3 || 0);
  }, 0);
}

// Methode 3: uit NAT resultaat
if (hypotheekBedrag === 0 && natRes?.scenario1?.annuitair?.max_box1) {
  hypotheekBedrag = natRes.scenario1.annuitair.max_box1;
}
```

---

## Stap 4: Datum uit opties gebruiken

In de `meta` van de payload, gebruik `options.datum` in plaats van automatisch vandaag:

```typescript
return {
  meta: {
    title: 'Adviesrapport Hypotheek',
    date: options.datum,  // Uit de dialog (default vandaag)
    dossierNumber: options.dossierNummer,
    advisor: options.adviseur,
    customerName,
    propertyAddress: '',
  },
  // ...
};
```

---

## Stap 5: Sectie-selectie automatisch bepalen

Vervang het `selectedSections` mechanisme. ALLE secties worden altijd meegestuurd. De backend template bepaalt op basis van `visible: true/false` en de aanwezigheid van data wat er getoond wordt.

In `buildAdviesrapportPayload`, verwijder alle `if (options.selectedSections.includes(...))` checks. Stuur altijd alle secties mee. Als een sectie geen data heeft, stel dan `visible: false` in.

```typescript
// Voorbeeld: betaalbaarheid sectie — altijd meesturen
const affordabilityRows = [];
if (natRes?.debug?.toets_inkomen) {
  affordabilityRows.push({ label: 'Toetsinkomen', value: formatBedrag(natRes.debug.toets_inkomen) });
}
// etc.

sections.push({
  id: 'affordability',
  title: 'Betaalbaarheid',
  visible: affordabilityRows.length > 0,  // automatisch visible als er data is
  narratives: [...],
  rows: affordabilityRows,
});
```

---

## Stap 6: Klantprofiel sectie vullen met zachte info

Pas de client-profile sectie aan zodat het de waarden uit de dialog-opties gebruikt:

```typescript
// --- Klantprofiel sectie ---
sections.push({
  id: 'client-profile',
  title: 'Klantprofiel',
  visible: true,
  narratives: hasPartner ? [] : ['Aanvraag zonder partner.'],
  rows: [
    // Persoonsgegevens (uit aanvraag)
    { label: 'Aanvrager — Naam', value: aanvragerNaam },
    { label: 'Aanvrager — Geboortedatum', value: klant.geboortedatumAanvrager || '' },
    ...(hasPartner ? [
      { label: '', value: '' },
      { label: 'Partner — Naam', value: partnerNaam },
      { label: 'Partner — Geboortedatum', value: klant.geboortedatumPartner || '' },
    ] : []),
    { label: '', value: '' },  // spacer
    // Kennis en ervaring (uit dialog opties — NIEUW)
    { label: 'Doel van de hypotheek', value: invoer.dossierType || 'Aankoop bestaande woning' },
    { label: 'Ervaring met een hypotheek', value: options.ervaringHypotheek },
    { label: 'Kennis van hypotheekvormen', value: options.kennisHypotheekvormen },
    { label: 'Kennis van fiscale regels', value: options.kennisFiscaleRegels },
    { label: '', value: '' },  // spacer
    // Inkomen (uit aanvraag)
    ...(ber?.inkomenGegevens ? [
      { label: 'Bruto jaarinkomen aanvrager', value: formatBedrag(ber.inkomenGegevens.hoofdinkomenAanvrager || 0) },
      ...(hasPartner ? [{ label: 'Bruto jaarinkomen partner', value: formatBedrag(ber.inkomenGegevens.hoofdinkomenPartner || 0) }] : []),
      { label: 'Totaal huishoudinkomen', value: formatBedrag(
        (ber.inkomenGegevens.hoofdinkomenAanvrager || 0) + (ber.inkomenGegevens.hoofdinkomenPartner || 0)
      ), bold: true },
    ] : []),
  ],
  // Risicobereidheid tabel (uit dialog opties — NIEUW)
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

---

## Stap 7: Hypotheek-velden in summary/loan-parts uit aanvraag-data

Gebruik de uit stap 3a gehaalde `geldverstrekker`, `productlijn` en `nhg` in de secties waar ze nodig zijn:

```typescript
// Summary highlights
highlights: [
  {
    label: 'Hypotheekbedrag',
    value: formatBedrag(hypotheekBedrag),
    note: [geldverstrekker, productlijn].filter(Boolean).join(' — ') || '',
  },
  // ...
],

// Loan-parts sectie
sections.push({
  id: 'loan-parts',
  title: 'Hypotheekonderdelen',
  visible: true,
  rows: [
    ...(geldverstrekker ? [{ label: 'Geldverstrekker', value: geldverstrekker }] : []),
    ...(productlijn ? [{ label: 'Productlijn', value: productlijn }] : []),
  ],
  // ...
});

// NHG in narratives of financing
if (nhg) {
  // Voeg NHG toe aan summary narratives en financieringsopzet
}
```

---

## Stap 8: Adviseur-dropdown — profielen ophalen uit Supabase

### 8a. Query voor de adviseur-lijst

Haal de lijst van adviseurs op uit de `profiles` tabel. Maak een query-functie (of hergebruik een bestaande):

```typescript
// In een service of hook
async function getAdviseurs(): Promise<{ id: string; naam: string }[]> {
  const { data, error } = await supabase
    .from('profiles')
    .select('id, user_name, email, role')
    .in('role', ['adviseur', 'admin'])
    .order('user_name');

  if (error || !data) return [];
  return data.map(p => ({
    id: p.id,
    naam: p.user_name || p.email || 'Onbekend',
  }));
}
```

**Let op:** De exacte kolomnaam voor de gebruikersnaam kan `user_name`, `name`, `full_name` of `display_name` zijn — controleer de bestaande `profiles` tabel-definitie in de Lovable codebase.

### 8b. In de dialog-component

```typescript
// State
const [adviseurs, setAdviseurs] = useState<{ id: string; naam: string }[]>([]);
const [selectedAdviseur, setSelectedAdviseur] = useState(dossierOwnerName);

// Ophalen bij mount
useEffect(() => {
  getAdviseurs().then(setAdviseurs);
}, []);

// Render als Select/dropdown
<Select value={selectedAdviseur} onValueChange={setSelectedAdviseur}>
  {adviseurs.map(a => (
    <SelectItem key={a.id} value={a.naam}>{a.naam}</SelectItem>
  ))}
</Select>
```

---

## Stap 9: advice_text aanpassen aan klantprofiel opties

In de `buildAdviceText` functie (uit prompt G2), gebruik `options.klantPrioriteit` in plaats van `invoer.klantGegevens?.klantPrioriteit`. Gebruik ook de uit de aanvraag gehaalde `geldverstrekker`, `nhg` etc.:

```typescript
// Alinea 1: gebruik geldverstrekker uit aanvraag-data (niet uit opties)
const geldverstrekkerNaam = geldverstrekker || 'de geldverstrekker';

// Alinea 4: Klantprioriteit uit dialog opties
const prioriteit = options.klantPrioriteit || '';
if (prioriteit) {
  paragraphs.push(
    `Bij dit advies is rekening gehouden met uw prioriteit: ${prioriteit.toLowerCase()}.`
  );
}
```

---

## Verificatie

| # | Check | Verwacht resultaat |
|---|-------|--------------------|
| 1 | Open "Adviesrapport samenstellen" dialog | Geen sectie-checkboxes, geen geldverstrekker/productlijn/NHG velden |
| 2 | Adviseur-dropdown toont alle adviseurs | Lijst uit `profiles` tabel, default = dossier-eigenaar |
| 3 | Datum-veld toont vandaag als default | Datumkiezer met DD-MM-YYYY format |
| 4 | Klantprofiel dropdowns hebben standaardwaarden | Ervaring=Nee, Kennis=Redelijk, etc. |
| 5 | Risicobereidheid dropdowns tonen 4 opties | "Risico aanvaarden" t/m "Risico niet bereid te aanvaarden" |
| 6 | Console.log toont beschikbare data | Check welke velden gevuld zijn (verwijder na test) |
| 7 | Genereer rapport → Samenvatting | Hypotheekbedrag is niet € 0, geldverstrekker komt uit aanvraag |
| 8 | Klantprofiel in PDF | Toont kennis/ervaring + risicobereidheid-tabel |
| 9 | Advies en onderbouwing | 4 alinea's met correcte bedragen en klantprioriteit |
| 10 | Datum in rapport | Toont de in de dialog gekozen datum |

---

## Samenvatting

| Onderdeel | Wijziging |
|-----------|-----------|
| Dialog UI (stap 2) | Sectie-checkboxes + hypotheek-velden verwijderen, klantprofiel-velden + datum toevoegen |
| Adviseur-veld | Dropdown i.p.v. tekstveld, gevuld uit `profiles` tabel |
| `AdviesrapportOptions` type | Vereenvoudigd: alleen meta + klantprofiel, geen hypotheek-velden |
| `buildAdviesrapportPayload` | Geldverstrekker/productlijn/NHG uit aanvraag-data halen, data-extractie met fallback-paden, automatische sectie-visibility |
| Client-profile sectie | Kennis/ervaring rows + risicobereidheid-tabel uit dialog opties |
| `buildAdviceText` | Klantprioriteit uit opties, geldverstrekker uit aanvraag |
