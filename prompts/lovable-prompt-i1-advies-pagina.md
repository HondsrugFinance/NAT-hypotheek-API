# Lovable Prompt I1: Adviesrapport — Volledige pagina met bewerkbare teksten

> Dit prompt vervangt de huidige in-dialog adviesrapport wizard door een volwaardige pagina met twee sub-pagina's: Uitgangspunten en Adviesuitkomsten. De adviseur kan gegenereerde teksten bewerken voordat het rapport als PDF wordt gegenereerd.

---

## Overzicht van wijzigingen

1. **Supabase `adviezen` tabel** aanmaken
2. **Adviesrapport flow** omzetten van dialog naar volledige pagina met 2 stappen
3. **Preview endpoint** aanroepen voor teksten + scenario-bedragen
4. **Bewerkbare tekstvelden** per risico-sectie
5. **Adviezen weergeven** in dossier-overzicht met versioning
6. **Nieuw API endpoint**: `POST /adviesrapport-preview-v2` (JSON response)
7. **Bestaand endpoint uitgebreid**: `POST /adviesrapport-pdf-v2` accepteert `text_overrides`

---

## Deel A: Supabase — `adviezen` tabel

### A1. Maak de tabel aan

Ga naar Supabase SQL Editor en voer uit:

```sql
CREATE TABLE adviezen (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  dossier_id UUID NOT NULL REFERENCES dossiers(id) ON DELETE CASCADE,
  aanvraag_id UUID NOT NULL REFERENCES aanvragen(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES auth.users(id),
  naam TEXT NOT NULL DEFAULT '',
  options JSONB NOT NULL DEFAULT '{}',
  preview_data JSONB,
  text_overrides JSONB,
  generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_adviezen_dossier_id ON adviezen(dossier_id);

ALTER TABLE adviezen ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can select own adviezen"
  ON adviezen FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own adviezen"
  ON adviezen FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own adviezen"
  ON adviezen FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete own adviezen"
  ON adviezen FOR DELETE USING (auth.uid() = user_id);
```

### A2. TypeScript types

Voeg toe aan het type-bestand (bijv. `src/types/hypotheek.ts` of een nieuw `src/types/advies.ts`):

```typescript
export interface Advies {
  id: string;
  dossier_id: string;
  aanvraag_id: string;
  user_id: string;
  naam: string;                           // Bijv. "Aankoop: Bestaande bouw"
  options: AdviesrapportV2Options;         // Uitgangspunten (klantprofiel, risico, etc.)
  preview_data: AdviesPreviewResponse | null;  // Snapshot van preview response
  text_overrides: Record<string, SectionTextOverride> | null;
  generated_at: string;                   // ISO timestamp
  updated_at: string;
}

export interface SectionTextOverride {
  narratives?: string[];
  conclusion?: string[];
}

export interface AdviesPreviewResponse {
  meta: {
    customerName: string;
    advisor: string;
    date: string;
    dossierNumber: string;
    propertyAddress: string;
  };
  geadviseerd_hypotheekbedrag: number;
  max_hypotheek: number;
  bruto_maandlast: number;
  netto_maandlast: number;
  scenario_checks: Array<{
    label: string;
    status: string;
    status_class: string;
  }>;
  sections: AdviesPreviewSection[];
}

export interface AdviesPreviewSection {
  id: string;
  title: string;
  editable_texts: {
    narratives: string[];
    conclusion: string[];
  } | null;
  per_person: Array<{
    naam: string;
    label: string;
    max_hypotheek: number;
    werkelijke_hypotheek: number;
    verschil: number;
  }> | null;
}
```

---

## Deel B: Adviesrapport flow — Van dialog naar pagina

### B1. Aanvraag selectie (blijft dialog)

De huidige stap 1 (selecteer aanvraag als basis) blijft een dialog/modal. Dit is de "Selecteer aanvraag als basis" popup die al bestaat.

**Wijziging:** Na het selecteren van een aanvraag en klikken op "Volgende", navigeer naar de nieuwe pagina in plaats van stap 2 in de dialog te tonen:

```typescript
// In de "Volgende" handler na aanvraag-selectie:
navigate(`/dossier/${dossierId}/advies/nieuw?aanvraag=${selectedAanvraagId}`);
```

### B2. Nieuwe route registreren

Voeg twee routes toe aan de router:

```typescript
// Nieuw advies aanmaken
<Route path="/dossier/:dossierId/advies/nieuw" element={<AdviesPage />} />
// Bestaand advies bekijken/bewerken
<Route path="/dossier/:dossierId/advies/:adviesId" element={<AdviesPage />} />
```

