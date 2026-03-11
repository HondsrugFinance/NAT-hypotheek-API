# Lovable Prompt H1: Backend-driven adviesrapport (vervangt G1-G7)

> Deze prompt vervangt de volledige G1-G7 rapportgeneratie-keten. De backend doet nu alle berekeningen en sectie-opbouw. Lovable hoeft alleen dialog-opties te verzamelen en één API-call te doen.

---

## Achtergrond

De huidige adviesrapport-generatie werkt via een complex TypeScript pad:
1. Data uit Supabase lezen
2. Veldnamen mappen (rentepercentage → werkelijke_rente, aflossingsvorm → aflos_type)
3. 3+ API calls maken (risk-scenarios, calculate ×2, monthly-costs)
4. 13 secties opbouwen met buildSection*() functies
5. Alles naar `POST /adviesrapport-pdf` sturen

Dit veroorzaakte herhaaldelijk bugs (G6/G7 fixes). **De backend doet dit nu allemaal.**

### Nieuw: `POST /adviesrapport-pdf-v2`

De backend leest zelf Supabase, doet alle berekeningen, bouwt alle secties, en retourneert de PDF. Lovable stuurt alleen:

```json
{
  "dossier_id": "uuid-van-het-dossier",
  "aanvraag_id": "uuid-van-de-aanvraag",
  "options": {
    "advisor_name": "Alex Kuijper CFP®",
    "report_date": "10-03-2026",
    "dossier_nummer": "HF-2026-001",
    "doel_hypotheek": "Aankoop bestaande woning",
    "ervaring_hypotheek": "Nee",
    "kennis_hypotheekvormen": "Redelijk",
    "kennis_fiscale_regels": "Matig",
    "risicobereidheid": {
      "pensioen": "Risico een beetje beperken",
      "overlijden": "Risico zoveel mogelijk beperken",
      "arbeidsongeschiktheid": "Risico een beetje beperken",
      "werkloosheid": "Risico aanvaarden",
      "relatiebeeindiging": "Risico aanvaarden",
      "waardedaling_woning": "Risico een beetje beperken",
      "rentestijging": "Risico aanvaarden",
      "aflopen_hypotheekrenteaftrek": "Risico aanvaarden"
    },
    "hypotheekverstrekker": "ING",
    "nhg": true,
    "prioriteit": "stabiele maandlast",
    "ao_percentage": 50,
    "benutting_rvc_percentage": 50,
    "loondoorbetaling_pct_jaar1_aanvrager": 1.0,
    "loondoorbetaling_pct_jaar2_aanvrager": 0.70,
    "loondoorbetaling_pct_jaar1_partner": 1.0,
    "loondoorbetaling_pct_jaar2_partner": 0.70,
    "arbeidsverleden_jaren_totaal_aanvrager": 15,
    "arbeidsverleden_pre2016_boven10_aanvrager": 5,
    "arbeidsverleden_vanaf2016_boven10_aanvrager": 0,
    "arbeidsverleden_jaren_totaal_partner": 10,
    "arbeidsverleden_pre2016_boven10_partner": 0,
    "arbeidsverleden_vanaf2016_boven10_partner": 0,
    "nabestaandenpensioen_bij_overlijden_aanvrager": 12000,
    "nabestaandenpensioen_bij_overlijden_partner": 8000,
    "heeft_kind_onder_18": false,
    "aov_dekking_bruto_jaar_aanvrager": 0,
    "aov_dekking_bruto_jaar_partner": 0,
    "woonlastenverzekering_ao_bruto_jaar": 0,
    "woonlastenverzekering_ww_bruto_jaar": 0
  }
}
```

**Geen NAT API-key nodig.** Geen `getApiHeaders()`. Wel moet de **Supabase session token** meegestuurd worden in de `Authorization` header, zodat de backend namens de ingelogde gebruiker data kan lezen uit Supabase (RLS).

**Response:** PDF bytes (`application/pdf`). Direct downloadbaar als blob.

---

## Stap 1: Wizard behouden — Stap 1 (aanvraag selectie)

De bestaande twee-stappen wizard blijft **exact hetzelfde**:

**Stap 1: Selecteer aanvraag**

