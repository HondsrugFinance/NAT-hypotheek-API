# Briefing: Hondsrug Finance Rekentool

## Wat is dit document?

Dit document beschrijft de Hondsrug Finance Rekentool — een webapplicatie waarmee hypotheekadviseurs hypotheekberekeningen maken, aanvragen samenstellen en samenvattingen genereren. Het doel is jou (ChatGPT) volledig te informeren over welke data en berekeningen beschikbaar zijn, zodat we samen kunnen bepalen wat er in een **adviesrapport-PDF** moet komen.

---

## 1. Wat de tool doet

De Rekentool is gebouwd voor hypotheekadviseurs van Hondsrug Finance. De adviseur doorloopt een wizard met de klant en vult stap voor stap alle relevante gegevens in. Op basis daarvan berekent de tool:

1. **Maximale hypotheek** — hoeveel de klant maximaal kan lenen (NAT 2026 normen)
2. **Financieringsopzet** — overzicht van kosten, eigen middelen en benodigd hypotheekbedrag
3. **Netto maandlasten** — bruto maandlast, renteaftrek, netto maandlast

De tool genereert nu een **samenvatting-PDF** (3-4 pagina's) met deze drie onderdelen. Wij willen een uitgebreider **adviesrapport** maken.

---

## 2. De stappen in de app

### Stap 1: Inventarisatie (klantgegevens verzamelen)

De adviseur verzamelt alle relevante informatie over de klant:

#### 2.1 Klantgegevens
- **Aanvrager**: naam, geboortedatum, adres (postcode + huisnummer → straat en woonplaats automatisch), telefoon, e-mail
- **Partner** (optioneel): zelfde velden + burgerlijke staat en samenlevingsvorm
  - Burgerlijke staat: samenwonend / gehuwd / geregistreerd partnerschap
  - Samenlevingsvorm: met of zonder contract, gemeenschap van goederen, huwelijkse voorwaarden, etc.

#### 2.2 Huidige woning(en)
- Adres, woningtype (woning, appartement, herenhuis, villa, maisonette)
- Woontoepassing: eigen woning (box 1), huurwoning, inwonend, tweede woning (box 3)
- Marktwaarde, bouwjaar

#### 2.3 Huidige hypotheek (indien van toepassing)
Per bestaande hypotheek:
- Geldverstrekker (34+ opties: ABN AMRO, ING, Rabobank, etc.)
- Hypotheeknummer, ingangsdatum, einddatum

Per leningdeel binnen de hypotheek:
- Aflosvorm: annuïteit, lineair, aflossingsvrij, overbrugging, spaarhypotheek
- Hoofdsom box 1 en box 3 (€)
- Looptijd (maanden), rentepercentage, rentevaste periode
- Inleg overig (voor spaarhypotheek)

#### 2.4 Inkomen
Per persoon (aanvrager en/of partner), met meerdere inkomensbronnen:

**Loondienst:**
- Soort dienstverband: vast, met intentieverklaring, flexibel, etc.
- Beroepstype (67+ opties)
- Jaarbedrag (bruto jaarinkomen)
- Uren per week, aantal werkgevers
- Arbeidsmarktscan-fase (A, B, C, N.v.t.)
- Ingangsdatum, einddatum (koppelt automatisch aan AOW-datum)

**Pensioen:**
- Jaarbedrag, ingangsdatum (koppelt aan AOW-datum)

**Lijfrente:**
- Jaarbedrag, ingangsdatum, einddatum

**Huurinkomsten:**
- Jaarbedrag

**Partneralimentatie (ontvangen):**
- Maandbedrag

**Overig inkomen:**
- Jaarbedrag

**AOW-berekening:**
De tool berekent automatisch de AOW-leeftijd op basis van geboortedatum. Dit bepaalt:
- Of de klant al AOW ontvangt
- Of de klant binnen 10 jaar AOW bereikt (triggert een tweede berekening "over 10 jaar")
- Automatische aanpassing van einddata van loondienst en startdata van pensioen

#### 2.5 Financiële verplichtingen
- **BKR-registraties**: doorlopend krediet (limiet → maandlast = 2% van limiet) of aflopend krediet (maandlast)
- **Niet-BKR verplichtingen**: zelfde structuur
- **Private lease**: maandbedrag, looptijd
- **Studieschuld**: maandlast, restschuld
- **Partneralimentatie (betalen)**: maandbedrag, ingangsdatum, einddatum

#### 2.6 Voorzieningen (verzekeringen)
- **AOV** (arbeidsongeschiktheidsverzekering): verzekeraar, premie, type
- **ORV** (overlijdensrisicoverzekering): verzekeraar, premie
- **Levensverzekering**: verzekeraar, premie
- **Lijfrente**: verzekeraar, uitkeringswijze

#### 2.7 Vermogen
- Spaarrekeningen (naam + bedrag)
- Beleggingen (naam + bedrag)
- Andere activa (naam + bedrag)

---

### Stap 2: Samenstellen (hypotheek structureren)

#### 2.8 Doelstelling
De adviseur selecteert het doel:
- **Aankoop bestaande bouw** — kopen van een bestaande woning
- **Aankoop nieuwbouw** — kopen in nieuwbouwproject
- **Aankoop eigen beheer** — zelfbouw
- **Hypotheek verhogen** — extra lenen op bestaande hypotheek
- **Hypotheek oversluiten** — herfinancieren bij andere geldverstrekker
- **Partner uitkopen** — uitkoop bij scheiding

Per doel zijn er specifieke velden (aankoopsom, bestedingsdoelen, welke leningdelen oversluiten, eigendomsverdeling bij uitkoop, etc.)

#### 2.9 Nieuwe hypotheekstructuur
- Geldverstrekker + productlijn (gefilterd per geldverstrekker)
- Passeerdatum
- Hypotheekinschrijving bedrag
- **Leningdelen** (nieuw, bestaand/behouden, of extern):
  - Aflosvorm, bedrag (box 1/box 3), looptijd, rentepercentage, rentevaste periode
  - Bij oversluiten: selectie welke bestaande delen mee te nemen
  - "Leningdeel elders": apart leningdeel bij andere partij (optioneel mee te nemen in toetsing)

#### 2.10 Haalbaarheidsberekening (maximale hypotheek)
De tool stuurt alle inkomen, verplichtingen en leningdelen naar de API en berekent:

**Scenario 1 (huidige situatie):**
- Maximale hypotheek box 1 (annuïtair)
- Maximale hypotheek box 3
- Beschikbare ruimte (max minus bestaande schuld)
- Toetsinkomen, toetsrente, woonquote

**Scenario 2 (over 10 jaar, alleen als AOW binnen 10 jaar):**
- Zelfde berekening maar met inkomen na AOW-datum
- Alleen leningdelen met resterende looptijd ≥ 120 maanden

**Debug-informatie:**
- Toetsinkomen (€)
- Toetsrente (%)
- Woonquote box 1 en box 3 (%)
- Gewogen werkelijke rente (%)
- Energielabel bonus (€)

#### 2.11 Onderpand
- Adres, marktwaarde, marktwaarde na verbouwing
- Energielabel (8 categorieën: van "Geen label" tot "A++++ met garantie")
- Energiebesparende voorzieningen (€, handmatig)
- Erfpachtcanon per jaar (€)
- Eigendomsverdeling (bij uitkoop): huidig % aanvrager/partner → nieuw %

#### 2.12 Financieringsopzet
Stapsgewijs opgebouwd:
1. **Aankoopsom / soort aanpassing** — koopsom of huidige hypotheek
2. **Kosten** — overdrachtsbelasting (handmatig, % en €), taxatie, advieskosten, notariskosten, makelaarskosten, boeterente, overige kosten
3. **NHG** — Nationale Hypotheek Garantie (toggle, grens €470.000, provisie 0,4%)
4. **Eigen middelen** — spaargeld, schenking, starterslening
5. **WOZ-waarde** — handmatig of automatisch uit koopsom
6. **Samenvatting** — totaal kosten, totaal eigen middelen, benodigd hypotheekbedrag

---

### Stap 3: Maandlasten berekenen

De tool berekent per scenario de netto maandlasten:

**Per leningdeel:**
- Maandelijkse rente
- Maandelijkse aflossing (annuïteit, lineair of aflossingsvrij)
- Bruto maandlast

**Fiscaal:**
- Eigenwoningforfait (EWF) op basis van WOZ-waarde (staffeltabel)
- Hypotheekrenteaftrek box 1 (marginaal tarief, gemaximeerd)
- Wet Hillen correctie (als EWF > aftrekbare rente, met jaarlijks afbouwpercentage)
- Partner-verdeling renteaftrek (optimalisatie over 2 partners)

**Resultaat:**
- Bruto maandlast (rente + aflossing)
- Renteaftrek (fiscaal voordeel)
- Netto maandlast (bruto minus renteaftrek)

---

## 3. Wat de tool nu al genereert

### Samenvatting-PDF (3-4 pagina's)

De huidige PDF bevat:
1. **Voorblad** — logo, bedrijfsgegevens, klantnaam, datum, dossiernummer
2. **Klantgegevens** — aanvrager (+ partner) persoonsgegevens
3. **Toelichting** — vrije tekst met uitleg over het rapport
4. **Maximaal haalbare hypotheek** — per scenario (max 3 naast elkaar): inkomen, verplichtingen, maximale hypotheek
5. **Onderpand** — WOZ-waarde, energielabel
6. **Financieringsopzet** — per scenario: kosten, eigen middelen, benodigd hypotheekbedrag
7. **Maandlasten** — per scenario: leningdelen (tabel), bruto, renteaftrek, netto maandlast
8. **Disclaimer** — juridische voorbehouden

### Concept e-mail
De tool kan de samenvatting-PDF als bijlage in een concept e-mail klaarzetten in Outlook (via Microsoft Graph API). De adviseur controleert en verstuurt handmatig.

---

## 4. Beschikbare berekeningen (wat de backend kan)

| Berekening | Beschrijving | Beschikbaar? |
|-----------|-------------|-------------|
| Maximale hypotheek | NAT 2026 normen, per scenario | ✅ Ja |
| Netto maandlasten | Per maand, met belastingeffecten | ✅ Ja |
| Eigenwoningforfait (EWF) | Op basis van WOZ en staffeltabel | ✅ Ja |
| Hypotheekrenteaftrek | Marginaal tarief, gemaximeerd | ✅ Ja |
| Wet Hillen | Correctie bij EWF > rente | ✅ Ja |
| Partner-verdeling | Optimale verdeling renteaftrek | ✅ Ja |
| AOW-berekening | AOW-datum en categorie | ✅ Ja |
| Annuïteit/lineair/aflossingsvrij | Per leningdeel, per maand | ✅ Ja |
| Aflossingsverloop (30 jaar) | Maand-voor-maand restschuld | ❌ Nog niet (te bouwen) |
| Rentegevoeligheid (what-if) | Maandlast bij hogere rente | ❌ Nog niet (te bouwen) |
| Jaarprojectie (30 jaar) | Restschuld + renteaftrek per jaar | ❌ Nog niet (te bouwen) |
| Scenario-vergelijking | Scenario's naast elkaar | ❌ Nog niet (te bouwen) |

De "nog te bouwen" berekeningen kunnen we toevoegen als het adviesrapport ze nodig heeft.

---

## 5. Beschikbare referentiedata

| Data | Inhoud |
|------|--------|
| Geldverstrekkers | 34 aanbieders met productlijnen |
| Beroepen | 67 beroepstitels |
| Energielabels | 8 categorieën met max. verduurzamingsbedragen |
| Studielening | Correctiefactoren per startjaar |
| Fiscale regels | Belastingschijven, max aftrekpercentage, EWF-staffel, Hillen-afbouw (per jaar) |
| AOW-leeftijden | Tabel per geboortedatum |
| Dropdown-opties | Alle keuzemenu's (dienstverband, woningtype, overdrachtsbelasting, etc.) |

---

## 6. Belastingregels 2026 (samengevat)

- **Belastingschijven box 1**: 36,97% tot €38.441, daarboven 49,50%
- **AOW-schijven**: afwijkend (lagere premie volksverzekeringen)
- **Max hypotheekrenteaftrek**: gemaximeerd op effectief tarief (2026: 36,97%)
- **Eigenwoningforfait**: staffel op basis van WOZ-waarde (ca. 0,35% voor woningen €75.000-€1.310.000)
- **Wet Hillen**: als EWF > aftrekbare rente, correctie met jaarlijks afnemend percentage
- **NHG-grens 2026**: €470.000, provisie 0,4%
- **Toetsrente**: 5,0% (of werkelijke rente als hoger)

---

## 7. Voorbeeldscenario

**Klant: Harry Slinger, alleenstaand, 40 jaar**
- Bruto jaarinkomen: €80.000
- Dienstverband: vast
- Geen partner, geen kinderen
- Doel: aankoop bestaande woning, €350.000 koopsom
- Energielabel: A of B
- Spaargeld: €25.000

**Berekend:**
- Maximale hypotheek: €326.250
- Financieringsbehoefte: €380.737 (koopsom + k.k. + taxatie + advies + NHG)
- Eigen middelen: €25.000
- Benodigd hypotheekbedrag: €355.737
- 1 leningdeel: annuïteit, 30 jaar, 4,50%, RVP 10 jaar
- Bruto maandlast: €1.855
- Renteaftrek: €588
- Netto maandlast: €1.267

---

## Doel van deze briefing

Met bovenstaande informatie weet je precies:
- Welke klantgegevens de adviseur invoert
- Welke berekeningen de tool kan maken
- Welke data beschikbaar is voor een adviesrapport

Nu willen we samen bepalen: **wat moet er in het adviesrapport komen?** Denk aan secties, inhoud, welke berekeningen we willen tonen, welke adviesteksten erbij moeten, en hoe het rapport eruit moet zien voor de klant.
