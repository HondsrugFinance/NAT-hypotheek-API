"""Gecentraliseerde tekst-constanten en renderers voor het adviesrapport.

Eén bron van waarheid voor alle narratieve teksten in het adviesrapport.
"""

from __future__ import annotations

from typing import TypedDict


# ============================================================================
# Type definitions
# ============================================================================

class _Outcomes(TypedDict):
    affordable: str
    resolved: str
    attention: str
    shortfall: str


class StandardScenarioText(TypedDict):
    intro: str
    outcome: _Outcomes
    advice: dict[str, str]
    nuance: dict[str, str]
    disclaimer: str


class _OverallOutcomes(TypedDict):
    affordable_for_both: str
    affordable_for_one: str
    affordable_for_none: str


class _PersonStatuses(TypedDict):
    affordable: str
    attention: str
    shortfall: str


class RelationshipScenarioText(TypedDict):
    intro: str
    overall_outcome: _OverallOutcomes
    person_status: _PersonStatuses
    advice: dict[str, str]
    disclaimer: str


# ============================================================================
# Shared text fragments
# ============================================================================

_VRAAGT_AANDACHT = "Dit vraagt aandacht."

_GEEN_MAATREGELEN = (
    "Op basis van deze berekening achten wij aanvullende maatregelen "
    "op dit moment niet noodzakelijk."
)

_RISICO_ACCEPTEREN = (
    "U heeft aangegeven dit risico te willen accepteren. "
    "Het is belangrijk dat u zich bewust bent van de mogelijke financiële gevolgen."
)

_ADVISEREN_BEOORDELEN = (
    "Wij adviseren u om te beoordelen of aanvullende maatregelen wenselijk zijn."
)

_VOORZIENINGEN_VOLDOENDE = (
    "De bestaande voorzieningen zijn echter voldoende om dit tekort op te vangen."
)

_NUANCE_PARTNER_INKOMEN = (
    "Bij deze berekening hebben wij rekening gehouden met het inkomen van de partner."
)


# ============================================================================
# Helpers
# ============================================================================

def compact_keys(*entries: tuple[str, bool]) -> list[str]:
    """Houd alleen keys waarvan de conditie truthy is.

    >>> compact_keys(("existing_orv", True), ("savings_used", False))
    ['existing_orv']
    """
    return [k for k, v in entries if v]


# ============================================================================
# Scenario renderers
# ============================================================================

def render_standard_scenario(
    text: StandardScenarioText,
    status: str,
    advice_type: str | None = None,
    nuance_keys: list[str] | None = None,
) -> list[str]:
    """Assembleer 3 paragrafen: intro | analyse (outcome+advice+nuance) | disclaimer."""
    # Analyse — outcome + advice + nuance(s) in één alinea
    analysis: list[str] = [text["outcome"][status]]

    advice = text.get("advice", {}).get(advice_type or "")
    if advice:
        analysis.append(advice)
    elif status == "attention":
        analysis.append(_ADVISEREN_BEOORDELEN)

    nuances = text.get("nuance", {})
    for key in nuance_keys or []:
        if key in nuances:
            analysis.append(nuances[key])

    result = [text["intro"], " ".join(analysis)]
    if text.get("disclaimer"):
        result.append(text["disclaimer"])
    return result


def render_relationship_scenario(
    text: RelationshipScenarioText,
    overall_status: str,
    applicant_status: str,
    partner_status: str,
) -> list[str]:
    """Assembleer: intro → overall → applicant → partner → awareness → disclaimer."""
    return [
        text["intro"],
        text["overall_outcome"][overall_status],
        text["person_status"][applicant_status],
        text["person_status"][partner_status],
        text["advice"]["awareness_only"],
        text["disclaimer"],
    ]


# ============================================================================
# Standaard scenario tekst-blokken
# ============================================================================

