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
- Datums altijd in YYYY-MM-DD formaat
- Bedragen als getallen (geen € teken)
- Percentages als getallen (8 = 8%, niet 0.08)
- Rente als percentage (4.5 = 4,5%)
- Looptijd in maanden (360 = 30 jaar)
- Lege strings voor onbekende tekstvelden, null voor onbekende getallen
- Vul ALLEEN velden in waar je data voor hebt uit de documenten
- Maak GEEN waarden aan die niet in de brondata staan
- Bij meerdere inkomstenbronnen (WGV, IBL, loonstrook): maak aparte entries in inkomenAanvrager[]
- Bij meerdere hypotheekdelen: maak aparte entries in hypotheken[0].leningdelen[]
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
- energielabel: "geen_label" | "G" | "F" | "E" | "D" | "C" | "B" | "A" | "A+" | "A++" | "A+++" | "A++++"
- aflossingsvorm: "annuiteit" | "lineair" | "aflossingsvrij" | "spaarhypotheek"
- Vul ALLEEN velden in waar je data voor hebt
"""
