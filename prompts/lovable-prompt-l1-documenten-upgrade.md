# L1 — Documentensectie upgrade: _inbox upload, sortering, communicatie-tab

## Context

Op de DossierDetail pagina staat een "Documenten" sectie die bestanden toont uit de SharePoint klantmap. Deze sectie moet op vier punten verbeterd worden.

De backend API endpoints (allemaal al werkend):

| Endpoint | Functie |
|----------|---------|
| `GET /sharepoint/klantmap/{dossier_id}` | Lijst bestanden in klantmap |
| `POST /sharepoint/klantmap/{dossier_id}/upload` | Upload naar **_inbox** (backend gewijzigd) |
| `DELETE /sharepoint/klantmap/item/{item_id}` | Verwijder bestand |
| `POST /doc-processing/{dossier_id}/process-all` | Verwerk alle documenten in _inbox |

De API URL staat in `src/config/apiConfig.ts` als `API_CONFIG.NAT_API_URL`.

Alle API calls vereisen een Authorization header met Supabase session token:
```typescript
const { data: { session } } = await supabase.auth.getSession();
const headers = {
  'Authorization': `Bearer ${session?.access_token ?? ''}`,
};
```

---

## Wijziging 1 — Upload gaat naar _inbox + automatische verwerking

### Huidige situatie
Bestanden die via drag-and-drop of de upload-knop worden geüpload, komen in de gewone klantmap terecht.

### Gewenste situatie
Bestanden worden geüpload naar de **_inbox** (de backend doet dit al automatisch — het upload endpoint is gewijzigd). Na een succesvolle upload moet de frontend automatisch de document processing pipeline starten.

**Implementatie:**

Na elke succesvolle upload (per bestand of na alle bestanden in een batch):

```typescript
// 1. Upload bestand (bestaande call, endpoint uploadt nu automatisch naar _inbox)
const uploadResponse = await fetch(
  `${API_CONFIG.NAT_API_URL}/sharepoint/klantmap/${dossierId}/upload`,
  { method: 'POST', headers: { 'Authorization': `Bearer ${token}` }, body: formData }
);

// 2. Start document processing (na alle uploads in de batch)
if (uploadResponse.ok) {
  try {
    await fetch(
      `${API_CONFIG.NAT_API_URL}/doc-processing/${dossierId}/process-all`,
      { method: 'POST', headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' } }
    );
  } catch (e) {
    console.warn('Document processing starten mislukt:', e);
    // Niet fataal — documenten staan in _inbox en kunnen later verwerkt worden
  }
}
```

**Toon een toast na upload:**
- Succes: "Documenten geüpload en worden verwerkt" (met een subtiele spinner of processing-indicator)
- Fout: "Upload mislukt: [foutmelding]"

**Ververs de documentenlijst** na een korte delay (3-5 seconden), omdat de processing pipeline even nodig heeft om bestanden van _inbox naar de hoofdmap te verplaatsen.

---

## Wijziging 2 — Sorteren op naam of datum

### Huidige situatie
Documenten worden gesorteerd op datum (nieuwste eerst). Er is geen mogelijkheid om de sortering te wijzigen.

### Gewenste situatie
Twee sorteeropties beschikbaar via een klein dropdown/toggle naast de "Documenten (X)" titel:

| Optie | Sortering | Icoon |
|-------|-----------|-------|
| **Datum** (standaard) | `lastModified` aflopend (nieuwste eerst) | `ArrowDownAZ` of `Calendar` |
| **Naam** | `name` alfabetisch oplopend (A→Z) | `ArrowDownAZ` of `SortAsc` |

Gebruik een simpele toggle-knop of een klein DropdownMenu (Lucide iconen). Onthoud de keuze NIET — datum is altijd de standaard bij paginalading.

---

## Wijziging 3 — Tabs: Documenten en Communicatie

### Huidige situatie
De sectie toont alleen documenten.

### Gewenste situatie
Boven de bestandenlijst komen twee tabs:

```
[ Documenten ]  [ Communicatie ]
```

**Tab "Documenten"** — bestaande functionaliteit (bestandenlijst + upload).

**Tab "Communicatie"** — placeholder voor nu:
- Toon een lege state: "Nog geen communicatie beschikbaar"
- Subtekst: "Hier verschijnen e-mails en notities uit het klantdossier"
- Gebruik een `MessageSquare` of `Mail` icoon

De communicatie-tab hoeft nog niets op te halen — dit wordt later gekoppeld aan de `_communicatie` map op SharePoint.

**Styling:**
- Gebruik bestaande Tabs/TabsList/TabsTrigger componenten (shadcn/ui)
- Documenten is de standaard actieve tab
- Upload-zone (drag-and-drop) alleen zichtbaar op de Documenten tab

---

## Wijziging 4 — Map-icoon opent Windows Verkenner (indien mogelijk)

### Huidige situatie
Het map-icoontje opent de SharePoint URL in de webbrowser (`window.open(sharepointUrl, '_blank')`).

### Gewenste situatie
Probeer de map te openen in de Windows Verkenner via het `odopen://` protocol. Dit werkt als de gebruiker OneDrive/SharePoint sync heeft ingesteld op hun computer. Als fallback: open in de browser.

**Implementatie:**

```typescript
function openKlantmap(sharepointUrl: string) {
  // Probeer via odopen:// protocol (opent Windows Verkenner als OneDrive sync actief is)
  // Format: odopen://sync/?siteId=...&webId=...&listId=...&userEmail=...
  // Maar dit vereist siteId/webId/listId die we niet direct hebben.
  
  // Eenvoudiger alternatief: open de SharePoint URL met ms-sharepoint: protocol
  // of gewoon de webURL — de gebruiker kan zelf kiezen om te syncen.
  
  // Voorlopig: open in browser (bestaand gedrag behouden)
  window.open(sharepointUrl, '_blank');
}
```

> **Opmerking:** Het direct openen van een SharePoint map in Windows Verkenner vereist dat de gebruiker OneDrive sync heeft ingesteld voor die SharePoint-site. Er is geen betrouwbaar cross-platform protocol om dit te forceren vanuit een webapp. **Behoud het huidige gedrag** (openen in browser) maar voeg een tooltip toe aan het icoon: "Open in SharePoint". In een toekomstige versie kunnen we dit uitbreiden met het `odopen://` protocol als de sync is ingesteld.

---

## Samenvatting wijzigingen

| # | Wat | Bestand(en) |
|---|-----|-------------|
| 1 | Upload → _inbox + auto process-all | DocumentenTab of DossierDetail |
| 2 | Sorteer toggle (datum/naam) | DocumentenTab |
| 3 | Tabs: Documenten / Communicatie | DocumentenTab of DossierDetail |
| 4 | Map-icoon tooltip "Open in SharePoint" | DocumentenTab |

## Verificatie

- [ ] Upload via drag-and-drop → bestand komt in _inbox → process-all wordt aangeroepen
- [ ] Upload via klik → idem
- [ ] Na upload: toast "Documenten geüpload en worden verwerkt"
- [ ] Na 3-5 sec: documentenlijst ververst automatisch
- [ ] Sorteren op naam: documenten staan A→Z
- [ ] Sorteren op datum (standaard): nieuwste eerst
- [ ] Tab "Communicatie" toont lege placeholder
- [ ] Tab "Documenten" toont bestandenlijst + upload-zone
- [ ] Map-icoon heeft tooltip "Open in SharePoint"
