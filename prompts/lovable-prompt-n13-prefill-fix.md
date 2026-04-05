# N13 — Fix: prefill=true maakt altijd een nieuwe aanvraag

## Probleem

Bij `?prefill=true` checkt Aanvraag.tsx of er al een aanvraag bestaat voor het dossier. Als die bestaat → laadt die → prefill wordt overgeslagen. Maar de adviseur wil een NIEUWE aanvraag met vooringevulde data.

## Fix

### Aanvraag.tsx — loadAanvraag useEffect

Bij `prefill=true`: sla het zoeken naar een bestaande aanvraag over. Haal altijd de prefill data op.

```tsx
const loadAanvraag = async () => {
  const prefillParam = searchParams.get('prefill');
  
  if (prefillParam === 'true') {
    // ALTIJD prefill ophalen, NOOIT bestaande aanvraag laden
    try {
      const { data: { session } } = await supabase.auth.getSession();
      const resp = await window.fetch(
        `${API_CONFIG.NAT_API_URL}/doc-processing/${dossierId}/prefill-aanvraag`,
        { headers: { 'Authorization': `Bearer ${session?.access_token ?? ''}` } }
      );
      if (resp.ok) {
        const result = await resp.json();
        if (result.prefill_data && Object.keys(result.prefill_data).length > 0) {
          setAanvraagData(sanitizeAanvraagData(result.prefill_data));
          toast({ title: `${result.velden_count} velden vooringevuld uit documenten` });
        } else if (result.error) {
          toast({ title: result.error, variant: 'destructive' });
          setAanvraagData(prefillFromDossier(dossier));
        } else {
          setAanvraagData(prefillFromDossier(dossier));
        }
      } else {
        setAanvraagData(prefillFromDossier(dossier));
      }
    } catch {
      setAanvraagData(prefillFromDossier(dossier));
    }
  } else {
    // Bestaande flow: laad bestaande aanvraag of prefill uit dossier
    let existingAanvraag: StoredAanvraag | undefined;
    if (aanvraagIdParam) {
      existingAanvraag = await getAanvraag(aanvraagIdParam);
    } else {
      existingAanvraag = await getRecenteAanvraagByDossier(dossierId);
    }
    if (existingAanvraag) {
      setStoredAanvraag(existingAanvraag);
      setAanvraagData(sanitizeAanvraagData(existingAanvraag.data));
    } else {
      setAanvraagData(prefillFromDossier(dossier));
    }
  }
  
  const naam = await computeAanvraagNaam(dossier, fromBerekening);
  setComputedAanvraagNaam(naam);
  setIsInitialized(true);
};
```

**Belangrijk:** bij `prefill=true` wordt `setStoredAanvraag` NIET aangeroepen. Hierdoor is `storedAanvraag` null → bij opslaan wordt een NIEUWE aanvraag aangemaakt (niet een bestaande overschreven).

---

## Verificatie

| # | Check | Verwacht |
|---|-------|----------|
| 1 | Dossier met cache → "Vooringevuld" → Volgende | Formulier instant gevuld, toast "50 velden vooringevuld" |
| 2 | Dossier zonder cache → "Vooringevuld" → Volgende | Toast "Verwerk eerst documenten", leeg formulier |
| 3 | Dossier met bestaande aanvraag → "Vooringevuld" | NIEUWE aanvraag met prefill, niet bestaande geladen |
| 4 | Opslaan na prefill | Nieuwe aanvraag-rij in Supabase (nieuw UUID) |

## Samenvatting bestanden

| Bestand | Wijziging |
|---------|-----------|
| `src/pages/Aanvraag.tsx` | Bij prefill=true: skip bestaande aanvraag, haal prefill op |
