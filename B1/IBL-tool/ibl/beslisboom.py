"""Beslisboom: orchestratie van de IBL-berekening conform §3 Rekenregels v8.1.1."""

from decimal import Decimal
from datetime import date, timedelta

from .models import (
    ContractBlok, SamengevoegdContract, LoonItem,
    Contractvorm, Betaaltermijn, BerekeningType,
    IBLResultaat, Tussenresultaat,
    UWV_UITKERING_LOONHEFFINGENNUMMERS,
    GRENSWAARDE_BESTENDIGHEID_STIJGING,
    URENGRENS_MAANDELIJKS, URENGRENS_VIERWEKELIJKS,
    jaar_perioden, perioden_voor,
)
from .preprocessing import samenvoeg_contracten, pas_verlofregel_toe
from .berekeningen import bereken_a, bereken_b, bereken_c, bereken_d

ZERO = Decimal("0")


# ---------------------------------------------------------------------------
# Bestendigheidstoets  (§3.7)
# ---------------------------------------------------------------------------

def bestendigheidstoets_criterium1(
    items: list[LoonItem],
    betaaltermijn: Betaaltermijn,
) -> tuple[bool, Decimal]:
    """§3.7.1: Maximale inkomensstijging ≤ 120 %.

    ijr1 = ∑(sv_loon - waarde_privegebruik + eigen_bijdrage) recent 12 periodes
    ijr2 = idem voorgaande 12 periodes
    Ratio = ijr1 / ijr2 × 100 %

    NB: Auto van de zaak wordt NIET op 0 gesteld bij negatief saldo.

    Returns: (geslaagd, ratio)
    """
    jp = jaar_perioden(betaaltermijn)

    if len(items) < 2 * jp:
        # Te weinig data → slaagt automatisch
        return True, ZERO

    def _netto_inkomen(li: LoonItem) -> Decimal:
        """SV-loon gecorrigeerd voor auto (zonder floor op 0)."""
        return li.sv_loon - li.netto_bijtelling

    ijr1 = sum(_netto_inkomen(items[i]) for i in range(jp))
    ijr2 = sum(_netto_inkomen(items[i]) for i in range(jp, 2 * jp))

    if ijr2 <= ZERO:
        return True, ZERO

    ratio = ijr1 / ijr2 * Decimal("100")

    geslaagd = ratio <= GRENSWAARDE_BESTENDIGHEID_STIJGING
    return geslaagd, ratio


def bestendigheidstoets_criterium2(
    items: list[LoonItem],
    betaaltermijn: Betaaltermijn,
) -> bool:
    """§3.7.2: Controle op Niet Bestendige Pieken.

    Per periode in jaar 1: controleer of er niet-bestendige pieken zijn.
    Returns True als het inkomen bestendig is (geen niet-bestendige pieken).
    """
    jp = jaar_perioden(betaaltermijn)

    if len(items) < jp + 2:
        return True

    def _sv(idx: int) -> Decimal:
        if 0 <= idx < len(items):
            sv = items[idx].sv_loon
            return sv if sv != ZERO else Decimal("0.01")
        return Decimal("0.01")

    for i in range(min(jp, len(items))):
        # Stap 1: V1 = SV[i] / SV[i+1]
        sv_i = _sv(i)
        sv_i1 = _sv(i + 1)
        v1 = sv_i / sv_i1

        if v1 <= Decimal("1.3"):
            continue  # Geen piek in deze periode

        # Stap 2: V2 = SV[i+jp] / SV[i+jp+1]
        if i + jp + 1 < len(items):
            sv_ref = _sv(i + jp)
            sv_ref1 = _sv(i + jp + 1)
            v2 = sv_ref / sv_ref1
            if v2 <= Decimal("1.3"):
                return False  # Niet bestendig

        # Stap 3: MAX(SV[i], SV[i+jp]) / MIN(SV[i], SV[i+jp])
        if i + jp < len(items):
            sv_jr = _sv(i + jp)
            max_v = max(sv_i, sv_jr)
            min_v = min(sv_i, sv_jr)
            if min_v <= ZERO:
                min_v = Decimal("0.01")
            if max_v / min_v > Decimal("1.3"):
                return False  # Niet bestendig

        # Stap 4: Dubbele piek controle
        if i > 0:  # Niet mogelijk voor meest recente periode (i=0)
            sv_later = _sv(i - 1)   # N+1 (recenter)
            sv_eerder = _sv(i + 1)  # N-1 (ouder)
            if sv_eerder > ZERO:
                v4a = sv_later / sv_eerder
                if v4a > Decimal("1.3"):
                    # Stap 4b: definitieve controle dubbele piek
                    if i - 1 + jp < len(items):
                        sv_later_jr = _sv(i - 1 + jp)
                        max_v = max(sv_later, sv_later_jr)
                        min_v = min(sv_later, sv_later_jr)
                        if min_v <= ZERO:
                            min_v = Decimal("0.01")
                        if max_v / min_v > Decimal("1.3"):
                            return False  # Dubbele piek, niet bestendig

    return True  # Bestendig


