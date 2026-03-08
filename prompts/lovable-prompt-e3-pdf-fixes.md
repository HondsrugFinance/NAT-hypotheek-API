# Lovable Prompt E3: Samenvatting PDF — energielabel + footer naam

## Doel

Twee fixes in de data die de frontend naar de `/samenvatting-pdf` API stuurt. Beide velden worden al correct gerenderd door de backend template — het probleem is dat de frontend ze niet (goed) meestuurt.

---

## Fix 1: Energielabel ontbreekt bij onderpand in PDF

### Probleem

Het onderpand-blok in de PDF toont alleen WOZ-waarde maar niet het energielabel. De backend verwacht het veld `onderpand.energielabel` (een string), maar de frontend stuurt dit niet mee.

Het energielabel IS wel beschikbaar in de app — het wordt getoond op de samenvattingspagina bij "Haalbare hypotheek" onder "ENERGIELABEL EN EBV/EBB".

### Stappen

1. **Zoek de `buildOnderpand` functie** in het bestand dat de PDF-data samenstelt (waarschijnlijk `pdfDownload.ts` of een vergelijkbaar bestand). Zoek op `buildOnderpand` of `onderpand` in de codebase.

2. **Zoek waar het energielabel wordt opgeslagen.** Dit is de waarde die de gebruiker selecteert bij het aanmaken van een haalbaarheidsberekening. Zoek op `energielabel` in de codebase. Het staat waarschijnlijk op een van deze plekken:
   - `invoer.energielabel`
   - `invoer.onderpand.energielabel`
   - `berekening.invoer.energielabel`
   - Een property op het scenario/haalbaarheids-object

3. **Map de interne waarde naar display-tekst.** De dropdown-waarden in de app zijn interne keys. De API verwacht leesbare tekst. Gebruik deze mapping:

```typescript
const energieLabelDisplay: Record<string, string> = {
  'geen_label': '',
  'Geen (geldig) Label': '',
  'E_F_G': 'E, F of G',
  'E,F,G': 'E, F of G',
  'C_D': 'C of D',
  'C,D': 'C of D',
  'A_B': 'A of B',
  'A,B': 'A of B',
  'A+_A++': 'A+ of A++',
  'A+,A++': 'A+ of A++',
  'A+++': 'A+++',
  'A++++': 'A++++',
  'A++++_garantie': 'A++++ met garantie',
  'A++++ met garantie': 'A++++ met garantie',
};
```

Let op: de mapping bevat zowel underscore-keys (`C_D`) als komma-keys (`C,D`) omdat niet duidelijk is welk formaat de frontend intern gebruikt. Hierdoor werkt het altijd.

4. **Voeg energielabel toe aan het onderpand-object:**

```typescript
// In buildOnderpand():
const onderpand = {
  woz_waarde: formatBedrag(wozWaarde),
  energielabel: energieLabelDisplay[energielabelWaarde] || energielabelWaarde || '',
};
```

### Verificatie

Na de fix: genereer een PDF en controleer dat onder "Onderpand" het energielabel wordt getoond (bijv. "C of D" of "A of B").

---

## Fix 2: Footer naam moet dossiertitel gebruiken

### Probleem

In de PDF footer staat bijv. "Harry Slinger en Harriëtte Slinger-Aap", maar de dossiertitel bovenaan de pagina in de Lovable app toont "Harry en Harriëtte Slinger". De PDF footer moet dezelfde tekst gebruiken.

Het `klant_naam` veld in het API request bepaalt:
- De running footer op elke pagina: "Hondsrug Finance — Samenvatting Hypotheekberekening — **[klant_naam]**"
- De page-header op pagina 2+: "Samenvatting Hypotheekberekening — **[klant_naam]**"

### Stappen

1. **Zoek waar `klant_naam` wordt samengesteld** voor het PDF request. Zoek op `klant_naam` of `klantNaam` in de codebase.

2. **Zoek hoe de dossiertitel wordt opgebouwd.** Dit is de tekst die bovenaan de dossierpagina staat (bijv. "Harry en Harriëtte Slinger • 7 maart 2026"). Zoek op de component die de dossiertitel rendert — het staat waarschijnlijk op een property zoals `dossier.titel`, `dossier.naam`, of `dossier.displayName`.

3. **Gebruik dezelfde titel-logica voor `klant_naam`:**

```typescript
// Gebruik de dossiertitel (zonder datum) als klant_naam:
klant_naam: dossierTitel,  // bijv. "Harry en Harriëtte Slinger"
```

Als de dossiertitel een datum bevat (bijv. "Harry en Harriëtte Slinger • 7 maart 2026"), strip dan het deel na het bullet-teken:

```typescript
klant_naam: dossierTitel.split('•')[0].trim(),
```

### Verificatie

Na de fix: genereer een PDF en controleer dat de footer en page-headers dezelfde naam tonen als de dossiertitel in de app.

---

## Fix 3: Namen i.p.v. "Aanvrager" / "Partner" bij inkomen

### Probleem

In de PDF bij "Maximaal haalbare hypotheek" staan de inkomenslabels als "Aanvrager" en "Partner". In plaats daarvan moeten hier de daadwerkelijke namen staan, indien bekend vanuit klantgegevens.

### Stappen

1. **Zoek de `buildHaalbaarheidData` functie** (of vergelijkbaar) waar `inkomen_items` wordt samengesteld.

2. **Haal de namen op uit klantgegevens.** De voornaam, tussenvoegsel en achternaam zijn beschikbaar in het klantgegevens-object. Stel de volledige naam samen:

```typescript
// Voorbeeld — zoek de juiste property-namen op:
const naamAanvrager = [kg.voornaamAanvrager, kg.tussenvoegselAanvrager, kg.achternaamAanvrager]
  .filter(Boolean).join(' ');
const naamPartner = [kg.voornaamPartner, kg.tussenvoegselPartner, kg.achternaamPartner]
  .filter(Boolean).join(' ');
```

3. **Gebruik de naam als label**, met fallback naar "Aanvrager" / "Partner":

```typescript
// In inkomen_items:
{
  label: `${naamAanvrager || 'Aanvrager'}${sterretjes.aanvragerSterretje}`,
  waarde: formatBedrag(aanvragerInkomen),
  is_totaal: false,
},
...(heeftPartner ? [{
  label: `${naamPartner || 'Partner'}${sterretjes.partnerSterretje}`,
  waarde: formatBedrag(partnerInkomen),
  is_totaal: false,
}] : []),
```

### Verificatie

Na de fix: genereer een PDF. Bij inkomen moeten de echte namen staan (bijv. "Harry Slinger*" en "Harriëtte Slinger**") in plaats van "Aanvrager*" en "Partner**".

---

## Samenvatting

| Fix | Wat | Verwacht resultaat |
|-----|-----|-------------------|
| 1 | `buildOnderpand`: energielabel ophalen en meesturen | "Energielabel: C of D" zichtbaar in PDF |
| 2 | `klant_naam`: dossiertitel gebruiken | Footer toont "Harry en Harriëtte Slinger" |
| 3 | `inkomen_items`: namen gebruiken i.p.v. "Aanvrager"/"Partner" | "Harry Slinger*" i.p.v. "Aanvrager*" |

## Belangrijk

- **Zoek altijd eerst de daadwerkelijke property-namen** op in de bestaande code/types voordat je velden mapt
- De backend API en template zijn al correct — alle fixes zitten uitsluitend in de frontend data-samenstelling
- Test na elke fix door een PDF te genereren en het resultaat te controleren
