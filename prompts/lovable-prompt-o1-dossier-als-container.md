# O1: Dossier als container — berekeningen worden kinderen

## Context

Er is een nieuw database-model. **Dossier** is nu een container (klantgegevens + metadata). **Berekeningen** zijn kinderen van een dossier, net als aanvragen en adviezen.

### Nieuwe tabel: `berekeningen`

```sql
CREATE TABLE berekeningen (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  dossier_id UUID NOT NULL REFERENCES dossiers(id) ON DELETE CASCADE,
  type TEXT NOT NULL CHECK (type IN ('aankoop', 'aanpassen')),
  naam TEXT NOT NULL DEFAULT '',
  invoer JSONB NOT NULL DEFAULT '{}',
  scenario1 JSONB NOT NULL DEFAULT '{}',
  scenario2 JSONB NOT NULL DEFAULT '{}',
  owner_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  aanmaak_datum TIMESTAMPTZ NOT NULL DEFAULT now(),
  laatst_gewijzigd TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**Belangrijk:** De bestaande data is al gemigreerd. Elk oud dossier met invoer-data heeft nu een corresponderend record in `berekeningen`. De kolommen `invoer`, `scenario1`, `scenario2` in `dossiers` zijn nullable geworden. Nieuwe dossiers krijgen deze kolommen NIET meer gevuld.

### Wat verandert

| Was | Wordt |
|-----|-------|
| Dossier = berekening (invoer/scenario in dossier) | Dossier = container (geen invoer/scenario) |
| "Nieuwe berekening" = nieuw dossier | "Nieuwe berekening" = nieuw record in `berekeningen` |
| Aankoop.tsx slaat op in `dossiers` tabel | Aankoop.tsx slaat op in `berekeningen` tabel |
| `dossierId` = ID van het dossier met de berekening | `dossierId` = container, `berekeningId` = de berekening |
| DossierDetail groepeert dossiers op `klant_naam` | DossierDetail toont één dossier met berekeningen-lijst |

---

## Stap 1: Nieuwe service `supabaseBerekeningService.ts`

Maak een nieuwe service aan naar het patroon van `supabaseDossierService.ts`:

```typescript
// src/services/supabaseBerekeningService.ts
import { supabase } from "@/integrations/supabase/client";

export interface BerekeningRow {
  id: string;
  dossier_id: string;
  type: 'aankoop' | 'aanpassen';
  naam: string;
  invoer: any;
  scenario1: any;
  scenario2: any;
  owner_id: string | null;
  aanmaak_datum: string;
  laatst_gewijzigd: string;
}

export async function fetchBerekeningenByDossier(dossierId: string) {
  const { data, error } = await supabase
    .from("berekeningen")
    .select("*")
    .eq("dossier_id", dossierId)
    .order("aanmaak_datum", { ascending: true });

  if (error) {
    console.error("fetchBerekeningen error:", error);
    return { data: null, error };
  }
  return { data: data as BerekeningRow[], error: null };
}

export async function fetchBerekeningById(id: string) {
  const { data, error } = await supabase
    .from("berekeningen")
    .select("*")
    .eq("id", id)
    .maybeSingle();

  if (error) {
    console.error("fetchBerekening error:", error);
    return { data: null, error };
  }
  return { data: data as BerekeningRow | null, error: null };
}

export async function upsertBerekening(row: Partial<BerekeningRow> & { id: string; dossier_id: string }) {
  const { data, error } = await supabase
    .from("berekeningen")
    .upsert([row] as any)
    .select()
    .maybeSingle();

  if (error) {
    console.error("upsertBerekening error:", error);
    return { data: null, error };
  }
  return { data: data as BerekeningRow, error: null };
}

