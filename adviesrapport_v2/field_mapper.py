"""Field mapper: Supabase dossier/aanvraag → genormaliseerde Python dataclasses.

Dit is het hart van Optie B. Alle veldnaam-variaties (camelCase vs snake_case,
Lovable vs API, percentage vs decimaal) worden hier afgevangen. Als Lovable
ooit veldnamen verandert, hoeft alleen dit bestand aangepast te worden.

Supabase tabelstructuur (productie):
  dossiers tabel:
    invoer (JSONB):
      klantGegevens: { naamAanvrager, roepnaamAanvrager, achternaamAanvrager, ... }
      haalbaarheidsBerekeningen: [{ naam, inkomenGegevens: {...}, onderpand: {...}, leningDelen: [...] }]
      berekeningen: [{ naam, aankoopsomWoning, eigenGeld, ... }]
      inkomenGegevens: { hoofdinkomenAanvrager, ... }
    scenario1 (JSON): { id, naam, leningDelen: [...] }  ← aparte kolom!
    klant_contact_gegevens (JSONB): { aanvrager: { voornaam, achternaam, email, ... } }

  aanvragen tabel:
    data (JSON):  ← PRIMAIRE BRON voor alle data!
      aanvrager: { persoon: {...}, adresContact: {...}, werkgever: {...} }
      partner: { persoon: {...}, adresContact: {...}, werkgever: {...} }
      inkomenAanvrager: [{ type, jaarbedrag, isAOW, soort, ... }]
      inkomenPartner: [{ type, jaarbedrag, isAOW, soort, ... }]
      onderpand: { straat, postcode, woonplaats, marktwaarde, energielabel, ... }
      financieringsopzet: { aankoopsomWoning, eigenGeld, verbouwing, ... }
      samenstellenHypotheek: { geldverstrekker, nhg, nieuweLeningdelen, meenemenLeningdelen }
      verplichtingen: [{ type, maandbedrag, ... }]
      kinderen: [{ roepnaam, achternaam, geboortedatum }]
      burgerlijkeStaat, samenlevingsvorm, doelstelling, heeftPartner
      voorzieningen: { verzekeringen: [...] }
      vermogenSectie: { items: [...] }
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
class NormalizedVerzekering:
    """Eén verzekering (ORV, AOV, etc.)."""
    type: str = ""           # "overlijdensrisicoverzekering", "arbeidsongeschiktheid", etc.
    aanbieder: str = ""
    polisnummer: str = ""
    verzekerde: str = ""     # "aanvrager", "partner", "beiden"
    dekking: float = 0       # Jaarlijks of eenmalig uitkeringsbedrag
    soort_dekking: str = ""  # "gelijkblijvend", "annuïtair", etc.
    einddatum: str = ""      # YYYY-MM-DD

    @property
    def type_display(self) -> str:
        """Leesbare weergave van verzekering type."""
        mapping = {
            "overlijdensrisicoverzekering": "ORV",
            "arbeidsongeschiktheidsverzekering": "AOV",
            "arbeidsongeschiktheid": "AOV",
            "woonlastenverzekering": "Woonlastenverzekering",
        }
        return mapping.get(self.type.lower(), self.type.capitalize())


@dataclass
class NormalizedVermogensItem:
    """Eén vermogenspost (spaargeld, schenking, etc.)."""
    type: str = ""           # "spaargeld", "schenking", "belegging", etc.
    saldo: float = 0
    eigenaar: str = ""       # "aanvrager", "partner", "gezamenlijk"
    maatschappij: str = ""   # Bank/instelling

    @property
    def type_display(self) -> str:
        return self.type.replace("_", " ").capitalize() if self.type else "Overig"


@dataclass
class NormalizedBestaandeWoning:
    """Gegevens van een bestaande woning."""
    adres: str = ""
    postcode_plaats: str = ""
    type_woning: str = ""
    marktwaarde: float = 0
    woz_waarde: float = 0
    status: str = ""         # "verkopen", "verhuren", "aanhouden", etc.
    erfpacht: bool = False
    energielabel: str = ""


@dataclass
class NormalizedBestaandeHypotheek:
    """Gegevens van een bestaande hypotheek."""
    verstrekker: str = ""
    nhg: bool = False
    hoofdsom: float = 0
    restschuld: float = 0
    leningdelen: list = field(default_factory=list)
    # Leningdelen: [{bedrag, rente, aflosvorm, looptijd, rentevast, ingangsdatum}]


@dataclass
class NormalizedWerkgever:
    """Werkgevergegevens."""
    naam: str = ""
    dienstverband: str = ""  # "vast", "tijdelijk", etc.
    datum_in_dienst: str = ""


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
    # Individuele kostenposten (voor gedetailleerde weergave)
    overdrachtsbelasting: float = 0
    notariskosten: float = 0       # hypotheekakte + transportakte
    taxatiekosten: float = 0
    advies_bemiddeling: float = 0
    nhg_kosten: float = 0
    bankgarantie: float = 0
    verbouwing: float = 0
    ebv_ebb: float = 0             # Energiebesparende voorzieningen/budget
    overbrugging: float = 0        # Overbruggingskrediet bedrag


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
    verplichtingen_details: list = field(default_factory=list)  # [{type, maandbedrag, saldo, omschrijving}]

    # Verzekeringen, vermogen, woningen, hypotheken
    verzekeringen: list[NormalizedVerzekering] = field(default_factory=list)
    vermogen: list[NormalizedVermogensItem] = field(default_factory=list)
    bestaande_woningen: list[NormalizedBestaandeWoning] = field(default_factory=list)
    bestaande_hypotheken: list[NormalizedBestaandeHypotheek] = field(default_factory=list)

    # Werkgever per persoon
    werkgever_aanvrager: Optional[NormalizedWerkgever] = None
    werkgever_partner: Optional[NormalizedWerkgever] = None

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


# ─── Utility helpers ───

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


# Woning type mapping
WONING_TYPE_MAPPING = {
    "bestaande_bouw": "Bestaande bouw",
    "bestaandebouw": "Bestaande bouw",
    "bestaande bouw": "Bestaande bouw",
    "nieuwbouw": "Nieuwbouw",
    "nieuw_bouw": "Nieuwbouw",
}

# Samenlevingsvorm mapping
SAMENLEVINGSVORM_MAPPING = {
    "beperkte_gemeenschap": "Beperkte gemeenschap van goederen",
    "gemeenschap_van_goederen": "Gemeenschap van goederen",
    "huwelijkse_voorwaarden": "Huwelijkse voorwaarden",
    "geregistreerd_partnerschap": "Geregistreerd partnerschap",
    "samenwonend": "Samenwonend",
}


def _map_woning_type(raw: str) -> str:
    """Map woning type naar display-naam. 'bestaande_bouw' → 'Bestaande bouw'."""
    if not raw:
        return "Bestaande bouw"
    return WONING_TYPE_MAPPING.get(raw, "Bestaande bouw")


# ─── Aanvraag-based extraction (PRIMAIRE BRON) ───

def _extract_inkomen_from_aanvraag(items: list) -> NormalizedInkomen:
    """Extraheer inkomen uit aanvraag.data.inkomenAanvrager/inkomenPartner array.

    Structuur per item: { type, soort, jaarbedrag, isAOW, loondienst: { dienstverband: {...} } }
    Types: "loondienst", "uitkering" (met isAOW), "pensioen", "ander_inkomen"
    """
    loondienst = 0
    onderneming = 0
    roz = 0
    aow = 0
    pensioen = 0
    overig = 0
    dienstverband = "Loondienst"

    for item in (items or []):
        item_type = str(item.get("type", "")).lower()
        jaarbedrag = _to_float(item.get("jaarbedrag"))

        if item_type == "loondienst":
            # Bepaal dienstverband type
            ld_data = item.get("loondienst") or {}
            dv_data = ld_data.get("dienstverband") or {}
            soort_dv = str(dv_data.get("soortDienstverband", "")).lower()

            if "onderneming" in soort_dv or "zelfstandig" in soort_dv:
                onderneming += jaarbedrag
                dienstverband = "Onderneming"
            elif "roz" in soort_dv:
                roz += jaarbedrag
                dienstverband = "ROZ"
            else:
                loondienst += jaarbedrag
                dienstverband = "Loondienst"

        elif item_type == "uitkering":
            if item.get("isAOW"):
                aow += jaarbedrag
            else:
                overig += jaarbedrag

        elif item_type == "pensioen":
            pensioen += jaarbedrag

        elif item_type == "ander_inkomen":
            overig += _to_float(
                item.get("jaarbedrag")
                or _get(item.get("anderInkomenData") or {},
                        "jaarlijksBrutoInkomen")
            )

    inkomen = NormalizedInkomen(
        loondienst=loondienst,
        onderneming=onderneming,
        roz=roz,
        aow_uitkering=aow,
        pensioen=pensioen,
        overig=overig,
    )

    logger.debug(
        "Inkomen (aanvraag): loondienst=%.0f, onderneming=%.0f, aow=%.0f, "
        "pensioen=%.0f, overig=%.0f, dienstverband=%s",
        loondienst, onderneming, aow, pensioen, overig, dienstverband,
    )
    return inkomen


def _extract_persoon_from_aanvraag(
    aanvraag_data: dict,
    role: str,
    inkomen_items: list,
) -> NormalizedPersoon:
    """Extraheer persoonsgegevens uit aanvraag.data.

    Args:
        aanvraag_data: aanvraag.data dict
        role: "aanvrager" of "partner"
        inkomen_items: aanvraag.data.inkomenAanvrager of inkomenPartner array
    """
    persoon_data = (aanvraag_data.get(role) or {})
    persoon = persoon_data.get("persoon") or {}
    adres_contact = persoon_data.get("adresContact") or {}

    # Naam
    roepnaam = str(persoon.get("roepnaam") or "").strip()
    tussenvoegsel = str(persoon.get("tussenvoegsel") or "").strip()
    achternaam = str(persoon.get("achternaam") or "").strip()
    parts = [p for p in [roepnaam, tussenvoegsel, achternaam] if p]
    naam = " ".join(parts)

    # Voorletters
    voorletters = str(persoon.get("voorletters") or "").strip()
    voorletters_achternaam = ""
    if voorletters and achternaam:
        tv = f" {tussenvoegsel}" if tussenvoegsel else ""
        voorletters_achternaam = f"{voorletters}{tv} {achternaam}"
    elif naam:
        p = naam.split()
        voorletters_achternaam = f"{p[0][0]}. {' '.join(p[1:])}" if len(p) >= 2 else naam

    geboortedatum = str(persoon.get("geboortedatum") or "")

    # Adres
    straat = str(adres_contact.get("straat") or "")
    huisnr = str(adres_contact.get("huisnummer") or "")
    toev = str(adres_contact.get("toevoeging") or "").strip()
    adres = f"{straat} {huisnr}".strip()
    if toev:
        adres = f"{adres}{toev}"

    postcode = str(adres_contact.get("postcode") or "")
    woonplaats = str(adres_contact.get("woonplaats") or "")
    postcode_plaats = f"{postcode} {woonplaats}".strip()

    telefoon = str(adres_contact.get("telefoonnummer") or "")
    email = str(adres_contact.get("email") or "")

    # Inkomen uit array
    inkomen = _extract_inkomen_from_aanvraag(inkomen_items)

    # Dienstverband uit loondienst items
    dienstverband = "Loondienst"
    for item in (inkomen_items or []):
        if str(item.get("type", "")).lower() == "loondienst":
            ld_data = item.get("loondienst") or {}
            dv_data = ld_data.get("dienstverband") or {}
            soort = str(dv_data.get("soortDienstverband", "")).lower()
            if "onderneming" in soort:
                dienstverband = "Onderneming"
            elif "roz" in soort:
                dienstverband = "ROZ"
            break

    return NormalizedPersoon(
        naam=naam,
        voorletters_achternaam=voorletters_achternaam,
        geboortedatum=geboortedatum,
        adres=adres,
        postcode_plaats=postcode_plaats,
        telefoon=telefoon,
        email=email,
        inkomen=inkomen,
        dienstverband=dienstverband,
    )


def _extract_financiering_from_aanvraag(aanvraag_data: dict) -> NormalizedFinanciering:
    """Extraheer financiering uit aanvraag.data.financieringsopzet + onderpand."""
    fin = aanvraag_data.get("financieringsopzet") or {}
    onderpand = aanvraag_data.get("onderpand") or {}
    samenstellen = aanvraag_data.get("samenstellenHypotheek") or {}

    koopsom = _to_float(fin.get("aankoopsomWoning"))
    eigen_geld = _to_float(fin.get("eigenGeld"))

    # Individuele kostenposten
    overdrachtsbelasting = _to_float(fin.get("overdrachtsbelasting"))
    bankgarantie = _to_float(fin.get("bankgarantie"))
    hypotheekakte = _to_float(fin.get("hypotheekakte"))
    transportakte = _to_float(fin.get("transportakte"))
    taxatiekosten = _to_float(fin.get("taxatiekosten"))
    advies_bemiddeling = _to_float(fin.get("adviesBemiddeling"))
    nhg_kosten = _to_float(fin.get("nhgKosten"))
    verbouwing = _to_float(fin.get("verbouwing"))
    ebv_ebb = _to_float(fin.get("ebvEbb") or fin.get("energiebesparendBudget"))

    notariskosten = hypotheekakte + transportakte
    kosten_koper = (
        overdrachtsbelasting + bankgarantie + notariskosten
        + taxatiekosten + advies_bemiddeling + nhg_kosten
    )

    # Woningwaarde uit onderpand (marktwaarde)
    woningwaarde = _to_float(onderpand.get("marktwaarde")) or koopsom

    # Energielabel uit onderpand
    energielabel = str(onderpand.get("energielabel") or "Geen (geldig) Label")

    # Type woning
    woning_type_raw = str(fin.get("woningType") or "").lower().strip()
    type_woning = _map_woning_type(woning_type_raw)

    # Onderpand adres
    straat = str(onderpand.get("straat") or "")
    postcode = str(onderpand.get("postcode") or "")
    woonplaats = str(onderpand.get("woonplaats") or "")
    adres = f"{straat}, {postcode} {woonplaats}".strip(", ")

    # Hypotheekverstrekker + NHG
    hypotheekverstrekker = str(samenstellen.get("geldverstrekker") or "")
    nhg = bool(samenstellen.get("nhg", True))

    logger.debug(
        "Financiering (aanvraag): koopsom=%.0f, woningwaarde=%.0f, eigen_geld=%.0f, "
        "kosten_koper=%.0f, energielabel=%s, adres=%s, verstrekker=%s",
        koopsom, woningwaarde, eigen_geld, kosten_koper, energielabel,
        adres or "(leeg)", hypotheekverstrekker,
    )

    # Overbrugging: zoek in leningdelen
    overbrugging = _to_float(fin.get("overbrugging"))

    return NormalizedFinanciering(
        koopsom=koopsom,
        kosten_koper=kosten_koper,
        eigen_middelen=eigen_geld,
        woningwaarde=woningwaarde,
        energielabel=energielabel,
        type_woning=type_woning,
        adres=adres,
        nhg=nhg,
        hypotheekverstrekker=hypotheekverstrekker,
        overdrachtsbelasting=overdrachtsbelasting,
        notariskosten=notariskosten,
        taxatiekosten=taxatiekosten,
        advies_bemiddeling=advies_bemiddeling,
        nhg_kosten=nhg_kosten,
        bankgarantie=bankgarantie,
        verbouwing=verbouwing,
        ebv_ebb=ebv_ebb,
        overbrugging=overbrugging,
    )


def _extract_leningdelen_from_aanvraag(aanvraag_data: dict) -> list[NormalizedLeningdeel]:
    """Extraheer leningdelen uit aanvraag.data.samenstellenHypotheek.

    Combineert meenemenLeningdelen (bestaande) + nieuweLeningdelen.
    Structuur per deel: { bedrag, aflosvorm, rentePercentage, looptijd, box, renteVastPeriode }
    """
    samenstellen = aanvraag_data.get("samenstellenHypotheek") or {}
    meenemen = samenstellen.get("meenemenLeningdelen") or []
    nieuw = samenstellen.get("nieuweLeningdelen") or []

    alle_delen = meenemen + nieuw

    if not alle_delen:
        return []

    logger.info("Leningdelen (aanvraag): %d meenemen + %d nieuw = %d",
                len(meenemen), len(nieuw), len(alle_delen))

    result = []
    for deel in alle_delen:
        raw_aflosvorm = str(deel.get("aflosvorm") or "annuiteit")
        rente_raw = deel.get("rentePercentage") or deel.get("rentepercentage")
        looptijd = int(_to_float(deel.get("looptijd"), 360))

        # RVP: renteVastPeriode is in jaren in aanvraag
        rvp_jaren = _to_float(deel.get("renteVastPeriode") or deel.get("rentevastePeriode"))
        rvp_maanden = int(rvp_jaren * 12) if rvp_jaren else 120

        # Box: "box1" of "box3"
        box_raw = str(deel.get("box") or "box1").lower()
        is_box3 = "3" in box_raw
        bedrag = _to_float(deel.get("bedrag"))

        ld = NormalizedLeningdeel(
            aflos_type=_map_aflosvorm(raw_aflosvorm),
            bedrag_box1=0 if is_box3 else bedrag,
            bedrag_box3=bedrag if is_box3 else 0,
            werkelijke_rente=_normalize_rente(rente_raw),
            org_lpt=looptijd,
            rest_lpt=looptijd,
            rvp=rvp_maanden,
            is_overbrugging=False,  # Aanvraag leningdelen zijn nooit overbrugging
        )
        result.append(ld)

    return result


def _extract_verplichtingen_from_aanvraag(aanvraag_data: dict) -> dict:
    """Extraheer verplichtingen uit aanvraag.data.verplichtingen[].

    Structuur per item: { type, maandbedrag, saldo, ... }
    Types: "studieschuld", "doorlopend_krediet", "persoonlijke_lening", etc.
    """
    items = aanvraag_data.get("verplichtingen") or []
    studielening = 0
    overige_kredieten = 0
    limieten = 0

    for item in items:
        vtype = str(item.get("type") or "").lower()
        maandbedrag = _to_float(item.get("maandbedrag"))
        saldo = _to_float(item.get("saldo"))

        if "studie" in vtype:
            studielening += maandbedrag
        elif "doorlopend" in vtype or "krediet" in vtype:
            limieten += saldo
            overige_kredieten += maandbedrag
        else:
            overige_kredieten += maandbedrag

    return {
        "studielening": studielening,
        "overige_kredieten": overige_kredieten,
        "limieten": limieten,
    }


def _extract_kinderen_from_aanvraag(aanvraag_data: dict) -> tuple[list[str], bool, str]:
    """Extraheer kinderen uit aanvraag.data.kinderen[].

    Returns: (kinderen_list, heeft_kind_onder_18, geboortedatum_jongste_kind)
    """
    items = aanvraag_data.get("kinderen") or []
    kinderen = []
    heeft_kind_onder_18 = False
    geboortedatum_jongste_kind = ""

    for kind in items:
        roepnaam = str(kind.get("roepnaam") or "").strip()
        achternaam = str(kind.get("achternaam") or "").strip()
        geb = str(kind.get("geboortedatum") or "").strip()
        naam = f"{roepnaam} {achternaam}".strip()

        if naam or geb:
            kinderen.append(f"{naam} ({geb})" if geb else naam)
            if geb:
                try:
                    from datetime import date as dt_date
                    geb_date = dt_date.fromisoformat(geb)
                    leeftijd = (dt_date.today() - geb_date).days / 365.25
                    if leeftijd < 18:
                        heeft_kind_onder_18 = True
                    if not geboortedatum_jongste_kind or geb > geboortedatum_jongste_kind:
                        geboortedatum_jongste_kind = geb
                except (ValueError, TypeError):
                    pass

    return kinderen, heeft_kind_onder_18, geboortedatum_jongste_kind


def _extract_werkgever_from_aanvraag(persoon_data: dict) -> Optional[NormalizedWerkgever]:
    """Extraheer werkgever uit aanvraag.data.aanvrager/partner.werkgever."""
    wg = persoon_data.get("werkgever")
    if not wg or not isinstance(wg, dict):
        return None

    naam = str(wg.get("naamWerkgever") or wg.get("naam") or "").strip()
    if not naam:
        return None

    dienstverband = str(wg.get("soortDienstverband") or wg.get("dienstverband") or "").strip()
    datum = str(wg.get("datumInDienst") or wg.get("datum_in_dienst") or "").strip()

    return NormalizedWerkgever(naam=naam, dienstverband=dienstverband, datum_in_dienst=datum)


def _extract_verzekeringen_from_aanvraag(aanvraag_data: dict) -> list[NormalizedVerzekering]:
    """Extraheer verzekeringen uit aanvraag.data.voorzieningen.verzekeringen[].

    Lovable slaat verzekeringen op met geneste verzekerdePersonen[]:
      { type, aanbieder, polisnummer, soortDekking, einddatum,
        verzekerdePersonen: [{ verzekerde: "aanvrager", orvDekking: 30000 }, ...] }

    Elke verzekerde persoon wordt een apart NormalizedVerzekering record.
    Fallback: als er geen verzekerdePersonen array is, gebruik flat velden.
    """
    voorzieningen = aanvraag_data.get("voorzieningen") or {}
    items = voorzieningen.get("verzekeringen") or []

    if not items:
        return []

    result = []
    for item in items:
        vtype = str(item.get("type") or "").strip()
        aanbieder = str(item.get("aanbieder") or "").strip()
        polisnummer = str(item.get("polisnummer") or "").strip()
        soort_dekking = str(item.get("soortDekking") or "").strip()
        einddatum = str(item.get("einddatum") or "").strip()

        # Log alle keys van dit verzekering item
        logger.info("Verzekering item keys: %s", sorted(item.keys()))

        # Geneste verzekerdePersonen array (Lovable structuur)
        personen = (
            item.get("verzekerdePersonen")
            or item.get("verzekerden")
            or item.get("verzekerde_personen")
            or []
        )

        if personen and isinstance(personen, list):
            # Split: één record per verzekerde persoon
            for vp in personen:
                if not isinstance(vp, dict):
                    logger.info("VP is niet een dict: %s (type=%s)", vp, type(vp).__name__)
                    continue
                # Log alle keys van deze verzekerde persoon
                logger.info("VezekerdePersonen item keys: %s, values: %s",
                            sorted(vp.keys()), {k: str(v)[:50] for k, v in vp.items()})
                verzekerde = str(
                    vp.get("verzekerde") or vp.get("type")
                    or vp.get("naam") or vp.get("persoon") or ""
                ).strip()
                dekking = _to_float(
                    vp.get("orvDekking") or vp.get("aovDekking")
                    or vp.get("dekking") or vp.get("uitkering")
                )
                result.append(NormalizedVerzekering(
                    type=vtype,
                    aanbieder=aanbieder,
                    polisnummer=polisnummer,
                    verzekerde=verzekerde,
                    dekking=dekking,
                    soort_dekking=soort_dekking,
                    einddatum=einddatum,
                ))
        else:
            # Flat structuur (fallback)
            verzekerde = str(
                item.get("verzekerde") or item.get("verzekerdeNaam") or ""
            ).strip()
            dekking = _to_float(
                item.get("orvDekking") or item.get("aovDekking")
                or item.get("dekking") or item.get("uitkering")
            )
            result.append(NormalizedVerzekering(
                type=vtype,
                aanbieder=aanbieder,
                polisnummer=polisnummer,
                verzekerde=verzekerde,
                dekking=dekking,
                soort_dekking=soort_dekking,
                einddatum=einddatum,
            ))

    logger.info("Verzekeringen: %d records (na split per persoon)", len(result))
    return result


def _extract_vermogen_from_aanvraag(aanvraag_data: dict) -> list[NormalizedVermogensItem]:
    """Extraheer vermogensposten uit aanvraag.data.vermogenSectie.items[]."""
    sectie = aanvraag_data.get("vermogenSectie") or {}
    items = sectie.get("items") or []

    if not items:
        return []

    result = []
    for item in items:
        vtype = str(item.get("type") or "").strip()
        saldo = _to_float(item.get("saldo") or item.get("bedrag"))
        eigenaar = str(item.get("eigenaar") or "").strip()
        maatschappij = str(item.get("maatschappij") or item.get("bank") or "").strip()

        result.append(NormalizedVermogensItem(
            type=vtype,
            saldo=saldo,
            eigenaar=eigenaar,
            maatschappij=maatschappij,
        ))

    logger.info("Vermogensposten: %d gevonden, totaal=%.0f",
                len(result), sum(v.saldo for v in result))
    return result


def _extract_woningen_from_aanvraag(aanvraag_data: dict) -> list[NormalizedBestaandeWoning]:
    """Extraheer bestaande woningen uit aanvraag.data.woningen[]."""
    items = aanvraag_data.get("woningen") or []

    if not items:
        return []

    result = []
    for w in items:
        straat = str(w.get("straat") or "").strip()
        huisnr = str(w.get("huisnummer") or "").strip()
        toev = str(w.get("toevoeging") or "").strip()
        adres = f"{straat} {huisnr}".strip()
        if toev:
            adres = f"{adres}{toev}"

        postcode = str(w.get("postcode") or "").strip()
        woonplaats = str(w.get("woonplaats") or "").strip()
        postcode_plaats = f"{postcode} {woonplaats}".strip()

        type_woning = str(w.get("typeWoning") or w.get("soortWoning") or "").strip()
        marktwaarde = _to_float(w.get("waardeWoning") or w.get("marktwaarde"))
        woz_waarde = _to_float(w.get("wozWaarde"))
        status = str(w.get("woningstatus") or w.get("status") or "").strip()
        erfpacht = bool(w.get("erfpacht"))
        energielabel = str(w.get("energielabel") or "").strip()

        result.append(NormalizedBestaandeWoning(
            adres=adres,
            postcode_plaats=postcode_plaats,
            type_woning=type_woning,
            marktwaarde=marktwaarde,
            woz_waarde=woz_waarde,
            status=status,
            erfpacht=erfpacht,
            energielabel=energielabel,
        ))

    logger.info("Bestaande woningen: %d gevonden", len(result))
    return result


def _extract_hypotheken_from_aanvraag(aanvraag_data: dict) -> list[NormalizedBestaandeHypotheek]:
    """Extraheer bestaande hypotheken uit aanvraag.data.hypotheken[].

    Verstrekker komt uit hypotheekInschrijvingen[] (apart top-level veld).
    Hypotheek.inschrijvingId linkt naar hypotheekInschrijvingen[].id.
    """
    items = aanvraag_data.get("hypotheken") or []

    if not items:
        return []

    # Bouw inschrijving lookup: id → inschrijving dict
    inschrijvingen = aanvraag_data.get("hypotheekInschrijvingen") or []
    inschrijving_map = {}
    for insc in inschrijvingen:
        if isinstance(insc, dict):
            insc_id = insc.get("id")
            if insc_id:
                inschrijving_map[insc_id] = insc
    if inschrijvingen:
        logger.info("HypotheekInschrijvingen: %d gevonden, keys: %s",
                     len(inschrijvingen),
                     sorted(inschrijvingen[0].keys()) if inschrijvingen else [])

    result = []
    for h in items:
        logger.info("Hypotheek item keys: %s", sorted(h.keys()))

        # Verstrekker: eerst in hypotheek zelf, dan via inschrijving
        verstrekker = str(h.get("geldverstrekker") or h.get("verstrekker") or "").strip()
        nhg = bool(h.get("nhg"))

        if not verstrekker:
            insc_id = h.get("inschrijvingId")
            insc = inschrijving_map.get(insc_id) or {}
            verstrekker = str(
                insc.get("geldverstrekker") or insc.get("verstrekker")
                or insc.get("maatschappij") or insc.get("naamGeldverstrekker") or ""
            ).strip()
            if not nhg:
                nhg = bool(insc.get("nhg"))
            logger.info("Verstrekker uit inschrijving %s: '%s' (keys: %s)",
                        insc_id, verstrekker, sorted(insc.keys()) if insc else [])

        hoofdsom = _to_float(h.get("hoofdsom") or h.get("oorspronkelijkeHoofdsom"))
        restschuld = _to_float(h.get("restschuld") or h.get("huidigeSaldo"))

        # Leningdelen van bestaande hypotheek
        ld_items = h.get("leningdelen") or []
        leningdelen = []
        for ld in ld_items:
            looptijd_raw = _to_float(ld.get("looptijd") or ld.get("origineleLooptijd"))
            rentevast_raw = _to_float(ld.get("renteVastPeriode") or ld.get("rentevastePeriode"))
            leningdelen.append({
                "bedrag": _to_float(ld.get("bedrag") or ld.get("hoofdsom")),
                "rente": _to_float(ld.get("rentePercentage") or ld.get("rente")),
                "aflosvorm": str(ld.get("aflosvorm") or "").strip(),
                "looptijd": int(looptijd_raw) if looptijd_raw else 0,
                "rentevast": int(rentevast_raw) if rentevast_raw else 0,
                "ingangsdatum": str(ld.get("ingangsdatum") or "").strip(),
            })

        result.append(NormalizedBestaandeHypotheek(
            verstrekker=verstrekker,
            nhg=nhg,
            hoofdsom=hoofdsom,
            restschuld=restschuld,
            leningdelen=leningdelen,
        ))

    logger.info("Bestaande hypotheken: %d gevonden", len(result))
    return result


def _extract_verplichtingen_details_from_aanvraag(aanvraag_data: dict) -> list[dict]:
    """Extraheer gedetailleerde verplichtingen voor display in rapport."""
    items = aanvraag_data.get("verplichtingen") or []
    result = []

    TYPE_DISPLAY = {
        "studieschuld": "Studielening",
        "doorlopend_krediet": "Doorlopend krediet",
        "persoonlijke_lening": "Persoonlijke lening",
        "huurkoop": "Huurkoop/Private lease",
        "creditcard": "Creditcard",
    }

    for item in items:
        vtype = str(item.get("type") or "").strip()
        maandbedrag = _to_float(item.get("maandbedrag"))
        saldo = _to_float(item.get("saldo"))
        omschrijving = str(item.get("omschrijving") or item.get("naam") or "").strip()

        result.append({
            "type": TYPE_DISPLAY.get(vtype, vtype.replace("_", " ").capitalize()),
            "maandbedrag": maandbedrag,
            "saldo": saldo,
            "omschrijving": omschrijving,
        })

    return result


# ─── Dossier-based extraction (FALLBACK) ───

def _extract_leningdelen_from_dossier(
    invoer: dict,
    scenario_kolom: dict | None = None,
) -> list[NormalizedLeningdeel]:
    """Extraheer en normaliseer leningdelen uit dossier (fallback).

    Zoekt in volgorde:
    1. scenario_kolom (dossier.scenario1 — aparte kolom in Supabase productie)
    2. invoer._dossierScenario1 (legacy/test data)
    3. invoer.haalbaarheidsBerekeningen[0].leningDelen
    4. invoer.leningdelen / invoer.hypotheekDelen (direct)
    """
    raw_delen = None

    # 1. Scenario kolom
    if scenario_kolom and isinstance(scenario_kolom, dict):
        raw_delen = _get(scenario_kolom, "leningDelen", "leningdelen")

    # 2. _dossierScenario1 in invoer (legacy test data)
    if not raw_delen:
        dossier_scenario = _get(invoer, "_dossierScenario1", "_dossierScenario") or {}
        raw_delen = _get(dossier_scenario, "leningDelen", "leningdelen")

    # 3. haalbaarheidsBerekeningen[0].leningDelen
    if not raw_delen:
        haalb_list = _get(invoer, "haalbaarheidsBerekeningen") or []
        if haalb_list and isinstance(haalb_list, list):
            raw_delen = _get(haalb_list[0], "leningDelen", "leningdelen")

    # 4. Direct op invoer
    if not raw_delen:
        raw_delen = _get(invoer, "leningdelen", "hypotheekDelen", "hypotheek_delen") or []

    if not raw_delen:
        logger.warning("Geen leningdelen gevonden in dossier")
        return []

    logger.info("Gevonden: %d leningdelen (dossier)", len(raw_delen))

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


def _extract_inkomen_from_dossier(invoer: dict, suffix: str = "Aanvrager") -> NormalizedInkomen:
    """Extraheer inkomen uit dossier.invoer (fallback)."""
    klant = _get(invoer, "klantGegevens", "klant") or {}
    haalb = (_get(invoer, "haalbaarheidsBerekeningen") or [{}])[0] if _get(invoer, "haalbaarheidsBerekeningen") else {}
    ink_obj = _get(haalb, "inkomenGegevens", "inkomen") or _get(invoer, "inkomenGegevens", "inkomen") or {}

    suffix_lower = suffix.lower()
    suffix_camel = suffix

    hoofd = _to_float(
        _get(ink_obj, f"hoofdinkomen{suffix_camel}", f"hoofd_inkomen_{suffix_lower}")
        or _get(klant, f"hoofdinkomen{suffix_camel}", f"hoofd_inkomen_{suffix_lower}")
        or _get(invoer, f"hoofd_inkomen_{suffix_lower}", f"hoofdinkomen{suffix_camel}")
        or _get(haalb, f"hoofd_inkomen_{suffix_lower}")
    )

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

    dienstverband = (
        _get(ink_obj, f"typeDienstverband{suffix_camel}",
             f"dienstverband_{suffix_lower}")
        or _get(klant, f"typeDienstverband{suffix_camel}")
        or _get(invoer, f"dienstverband_{suffix_lower}")
        or "Loondienst"
    )

    logger.debug(
        "Inkomen %s (dossier): hoofd=%.0f, aow=%.0f, pensioen=%.0f, "
        "lijfrente=%.0f, huur=%.0f, dienstverband=%s",
        suffix, hoofd, aow, pensioen, lijfrente, huur, dienstverband,
    )

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


def _extract_persoon_from_dossier(
    invoer: dict,
    suffix: str = "Aanvrager",
    contact_gegevens: dict | None = None,
) -> NormalizedPersoon:
    """Extraheer persoonsgegevens uit dossier (fallback)."""
    klant = _get(invoer, "klantGegevens", "klant") or {}
    suffix_camel = suffix
    suffix_lower = suffix.lower()

    contact = {}
    if contact_gegevens and isinstance(contact_gegevens, dict):
        contact = contact_gegevens.get(suffix_lower) or {}

    naam = str(_get(klant, f"naam{suffix_camel}", f"naam_{suffix_lower}") or "").strip()
    if not naam:
        roepnaam = str(_get(klant, f"roepnaam{suffix_camel}") or
                       _get(contact, "voornaam") or "").strip()
        tussenvoegsel = str(_get(klant, f"tussenvoegsel{suffix_camel}") or
                            _get(contact, "tussenvoegsel") or "").strip()
        achternaam = str(_get(klant, f"achternaam{suffix_camel}") or
                         _get(contact, "achternaam") or "").strip()
        parts = [p for p in [roepnaam, tussenvoegsel, achternaam] if p]
        naam = " ".join(parts)

    geboortedatum = str(
        _get(klant, f"geboortedatum{suffix_camel}", f"geboortedatum_{suffix_lower}") or ""
    )

    adres = str(_get(klant, f"adres{suffix_camel}", "adres") or "")
    if not adres and contact:
        straat = str(_get(contact, "straat") or "")
        huisnummer = str(_get(contact, "huisnummer") or "")
        if straat or huisnummer:
            adres = f"{straat} {huisnummer}".strip()

    postcode_plaats = str(_get(klant, f"postcodePlaats{suffix_camel}", "postcodePlaats") or "")
    if not postcode_plaats and contact:
        postcode = str(_get(contact, "postcode") or "")
        woonplaats = str(_get(contact, "woonplaats") or "")
        if postcode or woonplaats:
            postcode_plaats = f"{postcode} {woonplaats}".strip()

    telefoon = str(
        _get(klant, f"telefoon{suffix_camel}", "telefoon")
        or _get(contact, "telefoonnummer", "telefoon")
        or ""
    )
    email = str(
        _get(klant, f"email{suffix_camel}", "email")
        or _get(contact, "email")
        or ""
    )

    inkomen = _extract_inkomen_from_dossier(invoer, suffix)

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


def _extract_financiering_from_dossier(invoer: dict) -> NormalizedFinanciering:
    """Extraheer financieringsgegevens uit dossier.invoer (fallback)."""
    ber_list = _get(invoer, "berekeningen") or []
    ber = ber_list[0] if ber_list else {}
    klant = _get(invoer, "klantGegevens", "klant") or {}
    fin = _get(invoer, "financiering", "financieringInput") or {}

    # Onderpand uit haalbaarheidsBerekeningen
    haalb_list = _get(invoer, "haalbaarheidsBerekeningen") or []
    haalb_onderpand = {}
    if haalb_list:
        haalb_onderpand = haalb_list[0].get("onderpand") or {}

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
        _get(haalb_onderpand, "marktwaarde")
        or _get(ber, "woningwaarde", "marktwaarde")
        or _get(fin, "woningwaarde", "marktwaarde")
        or _get(invoer, "woningwaarde")
    ) or koopsom

    energielabel = str(
        _get(haalb_onderpand, "energielabel")
        or _get(ber, "energielabel")
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

    woning_type_raw = str(
        _get(ber, "woningType", "woning_type", "typeWoning")
        or _get(fin, "woningType", "typeWoning")
        or _get(invoer, "woningType")
        or ""
    ).lower().strip()
    type_woning = _map_woning_type(woning_type_raw)

    kosten_koper = _to_float(
        _get(ber, "kostenKoper", "kosten_koper")
        or _get(fin, "kostenKoper", "kosten_koper")
        or _get(invoer, "kostenKoper", "kosten_koper")
    )

    logger.debug(
        "Financiering (dossier): koopsom=%.0f, woningwaarde=%.0f, eigen_geld=%.0f, "
        "kosten_koper=%.0f, energielabel=%s, adres=%s",
        koopsom, woningwaarde, eigen_geld, kosten_koper, energielabel,
        adres or "(leeg)",
    )

    return NormalizedFinanciering(
        koopsom=koopsom,
        kosten_koper=kosten_koper,
        eigen_middelen=eigen_geld,
        woningwaarde=woningwaarde,
        energielabel=energielabel,
        type_woning=type_woning,
        adres=adres,
    )


# ─── Hoofdfunctie ───

def extract_dossier_data(
    dossier: dict,
    aanvraag: dict,
) -> NormalizedDossierData:
    """Hoofdfunctie: Supabase dossier + aanvraag → NormalizedDossierData.

    PRIMAIRE BRON: aanvraag.data (Inventarisatie + Samenstellen stappen)
    FALLBACK: dossier.invoer (Haalbaarheid stap)

    Args:
        dossier: Volledige rij uit Supabase `dossiers` tabel
        aanvraag: Volledige rij uit Supabase `aanvragen` tabel

    Returns:
        NormalizedDossierData met alle velden genormaliseerd.
    """
    invoer = dossier.get("invoer") or dossier
    aanvraag_data = {}
    if aanvraag and isinstance(aanvraag.get("data"), dict):
        aanvraag_data = aanvraag["data"]

    # has_aanvraag = True alleen als aanvraag_data daadwerkelijk Inventarisatie/
    # Samenstellen data bevat (aanvrager, inkomen, etc.)
    has_aanvraag = bool(aanvraag_data and (
        aanvraag_data.get("aanvrager")
        or aanvraag_data.get("inkomenAanvrager")
        or aanvraag_data.get("heeftPartner") is not None
    ))
    logger.info("Bron: %s", "aanvraag.data" if has_aanvraag else "dossier.invoer (fallback)")
    logger.info("Dossier keys: %s", list(dossier.keys()) if isinstance(dossier, dict) else "niet-dict")
    logger.info("Aanvraag data keys: %s", list(aanvraag_data.keys()) if aanvraag_data else "leeg")

    klant = _get(invoer, "klantGegevens", "klant") or {}
    contact_gegevens = dossier.get("klant_contact_gegevens")
    if isinstance(contact_gegevens, str):
        try:
            import json
            contact_gegevens = json.loads(contact_gegevens)
        except (json.JSONDecodeError, TypeError):
            contact_gegevens = None

    # ── Alleenstaand ──
    if has_aanvraag:
        alleenstaand = not bool(aanvraag_data.get("heeftPartner", False))
    else:
        alleenstaand_raw = _get(klant, "alleenstaand", "is_alleenstaand")
        if isinstance(alleenstaand_raw, bool):
            alleenstaand = alleenstaand_raw
        elif isinstance(alleenstaand_raw, str):
            alleenstaand = alleenstaand_raw.lower() in ("true", "ja", "yes", "1")
        else:
            has_partner_naam = bool(_get(klant, "naamPartner", "naam_partner"))
            has_partner_parts = bool(
                _get(klant, "achternaamPartner") or _get(klant, "roepnaamPartner")
            )
            alleenstaand = not (has_partner_naam or has_partner_parts)

    # ── Personen ──
    if has_aanvraag:
        inkomen_aanvrager_items = aanvraag_data.get("inkomenAanvrager") or []
        aanvrager = _extract_persoon_from_aanvraag(aanvraag_data, "aanvrager", inkomen_aanvrager_items)
        partner = None
        if not alleenstaand:
            inkomen_partner_items = aanvraag_data.get("inkomenPartner") or []
            partner = _extract_persoon_from_aanvraag(aanvraag_data, "partner", inkomen_partner_items)
    else:
        aanvrager = _extract_persoon_from_dossier(invoer, "Aanvrager", contact_gegevens)
        partner = None
        if not alleenstaand:
            partner = _extract_persoon_from_dossier(invoer, "Partner", contact_gegevens)

    # ── Leningdelen ──
    if has_aanvraag:
        leningdelen = _extract_leningdelen_from_aanvraag(aanvraag_data)
    if not has_aanvraag or not leningdelen:
        # Fallback naar dossier scenario1
        scenario_kolom = dossier.get("scenario1")
        if isinstance(scenario_kolom, str):
            try:
                import json
                scenario_kolom = json.loads(scenario_kolom)
            except (json.JSONDecodeError, TypeError):
                scenario_kolom = None
        leningdelen = _extract_leningdelen_from_dossier(invoer, scenario_kolom=scenario_kolom)

    # ── Financiering ──
    if has_aanvraag and aanvraag_data.get("financieringsopzet"):
        financiering = _extract_financiering_from_aanvraag(aanvraag_data)
    else:
        financiering = _extract_financiering_from_dossier(invoer)

    # Hypotheekverstrekker + NHG: check meerdere bronnen
    if not financiering.hypotheekverstrekker:
        # 1. aanvraag.data.samenstellenHypotheek (productie Lovable)
        samenstellen = (aanvraag_data.get("samenstellenHypotheek") or {}) if aanvraag_data else {}
        verstrekker = str(samenstellen.get("geldverstrekker") or "")
        # 2. aanvraag.data.hypotheekverstrekker (ouder formaat)
        if not verstrekker:
            verstrekker = str(aanvraag_data.get("hypotheekverstrekker") or "") if aanvraag_data else ""
        # 3. aanvraag.hypotheekverstrekker (top-level, backward compat)
        if not verstrekker and aanvraag:
            verstrekker = str(aanvraag.get("hypotheekverstrekker") or "")
        if verstrekker:
            financiering.hypotheekverstrekker = verstrekker

        nhg_raw = (
            samenstellen.get("nhg")
            if samenstellen.get("nhg") is not None
            else aanvraag_data.get("nhg") if aanvraag_data
            else None
        )
        if nhg_raw is None and aanvraag:
            nhg_raw = aanvraag.get("nhg")
        if nhg_raw is not None:
            financiering.nhg = bool(nhg_raw)

    # ── Verplichtingen ──
    if has_aanvraag and aanvraag_data.get("verplichtingen"):
        verpl = _extract_verplichtingen_from_aanvraag(aanvraag_data)
        studielening = verpl["studielening"]
        overig_krediet = verpl["overige_kredieten"]
        limieten_bkr = verpl["limieten"]
        erfpacht = 0
    else:
        # Fallback: uit dossier haalbaarheidsBerekeningen inkomenGegevens
        haalb_list = _get(invoer, "haalbaarheidsBerekeningen") or []
        haalb_ink = (haalb_list[0].get("inkomenGegevens") or {}) if haalb_list else {}
        verplichtingen = _get(invoer, "verplichtingen", "financieleVerplichtingen") or {}

        limieten_bkr = _to_float(
            _get(haalb_ink, "limieten", "bkrLimieten")
            or _get(verplichtingen, "limietenBkr", "limieten_bkr_geregistreerd", "limieten")
            or _get(invoer, "limieten_bkr_geregistreerd", "limietenBkr")
        )
        studielening = _to_float(
            _get(haalb_ink, "studielening")
            or _get(verplichtingen, "studielening", "studievoorschot_studielening")
            or _get(invoer, "studievoorschot_studielening", "studielening")
        )
        erfpacht = _to_float(
            _get(verplichtingen, "erfpachtcanon", "erfpachtcanon_per_jaar", "erfpacht")
            or _get(invoer, "erfpachtcanon_per_jaar", "erfpachtcanon")
        )
        overig_krediet = _to_float(
            _get(haalb_ink, "maandlastLeningen", "overigeKredieten")
            or _get(verplichtingen, "overigeKredieten", "jaarlast_overige_kredieten")
            or _get(invoer, "jaarlast_overige_kredieten", "overigeKredieten")
        )

    # ── Burgerlijke staat ──
    if has_aanvraag:
        bs_raw = aanvraag_data.get("burgerlijkeStaat") or ""
        burgerlijke_staat = bs_raw.capitalize() if bs_raw else ("Alleenstaand" if alleenstaand else "Gehuwd")

        sv_raw = aanvraag_data.get("samenlevingsvorm") or ""
        huwelijkse_voorwaarden = SAMENLEVINGSVORM_MAPPING.get(sv_raw, sv_raw)
    else:
        burgerlijke_staat = "Alleenstaand" if alleenstaand else "Gehuwd"
        bs_raw = _get(klant, "burgerlijkeStaat", "burgerlijke_staat", "burgelijkeStaat")
        if bs_raw and isinstance(bs_raw, str) and bs_raw.strip():
            burgerlijke_staat = bs_raw.strip()

        huwelijkse_voorwaarden = str(
            _get(klant, "huwelijkseVoorwaarden", "huwelijkse_voorwaarden",
                 "huwelijksVoorwaarden")
            or ""
        ).strip()

    # ── Werkgever ──
    werkgever_aanvrager = None
    werkgever_partner = None
    if has_aanvraag:
        werkgever_aanvrager = _extract_werkgever_from_aanvraag(
            aanvraag_data.get("aanvrager") or {}
        )
        if not alleenstaand:
            werkgever_partner = _extract_werkgever_from_aanvraag(
                aanvraag_data.get("partner") or {}
            )

    # ── Verzekeringen ──
    verzekeringen = []
    if has_aanvraag:
        verzekeringen = _extract_verzekeringen_from_aanvraag(aanvraag_data)

    # ── Vermogen ──
    vermogen = []
    if has_aanvraag:
        vermogen = _extract_vermogen_from_aanvraag(aanvraag_data)

    # ── Bestaande woningen ──
    bestaande_woningen = []
    if has_aanvraag:
        bestaande_woningen = _extract_woningen_from_aanvraag(aanvraag_data)

    # ── Bestaande hypotheken ──
    bestaande_hypotheken = []
    if has_aanvraag:
        bestaande_hypotheken = _extract_hypotheken_from_aanvraag(aanvraag_data)

    # ── Verplichtingen details ──
    verplichtingen_details = []
    if has_aanvraag:
        verplichtingen_details = _extract_verplichtingen_details_from_aanvraag(aanvraag_data)

    # ── Kinderen ──
    if has_aanvraag and aanvraag_data.get("kinderen"):
        kinderen, heeft_kind_onder_18, geboortedatum_jongste_kind = \
            _extract_kinderen_from_aanvraag(aanvraag_data)
    else:
        kinderen_raw = _get(klant, "kinderen") or []
        kinderen = []
        heeft_kind_onder_18 = False
        geboortedatum_jongste_kind = ""
        if isinstance(kinderen_raw, list):
            for kind in kinderen_raw:
                if isinstance(kind, dict):
                    naam = str(_get(kind, "naam", "voornaam") or "").strip()
                    geb = str(_get(kind, "geboortedatum") or "").strip()
                    if naam or geb:
                        kinderen.append(f"{naam} ({geb})" if geb else naam)
                        if geb:
                            try:
                                from datetime import date as dt_date
                                geb_date = dt_date.fromisoformat(geb)
                                leeftijd = (dt_date.today() - geb_date).days / 365.25
                                if leeftijd < 18:
                                    heeft_kind_onder_18 = True
                                if not geboortedatum_jongste_kind or geb > geboortedatum_jongste_kind:
                                    geboortedatum_jongste_kind = geb
                            except (ValueError, TypeError):
                                pass
                elif isinstance(kind, str) and kind.strip():
                    kinderen.append(kind.strip())

    data = NormalizedDossierData(
        aanvrager=aanvrager,
        partner=partner,
        alleenstaand=alleenstaand,
        burgerlijke_staat=burgerlijke_staat,
        huwelijkse_voorwaarden=huwelijkse_voorwaarden,
        kinderen=kinderen,
        heeft_kind_onder_18=heeft_kind_onder_18,
        geboortedatum_jongste_kind=geboortedatum_jongste_kind,
        financiering=financiering,
        leningdelen=leningdelen,
        limieten_bkr=limieten_bkr,
        studielening_maandlast=studielening,
        erfpachtcanon_per_maand=erfpacht,
        overige_kredieten_maandlast=overig_krediet,
        verplichtingen_details=verplichtingen_details,
        verzekeringen=verzekeringen,
        vermogen=vermogen,
        bestaande_woningen=bestaande_woningen,
        bestaande_hypotheken=bestaande_hypotheken,
        werkgever_aanvrager=werkgever_aanvrager,
        werkgever_partner=werkgever_partner,
    )

    logger.info(
        "Dossier genormaliseerd: alleenstaand=%s, leningdelen=%d, hypotheek=%.0f, "
        "bron=%s",
        alleenstaand, len(leningdelen), data.hypotheek_bedrag,
        "aanvraag" if has_aanvraag else "dossier",
    )

    return data
