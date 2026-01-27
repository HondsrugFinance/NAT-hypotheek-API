"""
NAT Hypotheeknormen Calculator 2026 - EXCEL EXACT
Alle berekeningen exact volgens NAT-sheet 2026.xlsm
Geen placeholders, geen simplificaties
"""

import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

# Load woonquote tables
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

with open(
    os.path.join(BASE_DIR, 'woonquote_tables.json'),
    'r',
    encoding='utf-8'
) as f:
    WOONQUOTE_TABLES = json.load(f)

@dataclass
class Annuitair:
    max_box1: float
    max_box3: float
    ruimte_box1: float
    ruimte_box3: float

@dataclass
class NietAnnuitair:
    max_box1: float
    max_box3: float
    ruimte_box1: float
    ruimte_box3: float

@dataclass
class Scenario:
    annuitair: Annuitair
    niet_annuitair: NietAnnuitair

def is_filled(value) -> bool:
    """Check if value is filled (not None, not empty string, not whitespace)"""
    if value is None:
        return False
    if isinstance(value, str):
        return len(value.strip()) > 0
    return True  # 0 counts as filled

def pmt(rate: float, nper: float, pv: float, fv: float = 0) -> float:
    """Excel PMT formula - returns negative payment"""
    if rate == 0:
        return -(pv + fv) / nper
    pvif = (1 + rate) ** nper
    return -(rate * (pv * pvif + fv)) / (pvif - 1)

def lookup_woonquote(toets_inkomen: float, toets_rente: float, ontvangt_aow: str, is_box3: bool) -> float:
    """Woonquote lookup exact volgens Excel MATCH/XMATCH"""
    if ontvangt_aow == 'JA':
        table_key = 'cWqVnfAowCons' if is_box3 else 'cWqVnfAow'
    else:
        table_key = 'cWqTotAowCons' if is_box3 else 'cWqTotAow'
    
    table = WOONQUOTE_TABLES[table_key]
    
    # MATCH: vind hoogste inkomen <= toets_inkomen
    income_keys = sorted([float(k) for k in table.keys()])
    selected_income = income_keys[0]
    for income in income_keys:
        if toets_inkomen >= income:
            selected_income = income
        else:
            break
    
    row_data = None
    for key in table.keys():
        if float(key) == selected_income:
            row_data = table[key]
            break
    
    if row_data is None:
        raise KeyError(f"Income {selected_income} not found in table {table_key}")
    
    # XMATCH: vind laagste rente >= toets_rente, or laatste kolom
    rate_keys = sorted([float(k) for k in row_data.keys()])
    selected_rate = rate_keys[-1]  # default laatste
    
    for rate in rate_keys:
        if toets_rente <= rate:
            selected_rate = rate
            break
    
    rate_value = None
    for key in row_data.keys():
        if float(key) == selected_rate:
            rate_value = row_data[key]
            break
    
    if rate_value is None:
        raise KeyError(f"Rate {selected_rate} not found")
    
    return rate_value

def calculate_energielabel_bonus(energielabel: Optional[str], verduurzamings_maatregelen: float) -> float:
    """
    Calculate C33:C50 sum - Excel energielabel bonuses
    C33-C40: Base bonuses per label
    C43-C50: Verduurzamings maatregelen capped per label
    """
    if energielabel is None:
        energielabel = ""
    
    # C33-C40: Base bonuses
    base_bonus = 0
    if energielabel == "Geen (geldig) Label":
        base_bonus = 0  # C33
    elif energielabel == "E,F,G":
        base_bonus = 0  # C34
    elif energielabel == "C,D":
        base_bonus = 5000  # C35
    elif energielabel == "A,B":
        base_bonus = 10000  # C36
    elif energielabel == "A+,A++":
        base_bonus = 20000  # C37
    elif energielabel == "A+++":
        base_bonus = 25000  # C38
    elif energielabel == "A++++":
        base_bonus = 30000  # C39
    elif energielabel == "A++++ met garantie":
        base_bonus = 40000  # C40
    
    # C43-C50: Verduurzamings maatregelen met cap per label
    verduurzaming_bonus = 0
    if verduurzamings_maatregelen > 0:
        if energielabel == "Geen (geldig) Label":
            # C43: IF(AND(F36>0, F36>10000), 10000, F36)
            verduurzaming_bonus = min(verduurzamings_maatregelen, 10000)
        elif energielabel == "E,F,G":
            # C44: cap 20000
            verduurzaming_bonus = min(verduurzamings_maatregelen, 20000)
        elif energielabel == "C,D":
            # C45: cap 15000
            verduurzaming_bonus = min(verduurzamings_maatregelen, 15000)
        elif energielabel in ["A,B", "A+,A++"]:
            # C46, C47: cap 10000
            verduurzaming_bonus = min(verduurzamings_maatregelen, 10000)
        # A+++, A++++, A++++ met garantie: 0 (C48, C49, C50)
    
    return base_bonus + verduurzaming_bonus