DEATH_TEXT: StandardScenarioText = {
    "intro": (
        "Wij hebben berekend wat de gevolgen zijn voor de betaalbaarheid "
        "van de hypotheek wanneer een van u overlijdt."
    ),
    "outcome": {
        "affordable": (
            "Wanneer een van u overlijdt blijft de hypotheek "
            "op basis van deze berekening betaalbaar."
        ),
        "resolved": (
            "Wanneer een van u overlijdt ontstaat er op basis van deze berekening "
            f"een financieel tekort. {_VOORZIENINGEN_VOLDOENDE}"
        ),
        "attention": (
            "Wanneer een van u overlijdt ontstaat er op basis van deze berekening "
            f"een beperkt financieel tekort. {_VRAAGT_AANDACHT}"
        ),
        "shortfall": (
            "Wanneer een van u overlijdt ontstaat er op basis van deze berekening "
            "een financieel tekort dat niet volledig kan worden opgevangen "
            "met de huidige voorzieningen."
        ),
    },
    "advice": {
        "no_action": _GEEN_MAATREGELEN,
        "awareness_only": _RISICO_ACCEPTEREN,
        "consider_solution": (
            "Om dit risico te beperken kan een "
            "overlijdensrisicoverzekering passend zijn."
        ),
        "advise_solution": (
            "Wij adviseren u om maatregelen te treffen om dit risico te beperken, "
            "bijvoorbeeld door een overlijdensrisicoverzekering af te sluiten "
            "of te verhogen."
        ),
    },
    "nuance": {
        "existing_orv": (
            "Bij deze berekening hebben wij rekening gehouden met de bestaande "
            "overlijdensrisicoverzekering(en)."
        ),
        "existing_life_insurance": (
            "Bij deze berekening hebben wij rekening gehouden met "
            "aanwezige levensverzekeringen."
        ),
        "savings_used": (
            "Bij deze berekening hebben wij rekening gehouden met een deel "
            "van het beschikbare spaargeld."
        ),
        "employer_provisions_unknown": (
            "Bij deze berekening hebben wij geen rekening gehouden met "
            "mogelijke voorzieningen via een werkgever."
        ),
    },
    "disclaimer": (
        "Deze berekening is gebaseerd op de gegevens die bij ons "
        "bekend zijn op het moment van advies."
    ),
}


RETIREMENT_TEXT: StandardScenarioText = {
    "intro": (
        "Wij hebben berekend hoe de betaalbaarheid van de hypotheek "
        "zich ontwikkelt wanneer u met pensioen gaat."
    ),
    "outcome": {
        "affordable": (
            "Op basis van deze berekening blijft de hypotheek "
            "ook na pensionering betaalbaar."
        ),
        "resolved": (
            "Na pensionering ontstaat er op basis van deze berekening "
            f"een financieel tekort. {_VOORZIENINGEN_VOLDOENDE}"
        ),
        "attention": (
            "Na pensionering ontstaat er op basis van deze berekening "
            f"een beperkt financieel tekort. {_VRAAGT_AANDACHT}"
        ),
        "shortfall": (
            "Na pensionering ontstaat er op basis van deze berekening "
            "een financieel tekort dat niet volledig kan worden opgevangen "
            "met de huidige voorzieningen."
        ),
    },
    "advice": {
        "no_action": _GEEN_MAATREGELEN,
        "awareness_only": _RISICO_ACCEPTEREN,
        "consider_solution": (
            "Om dit risico te beperken kan het passend zijn om extra "
            "af te lossen op de hypotheek."
        ),
        "advise_extra_repayment": (
            "Wij adviseren u om extra af te lossen op de hypotheek "
            "voor pensionering."
        ),
    },
    "nuance": {
        "couple_two_aow": (
            "Bij deze berekening hebben wij rekening gehouden met de verschillende "
            "momenten waarop u beiden de AOW-leeftijd bereikt."
        ),
        "income_decrease": (
            "Na pensionering daalt het huishoudinkomen ten opzichte "
            "van de huidige situatie."
        ),
        "later_shortfall": (
            "Wanneer ook de partner met pensioen gaat kan het tekort toenemen."
        ),
        "income_improves": (
            "Wanneer ook de partner de AOW-leeftijd bereikt kan de "
            "betaalbaarheid verbeteren."
        ),
        "annuity_income_used": (
            "Bij deze berekening hebben wij rekening gehouden met inkomen "
            "uit lijfrenteverzekeringen."
        ),
    },
    "disclaimer": (
        "Deze berekening is gebaseerd op de pensioeninformatie en "
        "fiscale regels zoals die op dit moment bekend zijn."
    ),
}


