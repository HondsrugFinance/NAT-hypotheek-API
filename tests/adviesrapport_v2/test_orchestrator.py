"""Integratie tests voor report_orchestrator.

Test de volledige flow: genormaliseerde data → berekeningen → secties.
Geen Supabase nodig — we voeden direct mock dossier/aanvraag data.

Let op: WeasyPrint werkt niet op Windows (GTK ontbreekt).
We mocken pdf_generator vóór de import van report_orchestrator.
"""

import sys
from unittest.mock import MagicMock

# Mock pdf_generator zodat WeasyPrint niet geladen hoeft te worden
mock_pdf_gen = MagicMock()
mock_pdf_gen.genereer_adviesrapport_pdf = MagicMock(return_value=b"%PDF-mock")
sys.modules["pdf_generator"] = mock_pdf_gen

import pytest
from adviesrapport_v2.report_orchestrator import (
    _bereken_max_hypotheek,
    _bereken_maandlasten,
    _bepaal_scenario_checks,
    _build_pensioen_chart_data,
)
from adviesrapport_v2.field_mapper import (
    extract_dossier_data,
    NormalizedDossierData,
    NormalizedLeningdeel,
)
from adviesrapport_v2.schemas import AdviesrapportOptions
from adviesrapport_v2.section_builders.summary import build_summary_section
from adviesrapport_v2.section_builders.client_profile import build_client_profile_section
from adviesrapport_v2.section_builders.financing import build_financing_section
from adviesrapport_v2.section_builders.closing import build_closing_section


# ═══════════════════════════════════════════════════════════════════════
# Mock data (vereenvoudigd: alleenstaand, 1 leningdeel)
# ═══════════════════════════════════════════════════════════════════════

MOCK_DOSSIER = {
    "invoer": {
        "klantGegevens": {
            "naamAanvrager": "Test Gebruiker",
            "alleenstaand": True,
            "geboortedatumAanvrager": "1990-06-15",
        },
        "berekeningen": [
            {"aankoopsomWoning": 350000, "eigenGeld": 25000}
        ],
        "_dossierScenario1": {
            "leningDelen": [
                {
                    "bedrag": 325000,
                    "aflossingsvorm": "annuiteit",
                    "rentepercentage": 4.5,
                    "origineleLooptijd": 360,
                    "restantLooptijd": 360,
                    "rentevastePeriode": 120,
                }
            ],
        },
    }
}

MOCK_AANVRAAG = {
    "hypotheekverstrekker": "ING",
    "nhg": True,
}


class TestMaxHypotheek:
    def test_bereken_met_data(self):
        """Max hypotheek berekening moet een positief getal teruggeven."""
        data = extract_dossier_data(MOCK_DOSSIER, MOCK_AANVRAAG)
        # Stel inkomen handmatig in (niet in mock invoer)
        data.aanvrager.inkomen.loondienst = 80000

        max_hyp = _bereken_max_hypotheek(data)
        assert max_hyp > 0
        assert max_hyp > 200000  # Met 80k inkomen moet dit ruim > 200k zijn

    def test_zonder_leningdelen(self):
        """Zonder leningdelen moet er een fallback zijn."""
        data = extract_dossier_data(MOCK_DOSSIER, MOCK_AANVRAAG)
        data.aanvrager.inkomen.loondienst = 80000
        data.leningdelen.clear()  # Verwijder alle leningdelen

        max_hyp = _bereken_max_hypotheek(data)
        assert max_hyp > 0


class TestMaandlasten:
    def test_bereken_maandlasten(self):
        """Maandlasten berekening moet positieve waarden geven."""
        data = extract_dossier_data(MOCK_DOSSIER, MOCK_AANVRAAG)
        data.aanvrager.inkomen.loondienst = 80000
        data.financiering.woningwaarde = 350000

        bruto, netto = _bereken_maandlasten(data)
        assert bruto > 0
        assert netto > 0
        assert netto < bruto  # Netto moet lager zijn door renteaftrek

    def test_zonder_leningdelen(self):
        """Zonder leningdelen: 0, 0."""
        data = extract_dossier_data(MOCK_DOSSIER, MOCK_AANVRAAG)
        data.leningdelen.clear()

        bruto, netto = _bereken_maandlasten(data)
        assert bruto == 0
        assert netto == 0


class TestScenarioChecks:
    def test_geen_scenarios(self):
        """Bij lege scenario-lijsten krijg je alleen pensioen check."""
        data = extract_dossier_data(MOCK_DOSSIER, MOCK_AANVRAAG)
        checks = _bepaal_scenario_checks(data, 400000, [], [], [], [], 0, 0)
        # Bij lege aow_scenarios → ok (vacuously true)
        assert any(c["label"] == "Pensionering" for c in checks)

    def test_aow_warning(self):
        """Als max hypotheek < geadviseerd → warning."""
        data = extract_dossier_data(MOCK_DOSSIER, MOCK_AANVRAAG)
        aow = [{"max_hypotheek_annuitair": 200000}]  # Onder de 325k
        checks = _bepaal_scenario_checks(data, 400000, aow, [], [], [], 0, 0)
        pensioen = [c for c in checks if c["label"] == "Pensionering"][0]
        assert pensioen["status"] == "warning"


