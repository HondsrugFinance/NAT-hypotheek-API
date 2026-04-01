# N3 — Fix: pagina-data herladen na import

## Probleem

Na het importeren van velden (via "Importeer geselecteerde") worden de waarden opgeslagen in Supabase, maar de formulier-state wordt niet bijgewerkt. Het inkomen blijft op €66.834 staan terwijl €68.351 geïmporteerd is.

**Oorzaak:** De `onImported` callback in Aanpassen.tsx (en Aankoop.tsx) zet alleen `setInvoer()`, maar bij Aanpassen zit het inkomen in `haalbaarheidsBerekeningen` — een aparte state.

## Fix

### Aanpassen.tsx — regel ~728

Huidige code:
```tsx
onImported={() => {
  if (dossierId) {
    getDossier(dossierId).then(d => {
      if (d && d.type === 'aanpassen') {
        setInvoer((d as AanpassenDossier).invoer);
      }
    });
  }
}}
```

Vervang door:
```tsx
onImported={() => {
  if (dossierId) {
    getDossier(dossierId).then(d => {
      if (d && d.type === 'aanpassen') {
        const savedInvoer = (d as AanpassenDossier).invoer;
        setInvoer(savedInvoer);
        if (savedInvoer.haalbaarheidsBerekeningen?.length > 0) {
          setHaalbaarheidsBerekeningen(savedInvoer.haalbaarheidsBerekeningen);
        }
        if (savedInvoer.wijzigingBerekeningen?.length > 0) {
          setWijzigingBerekeningen(savedInvoer.wijzigingBerekeningen);
        }
      }
    });
  }
}}
```

### Aankoop.tsx — zelfde patroon

Huidige code:
```tsx
onImported={() => {
  if (dossierId) {
    getDossier(dossierId).then(d => {
      if (d && d.type === 'aankoop') {
        setInvoer((d as AankoopDossier).invoer);
      }
    });
  }
}}
```

Vervang door:
```tsx
onImported={() => {
  if (dossierId) {
    getDossier(dossierId).then(d => {
      if (d && d.type === 'aankoop') {
        const savedInvoer = (d as AankoopDossier).invoer;
        setInvoer(savedInvoer);
        if (savedInvoer.haalbaarheidsBerekeningen?.length > 0) {
          setHaalbaarheidsBerekeningen(savedInvoer.haalbaarheidsBerekeningen);
        }
      }
    });
  }
}}
```

---

## Verificatie

| # | Check | Verwacht |
|---|-------|----------|
| 1 | Importeer IBL toetsinkomen (€68.351) | Inkomensveld in formulier toont €68.351 na import |
| 2 | Importeer WOZ-waarde (€326.000) | WOZ-veld in formulier toont €326.000 na import |
| 3 | Importeer energielabel | Energielabel dropdown is bijgewerkt |
| 4 | Geen TypeScript fouten | `npm run build` slaagt |

## Samenvatting bestanden

| Bestand | Wijziging |
|---------|-----------|
| `src/pages/Aanpassen.tsx` | onImported: ook setHaalbaarheidsBerekeningen + setWijzigingBerekeningen |
| `src/pages/Aankoop.tsx` | onImported: ook setHaalbaarheidsBerekeningen |
