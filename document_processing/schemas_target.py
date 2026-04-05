"""Doelschema's voor smart import mapping.

Deze schema's beschrijven de structuur van AanvraagData en berekening-invoer.
Claude gebruikt ze om geëxtraheerde data op de juiste plek te zetten.

ONDERHOUD: als het TypeScript-type in Lovable verandert, update hier.
Bron: src/utils/aanvraagStorage.ts en src/types/hypotheek.ts
"""

# ---------------------------------------------------------------------------
# AanvraagData schema — alle velden van een hypotheekaanvraag
# ---------------------------------------------------------------------------
AANVRAAG_SCHEMA = """\
AanvraagData is het volledige datamodel van een hypotheekaanvraag.
Het heeft de volgende structuur:

{
  "doelstelling": "",  // "aankoop_bestaande_bouw" | "hypotheek_verhogen" | "hypotheek_oversluiten" | "partner_uitkopen" | ""
  "heeftPartner": false,
  "burgerlijkeStaat": "",  // "samenwonend" | "gehuwd" | "geregistreerd_partner" | ""
  "samenlevingsvorm": "",

  "aanvrager": {
    "persoon": {
      "geslacht": "",  // "man" | "vrouw" | ""
      "voorletters": "",
      "voornamen": "",
      "roepnaam": "",
      "tussenvoegsel": "",
      "achternaam": "",
      "eerderGehuwd": false,
      "datumEchtscheiding": "",
      "weduweWeduwnaar": false,
      "geboortedatum": "",  // ISO date YYYY-MM-DD
      "geboorteplaats": "",
      "geboorteland": "Nederland",
      "nationaliteit": "Nederlandse"
    },
    "adresContact": {
      "postcode": "",
      "huisnummer": "",
      "toevoeging": "",
      "straat": "",
      "woonplaats": "",
      "land": "Nederland",
      "email": "",
      "telefoonnummer": ""
    },
    "identiteit": {
      "legitimatiesoort": "",  // "paspoort" | "europese_id" | ""
      "legitimatienummer": "",
      "afgiftedatum": "",  // ISO date
      "geldigTot": "",     // ISO date
      "afgifteplaats": "",
      "afgifteland": "Nederland"
    },
    "werkgever": {
      "naam": "",
      "adres": "",
      "postcode": "",
      "plaats": "",
      "telefoon": "",
      "dienstverband": "",
      "functie": "",
      "inDienstSinds": "",
      "contractType": "",
      "brutoJaarinkomen": 0,
      "vakantiegeld": true,
      "dertiendeMaand": false
    }
  },

  "partner": null,  // Zelfde structuur als aanvrager, of null als alleenstaand

  "kinderen": [],  // [{id, geboortedatum, roepnaam, achternaam}]

  "woningen": [
    {
      "id": "",
      "straat": "", "huisnummer": "", "toevoeging": "", "postcode": "", "woonplaats": "",
      "eigenaar": "",  // "aanvrager" | "partner" | "gezamenlijk" | ""
      "eigendomAandeelAanvrager": 50, "eigendomAandeelPartner": 50,
      "woningToepassing": "",  // "eigen_woning" | "huurwoning" | ""
      "soortOnderpand": "",    // "2-onder-1-kap" | "tussenwoning" | "vrijstaand" | etc.
      "typeWoning": "",        // "woning" | "appartement" | ""
      "waardeWoning": null,
      "waardeVastgesteldMet": "",  // "taxatierapport" | "desktoptaxatie" | etc.
      "wozWaarde": null,
      "woningstatus": "",  // "behouden" | "verkopen" | ""
      "erfpacht": false,
      "jaarlijkseErfpacht": null,
      "energielabel": "",  // "A" | "B" | ... | "geen_label"
      "afgiftedatumEnergielabel": ""
    }
  ],

  "inkomenAanvrager": [
    {
      "id": "",
      "type": "loondienst",  // "loondienst" | "onderneming" | "pensioen" | "uitkering" | "vermogen" | "ander_inkomen"
      "soort": "",
      "inkomstenbron": "",
      "ingangsdatum": "",
      "einddatum": "",
      "jaarbedrag": null,
      "isAOW": false,

      "loondienst": {
        "soortBerekening": "werkgeversverklaring",  // "inkomensbepaling_loondienst" | "werkgeversverklaring" | "flexibel_jaarinkomen"
        "gemiddeldJaarToetsinkomen": null,  // IBL toetsinkomen
        "maandelijksePensioenbijdrage": null,
        "aantalWerkgevers": 1,

        "werkgeversverklaringCalc": {
          "brutoSalaris": null,
          "periode": "jaar",  // "jaar" | "maand"
          "vakantiegeldPercentage": 8,
          "vakantiegeldBedrag": null,
          "eindejaarsuitkering": null,
          "onregelmatigheidstoeslag": null,
          "overwerk": null,
          "provisie": null,
          "structureelFlexibelBudget": null,
          "vebAfgelopen12Maanden": null,
          "dertiendeMaand": null,
          "variabelBrutoJaarinkomen": null,
          "vastToeslagOpHetInkomen": null
        },

        "flexibelJaarinkomen": {
          "jaar1": null, "jaar2": null, "jaar3": null
        },

        "werkgever": {
          "naamWerkgever": "",
          "postcodeWerkgever": "",
          "huisnummer": "",
          "toevoeging": "",
          "adresWerkgever": "",
          "vestigingsplaats": "",
          "vestigingsland": "Nederland",
          "kvkNummer": "",
          "rsin": ""
        },

        "dienstverband": {
          "beroepstype": "",
          "functie": "",
          "soortDienstverband": "",  // "Loondienst – vast" | etc.
          "gemiddeldUrenPerWeek": null,
          "directeurAandeelhouder": "Nee",
          "inDienstSinds": "",
          "dienstbetrekkingBijFamilie": "Nee",
          "proeftijd": "Nee",
          "proeftijdVerstreken": "Nee",
          "einddatumContract": "",
          "loonbeslag": "Nee",
          "onderhandseLening": "Nee"
        }
      },

      "pensioenData": {
        "ouderdomspensioen": {
          "ingangsdatumType": "AOW-datum",
          "ingangsdatum": "", "einddatum": "", "standPer": "",
          "bedrag": null, "indicatief": "Nee"
        },
        "partnerpensioen": { "verzekerdVoor": null, "verzekerdVanaf": null },
        "wezenpensioen": { "verzekerd": null, "uitkeringTotLeeftijdKind": "18 jaar" }
      }
    }
  ],

  "inkomenPartner": [],  // Zelfde structuur als inkomenAanvrager

  "verplichtingen": [
    {
      "id": "",
      "type": "",  // "doorlopend_krediet" | "aflopend_krediet" | "private_lease" | "studieschuld" | "partneralimentatie"
      "kredietnummer": "",
      "ingangsdatum": "", "einddatum": "",
      "maatschappij": "",
      "status": "",  // "lopend" | "aflossen_tijdens_passeren" | "aflossen_voor_passeren"
      "kredietbedrag": null,
      "maandbedrag": null,
      "saldo": null,
      "rentepercentage": null,
      "nogAfTeLossen": null
    }
  ],

  "hypotheekInschrijvingen": [
    {
      "id": "",
      "onderpandWoningIds": [],
      "geldverstrekker": "",
      "inschrijving": null,
      "rangorde": 1,
      "eigenaar": "",  // "gezamenlijk" | "aanvrager" | "partner"
      "nhg": false
    }
  ],

  "hypotheken": [
    {
      "id": "",
      "inschrijvingId": "",
      "hypotheeknummer": "",
      "hoofdsom": null,
      "leningdelen": [
        {
          "id": "",
          "leningdeelnummer": "",
          "aflosvorm": "",  // "annuitair" | "lineair" | "aflossingsvrij" | "bankspaarhypotheek" | "spaarhypotheek"
          "bedrag": null,
          "rentePercentage": null,
          "fiscaalRegime": "",  // "box1_na_2013" | "box1_voor_2013" | "box3"
          "ingangsdatum": "",
          "looptijd": null,  // maanden (1-360)
          "einddatum": "",
          "ingangsdatumRvp": "",
          "renteVastPeriode": null,  // jaren (1-30)
          "einddatumRvp": "",
          "renteAftrekTot": "",
          "restschuld": null
        }
      ]
    }
  ],

  "vermogenSectie": {
    "iban": {
      "ibanAanvrager": "",
      "ibanPartner": ""
    },
    "items": []
  }
}

REGELS:

Formatting:
- Datums altijd in YYYY-MM-DD formaat
- Bedragen als getallen (geen € teken)
- Percentages als getallen (8 = 8%, niet 0.08)
- Rente als percentage (4.5 = 4,5%)
- Looptijd in maanden (360 = 30 jaar)
- RenteVastPeriode in jaren (10 = 10 jaar)

Wat NIET invullen:
- Vul ALLEEN velden in waar je CONCRETE data voor hebt uit de documenten
- Maak GEEN waarden aan die niet in de brondata staan
- Als een waarde niet te extraheren is: LAAT HET VELD WEG uit de JSON (niet "" of null zetten)
  Dit is cruciaal: het formulier heeft defaults (bijv. einddatum=AOW). Als je "" invult overschrijf je die default.
- Vul GEEN financieringsopzet in (dat is een adviseur-keuze, geen documentdata)

Inkomen:
- Maak maar ÉÉN inkomen-entry per persoon. Kies het HOOGSTE betrouwbare inkomen.
  Als er WGV én IBL beschikbaar zijn: gebruik het WGV-inkomen (werkgeversverklaring) als primaire entry.
  Zet het IBL toetsinkomen als gemiddeldJaarToetsinkomen in hetzelfde inkomen-object.
- Bij soortBerekening: gebruik "werkgeversverklaring" als er een WGV is, anders "inkomensbepaling_loondienst"
- inkomstenbron: vul de werkgevernaam in
- ingangsdatum: datum in dienst
- einddatum: LAAT WEG (niet "" zetten — de frontend default is AOW-datum)
- jaarbedrag: totaal WGV inkomen of IBL toetsinkomen

Hypotheek:
- hypotheekInschrijvingen[].inschrijving = het bij de notaris GEREGISTREERDE bedrag (uit kadaster_hypotheek document).
  Dit is NIET de marktwaarde en NIET de som van leningdelen. Het kan hoger zijn dan de werkelijke lening.
  Als het kadaster-document niet beschikbaar is: LAAT het inschrijvingsbedrag WEG.
- hypotheekInschrijvingen[].geldverstrekker = de geldverstrekker uit het hypotheekoverzicht
- hypotheken[].leningdelen: vul ALLE beschikbare velden in:
  - ingangsdatum: oorspronkelijke startdatum van het leningdeel (als bekend)
  - looptijd: originele looptijd in maanden (als bekend)
  - einddatum: einddatum van het leningdeel (als bekend)
  - ingangsdatumRvp: startdatum van de huidige rentevaste periode
  - renteVastPeriode: duur in JAREN (niet maanden)
  - einddatumRvp: einddatum rentevaste periode
  - renteAftrekTot: tot wanneer rente aftrekbaar is (meestal 30 jaar na ingangsdatum)
  - fiscaalRegime: "box1_na_2013" voor leningen na 2013, "box1_voor_2013" voor leningen vóór 2013
- Bij meerdere hypotheekdelen: maak aparte entries in hypotheken[0].leningdelen[]

Geldverstrekker:
- Gebruik ALLEEN namen uit de TOEGESTANE WAARDEN sectie.
- Als de naam op het document niet exact matcht, kies de dichtstbijzijnde match
  en geef de originele naam als alternatief.
- Als er GEEN match is: laat het veld leeg met een reden.

Verplichtingen:
- Vul alleen verplichtingen in die EXPLICIET in de documenten staan (BKR, leningoverzicht)
- Geen aannames over verplichtingen die niet gedocumenteerd zijn
"""

