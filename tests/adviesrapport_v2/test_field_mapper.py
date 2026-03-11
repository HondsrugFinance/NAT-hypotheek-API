"""Tests voor adviesrapport_v2.field_mapper.

Gebruikt invoer JSONB snapshots gebaseerd op de G6 diagnostiek output.
"""

import pytest
from adviesrapport_v2.field_mapper import (
    extract_dossier_data, _normalize_rente, _map_aflosvorm,
    _is_overbrugging, _extract_leningdelen_from_dossier, _get, _map_woning_type,
)


# ═══════════════════════════════════════════════════════════════════════
# Invoer snapshots (uit G6 console output)
# ═══════════════════════════════════════════════════════════════════════

INVOER_SNAPSHOT = {
    "klantGegevens": {
        "naamAanvrager": "Harry Slinger",
        "naamPartner": "Harriette Slinger",
        "alleenstaand": False,
        "geboortedatumAanvrager": "1968-02-01",
        "geboortedatumPartner": "1971-02-01",
    },
    "haalbaarheidsBerekeningen": [
        {"id": "hb1", "naam": "Huidige situatie",
         "inkomenKeys": ["hoofd_inkomen_aanvrager"]},
    ],
    "berekeningen": [
        {"id": "ber1", "naam": "Bij tijdelijk twee woningen",
         "aankoopsomWoning": 635000, "eigenGeld": 0},
        {"id": "ber2", "naam": "Na verkoop bestaande woning",
         "aankoopsomWoning": 635000, "eigenGeld": 1000},
    ],
    "_dossierScenario1": {
        "id": "sc1",
        "naam": "Scenario 1",
        "leningDelen": [
            {
                "bedrag": 228000,
                "bedragBox3": 0,
                "aflossingsvorm": "aflossingsvrij",
                "rentepercentage": 2.8,
                "restantLooptijd": 360,
                "origineleLooptijd": 360,
                "rentevastePeriode": 120,
            },
            {
                "bedrag": 186300,
                "bedragBox3": 0,
                "aflossingsvorm": "annuiteit",
                "rentepercentage": 4.1,
                "restantLooptijd": 360,
                "origineleLooptijd": 360,
                "rentevastePeriode": 120,
            },
            {
                "bedrag": 239000,
                "bedragBox3": 0,
                "aflossingsvorm": "overbrugging",
                "rentepercentage": 4.3,
                "restantLooptijd": 24,
                "origineleLooptijd": 24,
                "rentevastePeriode": 12,
            },
        ],
    },
}

DOSSIER_SNAPSHOT = {"invoer": INVOER_SNAPSHOT}
AANVRAAG_SNAPSHOT = {
    "id": "aanvraag-1",
    "hypotheekverstrekker": "ING",
    "nhg": True,
}


# ═══════════════════════════════════════════════════════════════════════
# Helper tests
# ═══════════════════════════════════════════════════════════════════════

class TestHelpers:
    def test_get_first_key(self):
        assert _get({"a": 1, "b": 2}, "a", "b") == 1

    def test_get_fallback(self):
        assert _get({"b": 2}, "a", "b") == 2

    def test_get_default(self):
        assert _get({"c": 3}, "a", "b", default=99) == 99

    def test_normalize_rente_percentage(self):
        """4.1 (percentage) → 0.041 (decimaal)."""
        assert _normalize_rente(4.1) == pytest.approx(0.041)

    def test_normalize_rente_decimal(self):
        """0.041 blijft 0.041."""
        assert _normalize_rente(0.041) == pytest.approx(0.041)

    def test_normalize_rente_high_percentage(self):
        """2.8 (percentage) → 0.028."""
        assert _normalize_rente(2.8) == pytest.approx(0.028)

    def test_normalize_rente_none(self):
        assert _normalize_rente(None) == 0.05

    def test_map_aflosvorm_annuiteit(self):
        assert _map_aflosvorm("annuiteit") == "Annuïteit"

    def test_map_aflosvorm_annuitiet_met_trema(self):
        assert _map_aflosvorm("annuïteit") == "Annuïteit"

    def test_map_aflosvorm_aflossingsvrij(self):
        assert _map_aflosvorm("aflossingsvrij") == "Aflosvrij"

    def test_map_aflosvorm_lineair(self):
        assert _map_aflosvorm("lineair") == "Lineair"

    def test_map_aflosvorm_empty(self):
        assert _map_aflosvorm("") == "Annuïteit"

    def test_map_aflosvorm_unknown(self):
        assert _map_aflosvorm("onbekend") == "Annuïteit"

    def test_is_overbrugging(self):
        assert _is_overbrugging("overbrugging") is True

    def test_is_not_overbrugging(self):
        assert _is_overbrugging("annuiteit") is False

    def test_is_overbrugging_none(self):
        assert _is_overbrugging(None) is False