export async function deleteBerekening(id: string) {
  const { error } = await supabase
    .from("berekeningen")
    .delete()
    .eq("id", id);

  if (error) {
    console.error("deleteBerekening error:", error);
    return { error };
  }
  return { error: null };
}
```

## Stap 2: Update `Aankoop.tsx` — slaat op in `berekeningen`

### 2a. Nieuwe URL-structuur

Aankoop.tsx accepteert nu twee URL-parameters:

```
/aankoop?dossierId=UUID                     → nieuwe berekening voor dit dossier
/aankoop?dossierId=UUID&berekeningId=UUID   → bestaande berekening bewerken
```

**Verwijder** ondersteuning voor `?id=UUID` (oud formaat). Gebruik altijd `dossierId` + optioneel `berekeningId`.

### 2b. State wijzigingen

Voeg toe:
```typescript
const [berekeningId, setBerekeningId] = useState<string | null>(null);
```

De bestaande `dossierId` state blijft, maar verwijst nu altijd naar het **container-dossier**.

### 2c. Laden bij startup

Vervang de bestaande `loadDossier` useEffect (regel ~218-288):

```typescript
useEffect(() => {
  const loadData = async () => {
    const dossierId = searchParams.get('dossierId');
    const berekeningIdParam = searchParams.get('berekeningId');

    // Legacy support: ?id= → zoek berekening in nieuwe tabel
    const legacyId = searchParams.get('id');
    if (legacyId && !dossierId) {
      // Oud formaat: ?id= was een dossier-ID. Zoek de berekening.
      const { data: berekeningen } = await fetchBerekeningenByDossier(legacyId);
      if (berekeningen && berekeningen.length > 0) {
        const ber = berekeningen[0];
        // Redirect naar nieuw formaat
        navigate(`/aankoop?dossierId=${legacyId}&berekeningId=${ber.id}`, { replace: true });
        return;
      }
      // Geen berekening gevonden → open als nieuw
      navigate(`/aankoop?dossierId=${legacyId}`, { replace: true });
      return;
    }

    if (!dossierId) return;
    setDossierId(dossierId);

    // Laad dossier (voor klantgegevens)
    const dossier = await getDossier(dossierId);
    if (dossier) {
      setKlantContactGegevens(dossier.klantContactGegevens);
      setOriginalOwnerId(dossier.ownerId || null);
      setOriginalOwnerName(dossier.ownerName || '');

      // Zet klantGegevens in invoer (uit dossier)
      if (dossier.invoer?.klantGegevens) {
        setInvoer(prev => ({
          ...prev,
          klantGegevens: dossier.invoer.klantGegevens,
        }));
      }
    }

    // Laad berekening (als die bestaat)
    if (berekeningIdParam) {
      const { data: ber } = await fetchBerekeningById(berekeningIdParam);
      if (ber && ber.type === 'aankoop') {
        setBerekeningId(ber.id);
        const invoerWithDefaults = {
          ...ber.invoer,
          haalbaarheidsBerekeningen: ber.invoer.haalbaarheidsBerekeningen || defaultAankoopInvoer.haalbaarheidsBerekeningen,
          berekeningen: (ber.invoer.berekeningen || []).map(b => ({
            ...b,
            extraPostenAankoop: b.extraPostenAankoop || [],
            extraPostenKosten: b.extraPostenKosten || [],
            extraPostenEigenMiddelen: b.extraPostenEigenMiddelen || [],
          })),
        };
        setInvoer(invoerWithDefaults);
        setScenarios([ber.scenario1, ber.scenario2]);

        // Restore saved API results
        const savedInvoer = ber.invoer as any;
        if (savedInvoer.natResultaten) {
          // ... bestaande restore logica ...
        }
      }
    }
  };
  loadData().then(() => { pendingSnapshotRef.current = true; });
}, [searchParams]);
```

### 2d. Opslaan naar `berekeningen` tabel

Vervang de `performSave` functie. In plaats van `saveDossier()`, gebruik `upsertBerekening()`:

```typescript
const performSave = async (gegevens: DossierKlantGegevens, createNew: boolean = false) => {
  if (saveInProgressRef.current) return;
  saveInProgressRef.current = true;
  setIsSaving(true);

  try {
    // 1. Update klantgegevens op het DOSSIER (niet de berekening)
    if (dossierId && gegevens) {
      let klantNaam = gegevens.aanvrager.achternaam + (gegevens.aanvrager.voornaam ? `, ${gegevens.aanvrager.voornaam}` : '');
      if (gegevens.partner?.achternaam) {
        klantNaam += ` en ${gegevens.partner.achternaam}` + (gegevens.partner.voornaam ? `, ${gegevens.partner.voornaam}` : '');
      }

      // Update dossier met klantgegevens (NIET invoer/scenario)
      const { error } = await supabase
        .from('dossiers')
        .update({
          klant_naam: klantNaam,
          klant_contact_gegevens: gegevens,
        })
        .eq('id', dossierId);

      if (error) console.error('Dossier klantgegevens update mislukt:', error);
      setKlantContactGegevens(gegevens);
    }

    // 2. Sla berekening op
    const scenario1 = scenarios[0] || createDefaultScenario('Berekening 1');
    const scenario2 = scenarios[1] || createDefaultScenario('Berekening 2');

    const natResultatenArray = invoer.haalbaarheidsBerekeningen.map(ber => natResultaten[ber.id] || null);
    const maandlastenResultatenArray = scenarios.map(s => monthlyCostsResults[s.id] || null);
    const enrichedInvoer = {
      ...invoer,
      natResultaten: natResultatenArray,
      maandlastenResultaten: maandlastenResultatenArray,
    } as any;

    if (!berekeningId) {
      // Nieuwe berekening aanmaken
      const newId = crypto.randomUUID();
      const { error } = await upsertBerekening({
        id: newId,
        dossier_id: dossierId!,
        type: 'aankoop',
        naam: dossierNaam,
        invoer: enrichedInvoer,
        scenario1,
        scenario2,
        owner_id: currentUserId || undefined,
      });
      if (error) throw error;

      setBerekeningId(newId);
      toast({ title: 'Berekening opgeslagen' });

      // URL bijwerken
      const newParams = new URLSearchParams(searchParams);
      newParams.set('berekeningId', newId);
      navigate(`?${newParams.toString()}`, { replace: true });
    } else {
      // Bestaande berekening overschrijven
      const { error } = await upsertBerekening({
        id: berekeningId,
        dossier_id: dossierId!,
        type: 'aankoop',
        naam: dossierNaam,
        invoer: enrichedInvoer,
        scenario1,
        scenario2,
      });
      if (error) throw error;

      toast({ title: 'Berekening bijgewerkt' });
    }

    snapshotRef.current = JSON.stringify({ invoer, scenarios });
    setIsDirty(false);
  } finally {
    saveInProgressRef.current = false;
    setIsSaving(false);
  }
};
```

### 2e. `handleSaveClick` vereenvoudigen

De SaveChoiceDialog is niet meer nodig. Opslaan = altijd overschrijven (of aanmaken als nieuw).

```typescript
const handleSaveClick = () => {
  if (!klantContactGegevens) {
    setShowSaveDialog(true);  // Eerste keer: contactgegevens invullen
  } else {
    performSave(klantContactGegevens);
  }
};
```

**Verwijder** `handleOverwrite`, `handleSaveNew`, `handleOverwriteWithOwnership`, `showSaveChoiceDialog`, `showOwnershipChoice`. De `SaveChoiceDialog` component wordt niet meer gebruikt in Aankoop.tsx.

### 2f. Import toevoegen

```typescript
import { fetchBerekeningenByDossier, fetchBerekeningById, upsertBerekening } from '@/services/supabaseBerekeningService';
```

## Stap 3: Update `Aanpassen.tsx`

Exact dezelfde wijzigingen als Aankoop.tsx:
- `berekeningId` state
- Laden uit `berekeningen` tabel
- Opslaan naar `berekeningen` tabel met `type: 'aanpassen'`
- URL: `/aanpassen?dossierId=UUID&berekeningId=UUID`
- `handleSaveClick` vereenvoudigen (geen SaveChoiceDialog)

## Stap 4: Update `DossierDetail.tsx`

### 4a. Berekeningen laden

Laad berekeningen apart van het dossier:

```typescript
const [berekeningen, setBerekeningen] = useState<BerekeningRow[]>([]);