DISABILITY_TEXT: StandardScenarioText = {
    "intro": (
        "Wij hebben berekend wat de gevolgen zijn voor de betaalbaarheid "
        "van de hypotheek bij arbeidsongeschiktheid."
    ),
    "outcome": {
        "affordable": (
            "Op basis van deze berekening blijft de hypotheek "
            "ook bij arbeidsongeschiktheid betaalbaar."
        ),
        "resolved": (
            "Bij arbeidsongeschiktheid ontstaat er op basis van deze berekening "
            f"een financieel tekort. {_VOORZIENINGEN_VOLDOENDE}"
        ),
        "attention": (
            "Bij arbeidsongeschiktheid ontstaat er op basis van deze berekening "
            f"een beperkt financieel tekort. {_VRAAGT_AANDACHT}"
        ),
        "shortfall": (
            "Bij arbeidsongeschiktheid ontstaat er op basis van deze berekening "
            "een financieel tekort dat niet volledig kan worden opgevangen "
            "met de huidige voorzieningen."
        ),
    },
    "advice": {
        "no_action": _GEEN_MAATREGELEN,
        "awareness_only": _RISICO_ACCEPTEREN,
        "consider_solution": (
            "Om dit risico te beperken kan het passend zijn om "
            "aanvullende maatregelen te treffen."
        ),
        "refer_to_specialist": (
            "Wij adviseren u om te onderzoeken of aanvullende "
            "voorzieningen wenselijk zijn."
        ),
    },
    "nuance": {
        "aov_used": (
            "Bij deze berekening hebben wij rekening gehouden met de bestaande "
            "arbeidsongeschiktheidsverzekering."
        ),
        "partner_income_used": _NUANCE_PARTNER_INKOMEN,
    },
    "disclaimer": (
        "Deze berekening is gebaseerd op een indicatief scenario "
        "bij langdurige arbeidsongeschiktheid."
    ),
}


UNEMPLOYMENT_TEXT: StandardScenarioText = {
    "intro": (
        "Wij hebben berekend wat de gevolgen zijn voor de betaalbaarheid "
        "van de hypotheek bij werkloosheid."
    ),
    "outcome": {
        "affordable": (
            "Op basis van deze berekening blijft de hypotheek "
            "ook bij werkloosheid betaalbaar."
        ),
        "resolved": (
            "Bij werkloosheid ontstaat er op basis van deze berekening "
            f"een financieel tekort. {_VOORZIENINGEN_VOLDOENDE}"
        ),
        "attention": (
            "Bij werkloosheid ontstaat er op basis van deze berekening "
            f"een beperkt financieel tekort. {_VRAAGT_AANDACHT}"
        ),
        "shortfall": (
            "Bij werkloosheid ontstaat er op basis van deze berekening "
            "een financieel tekort dat niet volledig kan worden opgevangen "
            "met de huidige voorzieningen."
        ),
    },
    "advice": {
        "no_action": _GEEN_MAATREGELEN,
        "awareness_only": _RISICO_ACCEPTEREN,
        "consider_solution": (
            "Om dit risico te beperken kan het passend zijn om "
            "aanvullende maatregelen te treffen."
        ),
        "refer_to_specialist": (
            "Wij adviseren u om te onderzoeken of aanvullende "
            "voorzieningen wenselijk zijn."
        ),
    },
    "nuance": {
        "woonlastenverzekering_used": (
            "Bij deze berekening hebben wij rekening gehouden met de bestaande "
            "woonlastenverzekering."
        ),
        "partner_income_used": _NUANCE_PARTNER_INKOMEN,
    },
    "disclaimer": (
        "Deze berekening is gebaseerd op een indicatief scenario "
        "bij werkloosheid."
    ),
}