# ═══════════════════════════════════════════════════════════════════════
# Leningdelen extractie
# ═══════════════════════════════════════════════════════════════════════

class TestExtractLeningdelen:
    def test_extract_count(self):
        result = _extract_leningdelen_from_dossier(INVOER_SNAPSHOT)
        assert len(result) == 3

    def test_aflosvorm_mapping(self):
        result = _extract_leningdelen_from_dossier(INVOER_SNAPSHOT)
        assert result[0].aflos_type == "Aflosvrij"
        assert result[1].aflos_type == "Annuïteit"

    def test_rente_conversion(self):
        """rentepercentage 2.8 → werkelijke_rente 0.028."""
        result = _extract_leningdelen_from_dossier(INVOER_SNAPSHOT)
        assert result[0].werkelijke_rente == pytest.approx(0.028)
        assert result[1].werkelijke_rente == pytest.approx(0.041)

    def test_overbrugging_marked(self):
        result = _extract_leningdelen_from_dossier(INVOER_SNAPSHOT)
        assert result[2].is_overbrugging is True
        assert result[0].is_overbrugging is False

    def test_bedragen(self):
        result = _extract_leningdelen_from_dossier(INVOER_SNAPSHOT)
        assert result[0].bedrag_box1 == 228000
        assert result[1].bedrag_box1 == 186300
        assert result[2].bedrag_box1 == 239000

    def test_looptijden(self):
        result = _extract_leningdelen_from_dossier(INVOER_SNAPSHOT)
        assert result[0].org_lpt == 360
        assert result[2].org_lpt == 24


# ═══════════════════════════════════════════════════════════════════════
# Volledige extractie
# ═══════════════════════════════════════════════════════════════════════

class TestExtractDossierData:
    def test_alleenstaand_false(self):
        data = extract_dossier_data(DOSSIER_SNAPSHOT, AANVRAAG_SNAPSHOT)
        assert data.alleenstaand is False

    def test_aanvrager_naam(self):
        data = extract_dossier_data(DOSSIER_SNAPSHOT, AANVRAAG_SNAPSHOT)
        assert data.aanvrager.naam == "Harry Slinger"

    def test_partner_naam(self):
        data = extract_dossier_data(DOSSIER_SNAPSHOT, AANVRAAG_SNAPSHOT)
        assert data.partner is not None
        assert data.partner.naam == "Harriette Slinger"

    def test_geboortedatum(self):
        data = extract_dossier_data(DOSSIER_SNAPSHOT, AANVRAAG_SNAPSHOT)
        assert data.aanvrager.geboortedatum == "1968-02-01"

    def test_hypotheek_bedrag_excl_overbrugging(self):
        """hypotheek_bedrag = 228.000 + 186.300 = 414.300 (excl. overbrugging)."""
        data = extract_dossier_data(DOSSIER_SNAPSHOT, AANVRAAG_SNAPSHOT)
        assert data.hypotheek_bedrag == pytest.approx(414300)

    def test_leningdelen_voor_api(self):
        """leningdelen_voor_api filtert overbrugging uit."""
        data = extract_dossier_data(DOSSIER_SNAPSHOT, AANVRAAG_SNAPSHOT)
        api_delen = data.leningdelen_voor_api
        assert len(api_delen) == 2
        assert all(not d.is_overbrugging for d in api_delen)

    def test_financiering_koopsom(self):
        data = extract_dossier_data(DOSSIER_SNAPSHOT, AANVRAAG_SNAPSHOT)
        assert data.financiering.koopsom == 635000

    def test_hypotheekverstrekker_from_aanvraag(self):
        data = extract_dossier_data(DOSSIER_SNAPSHOT, AANVRAAG_SNAPSHOT)
        assert data.financiering.hypotheekverstrekker == "ING"

    def test_nhg_from_aanvraag(self):
        data = extract_dossier_data(DOSSIER_SNAPSHOT, AANVRAAG_SNAPSHOT)
        assert data.financiering.nhg is True


