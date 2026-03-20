# L4 — Onderpand Lookup: gecombineerde Calcasa + WOZ + Energielabel opvraging

## Context

We hebben een nieuw gecombineerd API endpoint op de NAT API backend:

```
POST /onderpand/lookup
Content-Type: application/json

{ "postcode": "9472VM", "huisnummer": 33 }
→ {
    "adres": {
      "straat": "de Langakkers",
      "huisnummer": 33,
      "toevoeging": null,
      "postcode": "9472VM",
      "plaats": "Zuidlaren"
    },
    "calcasa": {
      "modelwaarde": 939000,
      "error": null
    },
    "woz": {
      "waarde": 425000,
      "peildatum": "2024-01-01",
      "error": null
    },
    "energielabel": {
      "labelklasse": "A",
      "labelklasse_config": "A,B",
      "registratiedatum": "2024-03-15",
      "geldig_tot": null,
      "bouwjaar": 2005,
      "error": null
    }
  }
```

Met optionele toevoeging:
```
{ "postcode": "1017PT", "huisnummer": 4, "toevoeging": "H" }
```

Elke bron kan onafhankelijk falen — dan bevat die bron `null` waarden + een `error` string:
```json
{
  "calcasa": { "modelwaarde": null, "error": "Confidence Level te laag" },
  "woz": { "waarde": 425000, "peildatum": "2024-01-01", "error": null },
  "energielabel": { "labelklasse": "geen_label", "labelklasse_config": "Geen (geldig) Label", "error": "Geen energielabel gevonden voor ..." }
}
```

De API URL is geconfigureerd in `src/config/apiConfig.ts` als `API_CONFIG.NAT_API_URL`.

---

## Wat moet er gebeuren

### Verwijderen

Verwijder de volgende bestaande losse lookup-knoppen (als ze bestaan):
- Calculator-icoon achter Marktwaarde (CalcasaModelwaardePopover)
- Vergrootglas achter Energielabel dropdown (EnergielabelPopover)
- Calculator/icoon achter WOZ-waarde

### Toevoegen

Voeg **één vergrootglas-icoon** (Search icon uit Lucide) toe in de **CardHeader** naast de titel "Onderpand". Bij klikken opent een **Dialog** waarmee de gebruiker postcode + huisnummer + toevoeging invult en alle drie de waardes tegelijk ophaalt.

Na ophalen toont de dialog de resultaten met per stuk een **checkbox** (default aangevinkt als er een waarde is). De gebruiker klikt "Overnemen" om de geselecteerde waarden in het formulier over te nemen.

---

## Stap 1 — OnderpandLookupDialog component

Maak een nieuw bestand: `src/components/aanvraag/OnderpandLookupDialog.tsx`

### Props

```typescript
interface OnderpandLookupDialogProps {
  /** Callback met de waarden die overgenomen moeten worden */
  onOvernemen: (waarden: {
    marktwaarde?: number;
    marktwaardeVastgesteldMet?: string;
    wozWaarde?: number;
    energielabel?: string;
    afgiftedatumEnergielabel?: string;
  }) => void;
  /** Pre-filled postcode (uit onderpand-adresgegevens) */
  defaultPostcode?: string;
  /** Pre-filled huisnummer */
  defaultHuisnummer?: string;
  /** Pre-filled toevoeging */
  defaultToevoeging?: string;
}
```

### UI structuur

