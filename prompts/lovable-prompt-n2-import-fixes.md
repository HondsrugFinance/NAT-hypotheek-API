# N2 — Import op berekening- en aanvraag-niveau

## Context

De ImportBanner stond op dossier-niveau, maar de gebruiker wil bepalen waar gegevens naartoe gaan. De banner moet op **berekening-niveau** (Aankoop/Aanpassen) en **aanvraag-niveau** staan — niet op DossierDetail.

De API ondersteunt nu twee contexten via `?context=`:
- `?context=berekening` — alleen velden relevant voor de berekening (inkomen, naam, geboortedatum, onderpand, koopsom). Import gaat naar de pagina-state (`invoer`).
- `?context=aanvraag` — alle velden (klantgegevens, legitimatie, werkgever, inkomen, onderpand, pensioen, hypotheek, etc.). Import gaat naar `aanvragen.data` in Supabase.

Elke import-veld heeft nu een `target` pad dat aangeeft waar het in de datastructuur terecht komt.

### API Response (per veld)

```typescript
interface ImportVeld {
  veld: string;           // technische veldnaam
  label: string;          // Nederlandse leesbare naam
  categorie: string;      // groepering: Persoonsgegevens, Inkomen, Onderpand, etc.
  sectie: string;         // bron-document: werkgeversverklaring, paspoort, etc.
  persoon: 'aanvrager' | 'partner' | 'gezamenlijk';
  target: string;         // pad in de datastructuur (verschilt per context)
  value_type: string;     // "currency" | "date" | "number" | "text" | "boolean" | "percent"
  waarde_extractie: any;
  waarde_huidig: any;
  status: 'nieuw' | 'bevestigd' | 'afwijkend';
  confidence: number;
  bron_datum: string;
}
```

### Target paden per context

**Berekening** (`context=berekening`): target paden voor `invoer` structuur:
| Target prefix | Voorbeeld | Waar in invoer |
|---|---|---|
| `klantGegevens.X` | `klantGegevens.achternaamAanvrager` | `invoer.klantGegevens.achternaamAanvrager` |
| `inkomenGegevens.X` | `inkomenGegevens.hoofdinkomenAanvrager` | `invoer.inkomenGegevens.hoofdinkomenAanvrager` |
| `onderpand.X` | `onderpand.energielabel` | `invoer.haalbaarheidsBerekeningen[0].onderpand.energielabel` |
| `berekeningen.X` | `berekeningen.aankoopsomWoning` | `invoer.berekeningen[0].aankoopsomWoning` |

**Aanvraag** (`context=aanvraag`): target paden voor `AanvraagData` structuur — zie het bestaande `applyFieldToAanvraag()` uit N1.

---

## Wat moet er aangepast worden

### 1. Verwijder ImportBanner van DossierDetail.tsx

De banner op dossier-niveau verdwijnt. Optioneel: laat een subtiele tekstregel staan:

```tsx
{/* Was: <ImportBanner dossierId={...} /> */}
{/* Nu: alleen informatief */}
{documentenVerwerkt > 0 && (
  <p className="text-xs text-muted-foreground">
    {documentenVerwerkt} documenten verwerkt
  </p>
)}
```

### 2. Voeg ImportBanner toe aan Aankoop.tsx en Aanpassen.tsx

Op de berekening-pagina's verschijnt de banner met `context=berekening`.

**In Aankoop.tsx** (en vergelijkbaar in Aanpassen.tsx), voeg toe na de pagina-header:

```tsx
{dossierId && (
  <ImportBanner
    dossierId={dossierId}
    targetId={dossierId}  // voor berekening = dossier id
    context="berekening"
    onImported={(updates) => {
      // Merge updates in invoer state
      setInvoer(prev => applyBerekeningImports(prev, updates));
    }}
  />
)}
```

### 3. Voeg ImportBanner toe aan de aanvraag-pagina

Als de aanvraag-pagina bestaat (bijv. AanvraagDetail of vergelijkbaar), voeg daar de banner toe:

