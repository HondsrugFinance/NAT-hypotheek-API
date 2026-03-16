"""Field mapper: Supabase dossier/aanvraag → genormaliseerde Python dataclasses.

Constanten:
  ONDERNEMER_DREMPEL — Drempel (0.75 = 75%) waarboven iemand als "overwegend
  ondernemer" wordt beschouwd voor tekst-doeleinden (RVC, nuance).

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
from datetime import date
from typing import Optional

from aow_calculator import bereken_aow_datum

logger = logging.getLogger("nat-api.adviesrapport_v2.field_mapper")

ONDERNEMER_DREMPEL = 0.75  # Onderneming > 75% van actief inkomen → "overwegend ondernemer"

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
    herkomst: str = "nieuw"          # "nieuw", "meenemen", "bestaand", "elders"
    meenemen_in_toetsing: bool = True  # Alleen relevant voor herkomst="elders"

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
    overig: float = 0  # Doorlopend overig inkomen (geen einddatum → telt mee na AOW)
    overig_tijdelijk: float = 0  # Overig inkomen MET einddatum (stopt vóór AOW)
    uitkering: float = 0  # Niet-AOW uitkeringen (stopt bij AOW-leeftijd)
    aow_uitkering: float = 0
    pensioen: float = 0
    nabestaandenpensioen: float = 0  # Uitkering bij overlijden partner
    partneralimentatie_ontvangen: float = 0
    partneralimentatie_betalen: float = 0

    @property
    def totaal_huidig(self) -> float:
        return (self.loondienst + self.onderneming + self.roz
                + self.overig + self.overig_tijdelijk
                + self.uitkering
                + self.partneralimentatie_ontvangen - self.partneralimentatie_betalen)

    @property
    def totaal_aow(self) -> float:
        return self.aow_uitkering + self.pensioen + self.overig

    @property
    def hoofd_inkomen(self) -> float:
        """Hoofdinkomen = loondienst + onderneming + roz."""
        return self.loondienst + self.onderneming + self.roz

    @property
    def is_ondernemer(self) -> bool:
        """Pure ondernemer: alleen ondernemingsinkomen, geen loondienst."""
        return self.onderneming > 0 and self.loondienst == 0

    @property
    def is_overwegend_ondernemer(self) -> bool:
        """Onderneming > 75% van actief inkomen (loondienst + onderneming).

        True voor zowel pure als overwegend ondernemers.
        """
        actief = self.loondienst + self.onderneming
        if actief <= 0:
            return False
        return self.onderneming / actief > ONDERNEMER_DREMPEL


@dataclass
class NormalizedPersoon:
    """Gegevens van één persoon (aanvrager of partner)."""
    naam: str = ""
    voornaam: str = ""
    voorletters_achternaam: str = ""
    geboortedatum: str = ""  # YYYY-MM-DD
    adres: str = ""
    postcode_plaats: str = ""
    telefoon: str = ""
    email: str = ""
    inkomen: NormalizedInkomen = field(default_factory=NormalizedInkomen)
    dienstverband: str = "Loondienst"  # Loondienst, Onderneming, ROZ
    eerder_gehuwd: bool = False
    datum_echtscheiding: str = ""
    weduwe_weduwnaar: bool = False
    flexibel_inkomen_3j: bool = False  # Flexibel inkomen over 3 jaar
    arbeidsmarktscan_fase: str = ""    # Fase arbeidsmarktscan

    @property
    def korte_naam(self) -> str:
        """Roepnaam of voorletters+achternaam — voor teksten en tabellen."""
        return self.voornaam if self.voornaam else (self.voorletters_achternaam or self.naam)

    @property
    def titel_naam(self) -> str:
        """Roepnaam+achternaam of voorletters+achternaam — voor titels."""
        return self.naam if self.voornaam else (self.voorletters_achternaam or self.naam)


@dataclass
class NormalizedVerzekering:
    """Eén verzekering (ORV, AOV, etc.)."""
    type: str = ""           # "overlijdensrisicoverzekering", "arbeidsongeschiktheid", etc.
    aanbieder: str = ""
    polisnummer: str = ""
    verzekerde: str = ""     # "aanvrager", "partner", "beiden"
    dekking: float = 0       # Jaarlijks of eenmalig uitkeringsbedrag (ORV)
    dekking_aov: float = 0   # AOV dekking bedrag (jaarbasis)
    dekking_ao: float = 0    # Woonlastenverzekering AO component (jaarbasis)
    dekking_ww: float = 0    # Woonlastenverzekering WW component (jaarbasis)
    soort_dekking: str = ""  # "gelijkblijvend", "annuïtair", etc.
    einddatum: str = ""      # YYYY-MM-DD

    @property
    def type_display(self) -> str:
        """Leesbare weergave van verzekering type."""
        mapping = {
            "overlijdensrisicoverzekering": "ORV",
            "orv": "ORV",
            "arbeidsongeschiktheidsverzekering": "AOV",
            "arbeidsongeschiktheid": "AOV",
            "aov": "AOV",
            "woonlastenverzekering": "Woonlastenverzekering",
            "lijfrenteverzekering": "Lijfrente",
            "lijfrente": "Lijfrente",
            "levensverzekering": "Levensverzekering",
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
    erfpachtcanon: float = 0     # Canon per jaar
    energielabel: str = ""
    eigenaar: str = ""            # "aanvrager", "partner", "gezamenlijk"
    eigendom_aanvrager: float = 0 # percentage (0-100)
    eigendom_partner: float = 0   # percentage (0-100)
    woontoepassing: str = ""      # "hoofdverblijf", "recreatiewoning", etc.
    huur_per_maand: float = 0


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
    schenking_inbreng: float = 0  # Schenking ingezet voor financiering
    overwaarde: float = 0         # Overwaarde bestaande woning
    woningwaarde: float = 0
    woz_waarde: float = 0
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
    ebv_ebb: float = 0             # Energiebesparende voorzieningen/budget (gecombineerd)
    ebv: float = 0                 # EBV apart (voor display)
    ebb: float = 0                 # EBB apart (voor display)
    overbrugging: float = 0        # Overbruggingskrediet bedrag
    aankoopmakelaar: float = 0     # Aankoopmakelaar kosten
    consumptief: float = 0         # Consumptief bedrag
    # Nieuwbouw project
    koopsom_grond: float = 0
    aanneemsom: float = 0
    meerwerk: float = 0            # meerwerkOpties + meerwerkEigenBeheer
    bouwrente: float = 0
    # Nieuwbouw eigen beheer
    koopsom_kavel: float = 0
    sloop_oude_woning: float = 0
    bouw_woning: float = 0
    # Extra posten (custom)
    extra_posten_aankoop: list = field(default_factory=list)   # [{label, value}]
    extra_posten_kosten: list = field(default_factory=list)    # [{label, value}]
    extra_posten_eigen_middelen: list = field(default_factory=list)  # [{label, value}]
    # Onderpand detail
    plannummer: str = ""
    bouwnummer: str = ""
    erfpacht_onderpand: bool = False
    erfpachtcanon_onderpand: float = 0  # Canon per jaar
    marktwaarde_na_verbouwing: float = 0
    eigendom_aanvrager: float = 50      # percentage (0-100)
    eigendom_partner: float = 50        # percentage (0-100)
    # Wijziging financieringsopzet
    boeterente: float = 0
    uitkoop_partner: float = 0
    afkoop_erfpacht: float = 0
    oversluiten_leningen: float = 0
    is_wijziging: bool = False     # True bij verhogen/oversluiten/uitkopen flows
    doelstelling: str = ""         # "hypotheek-oversluiten", "hypotheek-verhogen", etc.

    @property
    def is_oversluiten(self) -> bool:
        """True als de doelstelling oversluiten is."""
        return "oversluiten" in self.doelstelling.lower()

    @property
    def is_uitkopen(self) -> bool:
        """True als de doelstelling partner uitkopen is."""
        return "uitkop" in self.doelstelling.lower()


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

    # Flag: bestaande leningdelen zitten al IN data.leningdelen
    # (d.w.z. bestaandeLeningdelen waren aanwezig in samenstellenHypotheek).
    # Als True → NIET apart fin.koopsom optellen bij totale schuld/pensioen.
    bestaande_in_leningdelen: bool = False

    # Berekende waarden (afgeleid)
    @property
    def hypotheek_bedrag(self) -> float:
        """Som van leningdelen bij de hypotheekverstrekker (excl. overbrugging en elders)."""
        return sum(
            d.totaal_bedrag for d in self.leningdelen
            if not d.is_overbrugging and d.herkomst != "elders"
        )

    @property
    def hypotheek_bedrag_incl_elders(self) -> float:
        """Hypotheekbedrag inclusief leningdeel elders (meenemen_in_toetsing=True)."""
        base = self.hypotheek_bedrag
        base += sum(
            d.totaal_bedrag for d in self.leningdelen
            if d.herkomst == "elders" and d.meenemen_in_toetsing
        )
        return base

    @property
    def totale_hypotheekschuld(self) -> float:
        """Totale hypotheekschuld inclusief elders (meenemen_in_toetsing=True).

        Als bestaande_in_leningdelen=True: hypotheek_bedrag is al compleet.
        Anders bij wijziging: bestaande hypotheek apart erbij tellen.
        """
        base = self.hypotheek_bedrag_incl_elders
        if self.financiering.is_wijziging and not self.bestaande_in_leningdelen:
            if self.financiering.is_oversluiten:
                totaal_bestaand = sum(h.hoofdsom for h in self.bestaande_hypotheken)
                base += max(0, totaal_bestaand - self.financiering.koopsom)
            else:
                base += self.financiering.koopsom
        return base

    @property
    def totale_investering(self) -> float:
        return self.financiering.koopsom + self.financiering.kosten_koper

    @property
    def leningdelen_voor_api(self) -> list[NormalizedLeningdeel]:
        """Leningdelen voor API calls: excl. overbrugging en elders met meenemen=False."""
        return [
            d for d in self.leningdelen
            if not d.is_overbrugging
            and (d.herkomst != "elders" or d.meenemen_in_toetsing)
        ]

    @property
    def inkomen_aanvrager_huidig(self) -> float:
        ink = self.aanvrager.inkomen
        return ink.hoofd_inkomen + ink.overig + ink.overig_tijdelijk + ink.uitkering

    @property
    def inkomen_partner_huidig(self) -> float:
        if not self.partner:
            return 0
        ink = self.partner.inkomen
        return ink.hoofd_inkomen + ink.overig + ink.overig_tijdelijk + ink.uitkering

    @property
    def inkomen_aanvrager_aow(self) -> float:
        return self.aanvrager.inkomen.totaal_aow

    @property
    def inkomen_partner_aow(self) -> float:
        return self.partner.inkomen.totaal_aow if self.partner else 0

    @property
    def aov_dekking_aanvrager(self) -> float:
        """AOV bruto jaardekking voor aanvrager (uit verzekeringen)."""
        return sum(
            v.dekking_aov for v in self.verzekeringen
            if v.verzekerde.lower() in ("aanvrager",)
            or (self.aanvrager.naam and v.verzekerde == self.aanvrager.naam)
        )

    @property
    def aov_dekking_partner(self) -> float:
        """AOV bruto jaardekking voor partner (uit verzekeringen)."""
        return sum(
            v.dekking_aov for v in self.verzekeringen
            if v.verzekerde.lower() in ("partner",)
            or (self.partner and self.partner.naam and v.verzekerde == self.partner.naam)
        )

    @property
    def woonlastenverzekering_ao(self) -> float:
        """Woonlastenverzekering AO bruto jaardekking (alle personen)."""
        return sum(v.dekking_ao for v in self.verzekeringen)

    @property
    def woonlastenverzekering_ww(self) -> float:
        """Woonlastenverzekering WW bruto jaardekking (alle personen)."""
        return sum(v.dekking_ww for v in self.verzekeringen)

    @property
    def beschikbare_buffer(self) -> float:
        """Restant liquide middelen na inbreng financiering.

        Buffer = (spaargeld + beleggingen + schenkingen) - eigen_middelen - schenking_inbreng.
        Kan ingezet worden om hypotheektekorten in risicoscenario's op te vangen.
        """
        liquide_types = {"spaargeld", "belegging", "schenking"}
        totaal = sum(v.saldo for v in self.vermogen if v.type.lower() in liquide_types)
        inbreng = self.financiering.eigen_middelen + self.financiering.schenking_inbreng
        return max(0, totaal - inbreng)


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


def _extract_extra_posten(items) -> list[dict]:
    """Extraheer extra posten array [{label, value}] → [{label: str, value: float}]."""
    if not items or not isinstance(items, list):
        return []
    result = []
    for item in items:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        value = _to_float(item.get("value"))
        if label and value > 0:
            result.append({"label": label, "value": value})
    return result


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
    "nieuwbouw_project": "Nieuwbouw (project)",
    "nieuwbouw_eigen_beheer": "Nieuwbouw (eigen beheer)",
}

# Burgerlijke staat mapping (Lovable dropdown: 'samenwonend' | 'gehuwd' | 'geregistreerd_partner')
BURGERLIJKE_STAAT_MAPPING = {
    "samenwonend": "Samenwonend",
    "gehuwd": "Gehuwd",
    "geregistreerd_partner": "Geregistreerd partnerschap",
    "geregistreerd_partnerschap": "Geregistreerd partnerschap",
    "alleenstaand": "Alleenstaand",
    "ongehuwd": "Ongehuwd",
    "gescheiden": "Gescheiden",
}

# Samenlevingsvorm mapping (Lovable: 'met_samenlevingscontract' | 'zonder_samenlevingscontract')
SAMENLEVINGSVORM_MAPPING = {
    "beperkte_gemeenschap": "Beperkte gemeenschap van goederen",
    "gemeenschap_van_goederen": "Gemeenschap van goederen",
    "huwelijkse_voorwaarden": "Huwelijkse voorwaarden",
    "partnerschap_voorwaarden": "Partnerschapsvoorwaarden",
    "partnerschapsvoorwaarden": "Partnerschapsvoorwaarden",
    "geregistreerd_partnerschap": "Geregistreerd partnerschap",
    "samenwonend": "Samenwonend",
    "met_samenlevingscontract": "Met samenlevingscontract",
    "zonder_samenlevingscontract": "Zonder samenlevingscontract",
    "buitenlands_recht": "Buitenlands recht",
}


def _map_woning_type(raw: str) -> str:
    """Map woning type naar display-naam. 'bestaande_bouw' → 'Bestaande bouw'."""
    if not raw:
        return "Bestaande bouw"
    return WONING_TYPE_MAPPING.get(raw, "Bestaande bouw")


# ─── Aanvraag-based extraction (PRIMAIRE BRON) ───


def _parse_datum(val) -> date | None:
    """Parse een datum string (YYYY-MM-DD of DD-MM-YYYY) naar date object."""
    if isinstance(val, date):
        return val
    if not val or not isinstance(val, str):
        return None
    val = val.strip()
    try:
        return date.fromisoformat(val)
    except ValueError:
        pass
    # DD-MM-YYYY fallback
    try:
        parts = val.split("-")
        if len(parts) == 3 and len(parts[0]) <= 2:
            return date(int(parts[2]), int(parts[1]), int(parts[0]))
    except (ValueError, IndexError):
        pass
    return None


def _get_einddatum(item: dict) -> date | None:
    """Haal einddatum op uit een inkomen-item (top-level of in type-specifieke data)."""
    d = _parse_datum(item.get("einddatum"))
    if d:
        return d
    for sub_key in ("anderInkomenData", "vermogenData"):
        sub = item.get(sub_key)
        if isinstance(sub, dict):
            d = _parse_datum(sub.get("einddatum"))
            if d:
                return d
    return None


def _heeft_einddatum(item: dict) -> bool:
    """Check of een inkomen-item een einddatum heeft.

    Inkomen met einddatum is per definitie tijdelijk en telt niet mee
    als permanent pensioeninkomen, ongeacht of de einddatum vóór of na
    de AOW-datum valt.
    """
    return _get_einddatum(item) is not None


def _extract_inkomen_from_aanvraag(items: list, aow_datum: date | None = None) -> NormalizedInkomen:
    """Extraheer inkomen uit aanvraag.data.inkomenAanvrager/inkomenPartner array.

    Structuur per item: { type, soort, jaarbedrag, isAOW, loondienst: { dienstverband: {...} } }
    Types: "loondienst", "uitkering" (met isAOW), "pensioen", "ander_inkomen"

    aow_datum: AOW-ingangsdatum van deze persoon. Wordt gebruikt om te bepalen
    of overig inkomen met einddatum nog doorloopt na AOW.
    """
    loondienst = 0
    onderneming = 0
    roz = 0
    aow = 0
    pensioen = 0
    nabestaandenpensioen = 0
    overig = 0
    overig_tijdelijk = 0  # Inkomen met einddatum → telt NIET mee na AOW
    uitkering = 0
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
                uitkering += jaarbedrag

        elif item_type == "pensioen":
            # Diagnostiek: dump pensioenData volledig
            pensioen_data = item.get("pensioenData")
            logger.info("Pensioen item: soort=%s, jaarbedrag=%.0f, pensioenData=%s",
                        item.get("soort", "?"), jaarbedrag, pensioen_data)

            # Nabestaandenpensioen: check soort veld of pensioenData
            soort = str(item.get("soort") or "").lower()
            if "nabestaanden" in soort or "partner" in soort:
                nabestaandenpensioen += jaarbedrag
            else:
                pensioen += jaarbedrag
                # Extraheer nabestaandenpensioen uit pensioenData.partnerpensioen
                # Velden: verzekerdVoor (vóór AOW), verzekerdVanaf (na AOW)
                pd = pensioen_data
                if isinstance(pd, str):
                    try:
                        import ast
                        pd = ast.literal_eval(pd)
                    except (ValueError, SyntaxError):
                        pd = None
                if isinstance(pd, dict):
                    pp = pd.get("partnerpensioen") or {}
                    if isinstance(pp, dict):
                        nb_bedrag = _to_float(
                            pp.get("verzekerdVoor") or pp.get("verzekerdVanaf")
                            or pp.get("verzekerd") or pp.get("jaarbedrag")
                        )
                        if nb_bedrag > 0:
                            nabestaandenpensioen += nb_bedrag
                            logger.info("Nabestaandenpensioen uit pensioenData: %.0f (voor=%.0f, vanaf=%.0f)",
                                        nb_bedrag,
                                        _to_float(pp.get("verzekerdVoor")),
                                        _to_float(pp.get("verzekerdVanaf")))

        elif item_type == "onderneming":
            onderneming += jaarbedrag
            dienstverband = "Onderneming"

        elif item_type == "vermogen":
            bedrag = jaarbedrag
            if not bedrag:
                vd = item.get("vermogenData") or {}
                bedrag = _to_float(vd.get("bedrag") or vd.get("jaarlijksBrutoInkomen"))
            if _heeft_einddatum(item):
                overig_tijdelijk += bedrag
            else:
                overig += bedrag

        elif item_type in ("ander_inkomen", "ander inkomen"):
            ai = item.get("anderInkomenData") or {}
            bedrag = jaarbedrag
            if not bedrag:
                bedrag = _to_float(ai.get("jaarlijksBrutoInkomen"))
            if _heeft_einddatum(item):
                overig_tijdelijk += bedrag
            else:
                overig += bedrag

        else:
            # Onbekend type — tel mee als overig, log waarschuwing
            if jaarbedrag > 0:
                logger.warning("Onbekend inkomentype '%s' met bedrag %.0f → overig", item_type, jaarbedrag)
                overig += jaarbedrag

    inkomen = NormalizedInkomen(
        loondienst=loondienst,
        onderneming=onderneming,
        roz=roz,
        aow_uitkering=aow,
        pensioen=pensioen,
        nabestaandenpensioen=nabestaandenpensioen,
        overig=overig,
        overig_tijdelijk=overig_tijdelijk,
        uitkering=uitkering,
    )

    logger.debug(
        "Inkomen (aanvraag): loondienst=%.0f, onderneming=%.0f, aow=%.0f, "
        "pensioen=%.0f, nabestaandenpensioen=%.0f, overig=%.0f, uitkering=%.0f, dienstverband=%s",
        loondienst, onderneming, aow, pensioen, nabestaandenpensioen,
        overig, uitkering, dienstverband,
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

    # AOW-datum berekenen voor einddatum-vergelijking in inkomen
    aow_datum = None
    geb_date = _parse_datum(geboortedatum)
    if geb_date:
        aow_datum = bereken_aow_datum(geb_date)

    # Inkomen uit array
    inkomen = _extract_inkomen_from_aanvraag(inkomen_items, aow_datum=aow_datum)

    # Eerder gehuwd / weduwe (#5, #6)
    eerder_gehuwd = bool(persoon.get("eerderGehuwd") or persoon.get("eerder_gehuwd"))
    datum_echtscheiding = str(persoon.get("datumEchtscheiding") or persoon.get("datum_echtscheiding") or "")
    weduwe_weduwnaar = bool(persoon.get("weduweWeduwnaar") or persoon.get("weduwe") or persoon.get("isWeduweWeduwnaar"))

    # Dienstverband + flexibel inkomen + arbeidsmarktscan uit loondienst items (#23, #24)
    dienstverband = "Loondienst"
    flexibel_inkomen_3j = False
    arbeidsmarktscan_fase = ""
    for item in (inkomen_items or []):
        if str(item.get("type", "")).lower() == "loondienst":
            ld_data = item.get("loondienst") or {}
            dv_data = ld_data.get("dienstverband") or {}
            soort = str(dv_data.get("soortDienstverband", "")).lower()
            if "onderneming" in soort:
                dienstverband = "Onderneming"
            elif "roz" in soort:
                dienstverband = "ROZ"
            # Flexibel inkomen (3 jaar) en arbeidsmarktscan
            flexibel_inkomen_3j = bool(
                dv_data.get("flexibelInkomen")
                or dv_data.get("flexibelInkomenDrieJaar")
                or dv_data.get("isFlexibel")
                or ld_data.get("flexibelInkomen")
            )
            arbeidsmarktscan_fase = str(
                dv_data.get("arbeidsmarktscanFase")
                or dv_data.get("arbeidsmarktscan")
                or ld_data.get("arbeidsmarktscanFase")
                or item.get("arbeidsmarktscanFase")
                or ""
            )
            break

    return NormalizedPersoon(
        naam=naam,
        voornaam=roepnaam,
        voorletters_achternaam=voorletters_achternaam,
        geboortedatum=geboortedatum,
        adres=adres,
        postcode_plaats=postcode_plaats,
        telefoon=telefoon,
        email=email,
        inkomen=inkomen,
        dienstverband=dienstverband,
        eerder_gehuwd=eerder_gehuwd,
        datum_echtscheiding=datum_echtscheiding,
        weduwe_weduwnaar=weduwe_weduwnaar,
        flexibel_inkomen_3j=flexibel_inkomen_3j,
        arbeidsmarktscan_fase=arbeidsmarktscan_fase,
    )


def _extract_financiering_from_aanvraag(aanvraag_data: dict) -> NormalizedFinanciering:
    """Extraheer financiering uit aanvraag.data.financieringsopzet + onderpand."""
    fin = aanvraag_data.get("financieringsopzet") or {}
    onderpand = aanvraag_data.get("onderpand") or {}
    samenstellen = aanvraag_data.get("samenstellenHypotheek") or {}

    koopsom = _to_float(fin.get("aankoopsomWoning"))
    eigen_geld = _to_float(fin.get("eigenGeld"))
    schenking_inbreng = _to_float(fin.get("schenkingLening") or fin.get("schenking"))
    overwaarde = _to_float(fin.get("overwaarde"))

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
    aankoopmakelaar = _to_float(fin.get("aankoopmakelaar"))
    consumptief = _to_float(fin.get("consumptief"))

    # Nieuwbouw project
    koopsom_grond = _to_float(fin.get("koopsomGrond"))
    aanneemsom = _to_float(fin.get("aanneemsom"))
    meerwerk_opties = _to_float(fin.get("meerwerkOpties") or fin.get("meerwerk"))
    meerwerk_eigen = _to_float(fin.get("meerwerkEigenBeheer"))
    meerwerk = meerwerk_opties + meerwerk_eigen
    bouwrente = _to_float(fin.get("bouwrente"))

    # Nieuwbouw eigen beheer
    koopsom_kavel = _to_float(fin.get("koopsomKavel"))
    sloop_oude_woning = _to_float(fin.get("sloopOudeWoning"))
    bouw_woning = _to_float(fin.get("bouwWoning"))

    # Extra posten (custom arrays)
    extra_posten_aankoop = _extract_extra_posten(fin.get("extraPostenAankoop"))
    extra_posten_kosten = _extract_extra_posten(fin.get("extraPostenKosten"))
    extra_posten_eigen_middelen = _extract_extra_posten(fin.get("extraPostenEigenMiddelen"))

    notariskosten = hypotheekakte + transportakte
    kosten_koper = (
        overdrachtsbelasting + bankgarantie + notariskosten
        + taxatiekosten + advies_bemiddeling + nhg_kosten
        + aankoopmakelaar
        + sum(ep["value"] for ep in extra_posten_kosten)
    )

    # Woningwaarde uit onderpand (marktwaarde)
    woningwaarde = _to_float(onderpand.get("marktwaarde")) or koopsom

    # WOZ-waarde uit onderpand
    woz_waarde = _to_float(onderpand.get("wozWaarde") or onderpand.get("woz_waarde"))

    # Energielabel uit onderpand
    energielabel = str(onderpand.get("energielabel") or "Geen (geldig) Label")

    # Type woning
    woning_type_raw = str(fin.get("woningType") or "").lower().strip()
    type_woning = _map_woning_type(woning_type_raw)

    # Onderpand adres (inclusief huisnummer + toevoeging)
    straat = str(onderpand.get("straat") or "").strip()
    huisnr = str(onderpand.get("huisnummer") or "").strip()
    toevoeging = str(onderpand.get("toevoeging") or onderpand.get("huisnummerToevoeging") or "").strip()
    postcode = str(onderpand.get("postcode") or "").strip()
    woonplaats = str(onderpand.get("woonplaats") or "").strip()
    straat_deel = f"{straat} {huisnr}".strip()
    if toevoeging:
        straat_deel = f"{straat_deel}{toevoeging}"
    postcode_deel = f"{postcode} {woonplaats}".strip()
    adres = f"{straat_deel}, {postcode_deel}".strip(", ")

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

    # Onderpand detail (#66-68, #70)
    plannummer = str(
        onderpand.get("plannummerProject") or onderpand.get("plannummer")
        or onderpand.get("planNummer") or ""
    ).strip()
    bouwnummer = str(
        onderpand.get("bouwnummerOnderpand") or onderpand.get("bouwnummer")
        or onderpand.get("bouwNummer") or ""
    ).strip()
    erfpacht_onderpand = bool(onderpand.get("erfpacht") or onderpand.get("heeftErfpacht"))
    erfpachtcanon_onderpand = _to_float(
        onderpand.get("jaarlijkseErfpacht") or onderpand.get("erfpachtcanon")
        or onderpand.get("canonPerJaar") or onderpand.get("groundLeaseAnnual")
    )
    marktwaarde_na_verbouwing = _to_float(
        onderpand.get("marktwaardeNaVerbouwing") or onderpand.get("marketValueAfterRenovation")
    )
    eigendom_aanvrager = _to_float(onderpand.get("eigendomAanvrager") or onderpand.get("eigendomsverhouding_aanvrager") or fin.get("eigendomAanvrager"))
    eigendom_partner = _to_float(onderpand.get("eigendomPartner") or onderpand.get("eigendomsverhouding_partner") or fin.get("eigendomPartner"))
    if eigendom_aanvrager == 0 and eigendom_partner == 0:
        eigendom_aanvrager = 50
        eigendom_partner = 50

    # Wijziging financieringsopzet (#74-77)
    boeterente = _to_float(fin.get("boeterente") or fin.get("penaltyInterest"))
    uitkoop_partner = _to_float(fin.get("uitkoopPartner") or fin.get("uitkoop"))
    afkoop_erfpacht = _to_float(fin.get("afkoopErfpacht"))
    oversluiten_leningen = _to_float(fin.get("oversluitenLeningen") or fin.get("aflossenLeningen"))

    return NormalizedFinanciering(
        koopsom=koopsom,
        kosten_koper=kosten_koper,
        eigen_middelen=eigen_geld,
        schenking_inbreng=schenking_inbreng,
        overwaarde=overwaarde,
        woningwaarde=woningwaarde,
        woz_waarde=woz_waarde,
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
        aankoopmakelaar=aankoopmakelaar,
        consumptief=consumptief,
        koopsom_grond=koopsom_grond,
        aanneemsom=aanneemsom,
        meerwerk=meerwerk,
        bouwrente=bouwrente,
        koopsom_kavel=koopsom_kavel,
        sloop_oude_woning=sloop_oude_woning,
        bouw_woning=bouw_woning,
        extra_posten_aankoop=extra_posten_aankoop,
        extra_posten_kosten=extra_posten_kosten,
        extra_posten_eigen_middelen=extra_posten_eigen_middelen,
        plannummer=plannummer,
        bouwnummer=bouwnummer,
        erfpacht_onderpand=erfpacht_onderpand,
        erfpachtcanon_onderpand=erfpachtcanon_onderpand,
        marktwaarde_na_verbouwing=marktwaarde_na_verbouwing,
        eigendom_aanvrager=eigendom_aanvrager,
        eigendom_partner=eigendom_partner,
        boeterente=boeterente,
        uitkoop_partner=uitkoop_partner,
        afkoop_erfpacht=afkoop_erfpacht,
        oversluiten_leningen=oversluiten_leningen,
    )


def _extract_financiering_from_wijziging(aanvraag_data: dict) -> NormalizedFinanciering:
    """Extraheer financiering uit aanvraag.data.wijzigingFinancieringsopzet + onderpand.

    Wijziging-flows (verhogen, oversluiten, uitkopen) gebruiken een andere
    data-structuur dan aankoop-flows.
    """
    wf = aanvraag_data.get("wijzigingFinancieringsopzet") or {}
    onderpand = aanvraag_data.get("onderpand") or {}
    samenstellen = aanvraag_data.get("samenstellenHypotheek") or {}

    # Doelstelling: "hypotheek-oversluiten", "hypotheek-verhogen", "partner-uitkopen"
    doelstelling = str(
        aanvraag_data.get("doelstelling")
        or aanvraag_data.get("doelstellingType")
        or ""
    ).strip()

    # Investering posten
    huidige_hypotheek = _to_float(wf.get("huidigeHypotheek"))
    verbouwing = _to_float(wf.get("verbouwing"))
    ebv = _to_float(wf.get("ebv"))
    ebb = _to_float(wf.get("ebb"))
    ebv_ebb = ebv + ebb
    afkoop_erfpacht = _to_float(wf.get("afkoopErfpacht"))
    oversluiten_leningen = _to_float(wf.get("oversluitenLeningen"))
    consumptief = _to_float(wf.get("consumptief"))
    uitkoop_partner = _to_float(wf.get("uitkoopPartner"))
    boeterente = _to_float(wf.get("boeterente"))

    # Kosten
    advies_bemiddeling = _to_float(wf.get("adviesBemiddeling"))
    hypotheekakte = _to_float(wf.get("hypotheekakte"))
    taxatiekosten = _to_float(wf.get("taxatiekosten"))
    nhg_kosten = _to_float(wf.get("nhgKosten"))

    extra_posten_aankoop = _extract_extra_posten(wf.get("extraPostenInvestering"))
    extra_posten_kosten = _extract_extra_posten(wf.get("extraPostenKosten"))
    extra_posten_eigen_middelen = _extract_extra_posten(wf.get("extraPostenEigenMiddelen"))

    notariskosten = hypotheekakte  # geen transportakte bij wijziging
    kosten_koper = (
        advies_bemiddeling + notariskosten + taxatiekosten + nhg_kosten
        + sum(ep["value"] for ep in extra_posten_kosten)
    )

    eigen_geld = _to_float(wf.get("eigenGeld"))

    # Onderpand (zelfde structuur als aankoop)
    woningwaarde = _to_float(onderpand.get("marktwaarde"))
    woz_waarde = _to_float(wf.get("wozWaarde") or onderpand.get("wozWaarde") or onderpand.get("woz_waarde"))
    energielabel = str(onderpand.get("energielabel") or "Geen (geldig) Label")

    # Type woning — bij wijziging is het altijd bestaande bouw
    type_woning = "Bestaande bouw"

    # Adres uit onderpand
    straat = str(onderpand.get("straat") or "").strip()
    huisnr = str(onderpand.get("huisnummer") or "").strip()
    toevoeging = str(onderpand.get("toevoeging") or onderpand.get("huisnummerToevoeging") or "").strip()
    postcode = str(onderpand.get("postcode") or "").strip()
    woonplaats = str(onderpand.get("woonplaats") or "").strip()
    straat_deel = f"{straat} {huisnr}".strip()
    if toevoeging:
        straat_deel = f"{straat_deel}{toevoeging}"
    postcode_deel = f"{postcode} {woonplaats}".strip()
    adres = f"{straat_deel}, {postcode_deel}".strip(", ")

    # Hypotheekverstrekker + NHG
    hypotheekverstrekker = str(samenstellen.get("geldverstrekker") or "")
    nhg = bool(samenstellen.get("nhg", True))

    # Onderpand detail
    plannummer = str(onderpand.get("plannummerProject") or onderpand.get("plannummer") or "").strip()
    bouwnummer = str(onderpand.get("bouwnummerOnderpand") or onderpand.get("bouwnummer") or "").strip()
    erfpacht_onderpand = bool(onderpand.get("erfpacht") or onderpand.get("heeftErfpacht"))
    erfpachtcanon_onderpand = _to_float(
        onderpand.get("jaarlijkseErfpacht") or onderpand.get("erfpachtcanon") or onderpand.get("canonPerJaar")
    )
    marktwaarde_na_verbouwing = _to_float(onderpand.get("marktwaardeNaVerbouwing"))
    eigendom_aanvrager = _to_float(onderpand.get("eigendomAandeelAanvrager") or onderpand.get("eigendomAanvrager") or wf.get("eigendomAanvrager"))
    eigendom_partner = _to_float(onderpand.get("eigendomAandeelPartner") or onderpand.get("eigendomPartner") or wf.get("eigendomPartner"))
    if eigendom_aanvrager == 0 and eigendom_partner == 0:
        eigendom_aanvrager = 50
        eigendom_partner = 50

    # Overbrugging: zoek in leningdelen
    overbrugging = _to_float(wf.get("overbrugging"))

    logger.debug(
        "Financiering (wijziging): huidige_hyp=%.0f, verbouwing=%.0f, kosten=%.0f, "
        "eigen_geld=%.0f, adres=%s, verstrekker=%s",
        huidige_hypotheek, verbouwing, kosten_koper, eigen_geld,
        adres or "(leeg)", hypotheekverstrekker,
    )

    return NormalizedFinanciering(
        koopsom=huidige_hypotheek,  # bij wijziging fungeert huidigeHypotheek als "koopsom"
        kosten_koper=kosten_koper,
        eigen_middelen=eigen_geld,
        schenking_inbreng=0,   # niet beschikbaar bij wijziging
        overwaarde=0,          # niet beschikbaar bij wijziging
        woningwaarde=woningwaarde,
        woz_waarde=woz_waarde,
        energielabel=energielabel,
        type_woning=type_woning,
        adres=adres,
        nhg=nhg,
        hypotheekverstrekker=hypotheekverstrekker,
        overdrachtsbelasting=0,
        notariskosten=notariskosten,
        taxatiekosten=taxatiekosten,
        advies_bemiddeling=advies_bemiddeling,
        nhg_kosten=nhg_kosten,
        bankgarantie=0,
        verbouwing=verbouwing,
        ebv_ebb=ebv_ebb,
        ebv=ebv,
        ebb=ebb,
        overbrugging=overbrugging,
        aankoopmakelaar=0,
        consumptief=consumptief,
        koopsom_grond=0,
        aanneemsom=0,
        meerwerk=0,
        bouwrente=0,
        koopsom_kavel=0,
        sloop_oude_woning=0,
        bouw_woning=0,
        extra_posten_aankoop=extra_posten_aankoop,
        extra_posten_kosten=extra_posten_kosten,
        extra_posten_eigen_middelen=extra_posten_eigen_middelen,
        plannummer=plannummer,
        bouwnummer=bouwnummer,
        erfpacht_onderpand=erfpacht_onderpand,
        erfpachtcanon_onderpand=erfpachtcanon_onderpand,
        marktwaarde_na_verbouwing=marktwaarde_na_verbouwing,
        eigendom_aanvrager=eigendom_aanvrager,
        eigendom_partner=eigendom_partner,
        boeterente=boeterente,
        uitkoop_partner=uitkoop_partner,
        afkoop_erfpacht=afkoop_erfpacht,
        oversluiten_leningen=oversluiten_leningen,
        is_wijziging=True,
        doelstelling=doelstelling,
    )


def _extract_leningdelen_from_aanvraag(aanvraag_data: dict) -> tuple[list["NormalizedLeningdeel"], bool]:
    """Extraheer leningdelen uit aanvraag.data.samenstellenHypotheek.

    Combineert bestaandeLeningdelen + meenemenLeningdelen + nieuweLeningdelen
    + leningdelenElders (als meenemenInToetsing=true).
    Deduplicatie op basis van `id` veld (bestaande heeft prioriteit boven meenemen).
    Structuur per deel: { bedrag, aflosvorm, rentePercentage, looptijd, box, renteVastPeriode }

    Returns:
        (leningdelen, had_bestaande): tuple met de lijst EN een flag die aangeeft
        of bestaandeLeningdelen aanwezig waren (= bestaande hypotheek zit al IN de
        leningdelen, dus NIET apart optellen via fin.koopsom).
    """
    samenstellen = aanvraag_data.get("samenstellenHypotheek") or {}
    bestaande = samenstellen.get("bestaandeLeningdelen") or []
    meenemen = samenstellen.get("meenemenLeningdelen") or []
    nieuw = samenstellen.get("nieuweLeningdelen") or []
    all_elders = samenstellen.get("leningdelenElders") or []

    had_bestaande = len(bestaande) > 0

    # Bouw geordende lijst met herkomst per deel
    ordered: list[tuple[dict, str]] = []
    for d in bestaande:
        ordered.append((d, "bestaand"))
    for d in meenemen:
        ordered.append((d, "meenemen"))
    for d in nieuw:
        ordered.append((d, "nieuw"))
    for d in all_elders:
        ordered.append((d, "elders"))

    # Dedup op id: bestaande > meenemen > nieuw > elders
    seen_ids: set[str] = set()
    alle_delen: list[tuple[dict, str]] = []
    for deel, herkomst in ordered:
        deel_id = deel.get("id", "")
        if deel_id and deel_id in seen_ids:
            continue
        if deel_id:
            seen_ids.add(deel_id)
        alle_delen.append((deel, herkomst))

    if not alle_delen:
        return [], had_bestaande

    logger.info("Leningdelen (aanvraag): %d bestaande + %d meenemen + %d nieuw + %d elders = %d (na dedup)",
                len(bestaande), len(meenemen), len(nieuw), len(all_elders), len(alle_delen))

    result = []
    for deel, herkomst in alle_delen:
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

        # meenemenInToetsing toggle (alleen relevant voor elders)
        meenemen_in_toetsing = True
        if herkomst == "elders":
            meenemen_in_toetsing = bool(deel.get("meenemenInToetsing", False))

        ld = NormalizedLeningdeel(
            aflos_type=_map_aflosvorm(raw_aflosvorm),
            bedrag_box1=0 if is_box3 else bedrag,
            bedrag_box3=bedrag if is_box3 else 0,
            werkelijke_rente=_normalize_rente(rente_raw),
            org_lpt=looptijd,
            rest_lpt=looptijd,
            rvp=rvp_maanden,
            is_overbrugging=False,
            herkomst=herkomst,
            meenemen_in_toetsing=meenemen_in_toetsing,
        )
        result.append(ld)

    return result, had_bestaande


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
            # Format geboortedatum als DD-MM-YYYY
            geb_display = geb
            if geb:
                try:
                    from datetime import date as dt_date_fmt
                    geb_display = dt_date_fmt.fromisoformat(geb).strftime("%d-%m-%Y")
                except (ValueError, TypeError):
                    pass
            kinderen.append(f"{naam} ({geb_display})" if geb else naam)
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
    datum = str(
        wg.get("datumInDienst") or wg.get("datum_in_dienst")
        or wg.get("inDienstSinds")  # Lovable veldnaam
        or ""
    ).strip()

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
                    vp.get("orvDekking") or vp.get("dekking") or vp.get("uitkering")
                )
                dekking_aov = _to_float(vp.get("dekkingAOV"))
                dekking_ao = _to_float(vp.get("dekkingAO"))
                dekking_ww = _to_float(vp.get("dekkingWW"))
                result.append(NormalizedVerzekering(
                    type=vtype,
                    aanbieder=aanbieder,
                    polisnummer=polisnummer,
                    verzekerde=verzekerde,
                    dekking=dekking,
                    dekking_aov=dekking_aov,
                    dekking_ao=dekking_ao,
                    dekking_ww=dekking_ww,
                    soort_dekking=soort_dekking,
                    einddatum=einddatum,
                ))
        else:
            # Flat structuur (fallback)
            verzekerde = str(
                item.get("verzekerde") or item.get("verzekerdeNaam") or ""
            ).strip()
            dekking = _to_float(
                item.get("orvDekking") or item.get("dekking") or item.get("uitkering")
            )
            result.append(NormalizedVerzekering(
                type=vtype,
                aanbieder=aanbieder,
                polisnummer=polisnummer,
                verzekerde=verzekerde,
                dekking=dekking,
                dekking_aov=_to_float(item.get("dekkingAOV")),
                dekking_ao=_to_float(item.get("dekkingAO")),
                dekking_ww=_to_float(item.get("dekkingWW")),
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
        erfpachtcanon = _to_float(
            w.get("jaarlijkseErfpacht")  # Lovable veldnaam
            or w.get("erfpachtcanon") or w.get("erfpachtCanon")
            or w.get("canonPerJaar") or w.get("canonBedrag") or w.get("canon")
        )
        energielabel = str(w.get("energielabel") or "").strip()

        # Eigenaar / eigendomsverhouding / woontoepassing / huur (#37-39, #42)
        eigenaar = str(w.get("eigenaar") or w.get("eigenaarWoning") or "").strip()
        eigendom_aanvrager = _to_float(w.get("eigendomAanvrager") or w.get("eigendomsverhouding_aanvrager"))
        eigendom_partner = _to_float(w.get("eigendomPartner") or w.get("eigendomsverhouding_partner"))
        woontoepassing = str(w.get("woontoepassing") or w.get("woningToepassing") or "").strip()
        huur_per_maand = _to_float(
            w.get("huurPerMaand") or w.get("huurBedrag")
            or w.get("maandelijkseHuur") or w.get("huur")
        )

        result.append(NormalizedBestaandeWoning(
            adres=adres,
            postcode_plaats=postcode_plaats,
            type_woning=type_woning,
            marktwaarde=marktwaarde,
            woz_waarde=woz_waarde,
            status=status,
            erfpacht=erfpacht,
            erfpachtcanon=erfpachtcanon,
            energielabel=energielabel,
            eigenaar=eigenaar,
            eigendom_aanvrager=eigendom_aanvrager,
            eigendom_partner=eigendom_partner,
            woontoepassing=woontoepassing,
            huur_per_maand=huur_per_maand,
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
        "aflopend_krediet": "Aflopend krediet",
        "persoonlijke_lening": "Persoonlijke lening",
        "private_lease": "Private lease",
        "huurkoop": "Huurkoop/Private lease",
        "partneralimentatie": "Partneralimentatie",
        "creditcard": "Creditcard",
    }

    for item in items:
        vtype = str(item.get("type") or "").strip()
        maandbedrag = _to_float(
            item.get("maandbedrag") or item.get("maandlast")
        )
        saldo = _to_float(
            item.get("saldo")
            or item.get("nogAfTeLossen")    # Lovable: aflopend krediet
            or item.get("nogTeBetalen")     # Lovable: aflopend krediet
            or item.get("kredietbedrag")    # Lovable: doorlopend krediet limiet
            or item.get("restantBedrag") or item.get("restschuld")
            or item.get("restantSaldo")
        )
        omschrijving = str(
            item.get("omschrijving") or item.get("naam")
            or item.get("maatschappij") or item.get("verstrekker") or ""
        ).strip()
        # Aparte maatschappij: als omschrijving leeg is maar maatschappij gevuld
        maatschappij = str(
            item.get("maatschappij") or item.get("verstrekker") or ""
        ).strip()
        # Als omschrijving ontbreekt maar maatschappij bestaat, gebruik die
        if not omschrijving and maatschappij:
            omschrijving = maatschappij

        result.append({
            "type": TYPE_DISPLAY.get(vtype, vtype.replace("_", " ").capitalize()),
            "maandbedrag": maandbedrag,
            "saldo": saldo,
            "omschrijving": omschrijving,
            "maatschappij": maatschappij,
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

    roepnaam = str(_get(klant, f"roepnaam{suffix_camel}") or
                   _get(contact, "voornaam") or "").strip()
    naam = str(_get(klant, f"naam{suffix_camel}", f"naam_{suffix_lower}") or "").strip()
    if not naam:
        tussenvoegsel = str(_get(klant, f"tussenvoegsel{suffix_camel}") or
                            _get(contact, "tussenvoegsel") or "").strip()
        achternaam = str(_get(klant, f"achternaam{suffix_camel}") or
                         _get(contact, "achternaam") or "").strip()
        parts = [p for p in [roepnaam, tussenvoegsel, achternaam] if p]
        naam = " ".join(parts)
    if not roepnaam and naam:
        roepnaam = naam.split()[0]

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
        voornaam=roepnaam,
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
    schenking_inbreng = _to_float(
        _get(fin, "schenkingLening", "schenking")
        or _get(ber, "schenkingLening", "schenking")
    )
    woningwaarde = _to_float(
        _get(haalb_onderpand, "marktwaarde")
        or _get(ber, "woningwaarde", "marktwaarde")
        or _get(fin, "woningwaarde", "marktwaarde")
        or _get(invoer, "woningwaarde")
    ) or koopsom

    woz_waarde = _to_float(
        _get(haalb_onderpand, "wozWaarde", "woz_waarde")
        or _get(ber, "wozWaarde", "woz_waarde")
        or _get(invoer, "wozWaarde", "woz_waarde")
    )

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
        schenking_inbreng=schenking_inbreng,
        woningwaarde=woningwaarde,
        woz_waarde=woz_waarde,
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

    # Diagnostic: dump veldnamen van woningen, verplichtingen, verzekeringen
    if has_aanvraag:
        for i, w in enumerate(aanvraag_data.get("woningen") or []):
            logger.info("  woningen[%d] keys=%s, erfpacht=%s, jaarlijkseErfpacht=%s",
                        i, sorted(w.keys()), w.get("erfpacht"), w.get("jaarlijkseErfpacht"))
        for i, v in enumerate(aanvraag_data.get("verplichtingen") or []):
            logger.info("  verplichtingen[%d] type=%s, keys=%s, saldo=%s, nogAfTeLossen=%s",
                        i, v.get("type"), sorted(v.keys()), v.get("saldo"), v.get("nogAfTeLossen"))
        voorz = (aanvraag_data.get("voorzieningen") or {}).get("verzekeringen") or []
        for i, vz in enumerate(voorz):
            logger.info("  verzekeringen[%d] type=%s, keys=%s", i, vz.get("type"), sorted(vz.keys()))

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
    had_bestaande = False
    if has_aanvraag:
        leningdelen, had_bestaande = _extract_leningdelen_from_aanvraag(aanvraag_data)
    if not has_aanvraag or not leningdelen:
        # Fallback naar dossier scenario1
        had_bestaande = False
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
    elif has_aanvraag and aanvraag_data.get("wijzigingFinancieringsopzet"):
        financiering = _extract_financiering_from_wijziging(aanvraag_data)
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
        burgerlijke_staat = BURGERLIJKE_STAAT_MAPPING.get(
            bs_raw.lower().strip(),
            bs_raw.replace("_", " ").title() if bs_raw else ("Alleenstaand" if alleenstaand else "Gehuwd")
        )

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
        bestaande_in_leningdelen=had_bestaande,
    )

    logger.info(
        "Dossier genormaliseerd: alleenstaand=%s, leningdelen=%d, hypotheek=%.0f, "
        "bestaande_in_ld=%s, bron=%s",
        alleenstaand, len(leningdelen), data.hypotheek_bedrag,
        had_bestaande, "aanvraag" if has_aanvraag else "dossier",
    )

    return data
