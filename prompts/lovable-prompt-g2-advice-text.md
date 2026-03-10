# Lovable Prompt G2: Automatische advice_text in adviesrapport samenvatting

> Kopieer deze prompt in Lovable om de "Advies en onderbouwing" tekst automatisch te genereren in de Samenvatting-sectie van het adviesrapport.

---

## Achtergrond

De samenvatting-sectie van het adviesrapport (sectie `id: "summary"`) heeft een subsectie "Advies en onderbouwing" die als `advice_text: string[]` wordt meegestuurd naar de API. De backend template rendert dit automatisch onder de samenvatting-highlights.

De `advice_text` bestaat uit 4 alinea's:
1. **Hypotheekadvies** — Wat wordt geadviseerd (bedrag, geldverstrekker, aflosvorm, RVP, NHG)
2. **Betaalbaarheid** — Bruto/netto maandlast, marge t.o.v. maximum
3. **Risico-overzicht** — Compact label per risicoscenario
4. **Klantprioriteit** — Welke prioriteit bij het advies is gehanteerd

---

## Wijziging: `src/utils/adviesrapportBuilder.ts`

### 1. Voeg een helperfunctie toe boven `buildAdviesrapportPayload`

```typescript
/**
 * Genereer de "Advies en onderbouwing" tekst voor de samenvatting-sectie.
 */
function buildAdviceText(
  invoer: any,
  options: AdviesrapportOptions,
  natRes: any,
  maandRes: any,
  hypotheekBedrag: number,
  hasPartner: boolean,
): string[] {
  const paragraphs: string[] = [];

  // --- Alinea 1: Hypotheekadvies ---
  const geldverstrekker = options.geldverstrekker || 'de geldverstrekker';

  // Aflosvorm samenvatten vanuit de leningdelen in het scenario
  const leningdelen = invoer.haalbaarheidsBerekeningen?.[options.scenarioIndex]?.leningdelen
    || invoer.berekeningen?.[options.scenarioIndex]?.leningdelen
    || [];

  const aflosvormLabels: Record<string, string> = {
    'Annuïteit': 'annuïtair',
    'annuiteit': 'annuïtair',
    'Lineair': 'lineair',
    'lineair': 'lineair',
    'Aflosvrij': 'aflossingsvrij',
    'aflossingsvrij': 'aflossingsvrij',
    'Spaar': 'spaarhypotheek',
    'spaarhypotheek': 'spaarhypotheek',
  };

  const uniqueTypes = [...new Set(
    leningdelen.map((d: any) => {
      const raw = d.aflossingsvorm || d.aflos_type || 'Annuïteit';
      return aflosvormLabels[raw] || raw.toLowerCase();
    })
  )];

  const aflosvormTekst = uniqueTypes.length === 1
    ? `een ${uniqueTypes[0]}e`
    : `een combinatie van ${uniqueTypes.slice(0, -1).join(', ')} en ${uniqueTypes[uniqueTypes.length - 1]}`;

  // Langste RVP
  const rvpWaarden = leningdelen
    .map((d: any) => d.rvp || 120)
    .sort((a: number, b: number) => b - a);
  const rvpJaar = rvpWaarden.length > 0 ? Math.round(rvpWaarden[0] / 12) : 10;

  let p1 = `Wij adviseren een hypotheek van ${formatBedrag(hypotheekBedrag)} bij ${geldverstrekker}` +
    `, met ${aflosvormTekst} aflossingsvorm en een rentevaste periode van ${rvpJaar} jaar.`;
  if (options.nhg) {
    p1 += ' De hypotheek wordt aangevraagd met Nationale Hypotheek Garantie.';
  }
  paragraphs.push(p1);

  // --- Alinea 2: Betaalbaarheid ---
  const bruto = maandRes?.total_gross_monthly || maandRes?.brutoMaandlast || 0;
  const netto = maandRes?.net_monthly_cost || maandRes?.nettoMaandlast || 0;
  const maxHypotheek = natRes?.scenario1?.annuitair?.max_box1 || 0;
  const marge = maxHypotheek > 0 && hypotheekBedrag <= maxHypotheek * 0.9 ? 'ruim ' : '';

  if (bruto > 0 && maxHypotheek > 0) {
    paragraphs.push(
      `De bruto maandlast bedraagt ${formatBedrag(bruto)}, wat na belastingvoordeel neerkomt ` +
      `op een netto maandlast van ${formatBedrag(netto)}. Het geadviseerde hypotheekbedrag past ` +
      `${marge}binnen de maximaal toegestane hypotheek van ${formatBedrag(maxHypotheek)}.`
    );
  }

  // --- Alinea 3: Risico-overzicht ---
  const riskParts: string[] = [];

  // Overlijden
  if (!hasPartner) {
    riskParts.push('Overlijden: niet van toepassing (alleenstaand)');
  } else if (options.selectedSections.includes('risk-death')) {
    riskParts.push('Overlijden: aandachtspunt');
  }

  // Arbeidsongeschiktheid
  if (options.selectedSections.includes('risk-disability')) {
    riskParts.push('Arbeidsongeschiktheid: aandachtspunt, verwijzing naar specialist');
  }

  // Werkloosheid
  if (options.selectedSections.includes('risk-unemployment')) {
    // Simpele buffer-check: als er spaargeld > 6x netto maandlast is
    const spaargeld = invoer.klantGegevens?.spaargeld || invoer.klantGegevens?.eigenGeld || 0;
    const bufferMaanden = netto > 0 ? Math.floor(spaargeld / netto) : 0;
    if (bufferMaanden >= 6) {
      riskParts.push('Werkloosheid: voldoende buffer');
    } else {
      riskParts.push('Werkloosheid: aandachtspunt');
    }
  }

  // Pensionering
  if (options.selectedSections.includes('retirement')) {
    riskParts.push('Pensionering: afgedekt');
  }

  if (riskParts.length > 0) {
    paragraphs.push(riskParts.join('. ') + '.');
  }

  // --- Alinea 4: Klantprioriteit ---
  const prioriteit = invoer.klantGegevens?.klantPrioriteit
    || invoer.klantGegevens?.customerPriority
    || '';
  if (prioriteit) {
    paragraphs.push(
      `Bij dit advies is rekening gehouden met uw prioriteit: ${prioriteit.toLowerCase()}.`
    );
  }

  return paragraphs;
}
```

