# N12 — Vooringevulde aanvraag uit documenten

## Context

Bij het aanmaken van een nieuwe aanvraag wordt nu een leeg formulier of een kopie van een berekening getoond. De adviseur moet alles handmatig invullen.

**Nieuw:** de backend biedt een endpoint dat een **vooringevuld AanvraagData object** retourneert op basis van geëxtraheerde documentdata. Alle beschikbare informatie (naam, geboortedatum, legitimatie, werkgever, inkomen, onderpand, hypotheekdelen, etc.) staat direct in het formulier.

### API Endpoint

```
GET /doc-processing/{dossier_id}/prefill-aanvraag
```

Response:
```json
{
  "prefill_data": { ... AanvraagData object ... },
  "velden_count": 50,
  "cached": true,
  "dossier_id": "..."
}
```

`prefill_data` is een kant-en-klaar AanvraagData object dat direct als startdata voor `createAanvraag()` gebruikt kan worden.

---

## Wat moet er veranderen

### 1. NieuweAanvraagDialog.tsx — optie "Vooringevuld uit documenten"

Voeg een derde optie toe in de dialog, **boven** de bestaande opties:

```tsx
{/* Vooringevuld uit documenten — alleen tonen als dossier documenten heeft */}
<label
  className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
    selected === 'prefill' ? 'border-primary bg-primary/5' : 'hover:bg-muted/50'
  }`}
>
  <RadioGroupItem value="prefill" />
  <div className="h-8 w-8 rounded-md flex items-center justify-center shrink-0 bg-green-100 text-green-700">
    <FileCheck className="h-4 w-4" />
  </div>
  <div>
    <p className="font-medium text-sm">Vooringevuld uit documenten</p>
    <p className="text-xs text-muted-foreground">
      Alle beschikbare gegevens uit verwerkte documenten staan direct in het formulier
    </p>
  </div>
</label>
```

Import `FileCheck` van Lucide.

**Default selectie:** als er verwerkte documenten zijn, selecteer "prefill" als default i.p.v. "blanco".

### 2. NieuweAanvraagDialog.tsx — handleVolgende aanpassen

```tsx
const handleVolgende = async () => {
  if (selected === 'prefill') {
    onClose();
    // Navigeer met prefill flag
    navigate(`/aanvraag/${primaryDossierId}?prefill=true`);
  } else if (selected === 'blanco') {
    onClose();
    navigate(`/aanvraag/${primaryDossierId}`);
  } else {
    onClose();
    navigate(`/aanvraag/${selected}?fromBerekening=true`);
  }
};
```

### 3. Aanvraag.tsx — prefill data ophalen

In de `loadAanvraag` useEffect, check de `prefill` query param:

```tsx
const prefillParam = searchParams.get('prefill');

// Na het laden van het dossier, als prefill=true en geen bestaande aanvraag:
if (prefillParam === 'true' && !existingAanvraag && dossierId) {
  try {
    const { data: { session } } = await supabase.auth.getSession();
    const resp = await window.fetch(
      `${API_CONFIG.NAT_API_URL}/doc-processing/${dossierId}/prefill-aanvraag`,
      { headers: { 'Authorization': `Bearer ${session?.access_token ?? ''}` } }
    );
    if (resp.ok) {
      const result = await resp.json();
      if (result.prefill_data && Object.keys(result.prefill_data).length > 0) {
        setAanvraagData(sanitizeAanvraagData(result.prefill_data));
        toast({ title: `${result.velden_count} velden vooringevuld uit documenten` });
      }
    }
  } catch {
    // Stille fallback naar leeg formulier
  }
}
```

### 4. DossierDetail.tsx — check of documenten beschikbaar zijn

De NieuweAanvraagDialog moet weten of er verwerkte documenten zijn. Voeg een prop toe:

```tsx
<NieuweAanvraagDialog
  open={nieuweAanvraagDialogOpen}
  onClose={() => setNieuweAanvraagDialogOpen(false)}
  primaryDossierId={primaryDossier.id}
  relatedDossiers={relatedDossiers}
  berekeningNames={numberedNames}
  hasDocumenten={documenten.length > 0}  // NIEUW
/>
```

In NieuweAanvraagDialog: toon de "Vooringevuld" optie alleen als `hasDocumenten` true is. Als er geen documenten zijn, default naar "blanco".

### 5. Import banner op aanvraag-pagina — delta-only

De bestaande ImportBanner op de aanvraag-pagina (context="aanvraag") hoeft niet meer alle 50 velden te tonen. Na prefill zijn de meeste al ingevuld.

De banner toont alleen:
- **Na eerste prefill:** "Alle beschikbare gegevens zijn ingevuld" (informatief, geen actie)
- **Na nieuwe documenten:** "3 nieuwe velden beschikbaar" (alleen de delta)

Dit werkt al automatisch: de `available-imports` vergelijkt met de huidige aanvraag-data en toont alleen nieuwe/afwijkende velden.

---

## Verificatie

| # | Check | Verwacht |
|---|-------|----------|
| 1 | Dossier met documenten → "Nieuwe aanvraag" | "Vooringevuld" optie bovenaan, default geselecteerd |
| 2 | Klik "Volgende" met prefill | Aanvraag opent met alle velden ingevuld |
| 3 | Toast melding | "50 velden vooringevuld uit documenten" |
| 4 | Formulier doorlopen | Klantgegevens, legitimatie, werkgever, inkomen staan er |
| 5 | Dossier zonder documenten | Geen "Vooringevuld" optie, default "blanco" |
| 6 | Na nieuwe documenten uploaden | Banner toont alleen delta |
| 7 | Geen TypeScript fouten | `npm run build` slaagt |

## Samenvatting bestanden

| Bestand | Actie | Wijziging |
|---------|-------|-----------|
| `src/components/NieuweAanvraagDialog.tsx` | Wijzig | Optie "Vooringevuld uit documenten" + hasDocumenten prop |
| `src/pages/Aanvraag.tsx` | Wijzig | Prefill data ophalen bij `?prefill=true` |
| `src/pages/DossierDetail.tsx` | Wijzig | hasDocumenten prop meegeven |
