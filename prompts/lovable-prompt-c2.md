# Lovable Prompt — Stap C2: Config ophalen uit NAT API

> Kopieer deze prompt in Lovable om de hardcoded configuratiedata te vervangen door API-gestuurde config.

---

## Wat moet er gebeuren?

De NAT API heeft 3 nieuwe endpoints die alle configuratiedata bevatten die nu hardcoded in de frontend staat. We gaan:

1. Een `useNatConfig` hook maken die bij app-mount alle config ophaalt
2. Een `NatConfigContext` maken zodat elk component bij de config kan
3. Alle hardcoded arrays en parameters vervangen door config-lookups
4. Hardcoded waarden behouden als fallback (als de API niet bereikbaar is)

## NAT API base URL

```
https://nat-hypotheek-api.onrender.com
```

## Nieuwe endpoints (publiek, geen API-key nodig)

| Endpoint | Wat het retourneert |
|----------|---------------------|
| `GET /config/fiscaal-frontend` | Fiscale parameters (NHG, belasting, AOW-bedragen) |
| `GET /config/geldverstrekkers` | 36 hypotheekverstrekkers + productlijnen |
| `GET /config/dropdowns` | Alle dropdown-opties (beroepen, woning, instellingen) |

---

## Stap 1: Maak `src/hooks/useNatConfig.ts`

```typescript
import { useState, useEffect } from 'react';

const NAT_API_BASE = 'https://nat-hypotheek-api.onrender.com';

export interface NatFiscaalFrontend {
  versie: string;
  parameters: {
    nhgGrens: number;
    nhgProvisie: number;
    belastingtariefBox1: number;
    belastingtariefBox1Hoog: number;
    grensBox1Hoog: number;
    aowLeeftijdJaren: number;
    aowLeeftijdMaanden: number;
    overdrachtsbelastingWoning: number;
    overdrachtsbelastingOverig: number;
    startersVrijstellingGrens: number;
    startersMaxLeeftijd: number;
    standaardLooptijdJaren: number;
    standaardLooptijdMaanden: number;
    toetsrente: number;
    jaar: number;
    datumIngang: string;
  };
  aow_jaarbedragen: {
    alleenstaand: number;
    samenwonend: number;
    toelichting: string;
  };
}

export interface NatGeldverstrekkers {
  versie: string;
  geldverstrekkers: string[];
  productlijnen: Record<string, string[]>;
}

export interface NatDropdowns {
  versie: string;
  inkomen: {
    soort_berekening: { value: string; label: string }[];
    soort_dienstverband: string[];
    arbeidsmarktscan_fase: string[];
    beroepstype: string[];
  };
  woning: {
    woningtoepassing: { value: string; label: string }[];
    type_woning: { value: string; label: string }[];
    soort_onderpand: { value: string; label: string }[];
    soort_onderpand_per_type: Record<string, string[]>;
    default_soort_per_type: Record<string, string>;
    energielabel: { value: string; label: string }[];
    waarde_vastgesteld_met: { value: string; label: string }[];
    overdrachtsbelasting_opties: { value: number; label: string }[];
    woningstatus: { value: string; label: string }[];
  };
  financiele_instellingen: string[];
}

export interface NatConfig {
  fiscaal: NatFiscaalFrontend | null;
  geldverstrekkers: NatGeldverstrekkers | null;
  dropdowns: NatDropdowns | null;
  isLoaded: boolean;
  error: string | null;
}

// In-memory cache (blijft bestaan zolang de tab open is)
let cachedConfig: NatConfig | null = null;

export function useNatConfig(): NatConfig {
  const [config, setConfig] = useState<NatConfig>(
    cachedConfig ?? { fiscaal: null, geldverstrekkers: null, dropdowns: null, isLoaded: false, error: null }
  );

  useEffect(() => {
    if (cachedConfig?.isLoaded) return; // Al geladen

    async function fetchAll() {
      try {
        const [fiscaalRes, gvRes, ddRes] = await Promise.all([
          fetch(`${NAT_API_BASE}/config/fiscaal-frontend`),
          fetch(`${NAT_API_BASE}/config/geldverstrekkers`),
          fetch(`${NAT_API_BASE}/config/dropdowns`),
        ]);

        if (!fiscaalRes.ok || !gvRes.ok || !ddRes.ok) {
          throw new Error('Een of meer config-endpoints niet bereikbaar');
        }

        const result: NatConfig = {
          fiscaal: await fiscaalRes.json(),
          geldverstrekkers: await gvRes.json(),
          dropdowns: await ddRes.json(),
          isLoaded: true,
          error: null,
        };

        cachedConfig = result;
        setConfig(result);
        console.log('NAT Config loaded:', {
          fiscaal: result.fiscaal?.versie,
          geldverstrekkers: result.geldverstrekkers?.versie,
          dropdowns: result.dropdowns?.versie,
        });
      } catch (err) {
        console.warn('NAT Config fetch failed, using fallbacks:', err);
        setConfig(prev => ({ ...prev, isLoaded: true, error: String(err) }));
      }
    }

    fetchAll();
  }, []);

  return config;
}
```

