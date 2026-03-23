# B1 — Dossiernummer, status en SharePoint-link in dossier-overzicht

## Context

We hebben het Supabase `dossiers` tabel uitgebreid met drie nieuwe kolommen:
- `dossiernummer` (TEXT, auto-gegenereerd: "2026-0001", "2026-0002", etc.)
- `status` (TEXT, default "orientatie", opties: orientatie, documenten_verzamelen, berekening, aanvraag, offerte, passeren, nazorg, afgerond)
- `sharepoint_url` (TEXT, URL naar de klantmap op SharePoint)

Deze kolommen worden automatisch gevuld door de backend. De frontend moet ze tonen.

---

## Wat moet er gebeuren

### 1. Dossier TypeScript types uitbreiden

In `src/types/hypotheek.ts`, voeg toe aan BEIDE `AankoopDossier` en `AanpassenDossier`:

```typescript
export interface AankoopDossier {
  // ... bestaande velden ...
  dossiernummer?: string;
  status?: string;
  sharepointUrl?: string;
}
```

Idem voor `AanpassenDossier`.

### 2. Supabase mapping uitbreiden

In `src/services/supabaseDossierService.ts`, breid de mapping functies uit:

**`mapRowToDossier`** — voeg toe:
```typescript
dossiernummer: row.dossiernummer ?? undefined,
status: row.status ?? 'orientatie',
sharepointUrl: row.sharepoint_url ?? undefined,
```

**`mapDossierToRow`** — voeg toe:
```typescript
// NIET meesturen bij upsert: dossiernummer, status, sharepoint_url
// Deze worden door de backend/triggers beheerd
```

**Let op:** `dossiernummer`, `status` en `sharepoint_url` worden NIET meegestuurd bij upsert. Ze zijn read-only vanuit de frontend. De backend (triggers en webhooks) beheert deze velden.

### 3. Dossier-overzicht pagina (`/dossiers`)

Toon het **dossiernummer** en de **status** in de dossierlijst.

**Per dossier-kaart, voeg toe:**

```tsx
{/* Dossiernummer — links van de klantnaam */}
{dossier.dossiernummer && (
  <span className="text-xs text-muted-foreground font-mono mr-2">
    {dossier.dossiernummer}
  </span>
)}

{/* Status badge — rechts */}
{dossier.status && dossier.status !== 'orientatie' && (
  <Badge variant="outline" className="text-xs">
    {statusLabels[dossier.status]}
  </Badge>
)}
```

**Status labels mapping:**
```typescript
const statusLabels: Record<string, string> = {
  orientatie: 'Oriëntatie',
  documenten_verzamelen: 'Documenten',
  berekening: 'Berekening',
  aanvraag: 'Aanvraag',
  offerte: 'Offerte',
  passeren: 'Passeren',
  nazorg: 'Nazorg',
  afgerond: 'Afgerond',
};
```

### 4. Dossier-detail pagina — SharePoint knop

Op de dossier-pagina (waar het dossier wordt bewerkt), voeg een **"Open klantmap"** knop toe in de header/toolbar:

```tsx
{dossier.sharepointUrl && (
  <Button
    variant="outline"
    size="sm"
    onClick={() => window.open(dossier.sharepointUrl, '_blank')}
    className="gap-1.5"
  >
    <FolderOpen className="h-4 w-4" />
    Klantmap
  </Button>
)}
```

Gebruik het `FolderOpen` icoon van Lucide. De knop verschijnt alleen als er een SharePoint URL is.

Plaats deze knop naast de bestaande knoppen (Samenvatting PDF, E-mail, etc.).

### 5. Status dropdown (optioneel maar handig)

Op de dossier-detail pagina, voeg een **status dropdown** toe waarmee de adviseur de status kan wijzigen:

```tsx
<Select
  value={dossier.status || 'orientatie'}
  onValueChange={async (newStatus) => {
    // Update direct in Supabase (niet via dossier upsert)
    const { error } = await supabase
      .from('dossiers')
      .update({ status: newStatus })
      .eq('id', dossier.id);

    if (!error) {
      toast({ title: `Status gewijzigd naar ${statusLabels[newStatus]}` });
      // Refresh dossier data
    }
  }}
>
  <SelectTrigger className="w-[180px]">
    <SelectValue />
  </SelectTrigger>
  <SelectContent>
    {Object.entries(statusLabels).map(([value, label]) => (
      <SelectItem key={value} value={value}>{label}</SelectItem>
    ))}
  </SelectContent>
</Select>
```

---

## Verificatie

| # | Check | Verwacht |
|---|-------|----------|
| 1 | Open `/dossiers` | Dossiernummers zichtbaar naast klantnamen |
| 2 | Open een dossier met sharepoint_url | "Klantmap" knop zichtbaar, opent SharePoint in nieuw tabblad |
| 3 | Wijzig status via dropdown | Toast bevestiging, status badge update |
| 4 | Dossier zonder sharepoint_url | Geen "Klantmap" knop (geen fout) |
| 5 | Geen TypeScript compilatiefouten | `npm run build` slaagt |

## Samenvatting bestanden

| Bestand | Actie | Wijziging |
|---------|-------|-----------|
| `src/types/hypotheek.ts` | Wijzig | + `dossiernummer`, `status`, `sharepointUrl` op beide interfaces |
| `src/services/supabaseDossierService.ts` | Wijzig | + mapping voor nieuwe velden (read-only) |
| Dossier-overzicht component | Wijzig | + dossiernummer + status badge |
| Dossier-detail pagina | Wijzig | + "Klantmap" knop + status dropdown |
