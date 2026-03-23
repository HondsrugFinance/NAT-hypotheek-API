# C4 — Hypotheekrentes beheren: admin matrix-editor + auto-fill formulier

## Context

We hebben twee nieuwe Supabase tabellen en backend endpoints voor hypotheekrentes.

### Supabase tabellen

**Voer deze SQL uit in Supabase SQL Editor** (het migratie-bestand staat klaar als `supabase/migrations/20260323_hypotheekrentes.sql` in de NAT API repo):

**`hypotheekrentes`** — Eén rij per tarievenblad-regel:
| Kolom | Type | Beschrijving |
|-------|------|-------------|
| `id` | uuid | PK |
| `geldverstrekker` | text | "ING", "ABN AMRO" etc. |
| `productlijn` | text | "Budget Hypotheek" etc. |
| `aflosvorm` | text | `annuitair`, `lineair`, `aflossingsvrij` |
| `rentevaste_periode` | integer | Jaren (0 = variabel) |
| `ltv_staffel` | jsonb | `{"NHG": 3.96, "55": 4.14, "65": 4.16, ...}` |
| `peildatum` | date | Datum waarop tarief geldt |
| `bron` | text | `handmatig`, `api`, `scraper` |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | |

LTV-staffel keys: `"NHG"` voor NHG-tarief, numerieke strings als drempelwaarden (`"55"` = ≤55%, `"100"` = ≤100%). Elke bank heeft een eigen set LTV-klassen (ING heeft 11, ABN AMRO heeft 5, Rabobank 4).

**`rente_kortingen`** — Kortingen/opslagen per geldverstrekker (energielabel, betaalrekening, etc.):
| Kolom | Type | Beschrijving |
|-------|------|-------------|
| `id` | uuid | PK |
| `geldverstrekker` | text | |
| `productlijn` | text | |
| `korting_type` | text | `energielabel`, `betaalrekening`, `duurzaamheid`, etc. |
| `staffel` | jsonb | `{"A++++": -0.20, "B": -0.12, ...}` |
| `omschrijving` | text | Vrije toelichting |
| `peildatum` | date | |

Elke geldverstrekker heeft z'n eigen kortingstypen en staffels. ING heeft een energielabel-tabel met 13 labels en een betaalrekeningkorting. ABN AMRO heeft een duurzaamheidskorting met 2 labels en een huisbankkorting. Etc.

### Backend endpoints (NAT API)

Alle endpoints forwarden het Authorization header (Supabase session token) zodat RLS werkt.

```
GET /rentes/lookup?geldverstrekker=ING&productlijn=Hypotheek&aflosvorm=annuitair
    &rentevaste_periode=10&ltv=80&energielabel=B
→ {
    "basis_rente": 4.19,
    "totale_korting": -0.12,
    "netto_rente": 4.07,
    "ltv_staffel": {"NHG": 3.96, "55": 4.14, ...},
    "kortingen": {
      "energielabel": {"staffel": {"A++++": -0.20, "B": -0.12, ...}},
      "betaalrekening": {"staffel": {"ja": -0.25, "nee": 0}}
    },
    "korting_details": [{"type": "energielabel", "label": "B", "korting": -0.12}],
    "peildatum": "2026-03-19"
  }

GET /rentes/tarieven?geldverstrekker=ING&productlijn=Hypotheek&aflosvorm=annuitair
→ {
    "aflosvormen": {
      "annuitair": [
        {"rentevaste_periode": 0, "ltv_staffel": {"NHG": 3.60, "55": 3.76, ...}, "peildatum": "2026-03-19"},
        {"rentevaste_periode": 1, "ltv_staffel": {"NHG": 3.60, ...}, ...},
        ...
      ]
    }
  }

GET /rentes/kortingen?geldverstrekker=ING&productlijn=Hypotheek
→ {
    "kortingen": [
      {"korting_type": "energielabel", "staffel": {"A++++": -0.20, "A": -0.20, "B": -0.12, "C": -0.06, "D": -0.03}, "omschrijving": "Energielabel rentecomponent"},
      {"korting_type": "betaalrekening", "staffel": {"ja": -0.25, "nee": 0}, "omschrijving": "Actieve Betaalrekening Korting"}
    ]
  }

POST /rentes/tarieven
{
  "geldverstrekker": "ING",
  "productlijn": "Hypotheek",
  "peildatum": "2026-03-19",
  "tarieven": [
    {"aflosvorm": "annuitair", "rentevaste_periode": 1, "ltv_staffel": {"NHG": 3.60, "55": 3.76, "65": 3.78}},
    {"aflosvorm": "annuitair", "rentevaste_periode": 5, "ltv_staffel": {"NHG": 3.90, "55": 3.94, ...}},
    ...
  ]
}

POST /rentes/kortingen
{
  "geldverstrekker": "ING",
  "productlijn": "Hypotheek",
  "peildatum": "2026-03-19",
  "kortingen": [
    {"korting_type": "energielabel", "staffel": {"A++++": -0.20, "A": -0.20, "B": -0.12, "C": -0.06}, "omschrijving": "Energielabel rentecomponent"},
    {"korting_type": "betaalrekening", "staffel": {"ja": -0.25, "nee": 0}, "omschrijving": "Actieve Betaalrekening Korting"}
  ]
}
```