```
┌─────────────────────────────────────────────┐
│  Selecteer aanvraag als basis               │
│                                             │
│  ┌─ ○ ─────────────────────────────────┐    │
│  │  🏠 Aankoop: Bestaande bouw         │    │
│  │  Laatst bewerkt: 17-2-2026 10:11    │    │
│  └─────────────────────────────────────┘    │
│                                             │
│  ┌─ ○ ─────────────────────────────────┐    │
│  │  🏠 Aanpassen: Oversluiten          │    │
│  │  Laatst bewerkt: 8-3-2026 13:05     │    │
│  └─────────────────────────────────────┘    │
│                                             │
│              [Volgende →]                   │
└─────────────────────────────────────────────┘
```

- Radio buttons, één selecteerbaar
- "Volgende" pas actief na selectie
- 1 aanvraag → automatisch geselecteerd
- Geen aanvragen → melding tonen

**Dit verandert niet.** Gebruik de bestaande code.

---

## Stap 2: Dialog configuratie — VEREENVOUDIGD

De huidige configuratie (stap 2) had twee kolommen: sectie-checkboxes links, opties rechts.

**Verwijder de sectie-checkboxes volledig.** De backend bepaalt welke secties in het rapport komen (op basis van de data — bijv. relatiebeëindiging alleen bij stel).

De nieuwe layout heeft twee kolommen:

```
┌──────────────────────────────────────────────────────────────┐
│  ← Terug          Adviesrapport samenstellen                 │
│                                                              │
│  Aanvraag: Aankoop: Bestaande bouw                           │
│                                                              │
│  ┌─ RAPPORT ─────────────────┐  ┌─ KLANTPROFIEL ──────────┐  │
│  │                           │  │                          │  │
│  │  Adviseur:                │  │  Doel hypotheek:         │  │
│  │  [▾ Alex Kuijper CFP®  ]  │  │  [▾ Aankoop best. won.] │  │
│  │                           │  │                          │  │
│  │  Datum:                   │  │  Ervaring hypotheek:     │  │
│  │  [📅 10-03-2026       ]   │  │  [▾ Nee              ]  │  │
│  │                           │  │                          │  │
│  │  Dossiernummer:           │  │  Kennis hypotheekvormen: │  │
│  │  [HF-2026-001         ]   │  │  [▾ Redelijk          ] │  │
│  │                           │  │                          │  │
│  │  Geldverstrekker:         │  │  Kennis fiscale regels:  │  │
│  │  [▾ ING              ]    │  │  [▾ Matig             ] │  │
│  │                           │  │                          │  │
│  │  ☑ NHG                    │  │  Prioriteit:             │  │
│  │                           │  │  [▾ Stabiele maandlast ] │  │
│  │                           │  │                          │  │
│  └───────────────────────────┘  └──────────────────────────┘  │
│                                                              │
│  ┌─ RISICOBEREIDHEID ────────────────────────────────────┐    │
│  │  (6 dropdowns in 2 kolommen)                          │    │
│  │                                                       │    │
│  │  Pensioen:           Overlijden:                      │    │
│  │  [▾ Een beetje bep.] [▾ Zoveel mog. bep.]             │    │
│  │                                                       │    │
│  │  Arbeidsongeschikth: Werkloosheid:                    │    │
│  │  [▾ Een beetje bep.] [▾ Aanvaarden     ]              │    │
│  │                                                       │    │
│  │  Waardedaling:       Rentestijging:                   │    │
│  │  [▾ Een beetje bep.] [▾ Aanvaarden     ]              │    │
│  │                                                       │    │
│  │  Hypotheekrenteaftr: Relatiebeëindiging:              │    │
│  │  [▾ Aanvaarden     ] [▾ Aanvaarden     ]              │    │
│  └───────────────────────────────────────────────────────┘    │
│                                                              │
│  ▸ Geavanceerde risico-analyse instellingen                  │
│  ┌───────────────────────────────────────────────────────┐    │
│  │  (inklapbaar accordion — standaard ingeklapt)         │    │
│  │                                                       │    │
│  │  AO-percentage:        [▾ 50%             ]           │    │
│  │  Benutting RVC:        [▾ 50%             ]           │    │
│  │  Loondoorbet. jr1 aanvr: [1.0]  jr2: [0.70]          │    │
│  │  Loondoorbet. jr1 partn: [1.0]  jr2: [0.70]          │    │
│  │  Arbeidsverleden aanvr:  [15] jaar totaal             │    │
│  │  Arbeidsverleden partn:  [10] jaar totaal             │    │
│  │  Nabestaandenp. aanvr:   [€ 12.000] bruto/jaar       │    │
│  │  Nabestaandenp. partner: [€ 8.000] bruto/jaar        │    │
│  │  Kind onder 18:          [☐]                          │    │
│  │  AOV dekking aanvrager:  [€ 0] bruto/jaar             │    │
│  │  AOV dekking partner:    [€ 0] bruto/jaar             │    │
│  │  Woonlastenverz. AO:    [€ 0] bruto/jaar             │    │
│  │  Woonlastenverz. WW:    [€ 0] bruto/jaar             │    │
│  └───────────────────────────────────────────────────────┘    │
│                                                              │
│        [Annuleren]              [Genereer rapport →]         │
└──────────────────────────────────────────────────────────────┘
```

