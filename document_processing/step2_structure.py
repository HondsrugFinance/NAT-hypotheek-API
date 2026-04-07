"""Stap 2: Structurering + dossiervergelijking.

Neemt de ruwe extractie uit stap 1 en:
- Mapt naar gestandaardiseerde veldnamen
- Vergelijkt met bestaande dossierdata
- Detecteert inconsistenties per document
"""

import json
import logging
import os

import httpx

logger = logging.getLogger("nat-api.step2")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


def _build_prompt(
    raw_extraction: dict,
    document_type: str,
    persoon: str,
    existing_fields: dict,
    dossier_context: dict,
) -> str:
    aanvrager = dossier_context.get("aanvrager_naam", "onbekend")
    partner = dossier_context.get("partner_naam", "")

    existing_text = ""
    if existing_fields:
        existing_text = f"""
## Bestaande dossierdata (eerder geëxtraheerd of handmatig ingevuld)
{json.dumps(existing_fields, indent=2, ensure_ascii=False)[:4000]}

Vergelijk de nieuwe extractie met bovenstaande data. Meld inconsistenties.
"""

    return f"""Je bent een hypotheekadvies-specialist. Je krijgt een ruwe document-extractie en moet deze structureren.

## Document
Type: {document_type}
Persoon: {persoon}
Aanvrager: {aanvrager}
Partner: {partner or 'geen'}

## Ruwe extractie (uit stap 1)
{json.dumps(raw_extraction, indent=2, ensure_ascii=False)[:8000]}
{existing_text}
## Opdracht
1. Map de geëxtraheerde data naar gestandaardiseerde velden.
2. Groepeer per sectie (persoonsgegevens, inkomen, onderpand, etc.)
3. Gebruik deze veldnamen en formaten:
   - Datums: YYYY-MM-DD
   - Bedragen: getal zonder valutasymbool (55000, niet €55.000)
   - Percentages: getal (8.13, niet 8,13%)
   - Boolean: true/false
   - Namen: voluit, correct gespeld
   - Voorletters: met punten (A.M.)
   - Achternaam apart, tussenvoegsel apart
4. Geef per veld een confidence (0.0-1.0)
5. Meld inconsistenties met bestaande dossierdata
6. Meld waarschuwingen (verlopen document, toekomstige datums, ontbrekende info)

## VERPLICHTE VELDNAMEN — gebruik EXACT deze namen, geen synoniemen

Persoonsgegevens:
  voornamen, achternaam, tussenvoegsel, voorletters, geboortedatum,
  geboorteplaats, geboorteland, nationaliteit, geslacht, bsn, roepnaam,
  eerderGehuwd, datumEchtscheiding, weduweWeduwnaar

Legitimatie:
  legitimatiesoort, legitimatienummer, afgiftedatum, geldigTot, afgifteplaats

Adres/Contact:
  straat, huisnummer, toevoeging, postcode, woonplaats, email, telefoonnummer

Werkgever:
  werkgeverNaam, werkgeverAdres, werkgeverPostcode, werkgeverPlaats,
  kvkNummer, rsin

Dienstverband:
  functie, soortDienstverband, inDienstSinds, directeurAandeelhouder,
  proeftijd, proeftijdVerstreken, loonbeslag, onderhandseLening,
  gemiddeldUrenPerWeek, beroepstype, dienstbetrekkingBijFamilie,
  einddatumContract

WGV inkomen (werkgeversverklaring):
  brutoJaarsalaris, brutoMaandloon, vakantiegeldBedrag, vakantiegeldPercentage,
  eindejaarsuitkering, onregelmatigheidstoeslag, overwerk, provisie,
  dertiendeMaand, structureelFlexibelBudget, variabelBrutoJaarinkomen,
  vastToeslagOpHetInkomen, totaalWgvInkomen

IBL (inkomensbepaling loondienst):
  gemiddeldJaarToetsinkomen, maandelijksePensioenbijdrage

Woning/Onderpand:
  straat, huisnummer, toevoeging, postcode, woonplaats, typeWoning,
  soortOnderpand, waardeWoning, wozWaarde, energielabel, bouwjaar,
  erfpacht, jaarlijkseErfpacht, eigenaar, eigendomAandeelAanvrager,
  eigendomAandeelPartner, woningToepassing, woningstatus, waardeVastgesteldMet

Hypotheek:
  geldverstrekker, hypotheeknummer, hoofdsom, inschrijving, nhg

Leningdeel (per leningdeel):
  bedrag, rentePercentage, aflosvorm, ingangsdatum, looptijd, einddatum,
  ingangsdatumRvp, renteVastPeriode, einddatumRvp, fiscaalRegime

Verplichtingen:
  type, kredietbedrag, maandbedrag, saldo, kredietnummer,
  ingangsdatum, einddatum, status, maatschappij

Bank:
  iban

Pensioen:
  ouderdomspensioenTotaalExclAow, aowBedrag, nabestaandenpensioenPartner,
  nabestaandenpensioenKinderen, pensioenleeftijd

## Documenttype-specifieke instructies

### Bij paspoort / ID-kaart:

ALLE onderstaande velden zijn VERPLICHT. Als een veld niet gevonden kan worden, meld dit als waarschuwing.

Voorbeeld van CORRECTE output bij een paspoort:
  "voornamen": "Aranxtha Alana",
  "tussenvoegsel": "van der",
  "achternaam": "Lee",
  "voorletters": "A.A.",
  "geslacht": "V",
  "geboortedatum": "1997-07-14",
  "geboorteplaats": "Weesp",
  "nationaliteit": "Nederlandse",
  "legitimatiesoort": "paspoort",
  "legitimatienummer": "NMHJR4073",
  "afgiftedatum": "2016-06-23",
  "geldigTot": "2026-06-23",
  "afgifteplaats": "Wijdemeren"

REGELS:
- ACHTERNAAM en TUSSENVOEGSEL ALTIJD apart splitsen. Dit is de BELANGRIJKSTE regel.
  Op een Nederlands paspoort staat de achternaam in de MRZ-zone EN bovenaan het document.
  Voorbeelden: "van der Lee" → tussenvoegsel="van der", achternaam="Lee"
  "de Jong" → tussenvoegsel="de", achternaam="Jong"
  "Van Hall" → tussenvoegsel="van", achternaam="Hall"
  "Brust" → tussenvoegsel (leeg), achternaam="Brust"
  Bekende tussenvoegsels: van, de, van de, van der, den, ter, ten, het, in 't, van den, van het.
- LEGITIMATIESOORT: ALTIJD "paspoort" bij paspoort, "id_kaart" bij ID-kaart. NOOIT leeg laten.
- GELDIG TOT: ALTIJD invullen. Staat op ELKE paspoort/ID. Als je het niet vindt: meld als waarschuwing.
- AFGIFTEDATUM: ALTIJD invullen. Staat op ELKE paspoort/ID als veld 9 "datum van afgifte".
  Format op paspoort: "13 JUL/JUL 2016" → afgiftedatum = "2016-07-13".
  Nederlandse maanden: JAN=01, FEB=02, MRT/MAA=03, APR=04, MEI/MAY=05, JUN=06,
  JUL=07, AUG=08, SEP=09, OKT/OCT=10, NOV=11, DEC=12.
- GELDIG TOT: staat op ELKE paspoort/ID als veld 10 "geldig tot / date of expiry".
  Zelfde format. ALTIJD invullen.
- AFGIFTEPLAATS: ALTIJD invullen. "Burg. van [stad]" = afgifteplaats = [stad].
- BSN: ALTIJD exact 9 cijfers. Als minder of meer: meld als waarschuwing.
- Documentnummer: kan NOOIT een klinker bevatten (A, E, I, O, U = OCR-fout: O→0, I→1).
- Geslacht: M of V (niet M/F of V/F)
- Voorletters: afleiden uit voornamen (eerste letters + punten)

### Bij werkgeversverklaring:
- BEREKEN het totale WGV toetsinkomen: de SOM van ALLE genummerde posten (1 t/m 10 of meer).
  Dit zijn: bruto jaarsalaris + vakantietoeslag + 13e maand + eindejaarsuitkering + ORT +
  overwerk + provisie + flexibel budget + bijdrage levensloop + consign. toeslag + eventuele andere posten.
  Sla dit op als veld "totaalWgvInkomen".
- gemiddeldUrenPerWeek: ALTIJD invullen. Staat op de WGV als "Aantal uren per week" of "Arbeidsduur".
- Neem ALLE posten op, ook als ze €0 zijn (dit bevestigt dat ze bewust zijn ingevuld).
- COMPLEETHEIDSCHECK: controleer of alle verplichte velden zijn ingevuld:
  * Loonbeslag/looncessie: MOET ja of nee zijn
  * Onderhandse lening: MOET ja of nee zijn
  * Directeur-aandeelhouder: MOET ja of nee zijn
  * Reorganisatie aangekondigd: MOET ja of nee zijn
  * Proeftijd: MOET ja of nee zijn
  * Als proeftijd = Ja → proeftijd verstreken MOET ook ingevuld zijn
  * Handtekening werkgever: MOET aanwezig zijn
  * Datum ondertekening: MOET ingevuld zijn
  Meld ELKE ontbrekende of niet-ingevulde veld als waarschuwing:
  "WGV onvolledig: [veldnaam] is niet ingevuld"

### Bij hypotheekoverzicht:
- Extraheer ELKE leningdeel APART. Gebruik een array "leningdelen" in de fields:
  "leningdelen": [
    {{"bedrag": 150000, "rentePercentage": 4.5, "aflosvorm": "annuitair", "ingangsdatum": "2020-01-01",
      "looptijd": 360, "einddatum": "2050-01-01", "ingangsdatumRvp": "2020-01-01",
      "renteVastPeriode": 10, "einddatumRvp": "2030-01-01", "fiscaalRegime": "box1_na_2013",
      "restschuld": 140000}},
    ...
  ]
- Extraheer OOK de overstijgende gegevens: geldverstrekker, hypotheeknummer, hoofdsom, inschrijving, nhg, wozWaarde.
- Als het overzicht meerdere leningdelen bevat (bijv. annuïtair + aflossingsvrij), maak aparte entries.
- INGANGSDATUM per leningdeel: ALTIJD invullen als deze op het document staat. Dit is cruciaal.
- RenteVastPeriode in JAREN (niet maanden). Looptijd in MAANDEN.
- FiscaalRegime: "box1_na_2013" voor leningen na 2013, "box1_voor_2013" voor leningen vóór 2013, "box3" voor box 3.
  Als ingangsdatum >= 2013 → ALTIJD "box1_na_2013" (niet "box1_voor_2013").

### Bij pensioenspecificatie / UPO:

ALLE onderstaande velden zijn VERPLICHT als ze op het document staan.

Voorbeeld van CORRECTE output:
  "ouderdomspensioenTotaalExclAow": 19249,
  "aowBedrag": 20929,
  "nabestaandenpensioenPartner": 8500,
  "nabestaandenpensioenKinderen": 3200,
  "pensioenleeftijd": 67

REGELS:
- "ouderdomspensioenTotaalExclAow": SOM van alle pensioenfondsen EXCLUSIEF SVB/AOW.
  Tel de "te bereiken" bedragen op van elk fonds. NIET de "opgebouwd" bedragen.
- "aowBedrag": het "te bereiken" AOW-bedrag van SVB. Dit staat apart vermeld.
- "nabestaandenpensioenPartner": het TOTALE nabestaandenpensioen voor de partner.
  Dit staat op het document als "nabestaandenpensioen", "partnerpensioen" of "Anw-hiaatpensioen".
  Tel alle fondsen op. Als dit bedrag op het document staat: ALTIJD invullen, NOOIT overslaan.
- "nabestaandenpensioenKinderen": het TOTALE wezenpensioen. ALTIJD invullen als vermeld.
- "pensioenleeftijd": de pensioenleeftijd (bijv. 67, 68). Staat op elk pensioenoverzicht.
- Bepaal scenario: AOW-datum in de toekomst = "voor pensionering", anders "na pensionering".
  Gebruik het bedrag van het juiste scenario.
- "weduweWeduwnaar": true als persoon nabestaandenpensioen ontvangt als nabestaande.

Antwoord in exact dit JSON formaat:
{{
  "sectie": "{document_type}",
  "persoon": "{persoon}",
  "fields": {{
    "veldnaam": waarde,
    ...
  }},
  "field_confidence": {{
    "veldnaam": 0.95,
    ...
  }},
  "inconsistenties": [
    {{"veld": "...", "huidig": "...", "nieuw": "...", "bron": "..."}}
  ],
  "waarschuwingen": ["...", "..."],
  "suggesties": ["...", "..."]
}}"""


async def structure_and_compare(
    raw_extraction: dict,
    document_type: str,
    persoon: str,
    existing_fields: dict,
    dossier_context: dict,
) -> dict:
    """Structureer ruwe extractie en vergelijk met bestaande dossierdata."""
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("Claude API niet geconfigureerd")

    prompt = _build_prompt(raw_extraction, document_type, persoon, existing_fields, dossier_context)

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 3000,
        "temperature": 0.0,
        "messages": [{"role": "user", "content": prompt}],
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(ANTHROPIC_URL, headers=headers, json=payload)

        if resp.status_code != 200:
            logger.error("Claude stap 2 mislukt: %s %s", resp.status_code, resp.text[:300])
            raise RuntimeError(f"Claude API fout: {resp.status_code}")

        data = resp.json()
        text = data["content"][0]["text"].strip()

        try:
            start = text.index("{")
            end = text.rindex("}") + 1
            return json.loads(text[start:end])
        except (ValueError, json.JSONDecodeError) as e:
            logger.error("Claude stap 2: ongeldig JSON: %s", text[:300])
            raise RuntimeError(f"Claude stap 2: kon JSON niet parsen: {e}")