useEffect(() => {
  if (primaryDossier?.id) {
    fetchBerekeningenByDossier(primaryDossier.id).then(({ data }) => {
      if (data) setBerekeningen(data);
    });
  }
}, [primaryDossier?.id]);
```

### 4b. Berekeningen sectie

Vervang de huidige berekeningen-weergave (die dossiers als berekeningen toont) door een lijst van berekening-records:

```tsx
<CardContent>
  {berekeningen.length === 0 ? (
    <p className="text-sm text-muted-foreground py-4 text-center">
      Nog geen berekeningen. Maak een eerste berekening aan.
    </p>
  ) : (
    <div className="space-y-2">
      {berekeningen.map((ber) => (
        <div key={ber.id} className="flex items-center justify-between p-2 rounded hover:bg-muted/50">
          <Link
            to={`/${ber.type === 'aankoop' ? 'aankoop' : 'aanpassen'}?dossierId=${primaryDossier.id}&berekeningId=${ber.id}`}
            className="flex-1"
          >
            <span className="text-sm font-medium">{ber.naam || `${ber.type === 'aankoop' ? 'Aankoop' : 'Aanpassen'} berekening`}</span>
            <span className="text-xs text-muted-foreground ml-2">
              {new Date(ber.laatst_gewijzigd).toLocaleDateString('nl-NL')}
            </span>
          </Link>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => handleDeleteBerekening(ber.id)}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      ))}
    </div>
  )}