### Veld-specificaties

**Linkerkolom — Rapport:**

| Veld | Type | Default | Toelichting |
|------|------|---------|-------------|
| Adviseur | Dropdown | Naam ingelogde user | Toon users met role='adviseur' of 'admin' uit `profiles` tabel |
| Datum | Datumpicker | Vandaag | Format: DD-MM-YYYY |
| Dossiernummer | Tekstveld | Dossiernummer uit dossier | Bewerkbaar |
| Geldverstrekker | Tekst of dropdown | Uit aanvraag (`hypotheekverstrekker`) | Vrij invulbaar |
| NHG | Checkbox | Uit aanvraag (`nhg`) | |

**Rechterkolom — Klantprofiel:**

| Veld | Type | Default | API key |
|------|------|---------|---------|
| Doel hypotheek | Dropdown | "Aankoop bestaande woning" | `doel_hypotheek` |
| Ervaring hypotheek | Dropdown | "Nee" | `ervaring_hypotheek` |
| Kennis hypotheekvormen | Dropdown | "Redelijk" | `kennis_hypotheekvormen` |
| Kennis fiscale regels | Dropdown | "Matig" | `kennis_fiscale_regels` |
| Prioriteit | Dropdown | "stabiele maandlast" | `prioriteit` |

**Dropdown opties:**

| Veld | Opties |
|------|--------|
| Doel hypotheek | "Aankoop bestaande woning", "Aankoop nieuwbouw", "Oversluiting", "Verhoging", "Rentemiddeling" |
| Ervaring hypotheek | "Ja", "Nee" |
| Kennis hypotheekvormen | "Geen", "Beperkt", "Redelijk", "Goed" |
| Kennis fiscale regels | "Geen", "Beperkt", "Matig", "Goed" |
| Prioriteit | "stabiele maandlast", "zo laag mogelijke maandlast", "zo snel mogelijk aflossen", "maximale flexibiliteit" |

**Risicobereidheid (8 dropdowns):**

Elke dropdown heeft dezelfde 4 opties:
- "Risico aanvaarden"
- "Risico een beetje beperken"
- "Risico zoveel mogelijk beperken"
- "Risico niet bereid te aanvaarden"

De 8 risicovelden:

| Label | API key (in `risicobereidheid` dict) | Default |
|-------|--------------------------------------|---------|
| Pensioen | `pensioen` | "Risico een beetje beperken" |
| Overlijden | `overlijden` | "Risico zoveel mogelijk beperken" |
| Arbeidsongeschiktheid | `arbeidsongeschiktheid` | "Risico een beetje beperken" |
| Werkloosheid | `werkloosheid` | "Risico aanvaarden" |
| Relatiebeëindiging | `relatiebeeindiging` | "Risico aanvaarden" |
| Waardedaling woning | `waardedaling_woning` | "Risico een beetje beperken" |
| Rentestijging | `rentestijging` | "Risico aanvaarden" |
| Aflopen hypotheekrenteaftrek | `aflopen_hypotheekrenteaftrek` | "Risico aanvaarden" |

**Geavanceerde instellingen (inklapbaar):**

