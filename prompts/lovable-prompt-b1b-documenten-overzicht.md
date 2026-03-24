# B1b — Documenten-overzicht per dossier (SharePoint bestanden)

## Context

De backend endpoint `GET /sharepoint/klantmap/{dossier_id}` retourneert de bestanden uit de klantmap op SharePoint. We willen deze bestanden tonen in een nette documenten-tab binnen het dossier, in Hondsrug Finance styling — in plaats van de rauwe SharePoint weergave.

De API URL is geconfigureerd in `src/config/apiConfig.ts` als `API_CONFIG.NAT_API_URL`.

### API Response

```typescript
// GET ${API_CONFIG.NAT_API_URL}/sharepoint/klantmap/{dossier_id}
interface KlantmapResponse {
  sharepoint_url: string | null;
  items: {
    name: string;
    id: string;
    type: "folder" | "file";
    size: number | null;
    web_url: string | null;
    last_modified: string | null;      // ISO datetime
    last_modified_by: string | null;   // "Alex Kuijper"
  }[];
}
```

---

## Wat moet er gebeuren

### 1. Hook: `useKlantmapBestanden.ts`

```typescript
import { useState, useEffect } from 'react';
import { API_CONFIG } from '@/config/apiConfig';
import { supabase } from '@/lib/supabaseCustom';

interface KlantmapBestand {
  name: string;
  id: string;
  type: 'folder' | 'file';
  size: number | null;
  webUrl: string | null;
  lastModified: string | null;
  lastModifiedBy: string | null;
}

export function useKlantmapBestanden(dossierId: string | undefined) {
  const [bestanden, setBestanden] = useState<KlantmapBestand[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchBestanden = async () => {
    if (!dossierId) return;
    setLoading(true);
    setError(null);

    try {
      const { data: { session } } = await supabase.auth.getSession();
      const resp = await fetch(
        `${API_CONFIG.NAT_API_URL}/sharepoint/klantmap/${dossierId}`,
        {
          headers: {
            'Authorization': `Bearer ${session?.access_token ?? ''}`,
          },
        }
      );

      if (resp.ok) {
        const data = await resp.json();
        setBestanden(
          data.items
            .filter((item: any) => item.type === 'file')
            .map((item: any) => ({
              name: item.name,
              id: item.id,
              type: item.type,
              size: item.size,
              webUrl: item.web_url,
              lastModified: item.last_modified,
              lastModifiedBy: item.last_modified_by,
            }))
        );
      } else if (resp.status === 404) {
        setBestanden([]);  // Geen klantmap
      } else {
        setError('Bestanden ophalen mislukt');
      }
    } catch {
      setError('Verbinding mislukt');
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchBestanden();
  }, [dossierId]);

  return { bestanden, loading, error, refresh: fetchBestanden };
}
```

### 2. Component: `DocumentenTab.tsx`

Een tab/sectie op de dossier-detail pagina die de bestanden toont in een nette tabel.

```tsx
import { useKlantmapBestanden } from '@/hooks/useKlantmapBestanden';
import { FileText, Download, RefreshCw, FolderOpen } from 'lucide-react';

// Helper: bestandsgrootte formatteren
function formatSize(bytes: number | null): string {
  if (!bytes) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} kB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// Helper: datum formatteren
function formatDatum(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleDateString('nl-NL', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

// Helper: bestandsicoon op basis van extensie
function getFileIcon(name: string): string {
  const ext = name.split('.').pop()?.toLowerCase();
  if (ext === 'pdf') return '📄';
  if (['jpg', 'jpeg', 'png', 'tiff'].includes(ext || '')) return '🖼️';
  if (['xlsx', 'xls'].includes(ext || '')) return '📊';
  if (['docx', 'doc'].includes(ext || '')) return '📝';
  return '📎';
}
```

**Layout:**

