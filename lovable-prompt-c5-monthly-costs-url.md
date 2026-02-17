# Lovable Prompt — Monthly Costs API URL migratie

> Kopieer deze prompt in Lovable om de maandlasten-API om te schakelen naar de geconsolideerde NAT API.

---

## Achtergrond

De maandlasten calculator (`/calculate/monthly-costs`) draaide als aparte service op `mortgage-monthly-costs.onrender.com`. Deze is nu geïntegreerd in de hoofd-API op `nat-hypotheek-api.onrender.com`. Het endpoint pad en de request/response structuur zijn **ongewijzigd**.

---

## Wat moet er veranderen

De frontend gebruikt een aparte base URL voor de maandlasten API. Deze moet gelijk worden aan de NAT API base URL. Het endpoint pad (`/calculate/monthly-costs`) blijft identiek.

### Stap 1: apiConfig.ts — verwijder aparte monthly costs URL

In `src/config/apiConfig.ts` staat een aparte base URL voor de monthly costs API, iets als:

```typescript
// OUD — aparte service:
export const MONTHLY_COSTS_API_URL = "https://mortgage-monthly-costs.onrender.com";
// of:
monthlyCosts: "https://mortgage-monthly-costs.onrender.com",
```

**Wijzig dit naar dezelfde URL als de NAT API:**

```typescript
// NIEUW — zelfde service:
export const MONTHLY_COSTS_API_URL = "https://nat-hypotheek-api.onrender.com";
// of, als het een object is:
monthlyCosts: "https://nat-hypotheek-api.onrender.com",
```

Nog beter: als er al een `NAT_API_URL` of `API_BASE_URL` constante bestaat, hergebruik die:

```typescript
// IDEAAL — één base URL voor alles:
export const MONTHLY_COSTS_API_URL = API_BASE_URL; // hergebruik bestaande constante
```

### Stap 2: monthlyCostsService.ts — controleer endpoint pad

In `src/services/monthlyCostsService.ts` wordt het endpoint aangeroepen. Het pad moet `/calculate/monthly-costs` zijn. Dit hoeft waarschijnlijk **niet** te veranderen, maar controleer:

```typescript
// Dit moet het pad zijn (ongewijzigd):
const response = await fetch(`${baseUrl}/calculate/monthly-costs`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(requestBody),
});
```

**Let op:** als de service `mortgage-monthly-costs.onrender.com` direct importeert in plaats van via `apiConfig.ts`, vervang dan ook daar de URL.

### Stap 3: Controleer alle bestanden die de oude URL gebruiken

Zoek in de hele codebase naar:
- `mortgage-monthly-costs.onrender.com`
- `mortgage-monthly-costs`

En vervang alle voorkomens door de NAT API URL. De bestanden waar dit kan voorkomen:

| Bestand | Waarschijnlijke wijziging |
|---------|--------------------------|
| `src/config/apiConfig.ts` | Base URL wijzigen |
| `src/services/monthlyCostsService.ts` | URL import controleren |
| `src/hooks/useMonthlyCostsCalculation.ts` | URL import controleren |

### Stap 4: Geen wijzigingen nodig aan request/response

De request body en response structuur zijn **exact identiek** aan de oude API. Er zijn geen wijzigingen nodig aan:
- De request payload opbouw
- De response parsing
- De TypeScript types/interfaces
- De foutafhandeling

---

## Verificatie

| # | Check | Verwacht resultaat |
|---|-------|--------------------|
| 1 | Zoek in hele codebase op `mortgage-monthly-costs` | Geen resultaten meer |
| 2 | Open Aankoop pagina → vul hypotheekgegevens in | Netto maandlasten worden berekend en getoond |
| 3 | Open Aanpassen pagina → pas leningdeel aan | Netto maandlasten worden herberekend |
| 4 | Open Samenvatting → controleer maandlasten sectie | Bedragen worden correct getoond |
| 5 | Open browser Developer Tools → Network tab | Requests gaan naar `nat-hypotheek-api.onrender.com`, niet naar `mortgage-monthly-costs` |
| 6 | Console tab | Geen CORS fouten, geen 404 errors |

---

## Samenvatting

| Bestand | Wijziging |
|---------|-----------|
| `src/config/apiConfig.ts` | Monthly costs URL → `nat-hypotheek-api.onrender.com` (of hergebruik bestaande base URL) |
| `src/services/monthlyCostsService.ts` | Controleer dat URL uit apiConfig komt |
| `src/hooks/useMonthlyCostsCalculation.ts` | Controleer dat URL uit apiConfig komt |

**Risico:** Laag. Alleen een URL wijziging, geen functionele veranderingen.