| Veld | Type | Default | API key | Toelichting |
|------|------|---------|---------|-------------|
| AO-percentage | Slider of number (35-100) | 50 | `ao_percentage` | Percentage arbeidsongeschiktheid |
| Benutting RVC | Slider of number (0-100) | 50 | `benutting_rvc_percentage` | |
| Loondoorbetaling jr1 aanvrager | Number (0-2.0) | 1.0 | `loondoorbetaling_pct_jaar1_aanvrager` | Factor (1.0 = 100%) |
| Loondoorbetaling jr2 aanvrager | Number (0-2.0) | 0.70 | `loondoorbetaling_pct_jaar2_aanvrager` | |
| Loondoorbetaling jr1 partner | Number (0-2.0) | 1.0 | `loondoorbetaling_pct_jaar1_partner` | Toon alleen bij stel |
| Loondoorbetaling jr2 partner | Number (0-2.0) | 0.70 | `loondoorbetaling_pct_jaar2_partner` | Toon alleen bij stel |
| Arbeidsverleden totaal aanvr. | Number (0-50) | 15 | `arbeidsverleden_jaren_totaal_aanvrager` | Schatting: leeftijd - 18 |
| Arbeidsverleden pre-2016 boven 10 aanvr. | Number (0-40) | 0 | `arbeidsverleden_pre2016_boven10_aanvrager` | |
| Arbeidsverleden vanaf 2016 boven 10 aanvr. | Number (0-20) | 0 | `arbeidsverleden_vanaf2016_boven10_aanvrager` | |
| Arbeidsverleden totaal partner | Number (0-50) | 10 | `arbeidsverleden_jaren_totaal_partner` | Toon alleen bij stel |
| Arbeidsverleden pre-2016 boven 10 partner | Number (0-40) | 0 | `arbeidsverleden_pre2016_boven10_partner` | Toon alleen bij stel |
| Arbeidsverleden vanaf 2016 boven 10 partner | Number (0-20) | 0 | `arbeidsverleden_vanaf2016_boven10_partner` | Toon alleen bij stel |
| Nabestaandenpensioen aanvrager | Number (€, ≥0) | 0 | `nabestaandenpensioen_bij_overlijden_aanvrager` | Bruto jaarbedrag |
| Nabestaandenpensioen partner | Number (€, ≥0) | 0 | `nabestaandenpensioen_bij_overlijden_partner` | Toon alleen bij stel |
| Kind onder 18 | Checkbox | uit | `heeft_kind_onder_18` | |
| Geboortedatum jongste kind | Datumpicker | — | `geboortedatum_jongste_kind` | Toon alleen als kind ☑ |
| AOV dekking aanvrager | Number (€, ≥0) | 0 | `aov_dekking_bruto_jaar_aanvrager` | Bruto jaarbedrag |
| AOV dekking partner | Number (€, ≥0) | 0 | `aov_dekking_bruto_jaar_partner` | Toon alleen bij stel |
| Woonlastenverzekering AO | Number (€, ≥0) | 0 | `woonlastenverzekering_ao_bruto_jaar` | |
| Woonlastenverzekering WW | Number (€, ≥0) | 0 | `woonlastenverzekering_ww_bruto_jaar` | |

**Stel vs alleenstaand bepalen:** Check of de invoer van het dossier een partner heeft. Als `klantGegevens.alleenstaand === true` of geen partner-naam/geboortedatum aanwezig is, verberg dan alle partner-specifieke velden (loondoorbetaling partner, arbeidsverleden partner, nabestaandenpensioen partner, AOV partner, relatiebeëindiging risicobereidheid).

---

## Stap 3: Rapportgeneratie — één fetch call

**Verwijder alle bestaande rapportgeneratie-code** en vervang het met deze ene functie:

