# Lovable Prompt J1: Frontend opschonen — Berekeningen naar backend migreren

> Dit prompt verwijdert ~400 regels dead code uit de frontend en vervangt lokale berekeningen door bestaande API-responses. Na deze wijziging is de backend de single source of truth voor alle financiële berekeningen.

---

## Overzicht van wijzigingen

1. **Dead code verwijderen** uit `berekeningen.ts` (~320 regels)
2. **Dead code verwijderen** uit `fiscaleParameters.ts` (~30 regels)
3. **Dead import/component verwijderen** uit `Aankoop.tsx`
4. **Bruto maandlast** vervangen door API-response
5. **AOW berekeningen** centraliseren via API-cached hook
6. **Gewogen werkelijke rente** uit API-response halen

---

## Deel A: Dead code verwijderen uit `berekeningen.ts`

### A1. Functies verwijderen

Verwijder de volgende functies volledig uit `src/utils/berekeningen.ts`. Ze worden nergens geïmporteerd of alleen door andere dead functies aangeroepen:

```typescript
// VERWIJDER deze functies:
berekenNatResultaat()         // ~128 regels — vervangen door POST /calculate API
berekenMaxHypotheek()         // ~58 regels — vervangen door POST /calculate API
bepaalWoonquote()             // ~36 regels — vervangen door POST /calculate API
berekenToetslast()            // ~28 regels — alleen door berekenNatResultaat
berekenWerkelijkeLast()       // ~26 regels — alleen door berekenNatResultaat
berekenGewogenGemiddeldeRente() // ~10 regels — nu in API debug response
berekenGewogenToetsrente()    // ~11 regels — nu in API debug response
bepaalToetsrente()            // ~5 regels — nu in API debug response
berekenAnnuiteitMaandlast()   // ~10 regels — alleen door dead functies
berekenLineaireMaandlast()    // ~18 regels — alleen door dead functies
berekenAflossingsvrij()       // ~3 regels — alleen door dead functies
berekenTotaleRente()          // ~3 regels — geen imports
berekenTotaleKosten()         // ~3 regels — geen imports
berekenNHGKosten()            // ~3 regels — geen imports
berekenOverdrachtsbelasting() // ~3 regels — geen imports
genereerAflosschema()         // ~43 regels — geïmporteerd maar nooit aangeroepen
```

### A2. Constanten die mee kunnen

Verwijder ook constanten die alleen door dead functies gebruikt worden:

```typescript
// VERWIJDER als ze alleen door bovenstaande functies gebruikt worden:
const MAANDEN_PER_JAAR = 12;     // behoud als het ook door actieve functies gebruikt wordt
const TOETSRENTE_DEFAULT = 0.05; // alleen door dead functies
```

Controleer per constante of een actieve functie deze nog nodig heeft. Zo ja: behoud.

### A3. Behoud deze functies

Deze functies zijn actief in gebruik en moeten **NIET** verwijderd worden:

```typescript
// BEHOUD:
berekenTotaleInvestering()        // real-time form feedback
berekenEigenMiddelen()            // real-time form feedback
berekenBenodigdeHypotheek()       // real-time form feedback
getAankoopBedrag()                // helper voor woningtype
berekenTotaalHypotheekBedrag()    // som leningdelen
formatBedrag()                    // formatting
formatBedragDecimaal()            // formatting
formatPercentage()                // formatting
```

### A4. Exports opschonen

Verwijder alle `export` statements voor de verwijderde functies. Controleer of er TypeScript interfaces/types zijn die alleen door dead functies gebruikt worden — verwijder die ook.

---

## Deel B: Dead code verwijderen uit `fiscaleParameters.ts`

### B1. Functies verwijderen

Verwijder de volgende functies uit `src/utils/fiscaleParameters.ts`. Ze worden nergens geïmporteerd:

```typescript
// VERWIJDER:
berekenAowDatum()            // duplicaat van aowBerekeningen.ts
bereiktAowBinnenLooptijd()   // geen imports gevonden
berekenLeeftijd()            // geen imports gevonden
heeftStartersvrijstelling()  // geen imports gevonden
```

### B2. Behoud

```typescript
// BEHOUD:
FISCALE_PARAMETERS_2026      // constanten object
getFiscaleParameters()       // merge met API config
isNhgMogelijk()              // NHG check
```

---

## Deel C: Dead imports verwijderen uit `Aankoop.tsx`

### C1. AflosschemaTable en genereerAflosschema

In `src/pages/Aankoop.tsx`:

1. Verwijder de import van `genereerAflosschema` (deze functie wordt nergens aangeroepen)
2. Verwijder de import van `AflosschemaTable` component (wordt niet gerenderd in de JSX)
3. Verwijder eventuele state-variabelen die met het aflosschema te maken hebben (bijv. `aflosschemaData`)

```typescript
// VERWIJDER deze imports:
import { genereerAflosschema } from '@/utils/berekeningen';
import { AflosschemaTable } from '@/components/AflosschemaTable';
```

---

## Deel D: Bruto maandlast uit API i.p.v. lokale berekening

### D1. Huidige situatie