# ---------------------------------------------------------------------------
# §3.1 — Werkt aanvrager in loondienst?
# ---------------------------------------------------------------------------

def _werkt_in_loondienst(
    contract_blokken: list[ContractBlok],
    algemeen_mrl_datum: date,
    aanmaakdatum: date,
) -> tuple[bool, list[str]]:
    """§3.1: Controleer of aanvrager in loondienst werkt.

    Drie criteria:
    1. AMRL einddatum niet te oud (max 2 periodes van aanmaakdatum)
    2. Minimaal 1 contract dat AMRL levert is geen UWV-uitkering
    3. Bij minimaal 1 AMRL-contract zijn uren > 0

    Returns: (geslaagd, lijst_waarschuwingen)
    """
    waarschuwingen: list[str] = []

    # Criterium 1: AMRL niet te oud
    dagen_verschil = (aanmaakdatum - algemeen_mrl_datum).days
    if dagen_verschil > 62:  # ~2 maanden
        waarschuwingen.append(
            "§3.1 criterium 1: AMRL einddatum te oud "
            f"({algemeen_mrl_datum}, {dagen_verschil} dagen voor aanmaakdatum)."
        )
        return False, waarschuwingen

    # Bepaal welke blokken bijdragen aan AMRL (MRL = AMRL)
    amrl_blokken = []
    for blok in contract_blokken:
        if blok.loon_items:
            blok_mrl = max(li.periode_eind for li in blok.loon_items)
            if blok_mrl == algemeen_mrl_datum:
                amrl_blokken.append(blok)

    # Criterium 2: Minimaal 1 AMRL-blok is geen UWV-uitkering
    heeft_niet_uwv = any(not blok.is_uitkering_uwv for blok in amrl_blokken)
    if not heeft_niet_uwv:
        waarschuwingen.append(
            "§3.1 criterium 2: Alle contracten met AMRL zijn UWV-uitkeringen. "
            "Aanvrager werkt niet in loondienst."
        )
        return False, waarschuwingen

    # Criterium 3: Minimaal 1 AMRL-blok (niet-UWV) heeft uren > 0
    heeft_uren = False
    for blok in amrl_blokken:
        if not blok.is_uitkering_uwv:
            mrl_items = [
                li for li in blok.loon_items
                if li.periode_eind == algemeen_mrl_datum
            ]
            if any(li.aantal_uur > ZERO for li in mrl_items):
                heeft_uren = True
                break

    if not heeft_uren:
        waarschuwingen.append(
            "§3.1 criterium 3: Geen uren > 0 bij AMRL-contracten (niet-uitkering)."
        )
        return False, waarschuwingen

    return True, []


# ---------------------------------------------------------------------------
# §3.2.3 — Aanvullende urencriteria
# ---------------------------------------------------------------------------

def _aanvullende_urencriteria(
    contracten: list[SamengevoegdContract],
    algemeen_mrl_datum: date,
) -> tuple[bool, list[str]]:
    """§3.2.3: Drie aanvullende urencriteria op totaalniveau.

    Check 1: 0 uren in een van de 3 meest recente periodes → geen IBL
    Check 2: Geen loonitems in eerste 3 periodes → geen IBL
    Check 3: Negatieve uren in eerste 4 mnd / 5 vierwekelijkse periodes → geen IBL

    Returns: (geslaagd, lijst_waarschuwingen)
    """
    waarschuwingen: list[str] = []

    # Verzamel alle items van actieve contracten, meest recent eerst
    alle_items: list[LoonItem] = []
    for c in contracten:
        if c.is_actief:
            alle_items.extend(c.loon_items)
    alle_items.sort(key=lambda li: li.periode_eind, reverse=True)

    if len(alle_items) < 3:
        waarschuwingen.append(
            "§3.2.3: Minder dan 3 periodes beschikbaar."
        )
        return False, waarschuwingen

    # Check 1: 0 uren in een van de 3 meest recente periodes
    for i in range(min(3, len(alle_items))):
        if alle_items[i].aantal_uur == ZERO:
            waarschuwingen.append(
                f"§3.2.3 check 1: 0 uren in periode "
                f"{alle_items[i].periode_start} t/m {alle_items[i].periode_eind}."
            )
            return False, waarschuwingen

    # Check 3: Negatieve uren in eerste 4 maandelijkse / 5 vierwekelijkse periodes
    check_periodes = min(5, len(alle_items))  # Conservatief: 5 periodes
    for i in range(check_periodes):
        if alle_items[i].aantal_uur < ZERO:
            waarschuwingen.append(
                f"§3.2.3 check 3: Negatieve uren in periode "
                f"{alle_items[i].periode_start} t/m {alle_items[i].periode_eind}."
            )
            return False, waarschuwingen

    return True, []


