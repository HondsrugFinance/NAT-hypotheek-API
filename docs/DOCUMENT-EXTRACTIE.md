# Document Extractie — Architectuur & Regels

## Overzicht

De document extractie pipeline verwerkt hypotheekdocumenten automatisch en vult het aanvraagformulier voor. Het systeem bestaat uit 4 stappen:

```
Document upload → [Stap 1: Extract] → [Stap 2: Structureer] → [Stap 3: Analyseer] → [Stap 4: Map naar formulier]
         ↓              Claude              Claude              Claude              Python
    SharePoint      "vertel me alles"    standaardiseer      dossier-analyse     field_mapper_v2.py
      _inbox        document_extractions  extracted_fields    dossier_analysis    import_cache
```

### Principe: AI analyseert, Python vertaalt

- **Claude** (AI) doet het denkwerk: documenten lezen, classificeren, data extraheren, inconsistenties signaleren
- **Python** doet de vertaling: extracted data → formuliervelden (deterministisch, instant, geen API call)
- **Checkvragen** komen uit stap 3 (AI-analyse), niet uit hardcoded regels

---

## Stap 1: Vrije extractie (`step1_extract_all.py`)

**Wat:** Claude leest het document en extraheert ALLE informatie.
**Input:** Document (PDF/foto via Vision API, of tekst via PyPDF2)
**Output:** `document_extractions` tabel (classificatie + ruwe data)

### Classificatie
Claude bepaalt:
- **document_type**: paspoort, werkgeversverklaring, hypotheekoverzicht, etc. (49 types)
- **persoon**: aanvrager, partner, gezamenlijk, ex-partner
- **confidence**: 0.0 - 1.0

### Extractie
Alle data in categorieën: persoonsgegevens, adressen, financieel, datums, document_specifiek, opvallend.

### Speciale routes
- **UWV Verzekeringsbericht**: skip stap 1, direct naar IBL-tool voor toetsinkomen
- **Simpele documenten** (bankafschrift, jaaropgave): gecombineerde stap 1+2 (`step_combined.py`)

### Prompt-locatie
`document_processing/step1_extract_all.py` → `_build_prompt()`

---

## Stap 2: Structurering (`step2_structure.py`)

**Wat:** Claude structureert de ruwe extractie naar gestandaardiseerde veldnamen.
**Input:** Ruwe extractie uit stap 1 + bestaande dossierdata
**Output:** `extracted_fields` tabel (sectie, persoon, fields, field_confidence)

### Canonieke veldnamen
Step 2 prompt bevat een VERPLICHTE veldnamenlijst. Claude moet EXACT deze namen gebruiken.
Zie: `step2_structure.py` → sectie "VERPLICHTE VELDNAMEN"

### Documenttype-specifieke instructies
- **Paspoort/ID**: achternaam + tussenvoegsel apart splitsen, legitimatiesoort altijd invullen
- **Werkgeversverklaring**: totaalWgvInkomen berekenen (som alle posten), compleetheidscheck
- **Hypotheekoverzicht**: leningdelen per stuk extraheren (array)
- **Pensioenspecificatie**: ouderdomspensioen, AOW, nabestaandenpensioen (verplichte velden)

### Prompt-locatie
`document_processing/step2_structure.py` → `_build_prompt()`

---

## Stap 3: Dossier-analyse (`step3_dossier_analysis.py`)

**Wat:** Claude analyseert ALLE documenten samen en identificeert keuzemomenten.
**Input:** Alle document_extractions + extracted_fields
**Output:** `dossier_analysis` tabel (compleetheid, inconsistenties, inkomen_analyse, beslissingen)

### Beslissingen (checkvragen)
Stap 3 identificeert situaties waar de adviseur moet kiezen:
- Meerdere inkomens (WGV vs IBL)
- Geldverstrekker naam-mismatch
- Doelstelling afleiden uit documenten
- Ondernemersinkomen (verwerk winsten of handmatig)

### Wat GEEN beslissing is
- Data die letterlijk uit één document komt
- Werkgever-details, WGV-deelbedragen
- Paspoortgegevens

### Prompt-locatie
`document_processing/step3_dossier_analysis.py` → `_build_prompt()`

### Config-injectie
Stap 3 krijgt de toegestane waarden uit `config/geldverstrekkers.json` en `config/dropdowns.json` mee via `config_loader.py`.

---

## Stap 4: Python field mapper (`field_mapper_v2.py`)

**Wat:** Deterministische vertaling van extracted_fields → AanvraagData formuliervelden.
**Input:** extracted_fields + beslissingen uit stap 3
**Output:** `import_cache` tabel (merged_data, velden, check_vragen)

### Geen Claude call
De mapper is pure Python — instant, deterministisch, testbaar. Zelfde input = zelfde output.

### Mapping-tabel
`_SECTIE_MAPPINGS` dict koppelt documenttypes aan mapping-tabellen:
- paspoort → `_PERSOON_MAP` + `_IDENTITEIT_MAP`
- werkgeversverklaring → `_WERKGEVER_MAP` + `_DIENSTVERBAND_MAP` + `_WGV_INKOMEN_MAP`
- hypotheekoverzicht → `_HYPOTHEEK_MAP` + `_WONING_MAP` (GEEN adres)
- etc.