```
┌─────────────────────────────────────────────────────────────┐
│  Documenten (7)                              [↻] [Open SP]  │
│                                                              │
│  📄 102879095N_2026-03-24.pdf     24-03-2026 10:33  A. Kuijper  │
│  📄 IBL Walter.pdf                24-03-2026 09:58  A. Kuijper  │
│  📄 IBL_resultaat_2026...pdf      24-03-2026 09:57  A. Kuijper  │
│  📄 Loonstroken_2026_PersNr...pdf 23-03-2026 20:37  A. Kuijper  │
│  📄 Loonstrook Walter van M...pdf 23-03-2026 20:37  A. Kuijper  │
│  📄 Verzekeringsbericht (1).pdf   23-03-2026 20:37  A. Kuijper  │
│  📄 Verzekeringsbericht.pdf       23-03-2026 20:37  A. Kuijper  │
│                                                              │
│  Geen documenten? Sleep bestanden naar de klantmap.          │
└─────────────────────────────────────────────────────────────┘
```

**Specificaties:**
- Titel: "Documenten ({aantal})" — alleen bestanden tellen, geen mappen
- Rechts: refresh-knop (↻) + "Open in SharePoint" knop (opent sharepoint_url)
- Tabel met kolommen: icoon + naam (klikbaar, opent web_url), gewijzigd op, gewijzigd door
- Bestandsnaam wordt afgekapt met ellipsis als te lang (`truncate` class, max ~50 tekens)
- Klik op bestandsnaam → opent het bestand in SharePoint (nieuw tabblad via web_url)
- Sorteer op `lastModified` (nieuwste bovenaan)
- Bij geen bestanden: subtiele tekst "Nog geen documenten in de klantmap"
- Bij laden: skeleton loader of spinner
- Bij fout: subtiele foutmelding met retry-knop

**Styling — gebruik bestaande Hondsrug Finance componenten:**
- Card component als wrapper
- Gebruik `text-sm` voor de tabelrijen
- `text-muted-foreground` voor datum en gewijzigd door
- `hover:bg-accent/50` op rijen voor hover-effect
- `cursor-pointer` op klikbare rijen
- Geen echte HTML `<table>` — gebruik een flex/grid layout zoals de rest van de app

### 3. Integratie in DossierDetail

Voeg de DocumentenTab toe op de dossier-detail pagina. Twee opties:

**Optie A (aanbevolen):** Als een aparte sectie/card onder de bestaande dossier-inhoud:
```tsx
<DocumentenTab dossierId={primaryDossier.id} sharepointUrl={primaryDossier.sharepointUrl} />
```

**Optie B:** Als een tab naast "Berekeningen" / "Aanvragen" als die er zijn.

Kies optie A tenzij er al een tab-structuur is op de pagina.

De component toont alleen iets als het dossier een `sharepointUrl` heeft. Als er geen SharePoint koppeling is, toon niets (geen lege card).

---

## Verificatie

| # | Check | Verwacht |
|---|-------|----------|
| 1 | Open dossier met klantmap | Documenten-sectie zichtbaar met bestanden |
| 2 | Klik op bestandsnaam | Opent in SharePoint (nieuw tabblad) |
| 3 | Klik refresh-knop | Bestanden worden opnieuw geladen |
| 4 | Klik "Open in SharePoint" | Opent klantmap in SharePoint |
| 5 | Dossier zonder klantmap | Geen documenten-sectie (niet een lege card) |
| 6 | Geen TypeScript fouten | `npm run build` slaagt |

## Samenvatting bestanden

| Bestand | Actie | Wijziging |
|---------|-------|-----------|
| Nieuw: `src/hooks/useKlantmapBestanden.ts` | Nieuw | Hook voor bestanden ophalen |
| Nieuw: `src/components/dossier/DocumentenTab.tsx` | Nieuw | Documenten overzicht component |
| `src/pages/DossierDetail.tsx` (of equivalent) | Wijzig | DocumentenTab toevoegen |
