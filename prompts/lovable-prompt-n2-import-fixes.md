# N2 — Import documenten-data naar berekening of aanvraag

## Context

De backend verwerkt documenten uit de klantmap en extraheert gegevens. Deze data kan geïmporteerd worden naar een **berekening** (Aankoop/Aanpassen) of een **aanvraag**.

Alle logica (mergen, formatteren, opslaan) zit in de backend. De frontend hoeft alleen:
1. Een lijst met checkboxes tonen
2. Een POST sturen met de geselecteerde velden
3. De pagina refreshen

### Twee API endpoints

**GET** — Beschikbare velden ophalen:
```
GET /doc-processing/{dossier_id}/available-imports?context=berekening&aanvraag_id={id}
GET /doc-processing/{dossier_id}/available-imports?context=aanvraag&aanvraag_id={id}
```

`context=berekening` geeft ~10 velden (naam, inkomen, onderpand).
`context=aanvraag` geeft ~46 velden (alles: legitimatie, werkgever, etc.).

**POST** — Geselecteerde velden importeren:
```
POST /doc-processing/{dossier_id}/apply-imports
{
  "target_id": "uuid-van-aanvraag-of-dossier",
  "context": "berekening",
  "selected_targets": ["klantGegevens.achternaamAanvrager", "inkomenGegevens.hoofdinkomenAanvrager"]
}
```

### API Response structuur

```typescript
interface AvailableImports {
  dossier_id: string;
  context: 'aanvraag' | 'berekening';
  documenten_verwerkt: number;
  inkomen_analyse: object;
  groups: ImportGroup[];        // gegroepeerd en gesorteerd door backend
  imports: ImportVeld[];        // flat lijst (voor totalen)
  samenvatting: {
    nieuw: number;
    bevestigd: number;
    afwijkend: number;
    totaal: number;
  };
}

interface ImportGroup {
  title: string;               // bijv. "Aanvrager — Inkomen"
  items: ImportVeld[];
}

interface ImportVeld {
  veld: string;
  label: string;               // Nederlands: "Bruto jaarsalaris"
  categorie: string;           // "Inkomen", "Persoonsgegevens", etc.
  persoon: 'aanvrager' | 'partner' | 'gezamenlijk';
  target: string;              // pad voor de POST (bijv. "inkomenGegevens.hoofdinkomenAanvrager")
  value_type: string;          // "currency", "date", "number", "text", "boolean", "percent"
  waarde_display: string;      // geformateerd door backend: "€ 42.768", "01-05-1983", "Ja"
  huidig_display: string | null; // huidige waarde geformateerd, of null
  waarde_extractie: any;       // ruwe waarde
  waarde_huidig: any;          // ruwe huidige waarde
  status: 'nieuw' | 'bevestigd' | 'afwijkend';
  confidence: number;
  bron_datum: string;
}
```

---

## Wat moet er gebeuren

### 1. Verwijder ImportBanner van DossierDetail.tsx

De import-banner op dossier-niveau verdwijnt. Optioneel: toon een subtiele tekstregel.

### 2. Voeg ImportBanner toe aan Aankoop.tsx

Na de pagina-header, als er een `dossierId` is:

```tsx
{dossierId && (
  <ImportBanner
    dossierId={dossierId}
    targetId={dossierId}
    context="berekening"
    onImported={() => {
      // Herlaad het dossier om bijgewerkte invoer te krijgen
      loadDossier(dossierId);
    }}
  />
)}
```

### 3. Voeg ImportBanner toe aan Aanpassen.tsx

Zelfde als Aankoop:

```tsx
{dossierId && (
  <ImportBanner
    dossierId={dossierId}
    targetId={dossierId}
    context="berekening"
    onImported={() => loadDossier(dossierId)}
  />
)}
```

### 4. Voeg ImportBanner toe aan de aanvraag-pagina

Als er een aanvraag-detailpagina is (waar je het aanvraag-formulier invult):

```tsx
{dossierId && aanvraagId && (
  <ImportBanner
    dossierId={dossierId}
    targetId={aanvraagId}
    context="aanvraag"
    onImported={() => refetchAanvraag()}
  />
)}
```

### 5. Hook: useAvailableImports.ts