RELATIONSHIP_TEXT: RelationshipScenarioText = {
    "intro": (
        "Wij hebben indicatief berekend of de hypotheek door ieder van u "
        "afzonderlijk gedragen kan worden wanneer de relatie eindigt."
    ),
    "overall_outcome": {
        "affordable_for_both": (
            "Op basis van deze berekening lijkt de hypotheek door ieder "
            "van u afzonderlijk betaalbaar."
        ),
        "affordable_for_one": (
            "Op basis van deze berekening lijkt de hypotheek door een "
            "van u afzonderlijk betaalbaar."
        ),
        "affordable_for_none": (
            "Op basis van deze berekening lijkt de hypotheek door geen "
            "van u afzonderlijk betaalbaar."
        ),
    },
    "person_status": {
        "affordable": (
            "De hypotheek blijft op basis van deze berekening betaalbaar."
        ),
        "attention": (
            "Op basis van deze berekening ontstaat een beperkt financieel "
            f"tekort. {_VRAAGT_AANDACHT}"
        ),
        "shortfall": (
            "Op basis van deze berekening ontstaat een financieel tekort "
            "waardoor de hypotheek niet zonder meer betaalbaar is."
        ),
    },
    "advice": {
        "awareness_only": (
            "Dit scenario is bedoeld om inzicht te geven in de mogelijke "
            "gevolgen voor de betaalbaarheid van de hypotheek."
        ),
    },
    "disclaimer": (
        "Deze berekening is indicatief. Er is geen rekening gehouden met "
        "mogelijke uitkoop, alimentatie, verkoop van de woning of "
        "verdeling van vermogen."
    ),
}


DEATH_SINGLE_TEXT: str = (
    "Bij overlijden ontstaat geen financieel risico voor een partner, "
    "maar het blijft van belang dat eventuele nabestaanden of erfgenamen "
    "zich bewust zijn van de gevolgen voor de woningfinanciering."
)


# ============================================================================
# Risico-labels voor samenvatting
# ============================================================================

ADVICE_RISK_LABELS: dict[str, str] = {
    "affordable": "afgedekt",
    "resolved": "afgedekt",
    "attention": "aandachtspunt",
    "shortfall": "tekort aanwezig",
}


# ============================================================================
# Non-scenario tekst-builders
# ============================================================================

def build_summary_narratives(
    *,
    objective_label: str = "",
    property_address: str = "",
    has_partner: bool = False,
    nhg: bool = False,
    customer_priority: str = "",
) -> list[str]:
    """Bouw samenvatting-narratieven."""
    blocks: list[str] = []

    if has_partner:
        intro = f"U wilt samen een hypotheek afsluiten voor {objective_label.lower()}"
    else:
        intro = f"U wilt een hypotheek afsluiten voor {objective_label.lower()}"
    if property_address:
        intro += f" aan {property_address}"
    intro += "."
    blocks.append(intro)

    blocks.append(
        "Op basis van uw financiële situatie, uw wensen en de geldende leennormen "
        "hebben wij beoordeeld dat de geadviseerde financiering passend is binnen uw situatie."
    )

    if customer_priority:
        blocks.append(
            f"Bij het advies hebben wij nadrukkelijk rekening gehouden met uw prioriteit: "
            f"{customer_priority.lower()}."
        )

    if nhg:
        blocks.append(
            "De hypotheek wordt aangevraagd met Nationale Hypotheek Garantie."
        )

    return blocks


def build_affordability_narratives() -> list[str]:
    """Betaalbaarheid-narratieven."""
    return [
        "De maximale hypotheek is beoordeeld op basis van de geldende leennormen, "
        "het toetsinkomen en uw financiële verplichtingen.",
        "De geadviseerde maandlasten zijn getoetst aan uw situatie en passen "
        "binnen de gehanteerde normen.",
    ]


