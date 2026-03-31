# N2 — Import dialog fixes (scrollen, datumformaat, importeer-functie)

## Context

De ImportBanner en ImportDialog zijn gebouwd (N1), maar er zijn drie problemen:

1. **Te veel velden** — opgelost in de backend: de API retourneert nu alleen velden die relevant zijn voor een hypotheekaanvraag (~40-50 i.p.v. 831). Elk veld heeft nu extra metadata:
   - `label` — Nederlandse leesbare naam (bijv. "Bruto jaarsalaris")
   - `categorie` — groepering (bijv. "Inkomen", "Persoonsgegevens")
   - `target` — pad in AanvraagData (bijv. "wgv.brutoSalaris", "persoon.achternaam")
2. **Dialog kan niet scrollen** — CSS fix nodig
3. **Datumformaat verkeerd** — YYYY-MM-DD moet DD-MM-YYYY worden
4. **"Importeer geselecteerde" knop doet niets** — importlogica ontbreekt

---

## Wat moet er aangepast worden

### 1. ImportDialog.tsx — Scrollen

De dialog content moet scrollbaar zijn. Voeg `max-height` en `overflow-y` toe:

```tsx
// In de DialogContent of het wrapper-element van de velden-lijst:
<div className="max-h-[60vh] overflow-y-auto pr-2">
  {/* ... alle velden-groepen ... */}
</div>
```

Zorg dat de header (samenvatting badges) en footer (knoppen) BUITEN de scrollbare container staan.

### 2. ImportDialog.tsx — Groepering op `categorie` + `persoon`

De API retourneert nu `categorie` (bijv. "Inkomen", "Persoonsgegevens") en `persoon` ("aanvrager" of "partner"). Groepeer hierop:

```tsx
// Groepeer imports per categorie + persoon
const grouped = useMemo(() => {
  if (!data?.imports) return {};
  const groups: Record<string, ImportVeld[]> = {};
  for (const item of data.imports) {
    const persoonLabel = item.persoon === 'partner' ? 'Partner' :
                         item.persoon === 'gezamenlijk' ? 'Gezamenlijk' : 'Aanvrager';
    const key = `${item.categorie} — ${persoonLabel}`;
    if (!groups[key]) groups[key] = [];
    groups[key].push(item);
  }
  return groups;
}, [data?.imports]);
```

### 3. ImportDialog.tsx — Toon `label` i.p.v. `veld`

Gebruik het `label` veld (Nederlands, leesbaar) als weergavenaam, niet het technische `veld`:

```tsx
// Was:
<span className="font-mono text-sm">{item.veld}</span>

// Wordt:
<span className="text-sm font-medium">{item.label}</span>
```

### 4. ImportDialog.tsx — Datumformaat DD-MM-YYYY

Alle datums in de hele frontend moeten in DD-MM-YYYY formaat staan. Maak een helper:

