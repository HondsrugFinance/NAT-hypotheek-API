# Lovable Prompt E6: Samenvatting fixes (onderpand + overige inkomsten)

> Kopieer deze prompt in Lovable om twee problemen in de samenvatting (Stap 6) op te lossen:
> 1. WOZ-waarde en marktwaarde correct tonen bij onderpand
> 2. Overige inkomsten tonen bij inkomen

---

## Probleem 1: WOZ-waarde bij onderpand

Bij het onderpand in de samenvatting wordt nu de **marktwaarde** in het `woz_waarde` veld gestuurd. De backend heeft nu twee aparte velden:

- `marktwaarde` — de marktwaarde/koopsom van de woning
- `woz_waarde` — de WOZ-waarde (kan afwijken van marktwaarde)

### Oplossing

Zoek de functie die de `onderpanden[]` array opbouwt voor de samenvatting PDF-request. Pas de data-mapping aan zodat **beide waarden apart** worden meegegeven:

```typescript
// Per onderpand/scenario:
{
  naam: scenario.naam,
  adres: onderpand.adres || '',
  marktwaarde: formatBedrag(onderpand.marktwaarde || onderpand.koopsom || 0),  // NIEUW veld
  woz_waarde: formatBedrag(onderpand.wozWaarde || 0),  // Was: marktwaarde, nu: echte WOZ-waarde
  woningtype: onderpand.woningtype || '',
  energielabel: onderpand.energielabel || '',
  ebv_ebb_bedrag: onderpand.ebvEbbBedrag ? formatBedrag(onderpand.ebvEbbBedrag) : '',
}
```

**Let op:**
- `marktwaarde` is een **nieuw veld** — de backend toont het alleen als het is ingevuld
- `woz_waarde` moet nu de **echte WOZ-waarde** bevatten, niet de marktwaarde
- Als er geen aparte WOZ-waarde is ingevuld, stuur dan een lege string (`''`) — de rij wordt dan niet getoond in de PDF
- Zoek de juiste property-namen op in de bestaande types (bijv. `wozWaarde`, `koopsom`, `marktwaarde`)

---

## Probleem 2: Overige inkomsten ontbreken

In de samenvatting (Stap 6 van de berekening) worden bij "Haalbare hypotheek" onder **Inkomen** alleen het hoofdinkomen van de aanvrager en partner getoond. Wanneer er overige inkomsten zijn ingevuld (lijfrente, partneralimentatie, inkomsten uit vermogen, huurinkomsten), verschijnen deze **niet** in de samenvatting.

**Huidige weergave:**
```
INKOMEN
Harry Slinger*          € 80.000
Harriëtte Slinger**     € 35.000
Totaal inkomen          € 115.000
```

**Gewenste weergave** (wanneer overige inkomsten > 0):
```
INKOMEN
Harry Slinger*          € 80.000
  Lijfrente             € 5.000
  Partneralimentatie    € 3.600
Harriëtte Slinger**     € 35.000
  Lijfrente             € 2.400
Totaal inkomen          € 126.000
```

---

## Oplossing

Zoek de functie die de `inkomen_items[]` array opbouwt voor de samenvatting PDF-data. Dit is de functie die de `haalbaarheid`-array samenstelt (waarschijnlijk `buildHaalbaarheidData` of vergelijkbaar, in het bestand dat de samenvatting-pagina rendert of de PDF-request opbouwt).

### Huidige logica (vereenvoudigd)

```typescript
const inkomen_items = [
  { label: `${naamAanvrager}${sterretjeAanvrager}`, waarde: formatBedrag(hoofdinkomenAanvrager) },
  // ... partner als niet-alleenstaand ...
  { label: 'Totaal inkomen', waarde: formatBedrag(totaalInkomen), is_totaal: true },
];
```

### Nieuwe logica

Voeg na elke persoon (aanvrager/partner) de overige inkomsten toe als aparte rijen, maar **alleen als het bedrag > 0** is. Gebruik inspringende labels (prefix met twee spaties `"  "`) om ze als sub-items te tonen.

```typescript
// Hulpfunctie: voeg overige inkomsten toe als sub-items
function addOverigeInkomsten(
  items: { label: string; waarde: string; is_totaal?: boolean }[],
  inkomenGegevens: any,
  suffix: 'Aanvrager' | 'Partner'
) {
  // Zoek de juiste property-namen op in de bestaande types.
  // Onderstaande namen zijn voorbeelden — pas aan naar de werkelijke property-namen.
  const velden = [
    { key: `lijfrente${suffix}` /* of inkomenUitLijfrente${suffix} */, label: 'Lijfrente' },
    { key: `partneralimentatieOntvangen${suffix}` /* of ontvangenPartneralimentatie${suffix} */, label: 'Partneralimentatie' },
    ...(suffix === 'Aanvrager' ? [
      { key: 'inkomstenUitVermogen' /* of inkomstenUitVermogenAanvrager */, label: 'Inkomsten uit vermogen' },
      { key: 'huurinkomsten' /* of huurinkomstenAanvrager */, label: 'Huurinkomsten' },
    ] : []),
  ];

  for (const veld of velden) {
    const bedrag = inkomenGegevens?.[veld.key] || 0;
    if (bedrag > 0) {
      items.push({
        label: `  ${veld.label}`,  // Twee spaties als inspringing
        waarde: formatBedrag(bedrag),
      });
    }
  }
}
```

