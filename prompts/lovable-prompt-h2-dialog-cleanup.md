# H2: Adviesrapport dialog opschonen — 9 velden verwijderen

## Context

De backend (V2) haalt nu 9 velden rechtstreeks uit de Supabase aanvraag database. Deze velden hoeven niet meer in het "Adviesrapport samenstellen" dialog te staan.

De backend leest deze waarden automatisch:
- **NHG** → uit `samenstellenHypotheek.nhg`
- **Geldverstrekker** → uit `samenstellenHypotheek.geldverstrekker`
- **Nabestaandenpensioen aanvrager** → uit `inkomenAanvrager[]` (type=pensioen, soort=nabestaandenpensioen)
- **Nabestaandenpensioen partner** → uit `inkomenPartner[]` (idem)
- **AOV dekking aanvrager** → uit `voorzieningen.verzekeringen[].verzekerdePersonen[].dekkingAOV`
- **AOV dekking partner** → idem, gefilterd op persoon=partner
- **Woonlastenverzekering AO** → uit `voorzieningen.verzekeringen[].verzekerdePersonen[].dekkingAO`
- **Woonlastenverzekering WW** → uit `voorzieningen.verzekeringen[].verzekerdePersonen[].dekkingWW`
- **Kind(eren) onder 18** → uit `kinderen[]` (geboortedatum check)

## Stap 1: Verwijder velden uit het dialog

Zoek het adviesrapport samenstellen dialog (waarschijnlijk in een component als `AdviesrapportDialog.tsx` of `AdviesrapportGenereren.tsx`). Verwijder de volgende formulier-elementen:

1. **NHG** checkbox
2. **Geldverstrekker** tekstveld/dropdown
3. **Nabestaandenpensioen bij overlijden aanvrager** — number input (€)
4. **Nabestaandenpensioen bij overlijden partner** — number input (€)
5. **AOV dekking aanvrager** — number input (€)
6. **AOV dekking partner** — number input (€)
7. **Woonlastenverzekering AO** — number input (€)
8. **Woonlastenverzekering WW** — number input (€)
9. **Kind(eren) onder 18** checkbox + geboortedatum jongste kind datumpicker

Verwijder ook de bijbehorende `useState` hooks en labels.

## Stap 2: Verwijder uit TypeScript interface

In de TypeScript interface voor de options (waarschijnlijk `AdviesrapportOptions` of vergelijkbaar), verwijder:

```typescript
// VERWIJDER deze velden:
hypotheekverstrekker: string;
nhg: boolean;
nabestaandenpensioen_bij_overlijden_aanvrager: number;
nabestaandenpensioen_bij_overlijden_partner: number;
heeft_kind_onder_18: boolean;
geboortedatum_jongste_kind?: string;
aov_dekking_bruto_jaar_aanvrager: number;
aov_dekking_bruto_jaar_partner: number;
woonlastenverzekering_ao_bruto_jaar: number;
woonlastenverzekering_ww_bruto_jaar: number;
```

## Stap 3: Verwijder uit request payload

In de functie die het API request bouwt (waar de `options` object wordt samengesteld voor de `POST /adviesrapport-pdf-v2` call), verwijder de 9 velden uit het options object:

```typescript
// VERWIJDER deze regels uit het options object:
hypotheekverstrekker: geldverstrekker,
nhg: nhg,
nabestaandenpensioen_bij_overlijden_aanvrager: nabestaandenAanvrager,
nabestaandenpensioen_bij_overlijden_partner: nabestaandenPartner,
heeft_kind_onder_18: heeftKindOnder18,
geboortedatum_jongste_kind: geboortedatumJongsteKind || undefined,
aov_dekking_bruto_jaar_aanvrager: aovAanvrager,
aov_dekking_bruto_jaar_partner: aovPartner,
woonlastenverzekering_ao_bruto_jaar: woonlastenverz_ao,
woonlastenverzekering_ww_bruto_jaar: woonlastenverz_ww,
```

## Stap 4: Verwijder prefill-logica

De dialog heeft waarschijnlijk code die NHG en geldverstrekker uit de aanvraag data prefilt:

```typescript
// VERWIJDER deze prefill-logica:
setGeldverstrekker(aanvraag?.hypotheekverstrekker || "");
setNhg(aanvraag?.nhg ?? true);
```

## Wat moet BEHOUDEN blijven

Deze velden blijven wél in het dialog — het zijn echte adviseur-keuzes:

| Veld | Type | Reden |
|------|------|-------|
| Doel hypotheek | Tekst | Adviseur kiest |
| Ervaring hypotheek | Dropdown | Adviseur beoordeelt |
| Kennis hypotheekvormen | Dropdown | Adviseur beoordeelt |
| Kennis fiscale regels | Dropdown | Adviseur beoordeelt |
| Risicobereidheid (8 scenario's) | Dropdowns | Klantprofiel |
| AO percentage | Number (%) | Adviseur kiest |
| Benutting RVC percentage | Number (%) | Adviseur kiest |
| Loondoorbetaling jaar 1/2 aanvrager | Number (%) | Adviseur kiest |
| Loondoorbetaling jaar 1/2 partner | Number (%) | Adviseur kiest |
| Arbeidsverleden velden | Numbers | Adviseur vult in |
| Prioriteit | Tekst | Adviseur kiest |
| Naam adviseur | Tekst | Rapport meta |
| Datum rapport | Datumpicker | Rapport meta |
| Dossiernummer | Tekst | Rapport meta |

## Verificatie

| Check | Verwacht |
|-------|----------|
| Dialog bevat GEEN NHG checkbox | ✓ |
| Dialog bevat GEEN Geldverstrekker veld | ✓ |
| Dialog bevat GEEN Nabestaandenpensioen velden | ✓ |
| Dialog bevat GEEN AOV dekking velden | ✓ |
| Dialog bevat GEEN Woonlastenverzekering velden | ✓ |
| Dialog bevat GEEN Kind onder 18 checkbox | ✓ |
| API request bevat GEEN van de 9 verwijderde velden | ✓ |
| Geen TypeScript compile errors | ✓ |
| Dialog bevat nog WEL alle adviseur-keuze velden | ✓ |

## Samenvatting wijzigingen

| Bestand | Actie |
|---------|-------|
| `AdviesrapportDialog.tsx` (of equivalent) | 9 form-elementen + useState hooks verwijderen |
| TypeScript interface | 10 velden verwijderen (9 + geboortedatum_jongste_kind) |
| API request builder | 10 velden uit options object verwijderen |
| Prefill logica | NHG/geldverstrekker prefill verwijderen |
