# Lovable Prompt F1: Verstuur samenvatting als concept e-mail in Outlook

## Doel

De "Verstuur samenvatting" knop moet een concept e-mail aanmaken in het Outlook-postvak van de ingelogde adviseur, met de samenvatting PDF als bijlage. De adviseur opent vervolgens Outlook, controleert de mail en verstuurt zelf.

---

## Huidige situatie

De knop "Verstuur samenvatting" (of "Stuur samenvatting") triggert nu `downloadSamenvattingPdf()` in `src/utils/pdfDownload.ts`. Deze functie:
1. Bouwt een payload op met alle PDF-data
2. POST naar `${API_BASE_URL}/samenvatting-pdf`
3. Ontvangt een PDF blob en start een browser-download

## Gewenste situatie

De knop roept een **nieuw API endpoint** aan dat:
1. De PDF genereert (server-side)
2. Een concept e-mail aanmaakt in het Outlook-postvak van de adviseur
3. De PDF als bijlage toevoegt
4. Ontvangers: aanvrager + partner (e-mailadressen uit klantgegevens)

---

## Stappen

### 1. Nieuwe functie `sendSamenvattingDraft()`

Maak een nieuwe async functie in `src/utils/pdfDownload.ts` (of een nieuw bestand `src/utils/emailDraft.ts`):

```typescript
export async function sendSamenvattingDraft(): Promise<{
  status: string;
  message: string;
  web_link: string;
  recipients: string[];
}> {
  // 1. Haal het e-mailadres van de ingelogde gebruiker op
  const { data: { user } } = await supabase.auth.getUser();
  const senderEmail = user?.email;

  if (!senderEmail) {
    throw new Error('Geen ingelogde gebruiker gevonden');
  }

  // 2. Bouw dezelfde PDF payload als downloadSamenvattingPdf()
  const pdfPayload = buildPdfPayload(); // Hergebruik bestaande logica

  // 3. POST naar het nieuwe endpoint
  const response = await fetch(`${API_BASE_URL}/email/draft-samenvatting`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getApiHeaders(), // X-API-Key header
    },
    body: JSON.stringify({
      sender_email: senderEmail,
      pdf_data: pdfPayload,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'E-mail draft aanmaken mislukt');
  }

  return response.json();
}
```

### 2. Pas de "Verstuur samenvatting" knop aan

Zoek de component met de "Verstuur samenvatting" (of "Stuur samenvatting") knop. Wijzig de `onClick` handler:

```typescript
const handleSendDraft = async () => {
  try {
    setLoading(true);
    const result = await sendSamenvattingDraft();

    // Succes: toon toast met optie om Outlook te openen
    toast({
      title: 'Concept e-mail aangemaakt',
      description: `E-mail klaargezet voor: ${result.recipients.join(', ')}`,
      action: result.web_link ? (
        <a href={result.web_link} target="_blank" rel="noopener noreferrer">
          Open in Outlook
        </a>
      ) : undefined,
    });
  } catch (error) {
    toast({
      title: 'Fout bij aanmaken e-mail',
      description: error.message,
      variant: 'destructive',
    });
  } finally {
    setLoading(false);
  }
};
```

### 3. Request formaat

Het nieuwe endpoint verwacht deze JSON-structuur:

```json
{
  "sender_email": "adviseur@hondsrugfinance.nl",
  "pdf_data": {
    // Exact dezelfde structuur als het huidige /samenvatting-pdf request:
    "klant_naam": "Harry Slinger",
    "datum": "08-03-2026",
    "klant_gegevens": {
      "aanvrager": {
        "naam": "Harry Slinger",
        "email": "harry@example.nl",
        ...
      },
      "partner": { ... }
    },
    "haalbaarheid": [ ... ],
    "financiering": [ ... ],
    "maandlasten": [ ... ],
    ...
  }
}
```

**Belangrijk:** de `pdf_data` is identiek aan wat nu naar `/samenvatting-pdf` wordt gestuurd. De enige toevoeging is `sender_email` op het hoogste niveau.

### 4. Behoud de PDF download knop

Houd de bestaande "Download PDF" functionaliteit beschikbaar als secundaire optie (bijv. een dropdown of tweede knop), zodat de adviseur ook handmatig kan downloaden.

---

## Response van het endpoint

```json
{
  "status": "ok",
  "message": "Concept e-mail aangemaakt in Outlook",
  "message_id": "AAMk...",
  "web_link": "https://outlook.office365.com/...",
  "recipients": ["harry@example.nl", "harriette@example.nl"],
  "attachment_size_bytes": 103622
}
```

## Foutafhandeling

| HTTP Status | Betekenis | Actie in UI |
|-------------|-----------|-------------|
| 200 | Succes | Succes-toast tonen |
| 422 | Geen ontvanger e-mail | "Vul eerst het e-mailadres van de aanvrager in" |
| 502 | Outlook/Graph API fout | "Fout bij aanmaken e-mail in Outlook" |
| 503 | E-mail niet geconfigureerd | "E-mail functie is niet beschikbaar" |

## Verificatie

1. Klik op "Verstuur samenvatting" → succes-toast verschijnt
2. Open Outlook → concept e-mail staat in de Concepten-map
3. Controleer: ontvangers kloppen, PDF zit als bijlage, onderwerp bevat klantnaam
4. Test zonder e-mailadres bij aanvrager → foutmelding
