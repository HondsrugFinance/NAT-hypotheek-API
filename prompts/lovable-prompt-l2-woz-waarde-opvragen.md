# L2 — WOZ-waarde opvragen: rekenmachine-knop achter WOZ-waarde invoerveld

## Context

We hebben een nieuw API endpoint op de NAT API backend:

```
POST /woz/waarde
Content-Type: application/json

{ "postcode": "9472VM", "huisnummer": 33 }
→ {
    "adres": {
      "straat": "de Langakkers",
      "huisnummer": 33,
      "postcode": "9472VM",
      "woonplaats": "Zuidlaren",
      "grondoppervlakte": 587
    },
    "woz_waarden": [
      { "peildatum": "2025-01-01", "waarde": 895000 },
      { "peildatum": "2024-01-01", "waarde": 806000 },
      { "peildatum": "2023-01-01", "waarde": 636000 }
    ],
    "meest_recente_waarde": 895000,
    "meest_recente_peildatum": "2025-01-01",
    "wozobjectnummer": 173000011266
  }
```

Met optionele toevoeging:
```json
{ "postcode": "1017CT", "huisnummer": 263, "toevoeging": "H" }
```

Bij een fout (adres niet gevonden):
```json
HTTP 404
{ "detail": "Adres niet gevonden: 9999ZZ 999" }
```

De API URL is al geconfigureerd in `src/config/apiConfig.ts` als `API_CONFIG.NAT_API_URL`.

---

## Wat moet er gebeuren

Voeg een **rekenmachine-icoontje** (Calculator icon uit Lucide) toe achter het WOZ-waarde invoerveld op **twee plekken**:
1. `src/pages/Aankoop.tsx` — bij het WOZ-waarde blok (na de toggle)
2. `src/pages/Aanpassen.tsx` — bij het WOZ-waarde blok

Bij klikken opent een **Popover** (compact, net als bij Overbrugging/Overwaarde calculators) waarmee de gebruiker de WOZ-waarde kan opvragen bij het Kadaster.

---

## Stap 1 — WozWaardePopover component

Maak een nieuw bestand: `src/components/aanvraag/WozWaardePopover.tsx`

### Props

```typescript
interface WozWaardePopoverProps {
  /** Callback wanneer gebruiker "Waarde overnemen" klikt */
  onWaardeOvernemen: (waarde: number) => void;
  /** Pre-filled postcode (uit klantContactGegevens bij wijzigen) */
  defaultPostcode?: string;
  /** Pre-filled huisnummer */
  defaultHuisnummer?: string;
  /** Pre-filled toevoeging */
  defaultToevoeging?: string;
}
```

### UI structuur

```
[Calculator icoon] ← trigger knop (naast WOZ-waarde label, zelfde patroon als Overbrugging)

Popover content (w-80):
┌──────────────────────────────────────────┐
│  WOZ-waarde opvragen                     │
│                                          │
│  Postcode     Huisnr    Toevoeging       │
│  [______]     [____]    [___]            │
│                                          │
│  [Waarde opvragen]                       │
│                                          │
│  ── resultaat (na opvragen) ──           │
│                                          │
│  de Langakkers 33, Zuidlaren            │
│  WOZ-waarde: € 895.000            ✓     │
│  Peildatum: 1 januari 2025              │
│                                          │
│  [Waarde overnemen]                      │
│                                          │
│  óf bij fout:                            │
│  ⚠ Adres niet gevonden                  │
└──────────────────────────────────────────┘
```

### State

```typescript
const [postcode, setPostcode] = useState(defaultPostcode || '');
const [huisnummer, setHuisnummer] = useState(defaultHuisnummer || '');
const [toevoeging, setToevoeging] = useState(defaultToevoeging || '');
const [loading, setLoading] = useState(false);
const [open, setOpen] = useState(false);
const [result, setResult] = useState<{
  adres?: { straat: string; huisnummer: number; woonplaats: string; grondoppervlakte?: number };
  meest_recente_waarde?: number | null;
  meest_recente_peildatum?: string | null;
  woz_waarden?: { peildatum: string; waarde: number }[];
  error?: string;
} | null>(null);
```

### API call

```typescript
const opvragen = async () => {
  if (!postcode || !huisnummer) return;
  setLoading(true);
  setResult(null);

  try {
    const body: Record<string, unknown> = {
      postcode: postcode.replace(/\s/g, '').toUpperCase(),
      huisnummer: parseInt(huisnummer, 10),
    };
    if (toevoeging.trim()) {
      body.toevoeging = toevoeging.trim();
    }

    const response = await fetch(
      `${API_CONFIG.NAT_API_URL}/woz/waarde`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }
    );

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      setResult({ error: err.detail || 'Onbekende fout' });
      return;
    }

    const data = await response.json();
    setResult(data);
  } catch (e) {
    setResult({ error: 'Verbinding met WOZ Waardeloket mislukt' });
  } finally {
    setLoading(false);
  }
};
```