```
[🔍 icoon] ← in CardHeader naast "Onderpand" titel

Dialog content (max-w-md):
┌─────────────────────────────────────────────────┐
│  Onderpand opzoeken                             │
│                                                 │
│  Postcode      Huisnummer     Toevoeging        │
│  [9472VM_]     [33____]       [_______]         │
│                                                 │
│  [Opzoeken]                                     │
│                                                 │
│  ── Resultaten ──                               │
│  de Langakkers 33, Zuidlaren                    │
│                                                 │
│  ☑ Marktwaarde (Calcasa)      € 939.000         │
│  ☑ WOZ-waarde (2024)          € 425.000         │
│  ☑ Energielabel               A                 │
│                                                 │
│  [Overnemen]                                    │
└─────────────────────────────────────────────────┘

Bij geen energielabel gevonden:
┌─────────────────────────────────────────────────┐
│  ...                                            │
│  ── Resultaten ──                               │
│  Hofakkers 14, Zuidlaren                        │
│                                                 │
│  ☑ Marktwaarde (Calcasa)      € 588.000         │
│  ☑ WOZ-waarde (2025)          € 536.000         │
│  ☑ Energielabel               Geen (geldig) label│
│                                                 │
│  [Overnemen]                                    │
└─────────────────────────────────────────────────┘

Bij Calcasa fout:
┌─────────────────────────────────────────────────┐
│  ...                                            │
│  ☐ Marktwaarde (Calcasa)      ⚠ Niet beschikbaar│
│     "Confidence Level te laag"                  │
│  ☑ WOZ-waarde (2024)          € 425.000         │
│  ☑ Energielabel               Geen (geldig) label│
│                                                 │
│  [Overnemen]                                    │
└─────────────────────────────────────────────────┘
```

### State

```typescript
const [open, setOpen] = useState(false);
const [postcode, setPostcode] = useState(defaultPostcode || '');
const [huisnummer, setHuisnummer] = useState(defaultHuisnummer || '');
const [toevoeging, setToevoeging] = useState(defaultToevoeging || '');
const [loading, setLoading] = useState(false);
const [result, setResult] = useState<{
  adres?: { straat: string; huisnummer: number; toevoeging?: string | null; postcode: string; plaats: string };
  calcasa: { modelwaarde: number | null; error: string | null };
  woz: { waarde: number | null; peildatum: string | null; error: string | null };
  energielabel: { labelklasse: string | null; labelklasse_config: string | null; registratiedatum: string | null; geldig_tot: string | null; bouwjaar: number | null; error: string | null };
} | null>(null);

// Checkboxes — default aan als waarde beschikbaar
const [selectCalcasa, setSelectCalcasa] = useState(true);
const [selectWoz, setSelectWoz] = useState(true);
const [selectEnergie, setSelectEnergie] = useState(true);
```

Wanneer `result` verandert, reset de checkboxes:
```typescript
useEffect(() => {
  if (result) {
    setSelectCalcasa(result.calcasa.modelwaarde !== null);
    setSelectWoz(result.woz.waarde !== null);
    // labelklasse is altijd gevuld (ook 'geen_label' bij niet-gevonden) → altijd overnemen
    setSelectEnergie(result.energielabel.labelklasse !== null);
  }
}, [result]);
```

### Sync defaults wanneer dialog opent

```typescript
useEffect(() => {
  if (open) {
    setPostcode(defaultPostcode || '');
    setHuisnummer(defaultHuisnummer || '');
    setToevoeging(defaultToevoeging || '');
    setResult(null);
  }
}, [open, defaultPostcode, defaultHuisnummer, defaultToevoeging]);
```

### API call

```typescript
const opzoeken = async () => {
  const cleanPostcode = postcode.replace(/\s/g, '').toUpperCase();
  if (!cleanPostcode || !huisnummer) return;

  setLoading(true);
  setResult(null);

  try {
    const body: Record<string, unknown> = {
      postcode: cleanPostcode,
      huisnummer: parseInt(huisnummer, 10),
    };
    if (toevoeging.trim()) {
      body.toevoeging = toevoeging.trim();
    }

    const response = await fetch(
      `${API_CONFIG.NAT_API_URL}/onderpand/lookup`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }
    );

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      toast.error(err.detail || 'Opzoeken mislukt');
      return;
    }

    const data = await response.json();
    setResult(data);
  } catch (e) {
    toast.error('Verbinding met server mislukt');
  } finally {
    setLoading(false);
  }
};
```

### Overnemen handler

