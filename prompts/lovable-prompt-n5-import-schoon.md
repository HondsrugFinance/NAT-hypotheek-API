# N5 — Import: schone implementatie

## Context

De import-functie is opnieuw opgezet. De oude implementatie had problemen doordat het dossier-ID als target werd gebruikt terwijl berekeningen in een aparte tabel staan.

**Nieuwe structuur:**
- `dossier_id` = bron (waar de extracties vandaan komen)
- `target_id` = bestemming (berekening-ID of aanvraag-ID)
- Deze worden altijd apart meegegeven

**Twee API endpoints:**

```
GET  /doc-processing/{dossier_id}/available-imports?target_id={BER_ID}&context=berekening
POST /doc-processing/{dossier_id}/apply-imports
     { "target_id": "BER_ID", "context": "berekening", "selected_targets": [...] }
```

Let op: de parameter heet nu `target_id` (was `aanvraag_id`).

---

## Wat moet er veranderen

### 1. useAvailableImports.ts — parameter hernoemen

```typescript
export function useAvailableImports(
  dossierId: string | undefined,
  targetId?: string,      // berekening-ID of aanvraag-ID
  context: 'aanvraag' | 'berekening' = 'berekening'
) {
  // ...
  const params = new URLSearchParams({ context });
  if (targetId) params.set('target_id', targetId);  // was: aanvraag_id

  const resp = await window.fetch(
    `${API_CONFIG.NAT_API_URL}/doc-processing/${dossierId}/available-imports?${params}`,
    // ...
  );
```

### 2. ImportBanner.tsx — altijd tonen + correcte props

```tsx
interface ImportBannerProps {
  dossierId: string;       // voor extracties ophalen
  targetId?: string;       // berekening-ID of aanvraag-ID
  context: 'aanvraag' | 'berekening';
  onImported?: () => void;
}
```

**Banner tonen:** altijd als `data.toon_banner === true`. Niet verbergen op basis van nieuw/afwijkend. Geen localStorage dismissal.

**Banner tekst:**
- Als er nieuwe/afwijkende velden zijn: "6 nieuwe velden beschikbaar uit documenten"
- Als alles bevestigd is: "Alle velden uit documenten zijn geïmporteerd" (informatief)
- Als `targetId` ontbreekt (nieuwe berekening nog niet opgeslagen): "Sla eerst op om documentgegevens te importeren"

**"Importeer" knop:** alleen tonen als `targetId` aanwezig is EN er nieuwe/afwijkende velden zijn.

### 3. Aankoop.tsx — berekeningId als targetId

```tsx
{dossierId && (
  <ImportBanner
    dossierId={dossierId}
    targetId={berekeningId || undefined}  // NIET dossierId als fallback!
    context="berekening"
    onImported={() => window.location.reload()}
  />
)}
```

**Belangrijk:** als `berekeningId` null is (nieuwe berekening, nog niet opgeslagen), stuur `undefined`. De banner toont dan "Sla eerst op om documentgegevens te importeren".

### 4. Aanpassen.tsx — zelfde

```tsx
{dossierId && (
  <ImportBanner
    dossierId={dossierId}
    targetId={berekeningId || undefined}
    context="berekening"
    onImported={() => window.location.reload()}
  />
)}
```

### 5. Aanvraag.tsx — banner toevoegen

Op de aanvraag-pagina, voeg de ImportBanner toe met `context="aanvraag"`:

```tsx
{dossierId && aanvraagId && (
  <ImportBanner
    dossierId={dossierId}
    targetId={aanvraagId}
    context="aanvraag"
    onImported={() => window.location.reload()}
  />
)}
```

Hier is `aanvraagId` altijd beschikbaar (de aanvraag bestaat al in Supabase).

### 6. DossierDetail.tsx — banner weg

Verwijder de ImportBanner van DossierDetail. Alleen op berekening- en aanvraag-pagina's.

### 7. ImportDialog.tsx — target_id in POST

In de `handleImport` functie, gebruik `target_id` (was impliciet via props):

```tsx
body: JSON.stringify({
  target_id: targetId,    // berekening-ID of aanvraag-ID
  context,
  selected_targets: Array.from(selectedTargets),
}),
```

---

## Verificatie

| # | Check | Verwacht |
|---|-------|----------|
| 1 | Bestaande berekening met data | Banner: "6 velden beschikbaar", knop "Importeer" |
| 2 | Na import + page reload | Waarden staan in formulier, banner toont "bevestigd" |
| 3 | Nieuwe berekening (niet opgeslagen) | Banner: "Sla eerst op om documentgegevens te importeren" |
| 4 | Na opslaan nieuwe berekening | Banner wordt actief met import-knop |
| 5 | Aanvraag-pagina | Banner met alle ~46 velden |
| 6 | DossierDetail | Geen ImportBanner |
| 7 | Geen TypeScript fouten | `npm run build` slaagt |

## Samenvatting bestanden

| Bestand | Actie | Wijziging |
|---------|-------|-----------|
| `src/hooks/useAvailableImports.ts` | Wijzig | `target_id` param (was `aanvraag_id`) |
| `src/components/dossier/ImportBanner.tsx` | Wijzig | `toon_banner`, geen dismissal, tekst voor niet-opgeslagen |
| `src/components/dossier/ImportDialog.tsx` | Wijzig | `target_id` in POST body |
| `src/pages/Aankoop.tsx` | Wijzig | `targetId={berekeningId \|\| undefined}` |
| `src/pages/Aanpassen.tsx` | Wijzig | `targetId={berekeningId \|\| undefined}` |
| `src/pages/Aanvraag.tsx` | Wijzig | ImportBanner toevoegen met context="aanvraag" |
| `src/pages/DossierDetail.tsx` | Wijzig | ImportBanner verwijderen |
