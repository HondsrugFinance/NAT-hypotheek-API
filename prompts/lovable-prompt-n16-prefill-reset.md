# N16 — Fix: prefill=true moet isInitialized resetten

## Probleem

Bij navigatie naar `/aanvraag/XXX?prefill=true` wordt de prefill niet uitgevoerd als de component al eerder geladen was (React hergebruikt de component, `isInitialized` is `true`).

## Fix

In `Aanvraag.tsx`, reset `isInitialized` wanneer de URL verandert:

```tsx
// Voeg toe, NA de bestaande useEffect die isInitialized checkt:
useEffect(() => {
  // Reset bij navigatie met nieuwe params (bijv. prefill=true)
  setIsInitialized(false);
  setStoredAanvraag(null);
}, [dossierId, prefillParam]);
```

Dit zorgt ervoor dat bij elke navigatie naar de aanvraag-pagina (met of zonder prefill) de data opnieuw geladen wordt.

**Belangrijk:** plaats deze useEffect VÓÓR de loadAanvraag useEffect, zodat de reset eerst plaatsvindt.

---

## Verificatie

| # | Check | Verwacht |
|---|-------|----------|
| 1 | Dossier → "Nieuwe aanvraag" → "Vooringevuld" | Prefill data geladen (nieuwe prompt) |
| 2 | Tweede keer "Vooringevuld" | Opnieuw prefill data geladen (niet cached component) |

## Samenvatting bestanden

| Bestand | Wijziging |
|---------|-----------|
| `src/pages/Aanvraag.tsx` | Reset useEffect bij dossierId/prefillParam wijziging |