### 2. Pas de summary-sectie aan in `buildAdviesrapportPayload`

Zoek het blok waar de summary-sectie wordt gebouwd (het `if (options.selectedSections.includes('summary'))` blok). Voeg `advice_text` toe aan het section-object:

```typescript
  // --- Samenvatting sectie ---
  if (options.selectedSections.includes('summary')) {
    const hypotheekBedrag = fin
      ? (fin.totaalInvestering || 0) - (fin.totaalEigenMiddelen || 0)
      : 0;

    sections.push({
      id: 'summary',
      title: 'Samenvatting advies',
      visible: true,
      narratives: [
        `U wilt een hypotheek afsluiten voor ${invoer.dossierType || 'aankoop bestaande woning'}.`,
        'Op basis van uw financiële situatie, uw wensen en de geldende leennormen hebben wij beoordeeld dat de geadviseerde financiering passend is binnen uw situatie.',
        ...(options.nhg ? ['De hypotheek wordt aangevraagd met Nationale Hypotheek Garantie.'] : []),
      ],
      // NIEUW: Advies en onderbouwing tekst
      advice_text: buildAdviceText(invoer, options, natRes, maandRes, hypotheekBedrag, hasPartner),
      highlights: [
        // ... bestaande highlights ongewijzigd ...
      ],
      rows: [
        // ... bestaande rows ongewijzigd ...
      ],
    });
  }
```

