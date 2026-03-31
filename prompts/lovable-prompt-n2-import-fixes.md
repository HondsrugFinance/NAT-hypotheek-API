# N2 — Import dialog fixes (aanvraag-selectie, formatting, importeer-functie)

## Context

De ImportBanner en ImportDialog zijn gebouwd (N1), maar er zijn vijf problemen:

1. **"Importeer" knop disabled / doet niets** — er is geen `aanvraag_id` context als de dialog vanuit DossierDetail geopend wordt
2. **Onduidelijk waar gegevens heen gaan** — gebruiker moet zien naar welke berekening/aanvraag geïmporteerd wordt
3. **Volgorde verkeerd** — moet de invulvolgorde van de aanvraag tool volgen (eerst aanvrager alles, dan partner alles, dan gezamenlijk)
4. **Bouwjaar toont "€ 2.009"** — getallen worden onterecht als bedragen geformateerd. De API stuurt nu `value_type` mee ("currency", "date", "number", "text", "boolean", "percent")
5. **Import-functie ontbreekt** — client-side merge naar aanvraag data

De API response per veld is uitgebreid:
```typescript
interface ImportVeld {
  veld: string;           // technische veldnaam
  label: string;          // Nederlandse leesbare naam (bijv. "Bruto jaarsalaris")
  categorie: string;      // groepering: Persoonsgegevens, Adres, Legitimatie, Werkgever, Inkomen, Onderpand, Hypotheek, Pensioen, Bankgegevens, Echtscheiding
  sectie: string;         // bron-document: werkgeversverklaring, paspoort, etc.
  persoon: 'aanvrager' | 'partner' | 'gezamenlijk';
  target: string;         // AanvraagData pad, bijv. "wgv.brutoSalaris"
  value_type: string;     // "currency" | "date" | "number" | "text" | "boolean" | "percent" (NIEUW)
  waarde_extractie: any;
  waarde_huidig: any;
  status: 'nieuw' | 'bevestigd' | 'afwijkend';
  confidence: number;
  bron_datum: string;
}
```

De velden komen nu gesorteerd uit de API: eerst aanvrager (persoonsgegevens → adres → legitimatie → werkgever → inkomen → onderpand → ...), dan partner, dan gezamenlijk.

---

## Wat moet er aangepast worden

### 1. Aanvraag-selectie: weet waar je importeert

De import moet naar een specifieke aanvraag gaan. Momenteel weet de dialog niet welke.

**In DossierDetail.tsx — haal beschikbare aanvragen op:**

```tsx
// Naast de bestaande aanvragen-query, geef de eerste aanvraag mee aan ImportBanner:
const eerstAanvraag = aanvragen?.[0]; // de meest recente

<ImportBanner
  dossierId={primaryDossier.id}
  aanvraagId={eersteAanvraag?.id}
  aanvraagNaam={eersteAanvraag?.naam || eersteAanvraag?.type || 'Berekening'}
/>
```

Als er meerdere aanvragen zijn, toon een dropdown in de ImportDialog header:

```tsx
// In ImportDialog, boven de velden:
{aanvragen.length > 1 && (
  <div className="flex items-center gap-2 text-sm text-muted-foreground mb-3">
    <span>Importeren naar:</span>
    <Select value={selectedAanvraagId} onValueChange={setSelectedAanvraagId}>
      <SelectTrigger className="w-[250px] h-8">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {aanvragen.map(a => (
          <SelectItem key={a.id} value={a.id}>
            {a.naam || a.type} — {formatDate(a.laatst_bewerkt)}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  </div>
)}

{aanvragen.length === 1 && (
  <p className="text-sm text-muted-foreground mb-3">
    Importeren naar: <strong>{aanvragen[0].naam || aanvragen[0].type}</strong>
  </p>
)}
```

**Haal de aanvragen-lijst op via Supabase in de dialog:**

```tsx
// In ImportDialog, bij openen:
useEffect(() => {
  if (!open || !dossierId) return;
  supabase
    .from('aanvragen')
    .select('id, naam, type, updated_at')
    .eq('dossier_id', dossierId)
    .order('updated_at', { ascending: false })
    .then(({ data }) => {
      if (data && data.length > 0) {
        setAanvragen(data);
        setSelectedAanvraagId(aanvraagId || data[0].id);
      }
    });
}, [open, dossierId]);
```

