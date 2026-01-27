# ToetsInkomen Fix - Verificatie Rapport

## 🎯 Probleem
ToetsInkomen (M25) gebruikte incorrectly `inkomen_totaal` (F18) bij alleenstaand.

## ✅ Oplossing
ToetsInkomen (M25) gebruikt nu correct:
- Bij alleenstaand: `inkomen_aanvrager` (F16) - **ZONDER** inkomen_overige
- Bij samen: `MAX(F16+G16*factor, G16+F16*factor)` - ook zonder inkomen_overige

Woonlast formules gebruiken correct `inkomen_totaal` (F18) met inkomen_overige.

## 📊 Excel Formule
```
M25 = IF(Alleenstaande="JA", Inkomen, MAX(F16+G16*cFactor, G16+F16*cFactor))
```
Waarbij `Inkomen` named range = `F16` (niet F18!)

## 🧪 Test Resultaat

### Test Scenario: Inkomen Overige €10,000
**Inputs:**
- Hoofd inkomen aanvrager: €50,000
- Inkomen overige: €10,000
- Alleenstaande: JA
- Totaal: €60,000

**Berekening:**
```
F16 (inkomen_aanvrager) = €50,000
F17 (inkomen_overige) = €10,000
F18 (inkomen_totaal) = €60,000

M25 (ToetsInkomen) = F16 = €50,000 ✓
M32 (InkomenRef) = F18 = €60,000 ✓

Woonquote lookup: met €50,000
Woonlast berekening: met €60,000
```

**Woonquote Verificatie:**
```
Scenario A (€50k totaal, geen overige):
  WoonquoteBox1: 0.216
  WoonquoteBox3: 0.169
  Max hypotheek: €217,425

Scenario B (€50k + €10k overige = €60k totaal):
  WoonquoteBox1: 0.216 ✓ (IDENTIEK!)
  WoonquoteBox3: 0.169 ✓ (IDENTIEK!)
  Max hypotheek: €257,511

Verschil: +€40,085 (18% meer ruimte!)
```

**Conclusie:** ✓ Woonquote blijft exact gelijk, hypotheekruimte neemt toe!

## 📈 Impact
- Woonquote wordt bepaald met LAGER inkomen (F16)
- Woonlast wordt berekend met HOGER inkomen (F18)
- Resultaat: MEER hypotheekruimte bij inkomen_overige > 0
- Dit is CORRECT volgens Excel formule M25

## ✅ All Tests Passed
```
✓ Test 1-5: Excel testcases (5/5 passed)
✓ Extra 1-4: Energielabel & Studielening (4/4 passed)
✓ Extra 5: Inkomen Overige verificatie (1/1 passed)

Total: 10/10 tests passed
Tolerance: €0.01
```

## 🎉 Status
**COMPLEET EN GEVERIFIEERD**
- ToetsInkomen gebruikt correct F16 (niet F18)
- Woonquote blijft exact gelijk met inkomen_overige
- Alle outputs exact volgens Excel
- Klaar voor productie!