```tsx
{dossierId && aanvraagId && (
  <ImportBanner
    dossierId={dossierId}
    targetId={aanvraagId}  // voor aanvraag = aanvraag id
    context="aanvraag"
    onImported={() => {
      // Herlaad aanvraag data
      refetchAanvraag();
    }}
  />
)}
```

### 4. Hook: useAvailableImports.ts — context parameter

Update de hook om `context` door te geven:

```typescript
export function useAvailableImports(
  dossierId: string | undefined,
  targetId?: string,  // aanvraag_id of dossier_id (berekening)
  context: 'aanvraag' | 'berekening' = 'aanvraag'
) {
  const [data, setData] = useState<AvailableImports | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchData = useCallback(async () => {
    if (!dossierId) return;
    setLoading(true);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      const params = new URLSearchParams({ context });
      if (targetId) params.set('aanvraag_id', targetId);

      const resp = await window.fetch(
        `${API_CONFIG.NAT_API_URL}/doc-processing/${dossierId}/available-imports?${params}`,
        { headers: { 'Authorization': `Bearer ${session?.access_token ?? ''}` } }
      );

      if (resp.ok) {
        setData(await resp.json());
      }
    } catch { /* stil falen */ }
    setLoading(false);
  }, [dossierId, targetId, context]);

  useEffect(() => { fetchData(); }, [fetchData]);

  return { data, loading, refresh: fetchData };
}
```

### 5. ImportBanner.tsx — Props uitbreiden

```tsx
interface ImportBannerProps {
  dossierId: string;
  targetId?: string;     // aanvraag_id of dossier_id
  context: 'aanvraag' | 'berekening';
  onImported?: (updates?: ImportUpdate[]) => void;
}
```

De banner toont:
- Berekening: "8 velden beschikbaar uit documenten"
- Aanvraag: "46 velden beschikbaar uit documenten"

### 6. ImportDialog.tsx — Import-functie per context

**Context = berekening**: de import wijzigt de React state, NIET Supabase direct:

```tsx
const handleImportBerekening = () => {
  // Bouw een lijst van updates
  const updates: ImportUpdate[] = [];
  for (const item of data.imports) {
    if (!selectedFields.has(fieldKey(item))) continue;
    updates.push({ target: item.target, value: item.waarde_extractie });
  }

  // Geef terug aan parent via callback
  onImported?.(updates);
  toast.success(`${updates.length} velden geïmporteerd`);
  onClose();
};
```

In Aankoop.tsx de `onImported` callback:

```tsx
function applyBerekeningImports(
  prev: AankoopInvoer,
  updates: ImportUpdate[]
): AankoopInvoer {
  const next = { ...prev };

  for (const { target, value } of updates) {
    const [prefix, field] = target.split('.');

    switch (prefix) {
      case 'klantGegevens':
        next.klantGegevens = { ...next.klantGegevens, [field]: value };
        break;

      case 'inkomenGegevens':
        next.inkomenGegevens = { ...next.inkomenGegevens, [field]: value };
        break;

      case 'onderpand': {
        // haalbaarheidsBerekeningen[0].onderpand.X
        const hb = [...next.haalbaarheidsBerekeningen];
        if (hb[0]) {
          hb[0] = {
            ...hb[0],
            onderpand: { ...hb[0].onderpand, [field]: value },
          };
        }
        next.haalbaarheidsBerekeningen = hb;
        break;
      }

      case 'berekeningen': {
        // berekeningen[0].X
        const ber = [...(next.berekeningen || [])];
        if (ber[0]) {
          ber[0] = { ...ber[0], [field]: value };
        }
        next.berekeningen = ber;
        break;
      }
    }
  }

  return next;
}
```

**Context = aanvraag**: de import schrijft naar Supabase (bestaande logica):