class TestAlleenstaandExtractie:
    """Test met alleenstaand = True."""

    def test_alleenstaand(self):
        invoer = {
            "klantGegevens": {
                "naamAanvrager": "Jan Jansen",
                "alleenstaand": True,
                "geboortedatumAanvrager": "1990-05-15",
            },
            "_dossierScenario1": {
                "leningDelen": [{
                    "bedrag": 300000,
                    "aflossingsvorm": "annuiteit",
                    "rentepercentage": 4.5,
                    "origineleLooptijd": 360,
                    "restantLooptijd": 360,
                    "rentevastePeriode": 120,
                }],
            },
            "berekeningen": [{"aankoopsomWoning": 320000, "eigenGeld": 20000}],
        }
        dossier = {"invoer": invoer}
        data = extract_dossier_data(dossier, {})

        assert data.alleenstaand is True
        assert data.partner is None
        assert data.aanvrager.naam == "Jan Jansen"
        assert len(data.leningdelen) == 1
        assert data.leningdelen[0].werkelijke_rente == pytest.approx(0.045)
        assert data.hypotheek_bedrag == 300000


# ═══════════════════════════════════════════════════════════════════════
# Productie Supabase data format (scenario1 als aparte kolom)
# ═══════════════════════════════════════════════════════════════════════

# Gebaseerd op echte dossiers-export CSV (Bob Kakisina dossier)
PRODUCTIE_DOSSIER = {
    "id": "cb86f23a-1cc5-49c0-8e5e-8b88fa4bfcd0",
    "type": "aankoop",
    "klant_naam": "Kakisina, Bob",
    "klant_contact_gegevens": {
        "aanvrager": {
            "achternaam": "Kakisina",
            "email": "bob@example.com",
            "huisnummer": "145",
            "postcode": "9406TS",
            "telefoonnummer": "0614503175",
            "tussenvoegsel": "",
            "voornaam": "Bob",
            "straat": "Hoofdstraat",
            "woonplaats": "Assen",
        }
    },
    "invoer": {
        "berekeningen": [
            {
                "id": "ber1",
                "naam": "Berekening 1",
                "aankoopsomWoning": 475000,
                "eigenGeld": 0,
                "nhgToepassen": False,
                "woningType": "bestaande_bouw",
            },
        ],
        "haalbaarheidsBerekeningen": [
            {
                "id": "hb1",
                "naam": "Huidige situatie",
                "inkomenGegevens": {
                    "hoofdinkomenAanvrager": 55000,
                    "hoofdinkomenPartner": 35000,
                },
                "leningDelen": [
                    {
                        "aflossingsvorm": "annuiteit",
                        "bedrag": 0,
                        "bedragBox3": 0,
                        "rentepercentage": 5,
                        "origineleLooptijd": 360,
                        "restantLooptijd": 360,
                        "rentevastePeriode": 120,
                    },
                ],
            },
        ],
        "inkomenGegevens": {
            "hoofdinkomenAanvrager": 0,
            "hoofdinkomenPartner": 0,
        },
        "klantGegevens": {
            "achternaamAanvrager": "Kakisina",
            "achternaamPartner": "Kakisina",
            "alleenstaand": False,
            "geboortedatumAanvrager": "1985-03-15",
            "geboortedatumPartner": "1987-06-20",
            "naamAanvrager": "",
            "naamPartner": "",
            "roepnaamAanvrager": "Bob",
            "roepnaamPartner": "Lisa",
            "tussenvoegselAanvrager": "",
            "tussenvoegselPartner": "",
        },
    },
    # scenario1 en scenario2 zijn APARTE kolommen (niet in invoer!)
    "scenario1": {
        "id": "sc1",
        "naam": "Berekening 1",
        "leningDelen": [
            {
                "aflossingsvorm": "annuiteit",
                "bedrag": 181250,
                "bedragBox3": 0,
                "rentepercentage": 3.83,
                "origineleLooptijd": 360,
                "restantLooptijd": 360,
                "rentevastePeriode": 120,
            },
            {
                "aflossingsvorm": "aflossingsvrij",
                "bedrag": 308750,
                "bedragBox3": 0,
                "rentepercentage": 4.3,
                "origineleLooptijd": 360,
                "restantLooptijd": 24,
                "rentevastePeriode": 1,
            },
        ],
    },
    "scenario2": {
        "id": "sc2",
        "naam": "Berekening 2",
        "leningDelen": [
            {
                "aflossingsvorm": "annuiteit",
                "bedrag": 181250,
                "bedragBox3": 0,
                "rentepercentage": 3.83,
                "origineleLooptijd": 360,
                "restantLooptijd": 360,
                "rentevastePeriode": 120,
            },
        ],
    },
}

