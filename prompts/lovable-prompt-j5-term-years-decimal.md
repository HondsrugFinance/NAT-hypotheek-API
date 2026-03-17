# J5 — Fix: term_years als decimaal doorsturen (niet afronden)

## Probleem

Bij de maandlasten API-aanroep (`POST /calculate/monthly-costs`) wordt de looptijd afgerond naar hele jaren:

```typescript
term_years: Math.round((d.org_lpt || 360) / 12),
```

Dit veroorzaakt een verschil: bij een looptijd van 260 maanden wordt `Math.round(260/12) = 22` jaar (= 264 maanden) gebruikt in de berekening. Daardoor is de bruto maandlast in de totaalrij (stap 5) **lager** dan het individuele leningdeel — een verschil van ca. €17.

## Oplossing

De backend accepteert nu decimale waarden voor `term_years`. Verwijder de `Math.round()` zodat de exacte looptijd wordt doorgestuurd.

## Wijziging

Zoek **alle plekken** in de codebase waar `term_years` wordt gezet bij het bouwen van een request naar `/calculate/monthly-costs`. Vervang overal:

```typescript
// OUD — afgerond naar hele jaren
term_years: Math.round((d.org_lpt || 360) / 12),

// NIEUW — exacte decimale waarde
term_years: (d.org_lpt || 360) / 12,
```

Dit geldt in ieder geval voor:
- De maandlasten-berekening op **stap 5** (Maandlasten)
- De risicoscenario-berekeningen (adviesrapport)
- Eventuele andere plekken waar `term_years` wordt berekend

## Verificatie

| Check | Verwacht |
|-------|----------|
| Leningdeel met 260 mnd looptijd | `term_years: 21.666...` (niet 22) |
| Leningdeel met 360 mnd looptijd | `term_years: 30` (geen verschil, was al rond) |
| Totaal maandlast = som leningdelen | Geen verschil meer tussen individueel en totaal |
| Stap 5: bruto maandlast per deel = totaalrij | Bedragen kloppen exact |

## Samenvatting

| Bestand | Wijziging |
|---------|-----------|
| Alle bestanden met `term_years: Math.round(...)` | Verwijder `Math.round()` |