```typescript
const handleOvernemen = () => {
  if (!result) return;

  const waarden: Parameters<typeof onOvernemen>[0] = {};

  if (selectCalcasa && result.calcasa.modelwaarde !== null) {
    waarden.marktwaarde = result.calcasa.modelwaarde;
    waarden.marktwaardeVastgesteldMet = 'desktoptaxatie';
  }

  if (selectWoz && result.woz.waarde !== null) {
    waarden.wozWaarde = result.woz.waarde;
  }

  if (selectEnergie && result.energielabel.labelklasse) {
    // labelklasse bevat de dropdown-value: 'A', 'B', ..., 'geen_label'
    waarden.energielabel = result.energielabel.labelklasse;
    if (result.energielabel.registratiedatum) {
      waarden.afgiftedatumEnergielabel = result.energielabel.registratiedatum;
    }
  }

  onOvernemen(waarden);
  setOpen(false);

  // Feedback
  const overgenomen = [];
  if (waarden.marktwaarde) overgenomen.push('marktwaarde');
  if (waarden.wozWaarde) overgenomen.push('WOZ');
  if (waarden.energielabel) overgenomen.push('energielabel');
  if (overgenomen.length > 0) {
    toast.success(`${overgenomen.join(', ')} overgenomen`);
  }
};
```

### Resultaat weergave

Elke bron als een rij met checkbox + label + waarde of foutmelding:

```tsx
{result && (
  <div className="space-y-4 mt-4">
    <Separator />

    {/* Adres */}
    <p className="text-sm font-medium">
      {result.adres?.straat} {result.adres?.huisnummer}
      {result.adres?.toevoeging || ''}, {result.adres?.plaats}
    </p>

    {/* Calcasa — Marktwaarde */}
    <div className="flex items-start gap-3">
      <Checkbox
        checked={selectCalcasa}
        onCheckedChange={(v) => setSelectCalcasa(!!v)}
        disabled={result.calcasa.modelwaarde === null}
      />
      <div className="flex-1">
        <div className="flex justify-between items-center">
          <span className="text-sm font-medium">Marktwaarde (Calcasa)</span>
          {result.calcasa.modelwaarde !== null ? (
            <span className="text-sm font-semibold text-primary">
              {formatBedrag(result.calcasa.modelwaarde)}
            </span>
          ) : (
            <span className="text-sm text-muted-foreground flex items-center gap-1">
              <AlertTriangle className="h-3.5 w-3.5" /> Niet beschikbaar
            </span>
          )}
        </div>
        {result.calcasa.error && (
          <p className="text-xs text-muted-foreground mt-0.5">{result.calcasa.error}</p>
        )}
      </div>
    </div>

    {/* WOZ */}
    <div className="flex items-start gap-3">
      <Checkbox
        checked={selectWoz}
        onCheckedChange={(v) => setSelectWoz(!!v)}
        disabled={result.woz.waarde === null}
      />
      <div className="flex-1">
        <div className="flex justify-between items-center">
          <span className="text-sm font-medium">
            WOZ-waarde{result.woz.peildatum ? ` (${result.woz.peildatum.substring(0, 4)})` : ''}
          </span>
          {result.woz.waarde !== null ? (
            <span className="text-sm font-semibold text-primary">
              {formatBedrag(result.woz.waarde)}
            </span>
          ) : (
            <span className="text-sm text-muted-foreground flex items-center gap-1">
              <AlertTriangle className="h-3.5 w-3.5" /> Niet beschikbaar
            </span>
          )}
        </div>
        {result.woz.error && (
          <p className="text-xs text-muted-foreground mt-0.5">{result.woz.error}</p>
        )}
      </div>
    </div>

    {/* Energielabel */}
    <div className="flex items-start gap-3">
      <Checkbox
        checked={selectEnergie}
        onCheckedChange={(v) => setSelectEnergie(!!v)}
        disabled={result.energielabel.labelklasse === null}
      />
      <div className="flex-1">
        <div className="flex justify-between items-center">
          <span className="text-sm font-medium">Energielabel</span>
          {result.energielabel.labelklasse !== null ? (
            <span className="text-sm font-semibold text-primary">
              {result.energielabel.labelklasse === 'geen_label'
                ? 'Geen (geldig) label'
                : result.energielabel.labelklasse}
              {result.energielabel.bouwjaar ? ` (bouwjaar ${result.energielabel.bouwjaar})` : ''}
            </span>
          ) : (
            <span className="text-sm text-muted-foreground flex items-center gap-1">
              <AlertTriangle className="h-3.5 w-3.5" /> Niet beschikbaar
            </span>
          )}
        </div>
        {result.energielabel.error && result.energielabel.labelklasse !== 'geen_label' && (
          <p className="text-xs text-muted-foreground mt-0.5">{result.energielabel.error}</p>
        )}
      </div>
    </div>

    <Separator />

    {/* Overnemen knop */}
    <Button
      className="w-full"
      onClick={handleOvernemen}
      disabled={!selectCalcasa && !selectWoz && !selectEnergie}
    >
      Overnemen
    </Button>
  </div>
)}
```