# ---------------------------------------------------------------------------
# Berekening schema — invoer voor Aankoop of Aanpassen
# ---------------------------------------------------------------------------
BEREKENING_SCHEMA = """\
Berekening-invoer is het datamodel voor een hypotheekberekening (haalbaarheid).
Het heeft twee varianten: Aankoop en Aanpassen.

GEMEENSCHAPPELIJKE structuur:
{
  "klantGegevens": {
    "alleenstaand": true,
    "roepnaamAanvrager": "",
    "tussenvoegselAanvrager": "",
    "achternaamAanvrager": "",
    "geboortedatumAanvrager": "",
    "roepnaamPartner": "",
    "tussenvoegselPartner": "",
    "achternaamPartner": "",
    "geboortedatumPartner": ""
  },

  "haalbaarheidsBerekeningen": [
    {
      "id": "",
      "naam": "",
      "inkomenGegevens": {
        "hoofdinkomenAanvrager": 0,
        "hoofdinkomenPartner": 0,
        "ontvangtAow": false,
        "inkomenUitLijfrenteAanvrager": 0,
        "partneralimentatieOntvangenAanvrager": 0,
        "inkomstenUitVermogen": 0,
        "huurinkomsten": 0,
        "partneralimentatieBetalenAanvrager": 0,
        "inkomenUitLijfrentePartner": 0,
        "partneralimentatieOntvangenPartner": 0,
        "partneralimentatieBetalenPartner": 0,
        "limieten": 0,
        "maandlastLeningen": 0,
        "studielening": 0,
        "erfpachtcanon": 0,
        "partneralimentatieBetalen": 0
      },
      "leningDelen": [
        {
          "id": "",
          "bedrag": 0,
          "bedragBox3": 0,
          "rentevastePeriode": 120,
          "rentepercentage": 5.0,
          "aflossingsvorm": "annuiteit",
          "renteAftrekbaar": true,
          "origineleLooptijd": 360,
          "restantLooptijd": 360,
          "inleg": 0
        }
      ],
      "onderpand": {
        "marktwaarde": 0,
        "energielabel": "geen_label",
        "bedragEbvEbb": 0
      }
    }
  ]
}

ALLEEN VOOR AANKOOP (extra velden):
{
  "berekeningen": [
    {
      "woningType": "bestaande_bouw",
      "aankoopsomWoning": 0,
      "verbouwing": 0,
      "wozWaarde": 0,
      "nhgToepassen": false,
      "eigenGeld": 0
    }
  ]
}

ALLEEN VOOR AANPASSEN (extra velden op root):
{
  "aanpassingType": "verhogen",  // "verhogen" | "oversluiten" | "uitkopen"
  "huidigeHypotheek": 0,
  "verbouwing": 0,
  "uitkoopPartner": 0,
  "wozWaarde": 0
}

REGELS:
- hoofdinkomenAanvrager/Partner = jaarbedrag
- rentepercentage = percentage (5.0 = 5%)
- Looptijden in maanden (360 = 30 jaar)
- energielabel: zie TOEGESTANE WAARDEN sectie
- aflossingsvorm: zie TOEGESTANE WAARDEN sectie
- Vul ALLEEN velden in waar je CONCRETE data voor hebt uit de documenten
- Als een waarde niet te extraheren is: LAAT HET VELD WEG (niet 0 of "" zetten)
- Maak maar ÉÉN inkomen-entry per persoon (gebruik het hoogste betrouwbare inkomen)
- Geldverstrekker: gebruik ALLEEN namen uit de TOEGESTANE WAARDEN sectie
"""