De API URL is al geconfigureerd in `src/config/apiConfig.ts` als `API_CONFIG.NAT_API_URL`.
De geldverstrekkers en productlijnen zijn beschikbaar via `GET /config/geldverstrekkers`.

---

## Wat moet er gebeuren

Twee dingen:
1. **Admin pagina**: matrix-editor om rentes handmatig in te voeren/bewerken
2. **Auto-fill in formulier**: wanneer adviseur geldverstrekker/product/aflosvorm/periode kiest → rente automatisch invullen

---

## Deel 1: Admin pagina — Rentebeheer

### Navigatie

Voeg een nieuw menu-item toe in de admin-navigatie (naast de bestaande config-pagina's):
- Label: **"Rentebeheer"**
- Icoon: `Percent` (Lucide)
- Route: `/admin/rentes`
- Alleen zichtbaar voor admin-gebruikers

### Pagina layout

```
┌─────────────────────────────────────────────────────────┐
│  Rentebeheer                                            │
│                                                         │
│  Geldverstrekker: [▼ ING          ]                     │
│  Productlijn:     [▼ Hypotheek    ]                     │
│  Peildatum:       [19-03-2026     ]                     │
│                                                         │
│  ┌─ Tabs ─────────────────────────────────────────────┐ │
│  │ [Annuïtair] [Lineair] [Aflossingsvrij] [Kortingen] │ │
│  └────────────────────────────────────────────────────┘ │
│                                                         │
│  ┌─ Matrix (per aflosvorm-tab) ──────────────────────┐  │
│  │ Rentevast   NHG    ≤55%   ≤65%   ≤70%   ≤80%  ...│  │
│  │ ──────────  ─────  ─────  ─────  ─────  ─────     │  │
│  │ Variabel    3,60   3,76   3,78   3,85   3,87      │  │
│  │ 1 jaar      3,60   3,76   3,78   3,85   3,87      │  │
│  │ 2 jaar      3,61   3,77   3,79   3,86   3,88      │  │
│  │ 5 jaar      3,90   3,94   3,96   3,97   3,99      │  │
│  │ 10 jaar     3,96   4,14   4,16   4,17   4,19      │  │
│  │ 15 jaar     4,20   4,31   4,33   4,38   4,43      │  │
│  │ 20 jaar     4,28   4,41   4,44   4,51   4,53      │  │
│  │ ...                                               │  │
│  │                                                   │  │
│  │ [+ Periode toevoegen]  [+ LTV-kolom toevoegen]    │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  [Opslaan]                                              │
└─────────────────────────────────────────────────────────┘
```

### Selectie bovenaan

1. **Geldverstrekker dropdown** — gevuld vanuit `GET /config/geldverstrekkers` → `geldverstrekkers[]`
2. **Productlijn dropdown** — cascade: filtert op geselecteerde geldverstrekker → `productlijnen[geldverstrekker]`
3. **Peildatum** — date input, default vandaag

Bij wijzigen geldverstrekker of productlijn: laad bestaande tarieven via `GET /rentes/tarieven` en kortingen via `GET /rentes/kortingen`. Beide via de NAT API (niet direct Supabase), zodat de backend de meest recente peildatum selecteert.

### Matrix-editor (tabs Annuïtair / Lineair / Aflossingsvrij)

- **Rijen** = rentevaste periodes. Default: Variabel (0), 1, 2, 3, 5, 6, 7, 10, 12, 15, 20, 25, 30. Als de geladen data andere periodes bevat, voeg die automatisch toe.
- **Kolommen** = LTV-categorieën, **dynamisch** uit de data. Bij laden: neem de union van alle LTV-keys uit alle `ltv_staffel` objecten. Sorteer: `NHG` eerst, dan numeriek oplopend (`55`, `65`, `70`, ..., `100`), dan eventueel `106plus` als laatste.
- **Kolomheaders**: `NHG` blijft `NHG`. Numerieke keys tonen als `≤55%`, `≤65%`, etc. Key `106plus` toont als `>106%`.
- **Cellen** = rentepercentage, editable `<input type="number" step="0.01" className="w-20 h-7 text-sm text-center">`. Lege cel = niet beschikbaar voor deze combinatie.

**Kolommen bepalen bij laden:**
```typescript
// Union van alle LTV-keys uit alle ltv_staffel objecten
const allLtvKeys = new Set<string>();
for (const tarief of tarieven) {
  for (const key of Object.keys(tarief.ltv_staffel)) {
    allLtvKeys.add(key);
  }
}
// Sorteer: NHG eerst, dan numeriek
const ltvKolommen = sortLtvKeys([...allLtvKeys]);
```

**Bij lege matrix (nog geen data):**
Start met default LTV-kolommen: `["NHG", "55", "65", "70", "75", "80", "85", "90", "95", "100"]`. De adviseur kan kolommen toevoegen of verwijderen.

**"+ Periode toevoegen"**: Popover met number input (0-30). Voegt een lege rij toe.
**"+ LTV-kolom toevoegen"**: Popover met text input (bijv. "40" voor ≤40%, of "106plus" voor >106%). Voegt kolom toe aan alle rijen.
**Verwijderen**: Klein X-icoon op rij/kolom-header (met bevestiging). Verwijdert de hele rij of kolom.

### Kortingen tab

Andere layout — vrije key-value paren per korting_type:

```
┌─ Kortingen ──────────────────────────────────────────┐
│                                                       │
│ ┌─ energielabel ────────────────────────────────────┐ │
│ │ Omschrijving: [Energielabel rentecomponent       ]│ │
│ │                                                   │ │
│ │ A++++  [-0,20]     A+++  [-0,20]                 │ │
│ │ A++    [-0,20]     A+    [-0,20]                 │ │
│ │ A      [-0,20]     B     [-0,12]                 │ │
│ │ C      [-0,06]     D     [-0,03]                 │ │
│ │ E      [ 0,00]     F     [ 0,00]                 │ │
│ │ G      [ 0,00]                                   │ │
│ │                                                   │ │
│ │ [+ Label toevoegen]                [Verwijderen]  │ │
│ └───────────────────────────────────────────────────┘ │
│                                                       │
│ ┌─ betaalrekening ──────────────────────────────────┐ │
│ │ Omschrijving: [Actieve Betaalrekening Korting    ]│ │
│ │                                                   │ │
│ │ ja     [-0,25]     nee   [ 0,00]                 │ │
│ │                                                   │ │
│ │ [+ Optie toevoegen]                [Verwijderen]  │ │
│ └───────────────────────────────────────────────────┘ │
│                                                       │
│ [+ Nieuw kortingstype toevoegen]                      │
└───────────────────────────────────────────────────────┘
```

Elke korting is een **Card** met:
- **Titel** = `korting_type` (niet bewerkbaar na aanmaken)
- **Omschrijving** = text input
- **Staffel** = grid van key-value paren. Key = label (text), value = korting in procentpunten (number input, stap 0.01, negatief = korting, positief = opslag)
- **"+ Optie toevoegen"** knop
- **"Verwijderen"** knop (verwijdert hele korting, met bevestiging)

**"+ Nieuw kortingstype toevoegen"**: Popover met text input voor het type (bijv. "dagrente", "starterskorting", "verhuur"). Maakt een lege card aan.

### Opslaan

De **"Opslaan"** knop verzamelt:
1. Alle matrix-data van **alle drie** aflosvorm-tabs → `POST /rentes/tarieven`
2. Alle kortingen → `POST /rentes/kortingen`

Beide calls met dezelfde `peildatum` uit het datumveld bovenaan.

Gebruik `getApiHeaders()` of bouw headers handmatig met het Supabase session token in het Authorization header (zodat de backend het kan forwarden naar Supabase).

Toast feedback na succes: `"Tarieven opgeslagen voor {geldverstrekker} — {productlijn}"`.

### API communicatie

Alle data gaat via de **NAT API endpoints** (niet direct Supabase). De NAT API forwardt het session token naar Supabase voor RLS.

```typescript
const headers = {
  'Content-Type': 'application/json',
  'Authorization': `Bearer ${session.access_token}`,
};

// Laden
const resp = await fetch(
  `${API_CONFIG.NAT_API_URL}/rentes/tarieven?geldverstrekker=${encodeURIComponent(gv)}&productlijn=${encodeURIComponent(pl)}`,
  { headers }
);

// Opslaan
await fetch(`${API_CONFIG.NAT_API_URL}/rentes/tarieven`, {
  method: 'POST',
  headers,
  body: JSON.stringify({
    geldverstrekker: gv,
    productlijn: pl,
    peildatum: peildatum,
    tarieven: [
      { aflosvorm: 'annuitair', rentevaste_periode: 10, ltv_staffel: { "NHG": 3.96, "55": 4.14, ... } },
      ...
    ]
  })
});
```

### Styling

Gebruik het bestaande Hondsrug Finance design system:
- Card component voor de matrix en kortingen
- Tabs component (shadcn) voor aflosvormen + kortingen
- Input velden compact: `className="w-20 h-7 text-sm text-center"`
- Toast voor feedback
- Popover voor toevoegen (geen zware modals)

---

## Deel 2: Auto-fill rente in hypotheekformulier

### Waar

In het hypotheekformulier waar leningdelen worden ingevoerd (`SamenstellenSection.tsx` of vergelijkbaar). Wanneer de adviseur deze velden heeft ingevuld:
- **Geldverstrekker** + **Productlijn** (dropdowns)
- **Aflosvorm** (dropdown: Annuïteit, Lineair, Aflosvrij)
- **Rentevaste periode** (number input)

...en optioneel:
- **LTV** (berekend uit hypotheekbedrag / marktwaarde)
- **Energielabel** (uit onderpand sectie)

### Hook: `useRenteLookup.ts`

```typescript
import { useState, useCallback, useRef } from 'react';
import { API_CONFIG } from '@/config/apiConfig';
import { supabase } from '@/integrations/supabase/client';

interface RenteLookupResult {
  basis_rente: number;
  netto_rente: number;
  totale_korting: number;
  peildatum: string;
  korting_details: { type: string; label: string; korting: number }[];
}

export function useRenteLookup() {
  const [lookupResult, setLookupResult] = useState<RenteLookupResult | null>(null);
  const [loading, setLoading] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout>>();

  const lookup = useCallback(async (params: {
    geldverstrekker: string;
    productlijn: string;
    aflosvorm: string;         // "annuitair", "lineair", "aflossingsvrij"
    rentevaste_periode: number;
    ltv?: number;
    energielabel?: string;
  }) => {
    // Debounce 500ms
    if (timerRef.current) clearTimeout(timerRef.current);

    timerRef.current = setTimeout(async () => {
      if (!params.geldverstrekker || !params.productlijn || !params.aflosvorm || !params.rentevaste_periode) {
        setLookupResult(null);
        return;
      }

      setLoading(true);
      try {
        const { data: { session } } = await supabase.auth.getSession();
        const queryParams = new URLSearchParams({
          geldverstrekker: params.geldverstrekker,
          productlijn: params.productlijn,
          aflosvorm: params.aflosvorm,
          rentevaste_periode: String(params.rentevaste_periode),
        });
        if (params.ltv !== undefined) queryParams.set('ltv', String(params.ltv));
        if (params.energielabel) queryParams.set('energielabel', params.energielabel);

        const resp = await fetch(
          `${API_CONFIG.NAT_API_URL}/rentes/lookup?${queryParams}`,
          {
            headers: {
              'Authorization': `Bearer ${session?.access_token ?? ''}`,
            },
          }
        );

        if (resp.ok) {
          const data = await resp.json();
          if (data.basis_rente !== undefined) {
            setLookupResult({
              basis_rente: data.basis_rente,
              netto_rente: data.netto_rente,
              totale_korting: data.totale_korting,
              peildatum: data.peildatum,
              korting_details: data.korting_details || [],
            });
          } else {
            setLookupResult(null);
          }
        } else {
          setLookupResult(null);  // 404 = geen tarief, geen foutmelding
        }
      } catch {
        setLookupResult(null);  // Stil falen
      }
      setLoading(false);
    }, 500);
  }, []);

  const clear = useCallback(() => {
    setLookupResult(null);
    if (timerRef.current) clearTimeout(timerRef.current);
  }, []);

  return { lookup, lookupResult, loading, clear };
}
```

### Integratie in formulier

Per leningdeel: wanneer geldverstrekker + productlijn + aflosvorm + rentevaste periode allemaal ingevuld zijn, roep `lookup()` aan.

**Aflosvorm mapping** (UI-waarde → API-waarde):
```typescript
const aflosvormMap: Record<string, string> = {
  'Annuïteit': 'annuitair',
  'Lineair': 'lineair',
  'Aflosvrij': 'aflossingsvrij',
};
```

**Auto-fill gedrag:**
1. Alleen auto-fillen als het renteveld **leeg** is of eerder **auto-ingevuld** was
2. Als de adviseur de rente handmatig overschrijft → markeer als handmatig, stop auto-fill voor dat leningdeel
3. Bij wijziging van geldverstrekker/product/aflosvorm/periode → opnieuw auto-fillen (tenzij handmatig overschreven)

**Indicator onder renteveld:**
```tsx
{lookupResult && isAutoFilled && (
  <p className="text-xs text-muted-foreground mt-1">
    {lookupResult.totale_korting !== 0
      ? `${lookupResult.basis_rente.toFixed(2)}% basis ${lookupResult.korting_details.map(k =>
          `${k.korting > 0 ? '+' : ''}${k.korting.toFixed(2)}% ${k.type}`
        ).join(' ')} = ${lookupResult.netto_rente.toFixed(2)}%`
      : `Tarief per ${lookupResult.peildatum}`
    }
  </p>
)}
```

Voorbeeld output: `"4,19% basis −0,12% energielabel = 4,07%"` of simpelweg `"Tarief per 2026-03-19"`.

**Stille failure:** Als geen tarief gevonden (404) of API niet bereikbaar: doe niets, geen toast, geen foutmelding. Het renteveld blijft leeg of behoudt de handmatige waarde.

---

## Verificatie

| # | Check | Verwacht resultaat |
|---|-------|--------------------|
| 1 | Admin: selecteer ING + Hypotheek | Matrix laadt met LTV-kolommen uit data (of default kolommen als leeg) |
| 2 | Admin: vul rentes in matrix, klik Opslaan | Toast "Tarieven opgeslagen", data zichtbaar bij herladen |
| 3 | Admin: voeg LTV-kolom "40" toe | Nieuwe kolom `≤40%` verschijnt in matrix |
| 4 | Admin: voeg periode "4 jaar" toe | Nieuwe rij verschijnt |
| 5 | Admin: verwijder een kolom of rij | Na bevestiging verdwijnt kolom/rij |
| 6 | Admin: wissel tab naar Lineair | Aparte matrix voor lineaire tarieven |
| 7 | Admin: voeg energielabel-korting toe in Kortingen tab | Card verschijnt met invoervelden |
| 8 | Admin: wijzig geldverstrekker | Productlijn dropdown update, matrix laadt nieuwe data |
| 9 | Formulier: kies ING + Hypotheek + Annuïteit + 10 jaar | Rente wordt automatisch ingevuld als tarief bestaat |
| 10 | Formulier: wijzig energielabel in onderpand | Rente update automatisch met korting |
| 11 | Formulier: overschrijf rente handmatig | Indicator verdwijnt, geen auto-override meer |
| 12 | Formulier: geen tarief beschikbaar | Geen foutmelding, veld blijft leeg |
| 13 | Geen TypeScript compilatiefouten | `npm run build` slaagt |

## Samenvatting bestanden

| Bestand | Actie | Wijziging |
|---------|-------|-----------|
| Supabase SQL Editor | SQL | `hypotheekrentes` + `rente_kortingen` tabellen + RLS + triggers |
| Nieuw: `src/pages/admin/RenteBeheer.tsx` | Nieuw | Admin pagina met matrix-editor |
| Nieuw: `src/components/admin/RenteMatrix.tsx` | Nieuw | Editable matrix grid (per aflosvorm-tab) |
| Nieuw: `src/components/admin/KortingenEditor.tsx` | Nieuw | Kortingen editor (cards per korting_type) |
| Nieuw: `src/hooks/useRenteLookup.ts` | Nieuw | Hook voor auto-fill rente in formulier (debounced) |
| Wijzig: admin navigatie/routing | Wijzig | Menu-item "Rentebeheer" + route `/admin/rentes` |
| Wijzig: leningdeel invoer in formulier | Wijzig | Auto-fill integratie via `useRenteLookup` + indicator |
