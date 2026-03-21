# M3 — Risicobereidheid velden verbergen op basis van klantsituatie

## Wat moet er gebeuren

Op de Adviespagina (AdviesPage.tsx) worden risicobereidheid-velden getoond die niet altijd van toepassing zijn:

1. **Alleenstaande klant:** verberg "Relatiebeëindiging" (overlijden wél tonen — LTV-perspectief)
2. **Alle personen AOW-gerechtigd:** verberg "Pensioen", "Arbeidsongeschiktheid" en "Werkloosheid"

De backend filtert deze al uit het rapport — de frontend moet de invoervelden ook verbergen.

## Wijzigingen

### Bestand: `src/pages/AdviesPage.tsx`

De risicobereidheid dropdowns staan in een grid. Voeg condities toe:

```typescript
// Bepaal of klant alleenstaand is en of AOW bereikt
const isAlleenstaand = !data.heeftPartner;
const isAllePersonenAOW = aowAanvrager?.isAOWBereikt && (!data.heeftPartner || aowPartner?.isAOWBereikt);
```

Bij elk risicobereidheid-veld: toon alleen als van toepassing.

```tsx
{/* Pensioen: verberg als alle personen AOW */}
{!isAllePersonenAOW && (
  <div>
    <Label>Pensioen</Label>
    <Select value={risicoPensioen} onValueChange={setRisicoPensioen}>...</Select>
  </div>
)}

{/* Overlijden: altijd tonen (stel: inkomensperspectief, alleenstaand: LTV-perspectief) */}
<div>
  <Label>Overlijden</Label>
  <Select value={risicoOverlijden} onValueChange={setRisicoOverlijden}>...</Select>
</div>

{/* AO: verberg als alle personen AOW */}
{!isAllePersonenAOW && (
  <div>
    <Label>Arbeidsongeschiktheid</Label>
    <Select value={risicoAO} onValueChange={setRisicoAO}>...</Select>
  </div>
)}

{/* WW: verberg als alle personen AOW */}
{!isAllePersonenAOW && (
  <div>
    <Label>Werkloosheid</Label>
    <Select value={risicoWW} onValueChange={setRisicoWW}>...</Select>
  </div>
)}

{/* Relatiebeëindiging: verberg als alleenstaand */}
{!isAlleenstaand && (
  <div>
    <Label>Relatiebeëindiging</Label>
    <Select value={risicoRelatie} onValueChange={setRisicoRelatie}>...</Select>
  </div>
)}

{/* Waardedaling, Rentestijging, Aflopen hypotheekrenteaftrek: altijd tonen */}
```

### AOW-data ophalen

`useAOWData` is waarschijnlijk al beschikbaar of te importeren:

```typescript
import { useAOWData } from '@/hooks/useAOWData';

const aowAanvrager = useAOWData(data.klantGegevens?.geboortedatumAanvrager);
const aowPartner = useAOWData(data.klantGegevens?.geboortedatumPartner);
```

## Verificatie

| Test | Verwacht |
|------|---------|
| Alleenstaande klant | Geen "Relatiebeëindiging" veld, "Overlijden" wél zichtbaar |
| Stel | Alle velden zichtbaar |
| Gepensioneerde alleenstaande (AOW bereikt) | Overlijden + Waardedaling, Rentestijging, Aflopen hypotheekrenteaftrek |
| Stel, beide AOW | Geen Pensioen/AO/WW, wél Overlijden en Relatiebeëindiging |
| Stel, één AOW | Alle velden (AO/WW nog relevant voor de niet-AOW partner) |
