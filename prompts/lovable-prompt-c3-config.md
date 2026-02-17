# Lovable Prompt — Stap C3: Admin Config Dashboard

> Kopieer deze prompt in Lovable om config-beheer toe te voegen aan de admin-pagina.

---

## Wat moet er gebeuren?

De `/admin` pagina heeft nu alleen "Gebruikersbeheer" (rollen toewijzen). We voegen een tweede tab "Configuratie" toe waarmee admins fiscale parameters, calculator defaults en geldverstrekkers kunnen bewerken.

De NAT API heeft nieuwe PUT endpoints:
- `PUT /config/fiscaal-frontend` — fiscale parameters voor de frontend
- `PUT /config/fiscaal` — calculator defaults
- `PUT /config/geldverstrekkers` — geldverstrekkers lijst

Alle PUT endpoints vereisen dezelfde `X-API-Key` header als `/calculate`.

---

## Stap 1: Tab-navigatie op Admin pagina

Wijzig `src/pages/Admin.tsx` om twee tabs te tonen:

```tsx
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

// In de return, na de admin-check:
<div className="container mx-auto py-8 px-4 max-w-5xl">
  <h1 className="text-2xl font-bold mb-6">Beheer</h1>

  <Tabs defaultValue="gebruikers">
    <TabsList>
      <TabsTrigger value="gebruikers">Gebruikersbeheer</TabsTrigger>
      <TabsTrigger value="configuratie">Configuratie</TabsTrigger>
    </TabsList>

    <TabsContent value="gebruikers">
      {/* Bestaande gebruikerstabel hier naartoe verplaatsen */}
    </TabsContent>

    <TabsContent value="configuratie">
      <ConfigEditor />
    </TabsContent>
  </Tabs>
</div>
```

Verplaats de bestaande gebruikerstabel (Card met "Gebruikers") in de `TabsContent value="gebruikers"`.

---

## Stap 2: Maak `src/components/admin/ConfigEditor.tsx`

Dit is het hoofdcomponent voor config-beheer. Het heeft drie accordions (secties).

### Data ophalen bij mount:

```typescript
import { useState, useEffect } from 'react';
import { useToast } from '@/hooks/use-toast';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel,
  AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger
} from '@/components/ui/alert-dialog';

const NAT_API_BASE = 'https://nat-hypotheek-api.onrender.com';

export function ConfigEditor() {
  const { toast } = useToast();
  const [fiscaalFrontend, setFiscaalFrontend] = useState<any>(null);
  const [fiscaal, setFiscaal] = useState<any>(null);
  const [geldverstrekkers, setGeldverstrekkers] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);

  async function fetchAll() {
    try {
      const [ff, f, gv] = await Promise.all([
        fetch(`${NAT_API_BASE}/config/fiscaal-frontend`).then(r => r.json()),
        fetch(`${NAT_API_BASE}/config/fiscaal`).then(r => r.json()),
        fetch(`${NAT_API_BASE}/config/geldverstrekkers`).then(r => r.json()),
      ]);
      setFiscaalFrontend(ff);
      setFiscaal(f);
      setGeldverstrekkers(gv);
    } catch (e) {
      toast({
        title: "Fout bij laden configuratie",
        description: "Kon config niet ophalen van NAT API.",
        variant: "destructive",
      });
    }
    setIsLoading(false);
  }

  useEffect(() => { fetchAll(); }, []);

  if (isLoading) return <p className="text-muted-foreground">Configuratie laden...</p>;

  // ... secties hieronder
}
```

### Save-functie:

