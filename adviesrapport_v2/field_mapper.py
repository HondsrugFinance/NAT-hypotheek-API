"""Field mapper: Supabase invoer JSONB → genormaliseerde Python dataclasses.

Dit is het hart van Optie B. Alle veldnaam-variaties (camelCase vs snake_case,
Lovable vs API, percentage vs decimaal) worden hier afgevangen. Als Lovable
ooit veldnamen verandert, hoeft alleen dit bestand aangepast te worden.

Bekende invoer JSONB structuur (uit G6 diagnostiek):
  invoer.klantGegevens: { naamAanvrager, naamPartner, geboortedatumAanvrager, ... }
  invoer.haalbaarheidsBerekeningen: [{ naam, inkomenKeys: [...] }]
  invoer.berekeningen: [{ naam, aankoopsomWoning, eigenGeld }]
  invoer._dossierScenario1: { leningDelen: [{ bedrag, rentepercentage, aflossingsvorm, ... }] }
  invoer._dossierScenario2: { leningDelen: [...] }
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("nat-api.adviesrapport_v2.field_mapper")

# Mapping van Lovable aflossingsvorm → API aflos_type
AFLOSVORM_MAPPING = {
    "annuiteit": "Annuïteit",
    "annuïteit": "Annuïteit",
    "annuitair": "Annuïteit",
    "lineair": "Lineair",
    "aflossingsvrij": "Aflosvrij",
    "aflosvrij": "Aflosvrij",
    "spaarhypotheek": "Spaarhypotheek",
    "spaar": "Spaarhypotheek",
}

# Aflosvorm display-namen voor PDF
AFLOSVORM_DISPLAY = {
    "Annuïteit": "Annuïteit",
    "Lineair": "Lineair",
    "Aflosvrij": "Aflossingsvrij",
    "Spaarhypotheek": "Spaarhypotheek",
}

# Aflosvormen die NIET naar de risk/calculate API gestuurd mogen worden
ONGELDIGE_API_AFLOSVORM = {"overbrugging"}


@dataclass
class NormalizedLeningdeel:
    """Eén genormaliseerd leningdeel."""
    aflos_type: str = "Annuïteit"
    bedrag_box1: float = 0
    bedrag_box3: float = 0
    werkelijke_rente: float = 0.05  # Altijd decimaal (0.041, niet 4.1)
    org_lpt: int = 360              # Maanden
    rest_lpt: int = 360
    rvp: int = 120                  # Rentevaste periode in maanden
    inleg_overig: float = 0
    is_overbrugging: bool = False

    @property
    def totaal_bedrag(self) -> float:
        return self.bedrag_box1 + self.bedrag_box3

    @property
    def aflosvorm_display(self) -> str:
        return AFLOSVORM_DISPLAY.get(self.aflos_type, self.aflos_type)

    def to_api_dict(self) -> dict:
        """Converteer naar dict voor calculator_final.calculate() of risk_scenarios."""
        return {
            "aflos_type": self.aflos_type,
            "org_lpt": self.org_lpt,
            "rest_lpt": self.rest_lpt,
            "hoofdsom_box1": self.bedrag_box1,
            "hoofdsom_box3": self.bedrag_box3,
            "rvp": self.rvp,
            "werkelijke_rente": self.werkelijke_rente,
            "inleg_overig": self.inleg_overig,
        }


@dataclass
class NormalizedInkomen:
    """Inkomen voor één persoon."""
    loondienst: float = 0
    onderneming: float = 0
    roz: float = 0
    overig: float = 0  # Lijfrente, huur, etc. (niet beïnvloed door AO)
    aow_uitkering: float = 0
    pensioen: float = 0
    partneralimentatie_ontvangen: float = 0
    partneralimentatie_betalen: float = 0

    @property
    def totaal_huidig(self) -> float:
        return (self.loondienst + self.onderneming + self.roz + self.overig
                + self.partneralimentatie_ontvangen - self.partneralimentatie_betalen)

    @property
    def totaal_aow(self) -> float:
        return self.aow_uitkering + self.pensioen + self.overig

    @property
    def hoofd_inkomen(self) -> float:
        """Hoofdinkomen = loondienst + onderneming + roz."""
        return self.loondienst + self.onderneming + self.roz


@dataclass
class NormalizedPersoon:
    """Gegevens van één persoon (aanvrager of partner)."""
    naam: str = ""
    voorletters_achternaam: str = ""
    geboortedatum: str = ""  # YYYY-MM-DD
    adres: str = ""
    postcode_plaats: str = ""
    telefoon: str = ""
    email: str = ""
    inkomen: NormalizedInkomen = field(default_factory=NormalizedInkomen)
    dienstverband: str = "Loondienst"  # Loondienst, Onderneming, ROZ


@dataclass
class NormalizedFinanciering:
    """Financieringsgegevens."""
    koopsom: float = 0
    kosten_koper: float = 0
    eigen_middelen: float = 0
    woningwaarde: float = 0
    energielabel: str = "Geen (geldig) Label"
    type_woning: str = "Bestaande bouw"
    adres: str = ""
    nhg: bool = True
    hypotheekverstrekker: str = ""


@dataclass
class NormalizedDossierData:
    """Volledig genormaliseerde dossier data — output van de field mapper."""
    # Personen
    aanvrager: NormalizedPersoon = field(default_factory=NormalizedPersoon)
    partner: Optional[NormalizedPersoon] = None
    alleenstaand: bool = True

    # Gezin
    burgerlijke_staat: str = "Alleenstaand"
    huwelijkse_voorwaarden: str = ""
    kinderen: list[str] = field(default_factory=list)
    heeft_kind_onder_18: bool = False
    geboortedatum_jongste_kind: str = ""

    # Financiering
    financiering: NormalizedFinanciering = field(default_factory=NormalizedFinanciering)

    # Leningdelen (genormaliseerd)
    leningdelen: list[NormalizedLeningdeel] = field(default_factory=list)

    # Verplichtingen
    limieten_bkr: float = 0
    studielening_maandlast: float = 0
    erfpachtcanon_per_maand: float = 0
    overige_kredieten_maandlast: float = 0

    # Berekende waarden (afgeleid)
    @property
    def hypotheek_bedrag(self) -> float:
        """Som van alle leningdelen (excl. overbrugging)."""
        return sum(
            d.totaal_bedrag for d in self.leningdelen if not d.is_overbrugging
        )

    @property
    def totale_investering(self) -> float:
        return self.financiering.koopsom + self.financiering.kosten_koper

    @property
    def leningdelen_voor_api(self) -> list[NormalizedLeningdeel]:
        """Leningdelen zonder overbrugging — geldig voor API calls."""
        return [d for d in self.leningdelen if not d.is_overbrugging]

    @property
    def inkomen_aanvrager_huidig(self) -> float:
        return self.aanvrager.inkomen.hoofd_inkomen

    @property
    def inkomen_partner_huidig(self) -> float:
        return self.partner.inkomen.hoofd_inkomen if self.partner else 0

    @property
    def inkomen_aanvrager_aow(self) -> float:
        return self.aanvrager.inkomen.totaal_aow

    @property
    def inkomen_partner_aow(self) -> float:
        return self.partner.inkomen.totaal_aow if self.partner else 0


def _get(d: dict, *keys, default=None):
    """Haal een waarde op uit een dict, probeer meerdere keys."""
    for key in keys:
        val = d.get(key)
        if val is not None:
            return val
    return default


def _to_float(val, default: float = 0) -> float:
    """Veilig naar float converteren."""
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _normalize_rente(val) -> float:
    """Normaliseer rente naar decimaal. 4.1 → 0.041, 0.041 → 0.041."""
    f = _to_float(val, 0.05)
    if f > 1:
        return f / 100
    return f


def _map_aflosvorm(raw: str) -> str:
    """Map Lovable aflosvorm naar API-formaat. 'annuiteit' → 'Annuïteit'."""
    if not raw:
        return "Annuïteit"
    key = raw.lower().strip()
    return AFLOSVORM_MAPPING.get(key, "Annuïteit")


def _is_overbrugging(raw_aflosvorm: str) -> bool:
    """Check of dit een overbruggingskrediet is."""
    return (raw_aflosvorm or "").lower().strip() in ONGELDIGE_API_AFLOSVORM


def _extract_leningdelen(invoer: dict) -> list[NormalizedLeningdeel]:
    """Extraheer en normaliseer leningdelen uit invoer JSONB.

    Bekende paden:
    - invoer._dossierScenario1.leningDelen (Lovable standaard, camelCase)
    - invoer.scenarios[0].leningdelen
    - invoer.leningdelen
    """
    # Probeer meerdere paden
    dossier_scenario = _get(invoer, "_dossierScenario1", "_dossierScenario") or {}
    raw_delen = (
        _get(dossier_scenario, "leningDelen", "leningdelen")
        or _get(invoer, "leningdelen", "hypotheekDelen", "hypotheek_delen")
        or []
    )

    # Fallback: scenarios array
    if not raw_delen:
        scenarios = _get(invoer, "scenarios") or []
        if scenarios and isinstance(scenarios, list):
            raw_delen = _get(scenarios[0], "leningdelen", "leningDelen") or []

    if not raw_delen:
        logger.warning("Geen leningdelen gevonden in invoer")
        return []

    logger.info("Gevonden: %d leningdelen", len(raw_delen))

    result = []
    for deel in raw_delen:
        raw_aflosvorm = _get(deel, "aflossingsvorm", "aflos_type", "aflosvorm") or ""
        rente_raw = _get(deel, "rentepercentage", "rente", "werkelijkeRente",
                         "werkelijke_rente")

        ld = NormalizedLeningdeel(
            aflos_type=_map_aflosvorm(raw_aflosvorm),
            bedrag_box1=_to_float(_get(deel, "bedrag", "bedragBox1", "hoofdsomBox1",
                                       "hoofdsom_box1")),
            bedrag_box3=_to_float(_get(deel, "bedragBox3", "hoofdsomBox3",
                                       "hoofdsom_box3")),
            werkelijke_rente=_normalize_rente(rente_raw),
            org_lpt=int(_to_float(_get(deel, "origineleLooptijd", "looptijd",
                                       "org_lpt"), 360)),
            rest_lpt=int(_to_float(_get(deel, "restantLooptijd", "restLooptijd",
                                        "rest_lpt",
                                        "origineleLooptijd"), 360)),
            rvp=int(_to_float(_get(deel, "rentevastePeriode", "rvp"), 120)),
            inleg_overig=_to_float(_get(deel, "inleg", "inlegOverig",
                                        "inleg_overig")),
            is_overbrugging=_is_overbrugging(raw_aflosvorm),
        )
        result.append(ld)

    return result


def _extract_inkomen(invoer: dict, suffix: str = "Aanvrager") -> NormalizedInkomen:
    """Extraheer inkomen voor aanvrager of partner.

    Zoekt in meerdere paden:
    - invoer.haalbaarheidsBerekeningen[0].inkomenKeys → niet de waarden!
    - invoer.klantGegevens.hoofdinkomenAanvrager
    - invoer.inkomen.hoofd_inkomen_aanvrager
    - invoer.hoofd_inkomen_aanvrager (direct op invoer)
    """
    klant = _get(invoer, "klantGegevens", "klant") or {}
    haalb = (_get(invoer, "haalbaarheidsBerekeningen") or [{}])[0] if _get(invoer, "haalbaarheidsBerekeningen") else {}
    ink_obj = _get(haalb, "inkomenGegevens", "inkomen") or _get(invoer, "inkomenGegevens", "inkomen") or {}

    suffix_lower = suffix.lower()
    suffix_camel = suffix  # "Aanvrager" of "Partner"

    # Hoofdinkomen (loondienst + onderneming + roz)
    hoofd = _to_float(
        _get(ink_obj, f"hoofdinkomen{suffix_camel}", f"hoofd_inkomen_{suffix_lower}")
        or _get(klant, f"hoofdinkomen{suffix_camel}", f"hoofd_inkomen_{suffix_lower}")
        or _get(invoer, f"hoofd_inkomen_{suffix_lower}", f"hoofdinkomen{suffix_camel}")
        or _get(haalb, f"hoofd_inkomen_{suffix_lower}")
    )

    # AOW inkomen
    aow = _to_float(
        _get(ink_obj, f"aowUitkering{suffix_camel}", f"aow_uitkering_{suffix_lower}")
        or _get(klant, f"aowUitkering{suffix_camel}")
        or _get(invoer, f"inkomen_{suffix_lower}_aow", f"inkomenAow{suffix_camel}")
    )

    pensioen = _to_float(
        _get(ink_obj, f"pensioen{suffix_camel}", f"pensioen_{suffix_lower}")
        or _get(klant, f"pensioen{suffix_camel}")
        or _get(invoer, f"pensioen_{suffix_lower}")
    )

    # Lijfrente, huur, etc.
    lijfrente = _to_float(
        _get(ink_obj, f"inkomenUitLijfrente{suffix_camel}",
             f"inkomen_uit_lijfrente_{suffix_lower}")
        or _get(invoer, f"inkomen_uit_lijfrente_{suffix_lower}")
    )

    huur = _to_float(
        _get(ink_obj, f"huurinkomsten{suffix_camel}",
             f"huurinkomsten_{suffix_lower}")
        or _get(invoer, f"huurinkomsten_{suffix_lower}")
    )

    alim_ontv = _to_float(
        _get(ink_obj, f"partneralimentatieOntvangen{suffix_camel}",
             f"ontvangen_partneralimentatie_{suffix_lower}")
        or _get(invoer, f"ontvangen_partneralimentatie_{suffix_lower}")
    )

    alim_bet = _to_float(
        _get(ink_obj, f"partneralimentatieBetalen{suffix_camel}",
             f"te_betalen_partneralimentatie_{suffix_lower}")
        or _get(invoer, f"te_betalen_partneralimentatie_{suffix_lower}")
    )

    # Dienstverband (bepaalt loondienst vs onderneming vs roz)
    dienstverband = (
        _get(ink_obj, f"typeDienstverband{suffix_camel}",
             f"dienstverband_{suffix_lower}")
        or _get(klant, f"typeDienstverband{suffix_camel}")
        or _get(invoer, f"dienstverband_{suffix_lower}")
        or "Loondienst"
    )

    # Verdeel hoofdinkomen over loondienst/onderneming/roz
    inkomen = NormalizedInkomen(
        aow_uitkering=aow,
        pensioen=pensioen,
        partneralimentatie_ontvangen=alim_ontv,
        partneralimentatie_betalen=alim_bet,
        overig=lijfrente + huur,
    )

    dienstverband_lower = dienstverband.lower() if dienstverband else "loondienst"
    if "onderneming" in dienstverband_lower:
        inkomen.onderneming = hoofd
    elif "roz" in dienstverband_lower:
        inkomen.roz = hoofd
    else:
        inkomen.loondienst = hoofd

    return inkomen


def _extract_persoon(invoer: dict, suffix: str = "Aanvrager") -> NormalizedPersoon:
    """Extraheer persoonsgegevens voor aanvrager of partner."""
    klant = _get(invoer, "klantGegevens", "klant") or {}
    suffix_camel = suffix
    suffix_lower = suffix.lower()

    naam = str(
        _get(klant, f"naam{suffix_camel}", f"naam_{suffix_lower}")
        or ""
    )
    geboortedatum = str(
        _get(klant, f"geboortedatum{suffix_camel}", f"geboortedatum_{suffix_lower}")
        or ""
    )
    adres = str(_get(klant, f"adres{suffix_camel}", "adres") or "")
    postcode_plaats = str(_get(klant, f"postcodePlaats{suffix_camel}", "postcodePlaats") or "")
    telefoon = str(_get(klant, f"telefoon{suffix_camel}", "telefoon") or "")
    email = str(_get(klant, f"email{suffix_camel}", "email") or "")

    inkomen = _extract_inkomen(invoer, suffix)

    # Dienstverband
    ink_obj = {}
    haalb_list = _get(invoer, "haalbaarheidsBerekeningen")
    if haalb_list and isinstance(haalb_list, list) and len(haalb_list) > 0:
        ink_obj = _get(haalb_list[0], "inkomenGegevens", "inkomen") or {}
    dienstverband = (
        _get(ink_obj, f"typeDienstverband{suffix_camel}")
        or _get(klant, f"typeDienstverband{suffix_camel}")
        or _get(invoer, f"dienstverband_{suffix_lower}")
        or "Loondienst"
    )

    # Voorletters + achternaam: probeer uit naam te halen
    voorletters = ""
    if naam:
        parts = naam.split()
        if len(parts) >= 2:
            voorletters = f"{parts[0][0]}. {' '.join(parts[1:])}"
        else:
            voorletters = naam

    return NormalizedPersoon(
        naam=naam,
        voorletters_achternaam=voorletters,
        geboortedatum=geboortedatum,
        adres=adres,
        postcode_plaats=postcode_plaats,
        telefoon=telefoon,
        email=email,
        inkomen=inkomen,
        dienstverband=dienstverband,
    )


def _extract_financiering(invoer: dict) -> NormalizedFinanciering:
    """Extraheer financieringsgegevens uit invoer JSONB."""
    # berekeningen[0] = eerste scenario (bijv. "Bij tijdelijk twee woningen")
    ber_list = _get(invoer, "berekeningen") or []
    ber = ber_list[0] if ber_list else {}

    klant = _get(invoer, "klantGegevens", "klant") or {}
    fin = _get(invoer, "financiering", "financieringInput") or {}

    koopsom = _to_float(
        _get(ber, "aankoopsomWoning", "koopsom", "aankoopsom")
        or _get(fin, "koopsom", "aankoopsomWoning")
        or _get(invoer, "aankoopsomWoning", "koopsom")
    )
    eigen_geld = _to_float(
        _get(ber, "eigenGeld", "eigenMiddelen", "eigen_middelen")
        or _get(fin, "eigenGeld", "eigenMiddelen")
        or _get(invoer, "eigenGeld", "eigenMiddelen")
    )
    woningwaarde = _to_float(
        _get(ber, "woningwaarde", "marktwaarde")
        or _get(fin, "woningwaarde", "marktwaarde")
        or _get(invoer, "woningwaarde")
    ) or koopsom  # Fallback naar koopsom

    energielabel = str(
        _get(ber, "energielabel")
        or _get(invoer, "energielabel")
        or _get(klant, "energielabel")
        or "Geen (geldig) Label"
    )

    adres = str(
        _get(ber, "adres", "adresWoning")
        or _get(invoer, "adresWoning", "onderpandAdres")
        or _get(klant, "adresWoning")
        or ""
    )

    return NormalizedFinanciering(
        koopsom=koopsom,
        kosten_koper=0,  # Wordt berekend door orchestrator
        eigen_middelen=eigen_geld,
        woningwaarde=woningwaarde,
        energielabel=energielabel,
        adres=adres,
    )


def extract_dossier_data(
    dossier: dict,
    aanvraag: dict,
) -> NormalizedDossierData:
    """Hoofdfunctie: Supabase dossier + aanvraag → NormalizedDossierData.

    Args:
        dossier: Volledige rij uit Supabase `dossiers` tabel
        aanvraag: Volledige rij uit Supabase `aanvragen` tabel

    Returns:
        NormalizedDossierData met alle velden genormaliseerd.
    """
    # De `invoer` JSONB zit op het dossier
    invoer = dossier.get("invoer") or dossier
    logger.info("Invoer keys: %s", list(invoer.keys()) if isinstance(invoer, dict) else "niet-dict")

    klant = _get(invoer, "klantGegevens", "klant") or {}

    # Alleenstaand?
    alleenstaand_raw = _get(klant, "alleenstaand", "is_alleenstaand")
    if isinstance(alleenstaand_raw, bool):
        alleenstaand = alleenstaand_raw
    elif isinstance(alleenstaand_raw, str):
        alleenstaand = alleenstaand_raw.lower() in ("true", "ja", "yes", "1")
    else:
        # Fallback: check of er partnergegevens zijn
        alleenstaand = not bool(_get(klant, "naamPartner", "naam_partner"))

    # Personen
    aanvrager = _extract_persoon(invoer, "Aanvrager")
    partner = None
    if not alleenstaand:
        partner = _extract_persoon(invoer, "Partner")

    # Leningdelen
    leningdelen = _extract_leningdelen(invoer)

    # Financiering
    financiering = _extract_financiering(invoer)

    # Aanvraag-data kan extra info bevatten
    if aanvraag:
        financiering.hypotheekverstrekker = str(
            _get(aanvraag, "hypotheekverstrekker", "geldverstrekker") or ""
        )
        nhg_raw = _get(aanvraag, "nhg", "met_nhg")
        if nhg_raw is not None:
            financiering.nhg = bool(nhg_raw)

    # Verplichtingen
    verplichtingen = _get(invoer, "verplichtingen", "financieleVerplichtingen") or {}
    limieten_bkr = _to_float(
        _get(verplichtingen, "limietenBkr", "limieten_bkr_geregistreerd", "limieten")
        or _get(invoer, "limieten_bkr_geregistreerd", "limietenBkr")
    )
    studielening = _to_float(
        _get(verplichtingen, "studielening", "studievoorschot_studielening")
        or _get(invoer, "studievoorschot_studielening", "studielening")
    )
    erfpacht = _to_float(
        _get(verplichtingen, "erfpachtcanon", "erfpachtcanon_per_jaar", "erfpacht")
        or _get(invoer, "erfpachtcanon_per_jaar", "erfpachtcanon")
    )
    overig_krediet = _to_float(
        _get(verplichtingen, "overigeKredieten", "jaarlast_overige_kredieten")
        or _get(invoer, "jaarlast_overige_kredieten", "overigeKredieten")
    )

    data = NormalizedDossierData(
        aanvrager=aanvrager,
        partner=partner,
        alleenstaand=alleenstaand,
        financiering=financiering,
        leningdelen=leningdelen,
        limieten_bkr=limieten_bkr,
        studielening_maandlast=studielening,
        erfpachtcanon_per_maand=erfpacht,
        overige_kredieten_maandlast=overig_krediet,
    )

    logger.info(
        "Dossier genormaliseerd: alleenstaand=%s, leningdelen=%d, hypotheek=%.0f",
        alleenstaand, len(leningdelen), data.hypotheek_bedrag,
    )

    return data