</CardContent>
```

### 4c. "Nieuwe berekening" links updaten

Vervang de huidige links die `?dossierId=` gebruiken (wat een parent-copy deed):

```tsx
<DropdownMenuItem asChild>
  <Link to={`/aankoop?dossierId=${primaryDossier.id}`}>
    <Home className="h-4 w-4 mr-2" />
    Aankoop woning
  </Link>
</DropdownMenuItem>
<DropdownMenuItem asChild>
  <Link to={`/aanpassen?dossierId=${primaryDossier.id}`}>
    <Calculator className="h-4 w-4 mr-2" />
    Aanpassen hypotheek
  </Link>
</DropdownMenuItem>
```

Dit hoeft niet te veranderen — het format is hetzelfde. Maar nu maakt `/aankoop?dossierId=UUID` (zonder `berekeningId`) een **nieuwe berekening** aan, niet een nieuw dossier.

### 4d. Delete berekening handler

```typescript
const handleDeleteBerekening = async (berekeningId: string) => {
  if (!confirm('Weet je zeker dat je deze berekening wilt verwijderen?')) return;
  const { error } = await deleteBerekening(berekeningId);
  if (error) {
    toast({ title: 'Verwijderen mislukt', variant: 'destructive' });
    return;
  }
  setBerekeningen(prev => prev.filter(b => b.id !== berekeningId));
  toast({ title: 'Berekening verwijderd' });
};
```

### 4e. Verwijder dossier-groepering op klant_naam

De huidige logica groepeert meerdere dossiers met dezelfde `klant_naam` als "gerelateerde dossiers". Dit is niet meer nodig — elk dossier is nu uniek per klant. Vereenvoudig de laad-logica: haal gewoon het ene dossier op via URL ID.

## Stap 5: Update `Index.tsx` — dossier aanmaken

In `handleCreateDossier()`:

1. Maak het dossier **zonder** `invoer`, `scenario1`, `scenario2`:

```typescript
const dossier = {
  id: crypto.randomUUID(),
  type: 'aankoop',  // default type, kan later wijzigen
  naam: dossierNaam,
  klantNaam,
  aanmaakDatum: now,
  laatstGewijzigd: now,
  klantContactGegevens,
  invoer: {},       // LEEG — geen berekening in dossier
  scenario1: {},    // LEEG
  scenario2: {},    // LEEG
};
```

2. Na het opslaan, navigeer naar DossierDetail (niet naar Aankoop):

```typescript
await saveDossier(dossier);
setOpen(false);
navigate(`/dossier/${dossier.id}`);  // Dit is al zo ✓
```

## Stap 6: Update `Aanvraag.tsx` — leest berekening i.p.v. dossier

Zoek waar `dossier.invoer` wordt gelezen in Aanvraag.tsx. Dit moet nu uit de berekening komen.

Haal de eerste berekening op voor het dossier:

```typescript
const [berekening, setBerekening] = useState<BerekeningRow | null>(null);

