# N11 — Import banner op aanvraag-pagina ook zonder opgeslagen aanvraag

## Probleem

De ImportBanner op de aanvraag-pagina verschijnt alleen als `storedAanvraag` niet null is. Bij een nieuwe (nog niet opgeslagen) aanvraag is `storedAanvraag` null → geen banner.

## Fix

In `Aanvraag.tsx`, verander de conditie:

```tsx
// Was:
{dossierId && storedAanvraag && (
  <ImportBanner
    dossierId={dossierId}
    targetId={storedAanvraag.id}
    context="aanvraag"
    onImported={() => window.location.reload()}
  />
)}

// Wordt:
{dossierId && (
  <ImportBanner
    dossierId={dossierId}
    targetId={storedAanvraag?.id || undefined}
    context="aanvraag"
    onImported={() => window.location.reload()}
  />
)}
```

Als `storedAanvraag` null is, stuurt de banner `targetId={undefined}` en toont "Sla eerst op om documentgegevens te importeren" (dit gedrag zit al in ImportBanner.tsx).

---

## Verificatie

| # | Check | Verwacht |
|---|-------|----------|
| 1 | Nieuwe aanvraag (niet opgeslagen) | Banner: "Sla eerst op..." |
| 2 | Na opslaan | Banner met import-velden |
| 3 | Bestaande aanvraag | Banner met import-velden |

## Samenvatting bestanden

| Bestand | Wijziging |
|---------|-----------|
| `src/pages/Aanvraag.tsx` | Verwijder `storedAanvraag &&` check, gebruik `storedAanvraag?.id` |