**Wanneer aanvraag wijzigt → herlaad imports met die aanvraag_id:**

```tsx
// Wanneer selectedAanvraagId verandert, opnieuw ophalen
useEffect(() => {
  if (!selectedAanvraagId) return;
  fetchImports(dossierId, selectedAanvraagId);
}, [selectedAanvraagId]);
```

### 2. Waarde-formatting op basis van `value_type`

Vervang de huidige formatting logica door een functie die `value_type` gebruikt:

```tsx
function formatDisplayValue(value: any, valueType?: string): string {
  if (value === null || value === undefined) return '—';

  switch (valueType) {
    case 'date':
      // YYYY-MM-DD → DD-MM-YYYY
      if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}/.test(value)) {
        const [y, m, d] = value.substring(0, 10).split('-');
        return `${d}-${m}-${y}`;
      }
      return String(value);

    case 'currency':
      const num = typeof value === 'number' ? value : parseFloat(String(value).replace(/[€\s.]/g, '').replace(',', '.'));
      if (!isNaN(num)) {
        return `€ ${num.toLocaleString('nl-NL', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
      }
      return String(value);

    case 'percent':
      return `${value}%`;

    case 'boolean':
      if (value === true || value === 'true') return 'Ja';
      if (value === false || value === 'false') return 'Nee';
      return String(value);

    case 'number':
      // Gewoon getal, GEEN € teken (bijv. bouwjaar 2009, woonoppervlakte 127)
      if (typeof value === 'number') {
        return value.toLocaleString('nl-NL');
      }
      return String(value);

    case 'text':
    default:
      return String(value);
  }
}
```

**Gebruik in de veldenlijst:**
```tsx
<span>{formatDisplayValue(item.waarde_extractie, item.value_type)}</span>
```

### 3. Groepering op `persoon` → `categorie`

De API sorteert al correct (aanvrager eerst, dan partner, dan gezamenlijk). Groepeer in de UI op **persoon** als eerste niveau, dan **categorie**:

```tsx
const grouped = useMemo(() => {
  if (!data?.imports) return [];

  const persoonLabels: Record<string, string> = {
    aanvrager: 'Aanvrager',
    partner: 'Partner',
    gezamenlijk: 'Gezamenlijk',
  };

  // Groepeer: persoon → categorie → items
  const groups: { title: string; items: ImportVeld[] }[] = [];
  let currentKey = '';

  for (const item of data.imports) {
    const persLabel = persoonLabels[item.persoon] || item.persoon;
    const key = `${persLabel} — ${item.categorie}`;
    if (key !== currentKey) {
      groups.push({ title: key, items: [] });
      currentKey = key;
    }
    groups[groups.length - 1].items.push(item);
  }

  return groups;
}, [data?.imports]);
```

Render:
```tsx
{grouped.map(group => (
  <div key={group.title} className="mb-4">
    <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
      {group.title}
    </h4>
    {group.items.map(item => (
      <ImportRow key={fieldKey(item)} item={item} ... />
    ))}
  </div>
))}
```

### 4. Import-functie: `applyFieldToAanvraag()`

Het `target` pad bepaalt waar de waarde in AanvraagData terecht komt.

```tsx
function applyFieldToAanvraag(data: any, item: ImportVeld) {
  const { target, persoon, waarde_extractie } = item;
  const [prefix, field] = target.split('.');

  const personKey = persoon === 'partner' ? 'partner' : 'aanvrager';

  switch (prefix) {
    case 'persoon': {
      if (!data[personKey]) data[personKey] = {};
      if (!data[personKey].persoon) data[personKey].persoon = {};
      data[personKey].persoon[field] = waarde_extractie;
      break;
    }

    case 'identiteit': {
      if (!data[personKey]) data[personKey] = {};
      if (!data[personKey].identiteit) data[personKey].identiteit = {};
      data[personKey].identiteit[field] = waarde_extractie;
      break;
    }

    case 'werkgever': {
      const inkomenKey = personKey === 'partner' ? 'inkomenPartner' : 'inkomenAanvrager';
      if (!data[inkomenKey]) data[inkomenKey] = [];
      if (data[inkomenKey].length === 0) {
        data[inkomenKey].push({ id: crypto.randomUUID(), type: 'loondienst', loondienst: { werkgever: {} } });
      }
      const item0 = data[inkomenKey][0];
      if (!item0.loondienst) item0.loondienst = {};
      if (!item0.loondienst.werkgever) item0.loondienst.werkgever = {};
      item0.loondienst.werkgever[field] = waarde_extractie;
      break;
    }

    case 'dienstverband': {
      const inkomenKey = personKey === 'partner' ? 'inkomenPartner' : 'inkomenAanvrager';
      if (!data[inkomenKey]) data[inkomenKey] = [];
      if (data[inkomenKey].length === 0) {
        data[inkomenKey].push({ id: crypto.randomUUID(), type: 'loondienst', loondienst: { dienstverband: {} } });
      }
      const item0 = data[inkomenKey][0];
      if (!item0.loondienst) item0.loondienst = {};
      if (!item0.loondienst.dienstverband) item0.loondienst.dienstverband = {};
      item0.loondienst.dienstverband[field] = waarde_extractie;
      break;
    }

    case 'wgv': {
      const inkomenKey = personKey === 'partner' ? 'inkomenPartner' : 'inkomenAanvrager';
      if (!data[inkomenKey]) data[inkomenKey] = [];
      if (data[inkomenKey].length === 0) {
        data[inkomenKey].push({ id: crypto.randomUUID(), type: 'loondienst', loondienst: { werkgeversverklaringCalc: {} } });
      }
      const item0 = data[inkomenKey][0];
      if (!item0.loondienst) item0.loondienst = {};
      if (!item0.loondienst.werkgeversverklaringCalc) item0.loondienst.werkgeversverklaringCalc = {};
      item0.loondienst.werkgeversverklaringCalc[field] = waarde_extractie;
      break;
    }

    case 'loondienst': {
      const inkomenKey = personKey === 'partner' ? 'inkomenPartner' : 'inkomenAanvrager';
      if (!data[inkomenKey]) data[inkomenKey] = [];
      if (data[inkomenKey].length === 0) {
        data[inkomenKey].push({ id: crypto.randomUUID(), type: 'loondienst', loondienst: {} });
      }
      const item0 = data[inkomenKey][0];
      if (!item0.loondienst) item0.loondienst = {};
      item0.loondienst[field] = waarde_extractie;
      break;
    }

    case 'onderpand': {
      if (!data.onderpand) data.onderpand = {};
      data.onderpand[field] = waarde_extractie;
      break;
    }

    case 'financiering': {
      if (!data.financieringsopzet) data.financieringsopzet = {};
      data.financieringsopzet[field] = waarde_extractie;
      break;
    }

    case 'vermogen': {
      if (field === 'iban') {
        if (!data.vermogenSectie) data.vermogenSectie = {};
        if (!data.vermogenSectie.iban) data.vermogenSectie.iban = {};
        const ibanKey = personKey === 'partner' ? 'ibanPartner' : 'ibanAanvrager';
        data.vermogenSectie.iban[ibanKey] = waarde_extractie;
      }
      break;
    }

    default:
      console.warn(`Import: onbekend target prefix "${prefix}" voor veld "${item.veld}"`);
  }
}
```

### 5. "Importeer geselecteerde" knop handler

```tsx
const [importing, setImporting] = useState(false);

