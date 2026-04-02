# N8 — Vernieuwen-knop op import banner

## Context

De import-data wordt nu gecached in Supabase. De banner laadt instant (geen wachttijd meer). Maar als er nieuwe documenten verwerkt worden, moet de adviseur de cache kunnen verversen.

## Wat moet er veranderen

### ImportBanner.tsx — Vernieuwen-knop toevoegen

Voeg een kleine "vernieuwen" knop toe naast de bestaande knoppen:

```tsx
<div className="flex gap-2 mt-2">
  <Button variant="outline" size="sm" onClick={() => setDialogOpen(true)}>
    Bekijk details
  </Button>
  {hasActionable && (
    <Button size="sm" onClick={() => setDialogOpen(true)}>
      Importeer nieuwe velden
    </Button>
  )}
  <Button
    variant="ghost"
    size="sm"
    onClick={async () => {
      // Force refresh: voeg ?refresh=true toe aan de API call
      setRefreshing(true);
      try {
        const { data: { session } } = await supabase.auth.getSession();
        const params = new URLSearchParams({ context });
        if (targetId) params.set('target_id', targetId);
        params.set('refresh', 'true');

        const resp = await window.fetch(
          `${API_CONFIG.NAT_API_URL}/doc-processing/${dossierId}/available-imports?${params}`,
          { headers: { 'Authorization': `Bearer ${session?.access_token ?? ''}` } }
        );
        if (resp.ok) {
          refresh(); // herlaad vanuit hook
        }
      } catch {}
      setRefreshing(false);
    }}
    disabled={refreshing}
  >
    <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin' : ''}`} />
  </Button>
</div>
```

Voeg `refreshing` state toe:
```tsx
const [refreshing, setRefreshing] = useState(false);
```

Import `RefreshCw` van Lucide.

### Optioneel: toon "gecached" indicator

Als de response `cached: true` bevat, toon een subtiele tekst:

```tsx
{data.cached && data.cache_updated_at && (
  <p className="text-xs text-muted-foreground">
    Laatst bijgewerkt: {new Date(data.cache_updated_at).toLocaleString('nl-NL')}
  </p>
)}
```

---

## Verificatie

| # | Check | Verwacht |
|---|-------|----------|
| 1 | Berekening openen | Banner laadt instant (uit cache) |
| 2 | Klik vernieuwen-knop | Spinner, ~10s, daarna bijgewerkte data |
| 3 | Geen TypeScript fouten | `npm run build` slaagt |

## Samenvatting bestanden

| Bestand | Wijziging |
|---------|-----------|
| `src/components/dossier/ImportBanner.tsx` | Vernieuwen-knop + refreshing state |
