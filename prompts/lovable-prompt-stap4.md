# Lovable Prompt — Stap 4: localStorage opruimen (Supabase-only)

> Kopieer deze prompt in Lovable om alle localStorage-code te verwijderen en Supabase als enige databron te gebruiken.

---

## Wat moet er gebeuren?

De app gebruikt nu "dual-write": data wordt naar ZOWEL localStorage ALS Supabase geschreven, en bij lezen wordt Supabase geprobeerd met localStorage als fallback. Dit was nodig tijdens de migratie, maar Supabase werkt nu stabiel. We ruimen localStorage volledig op.

**Het resultaat:** Supabase is de enige databron. Geen localStorage meer voor dossiers en aanvragen.

---

## Stap 1: `src/utils/dossierStorage.ts` — Verwijder localStorage

### Wat er nu staat (dual-write patroon):

Elke schrijffunctie doet zoiets:
```typescript
// 1. Schrijf naar localStorage
localStorage.setItem("hondsrug-dossiers-2026", JSON.stringify(dossiers));
// 2. Non-blocking Supabase upsert
upsertDossier(dossier).catch(err => console.warn("Supabase dual-write failed:", err));
```

En elke leesfunctie doet:
```typescript
// 1. Probeer Supabase
try {
  const result = await fetchAllDossiers();
  return result;
} catch (err) {
  // 2. Fallback naar localStorage
  console.warn("Supabase read failed, falling back to localStorage:", err);
  const stored = localStorage.getItem("hondsrug-dossiers-2026");
  return stored ? JSON.parse(stored) : [];
}
```

### Wat het moet worden:

**Schrijffuncties:** Verwijder alle `localStorage.setItem(...)` regels. Houd alleen de Supabase-aanroepen over. Maak de Supabase-aanroepen NIET meer non-blocking — ze moeten nu `await`-ed worden (want er is geen fallback meer).

```typescript
// VOOR (dual-write):
export function saveDossier(dossier: Dossier) {
  const dossiers = getDossiers();
  // ... update localStorage ...
  localStorage.setItem("hondsrug-dossiers-2026", JSON.stringify(dossiers));
  upsertDossier(mapToSupabase(dossier)).catch(err => console.warn(...));
}

// NA (Supabase-only):
export async function saveDossier(dossier: Dossier) {
  await upsertDossier(mapToSupabase(dossier));
}
```

**Leesfuncties:** Verwijder de localStorage-fallback. Alleen Supabase.

```typescript
// VOOR:
export async function getDossiers(): Promise<Dossier[]> {
  try {
    return await fetchAllDossiers();
  } catch {
    console.warn("Fallback naar localStorage");
    const stored = localStorage.getItem("hondsrug-dossiers-2026");
    return stored ? JSON.parse(stored) : [];
  }
}

// NA:
export async function getDossiers(): Promise<Dossier[]> {
  return await fetchAllDossiers();
}
```

**Verwijderfuncties:** Zelfde patroon — alleen Supabase.

### Belangrijk:

- Alle functies die voorheen synchroon waren (doordat ze localStorage gebruikten) worden nu `async`
- Controleer of alle aanroepers al `await` gebruiken (dat zou moeten, want we hadden in stap 5 van de migratie al alles async gemaakt)
- Verwijder de localStorage-key constante (`"hondsrug-dossiers-2026"` of vergelijkbaar)
- Verwijder ongebruikte imports die alleen voor localStorage nodig waren

---

## Stap 2: `src/utils/aanvraagStorage.ts` — Zelfde aanpak

Precies dezelfde wijzigingen als stap 1, maar dan voor aanvragen:

- Verwijder alle `localStorage.getItem("hondsrug-aanvragen-2026")` reads
- Verwijder alle `localStorage.setItem("hondsrug-aanvragen-2026", ...)` writes
- Verwijder localStorage-fallback logica
- Maak Supabase-aanroepen `await`-ed in plaats van `.catch()`
- Verwijder de localStorage-key constante

---

## Stap 3: Migratiepagina verwijderen

De migratiepagina (`/admin-migratie` of `/admin/migratie`) was eenmalig nodig om localStorage-data naar Supabase te kopiëren. Die is nu overbodig.

1. **Verwijder het migratie-component** (bijv. `src/pages/AdminMigratie.tsx` of vergelijkbaar)
2. **Verwijder de route** uit `App.tsx` of de router-configuratie
3. **Verwijder navigatie-links** naar de migratiepagina (als die ergens staan)

---

## Stap 4: Opruimen

1. **Zoek in de hele codebase** naar `localStorage` — er mogen geen verwijzingen meer zijn naar dossier- of aanvraag-gerelateerde localStorage. (NB: `localStorage` mag nog wel bestaan voor andere doeleinden, zoals UI-preferences of theme. Alleen dossier/aanvraag data moet weg.)

2. **Zoek naar** `"hondsrug-dossiers"` en `"hondsrug-aanvragen"` — alle verwijzingen moeten weg zijn.

3. **Zoek naar** `console.warn` met teksten als "fallback", "dual-write", "localStorage" — verwijder deze.

4. **Zoek naar** `JSON.parse(localStorage` en `localStorage.setItem` in de context van dossiers/aanvragen — alles moet weg.

---

## Stap 5: Error handling toevoegen

Nu localStorage niet meer als vangnet dient, moet Supabase-falen netjes afgehandeld worden.

In de dossier- en aanvraag-functies, voeg error handling toe met een toast:

```typescript
import { toast } from '@/hooks/use-toast';

export async function getDossiers(): Promise<Dossier[]> {
  try {
    return await fetchAllDossiers();
  } catch (err) {
    console.error("Fout bij laden dossiers:", err);
    toast({
      title: "Fout bij laden",
      description: "Dossiers konden niet geladen worden. Probeer het opnieuw.",
      variant: "destructive",
    });
    return [];
  }
}
```

Doe dit voor alle publieke functies in zowel `dossierStorage.ts` als `aanvraagStorage.ts`.

---

## Verificatie

1. **Open de app in een incognito-venster** (geen localStorage) → dossiers moeten laden uit Supabase
2. **Maak een nieuw dossier aan** → moet verschijnen in Supabase (check via Supabase dashboard of SQL Editor)
3. **Wijzig een dossier** → wijziging moet direct in Supabase staan
4. **Verwijder een dossier** → moet weg zijn uit Supabase
5. **Open DevTools → Application → Local Storage** → er mag GEEN `hondsrug-dossiers-2026` of `hondsrug-aanvragen-2026` key meer zijn
6. **Zoek in de code** naar `localStorage` → geen verwijzingen naar dossiers/aanvragen
7. **Test de migratiepagina URL** (`/admin-migratie`) → moet een 404 geven of redirecten

## Samenvatting

| Bestand | Wijziging |
|---------|-----------|
| `src/utils/dossierStorage.ts` | Verwijder alle localStorage code, Supabase-only + error toasts |
| `src/utils/aanvraagStorage.ts` | Verwijder alle localStorage code, Supabase-only + error toasts |
| Migratie-component | **Verwijderd** |
| App.tsx / router | Migratie-route verwijderd |
| Overige bestanden met localStorage refs | Opgeruimd |
