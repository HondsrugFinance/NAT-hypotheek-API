# N7 — Fix: DossierDetail links moeten berekeningId bevatten

## Probleem

De links vanuit DossierDetail naar berekeningen bevatten alleen `dossierId` maar niet `berekeningId`. Hierdoor is `berekeningId` null op de berekening-pagina en werkt de import-banner niet.

**Huidige link:** `/aanpassen?dossierId=XXX`
**Moet worden:** `/aanpassen?dossierId=XXX&berekeningId=YYY`

## Fix

In `DossierDetail.tsx`, waar de berekening-links worden gerenderd:

De berekeningen worden nu uit de `berekeningen` tabel geladen (via `fetchBerekeningenByDossier`). Elke berekening heeft een eigen `id`. Gebruik dat als `berekeningId` in de link.

```tsx
// Was (vermoedelijk):
<Link to={`/aanpassen?dossierId=${primaryDossier.id}`}>

// Wordt:
<Link to={`/${berekening.type}?dossierId=${primaryDossier.id}&berekeningId=${berekening.id}`}>
```

Dit geldt voor alle plekken waar naar een berekening gelinkt wordt — zowel bij het klikken op een bestaande berekening als bij "Nieuwe berekening".

Bij "Nieuwe berekening" (nog niet opgeslagen) is er geen `berekeningId` — dat is correct, de banner toont dan "Sla eerst op".

---

## Verificatie

| # | Check | Verwacht |
|---|-------|----------|
| 1 | Klik op bestaande berekening in DossierDetail | URL bevat `berekeningId=...` |
| 2 | Import banner verschijnt | Banner toont velden uit documenten |
| 3 | Nieuwe berekening | Banner toont "Sla eerst op" |
| 4 | Na opslaan nieuwe berekening | URL bevat `berekeningId`, banner wordt actief |

## Samenvatting bestanden

| Bestand | Wijziging |
|---------|-----------|
| `src/pages/DossierDetail.tsx` | Links naar berekeningen met `berekeningId` parameter |
