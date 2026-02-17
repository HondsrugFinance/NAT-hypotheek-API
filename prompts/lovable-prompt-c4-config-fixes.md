# Lovable Prompt — 3 Config Fixes (AOW, Woonquotes, Overdrachtsbelasting)

> Kopieer deze prompt in Lovable om drie kritieke bugs te fixen.

---

## Fix 1: AOW-bedrag discrepantie

In `src/hooks/useAOWData.ts` staat een **foutief** fallback-bedrag voor AOW samenwonend.

### Probleem

Er staat `14379` als fallback, maar het correcte bedrag is `14342` (conform de API).

### Oplossing

Zoek in `useAOWData.ts` naar alle voorkomens van `14379` en vervang ze door `14342`.

Dit zijn de regels (kan licht afwijken):
- Rond regel 80: fallback bedrag bij API-response
- Rond regel 95: fallback bedrag bij API-fout

```typescript
// FOUT:
samenwonend: 14379
// GOED:
samenwonend: 14342
```

Controleer ook of `aanvraagStorage.ts` al `14342` gebruikt — dat is correct en moet ongewijzigd blijven.

---

## Fix 2: Woonquote-tabel ophalen uit API

De functie `bepaalWoonquote()` in `src/utils/berekeningen.ts` heeft alle staffels, correctiefactoren en minima **hardcoded**. Deze waarden zijn nu beschikbaar via de API.

### API response

`GET https://nat-hypotheek-api.onrender.com/config/fiscaal-frontend` bevat nu een `woonquote_tabel` sectie:

```json
{
  "woonquote_tabel": {
    "toelichting": "NAT 2026 woonquote staffels...",
    "staffels": [
      { "grens": 0, "quote": 0.216 },
      { "grens": 25000, "quote": 0.22 },
      { "grens": 35000, "quote": 0.24 },
      { "grens": 45000, "quote": 0.26 },
      { "grens": 55000, "quote": 0.28 },
      { "grens": 65000, "quote": 0.29 },
      { "grens": 75000, "quote": 0.30 },
      { "grens": 85000, "quote": 0.31 },
      { "grens": 100000, "quote": 0.32 }
    ],
    "rentecorrectie_basis": 4.5,
    "rentecorrectie_factor": 0.005,
    "box3_reductie": 0.062,
    "box3_minimum": 0.10,
    "box1_minimum": 0.15
  }
}
```

### Wat moet er veranderen

1. De `useNatConfig()` hook haalt `fiscaal-frontend` al op. Breid het TypeScript type `NatConfig` uit met het `woonquote_tabel` veld:

```typescript
interface WoonquoteStaffel {
  grens: number;
  quote: number;
}

interface WoonquoteTabel {
  staffels: WoonquoteStaffel[];
  rentecorrectie_basis: number;
  rentecorrectie_factor: number;
  box3_reductie: number;
  box3_minimum: number;
  box1_minimum: number;
}
```

2. Voeg het `woonquote_tabel` veld toe aan het config type (optioneel, met fallback):

```typescript
woonquote_tabel?: WoonquoteTabel;
```

3. Pas `bepaalWoonquote()` in `berekeningen.ts` aan om de tabel als parameter te accepteren:

```typescript
function bepaalWoonquote(
  toetsinkomen: number,
  toetsrente: number,
  isBox3: boolean = false,
  tabel?: WoonquoteTabel
): number {
  // Fallback naar hardcoded waarden als tabel niet beschikbaar
  const staffels = tabel?.staffels || [
    { grens: 0, quote: 0.216 },
    { grens: 25000, quote: 0.22 },
    { grens: 35000, quote: 0.24 },
    { grens: 45000, quote: 0.26 },
    { grens: 55000, quote: 0.28 },
    { grens: 65000, quote: 0.29 },
    { grens: 75000, quote: 0.30 },
    { grens: 85000, quote: 0.31 },
    { grens: 100000, quote: 0.32 },
  ];

  const rentecorrectieBasis = tabel?.rentecorrectie_basis ?? 4.5;
  const rentecorrectieFactor = tabel?.rentecorrectie_factor ?? 0.005;
  const box3Reductie = tabel?.box3_reductie ?? 0.062;
  const box3Minimum = tabel?.box3_minimum ?? 0.10;
  const box1Minimum = tabel?.box1_minimum ?? 0.15;

  // Bepaal basisquote op basis van inkomensstaffels
  let basisQuote = staffels[0].quote;
  for (const staffel of staffels) {
    if (toetsinkomen > staffel.grens) {
      basisQuote = staffel.quote;
    }
  }

  // Correctie voor toetsrente (hogere rente = lagere quote)
  const rentecorrectie = Math.max(0, (toetsrente - rentecorrectieBasis) * rentecorrectieFactor);

  // Box 3 heeft lagere quote
  if (isBox3) {
    return Math.max(box3Minimum, basisQuote - box3Reductie - rentecorrectie);
  }

  return Math.max(box1Minimum, basisQuote - rentecorrectie);
}
```

