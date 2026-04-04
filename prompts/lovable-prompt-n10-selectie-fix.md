# N10 — Fix: afwijkende velden ook default aangevinkt

## Probleem

Alleen "nieuwe" velden worden default aangevinkt. Maar "afwijkende" velden (oranje driehoek) moeten OOK default geselecteerd zijn. De adviseur kan ze uitzetten als hij de huidige waarde wil behouden.

## Fix

In `ImportDialog.tsx`, de useEffect die velden pre-selecteert:

```tsx
// Was:
useEffect(() => {
  if (open && data) {
    const newTargets = new Set<string>();
    for (const item of data.imports) {
      if (item.status === 'nieuw') newTargets.add(item.pad);
    }
    setSelectedTargets(newTargets);
  }
}, [open, data]);

// Wordt:
useEffect(() => {
  if (open && data) {
    const newTargets = new Set<string>();
    for (const item of data.imports) {
      if (item.status === 'nieuw' || item.status === 'afwijkend') {
        newTargets.add(item.pad);
      }
    }
    setSelectedTargets(newTargets);
  }
}, [open, data]);
```

Doe hetzelfde voor de "Selecteer alle nieuwe" toggle — hernoem naar "Selecteer alle":

```tsx
// Was:
const toggleAllNew = (checked: boolean) => {
  // ... alleen status === 'nieuw'

// Wordt:
const toggleAll = (checked: boolean) => {
  setSelectedTargets(prev => {
    const next = new Set(prev);
    for (const item of data.imports) {
      if (item.status === 'nieuw' || item.status === 'afwijkend') {
        if (checked) next.add(item.pad);
        else next.delete(item.pad);
      }
    }
    return next;
  });
};
```

En het label:
```tsx
// Was: "Selecteer alle nieuwe"
// Wordt: "Selecteer alle"
```

---

## Verificatie

| # | Check | Verwacht |
|---|-------|----------|
| 1 | Dialog opent | Nieuwe EN afwijkende velden zijn aangevinkt |
| 2 | "Selecteer alle" toggle | Schakelt nieuwe + afwijkende velden |
| 3 | Bevestigde velden | Niet selecteerbaar (geen checkbox) |

## Samenvatting bestanden

| Bestand | Wijziging |
|---------|-----------|
| `src/components/dossier/ImportDialog.tsx` | Pre-selecteer ook afwijkende velden, hernoem toggle |