### Resultaat weergave

- **Laden:** Spinner (Loader2 met animate-spin) + "WOZ-waarde opvragen..."
- **Succes (meest_recente_waarde !== null):**
  - Adres tonen: `de Langakkers 33, Zuidlaren`
  - WOZ-waarde: `€ 895.000` in groen (text-primary), groot lettertype (text-xl font-semibold)
  - Peildatum: `Peildatum: 1 januari 2025` in text-sm text-muted-foreground
  - **Knop "Waarde overnemen"** (Button variant="default" className="w-full mt-3") → roept `onWaardeOvernemen(result.meest_recente_waarde)` aan + sluit popover + toast "WOZ-waarde overgenomen"
- **Fout:**
  - Waarschuwingsicoon (AlertTriangle) + foutmelding in text-sm text-muted-foreground
  - Geen "Waarde overnemen" knop

### Gedrag

- `Enter` in huisnummer-veld of toevoeging-veld triggert `opvragen`
- Popover sluit automatisch na "Waarde overnemen"
- Bij opnieuw openen: vorige resultaat wissen, postcode/huisnummer/toevoeging behouden
- Peildatum formatteren als Nederlandse datum: `2025-01-01` → `1 januari 2025`

### Peildatum formatteren

```typescript
const formatPeildatum = (datum: string): string => {
  const [jaar, maand] = datum.split('-');
  const maanden = ['januari', 'februari', 'maart', 'april', 'mei', 'juni',
    'juli', 'augustus', 'september', 'oktober', 'november', 'december'];
  return `1 ${maanden[parseInt(maand, 10) - 1]} ${jaar}`;
};
```

---

## Stap 2 — Integratie in Aankoop.tsx

Zoek het bestaande WOZ-waarde blok (rond regel 1030-1042):

```tsx
{/* Section 6: WOZ-waarde */}
<div className="px-6 pb-3 border-t pt-3">
  <div className="flex items-center justify-between mb-2">
    <p className="text-base font-semibold text-primary">WOZ-waarde</p>
    <Switch ... />
  </div>
  {ber.wozBekend && (
    <CurrencyInput value={ber.wozWaarde} onChange={...} />
  )}
</div>
```

Wijzig naar:

```tsx
{/* Section 6: WOZ-waarde */}
<div className="px-6 pb-3 border-t pt-3">
  <div className="flex items-center justify-between mb-2">
    <div className="flex items-center gap-2">
      <p className="text-base font-semibold text-primary">WOZ-waarde</p>
      <WozWaardePopover
        onWaardeOvernemen={(waarde) => updateBerekening(index, { wozBekend: true, wozWaarde: waarde })}
      />
    </div>
    <Switch
      checked={ber.wozBekend}
      onCheckedChange={(v) => updateBerekening(index, { wozBekend: v, wozWaarde: v ? ber.wozWaarde : 0 })}
    />
  </div>
  {ber.wozBekend && (
    <CurrencyInput value={ber.wozWaarde} onChange={(v) => updateBerekening(index, { wozWaarde: v })} />
  )}
</div>
```

**Let op:** Bij aankoop is er geen adres beschikbaar om te prefillen — de gebruiker moet postcode en huisnummer zelf invullen. De `onWaardeOvernemen` zet ook `wozBekend: true` zodat de toggle automatisch aan gaat.

---

## Stap 3 — Integratie in Aanpassen.tsx

Zoek het bestaande WOZ-waarde blok (rond regel 1015-1019):

```tsx
{/* WOZ-waarde */}
<div className="px-6 pb-3 border-t pt-3">
  <p className="text-base font-semibold text-primary mb-2">WOZ-waarde</p>
  <CurrencyInput value={ber.wozWaarde} onChange={(v) => updateWijzigingBerekening(index, { wozWaarde: v })} />
</div>
```

Wijzig naar:

```tsx
{/* WOZ-waarde */}
<div className="px-6 pb-3 border-t pt-3">
  <div className="flex items-center gap-2 mb-2">
    <p className="text-base font-semibold text-primary">WOZ-waarde</p>
    <WozWaardePopover
      onWaardeOvernemen={(waarde) => updateWijzigingBerekening(index, { wozWaarde: waarde })}
      defaultPostcode={klantContactGegevens?.aanvrager?.postcode}
      defaultHuisnummer={klantContactGegevens?.aanvrager?.huisnummer}
    />
  </div>
  <CurrencyInput value={ber.wozWaarde} onChange={(v) => updateWijzigingBerekening(index, { wozWaarde: v })} />
</div>
```