4. Op elke plek waar `bepaalWoonquote()` wordt aangeroepen (4-6 plekken in `berekeningen.ts`), geef de `woonquote_tabel` mee vanuit de fiscale parameters:

```typescript
// Voorbeeld — bij elke aanroep:
const woonquoteBox1 = bepaalWoonquote(totaalInkomen, toetsrente, false, params.woonquote_tabel);
const woonquoteBox3 = bepaalWoonquote(totaalInkomen, toetsrente, true, params.woonquote_tabel);
```

Dit vereist dat `params` (de fiscale parameters) het `woonquote_tabel` veld bevat. Controleer dat de functies die `bepaalWoonquote` aanroepen toegang hebben tot de config.

---

## Fix 3: Overdrachtsbelasting dropdown uit API halen

De overdrachtsbelasting dropdown-opties staan hardcoded in **twee** bestanden. De API biedt deze al aan via `GET /config/dropdowns` → `woning.overdrachtsbelasting_opties`.

### Probleem

Hardcoded arrays in:
- `src/components/aanvraag/sections/FinancieringsopzetSection.tsx` (rond regel 39-48)
- `src/pages/Aankoop.tsx` (rond regel 470-476)

Beide bevatten iets als:
```typescript
const ODB_OPTIES = [
  { value: 0.104, label: "10,4%" },
  { value: 0.10, label: "10%" },
  { value: 0.02, label: "2%" },
  { value: 0.08, label: "8%" },
];
```

### Oplossing

1. De `useNatConfig()` hook haalt `dropdowns` al op. De API response bevat:

```json
{
  "woning": {
    "overdrachtsbelasting_opties": [
      { "value": 0, "label": "0%" },
      { "value": 0.02, "label": "2%" },
      { "value": 0.08, "label": "8%" },
      { "value": 0.104, "label": "10,4%" }
    ]
  }
}
```

2. Gebruik in **beide** bestanden de API-data met een fallback:

```typescript
// In de component:
const { config } = useNatConfig();

const overdrachtsbelastingOpties = config?.dropdowns?.woning?.overdrachtsbelasting_opties || [
  { value: 0, label: "0%" },
  { value: 0.02, label: "2%" },
  { value: 0.08, label: "8%" },
  { value: 0.104, label: "10,4%" },
];
```

3. Vervang de hardcoded array door `overdrachtsbelastingOpties` in de `<Select>` of dropdown component.

4. **Verwijder** de hardcoded `ODB_OPTIES` (of vergelijkbare) constante uit beide bestanden.

---

## Verificatie

| # | Check | Verwacht resultaat |
|---|-------|--------------------|
| 1 | Zoek in hele codebase op `14379` | Geen resultaten meer |
| 2 | Open Haalbaarheid → vul inkomen in → woonquote verschijnt | Zelfde percentages als voorheen |
| 3 | Open Financieringsopzet → overdrachtsbelasting dropdown | Opties: 0%, 2%, 8%, 10,4% (uit API) |
| 4 | Open Aankoop pagina → overdrachtsbelasting dropdown | Zelfde opties als Financieringsopzet |
| 5 | API offline simuleren (bijv. nep-URL) | Fallback-waarden worden gebruikt, geen crash |

---

## Samenvatting

| Bestand | Wijziging |
|---------|-----------|
| `src/hooks/useAOWData.ts` | `14379` → `14342` (2 plekken) |
| `src/utils/berekeningen.ts` | `bepaalWoonquote()` accepteert API-tabel als parameter |
| `src/hooks/useNatConfig.ts` | Type uitbreiden met `WoonquoteTabel` |
| `src/components/aanvraag/sections/FinancieringsopzetSection.tsx` | ODB dropdown uit API |
| `src/pages/Aankoop.tsx` | ODB dropdown uit API |