### Adres formatting helper

```typescript
const formatBedrag = (n: number) =>
  `€ ${n.toLocaleString('nl-NL', { maximumFractionDigits: 0 })}`;
```

Gebruik eventueel de bestaande `formatBedrag` helper als die al beschikbaar is in het project.

### Gedrag

- `Enter` in huisnummer-veld of toevoeging-veld triggert opzoeken
- Dialog sluit na "Overnemen"
- Bij opnieuw openen: result wissen, velden opnieuw vullen vanuit defaults
- "Opzoeken" knop is disabled als postcode of huisnummer leeg is
- "Overnemen" knop is disabled als geen enkele checkbox is aangevinkt
- Alle drie de bronnen worden parallel opgehaald (server-side), dus de response komt in één keer

---

## Stap 2 — Integratie in OnderpandSection.tsx

### Import toevoegen

```typescript
import { OnderpandLookupDialog } from '../OnderpandLookupDialog';
```

### CardHeader aanpassen — Aankoop flows

Zoek de CardHeader voor de aankoop-flow (rond regel 838):

```tsx
<CardHeader>
  <CardTitle className="text-base">Onderpand</CardTitle>
</CardHeader>
```

Wijzig naar:

```tsx
<CardHeader className="flex flex-row items-center justify-between">
  <CardTitle className="text-base">Onderpand</CardTitle>
  <OnderpandLookupDialog
    onOvernemen={(waarden) => updateOnderpand(waarden as any)}
    defaultPostcode={onderpand.postcode}
    defaultHuisnummer={onderpand.huisnummer}
    defaultToevoeging={onderpand.toevoeging}
  />
</CardHeader>
```

### CardHeader aanpassen — Verhogen/Oversluiten/Uitkopen flows

Zoek de CardHeader voor de verhogen-like flow (rond regel 484):

```tsx
<CardHeader>
  <CardTitle className="text-base">Onderpand</CardTitle>
</CardHeader>
```

Wijzig ook deze naar hetzelfde patroon (met dezelfde OnderpandLookupDialog). Let op: hier komen de defaults mogelijk vanuit de geselecteerde woning:

```tsx
<CardHeader className="flex flex-row items-center justify-between">
  <CardTitle className="text-base">Onderpand</CardTitle>
  <OnderpandLookupDialog
    onOvernemen={(waarden) => updateOnderpand(waarden as any)}
    defaultPostcode={onderpand.postcode || selectedWoning?.postcode || ''}
    defaultHuisnummer={onderpand.huisnummer || selectedWoning?.huisnummer || ''}
    defaultToevoeging={onderpand.toevoeging || selectedWoning?.toevoeging || ''}
  />
</CardHeader>
```

### Verwijder losse lookup-knoppen

Als er nog losse CalcasaModelwaardePopover of EnergielabelPopover componenten in OnderpandSection staan, verwijder deze (inclusief hun imports). De gecombineerde dialog vervangt ze.

---

## Stap 3 — OnderpandLookupDialog: trigger-knop

De trigger is een Button met Search-icoon, **buiten** de Dialog trigger (gebruik `open` + `onOpenChange`):