def calculate_c26_d26(inkomen: float, inkomen_partner: float, alleenstaande: str, 
                     c_alleen_grens_o: float, c_alleen_grens_b: float, c_alleen_factor: float) -> tuple:
    """
    Excel C26/D26 formules exact
    IFS logica voor alleenstaand correctie
    """
    # C26 logica (cAlleenGrensO = 30000)
    if inkomen > 0 and inkomen_partner > 0 and alleenstaande == "JA":
        c26 = 0
    elif inkomen == 0 and inkomen_partner > c_alleen_grens_o and alleenstaande == "JA":
        c26 = c_alleen_factor
    elif inkomen > c_alleen_grens_o and inkomen_partner == 0 and alleenstaande == "JA":
        c26 = c_alleen_factor
    elif inkomen <= c_alleen_grens_o and inkomen_partner <= c_alleen_grens_o and alleenstaande == "JA":
        c26 = 0
    else:
        c26 = 0
    
    # D26 logica (cAlleenGrensB = 29000)
    if inkomen > 0 and inkomen_partner > 0 and alleenstaande == "JA":
        d26 = 0
    elif inkomen == 0 and inkomen_partner > c_alleen_grens_b and alleenstaande == "JA":
        d26 = c_alleen_factor
    elif inkomen > c_alleen_grens_b and inkomen_partner == 0 and alleenstaande == "JA":
        d26 = c_alleen_factor
    elif inkomen <= c_alleen_grens_b and inkomen_partner <= c_alleen_grens_b and alleenstaande == "JA":
        d26 = 0
    else:
        d26 = 0
    
    return c26, d26

def calculate_c73(toets_rente: float, studievoorschot: float) -> float:
    """
    Excel C73 = SUM(C60:C71)
    Studielening correctie op basis van toetsrente
    Exacte brackets volgens Excel
    """
    jaar_bedrag = studievoorschot * 12
    
    # C60: <= 1.5%
    if toets_rente <= 0.015:
        return jaar_bedrag * 1.05
    # C61: 1.501% - 2%
    elif toets_rente <= 0.02:
        return jaar_bedrag * 1.05
    # C62: 2.001% - 2.5%
    elif toets_rente <= 0.025:
        return jaar_bedrag * 1.1
    # C63: 2.501% - 3%
    elif toets_rente <= 0.03:
        return jaar_bedrag * 1.15
    # C64: 3.001% - 3.5%
    elif toets_rente <= 0.035:
        return jaar_bedrag * 1.2
    # C65: 3.501% - 4%
    elif toets_rente <= 0.04:
        return jaar_bedrag * 1.2
    # C66: 4.001% - 4.5%
    elif toets_rente <= 0.045:
        return jaar_bedrag * 1.25
    # C67: 4.501% - 5%
    elif toets_rente <= 0.05:
        return jaar_bedrag * 1.3
    # C68: 5.001% - 5.5%
    elif toets_rente <= 0.055:
        return jaar_bedrag * 1.3
    # C69: 5.501% - 6%
    elif toets_rente <= 0.06:
        return jaar_bedrag * 1.35
    # C70: 6.001% - 6.5%
    elif toets_rente <= 0.065:
        return jaar_bedrag * 1.4
    # C71: >= 6.501%
    else:
        return jaar_bedrag * 1.4

