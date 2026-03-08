# Lovable Prompt E4: Samenvatting PDF — namen bij inkomen

## Doel

In de PDF bij "Maximaal haalbare hypotheek" staan de inkomenslabels als "Aanvrager" en "Partner". Vervang deze door de daadwerkelijke namen van de klant, indien bekend.

---

## Probleem

Bij de haalbaarheidsblokken in de PDF (Huidige situatie / Toekomstige situatie) staat bij inkomen:

```
INKOMEN
Aanvrager*        € 80.000
Partner**         € 35.000
Totaal inkomen    € 115.000
```

Dit moet worden:

```
INKOMEN
Harry Slinger*           € 80.000
Harriëtte Slinger**      € 35.000
Totaal inkomen           € 115.000
```

## Stappen

1. **Zoek de functie waar `inkomen_items` wordt samengesteld** voor het PDF request. Dit is waarschijnlijk `buildHaalbaarheidData` in `pdfDownload.ts` of een vergelijkbaar bestand. Zoek op `inkomen_items` of `Aanvrager` in de codebase.

2. **Haal de namen op uit klantgegevens.** De voornaam, tussenvoegsel en achternaam zijn beschikbaar in het klantgegevens-object. Stel de volledige naam samen:

```typescript
// Voorbeeld — zoek de juiste property-namen op:
const naamAanvrager = [kg.voornaamAanvrager, kg.tussenvoegselAanvrager, kg.achternaamAanvrager]
  .filter(Boolean).join(' ');
const naamPartner = [kg.voornaamPartner, kg.tussenvoegselPartner, kg.achternaamPartner]
  .filter(Boolean).join(' ');
```

3. **Gebruik de naam als label**, met fallback naar "Aanvrager" / "Partner" als de naam niet beschikbaar is:

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

## Belangrijk

- **Zoek de daadwerkelijke property-namen** op in de bestaande code/types — bovenstaande zijn voorbeelden
- De fallback `'Aanvrager'` / `'Partner'` zorgt ervoor dat het altijd werkt, ook als klantgegevens niet zijn ingevuld
- Dit geldt voor **alle scenario-blokken** (Huidige situatie, Toekomstige situatie, etc.)
- De backend API en template zijn al correct — de fix zit uitsluitend in de frontend data-samenstelling

## Verificatie

Na de fix: genereer een PDF en controleer dat bij inkomen de echte namen staan (bijv. "Harry Slinger*" en "Harriëtte Slinger**") in plaats van "Aanvrager*" en "Partner**".