# ---------------------------------------------------------------------------
# §3.3 — Kortstondig contract
# ---------------------------------------------------------------------------

def _is_kortstondig_contract(
    contracten: list[SamengevoegdContract],
    algemeen_mrl_datum: date,
) -> bool:
    """§3.3: Detecteer kortstondig contract.

    Kortstondig = exact 1 samengevoegd contract waarvan MRL = AMRL
    EN dat contract heeft exact 1 loonitem.

    Gevolg: ALLE contracten via C-berekening.
    """
    amrl_contracten = [
        c for c in contracten
        if c.meest_recent_loonitem
        and c.meest_recent_loonitem.periode_eind == algemeen_mrl_datum
    ]

    if len(amrl_contracten) == 1 and amrl_contracten[0].perioden_count() == 1:
        return True
    return False


# ---------------------------------------------------------------------------
# §3.5 — Minimaal 4 periodes aaneengesloten
# ---------------------------------------------------------------------------

def _heeft_min_periodes_aaneengesloten(
    contract: SamengevoegdContract,
    min_periodes: int = 4,
) -> bool:
    """§3.5: Controleer of een contract minimaal N aaneengesloten periodes heeft.

    Aaneengesloten = geen gaten in de periodedata (volgende periode start
    max 1 dag na einde vorige).
    """
    items = contract.loon_items_gesorteerd()  # Meest recent eerst
    if len(items) < min_periodes:
        return False

    # Sorteer oudst eerst voor gap-check
    items_oudst_eerst = list(reversed(items))

    # Tel langste aaneengesloten reeks
    langste_reeks = 1
    huidige_reeks = 1

    for i in range(1, len(items_oudst_eerst)):
        vorige_eind = items_oudst_eerst[i - 1].periode_eind
        huidige_start = items_oudst_eerst[i].periode_start
        gat_dagen = (huidige_start - vorige_eind).days

        if gat_dagen <= 1:  # Aaneengesloten (0 of 1 dag verschil)
            huidige_reeks += 1
            langste_reeks = max(langste_reeks, huidige_reeks)
        else:
            huidige_reeks = 1

    return langste_reeks >= min_periodes


# ---------------------------------------------------------------------------
# §3.6 — Minimaal 2 jaar aaneengesloten (voor A-berekening)
# ---------------------------------------------------------------------------

def _heeft_min_2_jaar_aaneengesloten(
    contract: SamengevoegdContract,
    betaaltermijn: Betaaltermijn,
) -> bool:
    """§3.6: Controleer of een contract minimaal 2 jaar aaneengesloten periodes heeft.

    Controleert op gaten in de periodedata (niet alleen tijdspanne).
    """
    jp = jaar_perioden(betaaltermijn)
    items = contract.loon_items_gesorteerd()  # Meest recent eerst

    if len(items) < 2 * jp:
        return False

    # Sorteer oudst eerst
    items_oudst_eerst = list(reversed(items))

    # Tel langste aaneengesloten reeks
    langste_reeks = 1
    huidige_reeks = 1

    for i in range(1, len(items_oudst_eerst)):
        vorige_eind = items_oudst_eerst[i - 1].periode_eind
        huidige_start = items_oudst_eerst[i].periode_start
        gat_dagen = (huidige_start - vorige_eind).days

        if gat_dagen <= 1:
            huidige_reeks += 1
            langste_reeks = max(langste_reeks, huidige_reeks)
        else:
            huidige_reeks = 1

    return langste_reeks >= 2 * jp


# ---------------------------------------------------------------------------
# §5.3 — C en D Urencriterium
# ---------------------------------------------------------------------------