```tsx
const handleImportAanvraag = async () => {
  if (!targetId || selectedFields.size === 0) return;

  setImporting(true);
  try {
    const { data: aanvraag, error } = await supabase
      .from('aanvragen')
      .select('data')
      .eq('id', targetId)
      .single();

    if (error || !aanvraag) throw new Error('Aanvraag niet gevonden');

    const updatedData = JSON.parse(JSON.stringify(aanvraag.data || {}));

    for (const item of data.imports) {
      if (!selectedFields.has(fieldKey(item))) continue;
      applyFieldToAanvraag(updatedData, item);
    }

    const { error: saveError } = await supabase
      .from('aanvragen')
      .update({ data: updatedData, updated_at: new Date().toISOString() })
      .eq('id', targetId);

    if (saveError) throw saveError;

    toast.success(`${selectedFields.size} velden geïmporteerd`);
    onClose();
    onImported?.();
  } catch (err) {
    toast.error('Importeren mislukt: ' + (err as Error).message);
  } finally {
    setImporting(false);
  }
};
```

De `applyFieldToAanvraag()` functie is dezelfde als in de vorige N2 prompt — met switch op target prefix (persoon, identiteit, werkgever, dienstverband, wgv, loondienst, onderpand, financiering, vermogen).

### 7. Waarde-formatting op basis van `value_type`

```tsx
function formatDisplayValue(value: any, valueType?: string): string {
  if (value === null || value === undefined) return '—';

  switch (valueType) {
    case 'date':
      if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}/.test(value)) {
        const [y, m, d] = value.substring(0, 10).split('-');
        return `${d}-${m}-${y}`;
      }
      return String(value);

    case 'currency': {
      const num = typeof value === 'number' ? value : parseFloat(String(value).replace(/[€\s.]/g, '').replace(',', '.'));
      if (!isNaN(num)) {
        return `€ ${num.toLocaleString('nl-NL', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
      }
      return String(value);
    }

    case 'percent':
      return `${value}%`;

    case 'boolean':
      if (value === true || value === 'true') return 'Ja';
      if (value === false || value === 'false') return 'Nee';
      return String(value);

    case 'number':
      if (typeof value === 'number') return value.toLocaleString('nl-NL');
      return String(value);

    default:
      return String(value);
  }
}
```

### 8. Scrollbare dialog + groepering

Zelfde als vorige prompt — scrollbaar met `max-h-[60vh] overflow-y-auto`, groepering op persoon → categorie, header/footer vast.

### 9. ImportUpdate type

```typescript
interface ImportUpdate {
  target: string;   // bijv. "klantGegevens.achternaamAanvrager"
  value: any;
}
```

---

## Verificatie

| # | Check | Verwacht |
|---|-------|----------|
| 1 | DossierDetail | Geen ImportBanner meer (optioneel: "38 documenten verwerkt" tekst) |
| 2 | Aankoop pagina (berekening) | Banner met ~8-10 velden (naam, geboortedatum, inkomen, onderpand) |
| 3 | Aanvraag pagina | Banner met ~46 velden (alles) |
| 4 | Berekening: importeer inkomen | Waarde verschijnt direct in het formulier |
| 5 | Aanvraag: importeer legitimatie | Waarde opgeslagen in Supabase, zichtbaar na heropen |
| 6 | Bouwjaar | Toont "2.009" (getal), NIET "€ 2.009" |
| 7 | Datums | DD-MM-YYYY |
| 8 | Bedragen | € met duizendtallen |
| 9 | Volgorde | Aanvrager eerst, dan partner, dan gezamenlijk |
| 10 | Geen TypeScript fouten | `npm run build` slaagt |

## Samenvatting bestanden

| Bestand | Actie | Wijziging |
|---------|-------|-----------|
| `src/pages/DossierDetail.tsx` | Wijzig | Verwijder ImportBanner, optioneel subtiele tekst |
| `src/pages/Aankoop.tsx` | Wijzig | ImportBanner toevoegen met context="berekening", onImported callback |
| `src/pages/Aanpassen.tsx` | Wijzig | Idem als Aankoop |
| `src/hooks/useAvailableImports.ts` | Wijzig | context parameter toevoegen |
| `src/components/dossier/ImportBanner.tsx` | Wijzig | context/targetId/onImported props |
| `src/components/dossier/ImportDialog.tsx` | Wijzig | Twee import-modes (berekening=state, aanvraag=Supabase), formatting, scrollbaar |