# Aanvraag met geneste data kolom (productie format)
PRODUCTIE_AANVRAAG = {
    "id": "aanvraag-prod-1",
    "dossier_id": "cb86f23a-1cc5-49c0-8e5e-8b88fa4bfcd0",
    "naam": "Aanvraag 1",
    "data": {
        "hypotheekverstrekker": "ABN AMRO",
        "nhg": False,
    },
}


class TestProductieDataFormat:
    """Test met echte Supabase productie data structuur."""

    def test_leningdelen_from_scenario1_column(self):
        """scenario1 als aparte kolom wordt correct gelezen."""
        data = extract_dossier_data(PRODUCTIE_DOSSIER, PRODUCTIE_AANVRAAG)
        assert len(data.leningdelen) == 2
        assert data.leningdelen[0].bedrag_box1 == 181250
        assert data.leningdelen[1].bedrag_box1 == 308750

    def test_leningdelen_rente_from_scenario1(self):
        data = extract_dossier_data(PRODUCTIE_DOSSIER, PRODUCTIE_AANVRAAG)
        assert data.leningdelen[0].werkelijke_rente == pytest.approx(0.0383)
        assert data.leningdelen[1].werkelijke_rente == pytest.approx(0.043)

    def test_leningdelen_aflosvorm_from_scenario1(self):
        data = extract_dossier_data(PRODUCTIE_DOSSIER, PRODUCTIE_AANVRAAG)
        assert data.leningdelen[0].aflos_type == "Annuïteit"
        assert data.leningdelen[1].aflos_type == "Aflosvrij"

    def test_hypotheek_bedrag(self):
        data = extract_dossier_data(PRODUCTIE_DOSSIER, PRODUCTIE_AANVRAAG)
        assert data.hypotheek_bedrag == pytest.approx(490000)  # 181250 + 308750

    def test_naam_composed_from_parts(self):
        """naamAanvrager is leeg → samengesteld uit roepnaam + achternaam."""
        data = extract_dossier_data(PRODUCTIE_DOSSIER, PRODUCTIE_AANVRAAG)
        assert data.aanvrager.naam == "Bob Kakisina"

    def test_partner_naam_composed(self):
        data = extract_dossier_data(PRODUCTIE_DOSSIER, PRODUCTIE_AANVRAAG)
        assert data.partner is not None
        assert data.partner.naam == "Lisa Kakisina"

    def test_alleenstaand_false_with_partner_parts(self):
        data = extract_dossier_data(PRODUCTIE_DOSSIER, PRODUCTIE_AANVRAAG)
        assert data.alleenstaand is False

    def test_aanvraag_data_nested(self):
        """hypotheekverstrekker zit in aanvraag.data (genest)."""
        data = extract_dossier_data(PRODUCTIE_DOSSIER, PRODUCTIE_AANVRAAG)
        assert data.financiering.hypotheekverstrekker == "ABN AMRO"
        assert data.financiering.nhg is False

    def test_contact_gegevens_email(self):
        """Email uit klant_contact_gegevens kolom."""
        data = extract_dossier_data(PRODUCTIE_DOSSIER, PRODUCTIE_AANVRAAG)
        assert data.aanvrager.email == "bob@example.com"

    def test_contact_gegevens_telefoon(self):
        data = extract_dossier_data(PRODUCTIE_DOSSIER, PRODUCTIE_AANVRAAG)
        assert data.aanvrager.telefoon == "0614503175"

    def test_contact_gegevens_adres(self):
        data = extract_dossier_data(PRODUCTIE_DOSSIER, PRODUCTIE_AANVRAAG)
        assert data.aanvrager.adres == "Hoofdstraat 145"

    def test_contact_gegevens_postcode_plaats(self):
        data = extract_dossier_data(PRODUCTIE_DOSSIER, PRODUCTIE_AANVRAAG)
        assert data.aanvrager.postcode_plaats == "9406TS Assen"

    def test_inkomen_from_haalbaarheidsberekeningen(self):
        """Inkomen uit haalbaarheidsBerekeningen (niet uit top-level inkomenGegevens)."""
        data = extract_dossier_data(PRODUCTIE_DOSSIER, PRODUCTIE_AANVRAAG)
        assert data.inkomen_aanvrager_huidig == 55000
        assert data.inkomen_partner_huidig == 35000

    def test_koopsom(self):
        data = extract_dossier_data(PRODUCTIE_DOSSIER, PRODUCTIE_AANVRAAG)
        assert data.financiering.koopsom == 475000

    def test_geboortedatum(self):
        data = extract_dossier_data(PRODUCTIE_DOSSIER, PRODUCTIE_AANVRAAG)
        assert data.aanvrager.geboortedatum == "1985-03-15"
        assert data.partner.geboortedatum == "1987-06-20"