def calculate(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Main calculation - Excel exact"""
    
    # Constanten
    c_toets_rente = inputs.get('c_toets_rente', 0.05)
    c_actuele_10jr_rente = inputs.get('c_actuele_10jr_rente', 0.05)
    c_rvp_toets_rente = inputs.get('c_rvp_toets_rente', 120)
    c_factor_2e_inkomen = inputs.get('c_factor_2e_inkomen', 1.0)
    c_lpt = inputs.get('c_lpt', 360)
    c_alleen_grens_o = inputs.get('c_alleen_grens_o', 30000)
    c_alleen_grens_b = inputs.get('c_alleen_grens_b', 29000)
    c_alleen_factor = inputs.get('c_alleen_factor', 17000)
    
    # Inputs
    hoofd_inkomen_aanvrager = inputs.get('hoofd_inkomen_aanvrager', 0)
    hoofd_inkomen_partner = inputs.get('hoofd_inkomen_partner', 0)
    alleenstaande = inputs.get('alleenstaande', 'JA')
    ontvangt_aow = inputs.get('ontvangt_aow', 'NEE')
    
    # F16, G16 - Inkomen berekening
    inkomen_aanvrager = (
        hoofd_inkomen_aanvrager +
        inputs.get('inkomen_uit_lijfrente_aanvrager', 0) +
        inputs.get('ontvangen_partneralimentatie_aanvrager', 0) +
        inputs.get('inkomsten_uit_vermogen_aanvrager', 0) +
        inputs.get('huurinkomsten_aanvrager', 0) -
        inputs.get('te_betalen_partneralimentatie_aanvrager', 0)
    )
    
    inkomen_partner = (
        hoofd_inkomen_partner +
        inputs.get('inkomen_uit_lijfrente_partner', 0) +
        inputs.get('ontvangen_partneralimentatie_partner', 0) -
        inputs.get('te_betalen_partneralimentatie_partner', 0)
    )
    
    # F18 - Inkomen totaal
    inkomen_overige = inputs.get('inkomen_overige_aanvragers', 0)
    if alleenstaande == 'JA':
        inkomen_totaal = inkomen_aanvrager + inkomen_overige
    else:
        inkomen_totaal = inkomen_aanvrager + inkomen_partner + inkomen_overige
    
    # Hypotheek delen
    hypotheek_delen_raw = inputs.get('hypotheek_delen', [])
    hypotheek_delen = []
    for deel in hypotheek_delen_raw[:10]:
        hypotheek_delen.append({
            'aflos_type': deel.get('aflos_type', ''),
            'org_lpt': deel.get('org_lpt', 0),
            'rest_lpt': deel.get('rest_lpt', 0),
            'hoofdsom_box1': deel.get('hoofdsom_box1', 0),
            'hoofdsom_box3': deel.get('hoofdsom_box3', 0),
            'rvp': deel.get('rvp', 0),
            'inleg_overig': deel.get('inleg_overig', 0),
            'werkelijke_rente': deel.get('werkelijke_rente', 0),
        })
    
    # K9:K18 - Is annuitair/lineair?
    # S9:S18 - Rente per deel
    delen_processed = []
    for deel in hypotheek_delen:
        is_annuitair_linear = deel['aflos_type'] in ['Annuïteit', 'Lineair']
        k_value = 0 if is_annuitair_linear else 1
        rente = c_toets_rente if deel['rvp'] < c_rvp_toets_rente else deel['werkelijke_rente']
        
        delen_processed.append({
            **deel,
            'k_value': k_value,
            'rente': rente,
            'is_annuitair_linear': is_annuitair_linear,
        })
    
    # K19 - Aantal NIET-annuitair (LET OP: variabele naam!)
    aantal_niet_annuitair = sum(d['k_value'] for d in delen_processed)
    
    # N19, O19 - Som hoofdsommen
    som_box1 = sum(d['hoofdsom_box1'] for d in delen_processed)
    som_box3 = sum(d['hoofdsom_box3'] for d in delen_processed)
    
    # S19 - Gewogen rente
    if som_box1 == 0 and som_box3 == 0:
        gewogen_rente = c_toets_rente
    else:
        numerator = sum(
            d['rente'] * d['hoofdsom_box1'] * d['rest_lpt'] +
            d['rente'] * d['hoofdsom_box3'] * d['rest_lpt']
            for d in delen_processed
        )
        denominator = sum(
            d['hoofdsom_box1'] * d['rest_lpt'] +
            d['hoofdsom_box3'] * d['rest_lpt']
            for d in delen_processed
        )
        gewogen_rente = numerator / denominator if denominator > 0 else c_toets_rente
    
    # T-Y kolommen - Rente lasten
    rente_betalingen = []
    for d in delen_processed:
        lpt = d['rest_lpt'] if d['is_annuitair_linear'] else d['org_lpt']
        rente = d['rente']
        
        # T, U - Excel: =PMT(S9/12,IF(OR(J9="Annuïteit", J9="Lineair"),M9,L9),-N9)*12
        T = -pmt(rente / 12, lpt, d['hoofdsom_box1']) * 12
        U = -pmt(rente / 12, lpt, d['hoofdsom_box3']) * 12
        
        # V, W - Excel: =IF(J9="Annuïteit",12*PMT(S9/12,M9,-N9,0),IF(J9="Lineair",(N9)*(S9+12/M9),(N9)*S9))
        if d['aflos_type'] == 'Annuïteit':
            V = -12 * pmt(rente / 12, d['rest_lpt'], d['hoofdsom_box1'], 0)
            W = -12 * pmt(rente / 12, d['rest_lpt'], d['hoofdsom_box3'], 0)
        elif d['aflos_type'] == 'Lineair':
            V = d['hoofdsom_box1'] * (rente + 12 / d['rest_lpt'])
            W = d['hoofdsom_box3'] * (rente + 12 / d['rest_lpt'])
        else:  # Aflossingsvrij
            V = d['hoofdsom_box1'] * rente
            W = d['hoofdsom_box3'] * rente
        
        # X, Y - Excel: =IF(T9>0,Deel1InlegOverig,"0")
        X = d['inleg_overig'] if T > 0 else 0
        Y = d['inleg_overig'] if U > 0 else 0
        
        rente_betalingen.append({'T': T, 'U': U, 'V': V, 'W': W, 'X': X, 'Y': Y})
    
    # Sommen T19, U19, V19, W19, X19, Y19
    T19 = sum(r['T'] for r in rente_betalingen)
    U19 = sum(r['U'] for r in rente_betalingen)
    V19 = sum(r['V'] for r in rente_betalingen)
    W19 = sum(r['W'] for r in rente_betalingen)
    X19 = sum(r['X'] for r in rente_betalingen)
    Y19 = sum(r['Y'] for r in rente_betalingen)
    
    # F44 inputs
    limieten_bkr = inputs.get('limieten_bkr_geregistreerd', 0)
    limieten_niet_bkr = inputs.get('limieten_niet_bkr_geregistreerd', 0)
    erfpacht = inputs.get('erfpachtcanon_per_jaar', 0)
    jaarlast = inputs.get('jaarlast_overige_kredieten', 0)
    studievoorschot = inputs.get('studievoorschot_studielening', 0)
    energielabel = inputs.get('energielabel')
    verduurzamings_maatregelen = inputs.get('verduurzamings_maatregelen', 0)
    
    # Scenario 1
    scenario1 = calculate_scenario(
        inkomen_totaal, inkomen_aanvrager, inkomen_partner,
        alleenstaande, ontvangt_aow, gewogen_rente,
        som_box1, som_box3, T19, U19, V19, W19, X19, Y19,
        aantal_niet_annuitair,
        limieten_bkr, limieten_niet_bkr, erfpacht, jaarlast, studievoorschot,
        energielabel, verduurzamings_maatregelen,
        c_toets_rente, c_actuele_10jr_rente, c_factor_2e_inkomen, c_lpt,
        c_alleen_grens_o, c_alleen_grens_b, c_alleen_factor
    )
    
    # Scenario 2 - alleen als F29 EN/OF G29 gevuld
    scenario2 = None
    gewijzigd_aanvrager2 = inputs.get('gewijzigd_hoofd_inkomen_aanvrager2')
    gewijzigd_partner2 = inputs.get('gewijzigd_hoofd_inkomen_partner2')
    
    if is_filled(gewijzigd_aanvrager2) or is_filled(gewijzigd_partner2):
        gewijzigd_aanvrager2 = gewijzigd_aanvrager2 if gewijzigd_aanvrager2 is not None else 0
        gewijzigd_partner2 = gewijzigd_partner2 if gewijzigd_partner2 is not None else 0
        inkomen_overige_min2 = inputs.get('inkomen_overige_aanvragers_min2', 0)
        
        if alleenstaande == 'JA':
            inkomen_min2_totaal = gewijzigd_aanvrager2 + inkomen_overige_min2
        else:
            inkomen_min2_totaal = gewijzigd_aanvrager2 + gewijzigd_partner2 + inkomen_overige_min2
        
        ontvangt_aow2 = inputs.get('gewijzigd_hoofd_inkomen_aow2', ontvangt_aow)
        
        scenario2 = calculate_scenario(
            inkomen_min2_totaal, gewijzigd_aanvrager2, gewijzigd_partner2,
            alleenstaande, ontvangt_aow2, gewogen_rente,
            som_box1, som_box3, T19, U19, V19, W19, X19, Y19,
            aantal_niet_annuitair,
            limieten_bkr, limieten_niet_bkr, erfpacht, jaarlast, studievoorschot,
            energielabel, verduurzamings_maatregelen,
            c_toets_rente, c_actuele_10jr_rente, c_factor_2e_inkomen, c_lpt,
            c_alleen_grens_o, c_alleen_grens_b, c_alleen_factor
        )
    
    return {
        'scenario1': asdict(scenario1) if isinstance(scenario1, Scenario) else scenario1,
        'scenario2': asdict(scenario2) if scenario2 and isinstance(scenario2, Scenario) else scenario2,
    }

def calculate_scenario(
    inkomen_totaal: float, inkomen_aanvrager: float, inkomen_partner: float,
    alleenstaande: str, ontvangt_aow: str, gewogen_rente: float,
    som_box1: float, som_box3: float,
    T19: float, U19: float, V19: float, W19: float, X19: float, Y19: float,
    aantal_niet_annuitair: float,
    limieten_bkr: float, limieten_niet_bkr: float, erfpacht: float, 
    jaarlast: float, studievoorschot: float,
    energielabel: Optional[str], verduurzamings_maatregelen: float,
    c_toets_rente: float, c_actuele_10jr_rente: float, c_factor_2e_inkomen: float, c_lpt: float,
    c_alleen_grens_o: float, c_alleen_grens_b: float, c_alleen_factor: float
) -> Scenario:
    """Calculate single scenario - Excel exact"""
    
    # M25 - ToetsInkomen (ALLEEN voor woonquote lookup)
    # Excel: =IF(Alleenstaande="JA",Inkomen,MAX(F16+G16*cFactor2eInkomen,G16+F16*cFactor2eInkomen))
    # Waarbij "Inkomen" = F16 (inkomen_aanvrager), NIET F18 (inkomen_totaal)!
    # F16 bevat GEEN inkomen_overige, dat zit alleen in F18
    if alleenstaande == 'JA':
        toets_inkomen = inkomen_aanvrager  # F16, niet inkomen_totaal!
    else:
        toets_inkomen = max(
            inkomen_aanvrager + inkomen_partner * c_factor_2e_inkomen,
            inkomen_partner + inkomen_aanvrager * c_factor_2e_inkomen
        )
    
    # M26 - ToetsRente
    # Excel: =ROUND(IF(N19+O19=0,cActuele10jrRente,ROUND(S19,25)),5)
    if som_box1 + som_box3 == 0:
        toets_rente = round(c_actuele_10jr_rente, 5)
    else:
        toets_rente = round(round(gewogen_rente, 25), 5)
    
    # M27, M28 - Woonquote
    woonquote_box1 = lookup_woonquote(toets_inkomen, toets_rente, ontvangt_aow, False)
    woonquote_box3 = lookup_woonquote(toets_inkomen, toets_rente, ontvangt_aow, True)
    
    # C26, D26 - Alleenstaand correctie
    c26, d26 = calculate_c26_d26(inkomen_aanvrager, inkomen_partner, alleenstaande,
                                 c_alleen_grens_o, c_alleen_grens_b, c_alleen_factor)
    
    # C33:C50 - Energielabel bonus
    c33_c50_sum = calculate_energielabel_bonus(energielabel, verduurzamings_maatregelen)
    
    # C52 - Excel: =IF(OntvangtAOW="Ja",SUM(C33:C50)+D26,SUM(C33:C50)+C26)
    if ontvangt_aow == "JA":
        c52 = c33_c50_sum + d26
    else:
        c52 = c33_c50_sum + c26
    
    # C53 - Excel: =SUM(C52*PMT(ToetsRente/12,cLpt,-1,0)*12)
    pmt_factor = -pmt(toets_rente / 12, c_lpt, 1, 0)
    c53 = c52 * pmt_factor * 12
    
    # D53 - Excel: =SUM(C52*ToetsRente)
    d53 = c52 * toets_rente
    
    # C73 - Studielening correctie
    c73 = calculate_c73(toets_rente, studievoorschot)
    
    # F44 - Correctie
    # Excel: =IF(N19=0,(F39*24%)+(F40*24%)+(F42*12)+(F43*12)+(F41*12),(F39*24%)+(F40*24%)+(F42*12)+(F43*12)+constanten!C73)
    if som_box1 == 0:
        correctie = (limieten_bkr * 0.24 + limieten_niet_bkr * 0.24 + 
                    erfpacht * 12 + jaarlast * 12 + studievoorschot * 12)
    else:
        correctie = (limieten_bkr * 0.24 + limieten_niet_bkr * 0.24 + 
                    erfpacht * 12 + jaarlast * 12 + c73)
    
    # M34, M35 - Woonlast Box1/Box3
    # LET OP: Gebruikt inkomen_totaal (M32), NIET toets_inkomen!
    # Excel M34: =SUM((((((M32*WoonquoteBox1)+constanten!C53)-M33)-T19)/(WoonquoteBox1/WoonquoteBox3))-U19)*(WoonquoteBox1/WoonquoteBox3)
    woonlast_box1 = (
        (((inkomen_totaal * woonquote_box1) + c53 - correctie - T19) / 
         (woonquote_box1 / woonquote_box3)) - U19
    ) * (woonquote_box1 / woonquote_box3)
    
    # Excel M35: =SUM((((M32*WoonquoteBox1)+constanten!C53)-M33)-T19)/(WoonquoteBox1/WoonquoteBox3)-U19
    woonlast_box3 = (
        ((inkomen_totaal * woonquote_box1) + c53 - correctie - T19) / 
        (woonquote_box1 / woonquote_box3)
    ) - U19
    
    # M36, M37 - Alternative woonlast (voor niet-annuitair)
    # Excel M36: =IF(K19>0,SUM((((((M32*WoonquoteBox1)+constanten!D53)-M33)-V19-X19)/(WoonquoteBox1/WoonquoteBox3))-W19-Y19)*(WoonquoteBox1/WoonquoteBox3),SUM((((((M32*WoonquoteBox1)+constanten!C53)-M33)-V19-X19)/(WoonquoteBox1/WoonquoteBox3))-W19-Y19)*(WoonquoteBox1/WoonquoteBox3))
    if aantal_niet_annuitair > 0:
        const_for_alt = d53
    else:
        const_for_alt = c53
    
    woonlast_box1_alt = (
        (((inkomen_totaal * woonquote_box1) + const_for_alt - correctie - V19 - X19) / 
         (woonquote_box1 / woonquote_box3)) - W19 - Y19
    ) * (woonquote_box1 / woonquote_box3)
    
    # Excel M37: =IF(K19>0,SUM((((M32*WoonquoteBox1)+constanten!D53)-M33)-V19-X19)/(WoonquoteBox1/WoonquoteBox3)-W19-Y19,SUM((((M32*WoonquoteBox1)+constanten!C53)-M33)-V19-X19)/(WoonquoteBox1/WoonquoteBox3)-W19-Y19)
    woonlast_box3_alt = (
        ((inkomen_totaal * woonquote_box1) + const_for_alt - correctie - V19 - X19) / 
        (woonquote_box1 / woonquote_box3)
    ) - W19 - Y19
    
    # M42, M43 - Ruimte annuitair
    # LET OP: Excel naming is verwarrend!
    # M42 = M34/PMT (M34 is woonlast box1) → wordt gebruikt in M40 (max box1)
    # M43 = M35/PMT (M35 is woonlast box3) → wordt gebruikt in M41 (max box3)
    # Maar Excel named range zegt M42 = "ruimtebox3"!
    # We volgen de FORMULES, niet de labels
    
    # Excel M42: =SUM(M34/PMT(ToetsRente/12,cLpt,-1,0)/12)
    # Excel M43: =SUM(M35/PMT(ToetsRente/12,cLpt,-1,0)/12)
    ruimte_box1_annuitair = woonlast_box1 / pmt_factor / 12  # M42 in formule, maar for box1 max
    ruimte_box3_annuitair = woonlast_box3 / pmt_factor / 12  # M43 in formule, maar for box3 max
    
    # M40, M41 - Max hypotheek annuitair
    # Excel M40: =N19+O19+M42
    # Excel M41: =N19+O19+M43
    max_hyp_annuitair_box1 = som_box1 + som_box3 + ruimte_box1_annuitair
    max_hyp_annuitair_box3 = som_box1 + som_box3 + ruimte_box3_annuitair
    
    # M48, M49 - Ruimte niet-annuitair
    # Excel M48: =IF(K19>0,IF((N19+O19=0),M34/ToetsRente,M36/ToetsRente),SUM(M36/PMT(ToetsRente/12,cLpt,-1,0)/12))
    # Excel M49: =IF(K19>0,IF((N19+O19=0),M35/ToetsRente,M37/ToetsRente),SUM(M37/PMT(ToetsRente/12,cLpt,-1,0)/12))
    if aantal_niet_annuitair > 0:
        if som_box1 + som_box3 == 0:
            ruimte_box1_niet_annuitair = woonlast_box1 / toets_rente
            ruimte_box3_niet_annuitair = woonlast_box3 / toets_rente
        else:
            ruimte_box1_niet_annuitair = woonlast_box1_alt / toets_rente
            ruimte_box3_niet_annuitair = woonlast_box3_alt / toets_rente
    else:
        ruimte_box1_niet_annuitair = woonlast_box1_alt / pmt_factor / 12
        ruimte_box3_niet_annuitair = woonlast_box3_alt / pmt_factor / 12
    
    # M46, M47 - Max hypotheek niet-annuitair
    # Excel M46: =N19+O19+M48
    # Excel M47: =N19+O19+M49
    max_hyp_niet_annuitair_box1 = som_box1 + som_box3 + ruimte_box1_niet_annuitair
    max_hyp_niet_annuitair_box3 = som_box1 + som_box3 + ruimte_box3_niet_annuitair
    
    return Scenario(
        annuitair=Annuitair(
            max_box1=max_hyp_annuitair_box1,
            max_box3=max_hyp_annuitair_box3,
            ruimte_box1=ruimte_box1_annuitair,
            ruimte_box3=ruimte_box3_annuitair,
        ),
        niet_annuitair=NietAnnuitair(
            max_box1=max_hyp_niet_annuitair_box1,
            max_box3=max_hyp_niet_annuitair_box3,
            ruimte_box1=ruimte_box1_niet_annuitair,
            ruimte_box3=ruimte_box3_niet_annuitair,
        ),
    )