### B3. AdviesPage component

Maak een nieuw component `src/pages/AdviesPage.tsx`. Dit is een volledige pagina (niet een dialog) met twee sub-pagina's, geschakeld via tabs of een stepper:

```typescript
// Pagina-header:
// ← Terug naar dossier | Adviesrapport samenstellen
// Aanvraag: [naam van de geselecteerde aanvraag]

// Sub-pagina 1: "Uitgangspunten" (tab/stap 1)
// Sub-pagina 2: "Adviesuitkomsten" (tab/stap 2)
```

**Navigatie:**
- Boven de content: breadcrumb of "← Terug naar dossier" link
- Twee tabs of stepper: "1. Uitgangspunten" en "2. Adviesuitkomsten"
- Tab 2 is pas beschikbaar nadat tab 1 is ingevuld en "Verder" is geklikt

---

## Deel C: Sub-pagina 1 — Uitgangspunten

### C1. Inhoud

Verplaats alle velden uit de huidige stap 2 van `AdviesrapportDialog.tsx` naar deze sub-pagina:

- **Klantprofiel**: Doel hypotheek, Ervaring, Kennis hypotheekvormen, Kennis fiscale regels, Prioriteit
- **Risicobereidheid**: 8 dropdowns (pensioen, overlijden, AO, werkloosheid, waardedaling, rentestijging, aflopen renteaftrek, relatiebeeindiging)
- **Geavanceerde risico-analyse instellingen** (collapsible): AO-percentage, benutting RVC, loondoorbetaling, arbeidsverleden
- **Rapport**: Adviseur (dropdown uit profiles), Datum (datepicker), Dossiernummer

### C2. Actieknoppen

- **"Verder"** knop rechtsonder → roept het preview endpoint aan (zie Deel D)
- **"Annuleren"** → navigeer terug naar dossier
- Bij een bestaand advies (route `/advies/:adviesId`): laad de opgeslagen `options` in de velden

---

## Deel D: Sub-pagina 2 — Adviesuitkomsten

### D1. API-call bij laden

Wanneer de gebruiker op "Verder" klikt op sub-pagina 1, roep het nieuwe preview endpoint aan:

```typescript
const response = await fetch(`${API_BASE_URL}/adviesrapport-preview-v2`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${supabaseSession.access_token}`,
  },
  body: JSON.stringify({
    dossier_id: dossierId,
    aanvraag_id: aanvraagId,
    options: uitgangspuntenFormData,  // Alles uit sub-pagina 1
  }),
});

const preview: AdviesPreviewResponse = await response.json();
```

**Toon een loading spinner** tijdens het laden (de berekeningen duren enkele seconden).

### D2. Weergave van secties

Loop over `preview.sections` en toon alleen secties waar `editable_texts !== null`. De volgorde is:

1. **Samenvatting advies** (`id: "summary"`)
2. **Pensioen** (`id: "retirement"`)
3. **Overlijden** (`id: "risk-death"`)
4. **Arbeidsongeschiktheid** (`id: "risk-disability"`)
5. **Werkloosheid** (`id: "risk-unemployment"`)
6. **Relatiebeeindiging** (`id: "risk-relationship"`)

Per sectie toon:

#### A. Sectie-titel
Gebruik `section.title` als heading (bijv. "Pensioen", "Overlijden").

#### B. Per-persoon bedragen (als `per_person !== null`)
Toon een compacte tabel of kaart:

```
┌─────────────────────────────────────────────────────────────┐
│ Harry                                                        │
│ Max. hypotheek: € 280.000  |  Werkelijk: € 338.173          │
│ Verschil: -/€ 58.173 (tekort)                                │
├─────────────────────────────────────────────────────────────┤
│ Harriette                                                    │
│ Max. hypotheek: € 250.000  |  Werkelijk: € 338.173          │
│ Verschil: -/€ 88.173 (tekort)                                │
└─────────────────────────────────────────────────────────────┘
```

Gebruik `formatBedrag()` voor bedragen. Toon "overschot" (groen) of "tekort" (oranje/rood) op basis van het teken van `verschil`. Gebruik `per_person[].label` als subtitel (bijv. "AOW aanvrager (15-06-2032)").

#### C. Bewerkbare tekstvelden

Toon twee bewerkbare blokken per sectie:

**Introductietekst** (`editable_texts.narratives`):
- Elke string in de array is een paragraaf
- Toon als een textarea (of meerdere textarea's, 1 per paragraaf)
- Standaard gevuld met de gegenereerde tekst
- Breedte: 100%, minimale hoogte: 3 regels, auto-resize

**Conclusie/adviestekst** (`editable_texts.conclusion`):
- Elke string is een paragraaf
- Toon als een textarea (of meerdere textarea's, 1 per paragraaf)
- Standaard gevuld met de gegenereerde tekst

**Labels boven de blokken:**
- "Introductie" voor narratives
- "Analyse & advies" voor conclusion

**Belangrijk:** Bij de sectie "summary" is er alleen `narratives` (conclusion is leeg). Toon geen leeg "Analyse & advies" blok.

### D3. Actieknoppen

Onderaan de pagina:

- **"← Terug"** knop → ga terug naar sub-pagina 1 (uitgangspunten)
- **"Genereer rapport"** knop (primary, groen) → genereer de PDF

### D4. PDF generatie met text_overrides

Wanneer de gebruiker op "Genereer rapport" klikt:

1. **Vergelijk** de huidige teksten met de originele preview-teksten
2. **Bouw text_overrides** alleen voor secties waar teksten zijn aangepast:

```typescript
const textOverrides: Record<string, SectionTextOverride> = {};