```typescript
const API_BASE_URL = "https://nat-hypotheek-api.onrender.com";

interface AdviesrapportV2Options {
  // Rapport meta
  advisor_name: string;
  report_date: string;      // DD-MM-YYYY
  dossier_nummer: string;

  // Klantprofiel
  doel_hypotheek: string;
  ervaring_hypotheek: string;
  kennis_hypotheekvormen: string;
  kennis_fiscale_regels: string;
  prioriteit: string;

  // Risicobereidheid
  risicobereidheid: Record<string, string>;

  // Hypotheekverstrekker
  hypotheekverstrekker: string;
  nhg: boolean;

  // AO params
  ao_percentage: number;
  benutting_rvc_percentage: number;

  // Loondoorbetaling
  loondoorbetaling_pct_jaar1_aanvrager: number;
  loondoorbetaling_pct_jaar2_aanvrager: number;
  loondoorbetaling_pct_jaar1_partner: number;
  loondoorbetaling_pct_jaar2_partner: number;

  // Arbeidsverleden
  arbeidsverleden_jaren_totaal_aanvrager: number;
  arbeidsverleden_pre2016_boven10_aanvrager: number;
  arbeidsverleden_vanaf2016_boven10_aanvrager: number;
  arbeidsverleden_jaren_totaal_partner: number;
  arbeidsverleden_pre2016_boven10_partner: number;
  arbeidsverleden_vanaf2016_boven10_partner: number;

  // Nabestaanden
  nabestaandenpensioen_bij_overlijden_aanvrager: number;
  nabestaandenpensioen_bij_overlijden_partner: number;
  heeft_kind_onder_18: boolean;
  geboortedatum_jongste_kind?: string;

  // Verzekeringen
  aov_dekking_bruto_jaar_aanvrager: number;
  aov_dekking_bruto_jaar_partner: number;
  woonlastenverzekering_ao_bruto_jaar: number;
  woonlastenverzekering_ww_bruto_jaar: number;
}

async function generateAdviesrapportV2(
  dossierId: string,
  aanvraagId: string,
  options: AdviesrapportV2Options,
  customerName: string,
): Promise<void> {
  // Haal de Supabase session token op — nodig zodat de backend
  // namens de ingelogde gebruiker data uit Supabase kan lezen (RLS)
  const { data: { session } } = await supabase.auth.getSession();
  if (!session?.access_token) {
    throw new Error("Niet ingelogd — log opnieuw in en probeer het nog eens");
  }

  const response = await fetch(`${API_BASE_URL}/adviesrapport-pdf-v2`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${session.access_token}`,
    },
    body: JSON.stringify({
      dossier_id: dossierId,
      aanvraag_id: aanvraagId,
      options,
    }),
  });

  if (!response.ok) {
    let errorMessage = `Rapport generatie mislukt (${response.status})`;
    try {
      const errorData = await response.json();
      errorMessage = errorData.detail || errorMessage;
    } catch {
      // Response was niet JSON
    }
    throw new Error(errorMessage);
  }

  // Download PDF
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `Adviesrapport - ${customerName}.pdf`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
```

### Gebruik in het dialog component

Wanneer de gebruiker op "Genereer rapport" klikt:

```typescript
const handleGenerateReport = async () => {
  setIsGenerating(true);

  try {
    // Verzamel alle dialog-waarden in het options object
    const options: AdviesrapportV2Options = {
      advisor_name: selectedAdvisor,
      report_date: selectedDate,  // DD-MM-YYYY
      dossier_nummer: dossierNummer,
      doel_hypotheek: doelHypotheek,
      ervaring_hypotheek: ervaringHypotheek,
      kennis_hypotheekvormen: kennisHypotheekvormen,
      kennis_fiscale_regels: kennisFiscaleRegels,
      prioriteit: prioriteit,
      risicobereidheid: {
        pensioen: risicoPensioen,
        overlijden: risicoOverlijden,
        arbeidsongeschiktheid: risicoAO,
        werkloosheid: risicoWW,
        relatiebeeindiging: risicoRelatiebeeindiging,
        waardedaling_woning: risicoWaardedaling,
        rentestijging: risicoRentestijging,
        aflopen_hypotheekrenteaftrek: risicoAflopenRenteaftrek,
      },
      hypotheekverstrekker: geldverstrekker,
      nhg: nhg,
      ao_percentage: aoPercentage,
      benutting_rvc_percentage: benuttingRvc,
      loondoorbetaling_pct_jaar1_aanvrager: loondoorbetalingJr1Aanvrager,
      loondoorbetaling_pct_jaar2_aanvrager: loondoorbetalingJr2Aanvrager,
      loondoorbetaling_pct_jaar1_partner: loondoorbetalingJr1Partner,
      loondoorbetaling_pct_jaar2_partner: loondoorbetalingJr2Partner,
      arbeidsverleden_jaren_totaal_aanvrager: arbeidsverledenAanvrager,
      arbeidsverleden_pre2016_boven10_aanvrager: arbeidsverledenPre2016Aanvrager,
      arbeidsverleden_vanaf2016_boven10_aanvrager: arbeidsverledenVanaf2016Aanvrager,
      arbeidsverleden_jaren_totaal_partner: arbeidsverledenPartner,
      arbeidsverleden_pre2016_boven10_partner: arbeidsverledenPre2016Partner,
      arbeidsverleden_vanaf2016_boven10_partner: arbeidsverledenVanaf2016Partner,
      nabestaandenpensioen_bij_overlijden_aanvrager: nabestaandenAanvrager,
      nabestaandenpensioen_bij_overlijden_partner: nabestaandenPartner,
      heeft_kind_onder_18: heeftKindOnder18,
      geboortedatum_jongste_kind: geboortedatumJongsteKind || undefined,
      aov_dekking_bruto_jaar_aanvrager: aovAanvrager,
      aov_dekking_bruto_jaar_partner: aovPartner,
      woonlastenverzekering_ao_bruto_jaar: woonlastenverz_ao,
      woonlastenverzekering_ww_bruto_jaar: woonlastenverz_ww,
    };

    await generateAdviesrapportV2(
      dossierId,
      selectedAanvraagId,
      options,
      customerName,
    );

    toast.success("Adviesrapport gedownload");
    onClose();
  } catch (error: any) {
    console.error("Adviesrapport generatie mislukt:", error);
    toast.error(error.message || "Er ging iets mis bij het genereren van het rapport");
  } finally {
    setIsGenerating(false);
  }
};
```

---

## Stap 4: Verwijder oude rapportgeneratie-code

**Verwijder de volgende functies/bestanden die niet meer nodig zijn:**

### Functies om te verwijderen

Zoek in de codebase naar de volgende functies en verwijder ze. Ze worden niet meer aangeroepen:

1. **`buildAdviesrapportPayload()`** — bouwde de `sections[]` array op
2. **`extractDossierData()`** / **`extractLeningdelen()`** — las data uit invoer JSONB
3. **`mapAflosvorm()`** — mappte "annuiteit" → "Annuïteit"
4. **`mapLeningdeelVoorApi()`** — converteerde rente + veldnamen
5. **`displayAflosvorm()`** — kapitalisatie voor weergave
6. **Alle `buildSection*()` functies** — buildSummarySection, buildClientProfileSection, buildFinancingSection, etc.
7. **`downloadAdviesrapportPdf()`** (de oude versie die naar `/adviesrapport-pdf` postte)

### API-calls om te verwijderen (in rapport-context)

De volgende API-calls werden alleen gedaan voor het adviesrapport. Als ze nergens anders worden gebruikt, verwijder ze:

1. **`POST /calculate/risk-scenarios`** — risicoberekeningen (backend doet dit nu)
2. **`POST /calculate`** (×2 voor relatiebeëindiging) — max hypotheek per partner alleen (backend doet dit nu)
3. **`POST /calculate/monthly-costs`** (in rapport-context) — maandlasten (backend doet dit nu)

**Let op:** Deze endpoints worden mogelijk ook buiten de rapport-context gebruikt (bijv. in de wizard-stappen). Verwijder alleen de aanroepen die specifiek voor het adviesrapport zijn. Als je twijfelt, laat ze staan.

### Type definities om te verwijderen

Als deze types alleen voor het adviesrapport werden gebruikt:

1. **`AdviesrapportPayload`** — het volledige payload type
2. **`PdfSection`** / **`Section`** — sectie structuur
3. **`AdviesrapportOptions`** (de oude versie met `selectedSections[]`, `scenarioIndex`, etc.)

### Bestanden om te verwijderen

Als `src/utils/adviesrapportBuilder.ts` (of vergelijkbare naam) alleen voor het rapport werd gebruikt, verwijder het hele bestand.

---

## Stap 5: Geldverstrekker en NHG prefill

De dialog-velden "Geldverstrekker" en "NHG" moeten worden voorgevuld met de waarden uit de geselecteerde aanvraag. Wanneer de gebruiker een aanvraag selecteert in stap 1:

```typescript
// Na selectie van aanvraag in stap 1:
const aanvraag = aanvragen.find(a => a.id === selectedAanvraagId);