class TestProductieAlleenstaand:
    """Test productie format met alleenstaand dossier."""

    def test_alleenstaand_with_empty_partner_fields(self):
        """Alleenstaand dossier waar achternaamPartner leeg is."""
        dossier = {
            "invoer": {
                "klantGegevens": {
                    "achternaamAanvrager": "Hardholt",
                    "alleenstaand": True,
                    "geboortedatumAanvrager": "1956-06-05",
                    "naamAanvrager": "Elly Hardholt",
                    "roepnaamAanvrager": "Elly",
                    "achternaamPartner": "",
                    "roepnaamPartner": "",
                },
                "berekeningen": [{"aankoopsomWoning": 250000}],
            },
            "scenario1": {
                "leningDelen": [
                    {
                        "aflossingsvorm": "aflossingsvrij",
                        "bedrag": 135000,
                        "bedragBox3": 0,
                        "rentepercentage": 5,
                        "origineleLooptijd": 360,
                        "restantLooptijd": 360,
                        "rentevastePeriode": 120,
                    },
                ],
            },
        }
        data = extract_dossier_data(dossier, {})
        assert data.alleenstaand is True
        assert data.partner is None
        assert data.aanvrager.naam == "Elly Hardholt"
        assert len(data.leningdelen) == 1
        assert data.leningdelen[0].bedrag_box1 == 135000


class TestNaamTussenvoegsel:
    """Test naam compositie met tussenvoegsel."""

    def test_naam_with_tussenvoegsel(self):
        dossier = {
            "invoer": {
                "klantGegevens": {
                    "naamAanvrager": "",
                    "roepnaamAanvrager": "Jan",
                    "tussenvoegselAanvrager": "van der",
                    "achternaamAanvrager": "Berg",
                    "alleenstaand": True,
                },
            },
            "scenario1": {"leningDelen": [
                {"bedrag": 200000, "aflossingsvorm": "annuiteit",
                 "rentepercentage": 4, "origineleLooptijd": 360,
                 "restantLooptijd": 360, "rentevastePeriode": 120},
            ]},
        }
        data = extract_dossier_data(dossier, {})
        assert data.aanvrager.naam == "Jan van der Berg"