for (const section of preview.sections) {
  if (!section.editable_texts) continue;

  const editedNarratives = editedTexts[section.id]?.narratives;
  const editedConclusion = editedTexts[section.id]?.conclusion;

  const narrativesChanged = editedNarratives &&
    JSON.stringify(editedNarratives) !== JSON.stringify(section.editable_texts.narratives);
  const conclusionChanged = editedConclusion &&
    JSON.stringify(editedConclusion) !== JSON.stringify(section.editable_texts.conclusion);

  if (narrativesChanged || conclusionChanged) {
    textOverrides[section.id] = {
      ...(narrativesChanged ? { narratives: editedNarratives } : {}),
      ...(conclusionChanged ? { conclusion: editedConclusion } : {}),
    };
  }
}
```

3. **Roep het PDF endpoint aan** met de text_overrides:

```typescript
const pdfResponse = await fetch(`${API_BASE_URL}/adviesrapport-pdf-v2`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${supabaseSession.access_token}`,
  },
  body: JSON.stringify({
    dossier_id: dossierId,
    aanvraag_id: aanvraagId,
    options: uitgangspuntenFormData,
    text_overrides: Object.keys(textOverrides).length > 0 ? textOverrides : undefined,
  }),
});

// Download PDF
const blob = await pdfResponse.blob();
const url = URL.createObjectURL(blob);
const a = document.createElement('a');
a.href = url;
a.download = `adviesrapport-${dossierId.slice(0, 8)}.pdf`;
a.click();
```

---

## Deel E: Adviezen opslaan + versioning

### E1. Opslaan bij "Verder" (preview laden)

Wanneer de preview succesvol is geladen, sla het advies op in Supabase:

```typescript
// Bij NIEUW advies:
const { data: advies } = await supabase
  .from('adviezen')
  .insert({
    dossier_id: dossierId,
    aanvraag_id: aanvraagId,
    user_id: session.user.id,
    naam: aanvraagNaam,  // Bijv. "Aankoop: Bestaande bouw"
    options: uitgangspuntenFormData,
    preview_data: preview,
    text_overrides: null,
    generated_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  })
  .select()
  .single();

// Update URL naar /dossier/:dossierId/advies/:adviesId
navigate(`/dossier/${dossierId}/advies/${advies.id}`, { replace: true });
```

### E2. Opslaan bij "Genereer rapport"

Bij het genereren van het PDF-rapport:

```typescript
const hasTextOverrides = Object.keys(textOverrides).length > 0;

if (hasTextOverrides) {
  // Teksten zijn aangepast → maak NIEUW advies-record (versie naast bestaande)
  const { data: nieuwAdvies } = await supabase
    .from('adviezen')
    .insert({
      dossier_id: dossierId,
      aanvraag_id: aanvraagId,
      user_id: session.user.id,
      naam: aanvraagNaam,
      options: uitgangspuntenFormData,
      preview_data: preview,
      text_overrides: textOverrides,
      generated_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    })
    .select()
    .single();

  // Update URL naar het nieuwe advies
  navigate(`/dossier/${dossierId}/advies/${nieuwAdvies.id}`, { replace: true });
} else {
  // Geen wijzigingen → overschrijf bestaand record
  await supabase
    .from('adviezen')
    .update({
      preview_data: preview,
      text_overrides: null,
      updated_at: new Date().toISOString(),
    })
    .eq('id', adviesId);
}
```

### E3. Bestaand advies laden

Wanneer de gebruiker navigeert naar `/dossier/:dossierId/advies/:adviesId`:

1. Laad het advies uit Supabase: `supabase.from('adviezen').select().eq('id', adviesId).single()`
2. Vul sub-pagina 1 (Uitgangspunten) met `advies.options`
3. Toon sub-pagina 2 (Adviesuitkomsten) direct met `advies.preview_data`
4. Als `advies.text_overrides` bestaat, pas die toe op de tekstblokken (in plaats van de standaard preview-teksten)

---

## Deel F: Adviezen in dossier-overzicht

### F1. Query

Vervang de huidige mock `adviezen: []` in `DossierDetail.tsx` door een echte Supabase query:

```typescript
const [adviezen, setAdviezen] = useState<Advies[]>([]);

useEffect(() => {
  const fetchAdviezen = async () => {
    const { data } = await supabase
      .from('adviezen')
      .select('id, naam, generated_at, text_overrides')
      .eq('dossier_id', dossierId)
      .order('generated_at', { ascending: false });
    setAdviezen(data || []);
  };
  fetchAdviezen();
}, [dossierId]);
```

### F2. Weergave

In de "Adviezen" sectie van het dossier-overzicht:

```
┌─────────────────────────────────────────────────────────────┐
│ 📋 Adviezen                                  [+ Nieuw advies] │
├─────────────────────────────────────────────────────────────┤
│ 📄 Aankoop: Bestaande bouw                                    │
│    Gegenereerd: 16-03-2026 09:30  •  Aangepaste teksten: Nee  │
├─────────────────────────────────────────────────────────────┤
│ 📄 Aankoop: Bestaande bouw                                    │
│    Gegenereerd: 15-03-2026 14:00  •  Aangepaste teksten: Ja   │
└─────────────────────────────────────────────────────────────┘
```

- Toon `naam` als titel
- Toon `generated_at` geformateerd als "DD-MM-YYYY HH:mm"
- Toon "Aangepaste teksten: Ja" als `text_overrides !== null`
- Klik → navigeer naar `/dossier/${dossierId}/advies/${advies.id}`

### F3. Verwijderen

Gebruik het bestaande delete-patroon. Bij klik op het prullenbak-icoon:

```typescript
await supabase.from('adviezen').delete().eq('id', adviesId);
```

---

## Deel G: AdviesrapportDialog aanpassen

De bestaande `AdviesrapportDialog.tsx` wordt vereenvoudigd:

- **Stap 1 blijft**: Selecteer aanvraag als basis
- **Stap 2 verdwijnt** uit de dialog (verplaatst naar AdviesPage)
- Na selectie + "Volgende" → `navigate('/dossier/${dossierId}/advies/nieuw?aanvraag=${selectedAanvraagId}')` en sluit de dialog

---

## Verificatie-tabel

| # | Check | Verwacht resultaat |
|---|-------|--------------------|
| 1 | Klik "Nieuw advies" | Dialog opent met aanvraag-selectie |
| 2 | Selecteer aanvraag + klik "Volgende" | Navigeert naar `/dossier/:id/advies/nieuw` |
| 3 | Sub-pagina 1 toont alle uitgangspunten | Klantprofiel, risicobereidheid, geavanceerd, rapport meta |
| 4 | Klik "Verder" | Loading spinner → preview geladen → sub-pagina 2 |
| 5 | Sub-pagina 2 toont per sectie | Bedragen-tabel + bewerkbare tekstvelden |
| 6 | Tekst niet bewerkt + "Genereer rapport" | PDF download + bestaand advies overschreven |
| 7 | Tekst bewerkt + "Genereer rapport" | PDF met aangepaste tekst + nieuw advies-record |
| 8 | Dossier-overzicht toont advies | Naam, datum, aangepaste teksten indicator |
| 9 | Klik op advies in overzicht | Navigeert naar advies met opgeslagen teksten |
| 10 | Verwijder advies | Record verwijderd uit Supabase en lijst |

---

## Samenvatting bestanden

| Bestand | Actie | Wijziging |
|---------|-------|-----------|
| Supabase SQL Editor | Nieuw | `adviezen` tabel + RLS policies |
| `src/types/advies.ts` | Nieuw | TypeScript types voor Advies, Preview, TextOverride |
| `src/pages/AdviesPage.tsx` | Nieuw | Volledige pagina met 2 sub-pagina's |
| `src/components/AdviesrapportDialog.tsx` | Wijzig | Stap 2 verwijderen, navigatie naar AdviesPage |
| `src/pages/DossierDetail.tsx` | Wijzig | Echte adviezen-query i.p.v. mock array |
| Router configuratie | Wijzig | Twee nieuwe routes toevoegen |