def _controleer_urencriterium_cd(
    c_blokken: list[ContractBlok],
    d_contract: SamengevoegdContract,
    betaaltermijn: Betaaltermijn,
) -> tuple[bool, str]:
    """§5.3: Controleer of C-contracten naast D-contract niet te veel uren hebben.

    Per periode: totaal uren C+D ≤ 200 (maandelijks) / 184 (vierwekelijks).
    Als overschreden: geen C-berekening mogelijk.

    Returns: (ok, waarschuwing)
    """
    if betaaltermijn == Betaaltermijn.MAANDELIJKS:
        grens = URENGRENS_MAANDELIJKS
    else:
        grens = URENGRENS_VIERWEKELIJKS

    # Verzamel alle items van D-contract en C-blokken per periode
    uren_per_periode: dict[tuple, Decimal] = {}

    for li in d_contract.loon_items:
        key = (li.periode_start, li.periode_eind)
        uren_per_periode[key] = uren_per_periode.get(key, ZERO) + li.aantal_uur

    for blok in c_blokken:
        for li in blok.loon_items:
            key = (li.periode_start, li.periode_eind)
            uren_per_periode[key] = uren_per_periode.get(key, ZERO) + li.aantal_uur

    for periode, uren in uren_per_periode.items():
        if uren > grens:
            return False, (
                f"§5.3: Urencriterium C/D overschreden in periode "
                f"{periode[0]} t/m {periode[1]}: {uren} > {grens} uur."
            )

    return True, ""


# ---------------------------------------------------------------------------
# Beslisboom  (§3)
# ---------------------------------------------------------------------------

def bepaal_jaren_loonhistorie(contract: SamengevoegdContract) -> int:
    """Bepaal het aantal jaren loonhistorie bij dezelfde werkgever."""
    items = contract.loon_items
    if not items:
        return 0
    nieuwste = max(li.periode_eind for li in items)
    oudste = min(li.periode_start for li in items)
    return int((nieuwste - oudste).days / 365.25)


def _is_actief_contract(
    contract: SamengevoegdContract,
    algemeen_mrl: date,
    betaaltermijn: Betaaltermijn,
) -> bool:
    """§3.4: Controleer of een contract actief is.

    Criteria:
    - Vast: MRL max 1 periode van AMRL (ruimere marge).
    - Niet-Vast: MRL EXACT gelijk aan AMRL.
    - §3.4 crit.4: MRL mag geen 0 uren of ≤ 0 SV loon tonen.
    """
    mrl = contract.meest_recent_loonitem
    if mrl is None:
        return False

    # §3.4 criterium 4: MRL mag geen 0 uren of ≤ 0 SV loon tonen
    if mrl.aantal_uur == ZERO or mrl.sv_loon <= ZERO:
        return False

    if contract.contractvorm == Contractvorm.VAST:
        # Vast: max 1 periode verschil
        if betaaltermijn == Betaaltermijn.MAANDELIJKS:
            grens = timedelta(days=62)  # ~2 maanden
        else:
            grens = timedelta(days=56)  # ~2 × 28 dagen
        return (algemeen_mrl - mrl.periode_eind).days <= grens.days
    else:
        # Niet-Vast: MRL moet exact gelijk zijn aan AMRL
        return mrl.periode_eind == algemeen_mrl