## Stap 2: Maak `src/contexts/NatConfigContext.tsx`

```typescript
import { createContext, useContext } from 'react';
import { useNatConfig, type NatConfig } from '@/hooks/useNatConfig';

const NatConfigContext = createContext<NatConfig>({
  fiscaal: null,
  geldverstrekkers: null,
  dropdowns: null,
  isLoaded: false,
  error: null,
});

export function NatConfigProvider({ children }: { children: React.ReactNode }) {
  const config = useNatConfig();
  return (
    <NatConfigContext.Provider value={config}>
      {children}
    </NatConfigContext.Provider>
  );
}

export function useNatConfigContext() {
  return useContext(NatConfigContext);
}
```

## Stap 3: Wrap de app met de Provider

In `App.tsx`, wrap de bestaande app-content met `<NatConfigProvider>`:

```typescript
import { NatConfigProvider } from '@/contexts/NatConfigContext';

// In de return, omheen de bestaande providers:
<NatConfigProvider>
  {/* bestaande app content */}
</NatConfigProvider>
```

## Stap 4: Vervang hardcoded waarden in componenten

### 4a. `src/utils/fiscaleParameters.ts`

Behoud `FISCALE_PARAMETERS_2026` als fallback-default. Voeg een helper toe:

```typescript
import type { NatFiscaalFrontend } from '@/hooks/useNatConfig';

// Bestaande FISCALE_PARAMETERS_2026 blijft als fallback
export function getFiscaleParameters(natConfig: NatFiscaalFrontend | null) {
  if (!natConfig) return FISCALE_PARAMETERS_2026;
  return {
    ...FISCALE_PARAMETERS_2026,
    nhgGrens: natConfig.parameters.nhgGrens,
    nhgProvisie: natConfig.parameters.nhgProvisie,
    belastingtariefBox1: natConfig.parameters.belastingtariefBox1,
    belastingtariefBox1Hoog: natConfig.parameters.belastingtariefBox1Hoog,
    grensBox1Hoog: natConfig.parameters.grensBox1Hoog,
    aowLeeftijdJaren: natConfig.parameters.aowLeeftijdJaren,
    aowLeeftijdMaanden: natConfig.parameters.aowLeeftijdMaanden,
    overdrachtsbelastingWoning: natConfig.parameters.overdrachtsbelastingWoning,
    overdrachtsbelastingOverig: natConfig.parameters.overdrachtsbelastingOverig,
    startersVrijstellingGrens: natConfig.parameters.startersVrijstellingGrens,
    startersMaxLeeftijd: natConfig.parameters.startersMaxLeeftijd,
    standaardLooptijdJaren: natConfig.parameters.standaardLooptijdJaren,
    standaardLooptijdMaanden: natConfig.parameters.standaardLooptijdMaanden,
    toetsrente: natConfig.parameters.toetsrente,
    jaar: natConfig.parameters.jaar,
    datumIngang: natConfig.parameters.datumIngang,
  };
}
```

### 4b. Componenten die `FISCALE_PARAMETERS_2026` gebruiken

