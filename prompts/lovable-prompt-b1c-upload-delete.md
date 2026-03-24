# B1c — Documenten uploaden (drag & drop) en verwijderen

## Context

De DocumentenTab toont al bestanden uit de klantmap. Nu voegen we upload (drag & drop + knop) en verwijderen toe. De backend endpoints zijn:

```
POST ${API_CONFIG.NAT_API_URL}/sharepoint/klantmap/{dossier_id}/upload
  Content-Type: multipart/form-data
  Field: file (bestand)
  Response: { name, id, size, web_url }

DELETE ${API_CONFIG.NAT_API_URL}/sharepoint/klantmap/item/{item_id}
  Response: { status: "ok", deleted: "..." }
```

---

## Wat moet er gebeuren

### 1. Upload functionaliteit toevoegen aan DocumentenTab

**Drag & drop zone:**
- De hele DocumentenTab card wordt een drop zone
- Bij dragover: subtiele visuele feedback (bijv. `border-2 border-dashed border-primary/50 bg-accent/30`)
- Bij drop: upload het bestand
- Onderaan de bestandenlijst: een "+ Document toevoegen" knop die een file picker opent

**Upload logica:**

```typescript
async function uploadBestand(dossierId: string, file: File) {
  const { data: { session } } = await supabase.auth.getSession();
  const formData = new FormData();
  formData.append('file', file);

  const resp = await fetch(
    `${API_CONFIG.NAT_API_URL}/sharepoint/klantmap/${dossierId}/upload`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${session?.access_token ?? ''}`,
      },
      body: formData,
    }
  );

  if (!resp.ok) {
    throw new Error('Upload mislukt');
  }
  return resp.json();
}
```

**Na upload:** toast "Bestand geüpload" + automatisch refresh van de bestandenlijst.

**Meerdere bestanden tegelijk:** Als meerdere bestanden worden gesleept, upload ze één voor één en refresh daarna.

**Upload status:** Toon een kleine progress indicator (bijv. spinner naast de bestandsnaam) tijdens upload.

### 2. Verwijder functionaliteit

**Per bestand:** Een prullenbak-icoon (`Trash2` van Lucide) aan de rechterkant van elke rij, alleen zichtbaar bij hover.

**Bij klik:** Bevestigingsdialoog: "Weet je zeker dat je {bestandsnaam} wilt verwijderen?"

**Delete logica:**

```typescript
async function verwijderBestand(itemId: string) {
  const { data: { session } } = await supabase.auth.getSession();
  const resp = await fetch(
    `${API_CONFIG.NAT_API_URL}/sharepoint/klantmap/item/${itemId}`,
    {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${session?.access_token ?? ''}`,
      },
    }
  );

  if (!resp.ok) {
    throw new Error('Verwijderen mislukt');
  }
}
```

**Na verwijderen:** toast "Bestand verwijderd" + automatisch refresh.

### 3. Layout update

```
┌─────────────────────────────────────────────────────────────────┐
│  Documenten (7)                              [↻] [Open in SP]  │
│                                                                  │
│  📄 IBL Walter.pdf          92 kB   24-03 14:43  A. Kuijper  🗑 │
│  📄 IBL_resultaat_20...pdf  84 kB   24-03 14:43  A. Kuijper  🗑 │
│  📄 Hypotheek ING.pdf       73 kB   24-03 14:38  A. Kuijper  🗑 │
│  ...                                                             │
│                                                                  │
│  ┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐  │
│  │     Sleep bestanden hierheen of klik om te uploaden       │  │
│  └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘  │
└─────────────────────────────────────────────────────────────────┘
```

**Upload zone onderaan:**
- Stippellijn-border, subtiele tekst "Sleep bestanden hierheen of klik om te uploaden"
- `text-muted-foreground text-sm`
- Bij hover: `bg-accent/30`
- Bevat een verborgen `<input type="file" multiple>` die opent bij klik
- Accepteert: PDF, JPG, PNG, TIFF, DOCX, XLSX

**Prullenbak-icoon:**
- `Trash2` icoon, `h-4 w-4`, `text-muted-foreground hover:text-destructive`
- Alleen zichtbaar bij hover op de rij (`opacity-0 group-hover:opacity-100`)

---

## Verificatie

| # | Check | Verwacht |
|---|-------|----------|
| 1 | Sleep een PDF naar het documenten-overzicht | Upload start, bestand verschijnt na refresh |
| 2 | Klik op upload zone | File picker opent, upload na selectie |
| 3 | Upload meerdere bestanden tegelijk | Alle worden geüpload, lijst refresht |
| 4 | Klik prullenbak-icoon | Bevestigingsdialoog, na bevestiging wordt bestand verwijderd |
| 5 | Upload een te groot bestand (>25MB) | Foutmelding |
| 6 | Geen TypeScript fouten | `npm run build` slaagt |

## Samenvatting bestanden

| Bestand | Actie | Wijziging |
|---------|-------|-----------|
| `src/components/dossier/DocumentenTab.tsx` | Wijzig | + drag & drop upload zone + verwijder-icoon + bevestigingsdialoog |
| `src/hooks/useKlantmapBestanden.ts` | Wijzig | + upload en delete functies (of aparte hook) |