def voer_berekening_uit(
    contract_blokken: list[ContractBlok],
    aanvrager_naam: str,
    aanmaakdatum: date,
    pensioen_maand: Decimal,
) -> list[IBLResultaat]:
    """Doorloop de beslisboom en voer berekeningen uit.

    Stappen:
    0. §3.1: Controle of aanvrager in loondienst werkt
    1. Samenvoegen contracten
    2. Verlofregel toepassen
    3. §3.3: Kortstondig contract detectie
    4. §3.2.3: Aanvullende urencriteria
    5. Per actief contract: §3.4/3.5/3.6 checks, bepaal type, voer uit
    """
    # Stap: Samenvoegen
    contracten = samenvoeg_contracten(contract_blokken)

    if not contracten:
        return []

    # Verlofregel toepassen
    contracten = [pas_verlofregel_toe(c) for c in contracten]

    # Bepaal Algemeen Meest Recent Loonitem
    alle_items = []
    for c in contracten:
        alle_items.extend(c.loon_items)
    if not alle_items:
        return []

    algemeen_mrl_datum = max(li.periode_eind for li in alle_items)

    # §3.1: Werkt aanvrager in loondienst?
    loondienst_ok, loondienst_warn = _werkt_in_loondienst(
        contract_blokken, algemeen_mrl_datum, aanmaakdatum,
    )
    if not loondienst_ok:
        return [IBLResultaat(
            aanvrager_naam=aanvrager_naam,
            aanmaakdatum=aanmaakdatum,
            werkgever_naam="N.v.t.",
            berekening_type=BerekeningType.A,
            toetsinkomen=ZERO,
            tussenresultaat=Tussenresultaat(),
            waarschuwingen=loondienst_warn,
        )]

    # Totaal jaren VZB loonhistorie (voor C vs D routing bij niet-vast)
    alle_vzb_items = []
    for blok in contract_blokken:
        alle_vzb_items.extend(blok.loon_items)
    if alle_vzb_items:
        vzb_nieuwste = max(li.periode_eind for li in alle_vzb_items)
        vzb_oudste = min(li.periode_start for li in alle_vzb_items)
        totaal_vzb_jaren = int((vzb_nieuwste - vzb_oudste).days / 365.25)
    else:
        totaal_vzb_jaren = 0

    # Markeer actieve contracten
    for contract in contracten:
        if not _is_actief_contract(contract, algemeen_mrl_datum, contract.betaaltermijn):
            contract.is_actief = False

    # §3.3: Kortstondig contract detectie
    kortstondig = _is_kortstondig_contract(contracten, algemeen_mrl_datum)

    # §3.2.3: Aanvullende urencriteria
    uren_ok, uren_warn = _aanvullende_urencriteria(contracten, algemeen_mrl_datum)
    if not uren_ok:
        return [IBLResultaat(
            aanvrager_naam=aanvrager_naam,
            aanmaakdatum=aanmaakdatum,
            werkgever_naam="N.v.t.",
            berekening_type=BerekeningType.A,
            toetsinkomen=ZERO,
            tussenresultaat=Tussenresultaat(),
            waarschuwingen=uren_warn,
        )]

    resultaten = []
    # §4.3 stap 1: Bijhouden welke LHNs al een A/B/D-berekening kregen
    abd_lhns: set[str] = set()

    for contract in contracten:
        if not contract.is_actief:
            continue

        items = contract.loon_items_gesorteerd()
        bt = contract.betaaltermijn
        jp = jaar_perioden(bt)
        jaren = bepaal_jaren_loonhistorie(contract)
        waarschuwingen: list[str] = []

        # §3.3: Kortstondig contract → alles via C-berekening
        if kortstondig:
            if totaal_vzb_jaren >= 3:
                berekening_type = BerekeningType.C
            else:
                berekening_type = BerekeningType.D
            waarschuwingen.append(
                "§3.3: Kortstondig contract gedetecteerd, "
                "C/D-berekening toegepast."
            )
        elif contract.contractvorm == Contractvorm.VAST:
            # §3.5: Minimaal 4 periodes aaneengesloten
            if not _heeft_min_periodes_aaneengesloten(contract, 4):
                waarschuwingen.append(
                    "§3.5: Minder dan 4 aaneengesloten periodes. "
                    "Geen berekening mogelijk voor dit contract."
                )
                continue

            # §3.6: Minimaal 2 jaar aaneengesloten voor A-berekening
            heeft_2jr = _heeft_min_2_jaar_aaneengesloten(contract, bt)

            if heeft_2jr:
                # Bestendigheidstoets
                c1_geslaagd, c1_ratio = bestendigheidstoets_criterium1(items, bt)

                if not c1_geslaagd:
                    berekening_type = BerekeningType.B
                    waarschuwingen.append(
                        f"Bestendigheidstoets criterium 1 gefaald: "
                        f"ratio {c1_ratio:.2f}% > 120%"
                    )
                else:
                    c2_geslaagd = bestendigheidstoets_criterium2(items, bt)
                    if not c2_geslaagd:
                        berekening_type = BerekeningType.B
                        waarschuwingen.append(
                            "Bestendigheidstoets criterium 2 gefaald: "
                            "niet-bestendige pieken gedetecteerd"
                        )
                    else:
                        berekening_type = BerekeningType.A
            else:
                berekening_type = BerekeningType.B
        else:
            # §3.5: Minimaal 4 periodes aaneengesloten
            if not _heeft_min_periodes_aaneengesloten(contract, 4):
                waarschuwingen.append(
                    "§3.5: Minder dan 4 aaneengesloten periodes. "
                    "Geen berekening mogelijk voor dit contract."
                )
                continue

            # Niet-vast: C als totale VZB loonhistorie ≥ 3 jaar
            if totaal_vzb_jaren >= 3:
                berekening_type = BerekeningType.C
            else:
                berekening_type = BerekeningType.D

        # Appendix 2: Bij oproepovereenkomst geen pensioen
        contract_pensioen = pensioen_maand
        if contract.contractvorm_raw:
            cv_lower = contract.contractvorm_raw.lower()
            # Alleen echte oproepovereenkomsten, niet "geen oproepovereenkomst"
            is_oproep = (
                "oproepovereenkomst" in cv_lower
                and "geen oproepovereenkomst" not in cv_lower
            )
            if is_oproep:
                contract_pensioen = ZERO
                waarschuwingen.append(
                    "Appendix 2: Oproepovereenkomst — geen eigen bijdrage "
                    "pensioen toegestaan."
                )

        # Voer berekening uit
        if berekening_type == BerekeningType.A:
            toetsinkomen, bt_type, tussenresultaat = bereken_a(contract, contract_pensioen)
            abd_lhns.add(contract.loonheffingennummer)
        elif berekening_type == BerekeningType.B:
            toetsinkomen, bt_type, tussenresultaat = bereken_b(contract, contract_pensioen)
            abd_lhns.add(contract.loonheffingennummer)
        elif berekening_type == BerekeningType.D:
            toetsinkomen, bt_type, tussenresultaat = bereken_d(contract, contract_pensioen)
            abd_lhns.add(contract.loonheffingennummer)
        else:
            # C-berekening: multi-contract
            # §4.3 stap 1: Excludeer blokken die al A/B/D-berekening kregen
            # en filter items tot meest recente 3 jaar (§5.1 cutoff)
            cutoff_3jr = algemeen_mrl_datum - timedelta(days=3 * 365 + 30)

            c_blokken = []
            for blok in contract_blokken:
                if not (blok.heeft_contractvorm or blok.is_uitkering_uwv):
                    continue
                if blok.loonheffingennummer in abd_lhns:
                    continue
                # Filter items ouder dan 3 jaar
                recente_items = [
                    li for li in blok.loon_items
                    if li.periode_eind >= cutoff_3jr
                ]
                if recente_items:
                    from copy import deepcopy
                    gefilterd_blok = deepcopy(blok)
                    gefilterd_blok.loon_items = recente_items
                    c_blokken.append(gefilterd_blok)

            # §5.6.6 stap 3: Bepaal betaaltermijn uit MRLs van C-blokken
            # Als ALLE MRLs vierwekelijks → vierwekelijks, anders maandelijks
            from .preprocessing import bepaal_betaaltermijn as _bepaal_bt
            c_bt = Betaaltermijn.MAANDELIJKS
            if c_blokken:
                alle_mrls_vierwekelijks = True
                for blok in c_blokken:
                    if blok.loon_items:
                        mrl_item = max(blok.loon_items, key=lambda li: li.periode_eind)
                        if mrl_item.dagen != 28:  # 28 dagen = vierwekelijks
                            alle_mrls_vierwekelijks = False
                            break
                    else:
                        alle_mrls_vierwekelijks = False
                        break
                if alle_mrls_vierwekelijks:
                    c_bt = Betaaltermijn.VIERWEKELIJKS

            toetsinkomen, bt_type, tussenresultaat = bereken_c(
                c_blokken, algemeen_mrl_datum, contract_pensioen, c_bt,
            )

        # Sla bestendigheidstoets resultaten op
        if (contract.contractvorm == Contractvorm.VAST
                and not kortstondig and heeft_2jr):
            tussenresultaat.bestendigheid_criterium1_ratio = c1_ratio
            tussenresultaat.bestendigheid_criterium1_geslaagd = c1_geslaagd
            if c1_geslaagd:
                tussenresultaat.bestendigheid_criterium2_geslaagd = c2_geslaagd
            tussenresultaat.bestendigheid_geslaagd = (
                berekening_type == BerekeningType.A
            )

        resultaten.append(IBLResultaat(
            aanvrager_naam=aanvrager_naam,
            aanmaakdatum=aanmaakdatum,
            werkgever_naam=contract.werkgever_naam,
            berekening_type=bt_type,
            toetsinkomen=toetsinkomen,
            tussenresultaat=tussenresultaat,
            waarschuwingen=waarschuwingen,
        ))

    return resultaten