In deze bestanden:
- `src/pages/Aankoop.tsx`
- `src/pages/Aanpassen.tsx`
- `src/components/ResultCards.tsx`
- `src/components/SamenvattingStep.tsx`
- `src/utils/berekeningen.ts`
- `src/components/aanvraag/sections/FinancieringsopzetSection.tsx`

Vervang het directe gebruik van `FISCALE_PARAMETERS_2026` door `getFiscaleParameters(natConfig.fiscaal)`. In componenten gebruik je `const { fiscaal } = useNatConfigContext()` en roep je `getFiscaleParameters(fiscaal)` aan.

Voor `berekeningen.ts` (geen component): geef de fiscale parameters als argument mee aan functies die ze gebruiken, zodat de aanroepende component de config doorgeeft.

### 4c. Dropdown-componenten — vervang hardcoded arrays

**`InkomenEditLoondienst.tsx`** — Vervang:
- `BEROEPSTYPE_OPTIONS` → `natConfig.dropdowns?.inkomen.beroepstype ?? BEROEPSTYPE_OPTIONS`
- `SOORT_DIENSTVERBAND_OPTIONS` → `natConfig.dropdowns?.inkomen.soort_dienstverband ?? SOORT_DIENSTVERBAND_OPTIONS`
- `SOORT_BEREKENING_OPTIONS` → `natConfig.dropdowns?.inkomen.soort_berekening ?? SOORT_BEREKENING_OPTIONS`

**`ArbeidsmarktscanSection.tsx`** — Vervang:
- `BEROEPSTYPE_OPTIONS` → `natConfig.dropdowns?.inkomen.beroepstype ?? BEROEPSTYPE_OPTIONS`
- `SOORT_DIENSTVERBAND_OPTIONS` → `natConfig.dropdowns?.inkomen.soort_dienstverband ?? SOORT_DIENSTVERBAND_OPTIONS`
- `FASE_OPTIONS` → `natConfig.dropdowns?.inkomen.arbeidsmarktscan_fase ?? FASE_OPTIONS`

**`FlexibelJaarinkomenSection.tsx`** — Vervang:
- `BEROEPSTYPE_OPTIONS` → `natConfig.dropdowns?.inkomen.beroepstype ?? BEROEPSTYPE_OPTIONS`
- `SOORT_DIENSTVERBAND_OPTIONS` → `natConfig.dropdowns?.inkomen.soort_dienstverband ?? SOORT_DIENSTVERBAND_OPTIONS`

**`WerkgeversverklaringSection.tsx`** — Vervang:
- `BEROEPSTYPE_OPTIONS` → `natConfig.dropdowns?.inkomen.beroepstype ?? BEROEPSTYPE_OPTIONS`
- `SOORT_DIENSTVERBAND_OPTIONS` → `natConfig.dropdowns?.inkomen.soort_dienstverband ?? SOORT_DIENSTVERBAND_OPTIONS`

**`WoningSection.tsx`** — Vervang:
- `woningToepassingOptions` → `natConfig.dropdowns?.woning.woningtoepassing ?? woningToepassingOptions`
- `soortOnderpandAllOptions` → `natConfig.dropdowns?.woning.soort_onderpand ?? soortOnderpandAllOptions`
- `soortOnderpandPerType` → `natConfig.dropdowns?.woning.soort_onderpand_per_type ?? soortOnderpandPerType`
- `typeWoningOptions` → `natConfig.dropdowns?.woning.type_woning ?? typeWoningOptions`
- `energielabelWoningOpties` → `natConfig.dropdowns?.woning.energielabel ?? energielabelWoningOpties`
- `waardeVastgesteldMetOptions` → `natConfig.dropdowns?.woning.waarde_vastgesteld_met ?? waardeVastgesteldMetOptions`
- `woningstatusOptions` → `natConfig.dropdowns?.woning.woningstatus ?? woningstatusOptions`

**`OnderpandSection.tsx`** — Zelfde als WoningSection (bevat dezelfde duplicaat-arrays).