**Prefill logica:** Bij stroom "wijzigen hypotheek" is `klantContactGegevens` al beschikbaar (geladen uit het dossier). Het adres van de aanvrager (`klantContactGegevens.aanvrager.postcode` en `.huisnummer`) wordt als default meegegeven. Dit is het huidige woonadres — bij oversluiten/verhogen is dat het onderpand.

`klantContactGegevens` is al aanwezig als state variabele in `Aanpassen.tsx` (regel 174):
```typescript
const [klantContactGegevens, setKlantContactGegevens] = useState<DossierKlantGegevens | undefined>(undefined);
```

Het type `DossierKlantGegevens.aanvrager` is van type `ContactGegevens` met velden `postcode: string` en `huisnummer: string`.

---

## Stap 4 — Styling

Het popover-patroon volgt exact het bestaande Overbrugging/Overwaarde calculator patroon in `FinancieringsopzetSection.tsx`:

```tsx
// Trigger knop — zelfde stijl als bestaande calculators
<Popover open={open} onOpenChange={(v) => { setOpen(v); if (v) setResult(null); }}>
  <PopoverTrigger asChild>
    <Button variant="outline" size="icon" className="h-7 w-7">
      <Calculator className="h-4 w-4" />
    </Button>
  </PopoverTrigger>
  <PopoverContent className="w-80" align="end">
    {/* Popover content */}
  </PopoverContent>
</Popover>
```

- **Postcode veld:** `w-24`, placeholder "9472VM"
- **Huisnummer veld:** `w-16`, placeholder "33"
- **Toevoeging veld:** `w-14`, placeholder "A"
- **WOZ-waarde tekst:** `text-xl font-semibold text-primary` (groen)
- **Peildatum:** `text-sm text-muted-foreground`
- **"Waarde overnemen" knop:** `Button variant="default" className="w-full mt-3"`
- **"Waarde opvragen" knop:** `Button variant="outline" className="w-full mt-2"` met disabled wanneer loading of geen postcode/huisnummer
- **Foutmelding:** `text-sm text-muted-foreground` met `AlertTriangle` icoon (lucide-react)
- **Laden:** `Loader2` icoon met `animate-spin` + "WOZ-waarde opvragen..."

---

## Stap 5 — Import toevoegen

Voeg in **beide** bestanden (`Aankoop.tsx` en `Aanpassen.tsx`) de import toe:

```typescript
import { WozWaardePopover } from '@/components/aanvraag/WozWaardePopover';
```

Zorg dat in `WozWaardePopover.tsx` de benodigde imports staan:

```typescript
import { useState } from 'react';
import { Calculator, Loader2, AlertTriangle, Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { useToast } from '@/hooks/use-toast';
import { API_CONFIG } from '@/config/apiConfig';
```

---

## Verificatie

| # | Check | Verwacht |
|---|-------|----------|
| 1 | Aankoop stap 3: klik op calculator-icoon naast "WOZ-waarde" | Popover opent met lege postcode/huisnummer/toevoeging velden |
| 2 | Aanpassen stap 3: klik op calculator-icoon naast "WOZ-waarde" | Popover opent met postcode en huisnummer vooraf ingevuld uit dossier |
| 3 | Vul postcode 9472VM + huisnummer 33 in, klik "Waarde opvragen" | Toont: de Langakkers 33, Zuidlaren / € 895.000 / Peildatum: 1 januari 2025 |
| 4 | Klik "Waarde overnemen" | WOZ-waarde veld wordt € 895.000, popover sluit, toast "WOZ-waarde overgenomen" |
| 5 | Aankoop: "Waarde overnemen" bij uitgeschakelde toggle | Toggle gaat automatisch AAN + waarde wordt ingevuld |
| 6 | Vul ongeldig adres in (9999ZZ 999) | Toont foutmelding: "Adres niet gevonden" met waarschuwingsicoon |
| 7 | Enter in huisnummer-veld | Triggert "Waarde opvragen" |
| 8 | Opnieuw openen na eerdere lookup | Resultaat gewist, postcode/huisnummer behouden |

## Samenvatting bestanden

| Bestand | Actie |
|---------|-------|
| `src/components/aanvraag/WozWaardePopover.tsx` | **Nieuw** — Popover component met WOZ API call |
| `src/pages/Aankoop.tsx` | **Wijzig** — Calculator-icoon + WozWaardePopover bij WOZ-waarde blok (geen prefill) |
| `src/pages/Aanpassen.tsx` | **Wijzig** — Calculator-icoon + WozWaardePopover bij WOZ-waarde blok (prefill uit klantContactGegevens) |