```tsx
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Search, Loader2, AlertTriangle } from 'lucide-react';
import { Checkbox } from '@/components/ui/checkbox';
import { Separator } from '@/components/ui/separator';

export function OnderpandLookupDialog({ onOvernemen, defaultPostcode, defaultHuisnummer, defaultToevoeging }: OnderpandLookupDialogProps) {
  // ... state ...

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="icon" className="h-8 w-8" title="Onderpand opzoeken">
          <Search className="h-4 w-4" />
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Onderpand opzoeken</DialogTitle>
        </DialogHeader>

        {/* Invoervelden */}
        <div className="grid grid-cols-3 gap-3">
          <div className="space-y-1">
            <Label className="text-xs">Postcode</Label>
            <Input
              value={postcode}
              placeholder="1234AB"
              onChange={(e) => setPostcode(e.target.value.toUpperCase())}
              onKeyDown={(e) => e.key === 'Enter' && opzoeken()}
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Huisnummer</Label>
            <Input
              value={huisnummer}
              placeholder="1"
              onChange={(e) => setHuisnummer(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && opzoeken()}
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Toevoeging</Label>
            <Input
              value={toevoeging}
              placeholder="A"
              onChange={(e) => setToevoeging(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && opzoeken()}
            />
          </div>
        </div>

        <Button
          onClick={opzoeken}
          disabled={!postcode || !huisnummer || loading}
          className="w-full"
        >
          {loading ? (
            <>
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              Opzoeken...
            </>
          ) : (
            'Opzoeken'
          )}
        </Button>

        {/* Resultaten */}
        {result && (
          /* ... resultaat weergave uit Stap 1 ... */
        )}
      </DialogContent>
    </Dialog>
  );
}
```

---

## Stap 4 — Styling

- **Search icoon:** `Search` uit `lucide-react`, in `Button variant="ghost" size="icon"` (h-8 w-8)
- **Dialog:** `max-w-md`
- **Checkbox:** shadcn/ui `Checkbox` component
- **Waarde tekst:** `text-sm font-semibold text-primary` (groen)
- **Foutmelding:** `text-xs text-muted-foreground` met `AlertTriangle` icoon
- **Laden:** `Loader2` icoon met `animate-spin`
- **"Overnemen" knop:** `Button className="w-full"` (default variant)
- **Disabled checkbox:** wanneer waarde `null` is (bron faalde)

---

## Verificatie

| # | Check | Verwacht |
|---|-------|----------|
| 1 | Klik op vergrootglas-icoon naast "Onderpand" titel | Dialog opent met postcode/huisnummer/toevoeging velden |
| 2 | Aankoop-flow met ingevuld adres | Postcode, huisnummer en toevoeging zijn vooraf ingevuld |
| 3 | Verhogen-flow met geselecteerde woning | Postcode en huisnummer vanuit woning-selectie |
| 4 | Vul 9472VM + 33 in, klik Opzoeken | Alle drie de resultaten verschijnen met waarden |
| 5 | Alle checkboxes staan default aan | ✅ |
| 6 | Vink "Marktwaarde" uit, klik Overnemen | Alleen WOZ en energielabel worden overgenomen |
| 7 | Bij geen energielabel gevonden | Checkbox staat AAN, toont "Geen (geldig) label" — wordt overgenomen in dropdown |
| 7b | Bij Calcasa fout (bijv. confidence te laag) | Checkbox is disabled, foutmelding getoond |
| 8 | Klik Overnemen | Dialog sluit, waarden in formulier, toast "marktwaarde, WOZ, energielabel overgenomen" |
| 9 | Marktwaarde overgenomen | `marktwaardeVastgesteldMet` = 'desktoptaxatie' |
| 10 | Energielabel overgenomen | Dropdown toont juiste label (via `labelklasse_config`), afgiftedatum ingevuld |
| 11 | WOZ-waarde overgenomen | WOZ-waarde veld bevat opgehaalde waarde |
| 12 | Enter in een invoerveld | Triggert opzoeken |
| 13 | Geen losse Calculator/Search iconen meer | Achter marktwaarde, energielabel en WOZ-waarde staan geen losse lookup-knoppen meer |

## Samenvatting bestanden

| Bestand | Actie |
|---------|-------|
| `src/components/aanvraag/OnderpandLookupDialog.tsx` | **Nieuw** — Dialog component met gecombineerde lookup |
| `src/components/aanvraag/sections/OnderpandSection.tsx` | **Wijzig** — Search-icoon in CardHeader (2-3 plekken), verwijder losse lookup-iconen |
| `src/components/aanvraag/CalcasaModelwaardePopover.tsx` | **Verwijder** (als bestand bestaat) |
| `src/components/aanvraag/EnergielabelPopover.tsx` | **Verwijder** (als bestand bestaat) |
