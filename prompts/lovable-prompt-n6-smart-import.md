# N6 — Smart import: veld-key heet nu "pad"

## Kleine API wijziging

De backend gebruikt nu Claude AI om velden te mappen (slimmer, meer velden, hypotheekdelen). De API endpoints zijn hetzelfde, maar het veld-object heeft een kleine wijziging:

**Was:** `item.target` (bijv. `"klantGegevens.achternaamAanvrager"`)
**Wordt:** `item.pad` (bijv. `"aanvrager.persoon.achternaam"`)

### Wijzigingen in ImportDialog.tsx

Overal waar `item.target` staat, vervang door `item.pad`:

```tsx
// Checkbox toggle
const toggleField = (pad: string) => { ... }
selectedTargets.has(item.pad)

// POST body
selected_targets: Array.from(selectedTargets)

// Key in map
<div key={item.pad} ...>
```

### Wijzigingen in useAvailableImports.ts

Het interface `ImportVeld` wijzigt:

```typescript
interface ImportVeld {
  pad: string;              // was: target
  label: string;
  waarde: any;              // ruwe waarde (NIEUW)
  waarde_display: string;
  bron: string;             // bron-document (NIEUW, bijv. "paspoort")
  status: 'nieuw' | 'bevestigd' | 'afwijkend';
  waarde_huidig?: any;      // alleen bij afwijkend
  huidig_display?: string;  // alleen bij afwijkend
}
```

De rest (groepen, samenvatting, toon_banner, POST endpoint) is identiek.

---

## Verificatie

| # | Check | Verwacht |
|---|-------|----------|
| 1 | Dialog opent | Velden met label + waarde_display |
| 2 | Importeer velden | POST met selected_targets (pad-waarden) |
| 3 | Geen TypeScript fouten | `npm run build` slaagt |

## Samenvatting bestanden

| Bestand | Wijziging |
|---------|-----------|
| `src/hooks/useAvailableImports.ts` | `target` → `pad` in interface |
| `src/components/dossier/ImportDialog.tsx` | `item.target` → `item.pad` |
