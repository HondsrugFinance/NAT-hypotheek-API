# M3: Voorkom dubbele dossiers — definitieve fix

## Probleem

Er worden regelmatig dubbele dossiers aangemaakt voor dezelfde klant. Dit leidt tot dubbele dossiernummers en dubbele SharePoint klantmappen. Er zijn vier oorzaken:

1. **Geen dubbelklik-beveiliging** — `performSave()` is async zonder guard
2. **URL niet bijgewerkt na save** — na eerste opslag blijft de URL `/aankoop` zonder `?id=`, waardoor bij refresh/navigatie het dossierId verloren gaat
3. **SaveChoiceDialog verwarrend** — "Nieuwe berekening" knop maakt onbedoeld een nieuw dossier
4. **Partner niet gesync** — van alleenstaand naar partner schakelen voegt partner niet toe aan klantContactGegevens

## Stap 1: `saveInProgressRef` guard + visuele feedback

In `src/pages/Aankoop.tsx`, voeg toe bij de andere refs/state:

```typescript
const saveInProgressRef = useRef(false);
const [isSaving, setIsSaving] = useState(false);
```

**Wrap de VOLLEDIGE body van `performSave()` in een guard + try/finally:**

```typescript
const performSave = async (gegevens: DossierKlantGegevens, createNew: boolean = false, takeOwnership: boolean = false) => {
  // ── Guard tegen dubbelklik ──
  if (saveInProgressRef.current) return;
  saveInProgressRef.current = true;
  setIsSaving(true);

  try {
    // ── klantNaam opbouwen INCLUSIEF partner ──
    let klantNaam = gegevens.aanvrager.achternaam + (gegevens.aanvrager.voornaam ? `, ${gegevens.aanvrager.voornaam}` : '');
    if (gegevens.partner?.achternaam) {
      klantNaam += ` en ${gegevens.partner.achternaam}` + (gegevens.partner.voornaam ? `, ${gegevens.partner.voornaam}` : '');
    }

    const scenario1 = scenarios[0] || createDefaultScenario('Berekening 1');
    const scenario2 = scenarios[1] || createDefaultScenario('Berekening 2');
    const now = new Date().toISOString();

    const ownerId = takeOwnership || createNew || !originalOwnerId ? currentUserId : originalOwnerId;
    const ownerName = takeOwnership || createNew || !originalOwnerName ? currentUserName : originalOwnerName;

    const natResultatenArray = invoer.haalbaarheidsBerekeningen.map(ber => natResultaten[ber.id] || null);
    const maandlastenResultatenArray = scenarios.map(s => monthlyCostsResults[s.id] || null);
    const enrichedInvoer = {
      ...invoer,
      natResultaten: natResultatenArray,
      maandlastenResultaten: maandlastenResultatenArray,
    } as any;

    if (createNew || !dossierId) {
      const newDossier = createAankoopDossier(dossierNaam, klantNaam, enrichedInvoer, scenario1, scenario2);
      newDossier.klantContactGegevens = gegevens;
      newDossier.ownerId = currentUserId || undefined;
      newDossier.ownerName = currentUserName || undefined;
      await saveDossier(newDossier);
      setDossierId(newDossier.id);
      setKlantContactGegevens(gegevens);
      setOriginalOwnerId(currentUserId);
      setOriginalOwnerName(currentUserName);
      toast({ title: 'Berekening opgeslagen' });

      // ── KRITIEK: URL bijwerken met ?id= zodat dossierId niet verloren gaat ──
      const newParams = new URLSearchParams(searchParams);
      newParams.set('id', newDossier.id);
      newParams.delete('dossierId');  // parentDossierId verwijderen
      navigate(`?${newParams.toString()}`, { replace: true });

      snapshotRef.current = JSON.stringify({ invoer, scenarios });
      setIsDirty(false);
    } else {
      const dossier: AankoopDossier = {
        id: dossierId,
        type: 'aankoop',
        naam: dossierNaam,
        klantNaam,
        klantContactGegevens: gegevens,
        aanmaakDatum: now,
        laatstGewijzigd: now,
        ownerId: ownerId || undefined,
        ownerName: ownerName || undefined,
        invoer: enrichedInvoer,
        scenario1,
        scenario2
      };
      await saveDossier(dossier);
      setKlantContactGegevens(gegevens);
      if (takeOwnership) {
        setOriginalOwnerId(currentUserId);
        setOriginalOwnerName(currentUserName);
      }
      toast({ title: 'Berekening bijgewerkt' });
      snapshotRef.current = JSON.stringify({ invoer, scenarios });
      setIsDirty(false);
    }
  } finally {
    saveInProgressRef.current = false;
    setIsSaving(false);
  }
};
```

