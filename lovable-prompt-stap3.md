# Lovable Prompt — Stap 3: Laatste duplicaties opruimen

> Kopieer deze prompt in Lovable om de laatste hardcoded waarden te vervangen door config uit de NAT API.

---

## Wat moet er gebeuren?

Na de C2-implementatie (config externalisatie) zijn er nog 3 waarden hardcoded in de frontend die nu ook beschikbaar zijn via de NAT Config API. Deze moeten vervangen worden zodat ALLE configureerbare waarden uit één bron komen.

De 3 nieuwe waarden staan in `GET /config/fiscaal-frontend` onder `parameters`:

```json
{
  "parameters": {
    "bkrForfait": 100,
    "taxatiekosten": 695,
    "hypotheekadvieskosten": 3500,
    ...bestaande parameters...
  }
}
```

---

## Stap 1: TypeScript interface bijwerken

In `src/hooks/useNatConfig.ts`, voeg de 3 nieuwe velden toe aan de `NatFiscaalFrontend` interface:

```typescript
export interface NatFiscaalFrontend {
  versie: string;
  parameters: {
    // ...bestaande velden...
    toetsrente: number;
    bkrForfait: number;         // NIEUW
    taxatiekosten: number;      // NIEUW
    hypotheekadvieskosten: number; // NIEUW
    jaar: number;
    datumIngang: string;
  };
  aow_jaarbedragen: { ... };
}
```

## Stap 2: Fallback-defaults bijwerken

In `src/utils/fiscaleParameters.ts`, voeg de 3 waarden toe aan `FISCALE_PARAMETERS_2026` (de fallback):

```typescript
export const FISCALE_PARAMETERS_2026 = {
  // ...bestaande waarden...
  bkrForfait: 100,
  taxatiekosten: 695,
  hypotheekadvieskosten: 3500,
};
```

En in `getFiscaleParameters()`, map de 3 nieuwe velden mee:

```typescript
export function getFiscaleParameters(natConfig: NatFiscaalFrontend | null) {
  if (!natConfig) return FISCALE_PARAMETERS_2026;
  return {
    ...FISCALE_PARAMETERS_2026,
    // ...bestaande mappings...
    bkrForfait: natConfig.parameters.bkrForfait,
    taxatiekosten: natConfig.parameters.taxatiekosten,
    hypotheekadvieskosten: natConfig.parameters.hypotheekadvieskosten,
  };
}
```

## Stap 3: Vervang hardcoded waarden in componenten

### 3a. BKR-forfait (€100)

Zoek in de hele codebase naar het getal `100` in de context van BKR/limieten. Het staat waarschijnlijk in:
- `src/components/aanvraag/sections/BkrSection.tsx` of vergelijkbaar
- `src/utils/fiscaleParameters.ts`

Vervang elke hardcoded `100` (BKR-forfait) door `params.bkrForfait` waarbij `params` komt uit `getFiscaleParameters(fiscaal)`.

### 3b. Taxatiekosten (€695)

Zoek naar het getal `695` in de codebase. Het staat waarschijnlijk in:
- `src/utils/fiscaleParameters.ts`
- `src/pages/Aankoop.tsx` of `FinancieringsopzetSection.tsx`

Vervang door `params.taxatiekosten`.

### 3c. Hypotheekadvieskosten (€3.500)

Zoek naar het getal `3500` in de codebase. Het staat waarschijnlijk in:
- `src/utils/fiscaleParameters.ts`
- `src/pages/Aankoop.tsx` of `FinancieringsopzetSection.tsx`

Vervang door `params.hypotheekadvieskosten`.

## Stap 4: Controleer resterende duplicaten

Zoek in de hele codebase of er nog hardcoded duplicaten zijn van waarden die al in de config staan:

1. **Overdrachtsbelasting `0.02`** — moet overal uit `params.overdrachtsbelastingWoning` komen (niet hardcoded `0.02` of `2`)
2. **NHG-grens** — moet overal uit `params.nhgGrens` komen (niet hardcoded `470000` of `435000`)
3. **NHG-provisie** — moet overal uit `params.nhgProvisie` komen (niet hardcoded `0.004` of `0.006`)

Als je ergens nog een hardcoded waarde vindt die ook in `params` staat, vervang deze.

---

## Verificatie

1. Open de app → console toont `NAT Config loaded: { fiscaal: "2026", ... }`
2. Ga naar een dossier → BKR-limieten sectie moet correct werken (forfait €100 per limiet)
3. Ga naar Financieringsopzet → taxatiekosten (€695) en advieskosten (€3.500) moeten correct zijn
4. Zoek in de broncode naar `100`, `695`, `3500`, `0.02`, `470000` — er mogen geen hardcoded duplicaten meer zijn buiten de fallback-defaults in `fiscaleParameters.ts`

## Samenvatting

| Bestand | Wijziging |
|---------|-----------|
| `src/hooks/useNatConfig.ts` | 3 velden toevoegen aan interface |
| `src/utils/fiscaleParameters.ts` | 3 velden in fallback + getFiscaleParameters mapping |
| BkrSection (of equivalent) | `100` → `params.bkrForfait` |
| Aankoop/Financiering componenten | `695` → `params.taxatiekosten`, `3500` → `params.hypotheekadvieskosten` |
| Overige componenten met duplicaten | Hardcoded waarden → `params.*` |
