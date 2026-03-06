# Lovable Prompt E2: Samenvatting PDF — fixes na eerste test

## Doel

Na de eerste test van de vernieuwde samenvatting-PDF zijn er een aantal problemen gevonden in de data die de frontend naar de API stuurt. Hieronder de fixes.

---

## Fix 1: Klantgegevens — adres, telefoon en email ontbreken

De `buildKlantGegevens` functie stuurt nu alleen `naam` en `geboortedatum`. De overige velden (straat, postcode, woonplaats, telefoon, email) worden niet gevuld.

### Probleem

De velden `straatAanvrager`, `postcodeAanvrager`, etc. bestaan mogelijk niet met die namen op het `klantGegevens` object. Zoek de daadwerkelijke property-namen op in de code.

### Verwachte velden per persoon

Het klantgegevens-formulier (het modal "Klantgegevens invullen" op de dossierpagina) slaat op:
- Voornaam, Achternaam
- Postcode, Huisnummer → combineer tot adres samen met straat en woonplaats
- Straat, Woonplaats
- Telefoonnummer
- E-mailadres

### Fix

In `buildKlantGegevens()`, zoek de correcte property-namen uit de code en map ze. Voorbeeld (pas de property-namen aan):

```typescript
const aanvrager = {
  naam: [kg.voornaamAanvrager, kg.achternaamAanvrager].filter(Boolean).join(' '),
  geboortedatum: kg.geboortedatumAanvrager
    ? new Date(kg.geboortedatumAanvrager).toLocaleDateString('nl-NL')
    : '',
  // Zoek de juiste veldnamen op:
  straat: kg.straatAanvrager
    ? `${kg.straatAanvrager} ${kg.huisnummerAanvrager || ''}`.trim()
    : '',
  postcode: kg.postcodeAanvrager || '',
  woonplaats: kg.woonplaatsAanvrager || '',
  telefoon: kg.telefoonAanvrager || '',
  email: kg.emailAanvrager || '',
};
```

Doe hetzelfde voor partner.

---

## Fix 2: Partner sterretje ontbreekt bij haalbaarheid

In de PDF staat "Aanvrager*" maar "Partner" zonder sterretje.

### Fix

Controleer dat `inkomenStatus.partner` correct wordt doorgegeven aan `getInkomenSterretjes()`. Als er een partner is maar `inkomenStatus.partner` niet is ingesteld, gebruik dan dezelfde status als de aanvrager als default:

```typescript
const sterretjes = getInkomenSterretjes(
  inkomenStatus?.aanvrager || 'aanname',
  // Default: gebruik aanvrager-status als partner-status niet is ingesteld
  !kg.alleenstaand ? (inkomenStatus?.partner || inkomenStatus?.aanvrager || 'aanname') : undefined,
);
```

Controleer ook dat het sterretje daadwerkelijk aan het Partner-label wordt toegevoegd in `buildHaalbaarheidData`:

```typescript
// Per scenario, in de inkomen_items array:
...(heeftPartner ? [{
  label: `Partner${sterretjes.partnerSterretje}`,
  waarde: formatBedrag(partnerInkomen),
  is_totaal: false,
}] : []),
```

---

## Fix 3: Energielabel ontbreekt bij onderpand

Het onderpand-blok in de PDF toont alleen WOZ-waarde maar niet het energielabel.

### Fix

In `buildOnderpand()`, controleer of de energielabel-waarde correct wordt opgehaald en gemapt. De interne waarden uit de dropdown moeten worden vertaald naar display-tekst:

```typescript
const energieLabelDisplay: Record<string, string> = {
  'geen_label': '',
  'E_F_G': 'E, F of G',
  'C_D': 'C of D',
  'A_B': 'A of B',
  'A+_A++': 'A+ of A++',
  'A+++': 'A+++',
  'A++++': 'A++++',
  'A++++_garantie': 'A++++ met garantie',
};
```

Zoek op welke property de energielabel-waarde bevat. Het is waarschijnlijk `invoer.haalbaarheidsBerekeningen[0].onderpand.energielabel` of een vergelijkbare locatie. Debug door de waarde te loggen als het niet werkt.

---

## Samenvatting

| Fix | Bestand | Wat |
|-----|---------|-----|
| 1 | `pdfDownload.ts` | `buildKlantGegevens`: correcte veldnamen voor adres/telefoon/email |
| 2 | `pdfDownload.ts` | `buildHaalbaarheidData`: sterretjes toepassen op Partner label |
| 3 | `pdfDownload.ts` | `buildOnderpand`: energielabel mapping fixen |

## Belangrijk

- Zoek altijd eerst de **daadwerkelijke property-namen** op in de bestaande code/types voordat je velden mapt
- De backend API is al correct — alle fixes zitten in de frontend data-samenstelling
- Test na de fix door een PDF te genereren en te controleren of alle velden gevuld zijn