const handleImport = async () => {
  if (!selectedAanvraagId || selectedFields.size === 0) return;

  setImporting(true);
  try {
    // 1. Haal huidige aanvraag data op
    const { data: aanvraag, error } = await supabase
      .from('aanvragen')
      .select('data')
      .eq('id', selectedAanvraagId)
      .single();

    if (error || !aanvraag) throw new Error('Aanvraag niet gevonden');

    // 2. Deep copy en merge geselecteerde velden
    const updatedData = JSON.parse(JSON.stringify(aanvraag.data || {}));

    for (const importItem of data.imports) {
      if (!selectedFields.has(fieldKey(importItem))) continue;
      applyFieldToAanvraag(updatedData, importItem);
    }

    // 3. Opslaan
    const { error: saveError } = await supabase
      .from('aanvragen')
      .update({ data: updatedData, updated_at: new Date().toISOString() })
      .eq('id', selectedAanvraagId);

    if (saveError) throw saveError;

    toast.success(`${selectedFields.size} velden geïmporteerd`);
    onClose();
    refresh?.();  // callback om banner te refreshen
  } catch (err) {
    toast.error('Importeren mislukt: ' + (err as Error).message);
  } finally {
    setImporting(false);
  }
};
```

### 6. Scrollbare dialog

Zorg dat de veldenlijst scrollbaar is maar header en footer vast staan:

```tsx
<DialogContent className="max-w-2xl max-h-[85vh] flex flex-col">
  {/* Header: titel + badges + aanvraag-selectie */}
  <DialogHeader>
    <DialogTitle>Beschikbare gegevens uit documenten</DialogTitle>
    {/* badges + aanvraag selectie */}
  </DialogHeader>

  {/* Scrollbare veldenlijst */}
  <div className="flex-1 overflow-y-auto pr-2 min-h-0">
    {grouped.map(group => (
      // ... groepen met velden
    ))}
  </div>

  {/* Footer: selecteer alle + importeer knop */}
  <div className="flex items-center justify-between pt-4 border-t">
    <label className="flex items-center gap-2 text-sm cursor-pointer">
      <Checkbox checked={allNewSelected} onCheckedChange={toggleAllNew} />
      Selecteer alle nieuwe
    </label>
    <div className="flex gap-2">
      <Button variant="outline" onClick={onClose}>Annuleren</Button>
      <Button onClick={handleImport} disabled={selectedFields.size === 0 || importing}>
        {importing ? 'Importeren...' : `Importeer geselecteerde (${selectedFields.size})`}
      </Button>
    </div>
  </div>