```typescript
import { useState, useEffect, useCallback } from 'react';
import { API_CONFIG } from '@/config/apiConfig';
import { supabase } from '@/lib/supabaseCustom';

interface ImportVeld {
  veld: string;
  label: string;
  categorie: string;
  persoon: 'aanvrager' | 'partner' | 'gezamenlijk';
  target: string;
  value_type: string;
  waarde_display: string;
  huidig_display: string | null;
  waarde_extractie: any;
  waarde_huidig: any;
  status: 'nieuw' | 'bevestigd' | 'afwijkend';
  confidence: number;
  bron_datum: string;
}

interface ImportGroup {
  title: string;
  items: ImportVeld[];
}

interface AvailableImports {
  dossier_id: string;
  context: string;
  documenten_verwerkt: number;
  inkomen_analyse: any;
  groups: ImportGroup[];
  imports: ImportVeld[];
  samenvatting: { nieuw: number; bevestigd: number; afwijkend: number; totaal: number };
}

export function useAvailableImports(
  dossierId: string | undefined,
  targetId?: string,
  context: 'aanvraag' | 'berekening' = 'aanvraag'
) {
  const [data, setData] = useState<AvailableImports | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchData = useCallback(async () => {
    if (!dossierId) return;
    setLoading(true);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      const params = new URLSearchParams({ context });
      if (targetId) params.set('aanvraag_id', targetId);

      const resp = await window.fetch(
        `${API_CONFIG.NAT_API_URL}/doc-processing/${dossierId}/available-imports?${params}`,
        { headers: { 'Authorization': `Bearer ${session?.access_token ?? ''}` } }
      );
      if (resp.ok) setData(await resp.json());
    } catch { /* stil falen */ }
    setLoading(false);
  }, [dossierId, targetId, context]);

  useEffect(() => { fetchData(); }, [fetchData]);

  return { data, loading, refresh: fetchData };
}
```

### 6. ImportBanner.tsx

Compacte banner met "Bekijk details" en "Importeer nieuwe velden" knoppen.

```tsx
interface ImportBannerProps {
  dossierId: string;
  targetId: string;
  context: 'aanvraag' | 'berekening';
  onImported?: () => void;
}

export function ImportBanner({ dossierId, targetId, context, onImported }: ImportBannerProps) {
  const { data, loading, refresh } = useAvailableImports(dossierId, targetId, context);
  const [dialogOpen, setDialogOpen] = useState(false);

  if (loading || !data || (data.samenvatting.nieuw === 0 && data.samenvatting.afwijkend === 0)) {
    return null;
  }

  return (
    <>
      <div className="bg-accent/50 border border-primary/20 rounded-lg p-4 mb-4">
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-3">
            <FileText className="h-5 w-5 text-primary mt-0.5" />
            <div>
              <p className="font-medium text-sm">
                {data.samenvatting.nieuw} nieuwe velden beschikbaar uit documenten
                {data.samenvatting.afwijkend > 0 && (
                  <span className="text-orange-600 ml-1">
                    • {data.samenvatting.afwijkend} afwijkend
                  </span>
                )}
              </p>
              {data.inkomen_analyse?.aanvrager?.ibl_inkomen && (
                <p className="text-xs text-muted-foreground mt-1">
                  IBL toetsinkomen: € {data.inkomen_analyse.aanvrager.ibl_inkomen.toLocaleString('nl-NL')}
                </p>
              )}
            </div>
          </div>
        </div>
        <div className="flex gap-2 mt-3">
          <Button variant="outline" size="sm" onClick={() => setDialogOpen(true)}>
            Bekijk details
          </Button>
          <Button size="sm" onClick={() => {
            setDialogOpen(true);
            // Dialog opent met alle nieuwe velden geselecteerd
          }}>
            Importeer nieuwe velden
          </Button>
        </div>
      </div>

      <ImportDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        data={data}
        dossierId={dossierId}
        targetId={targetId}
        context={context}
        onImported={() => {
          refresh();
          onImported?.();
        }}
      />
    </>
  );
}
```

### 7. ImportDialog.tsx

De dialog toont de gegroepeerde velden (al gesorteerd door backend). Selectie + één POST call.