```tsx
function formatDisplayValue(value: any): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'boolean') return value ? 'Ja' : 'Nee';

  // Datum detectie: YYYY-MM-DD
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [y, m, d] = value.split('-');
    return `${d}-${m}-${y}`;
  }

  // Bedrag detectie
  if (typeof value === 'number' && value > 100) {
    return `€ ${value.toLocaleString('nl-NL', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
  }
  if (typeof value === 'number') {
    return value.toLocaleString('nl-NL');
  }

  // String met € teken: laat staan
  if (typeof value === 'string' && value.startsWith('€')) return value;

  return String(value);
}
```

Gebruik deze helper voor zowel `waarde_extractie` als `waarde_huidig`.

### 5. ImportDialog.tsx — Importeer geselecteerde velden

De "Importeer geselecteerde" knop moet:
1. De huidige `aanvragen.data` ophalen uit Supabase
2. De geselecteerde velden op de juiste plek mergen (via `target` pad)
3. Opslaan via de bestaande `upsertAanvraag()` functie
4. Toast tonen + dialog sluiten + banner refreshen

```tsx
const handleImport = async () => {
  if (!aanvraagId || selectedFields.size === 0) return;

  setImporting(true);
  try {
    // 1. Haal huidige aanvraag data op
    const { data: aanvraag, error } = await supabase
      .from('aanvragen')
      .select('data')
      .eq('id', aanvraagId)
      .single();

    if (error || !aanvraag) throw new Error('Aanvraag niet gevonden');

    const currentData = aanvraag.data || {};

    // 2. Merge geselecteerde velden
    const updatedData = { ...currentData };

    for (const item of data.imports) {
      if (!selectedFields.has(fieldKey(item))) continue;

      applyFieldToAanvraag(updatedData, item);
    }

    // 3. Opslaan
    const { error: saveError } = await supabase
      .from('aanvragen')
      .update({ data: updatedData })
      .eq('id', aanvraagId);

    if (saveError) throw saveError;

    toast.success(`${selectedFields.size} velden geïmporteerd`);
    onClose();
    onImported?.();  // callback om banner te refreshen
  } catch (err) {
    toast.error('Importeren mislukt: ' + (err as Error).message);
  } finally {
    setImporting(false);
  }
};
```

### 6. Merge-functie: `applyFieldToAanvraag()`

Het `target` pad bepaalt waar de waarde in AanvraagData terecht komt. De `persoon` bepaalt of het in `aanvrager` of `partner` komt.

```tsx
function applyFieldToAanvraag(data: any, item: ImportVeld) {
  const { target, persoon, waarde_extractie } = item;
  const [prefix, field] = target.split('.');

  const personKey = persoon === 'partner' ? 'partner' : 'aanvrager';

  switch (prefix) {
    case 'persoon': {
      // data.aanvrager.persoon.achternaam = waarde
      if (!data[personKey]) data[personKey] = {};
      if (!data[personKey].persoon) data[personKey].persoon = {};
      data[personKey].persoon[field] = waarde_extractie;
      break;
    }

    case 'identiteit': {
      // data.aanvrager.identiteit.legitimatienummer = waarde
      if (!data[personKey]) data[personKey] = {};
      if (!data[personKey].identiteit) data[personKey].identiteit = {};
      data[personKey].identiteit[field] = waarde_extractie;
      break;
    }

    case 'werkgever': {
      // data.inkomenAanvrager[0].loondienst.werkgever.naamWerkgever = waarde
      const inkomenKey = personKey === 'partner' ? 'inkomenPartner' : 'inkomenAanvrager';
      if (!data[inkomenKey]) data[inkomenKey] = [];
      if (data[inkomenKey].length === 0) {
        data[inkomenKey].push({ id: crypto.randomUUID(), type: 'loondienst', loondienst: { werkgever: {} } });
      }
      const firstIncome = data[inkomenKey][0];
      if (!firstIncome.loondienst) firstIncome.loondienst = {};
      if (!firstIncome.loondienst.werkgever) firstIncome.loondienst.werkgever = {};
      firstIncome.loondienst.werkgever[field] = waarde_extractie;
      break;
    }

    case 'dienstverband': {
      const inkomenKey = personKey === 'partner' ? 'inkomenPartner' : 'inkomenAanvrager';
      if (!data[inkomenKey]) data[inkomenKey] = [];
      if (data[inkomenKey].length === 0) {
        data[inkomenKey].push({ id: crypto.randomUUID(), type: 'loondienst', loondienst: { dienstverband: {} } });
      }
      const firstIncome = data[inkomenKey][0];
      if (!firstIncome.loondienst) firstIncome.loondienst = {};
      if (!firstIncome.loondienst.dienstverband) firstIncome.loondienst.dienstverband = {};
      firstIncome.loondienst.dienstverband[field] = waarde_extractie;
      break;
    }

    case 'wgv': {
      const inkomenKey = personKey === 'partner' ? 'inkomenPartner' : 'inkomenAanvrager';
      if (!data[inkomenKey]) data[inkomenKey] = [];
      if (data[inkomenKey].length === 0) {
        data[inkomenKey].push({ id: crypto.randomUUID(), type: 'loondienst', loondienst: { werkgeversverklaringCalc: {} } });
      }
      const firstIncome = data[inkomenKey][0];
      if (!firstIncome.loondienst) firstIncome.loondienst = {};
      if (!firstIncome.loondienst.werkgeversverklaringCalc) firstIncome.loondienst.werkgeversverklaringCalc = {};
      firstIncome.loondienst.werkgeversverklaringCalc[field] = waarde_extractie;
      break;
    }

    case 'loondienst': {
      const inkomenKey = personKey === 'partner' ? 'inkomenPartner' : 'inkomenAanvrager';
      if (!data[inkomenKey]) data[inkomenKey] = [];
      if (data[inkomenKey].length === 0) {
        data[inkomenKey].push({ id: crypto.randomUUID(), type: 'loondienst', loondienst: {} });
      }
      const firstIncome = data[inkomenKey][0];
      if (!firstIncome.loondienst) firstIncome.loondienst = {};
      firstIncome.loondienst[field] = waarde_extractie;
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
      // Onbekend prefix — log maar sla over
      console.warn(`Import: onbekend target prefix "${prefix}" voor veld "${item.veld}"`);
  }
}
```

### 7. ImportBanner.tsx — Toon aantal als het minder dan voorheen is

Na de backend-update zijn het ~40-50 velden i.p.v. 831. Pas de banner tekst aan:

```tsx
// Was: "831 nieuwe velden beschikbaar"
// Nu de tekst is al correct, maar verifieer dat het nu lagere aantallen toont
```

### 8. ImportBanner.tsx — "Importeer nieuwe velden" knop

De directe "Importeer nieuwe velden" knop op de banner moet de dialog openen met alle nieuwe velden al geselecteerd. Voeg een prop toe:

```tsx
<ImportDialog
  ...
  defaultSelectNew={importDirectly}  // true als via banner-knop geopend
/>
```

In ImportDialog: als `defaultSelectNew` true is, selecteer bij openen alle velden met status "nieuw".

### 9. Interface update

De response van de API is uitgebreid. Update het TypeScript interface:

```typescript
interface ImportVeld {
  veld: string;           // technische veldnaam
  label: string;          // Nederlandse leesbare naam (NIEUW)
  categorie: string;      // groepering: Persoonsgegevens, Inkomen, etc. (NIEUW)
  sectie: string;         // bron: werkgeversverklaring, paspoort, etc.
  persoon: 'aanvrager' | 'partner' | 'gezamenlijk';
  target: string;         // AanvraagData pad, bijv. "wgv.brutoSalaris" (NIEUW)
  waarde_extractie: any;
  waarde_huidig: any;
  status: 'nieuw' | 'bevestigd' | 'afwijkend';
  confidence: number;
  bron_datum: string;
}
```

---

## Verificatie

| # | Check | Verwacht |
|---|-------|----------|
| 1 | Open dossier met verwerkte documenten | Banner toont ~40-50 velden, NIET 831 |
| 2 | Klik "Bekijk details" | Dialog opent, scrollbaar, velden gegroepeerd per categorie |
| 3 | Datums in de dialog | DD-MM-YYYY formaat (bijv. "01-05-1983") |
| 4 | Bedragen in de dialog | € met duizendtallen (bijv. "€ 42.768") |
| 5 | Selecteer velden + klik "Importeer" | Velden worden opgeslagen in aanvraag, toast bevestiging |
| 6 | Heropen dialog | Geïmporteerde velden staan als "bevestigd" (groen) |
| 7 | Boolean waarden | Tonen "Ja" / "Nee" i.p.v. "true" / "false" |
| 8 | Geen TypeScript fouten | `npm run build` slaagt |

## Samenvatting bestanden

| Bestand | Actie | Wijziging |
|---------|-------|-----------|
| `src/components/dossier/ImportDialog.tsx` | Wijzig | Scrollbaar, groepering, datumformaat, importlogica |
| `src/components/dossier/ImportBanner.tsx` | Wijzig | Knop opent dialog met preselectie |
| `src/hooks/useAvailableImports.ts` | Wijzig | Interface update met label/categorie/target |