### Bronprioriteit
Documenten worden in volgorde van betrouwbaarheid verwerkt:
1. Paspoort (0)
2. ID-kaart (1)
3. Werkgeversverklaring (3)
4. Salarisstrook/loonstrook (4)
5. IBL (5)
6. Taxatierapport (6)
7. Hypotheekoverzicht (7)
8. Overig (99)

**Rijbewijs wordt NIET gemapped** (kan van ex-partner zijn, geen geldig legitimatiebewijs).

### Waarde-transformaties (`_VALUE_TRANSFORMS`)
Document-waarden → Lovable dropdown-waarden:
- "arbeidsovereenkomst voor onbepaalde tijd" → "Loondienst – vast"
- "Tussen-/schakelwoning" → "woning" (typeWoning)
- "Semi-bungalow" → "vrijstaand" (soortOnderpand)
- "Onbekend" → "geen_label" (energielabel)
- True/False → "Ja"/"Nee" (directeurAandeelhouder, proeftijd, etc.)

### Afgeleide velden (`_set_derived_fields`)
Python berekent velden die Claude niet betrouwbaar levert:
- **Voorletters**: afleiden uit voornamen ("Chantal" → "C.")
- **Roepnaam**: eerste voornaam
- **Legitimatiesoort**: afleiden uit documenttype (paspoort → "paspoort")
- **GeldigTot**: afgiftedatum + 10 jaar (als geldigTot mist)
- **Achternaam split**: "van Hall" → tussenvoegsel "van" + achternaam "Hall"
- **heeftPartner**: true als er partner-documenten zijn
- **Inkomen type + soortBerekening**: afleiden uit welke documenten aanwezig zijn

### Velden die NIET gemapped worden
- **BSN**: privacy, niet opslaan in formulier
- **WGV sub-inkomens**: alleen totaalWgvInkomen telt
- **Adres/contact**: komt uit Lovable dossier-prefill, niet uit documenten
- **Einddatum inkomen**: Lovable default = AOW-datum
- **Defaults** (geboorteland, nationaliteit, land, afgifteland): behouden, alleen overschrijven als duidelijk anders

### Skip 0-waarden
WGV deelbedragen met waarde 0 worden niet ingevuld (ruis).

---

## Referentie-documenten

| Document | Locatie | Beschrijving |
|----------|---------|-------------|
| **Master Excel** | `docs/prefill-mapping-master.xlsx` | Levend document: alle formuliervelden, bronnen per veld, dossierdata, feedback |
| **Document-lijst** | `docs/document-lijst.xlsx` | Alle 49 documenttypen met extractievelden |
| **Extractie-mapping** | `docs/document-extractie-mapping.xlsx` | Per veld: primaire/secundaire bron, vereist bij klanttype, auto/handmatig |
| **Config: geldverstrekkers** | `config/geldverstrekkers.json` | Toegestane geldverstrekker-namen |
| **Config: dropdowns** | `config/dropdowns.json` | Alle dropdown-opties (energielabel, dienstverband, etc.) |

---

## Bekende beperkingen

### Claude extractie-kwaliteit
Claude volgt instructies niet altijd consistent:
- Achternaam/tussenvoegsel wordt soms niet gesplitst → Python fallback
- GeldigTot paspoort wordt soms niet geëxtraheerd → Python berekening
- Nabestaandenpensioen wordt niet betrouwbaar geëxtraheerd → verbeteren met voorbeelden
- Partner-gegevens missen soms → step 1 classificatie verbeteren

### Aanbeveling: feedback-loop
Verwerk dossiers en noteer fouten. Na 10-20 dossiers: patronen analyseren en prompts gericht verbeteren. Gebruik het "Feedback log" tabblad in de master Excel.

---

## Bestanden

| Bestand | Functie |
|---------|---------|
| `document_processing/pipeline_v2.py` | Orchestratie: stap 0-3 + cache vullen |
| `document_processing/step1_extract_all.py` | Stap 1: vrije extractie (Claude Vision/tekst) |
| `document_processing/step2_structure.py` | Stap 2: structurering + vergelijking |
| `document_processing/step3_dossier_analysis.py` | Stap 3: dossier-analyse + beslissingen |
| `document_processing/field_mapper_v2.py` | Stap 4: Python field mapping (deterministisch) |
| `document_processing/smart_mapper.py` | Cache, prefill endpoint, apply-imports |
| `document_processing/config_loader.py` | Config-waarden laden voor prompts |
| `document_processing/ibl_runner.py` | IBL-tool wrapper (UWV → toetsinkomen) |
| `document_processing/route.py` | FastAPI endpoints |

### Admin endpoints
| Endpoint | Functie |
|----------|---------|
| `POST /doc-processing/{id}/process-all` | Scan inbox + verwerk alles |
| `POST /doc-processing/{id}/reprocess-all` | Herverwerk alle documenten (stap 1+2+3) |
| `POST /doc-processing/{id}/rerun-analysis` | Alleen stap 3 + cache opnieuw |
| `DELETE /doc-processing/{id}/clear-cache` | Cache legen |
| `GET /doc-processing/{id}/prefill-aanvraag` | Prefill data ophalen |
| `GET /doc-processing/{id}/available-imports` | Alle gemapte velden bekijken |