```typescript
const NAT_API_KEY = import.meta.env.VITE_NAT_API_KEY || 'hf-nat-2026-production';

async function saveConfig(configName: string, data: any) {
  setSaving(configName);
  try {
    const response = await fetch(`${NAT_API_BASE}/config/${configName}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': NAT_API_KEY,
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.detail || 'Opslaan mislukt');
    }

    const result = await response.json();

    if (!result.github_committed) {
      toast({
        title: "Opgeslagen (zonder GitHub)",
        description: "Wijziging is actief maar niet naar GitHub geschreven. Bij volgende deploy wordt deze reset.",
        variant: "default",
      });
    } else {
      toast({
        title: "Configuratie opgeslagen",
        description: `${configName} is bijgewerkt en naar GitHub geschreven.`,
      });
    }

    // Herlaad config
    await fetchAll();
  } catch (e: any) {
    toast({
      title: "Fout bij opslaan",
      description: e.message || "Onbekende fout",
      variant: "destructive",
    });
  }
  setSaving(null);
}
```

---

## Stap 3: Sectie "Fiscale parameters" (fiscaal-frontend.json)

Binnen het ConfigEditor component, maak een formulier met gegroepeerde velden:

```tsx
<AccordionItem value="fiscaal-frontend">
  <AccordionTrigger>
    <div className="flex items-center gap-2">
      <span className="font-semibold">Fiscale parameters</span>
      <span className="text-xs text-muted-foreground">
        (versie {fiscaalFrontend?.versie}, bijgewerkt {fiscaalFrontend?.laatst_bijgewerkt})
      </span>
    </div>
  </AccordionTrigger>
  <AccordionContent>
    {/* Formulier-groepen hieronder */}
  </AccordionContent>
</AccordionItem>
```

**Maak een herbruikbare NumberField component:**

```tsx
function NumberField({ label, value, onChange, prefix, suffix, step }: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  prefix?: string;
  suffix?: string;
  step?: number;
}) {
  return (
    <div className="flex items-center gap-2">
      <Label className="w-48 text-sm shrink-0">{label}</Label>
      {prefix && <span className="text-sm text-muted-foreground">{prefix}</span>}
      <Input
        type="number"
        value={value}
        step={step || 1}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-32"
      />
      {suffix && <span className="text-sm text-muted-foreground">{suffix}</span>}
    </div>
  );
}
```

**Groepen in het formulier:**

Gebruik `fiscaalFrontend` state. Bij wijziging van een veld: update de state met een spread + nested update.

**Groep: NHG**

| Label | Veld pad | Prefix/Suffix | Step |
|-------|----------|---------------|------|
| NHG grens | parameters.nhgGrens | € | 1000 |
| NHG provisie | parameters.nhgProvisie | | 0.001 |

Toon nhgProvisie als percentage: waarde × 100 weergeven, bij invoer ÷ 100 opslaan.

**Groep: Belasting**

| Label | Veld pad | Weergave | Step |
|-------|----------|----------|------|
| Tarief Box 1 | parameters.belastingtariefBox1 | % (×100) | 0.0001 |
| Tarief Box 1 hoog | parameters.belastingtariefBox1Hoog | % (×100) | 0.0001 |
| Grens Box 1 hoog | parameters.grensBox1Hoog | € | 1 |

**Groep: AOW**

| Label | Veld pad | Prefix/Suffix |
|-------|----------|---------------|
| AOW leeftijd (jaren) | parameters.aowLeeftijdJaren | |
| AOW leeftijd (maanden) | parameters.aowLeeftijdMaanden | |
| Jaarbedrag alleenstaand | aow_jaarbedragen.alleenstaand | € |
| Jaarbedrag samenwonend | aow_jaarbedragen.samenwonend | € |

**Groep: Overdrachtsbelasting**

| Label | Veld pad | Weergave |
|-------|----------|----------|
| Tarief woning | parameters.overdrachtsbelastingWoning | % (×100) |
| Tarief overig | parameters.overdrachtsbelastingOverig | % (×100) |
| Startersvrijstelling grens | parameters.startersVrijstellingGrens | € |
| Startersvrijstelling max leeftijd | parameters.startersMaxLeeftijd | jaar |

**Groep: Looptijd & rente**

| Label | Veld pad | Suffix |
|-------|----------|--------|
| Standaard looptijd (jaren) | parameters.standaardLooptijdJaren | |
| Standaard looptijd (maanden) | parameters.standaardLooptijdMaanden | |
| Toetsrente | parameters.toetsrente | % |

**Let op:** `toetsrente` is opgeslagen als percentage (5.0), niet als decimaal. Toon en bewerk direct als getal.

**Groep: Kosten**

| Label | Veld pad | Prefix |
|-------|----------|--------|
| BKR forfait | parameters.bkrForfait | € |
| Taxatiekosten | parameters.taxatiekosten | € |
| Hypotheekadvieskosten | parameters.hypotheekadvieskosten | € |

**Opslaan knop onderaan:**

```tsx
<AlertDialog>
  <AlertDialogTrigger asChild>
    <Button disabled={saving === 'fiscaal-frontend'}>
      {saving === 'fiscaal-frontend' ? 'Opslaan...' : 'Fiscale parameters opslaan'}
    </Button>
  </AlertDialogTrigger>
  <AlertDialogContent>
    <AlertDialogHeader>
      <AlertDialogTitle>Configuratie wijzigen?</AlertDialogTitle>
      <AlertDialogDescription>
        Deze wijziging wordt direct doorgevoerd voor alle gebruikers.
      </AlertDialogDescription>
    </AlertDialogHeader>
    <AlertDialogFooter>
      <AlertDialogCancel>Annuleren</AlertDialogCancel>
      <AlertDialogAction onClick={() => saveConfig('fiscaal-frontend', fiscaalFrontend)}>
        Opslaan
      </AlertDialogAction>
    </AlertDialogFooter>
  </AlertDialogContent>
