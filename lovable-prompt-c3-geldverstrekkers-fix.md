# Lovable Prompt — Geldverstrekkers sectie verbeteren

> Kopieer deze prompt in Lovable om de Geldverstrekkers sectie in de Config Editor te verbeteren.

---

## Wat moet er veranderen?

De huidige Geldverstrekkers sectie in `ConfigEditor.tsx` toont geldverstrekkers als een platte lijst met daaronder apart de productlijnen. Dit moet worden vervangen door een interactieve lijst waar je op een geldverstrekker klikt om de productlijnen te zien en bewerken.

**Belangrijk:** De data komt uit de NAT API (`GET /config/geldverstrekkers`). De JSON-structuur is:

```json
{
  "geldverstrekkers": ["ABN AMRO", "Aegon", ...],
  "productlijnen": {
    "ABN AMRO": ["Budget Hypotheek", "Woning Hypotheek"],
    "Aegon": ["Hypotheek"],
    ...
  }
}
```

Elke geldverstrekker in de `geldverstrekkers` array heeft **altijd** een entry in `productlijnen` met minimaal 1 productlijn.

---

## Nieuwe UX voor Geldverstrekkers accordion

Vervang de huidige inhoud van `<AccordionItem value="geldverstrekkers">` met het volgende ontwerp:

### Geldverstrekkers lijst (overzicht)

Toon elke geldverstrekker als een **klikbare rij** met:
- Links: naam van de geldverstrekker (klikbaar om te expanden)
- Midden: aantal productlijnen in grijs, bijv. "(2 productlijnen)"
- Rechts: verwijder-knop (Trash2 icoon, rood)

```tsx
import { ChevronDown, ChevronRight, Trash2, Plus } from 'lucide-react';

// State voor welke geldverstrekker is open
const [expandedBank, setExpandedBank] = useState<string | null>(null);
```

Per geldverstrekker:

```tsx
{geldverstrekkers.geldverstrekkers.map((naam: string, index: number) => {
  const lijnen = geldverstrekkers.productlijnen?.[naam] || [];
  const isExpanded = expandedBank === naam;

  return (
    <div key={index} className="border rounded-md mb-2">
      {/* Header rij — klik om te expanden */}
      <div
        className="flex items-center gap-2 p-3 cursor-pointer hover:bg-gray-50"
        onClick={() => setExpandedBank(isExpanded ? null : naam)}
      >
        {isExpanded ? (
          <ChevronDown className="h-4 w-4 text-gray-500 shrink-0" />
        ) : (
          <ChevronRight className="h-4 w-4 text-gray-500 shrink-0" />
        )}

        <span className="font-medium flex-1">{naam}</span>

        <span className="text-xs text-muted-foreground">
          ({lijnen.length} productlijn{lijnen.length !== 1 ? 'en' : ''})
        </span>

        {/* Verwijder geldverstrekker + alle productlijnen */}
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 text-red-500 hover:text-red-700"
          onClick={(e) => {
            e.stopPropagation(); // voorkom expanden bij klik op delete
            const updatedList = geldverstrekkers.geldverstrekkers.filter(
              (_: any, i: number) => i !== index
            );
            const updatedProd = { ...geldverstrekkers.productlijnen };
            delete updatedProd[naam];
            setGeldverstrekkers({
              ...geldverstrekkers,
              geldverstrekkers: updatedList,
              productlijnen: updatedProd,
            });
            if (isExpanded) setExpandedBank(null);
          }}
          disabled={geldverstrekkers.geldverstrekkers.length <= 1}
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>

      {/* Productlijnen (zichtbaar als expanded) */}
      {isExpanded && (
        <div className="px-3 pb-3 pt-1 border-t bg-gray-50/50">
          <p className="text-xs text-muted-foreground mb-2 font-medium uppercase tracking-wide">
            Productlijnen
          </p>

          {lijnen.map((lijn: string, i: number) => (
            <div key={i} className="flex items-center gap-2 mb-1">
              <Input
                value={lijn}
                onChange={(e) => {
                  const updated = { ...geldverstrekkers.productlijnen };
                  updated[naam] = [...updated[naam]];
                  updated[naam][i] = e.target.value;
                  setGeldverstrekkers({
                    ...geldverstrekkers,
                    productlijnen: updated,
                  });
                }}
                className="flex-1 h-8 text-sm"
              />
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 text-red-500 hover:text-red-700"
                onClick={() => {
                  const updated = { ...geldverstrekkers.productlijnen };
                  updated[naam] = updated[naam].filter(
                    (_: any, idx: number) => idx !== i
                  );
                  setGeldverstrekkers({
                    ...geldverstrekkers,
                    productlijnen: updated,
                  });
                }}
                disabled={lijnen.length <= 1}
              >
                <Trash2 className="h-3 w-3" />
              </Button>
            </div>
          ))}

          {/* Productlijn toevoegen */}
          <Button
            variant="outline"
            size="sm"
            className="mt-1"
            onClick={() => {
              const updated = { ...geldverstrekkers.productlijnen };
              updated[naam] = [...(updated[naam] || []), ""];
              setGeldverstrekkers({
                ...geldverstrekkers,
                productlijnen: updated,
              });
            }}
          >
            <Plus className="h-3 w-3 mr-1" /> Productlijn toevoegen
          </Button>
        </div>
      )}
    </div>
  );
})}
```