```tsx
interface ImportDialogProps {
  open: boolean;
  onClose: () => void;
  data: AvailableImports;
  dossierId: string;
  targetId: string;
  context: 'aanvraag' | 'berekening';
  onImported?: () => void;
}

export function ImportDialog({ open, onClose, data, dossierId, targetId, context, onImported }: ImportDialogProps) {
  const [selectedTargets, setSelectedTargets] = useState<Set<string>>(new Set());
  const [importing, setImporting] = useState(false);

  // Bij openen: selecteer alle "nieuw" velden
  useEffect(() => {
    if (open && data) {
      const newTargets = new Set<string>();
      for (const item of data.imports) {
        if (item.status === 'nieuw') newTargets.add(item.target);
      }
      setSelectedTargets(newTargets);
    }
  }, [open, data]);

  const toggleField = (target: string) => {
    setSelectedTargets(prev => {
      const next = new Set(prev);
      if (next.has(target)) next.delete(target);
      else next.add(target);
      return next;
    });
  };

  const handleImport = async () => {
    if (selectedTargets.size === 0) return;
    setImporting(true);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      const resp = await window.fetch(
        `${API_CONFIG.NAT_API_URL}/doc-processing/${dossierId}/apply-imports`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${session?.access_token ?? ''}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            target_id: targetId,
            context,
            selected_targets: Array.from(selectedTargets),
          }),
        }
      );
      if (!resp.ok) throw new Error('Importeren mislukt');
      const result = await resp.json();
      toast.success(`${result.imported} velden geïmporteerd`);
      onClose();
      onImported?.();
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setImporting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-2xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Beschikbare gegevens uit documenten</DialogTitle>
          <div className="flex gap-2 mt-2">
            <Badge variant="default">{data.samenvatting.nieuw} nieuw</Badge>
            <Badge variant="secondary">{data.samenvatting.bevestigd} bevestigd</Badge>
            {data.samenvatting.afwijkend > 0 && (
              <Badge variant="destructive">{data.samenvatting.afwijkend} afwijkend</Badge>
            )}
          </div>
        </DialogHeader>

        {/* Scrollbare veldenlijst */}
        <div className="flex-1 overflow-y-auto min-h-0 pr-2 space-y-4">
          {data.groups.map((group) => (
            <div key={group.title}>
              <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2 sticky top-0 bg-background py-1">
                {group.title}
              </h4>
              <div className="space-y-1">
                {group.items.map((item) => (
                  <div key={item.target} className="flex items-center gap-3 py-1.5 px-2 rounded hover:bg-muted/50">
                    {/* Checkbox — alleen voor nieuw en afwijkend */}
                    {item.status === 'bevestigd' ? (
                      <CheckCircle2 className="h-4 w-4 text-green-600 shrink-0" />
                    ) : (
                      <Checkbox
                        checked={selectedTargets.has(item.target)}
                        onCheckedChange={() => toggleField(item.target)}
                      />
                    )}

                    {/* Label + waarde */}
                    <div className="flex-1 min-w-0">
                      <span className="text-sm font-medium">{item.label}</span>
                    </div>
                    <div className="text-sm text-right shrink-0">
                      <span className="font-medium">{item.waarde_display}</span>
                    </div>
                    <div className="text-xs text-muted-foreground w-24 text-right shrink-0">
                      {item.status === 'nieuw' && 'niet ingevuld'}
                      {item.status === 'bevestigd' && '= je invoer'}
                      {item.status === 'afwijkend' && (
                        <span className="text-orange-600">≠ {item.huidig_display}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between pt-4 border-t">
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <Checkbox
              checked={
                data.imports.filter(i => i.status === 'nieuw').length > 0 &&
                data.imports.filter(i => i.status === 'nieuw').every(i => selectedTargets.has(i.target))
              }
              onCheckedChange={(checked) => {
                setSelectedTargets(prev => {
                  const next = new Set(prev);
                  for (const item of data.imports) {
                    if (item.status === 'nieuw') {
                      if (checked) next.add(item.target);
                      else next.delete(item.target);
                    }
                  }
                  return next;
                });
              }}
            />
            Selecteer alle nieuwe
          </label>
          <div className="flex gap-2">
            <Button variant="outline" onClick={onClose}>Annuleren</Button>
            <Button onClick={handleImport} disabled={selectedTargets.size === 0 || importing}>
              {importing ? 'Importeren...' : `Importeer geselecteerde (${selectedTargets.size})`}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
```

**Let op:**
- De backend retourneert `waarde_display` al geformateerd — geen formatting in de frontend nodig
- De `groups[]` array is al gesorteerd — gewoon mappen
- De `handleImport` stuurt alleen `selected_targets` (strings) naar de backend — de backend doet het mergen en opslaan
- Na import: `onImported()` callback → herlaad de pagina-data

---

## Verificatie

| # | Check | Verwacht |
|---|-------|----------|
| 1 | DossierDetail | Geen ImportBanner meer |
| 2 | Aankoop/Aanpassen pagina | Banner met ~8-10 velden |
| 3 | Aanvraag pagina | Banner met ~46 velden |
| 4 | Bouwjaar | Toont "2.009" (getal), NIET "€ 2.009" |
| 5 | Datums | DD-MM-YYYY (bijv. "01-05-1983") |
| 6 | Bedragen | € met duizendtallen (bijv. "€ 42.768") |
| 7 | Selecteer velden + klik "Importeer" | Toast "X velden geïmporteerd" |
| 8 | Na import: heropen dialog | Geïmporteerde velden staan als "bevestigd" |
| 9 | Volgorde | Aanvrager eerst, dan partner, dan gezamenlijk |
| 10 | Geen TypeScript fouten | `npm run build` slaagt |

## Samenvatting bestanden

| Bestand | Actie | Wijziging |
|---------|-------|-----------|
| `src/pages/DossierDetail.tsx` | Wijzig | Verwijder ImportBanner |
| `src/pages/Aankoop.tsx` | Wijzig | ImportBanner met context="berekening" |
| `src/pages/Aanpassen.tsx` | Wijzig | ImportBanner met context="berekening" |
| `src/hooks/useAvailableImports.ts` | Herschrijf | context parameter, nieuw interface |
| `src/components/dossier/ImportBanner.tsx` | Herschrijf | Props: dossierId, targetId, context, onImported |
| `src/components/dossier/ImportDialog.tsx` | Herschrijf | Groepen uit API, waarde_display, POST naar backend |
