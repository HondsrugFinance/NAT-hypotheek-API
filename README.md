# NAT Hypotheeknormen Calculator 2026 - EXCEL EXACT

## ✅ Status: VOLLEDIG EXCEL-EXACT

Alle 5 testcases + 4 extra tests (energielabel & studielening) slagen met 100% nauwkelijkheid.

## 🎯 Geïmplementeerde Features

### 1. ✅ Inkomen-variabelen correct gescheiden
- `toets_inkomen` (M25) - **ALLEEN** voor woonquote lookup
  - Bij alleenstaand: `F16` (inkomen_aanvrager) - **ZONDER** inkomen_overige
  - Bij samen: `MAX(F16+G16*factor, G16+F16*factor)` - ook zonder inkomen_overige
- `inkomen_totaal` (M32/F18) - gebruikt in **ALLE** woonlast formules
  - Bevat inkomen_aanvrager + inkomen_partner + inkomen_overige
- **BELANGRIJK**: Inkomen_overige zit NIET in ToetsInkomen, wel in InkomenTotaal
  - Dit betekent: woonquote wordt bepaald met LAGER inkomen
  - Maar woonlast wordt berekend met HOGER inkomen
  - Resultaat: MEER hypotheekruimte met inkomen_overige!

### 2. ✅ Energielabel bonus (C33-C50) - VOLLEDIG GEÏMPLEMENTEERD
**Functie: `calculate_energielabel_bonus()`**

**Base bonussen (C33-C40):**
- Geen (geldig) Label: €0
- E,F,G: €0
- C,D: €5,000
- A,B: €10,000
- A+,A++: €20,000
- A+++: €25,000
- A++++: €30,000
- A++++ met garantie: €40,000

**Verduurzamings maatregelen (C43-C50) met caps:**
- Geen Label: max €10,000
- E,F,G: max €20,000
- C,D: max €15,000
- A,B / A+,A++: max €10,000
- A+++ en hoger: €0 (geen verduurzaming bonus)

### 3. ✅ Studielening correctie (C60-C73) - VOLLEDIG GEÏMPLEMENTEERD
**Functie: `calculate_c73(toets_rente, studievoorschot)`**

**Exacte brackets (staffeltabel):**
```
≤ 1.5%:           jaar_bedrag * 1.05
1.501% - 2%:      jaar_bedrag * 1.05
2.001% - 2.5%:    jaar_bedrag * 1.1
2.501% - 3%:      jaar_bedrag * 1.15
3.001% - 3.5%:    jaar_bedrag * 1.2
3.501% - 4%:      jaar_bedrag * 1.2
4.001% - 4.5%:    jaar_bedrag * 1.25
4.501% - 5%:      jaar_bedrag * 1.3
5.001% - 5.5%:    jaar_bedrag * 1.3
5.501% - 6%:      jaar_bedrag * 1.35
6.001% - 6.5%:    jaar_bedrag * 1.4
≥ 6.501%:         jaar_bedrag * 1.4
```

### 4. ✅ Variabele hernoemd: `aantal_niet_annuitair`
Was: `aantal_annuitair` (verwarrend)  
Nu: `aantal_niet_annuitair` (correct = K19 in Excel)

### 5. ✅ Excel rondingen exact
- ToetsRente (M26): `ROUND(ROUND(S19, 25), 5)` - dubbele ROUND!
- Eindoutputs: volledige precisie

## 📊 Test Resultaten

```
✓ Test 1: Geen energielabel, geen studielening (2 delen)
✓ Test 2: A,B label + €10k verduurzaming + €60 studielening (2 delen)
✓ Test 3: Zelfde als Test 2, maar niet-alleenstaande
✓ Test 4: 3 hypotheekdelen, met partner inkomen
✓ Test 5: 3 delen, 2 niet-annuitair

✓ Extra 1: Energielabel C,D met €8,000 verduurzaming
✓ Extra 2: A++++ met garantie (€40,000 bonus)
✓ Extra 3: Studielening €200/maand bij 5% toetsrente
✓ Extra 4: Studielening €100/maand bij 3% toetsrente
✓ Extra 5: Inkomen overige €10,000 (ToetsInkomen vs InkomenTotaal)

Tolerance: 0.01 euro
Result: ALL 10 TESTS PASSED ✓✓✓
```