### Geldverstrekker toevoegen

Onderaan de lijst een knop om een nieuwe geldverstrekker toe te voegen:

```tsx
<Button
  variant="outline"
  className="mt-2"
  onClick={() => {
    const nieuweNaam = "Nieuwe geldverstrekker";
    setGeldverstrekkers({
      ...geldverstrekkers,
      geldverstrekkers: [...geldverstrekkers.geldverstrekkers, nieuweNaam],
      productlijnen: {
        ...geldverstrekkers.productlijnen,
        [nieuweNaam]: ["Hypotheek"],
      },
    });
    setExpandedBank(nieuweNaam);
  }}
>
  <Plus className="h-4 w-4 mr-1" /> Geldverstrekker toevoegen
</Button>
```

### Geldverstrekker naam bewerken

Maak de naam van de geldverstrekker bewerkbaar in de expanded view. Voeg dit toe bovenaan de expanded sectie, boven de productlijnen:

```tsx
{isExpanded && (
  <div className="px-3 pb-3 pt-1 border-t bg-gray-50/50">
    {/* Naam bewerken */}
    <div className="flex items-center gap-2 mb-3">
      <Label className="text-xs shrink-0">Naam:</Label>
      <Input
        value={naam}
        onChange={(e) => {
          const oudeNaam = naam;
          const nieuweNaam = e.target.value;
          const updatedList = [...geldverstrekkers.geldverstrekkers];
          updatedList[index] = nieuweNaam;
          const updatedProd = { ...geldverstrekkers.productlijnen };
          updatedProd[nieuweNaam] = updatedProd[oudeNaam];
          delete updatedProd[oudeNaam];
          setGeldverstrekkers({
            ...geldverstrekkers,
            geldverstrekkers: updatedList,
            productlijnen: updatedProd,
          });
          setExpandedBank(nieuweNaam);
        }}
        className="flex-1 h-8 text-sm font-medium"
      />
    </div>

    {/* Productlijnen hieronder ... */}
  </div>
)}
```

### Opslaan validatie

Bij het opslaan van geldverstrekkers, voeg deze validaties toe vóór het aanroepen van `saveConfig`:

```typescript
// Validatie: elke geldverstrekker moet minimaal 1 productlijn hebben
const legeProductlijnen = geldverstrekkers.geldverstrekkers.filter(
  (naam: string) => !geldverstrekkers.productlijnen?.[naam]?.length
);
if (legeProductlijnen.length > 0) {
  toast({
    title: "Validatiefout",
    description: `Elke geldverstrekker moet minimaal 1 productlijn hebben. Check: ${legeProductlijnen.join(', ')}`,
    variant: "destructive",
  });
  return;
}

// Validatie: geen lege namen
const legeNamen = geldverstrekkers.geldverstrekkers.filter(
  (naam: string) => !naam.trim()
);
if (legeNamen.length > 0) {
  toast({
    title: "Validatiefout",
    description: "Er zijn geldverstrekkers zonder naam. Vul alle namen in of verwijder ze.",
    variant: "destructive",
  });
  return;
}

// Sorteer alfabetisch bij opslaan
const sorted = [...geldverstrekkers.geldverstrekkers].sort((a, b) =>
  a.localeCompare(b, 'nl')
);
const sortedData = {
  ...geldverstrekkers,
  geldverstrekkers: sorted,
};

saveConfig('geldverstrekkers', sortedData);
```

---

## Verwijder de oude "Productlijnen" sectie

De oude aparte "PRODUCTLIJNEN" sectie onder de geldverstrekkers-lijst (met `Object.entries(geldverstrekkers.productlijnen)`) moet volledig verwijderd worden. De productlijnen zitten nu **binnen** elke expanded geldverstrekker.

---

## Verificatie

1. Klik op een geldverstrekker → productlijnen worden zichtbaar
2. Klik nogmaals → productlijnen klappen in
3. Bewerk een productlijn naam → waarde verandert in het formulier
4. Verwijder een productlijn → verdwijnt (maar minimaal 1 moet overblijven, knop disabled)
5. Voeg productlijn toe → nieuwe lege rij verschijnt
6. Klik op emmertje achter geldverstrekker → geldverstrekker + productlijnen verdwijnen
7. Voeg nieuwe geldverstrekker toe → verschijnt onderaan, expanded, met 1 default productlijn
8. Opslaan → bevestigingsdialoog → groene toast → data persistent na refresh

---

## Samenvatting

| Bestand | Wijziging |
|---------|-----------|
| `src/components/admin/ConfigEditor.tsx` | Geldverstrekkers sectie vervangen met klikbare expandable lijst |