useEffect(() => {
  if (dossierId) {
    fetchBerekeningenByDossier(dossierId).then(({ data }) => {
      if (data && data.length > 0) setBerekening(data[0]);
    });
  }
}, [dossierId]);
```

Vervang dan `dossier.invoer` door `berekening?.invoer` waar nodig.

## Stap 7: Supabase types regenereren

Na het aanmaken van de `berekeningen` tabel in Supabase (via de SQL editor), regenereer de TypeScript types:

```bash
npx supabase gen types typescript --project-id zecrknauqcxbsqjdramq > src/integrations/supabase/types.ts
```

---

## Verificatie

| # | Check | Verwacht |
|---|-------|----------|
| 1 | Nieuw dossier aanmaken op homepage | Dossier aangemaakt, geen berekening, navigeert naar DossierDetail |
| 2 | "Nieuwe berekening" → "Aankoop" vanuit DossierDetail | Aankoop pagina opent met `?dossierId=UUID` (geen `berekeningId`) |
| 3 | Berekening invullen en opslaan | Record aangemaakt in `berekeningen` tabel, URL krijgt `&berekeningId=UUID` |
| 4 | Pagina refreshen na opslaan | Berekening wordt correct geladen via `berekeningId` |
| 5 | Opnieuw opslaan (na wijziging) | Bestaande berekening bijgewerkt (geen nieuw record) |
| 6 | Tweede berekening toevoegen | Nieuw record in `berekeningen`, eerste blijft bestaan |
| 7 | Berekening verwijderen in DossierDetail | Record verwijderd, lijst geüpdatet |
| 8 | Dossier-overzicht (Dossiers pagina) | Elk dossier = één rij (geen groepering meer) |
| 9 | Klantnaam wijzigen in DossierDetail | Alleen `dossiers.klant_naam` wijzigt, geen nieuw dossier |
| 10 | Geen TypeScript fouten | `npm run build` slaagt |

## Samenvatting bestanden

| Bestand | Actie |
|---------|-------|
| `src/services/supabaseBerekeningService.ts` | **Nieuw** — CRUD voor berekeningen tabel |
| `src/pages/Aankoop.tsx` | **Herschrijf** save/load — berekeningen tabel i.p.v. dossiers |
| `src/pages/Aanpassen.tsx` | **Herschrijf** save/load — zelfde als Aankoop |
| `src/pages/DossierDetail.tsx` | **Update** — berekeningen als kinderen tonen, verwijder dossier-groepering |
| `src/pages/Index.tsx` | **Update** — dossier aanmaken zonder invoer/scenario |
| `src/pages/Aanvraag.tsx` | **Update** — lees berekening i.p.v. dossier.invoer |
| `src/components/SaveDossierDialog.tsx` | **Geen wijziging** — wordt nog steeds gebruikt voor klantgegevens |
| `src/integrations/supabase/types.ts` | **Regenereer** na SQL migratie |