In `SamenvattingStep.tsx` en/of `MaandlastenSummaryCard` wordt `berekenMaandlasten()` uit `berekeningen.ts` gebruikt voor de bruto maandlast. Deze functie doet een **vereenvoudigde** berekening: vlak belastingtarief, geen EWF, geen Wet Hillen, geen partner-optimalisatie.

De hook `useMonthlyCostsCalculation` roept al `POST /calculate/monthly-costs` aan en retourneert het volledige API-resultaat, dat **nauwkeurigere** waarden bevat.

### D2. Wijziging

Vervang de lokale `berekenMaandlasten()` aanroep door de API-response velden:

```typescript
// OUD (lokale berekening):
const maandlasten = berekenMaandlasten({
  leningDelen: scenario.leningDelen,
  belastingtariefBox1: fiscaleParams.belastingtariefBox1,
});
// brutoBedrag, renteaftrek, nettoBedrag

// NIEUW (uit API response):
// De monthlyCostsResult bevat al:
// - total_gross_monthly → bruto maandlast
// - net_monthly_cost → netto maandlast
// - tax_breakdown.net_tax_effect_monthly → renteaftrek effect
// - loan_parts[].gross_payment → bruto per leningdeel

const result = monthlyCostsResults[scenarioId];
if (result) {
  const brutoMaandlast = result.total_gross_monthly;
  const nettoMaandlast = result.net_monthly_cost;
  const renteaftrekEffect = result.tax_breakdown.net_tax_effect_monthly;
}
```

### D3. Per leningdeel breakdown

De API retourneert ook per leningdeel de bruto maandlast:

```typescript
// Per leningdeel uit API:
result.loan_parts.forEach(part => {
  // part.loan_part_id → "deel_1_box1"
  // part.gross_payment → bruto maandlast dit deel
  // part.interest_payment → rentegedeelte
  // part.principal_payment → aflossingsgedeelte
});
```

### D4. Na de wijziging

Verwijder `berekenMaandlasten()` uit `berekeningen.ts` (als het niet al in Deel A is verwijderd) en verwijder de import in de componenten die het gebruikten.

---

## Deel E: AOW berekeningen centraliseren

### E1. Nieuwe hook: `useAOWData.ts`

Maak een nieuwe hook `src/hooks/useAOWData.ts` die de bestaande `GET /aow-categorie` API aanroept en het resultaat cachet per geboortedatum:

```typescript
import { useState, useCallback, useRef } from 'react';

const API_BASE_URL = import.meta.env.VITE_NAT_API_URL || 'https://nat-hypotheek-api.onrender.com';

interface AOWData {
  categorie: 'AOW_BEREIKT' | 'BINNEN_10_JAAR' | 'MEER_DAN_10_JAAR';
  aow_datum: string;       // "YYYY-MM-DD"
  jaren_tot_aow: number;
}

// Cache buiten de hook zodat het gedeeld wordt tussen componenten
const aowCache = new Map<string, AOWData>();

export function useAOWData() {
  const [loading, setLoading] = useState(false);

  const getAOWData = useCallback(async (geboortedatum: string): Promise<AOWData | null> => {
    if (!geboortedatum) return null;

    // Check cache
    const cached = aowCache.get(geboortedatum);
    if (cached) return cached;

    try {
      setLoading(true);
      const response = await fetch(
        `${API_BASE_URL}/aow-categorie?geboortedatum=${geboortedatum}`
      );
      if (!response.ok) return null;

      const data: AOWData = await response.json();
      aowCache.set(geboortedatum, data);
      return data;
    } catch {
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const isAOWBereikt = useCallback(async (geboortedatum: string): Promise<boolean> => {
    const data = await getAOWData(geboortedatum);
    return data?.categorie === 'AOW_BEREIKT';
  }, [getAOWData]);

  const isAOWBinnen10Jaar = useCallback(async (geboortedatum: string): Promise<boolean> => {
    const data = await getAOWData(geboortedatum);
    return data?.categorie === 'BINNEN_10_JAAR';
  }, [getAOWData]);

  return { getAOWData, isAOWBereikt, isAOWBinnen10Jaar, loading };
}
```

### E2. Bestaande imports vervangen

Vervang in de volgende bestanden de directe import van `aowBerekeningen.ts` door de nieuwe hook:

**`src/hooks/useAanvraagMaxHypotheek.ts`:**
```typescript
// OUD:
import { isAOWBereikt } from '@/utils/aowBerekeningen';
// ...
const aowBereikt = isAOWBereikt(geboortedatum);

// NIEUW:
import { useAOWData } from '@/hooks/useAOWData';
// ...
const { isAOWBereikt } = useAOWData();
const aowBereikt = await isAOWBereikt(geboortedatum);
```

**`src/hooks/useAanvraagMaxHypotheekOver10Jaar.ts`:**
```typescript
// OUD:
import { bepaalAOWCategorie, berekenAOWDatum } from '@/utils/aowBerekeningen';

// NIEUW:
import { useAOWData } from '@/hooks/useAOWData';
const { getAOWData } = useAOWData();
const aowData = await getAOWData(geboortedatum);
// aowData.categorie → 'BINNEN_10_JAAR', etc.
// aowData.aow_datum → '2032-06-15'
```