### Aangepaste inkomen_items opbouw

```typescript
const inkomen_items: { label: string; waarde: string; is_totaal?: boolean }[] = [];

// Aanvrager hoofdinkomen
inkomen_items.push({
  label: `${naamAanvrager || 'Aanvrager'}${sterretjeAanvrager}`,
  waarde: formatBedrag(hoofdinkomenAanvrager),
});

// Overige inkomsten aanvrager
addOverigeInkomsten(inkomen_items, inkomenGegevens, 'Aanvrager');

// Partner (als niet-alleenstaand)
if (hasPartner) {
  inkomen_items.push({
    label: `${naamPartner || 'Partner'}${sterretjePartner}`,
    waarde: formatBedrag(hoofdinkomenPartner),
  });

  // Overige inkomsten partner
  addOverigeInkomsten(inkomen_items, inkomenGegevens, 'Partner');
}

// Totaal inkomen (inclusief alle overige inkomsten)
// LET OP: Het totaalbedrag moet alle inkomsten bevatten, niet alleen de hoofdinkomens.
const totaalInkomen = (hoofdinkomenAanvrager || 0)
  + (hoofdinkomenPartner || 0)
  + (inkomenGegevens?.lijfrenteAanvrager || 0)
  + (inkomenGegevens?.partneralimentatieOntvangenAanvrager || 0)
  + (inkomenGegevens?.inkomstenUitVermogen || 0)
  + (inkomenGegevens?.huurinkomsten || 0)
  + (hasPartner ? (inkomenGegevens?.lijfrentePartner || 0) : 0)
  + (hasPartner ? (inkomenGegevens?.partneralimentatieOntvangenPartner || 0) : 0);

inkomen_items.push({
  label: 'Totaal inkomen',
  waarde: formatBedrag(totaalInkomen),
  is_totaal: true,
});
```

**Belangrijk:** Zoek de daadwerkelijke property-namen op in de bestaande TypeScript types (bijv. `AankoopInvoer`, `InkomenGegevens` of vergelijkbaar). De bovenstaande namen (`lijfrenteAanvrager`, `partneralimentatieOntvangenAanvrager`, etc.) zijn voorbeelden. De werkelijke namen kunnen afwijken.

**Tip:** Kijk naar hoe de stap "Haalbaarheid" (Stap 2) de overige inkomsten al uitleest — dezelfde velden moeten hier worden hergebruikt.

---

## Belangrijk

- Dit is een **frontend-only** wijziging. De backend (PDF template) rendert al een generieke `inkomen_items[]` array en hoeft niet aangepast te worden.
- De `formatBedrag` functie wordt al gebruikt voor bedragnotatie — hergebruik deze.
- De overige inkomsten worden alleen getoond als ze > 0 zijn. Bij 0 of leeg worden ze weggelaten.
- De sub-item labels starten met twee spaties (`"  Lijfrente"`) zodat ze visueel inspringen in de PDF.

---

## Verificatie

| # | Check | Verwacht resultaat |
|---|-------|--------------------|
| 1 | Onderpand met marktwaarde € 635.000 en WOZ € 580.000 | Beide waarden apart getoond |
| 2 | Onderpand zonder WOZ-waarde | Alleen marktwaarde getoond, WOZ-rij verborgen |
| 3 | Samenvatting zonder overige inkomsten | Alleen hoofdinkomen + totaal (geen extra rijen) |
| 4 | Aanvrager met lijfrente € 5.000 | Extra rij "  Lijfrente  € 5.000" onder aanvrager |
| 5 | Partner met partneralimentatie € 3.600 | Extra rij "  Partneralimentatie  € 3.600" onder partner |
| 6 | Totaal inkomen klopt | Totaal = hoofdinkomen + alle overige inkomsten |
| 7 | PDF downloaden | Onderpand + overige inkomsten correct in PDF |
| 8 | E-mail samenvatting | Alles ook correct in e-mail PDF bijlage |

---

## Samenvatting

| Onderdeel | Wijziging |
|-----------|-----------|
| **Wijzig:** Onderpanden data-mapping | Stuur `marktwaarde` en `woz_waarde` als aparte velden |
| **Wijzig:** `buildHaalbaarheidData` (of vergelijkbare functie) | Voeg overige inkomsten toe aan `inkomen_items[]` array |
| **Hergebruik:** `formatBedrag` | Bedragnotatie |
| **Hergebruik:** Bestaande `inkomenGegevens` properties | Dezelfde velden als Stap 2 (Haalbaarheid) |
| **Geen wijziging:** Backend / PDF template | Backend is al aangepast voor beide velden |

**Risico:** Laag. Bestaande functionaliteit blijft intact.