**Let op:** De hele functie-body (van `let klantNaam = ...` tot en met `setIsDirty(false)`) moet in het `try` blok. Het `finally` blok garandeert dat de lock altijd wordt vrijgegeven.

**Opslaan-button (regel ~697):**

Zoek:
```tsx
<Button variant="outline" size="sm" onClick={handleSaveClick}><Save className="h-4 w-4 mr-2" />Opslaan</Button>
```

Vervang door:
```tsx
<Button variant="outline" size="sm" onClick={handleSaveClick} disabled={isSaving}>
  <Save className="h-4 w-4 mr-2" />
  {isSaving ? 'Opslaan...' : 'Opslaan'}
</Button>
```

## Stap 2: URL bijwerken na save (al in stap 1)

De regel `navigate(\`?\${newParams.toString()}\`, { replace: true })` in stap 1 zorgt ervoor dat na eerste opslag de URL wordt bijgewerkt naar `/aankoop?id=UUID`. Dit voorkomt dat bij pagina-refresh het dossierId verloren gaat.

`searchParams` is al beschikbaar via `const [searchParams] = useSearchParams()` bovenaan de component.

## Stap 3: SaveChoiceDialog default naar Overschrijven

De huidige SaveChoiceDialog toont "Nieuwe berekening" en "Overschrijven" naast elkaar, zonder indicatie welke de veilige keuze is. Gebruikers klikken per ongeluk op "Nieuwe berekening" en krijgen een dubbel dossier.

**In `SaveChoiceDialog` in `src/components/SaveDossierDialog.tsx`:**

Verander de knoppen-volgorde en styling in het niet-ownership geval (regel ~452-461):

```tsx
{showOwnershipOption ? (
  <>
    <Button variant="outline" onClick={() => { onOverwrite(); onOpenChange(false); }}>
      Behoud bij {originalOwnerName}
    </Button>
    <Button onClick={() => { onOverwriteWithOwnership?.(); onOpenChange(false); }}>
      Overnemen op mijn naam
    </Button>
  </>
) : (
  <>
    <Button onClick={() => { onOverwrite(); onOpenChange(false); }}>
      Overschrijven
    </Button>
  </>
)}
```

**Verwijder de "Nieuwe berekening" knop uit de SaveChoiceDialog.** Gebruikers die echt een nieuwe berekening willen, gaan naar DossierDetail → "Nieuwe berekening" dropdown. Dat is de juiste plek daarvoor.

## Stap 4: Fix partner-sync in klantContactGegevens

Vervang de useEffect "Sync wizard name changes to klantContactGegevens" (regel ~98-118):

```typescript
useEffect(() => {
  if (!klantContactGegevens) return;
  const kg = invoer.klantGegevens;
  const isPartner = !kg.alleenstaand;

  setKlantContactGegevens(prev => {
    if (!prev) return prev;

    const updatedAanvrager = {
      ...prev.aanvrager,
      voornaam: kg.roepnaamAanvrager || '',
      tussenvoegsel: kg.tussenvoegselAanvrager || '',
      achternaam: kg.achternaamAanvrager || '',
    };

    let updatedPartner: typeof prev.partner;
    if (isPartner) {
      // Partner aanmaken als nog niet bestaat, anders alleen namen updaten
      updatedPartner = {
        ...(prev.partner || {
          postcode: prev.aanvrager.postcode || '',
          huisnummer: prev.aanvrager.huisnummer || '',
          straat: prev.aanvrager.straat || '',
          woonplaats: prev.aanvrager.woonplaats || '',
          telefoonnummer: prev.aanvrager.telefoonnummer || '',
          email: prev.aanvrager.email || '',
        }),
        voornaam: kg.roepnaamPartner || '',
        tussenvoegsel: kg.tussenvoegselPartner || '',
        achternaam: kg.achternaamPartner || '',
      };
    } else {
      updatedPartner = undefined;
    }

    return { ...prev, aanvrager: updatedAanvrager, partner: updatedPartner };
  });
}, [
  invoer.klantGegevens.roepnaamAanvrager,
  invoer.klantGegevens.tussenvoegselAanvrager,
  invoer.klantGegevens.achternaamAanvrager,
  invoer.klantGegevens.roepnaamPartner,
  invoer.klantGegevens.tussenvoegselPartner,
  invoer.klantGegevens.achternaamPartner,
  invoer.klantGegevens.alleenstaand,  // BELANGRIJK: reageer op alleenstaand toggle
]);
```