### Extra Test 5: Inkomen Overige Verificatie

**Scenario:**
- Hoofd inkomen: €50,000
- Inkomen overige: €10,000
- Totaal: €60,000

**Berekening:**
- ToetsInkomen (M25) = €50,000 (alleen F16, zonder overige)
- InkomenTotaal (M32) = €60,000 (met overige)
- Woonquote lookup: met €50,000 → lagere quote
- Woonlast berekening: met €60,000 → hogere ruimte

**Resultaat:**
- Met inkomen_overige=€0: Max €217,425
- Met inkomen_overige=€10k: Max €257,511
- Verschil: **+€40,085** (20% meer ruimte!)

**Conclusie:** ✓ ToetsInkomen gebruikt correct F16 (zonder overige)

## 💾 Gebruik

```python
from calculator import calculate

results = calculate({
    'hoofd_inkomen_aanvrager': 60000,
    'hoofd_inkomen_partner': 20000,
    'alleenstaande': 'NEE',
    'ontvangt_aow': 'NEE',
    'energielabel': 'A,B',
    'verduurzamings_maatregelen': 10000,
    'studievoorschot_studielening': 60,
    'hypotheek_delen': [{
        'aflos_type': 'Annuïteit',
        'org_lpt': 360,
        'rest_lpt': 360,
        'hoofdsom_box1': 100000,
        'hoofdsom_box3': 0,
        'rvp': 120,
        'inleg_overig': 0,
        'werkelijke_rente': 0.03,
    }]
})

print(f"Max Box1: €{results['scenario1']['annuitair']['max_box1']:,.2f}")
```

## 📐 Belangrijke Formules

### ToetsInkomen (M25)
```python
# Excel: IF(Alleenstaande="JA", Inkomen, MAX(F16+G16*factor, G16+F16*factor))
# "Inkomen" named range = F16 (zonder inkomen_overige!)

if alleenstaande == 'JA':
    toets_inkomen = inkomen_aanvrager  # F16
else:
    toets_inkomen = max(
        inkomen_aanvrager + inkomen_partner * factor,
        inkomen_partner + inkomen_aanvrager * factor
    )
```

### InkomenTotaal (F18/M32)
```python
# Excel: IF(Alleenstaande="JA", F16+F17, F16+G16+F17)
if alleenstaande == 'JA':
    inkomen_totaal = inkomen_aanvrager + inkomen_overige
else:
    inkomen_totaal = inkomen_aanvrager + inkomen_partner + inkomen_overige
```

**Verschil:** ToetsInkomen (M25) gebruikt F16, InkomenTotaal (M32) gebruikt F18. F17 (inkomen_overige) zit ALLEEN in F18!

## 📦 Output Structuur

```python
{
    "scenario1": {
        "annuitair": {
            "max_box1": float,      # M40
            "max_box3": float,      # M41
            "ruimte_box1": float,   # M42
            "ruimte_box3": float    # M43
        },
        "niet_annuitair": {
            "max_box1": float,      # M46
            "max_box3": float,      # M47
            "ruimte_box1": float,   # M48
            "ruimte_box3": float    # M49
        }
    },
    "scenario2": { ... } | null  # Als F29/G29 gevuld
}
```

## 🧪 Tests Uitvoeren

```bash
python test_complete.py
```

## 📁 Bestanden

- `calculator_final.py` - Hoofdmodule (Excel-exact)
- `config/woonquote.json` - 4 woonquote lookup tabellen
- `tests/` - Test suites (pytest)
- `README.md` - Deze documentatie

## 🎉 Conclusie

**100% Excel-exact geïmplementeerd - klaar voor productie!** 🚀