def build_loan_part_narratives(
    *,
    has_annuity: bool = False,
    has_linear: bool = False,
    has_interest_only: bool = False,
    has_box3: bool = False,
) -> list[str]:
    """Leningdelen-narratieven."""
    blocks: list[str] = []

    if has_annuity:
        blocks.append(
            "Een annuïtaire hypotheek kent een maandlast die bestaat uit rente en aflossing. "
            "Binnen de looptijd wordt de lening volledig afgelost."
        )
    if has_linear:
        blocks.append(
            "Bij een lineaire hypotheek lost u iedere maand een vast bedrag af. "
            "Daardoor daalt de schuld sneller en nemen de maandlasten in de tijd af."
        )
    if has_interest_only:
        blocks.append(
            "Bij een aflossingsvrij leningdeel betaalt u gedurende de looptijd "
            "in beginsel alleen rente en blijft de hoofdsom openstaan."
        )
    if has_box3:
        blocks.append(
            "Voor zover sprake is van een leningdeel in box 3 is de rente "
            "daarop fiscaal niet aftrekbaar als eigenwoningrente."
        )

    return blocks


def build_tax_narratives(
    *,
    qualifies_for_deduction: bool = True,
    deduction_end_year: int | None = None,
    has_equity_reserve: bool = False,
    has_box3: bool = False,
) -> list[str]:
    """Fiscale kwalificatie-narratieven."""
    blocks: list[str] = []

    if qualifies_for_deduction:
        blocks.append(
            "De leningdelen die kwalificeren als eigenwoningschuld vallen in box 1. "
            "De betaalde hypotheekrente kan fiscaal aftrekbaar zijn, voor zover "
            "aan de wettelijke voorwaarden wordt voldaan."
        )
    if deduction_end_year:
        blocks.append(
            f"Op basis van het bekende eigenwoningverleden loopt de renteaftrek "
            f"tot en met {deduction_end_year}."
        )
    if has_equity_reserve:
        blocks.append(
            "Bij het advies is rekening gehouden met een bestaande eigenwoningreserve "
            "en de mogelijke gevolgen van de bijleenregeling."
        )
    if has_box3:
        blocks.append(
            "Voor zover een leningdeel niet kwalificeert als eigenwoningschuld, "
            "valt dit fiscaal in box 3."
        )

    return blocks


def build_attention_points(
    *,
    has_rvp: bool = True,
    has_box3: bool = False,
    customer_rejected_orv: bool = False,
) -> list[str]:
    """Aandachtspunten (bullet list)."""
    items: list[str] = []

    if has_rvp:
        items.append(
            "Na afloop van de rentevaste periode kan de rente wijzigen, "
            "waardoor de maandlasten kunnen stijgen of dalen."
        )
    if has_box3:
        items.append(
            "Voor zover sprake is van een leningdeel in box 3, is de rente daarop "
            "niet aftrekbaar als eigenwoningrente."
        )
    if customer_rejected_orv:
        items.append(
            "U heeft ervoor gekozen om geen overlijdensrisicoverzekering af te sluiten. "
            "Dit betekent dat het financiële risico bij overlijden niet afzonderlijk is afgedekt."
        )

    items.append(
        "Veranderingen in uw persoonlijke of financiële situatie kunnen invloed "
        "hebben op de betaalbaarheid van de hypotheek."
    )

    return items


def build_disclaimer_narratives() -> list[str]:
    """Disclaimer-paragrafen."""
    return [
        "Dit adviesrapport is opgesteld op basis van de door u verstrekte informatie. "
        "Wij gaan ervan uit dat deze gegevens juist en volledig zijn.",
        "Het advies is een momentopname en gebaseerd op de huidige wet- en regelgeving "
        "en de op het moment van opstellen bekende uitgangspunten.",
        "De definitieve acceptatie van de hypotheek is afhankelijk van de beoordeling "
        "door de geldverstrekker.",
    ]