class TestSectionBuilders:
    def test_summary_section_structure(self):
        """Summary sectie moet highlights en scenario_checks bevatten."""
        data = extract_dossier_data(MOCK_DOSSIER, MOCK_AANVRAAG)
        section = build_summary_section(
            data=data,
            max_hypotheek=400000,
            netto_maandlast=1200,
            bruto_maandlast=1800,
            scenario_checks=[{"label": "Pensionering", "status": "ok"}],
        )
        assert section["id"] == "summary"
        assert len(section["highlights"]) == 4
        assert section["highlights"][0]["label"] == "Hypotheek"
        assert "€" in section["highlights"][0]["value"]

    def test_client_profile_alleenstaand(self):
        """Klantprofiel alleenstaand moet geen relatiebeëindiging tonen."""
        options = AdviesrapportOptions()
        section = build_client_profile_section(options, alleenstaand=True)
        assert section["id"] == "client-profile"
        risico_labels = [r[0] for r in section["tables"][0]["rows"]]
        assert "Relatiebeëindiging" not in risico_labels

    def test_client_profile_stel(self):
        """Klantprofiel stel moet relatiebeëindiging tonen."""
        options = AdviesrapportOptions()
        section = build_client_profile_section(options, alleenstaand=False)
        risico_labels = [r[0] for r in section["tables"][0]["rows"]]
        assert "Relatiebeëindiging" in risico_labels

    def test_financing_section(self):
        """Financiering sectie moet subsections hebben."""
        data = extract_dossier_data(MOCK_DOSSIER, MOCK_AANVRAAG)
        section = build_financing_section(data)
        assert section["id"] == "financing"
        subtitles = [s["subtitle"] for s in section["subsections"]]
        assert "Onderpand" in subtitles
        assert "Financieringsopzet" in subtitles
        assert "Hypotheekconstructie" in subtitles

    def test_closing_section(self):
        """Afsluiting sectie moet narratives hebben."""
        section = build_closing_section()
        assert section["id"] == "closing"
        assert len(section["narratives"]) >= 2


class TestPensioenChartData:
    def test_chart_data_structure(self):
        """Pensioen chart data moet jaren array en aow_markers bevatten."""
        data = extract_dossier_data(MOCK_DOSSIER, MOCK_AANVRAAG)
        aow = [{
            "max_hypotheek_annuitair": 280000,
            "max_hypotheek_niet_annuitair": 300000,
            "van_toepassing_op": "aanvrager",
            "peildatum": "2057-09-15",
        }]
        chart = _build_pensioen_chart_data(data, aow, 400000)
        assert chart is not None
        assert "jaren" in chart
        assert len(chart["jaren"]) >= 25
        assert "geadviseerd_hypotheekbedrag" in chart
        assert "aow_markers" in chart
        assert len(chart["aow_markers"]) == 1
        assert chart["aow_markers"][0]["jaar"] == 2057

    def test_chart_step_function(self):
        """Max hypotheek moet constant zijn vóór AOW, dan dalen."""
        data = extract_dossier_data(MOCK_DOSSIER, MOCK_AANVRAAG)
        aow = [{
            "max_hypotheek_annuitair": 280000,
            "max_hypotheek_niet_annuitair": 300000,
            "van_toepassing_op": "aanvrager",
            "peildatum": "2057-09-15",
        }]
        chart = _build_pensioen_chart_data(data, aow, 400000)
        # Vóór AOW: max moet gelijk zijn aan huidig (400000)
        eerste = chart["jaren"][0]["max_hypotheek"]
        assert eerste == 400000
        # Na AOW: max moet gelijk zijn aan max(280000, 300000) = 300000
        aow_idx = 2057 - chart["jaren"][0]["jaar"]
        if aow_idx < len(chart["jaren"]):
            assert chart["jaren"][aow_idx]["max_hypotheek"] == 300000

    def test_chart_restschuld_decreasing(self):
        """Restschuld moet afnemen over tijd (annuïteit)."""
        data = extract_dossier_data(MOCK_DOSSIER, MOCK_AANVRAAG)
        aow = [{
            "max_hypotheek_annuitair": 280000,
            "max_hypotheek_niet_annuitair": 300000,
            "van_toepassing_op": "aanvrager",
            "peildatum": "2057-09-15",
        }]
        chart = _build_pensioen_chart_data(data, aow, 400000)
        eerste = chart["jaren"][0]["restschuld"]
        laatste = chart["jaren"][-1]["restschuld"]
        assert eerste > laatste
