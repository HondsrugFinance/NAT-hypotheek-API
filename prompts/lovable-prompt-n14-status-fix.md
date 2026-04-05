# N14 — Fix: document status is "extracted", niet "verwerkt"

## Probleem

De "Vooringevuld uit documenten" optie verschijnt niet in de NieuweAanvraagDialog omdat `hasDocumenten` altijd `false` is. De Supabase query in DossierDetail.tsx filtert op `status = 'verwerkt'`, maar de backend slaat documenten op met status `'extracted'`.

## Fix

In `DossierDetail.tsx`, verander de query:

```tsx
// Was:
.eq('status', 'verwerkt')

// Wordt:
.eq('status', 'extracted')
```

---

## Verificatie

| # | Check | Verwacht |
|---|-------|----------|
| 1 | Dossier met verwerkte documenten | "Vooringevuld uit documenten" optie verschijnt |
| 2 | Dossier zonder documenten | Geen optie |

## Samenvatting bestanden

| Bestand | Wijziging |
|---------|-----------|
| `src/pages/DossierDetail.tsx` | `'verwerkt'` → `'extracted'` in documents query |