### 3. Voeg `advice_text` toe aan het Section interface

Als er een TypeScript interface `Section` is gedefinieerd, voeg het veld toe:

```typescript
interface Section {
  id: string;
  title: string;
  visible: boolean;
  narratives?: string[];
  rows?: Row[];
  tables?: Table[];
  highlights?: Highlight[];
  advice_text?: string[];    // NIEUW
}
```

---

## Geen template-wijzigingen nodig

De backend template (`adviesrapport.html`) rendert `section.advice_text` al:

```html
{% if section.advice_text %}
<div class="subsection" style="margin-top: 22px;">
  <h4 class="subsection-title">Advies en onderbouwing</h4>
  <div class="text-block">
    {% for text in section.advice_text %}
    <div>{{ text }}</div>
    {% endfor %}
  </div>
</div>
{% endif %}
```

Het Pydantic model (`AdviesrapportSection`) accepteert `advice_text: Optional[List[str]]` al.

---

## Voorbeeld output

### Alleenstaand

```
Wij adviseren een hypotheek van € 338.173 bij ING, met een annuïtaire
aflossingsvorm en een rentevaste periode van 10 jaar. De hypotheek wordt
aangevraagd met Nationale Hypotheek Garantie.

De bruto maandlast bedraagt € 1.855, wat na belastingvoordeel neerkomt
op een netto maandlast van € 1.267. Het geadviseerde hypotheekbedrag past
binnen de maximaal toegestane hypotheek van € 326.250.

Overlijden: niet van toepassing (alleenstaand). Arbeidsongeschiktheid:
aandachtspunt, verwijzing naar specialist. Werkloosheid: aandachtspunt.
Pensionering: afgedekt.

Bij dit advies is rekening gehouden met uw prioriteit: stabiele maandlast.
```

### Stel

```
Wij adviseren een hypotheek van € 450.000 bij ING, met een combinatie van
annuïtair, lineair en aflossingsvrij als aflossingsvorm en een rentevaste
periode van 20 jaar. De hypotheek wordt aangevraagd met NHG.

De bruto maandlast bedraagt € 2.410, wat na belastingvoordeel neerkomt
op een netto maandlast van € 1.890. Het geadviseerde hypotheekbedrag past
ruim binnen de maximaal toegestane hypotheek van € 520.000.

Overlijden: aandachtspunt. Arbeidsongeschiktheid: aandachtspunt, verwijzing
naar specialist. Werkloosheid: voldoende buffer. Pensionering: afgedekt.

Bij dit advies is rekening gehouden met uw prioriteit: zo laag mogelijke maandlast.
```

---

## Verificatie

| # | Check | Verwacht resultaat |
|---|-------|--------------------|
| 1 | Genereer adviesrapport voor alleenstaand | "Advies en onderbouwing" subsectie zichtbaar met 4 alinea's |
| 2 | Genereer adviesrapport voor stel | Overlijden toont "aandachtspunt" i.p.v. "niet van toepassing" |
| 3 | NHG aan | Laatste zin alinea 1 bevat NHG-tekst |
| 4 | NHG uit | Geen NHG-zin in alinea 1 |
| 5 | Meerdere leningdelen | "combinatie van annuïtair en lineair" i.p.v. "een annuïtaire" |
| 6 | Voldoende spaarbuffer | Werkloosheid toont "voldoende buffer" |
| 7 | Klantprioriteit leeg | Alinea 4 wordt niet getoond |
| 8 | Risico-secties uitgeschakeld | Bijbehorend risico verschijnt niet in alinea 3 |

---

## Samenvatting

| Onderdeel | Wijziging |
|-----------|-----------|
| `src/utils/adviesrapportBuilder.ts` | Nieuwe `buildAdviceText()` functie + `advice_text` toevoegen aan summary-sectie |
| Section interface | `advice_text?: string[]` toevoegen |
| Backend / template | Geen wijzigingen nodig (al voorbereid) |