</DialogContent>
```

### 7. Banner tekst verduidelijken

```tsx
// In ImportBanner.tsx:
<p className="font-medium">
  {data.documenten_verwerkt} documenten verwerkt — {data.samenvatting.nieuw} nieuwe velden beschikbaar
  {aanvraagNaam && <span className="text-muted-foreground"> voor {aanvraagNaam}</span>}
</p>
```

---

## Verificatie

| # | Check | Verwacht |
|---|-------|----------|
| 1 | Open dossier met 1 aanvraag | Dialog toont "Importeren naar: Hypotheek verhogen" |
| 2 | Open dossier met 2+ aanvragen | Dropdown om aanvraag te kiezen |
| 3 | Bouwjaar | Toont "2.009" (getal), NIET "€ 2.009" |
| 4 | Woonoppervlakte | Toont "127" (getal), NIET "€ 127" |
| 5 | Datums | DD-MM-YYYY (bijv. "01-05-1983") |
| 6 | Bedragen | € met duizendtallen (bijv. "€ 42.768") |
| 7 | Volgorde | Aanvrager eerst (persoon → adres → legitimatie → werkgever → inkomen → onderpand), dan partner |
| 8 | Selecteer velden + klik "Importeer" | Toast "X velden geïmporteerd" + dialog sluit |
| 9 | Heropen dialog | Geïmporteerde velden staan als "bevestigd" |
| 10 | Boolean waarden | "Ja" / "Nee" |
| 11 | Geen TypeScript fouten | `npm run build` slaagt |

## Samenvatting bestanden

| Bestand | Actie | Wijziging |
|---------|-------|-----------|
| `src/components/dossier/ImportDialog.tsx` | Wijzig | Scrollbaar, aanvraag-selectie, formatting op value_type, import-functie, groepering persoon→categorie |
| `src/components/dossier/ImportBanner.tsx` | Wijzig | aanvraagId/aanvraagNaam props, verduidelijking tekst |
| `src/hooks/useAvailableImports.ts` | Wijzig | Interface update met value_type |
| `src/pages/DossierDetail.tsx` | Wijzig | Geef aanvraagId mee aan ImportBanner |