class TestScenarioKolomPriority:
    """Test dat scenario1 kolom prioriteit heeft over invoer._dossierScenario1."""

    def test_scenario_kolom_takes_priority(self):
        """Als zowel scenario1 kolom als _dossierScenario1 bestaan,
        scenario1 kolom wint."""
        dossier = {
            "invoer": {
                "klantGegevens": {
                    "naamAanvrager": "Test",
                    "alleenstaand": True,
                },
                "_dossierScenario1": {
                    "leningDelen": [
                        {"bedrag": 100000, "aflossingsvorm": "annuiteit",
                         "rentepercentage": 5, "origineleLooptijd": 360,
                         "restantLooptijd": 360, "rentevastePeriode": 120},
                    ],
                },
            },
            "scenario1": {
                "leningDelen": [
                    {"bedrag": 250000, "aflossingsvorm": "lineair",
                     "rentepercentage": 4, "origineleLooptijd": 360,
                     "restantLooptijd": 360, "rentevastePeriode": 120},
                ],
            },
        }
        data = extract_dossier_data(dossier, {})
        # scenario1 kolom (250k lineair) moet winnen, niet _dossierScenario1 (100k)
        assert len(data.leningdelen) == 1
        assert data.leningdelen[0].bedrag_box1 == 250000
        assert data.leningdelen[0].aflos_type == "Lineair"


# ═══════════════════════════════════════════════════════════════════════
# Fix 1-5: Nieuwe extracties
# ═══════════════════════════════════════════════════════════════════════

class TestBurgerlijkeStaat:
    """Fix 1: Burgerlijke staat afleiden uit alleenstaand flag."""

    def test_stel_gehuwd(self):
        data = extract_dossier_data(DOSSIER_SNAPSHOT, AANVRAAG_SNAPSHOT)
        assert data.burgerlijke_staat == "Gehuwd"

    def test_alleenstaand(self):
        dossier = {
            "invoer": {
                "klantGegevens": {
                    "naamAanvrager": "Jan",
                    "alleenstaand": True,
                },
            },
            "scenario1": {"leningDelen": [
                {"bedrag": 200000, "aflossingsvorm": "annuiteit",
                 "rentepercentage": 4, "origineleLooptijd": 360,
                 "restantLooptijd": 360, "rentevastePeriode": 120},
            ]},
        }
        data = extract_dossier_data(dossier, {})
        assert data.burgerlijke_staat == "Alleenstaand"

    def test_explicit_value_override(self):
        dossier = {
            "invoer": {
                "klantGegevens": {
                    "naamAanvrager": "Jan",
                    "naamPartner": "Piet",
                    "alleenstaand": False,
                    "burgerlijkeStaat": "Geregistreerd partnerschap",
                },
            },
            "scenario1": {"leningDelen": [
                {"bedrag": 200000, "aflossingsvorm": "annuiteit",
                 "rentepercentage": 4, "origineleLooptijd": 360,
                 "restantLooptijd": 360, "rentevastePeriode": 120},
            ]},
        }
        data = extract_dossier_data(dossier, {})
        assert data.burgerlijke_staat == "Geregistreerd partnerschap"


class TestHuwelijkseVoorwaarden:
    """Fix 2: Huwelijkse voorwaarden extractie."""

    def test_empty_when_not_present(self):
        data = extract_dossier_data(DOSSIER_SNAPSHOT, AANVRAAG_SNAPSHOT)
        assert data.huwelijkse_voorwaarden == ""

    def test_extracted_when_present(self):
        dossier = {
            "invoer": {
                "klantGegevens": {
                    "naamAanvrager": "Jan",
                    "naamPartner": "Piet",
                    "alleenstaand": False,
                    "huwelijkseVoorwaarden": "Koude uitsluiting",
                },
            },
            "scenario1": {"leningDelen": [
                {"bedrag": 200000, "aflossingsvorm": "annuiteit",
                 "rentepercentage": 4, "origineleLooptijd": 360,
                 "restantLooptijd": 360, "rentevastePeriode": 120},
            ]},
        }
        data = extract_dossier_data(dossier, {})
        assert data.huwelijkse_voorwaarden == "Koude uitsluiting"