## Stap 5: SaveDossierDialog ook voor bestaande dossiers

Pas de `onSave` van `SaveDossierDialog` aan zodat het werkt voor zowel eerste opslag als bijwerken:

```tsx
<SaveDossierDialog
  open={showSaveDialog}
  onOpenChange={setShowSaveDialog}
  onSave={(gegevens) => {
    setKlantContactGegevens(gegevens);
    performSave(gegevens, false);  // altijd false → update als dossierId bestaat
  }}
  hasPartner={!invoer.klantGegevens.alleenstaand}
  existingGegevens={klantContactGegevens}
  prefillAanvrager={{
    roepnaam: invoer.klantGegevens.roepnaamAanvrager,
    tussenvoegsel: invoer.klantGegevens.tussenvoegselAanvrager,
    achternaam: invoer.klantGegevens.achternaamAanvrager,
  }}
  prefillPartner={!invoer.klantGegevens.alleenstaand ? {
    roepnaam: invoer.klantGegevens.roepnaamPartner,
    tussenvoegsel: invoer.klantGegevens.tussenvoegselPartner,
    achternaam: invoer.klantGegevens.achternaamPartner,
  } : undefined}
  onNamenChange={(aanvrager, partner) => {
    setInvoer(prev => ({
      ...prev,
      klantGegevens: {
        ...prev.klantGegevens,
        roepnaamAanvrager: aanvrager.roepnaam || '',
        tussenvoegselAanvrager: aanvrager.tussenvoegsel || '',
        achternaamAanvrager: aanvrager.achternaam || '',
        ...(partner ? {
          roepnaamPartner: partner.roepnaam || '',
          tussenvoegselPartner: partner.tussenvoegsel || '',
          achternaamPartner: partner.achternaam || '',
        } : {}),
      },
    }));
  }}
/>
```

Verwijder `handleFirstSave` — die is niet meer nodig.

Voeg een link toe in de Klant stap (Step 1) om contactgegevens te kunnen bewerken:

```tsx
{klantContactGegevens && (
  <Button
    variant="link"
    size="sm"
    className="text-xs text-muted-foreground p-0 h-auto"
    onClick={() => setShowSaveDialog(true)}
  >
    Contactgegevens bewerken
  </Button>
)}
```

## Stap 6: Doe hetzelfde in Aanpassen.tsx

`Aanpassen.tsx` heeft dezelfde save-logica als `Aankoop.tsx`. Pas dezelfde wijzigingen toe:
1. `saveInProgressRef` + `isSaving` guard
2. URL bijwerken na save: `navigate(\`?\${newParams.toString()}\`, { replace: true })`
3. Disabled button met "Opslaan..." tekst
4. Partner-sync useEffect met `alleenstaand` in dependencies
5. klantNaam inclusief partner

---

## Verificatie

| # | Check | Verwacht |
|---|-------|----------|
| 1 | Snel dubbelklikken op Opslaan | 1 dossier, button "Opslaan..." + disabled |
| 2 | Na opslaan: check URL | URL bevat `?id=UUID` |
| 3 | Pagina refreshen na opslaan | Dossier wordt correct geladen (URL heeft `?id=`) |
| 4 | Bestaand dossier → Opslaan | Geen "Nieuwe berekening" knop meer, direct overschrijven |
| 5 | Alleenstaand → partner + opslaan | Partner in klant_naam en klantContactGegevens |
| 6 | Partner → alleenstaand + opslaan | Partner verwijderd uit klantContactGegevens |
| 7 | "Contactgegevens bewerken" link | Dialog opent met bestaande gegevens |
| 8 | Geen TypeScript fouten | `npm run build` slaagt |

## Samenvatting bestanden

| Bestand | Wijziging |
|---------|-----------|
| `src/pages/Aankoop.tsx` | saveInProgressRef, isSaving, guard in performSave, URL update na save, verwijder handleFirstSave, fix partner-sync useEffect, klantNaam met partner, "Contactgegevens bewerken" link |
| `src/pages/Aanpassen.tsx` | Zelfde wijzigingen als Aankoop.tsx |
| `src/components/SaveDossierDialog.tsx` | Verwijder "Nieuwe berekening" knop uit SaveChoiceDialog |