**`FinancieringsopzetSection.tsx`** — Vervang:
- `overdrachtsbelastingOpties` → `natConfig.dropdowns?.woning.overdrachtsbelasting_opties ?? overdrachtsbelastingOpties`

**`HuidigeHypotheekSection.tsx`** — Vervang:
- `GELDVERSTREKKER_OPTIONS` → `natConfig.geldverstrekkers?.geldverstrekkers ?? GELDVERSTREKKER_OPTIONS`

**`VerplichtingenSection.tsx`** — Vervang:
- Import van `nederlandseBanken` → `natConfig.dropdowns?.financiele_instellingen ?? nederlandseBanken`

**`src/utils/vermogenAanvraagTypes.ts`** — Behoud `nederlandseBanken` als fallback-default. Componenten die het gebruiken halen het nu via config.

### 4d. Geldverstrekkers productlijnen

Als een component de productlijnen per geldverstrekker toont, gebruik dan:
```typescript
const productlijnen = natConfig.geldverstrekkers?.productlijnen?.[geselecteerdeVerstrekker] ?? [];
```

## Stap 5: Toon een melding als config niet geladen kon worden

In `App.tsx` (of een layout-component), toon een subtiele toast als `natConfig.error` gevuld is:

```typescript
const { error } = useNatConfigContext();

useEffect(() => {
  if (error) {
    toast({ title: 'Config kon niet geladen worden', description: 'Standaardwaarden worden gebruikt.', variant: 'default' });
  }
}, [error]);
```

## Verificatie na implementatie

1. Open de app → console moet tonen: `NAT Config loaded: { fiscaal: "2026", geldverstrekkers: "2026", dropdowns: "2026" }`
2. Check dropdowns: beroepen-lijst moet 67 opties bevatten
3. Check NHG: moet €470.000 zijn met 0,4% provisie
4. Test offline: zet de NAT API URL tijdelijk naar iets fouts → app moet werken met fallback-waarden + toast-melding
5. Check dat alle pagina's nog correct laden (Aankoop, Aanpassen, Aanvraag)

## Samenvatting gewijzigde bestanden

| Bestand | Wijziging |
|---------|-----------|
| `src/hooks/useNatConfig.ts` | **Nieuw** — fetcht 3 endpoints, cache in memory |
| `src/contexts/NatConfigContext.tsx` | **Nieuw** — React context + provider |
| `App.tsx` | Wrap met `NatConfigProvider` + error toast |
| `src/utils/fiscaleParameters.ts` | `getFiscaleParameters()` helper toegevoegd |
| `src/utils/berekeningen.ts` | Gebruik `getFiscaleParameters()` ipv direct `FISCALE_PARAMETERS_2026` |
| `src/pages/Aankoop.tsx` | Config via context ipv hardcoded |
| `src/pages/Aanpassen.tsx` | Config via context ipv hardcoded |
| `src/components/ResultCards.tsx` | Config via context ipv hardcoded |
| `src/components/SamenvattingStep.tsx` | Config via context ipv hardcoded |
| `src/components/aanvraag/sections/InkomenEditLoondienst.tsx` | Dropdowns via config |
| `src/components/aanvraag/sections/ArbeidsmarktscanSection.tsx` | Dropdowns via config |
| `src/components/aanvraag/sections/FlexibelJaarinkomenSection.tsx` | Dropdowns via config |
| `src/components/aanvraag/sections/WerkgeversverklaringSection.tsx` | Dropdowns via config |
| `src/components/aanvraag/sections/WoningSection.tsx` | Dropdowns via config |
| `src/components/aanvraag/sections/OnderpandSection.tsx` | Dropdowns via config |
| `src/components/aanvraag/sections/FinancieringsopzetSection.tsx` | Overdrachtsbelasting + fiscaal via config |
| `src/components/aanvraag/sections/HuidigeHypotheekSection.tsx` | Geldverstrekkers via config |
| `src/components/aanvraag/sections/VerplichtingenSection.tsx` | Financiële instellingen via config |

**Belangrijk:** Behoud ALLE hardcoded arrays als fallback-defaults. Verwijder ze NIET. Ze dienen als vangnet als de API niet bereikbaar is.