// Prefill uit aanvraag
setGeldverstrekker(aanvraag?.hypotheekverstrekker || "");
setNhg(aanvraag?.nhg ?? true);
```

Als de aanvraag geen `hypotheekverstrekker` of `nhg` veld heeft, zoek dan in de Supabase `aanvragen` tabel naar de correcte kolomnamen. De backend verwacht `hypotheekverstrekker` als string (bijv. "ING") en `nhg` als boolean.

---

## Stap 6: Loading state en error handling

**Tijdens het genereren:**
- Toon een loading spinner op de "Genereer rapport" knop
- Tekst: "Rapport genereren..." (met spinner icon)
- Disable alle form velden en knoppen
- Het genereren duurt 5-15 seconden (WeasyPrint PDF rendering op de server)

**Bij fouten:**
- Toon een `toast.error()` met de foutmelding
- Houd de modal open (zodat de gebruiker instellingen kan aanpassen)
- De foutmelding komt uit `response.detail` (bijv. "Dossier niet gevonden" bij 404)

**Bij succes:**
- Toon een `toast.success("Adviesrapport gedownload")`
- Sluit de modal
- De PDF wordt automatisch gedownload door de browser

---

## Verificatie

| # | Check | Verwacht resultaat |
|---|-------|--------------------|
| 1 | Klik "+ Nieuw advies" op dossierpagina | Modal opent met aanvraag-selectie |
| 2 | Geen aanvragen in dossier | Melding "Maak eerst een aanvraag aan" |
| 3 | Selecteer aanvraag → Volgende | Configuratiescherm verschijnt |
| 4 | Adviseur dropdown | Toont users met role='adviseur'/'admin' |
| 5 | Geldverstrekker en NHG | Voorgevuld uit geselecteerde aanvraag |
| 6 | Risicobereidheid dropdowns | 8 dropdowns met 4 opties elk |
| 7 | Geavanceerde instellingen | Inklapbaar, standaard ingeklapt |
| 8 | Partner-velden (bij stel) | Zichtbaar: loondoorbetaling partner, arbeidsverleden partner, etc. |
| 9 | Partner-velden (bij alleenstaand) | Verborgen |
| 10 | Klik "Genereer rapport" | Loading spinner, PDF wordt gedownload na 5-15 sec |
| 11 | PDF openen | Professioneel rapport met klantnaam, secties, grafieken |
| 12 | PDF secties | Samenvatting, klantprofiel, huidige situatie, financiering, pensioen, risico's, afsluiting |
| 13 | PDF grafieken | Pensioen SVG, overlijden vergelijking, AO/WW staven |
| 14 | Fout bij API-aanroep | Error-toast met foutmelding, modal blijft open |
| 15 | Annuleren | Modal sluit, geen download |
| 16 | Console: geen 422/403 errors | Clean console |
| 17 | Geen oude API-calls meer | Geen fetch naar /calculate/risk-scenarios, /calculate, /monthly-costs in rapport-context |

---

## Samenvatting wijzigingen

| Onderdeel | Actie |
|-----------|-------|
| **Verwijder:** `adviesrapportBuilder.ts` (of equivalent) | Was: 700+ regels data-mapping + sectie-bouw |
| **Verwijder:** `buildAdviesrapportPayload()`, `extractDossierData()`, `mapAflosvorm()`, `mapLeningdeelVoorApi()` | Was: veldnaam-mapping helpers |
| **Verwijder:** `buildSection*()` functies (13 section builders) | Was: per-sectie opbouw |
| **Verwijder:** API calls naar `/risk-scenarios`, `/calculate` ×2, `/monthly-costs` in rapport-context | Was: 3-4 API calls |
| **Wijzig:** AdviesrapportDialog stap 2 | Verwijder sectie-checkboxes, voeg klantprofiel/risicobereidheid velden toe |
| **Nieuw:** `generateAdviesrapportV2()` functie | ~35 regels: haal session token + verzamel opties + 1 fetch call |
| **Behoud:** Wizard stap 1 (aanvraag selectie) | Ongewijzigd |
| **Behoud:** Dialog state management | Ongewijzigd |
| **Behoud:** toast feedback patronen | Ongewijzigd |

**API endpoint:** `POST https://nat-hypotheek-api.onrender.com/adviesrapport-pdf-v2`

**Auth:** Supabase session token meesturen via `Authorization: Bearer <token>`. Haal op via `supabase.auth.getSession()`. Geen NAT API-key nodig.

**Risico:** Laag. De oude `POST /adviesrapport-pdf` (v1) endpoint blijft bestaan voor backward compatibility. De nieuwe `/adviesrapport-pdf-v2` endpoint werkt onafhankelijk.
