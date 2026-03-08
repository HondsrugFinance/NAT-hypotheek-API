# Lovable Prompt E5: Samenvatting PDF — onderpanden per scenario

## Doel

De PDF toont nu één enkel onderpand-blok. De backend ondersteunt nu een `onderpanden[]` array — één onderpand per haalbaarheidsberekening/scenario. De frontend moet per scenario een apart onderpand-object meesturen met de bijbehorende WOZ-waarde, energielabel en eventuele EBV/EBB.

---

## Huidige situatie

De frontend stuurt nu een enkel `onderpand` object mee in het PDF request:

```typescript
onderpand: {
  woz_waarde: "€ 350.000",
  energielabel: "C of D",
}
```

## Gewenste situatie

Vervang het `onderpand` veld door een `onderpanden` array. Elk element komt overeen met één haalbaarheidsberekening/scenario:

```typescript
onderpanden: [
  {
    naam: "Huidige situatie",          // Moet overeenkomen met scenario-naam
    woz_waarde: "€ 350.000",          // Geformatteerd bedrag
    energielabel: "C of D",           // Leesbare tekst (zie mapping hieronder)
    ebv_ebb_bedrag: "",                // Optioneel: energiebesparende voorzieningen
    adres: "",                         // Optioneel
    woningtype: "",                    // Optioneel
  },
  {
    naam: "Toekomstige situatie",
    woz_waarde: "€ 400.000",
    energielabel: "A of B",
    ebv_ebb_bedrag: "€ 15.000",
  },
]
```

**Belangrijk:** het `onderpand` veld mag worden verwijderd — de backend accepteert beide, maar `onderpanden[]` heeft voorrang.

---

## Stappen

1. **Zoek de functie waar onderpand-data wordt samengesteld** voor het PDF request. Zoek op `buildOnderpand` of `onderpand` in de codebase (waarschijnlijk in `pdfDownload.ts` of vergelijkbaar).

2. **Zoek waar de onderpand-gegevens per scenario worden opgeslagen.** Elk scenario/haalbaarheidsberekening heeft eigen onderpand-gegevens (WOZ-waarde, energielabel, EBV/EBB). Zoek op `wozWaarde`, `energielabel`, `ebv` in de codebase.

3. **Map energielabel naar display-tekst.** De dropdown-waarden in de app zijn interne keys. De API verwacht leesbare tekst:

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

4. **Bouw de `onderpanden` array** door over alle scenario's te itereren:

```typescript
const onderpanden = scenarios.map(scenario => ({
  naam: scenario.naam,  // bijv. "Huidige situatie"
  woz_waarde: formatBedrag(scenario.wozWaarde),
  energielabel: energieLabelDisplay[scenario.energielabel] || scenario.energielabel || '',
  ebv_ebb_bedrag: scenario.ebvEbbBedrag ? formatBedrag(scenario.ebvEbbBedrag) : '',
}));
```

5. **Vervang `onderpand` door `onderpanden` in het PDF request:**

```typescript
// Verwijder:
onderpand: buildOnderpand(...)

// Vervang door:
onderpanden: onderpanden,
```

---

## Verificatie

- **1 scenario:** genereer PDF → onderpand-blok staat over de volle breedte, zonder titel
- **2 scenario's:** genereer PDF → 2 onderpand-blokken naast elkaar, elk met scenario-naam als titel en eigen WOZ-waarde/energielabel
- Controleer dat energielabel als leesbare tekst wordt getoond (bijv. "C of D", niet "C_D")

## Belangrijk

- **Zoek altijd eerst de daadwerkelijke property-namen** op in de bestaande code/types voordat je velden mapt
- De backend API en template zijn al correct — de fix zit uitsluitend in de frontend data-samenstelling
