"""Tests voor adviesrapport_v2.field_mapper.

Gebruikt invoer JSONB snapshots gebaseerd op de G6 diagnostiek output.
"""

import pytest
from adviesrapport_v2.field_mapper import (
    extract_dossier_data, _normalize_rente, _map_aflosvorm,
    _is_overbrugging, _extract_leningdelen, _get,
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
        result = _extract_leningdelen(INVOER_SNAPSHOT)
        assert len(result) == 3

    def test_aflosvorm_mapping(self):
        result = _extract_leningdelen(INVOER_SNAPSHOT)
        assert result[0].aflos_type == "Aflosvrij"
        assert result[1].aflos_type == "Annuïteit"

    def test_rente_conversion(self):
        """rentepercentage 2.8 → werkelijke_rente 0.028."""
        result = _extract_leningdelen(INVOER_SNAPSHOT)
        assert result[0].werkelijke_rente == pytest.approx(0.028)
        assert result[1].werkelijke_rente == pytest.approx(0.041)

    def test_overbrugging_marked(self):
        result = _extract_leningdelen(INVOER_SNAPSHOT)
        assert result[2].is_overbrugging is True
        assert result[0].is_overbrugging is False

    def test_bedragen(self):
        result = _extract_leningdelen(INVOER_SNAPSHOT)
        assert result[0].bedrag_box1 == 228000
        assert result[1].bedrag_box1 == 186300
        assert result[2].bedrag_box1 == 239000

    def test_looptijden(self):
        result = _extract_leningdelen(INVOER_SNAPSHOT)
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
