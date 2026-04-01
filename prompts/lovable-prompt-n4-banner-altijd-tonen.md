# N4 — Banner altijd tonen + data herladen na import

## Probleem 1: Banner verdwijnt na import

De ImportBanner verdwijnt als alle velden "bevestigd" zijn. Maar de gebruiker wil de banner altijd zien als er verwerkte documenten zijn — ook bij een nieuwe berekening voor hetzelfde dossier.

**Fix in `ImportBanner.tsx`:**

De API stuurt nu `toon_banner: true` mee als er velden beschikbaar zijn. Gebruik dit i.p.v. de nieuw/afwijkend check:

```tsx
// Was:
if (loading || !data || (data.samenvatting.nieuw === 0 && data.samenvatting.afwijkend === 0)) {
  return null;
}

// Wordt:
if (loading || !data || !data.toon_banner) {
  return null;
}
```

En verwijder de localStorage dismissal logica — de banner moet altijd zichtbaar blijven.

## Probleem 2: Data niet zichtbaar na import

Na import worden de velden opgeslagen maar het formulier toont de oude waarden. De `onImported` callback moet de volledige berekening-state herladen.

**Fix in `Aanpassen.tsx` — onImported callback:**

De huidige code roept `fetchBerekeningById` aan, maar de `setInvoer` alleen is niet genoeg. De pagina moet volledig herladen worden:

```tsx
onImported={() => {
  // Volledige pagina refresh om alle state correct te laden
  window.location.reload();
}}
```

Dit is een tijdelijke maar betrouwbare oplossing. Een `window.location.reload()` herlaadt alle state uit Supabase.

**Zelfde fix in `Aankoop.tsx`:**

```tsx
onImported={() => {
  window.location.reload();
}}
```

---

## Verificatie

| # | Check | Verwacht |
|---|-------|----------|
| 1 | Banner na import | Banner blijft zichtbaar, velden staan als "bevestigd" |
| 2 | Nieuwe berekening voor zelfde dossier | Banner verschijnt met "niet ingevuld" |
| 3 | Na import: pagina herlaadt | Geïmporteerde waarden zichtbaar in formulier |
| 4 | Geen TypeScript fouten | `npm run build` slaagt |

## Samenvatting bestanden

| Bestand | Wijziging |
|---------|-----------|
| `src/components/dossier/ImportBanner.tsx` | Gebruik `toon_banner` i.p.v. nieuw/afwijkend check, verwijder localStorage dismissal |
| `src/pages/Aanpassen.tsx` | onImported: `window.location.reload()` |
| `src/pages/Aankoop.tsx` | onImported: `window.location.reload()` |