</AlertDialog>
```

---

## Stap 4: Sectie "Calculator defaults" (fiscaal.json)

Kleiner formulier met een waarschuwing bovenaan:

```tsx
<AccordionItem value="fiscaal">
  <AccordionTrigger>
    <div className="flex items-center gap-2">
      <span className="font-semibold">Calculator defaults</span>
      <span className="text-xs text-muted-foreground">
        (versie {fiscaal?.versie})
      </span>
    </div>
  </AccordionTrigger>
  <AccordionContent>
    <div className="bg-amber-50 border border-amber-200 rounded-md p-3 mb-4">
      <p className="text-sm text-amber-800">
        Deze waarden zijn defaults voor de rekenkern. Wijzig alleen als je zeker weet wat je doet.
      </p>
    </div>

    {/* Velden */}
  </AccordionContent>
</AccordionItem>
```

**Velden:**

| Label | Veld pad | Suffix |
|-------|----------|--------|
| Toetsrente (decimaal) | defaults.c_toets_rente | (bijv. 0.05 = 5%) |
| Actuele 10jr rente | defaults.c_actuele_10jr_rente | |
| RVP toetsrente (mnd) | defaults.c_rvp_toets_rente | maanden |
| Factor 2e inkomen | defaults.c_factor_2e_inkomen | |
| Standaard looptijd (mnd) | defaults.c_lpt | maanden |
| Alleenstaande grens O | defaults.c_alleen_grens_o | € |
| Alleenstaande grens B | defaults.c_alleen_grens_b | € |
| Alleenstaande factor | defaults.c_alleen_factor | € |

Zelfde Opslaan-patroon met AlertDialog als bij Stap 3.

---

## Stap 5: Sectie "Geldverstrekkers" (geldverstrekkers.json)

```tsx
<AccordionItem value="geldverstrekkers">
  <AccordionTrigger>
    <div className="flex items-center gap-2">
      <span className="font-semibold">Geldverstrekkers</span>
      <span className="text-xs text-muted-foreground">
        ({geldverstrekkers?.geldverstrekkers?.length} stuks)
      </span>
    </div>
  </AccordionTrigger>
  <AccordionContent>
    {/* Bewerkbare lijst */}
  </AccordionContent>
</AccordionItem>
```

### Geldverstrekkers lijst:

Toon elke geldverstrekker als een rij met:
- Tekstveld (Input) met de naam
- Verwijder-knop (rood × icoon, `Trash2` uit lucide-react)
- Disable verwijderen als er maar 1 item is

Onderaan een "Toevoegen" knop die een lege rij toevoegt.

```tsx
{geldverstrekkers.geldverstrekkers.map((naam: string, index: number) => (
  <div key={index} className="flex items-center gap-2 mb-2">
    <Input
      value={naam}
      onChange={(e) => {
        const updated = [...geldverstrekkers.geldverstrekkers];
        updated[index] = e.target.value;
        setGeldverstrekkers({...geldverstrekkers, geldverstrekkers: updated});
      }}
      className="flex-1"
    />
    <Button
      variant="ghost"
      size="icon"
      className="text-red-500 hover:text-red-700"
      onClick={() => {
        const updated = geldverstrekkers.geldverstrekkers.filter((_: any, i: number) => i !== index);
        setGeldverstrekkers({...geldverstrekkers, geldverstrekkers: updated});
      }}
      disabled={geldverstrekkers.geldverstrekkers.length <= 1}
    >
      <Trash2 className="h-4 w-4" />
    </Button>
  </div>
))}