class TestKinderen:
    """Fix 3: Kinderen extractie."""

    def test_no_kinderen(self):
        data = extract_dossier_data(DOSSIER_SNAPSHOT, AANVRAAG_SNAPSHOT)
        assert data.kinderen == []
        assert data.heeft_kind_onder_18 is False

    def test_kinderen_as_dicts(self):
        dossier = {
            "invoer": {
                "klantGegevens": {
                    "naamAanvrager": "Jan",
                    "alleenstaand": True,
                    "kinderen": [
                        {"naam": "Emma", "geboortedatum": "2015-06-01"},
                        {"naam": "Lucas", "geboortedatum": "2020-03-15"},
                    ],
                },
            },
            "scenario1": {"leningDelen": [
                {"bedrag": 200000, "aflossingsvorm": "annuiteit",
                 "rentepercentage": 4, "origineleLooptijd": 360,
                 "restantLooptijd": 360, "rentevastePeriode": 120},
            ]},
        }
        data = extract_dossier_data(dossier, {})
        assert len(data.kinderen) == 2
        assert "Emma" in data.kinderen[0]
        assert "Lucas" in data.kinderen[1]
        assert data.heeft_kind_onder_18 is True
        assert data.geboortedatum_jongste_kind == "2020-03-15"


class TestWoningType:
    """Fix 4: Type woning extractie."""

    def test_default_bestaande_bouw(self):
        data = extract_dossier_data(DOSSIER_SNAPSHOT, AANVRAAG_SNAPSHOT)
        assert data.financiering.type_woning == "Bestaande bouw"

    def test_bestaande_bouw_from_berekeningen(self):
        data = extract_dossier_data(PRODUCTIE_DOSSIER, PRODUCTIE_AANVRAAG)
        assert data.financiering.type_woning == "Bestaande bouw"

    def test_nieuwbouw(self):
        dossier = {
            "invoer": {
                "klantGegevens": {"naamAanvrager": "Jan", "alleenstaand": True},
                "berekeningen": [{"aankoopsomWoning": 400000, "woningType": "nieuwbouw"}],
            },
            "scenario1": {"leningDelen": [
                {"bedrag": 350000, "aflossingsvorm": "annuiteit",
                 "rentepercentage": 4, "origineleLooptijd": 360,
                 "restantLooptijd": 360, "rentevastePeriode": 120},
            ]},
        }
        data = extract_dossier_data(dossier, {})
        assert data.financiering.type_woning == "Nieuwbouw"

    def test_map_woning_type_helper(self):
        assert _map_woning_type("bestaande_bouw") == "Bestaande bouw"
        assert _map_woning_type("nieuwbouw") == "Nieuwbouw"
        assert _map_woning_type("") == "Bestaande bouw"
        assert _map_woning_type("onbekend") == "Bestaande bouw"


class TestKostenKoper:
    """Fix 5: Kosten koper extractie."""

    def test_default_zero(self):
        data = extract_dossier_data(DOSSIER_SNAPSHOT, AANVRAAG_SNAPSHOT)
        assert data.financiering.kosten_koper == 0

    def test_extracted_from_berekeningen(self):
        dossier = {
            "invoer": {
                "klantGegevens": {"naamAanvrager": "Jan", "alleenstaand": True},
                "berekeningen": [{"aankoopsomWoning": 400000, "kostenKoper": 15000}],
            },
            "scenario1": {"leningDelen": [
                {"bedrag": 350000, "aflossingsvorm": "annuiteit",
                 "rentepercentage": 4, "origineleLooptijd": 360,
                 "restantLooptijd": 360, "rentevastePeriode": 120},
            ]},
        }
        data = extract_dossier_data(dossier, {})
        assert data.financiering.kosten_koper == 15000
