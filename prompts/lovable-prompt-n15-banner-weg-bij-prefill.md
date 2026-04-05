# N15 — Verberg import-banner bij prefill aanvraag

## Probleem

Na "Vooringevuld uit documenten" toont de banner "Sla eerst op om documentgegevens te importeren". Maar de data IS al vooringevuld — de banner is verwarrend en overbodig.

## Fix

In `Aanvraag.tsx`, voeg de `prefill` check toe aan de ImportBanner conditie:

```tsx
// Was:
{dossierId && (
  <ImportBanner ... />
)}

// Wordt:
{dossierId && !searchParams.get('prefill') && (
  <ImportBanner ... />
)}
```

Bij `?prefill=true` wordt de banner helemaal niet getoond. Na opslaan (redirect zonder `?prefill`) verschijnt de banner weer normaal.

---

## Verificatie

| # | Check | Verwacht |
|---|-------|----------|
| 1 | Vooringevulde aanvraag | Geen import-banner |
| 2 | Bestaande aanvraag (zonder prefill) | Import-banner normaal zichtbaar |

## Samenvatting bestanden

| Bestand | Wijziging |
|---------|-----------|
| `src/pages/Aanvraag.tsx` | Hide ImportBanner bij `?prefill=true` |