**`src/pages/Aankoop.tsx` en `src/pages/Aanpassen.tsx`:**
```typescript
// OUD:
import { isAOWBinnen10Jaar, isAOWBereikt } from '@/utils/aowBerekeningen';

// NIEUW:
import { useAOWData } from '@/hooks/useAOWData';
const { getAOWData } = useAOWData();
// Gebruik getAOWData() in useEffect of event handler
```

**`src/components/aanvraag/sections/HaalbaarheidsForm.tsx`:**
```typescript
// OUD:
import { isAOWBereikt } from '@/utils/aowBerekeningen';

// NIEUW:
import { useAOWData } from '@/hooks/useAOWData';
```

### E3. aowBerekeningen.ts markeren als deprecated

Voeg bovenaan `src/utils/aowBerekeningen.ts` een opmerking toe:

```typescript
/**
 * @deprecated Gebruik useAOWData hook in plaats van deze functies.
 * Deze module wordt behouden als lokale fallback maar moet niet meer direct geïmporteerd worden.
 * AOW-berekeningen worden nu via de backend API gedaan (GET /aow-categorie).
 */
```

### E4. Async afhandeling

Let op: de nieuwe hook retourneert **Promises** in plaats van synchrone waarden. In componenten die dit in een `useEffect` of event handler gebruiken gaat dit goed. In plekken waar het synchron nodig is (bijv. een render-functie), gebruik een state-variabele:

```typescript
const [aowBereikt, setAowBereikt] = useState(false);
const { isAOWBereikt } = useAOWData();

useEffect(() => {
  if (geboortedatum) {
    isAOWBereikt(geboortedatum).then(setAowBereikt);
  }
}, [geboortedatum, isAOWBereikt]);
```

---

## Deel F: Gewogen werkelijke rente uit API

### F1. Huidige situatie

De gewogen werkelijke rente wordt in de UI weergegeven in de resultaten. De frontend berekent dit lokaal (of deed dit — het is nu dead code).

### F2. Wijziging

De backend `POST /calculate` retourneert nu `debug.gewogen_werkelijke_rente` in de response. Gebruik dit veld:

```typescript
// In natApiService.ts of waar de NAT API response verwerkt wordt:
const natResultaat = {
  ...bestaandeVelden,
  gewogenWerkelijkeRente: apiResponse.debug.gewogen_werkelijke_rente * 100, // decimaal → percentage
};
```

Zoek in de codebase waar de gewogen werkelijke rente wordt weergegeven (waarschijnlijk in de leningdelen-totaalrij in de resultaten) en gebruik `natResultaat.gewogenWerkelijkeRente` in plaats van een lokale berekening.

---

## Verificatie-tabel

| # | Check | Verwacht resultaat |
|---|-------|--------------------|
| 1 | `berekeningen.ts` bevat geen dead functies meer | Alleen investering/formatting functies overblijven (~280 regels) |
| 2 | `fiscaleParameters.ts` bevat geen dead functies meer | Alleen constanten + getFiscaleParameters + isNhgMogelijk |
| 3 | Geen TypeScript compilatiefouten | `npm run build` slaagt |
| 4 | Haalbaarheidsberekening werkt nog | Max hypotheek wordt correct berekend via API |
| 5 | SamenvattingStep toont bruto/netto maandlasten | Uit API response, niet lokaal berekend |
| 6 | AOW-waarschuwing werkt in Aankoop/Aanpassen | Via useAOWData hook + API cache |
| 7 | Gewogen werkelijke rente wordt correct getoond | Uit API debug.gewogen_werkelijke_rente |
| 8 | Geen `genereerAflosschema` of `AflosschemaTable` imports | Verwijderd uit Aankoop.tsx |

---

## Samenvatting bestanden

| Bestand | Actie | Wijziging |
|---------|-------|-----------|
| `src/utils/berekeningen.ts` | Wijzig | ~400 regels dead code verwijderen |
| `src/utils/fiscaleParameters.ts` | Wijzig | 4 dead functies verwijderen |
| `src/utils/aowBerekeningen.ts` | Wijzig | @deprecated markering toevoegen |
| `src/hooks/useAOWData.ts` | Nieuw | API-cached AOW hook |
| `src/hooks/useAanvraagMaxHypotheek.ts` | Wijzig | AOW via useAOWData hook |
| `src/hooks/useAanvraagMaxHypotheekOver10Jaar.ts` | Wijzig | AOW via useAOWData hook |
| `src/pages/Aankoop.tsx` | Wijzig | Dead imports verwijderen, AOW via hook |
| `src/pages/Aanpassen.tsx` | Wijzig | AOW via hook |
| `src/components/aanvraag/sections/HaalbaarheidsForm.tsx` | Wijzig | AOW via hook |
| `src/components/SamenvattingStep.tsx` | Wijzig | Bruto maandlast uit API |
| `src/services/natApiService.ts` | Wijzig | gewogenWerkelijkeRente uit debug response |