<Button
  variant="outline"
  onClick={() => {
    setGeldverstrekkers({
      ...geldverstrekkers,
      geldverstrekkers: [...geldverstrekkers.geldverstrekkers, ""]
    });
  }}
>
  + Toevoegen
</Button>
```

### Productlijnen:

Toon de productlijnen als een apart blok onder de geldverstrekkers-lijst. Per geldverstrekker die in `productlijnen` staat:

```tsx
<h4 className="font-medium mt-6 mb-2">Productlijnen</h4>
{Object.entries(geldverstrekkers.productlijnen || {}).map(([bank, lijnen]: [string, any]) => (
  <div key={bank} className="mb-4 pl-4 border-l-2 border-gray-200">
    <p className="font-medium text-sm mb-1">{bank}</p>
    {lijnen.map((lijn: string, i: number) => (
      <div key={i} className="flex items-center gap-2 mb-1">
        <Input
          value={lijn}
          onChange={(e) => {
            const updated = {...geldverstrekkers.productlijnen};
            updated[bank] = [...updated[bank]];
            updated[bank][i] = e.target.value;
            setGeldverstrekkers({...geldverstrekkers, productlijnen: updated});
          }}
          className="flex-1 h-8 text-sm"
        />
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 text-red-500"
          onClick={() => {
            const updated = {...geldverstrekkers.productlijnen};
            updated[bank] = updated[bank].filter((_: any, idx: number) => idx !== i);
            if (updated[bank].length === 0) delete updated[bank];
            setGeldverstrekkers({...geldverstrekkers, productlijnen: updated});
          }}
        >
          <Trash2 className="h-3 w-3" />
        </Button>
      </div>
    ))}
  </div>
))}
```

Zelfde Opslaan-patroon met AlertDialog. Bij opslaan: sorteer de `geldverstrekkers` array alfabetisch.

---

## Stap 6: Versie-info bovenaan

Bovenaan de Configuratie tab, haal `/config/versie` op en toon in een klein grijs blokje:

```tsx
const [versieInfo, setVersieInfo] = useState<any>(null);

useEffect(() => {
  fetch(`${NAT_API_BASE}/config/versie`)
    .then(r => r.json())
    .then(setVersieInfo);
}, []);

// In de render:
{versieInfo && (
  <div className="text-xs text-muted-foreground mb-4 flex gap-4">
    <span>API: v{versieInfo.api_versie}</span>
    <span>Config: {versieInfo.config_versies?.fiscaal_frontend || '?'}</span>
  </div>
)}
```

---

## Verificatie

1. **Tabs:** Open `/admin` → twee tabs zichtbaar (Gebruikersbeheer, Configuratie)
2. **Laden:** Klik "Configuratie" → drie secties laden met huidige waarden
3. **Bewerken:** Wijzig NHG grens naar 475.000 → klik Opslaan → bevestigingsdialoog → groene toast
4. **Persistentie:** Herlaad pagina → NHG grens toont 475.000
5. **Validatie:** Voer een negatief getal in → API geeft foutmelding → rode toast
6. **Geldverstrekkers:** Voeg "Test Bank" toe → Opslaan → verschijnt in lijst
7. **Calculator defaults:** Waarschuwing zichtbaar, waarden bewerkbaar

---

## Samenvatting

| Bestand | Wijziging |
|---------|-----------|
| `src/pages/Admin.tsx` | Tabs toevoegen (Gebruikersbeheer + Configuratie) |
| `src/components/admin/ConfigEditor.tsx` | **Nieuw** — config editor met 3 secties |
