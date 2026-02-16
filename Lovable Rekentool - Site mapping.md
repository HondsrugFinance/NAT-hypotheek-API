# Hondsrug Finance Rekentool 2026 — Complete Project Knowledge

Geëxporteerd op: 2026-02-10
Bijgewerkt op: 2026-02-16 (avond)

---

## 1. Components: Extra Posten List

De `ExtraPostenList` component biedt een gestandaardiseerde interface voor het beheren van extra financiële posten in zowel de Financieringsopzet (Aanvraag) als de Berekening-wizard (Stap 4). Het maakt gebruik van een `EditableLabel` (tekst op witte achtergrond met een potlood-icoon) voor de omschrijving, geplaatst direct boven een standaard `CurrencyInput` voor het bedrag. Dit patroon waarborgt verticale uitlijning en consistente tussenruimtes tussen verschillende invoervelden in complexe formulieren.

---

## 2. Data: Storage and Terminology

Dossiers worden lokaal opgeslagen (localStorage) en gesynchroniseerd naar Supabase. Gebruiksterminologie is strikt "Aanvrager" en "Partner" in plaats van "Klant 1/2". De "Partner"-toggle in Stap 1 (Klant) fungeert als input voor de status: "Nee" betekent alleenstaande (alleenstaande = JA), "Ja" betekent dat er een partner is (alleenstaande = NEE). Contactgegevens (postcode, huisnummer, straat, woonplaats, telefoon, email) worden opgeslagen per aanvrager en partner. Straat en woonplaats worden automatisch opgehaald via PDOK API bij het invoeren van postcode + huisnummer.

---

## 3. Features: Application — Income: Loondienst

Inkomen uit loondienst gebruikt standaardwaarden: 'Anders' (dienstverband), 'Medewerker' (functie), 40 uur, 1 werkgever en einddatum op de AOW-datum. Methoden include Inkomensbepaling, Werkgeversverklaring, Flexibel, and Arbeidsmarktscan. Crucially, the calculated 'gemiddeldJaarToetsinkomen' from the sub-object must be synchronized to the top-level 'jaarbedrag' field during save to ensure it appears in summaries and downstream calculations.

AOW-datum propagatie: Bij wijziging van de geboortedatum wordt de AOW-datum berekend via de NAT API (`/aow-categorie`). Deze datum wordt automatisch doorgezet naar einddatums van dienstverbanden en startdatums van pensioenen. Het "Inkomen vanaf AOW-datum" telt alleen inkomensposten mee waarvan de einddatum NA de AOW-datum valt (loondienst dat eindigt op de AOW-datum wordt correct uitgesloten).

---

## 4. Features: Application — Samenstellen: Doelstelling

De Doelstelling-sectie in Samenstellen (Aanvraag) configureert de hoofdopzet van de hypotheek:
1. Doelstellingen: Aankoop (Bestaande bouw, Nieuwbouw project of eigen beheer), Hypotheek verhogen, Hypotheek oversluiten, Partner uitkopen.
2. Relocatie: De functionaliteit voor 'Bestedingsdoelen' en de toggle 'Oversluiten en verhogen' zijn verplaatst van de Onderpand-sectie naar de Doelstelling-sectie voor een betere gebruikersflow.
3. Hypotheek oversluiten: Bevat een multi-selectie voor bestaande hypotheken en leningdelen uit de inventarisatie. 'Kosten oversluiten' staat standaard op 'Ja' bij oversluiten en verhogen.
4. Partner uitkopen: Toont 'Overige bestedingsdoelen' (gelijk aan verhogen). De eigendomsverdeling is voor deze flow verplaatst naar de Onderpand-sectie.
5. Automatisering: De selectie van leningdelen of woningen in deze sectie triggert de synchronisatie van adres-, waarde- en erfpachtgegevens naar de rest van de aanvraag-workflow.

---

## 5. Features: Application — Samenstellen: Hypotheek Configuratie

De sectie 'Samenstellen' (Aanvraag Stap 2) configureert de nieuwe hypotheekopzet:
1. Titel: De sectietitel is dynamisch: 'Samenstellen: [Geselecteerde Doelstelling]' (bijv. 'Samenstellen: Hypotheek verhogen').
2. Veldvolgorde (Modificatie): Toggle 'Nieuwe inschrijving' → Woningselectie → Hypotheekinschrijving (bedrag of selectie) → Geldverstrekker & Productlijn → Passeerdatum.
3. Passeerdatum: Default op de 1e van de maand na de gehele opvolgende maand (bijv. 9 feb wordt 1 april). Opgeslagen in YYYY-MM-DD formaat.
4. Hypotheekinschrijving: Bedrag valt automatisch terug op de 'benodigde hypotheek' als fallback wanneer het veld leeg is.
5. Geldverstrekker & Productlijn: Dropdowns met mapping per verstrekker. Bij 'Meenemen' beperkt tot partijen uit de inventarisatie.
6. Leningdelen (Aankoop):
   - Meenemen: Ingangsdatum default naar passeerdatum; looptijd wordt herberekend o.b.v. de onveranderde einddatum.
   - Nieuw: Default bedrag is het resterende tekort; bij initialisatie wordt automatisch een eerste leningdeel aangemaakt met het volledige benodigde bedrag en 5% rente.
   - Tijdslijnen: Ingangsdatum/RVP-ingang volgen passeerdatum; looptijd default op 360 maanden; RVP op 10 jaar.
   - Sync: Looptijd (1-360 maanden) en einddatum zijn bidirectioneel gesynchroniseerd.
7. Leningdeel elders: Apart blok onderaan, uitgesloten van de hypotheeksom en financieringswaarschuwing. Bevat een eigen geldverstrekker-selector en een toggle 'Meenemen in toetsing' (standaard uit) voor de NAT API. Defaults: 5% rente, 30 jaar looptijd/rente-aftrek, 10 jaar RVP. Toegestane aflosvormen: Annuïteiten (default), Lineair, Aflossingsvrij.
8. Waarschuwing (Oranje): De financieringswaarschuwing (verschil tussen benodigde hypotheek en leningdelen) staat bovenaan de leningdelen-sectie.

---

## 6. Features: Application — Samenstellen: Hypotheek Configuratie Modificatie

Voor modificatie-flows (Verhogen, Oversluiten, Partner uitkopen) gelden specifieke regels in de sectie 'Samenstellen':
1. Nieuwe inschrijving: Toggle vervangt de oude keuzes. Default UIT voor Verhogen/Uitkoop; AAN voor Oversluiten.
   - UIT: Selecteer bestaande woning/inschrijving; de geldverstrekker en het inschrijvingsbedrag worden read-only overgenomen.
   - AAN: Selecteer woning en definieer nieuwe inschrijving/geldverstrekker. Het invulveld 'Hypotheekinschrijving' (bedrag) is alleen zichtbaar als deze toggle AAN staat.
2. Bestaande/Behouden leningdelen: Getoond in een blok boven de nieuwe leningdelen.
   - Synchronisatie: Wijzigingen in de 'Huidige hypotheek' (Inventarisatie) worden automatisch en onmiddellijk gesynchroniseerd met dit blok.
   - Status: Standaard 'read-only' (vergrendeld/grijs). Een bewerk-knop (potlood) per leningdeel maakt wijzigingen mogelijk.
   - Labeling: Labels voor deze delen tonen de herkomst in het formaat: [Geldverstrekker] · [Hypotheeknummer] · [Leningdeelnaam/nummer].
   - Acties: Bevat een 'Split' functie om een leningdeel in twee gelijke helften te verdelen.
   - Revert: Het opnieuw vergrendelen herstelt de originele waarden en verwijdert splitsingen na bevestiging ("Ja").
3. Filtering (Oversluiten): Toont in het blok 'Behouden leningdelen' alleen de delen die in de Doelstelling-fase NIET zijn aangevinkt voor oversluiten.
4. Waarschuwing (Oranje):
   - Verhogen/Uitkoop: Benodigde hypotheek = (Totaal - Huidige hypotheek). De waarschuwing vergelijkt dit doelbedrag alleen met de NIEUWE leningdelen.
   - Oversluiten: Benodigde hypotheek = Totaalbedrag (nieuwe delen moeten de volledige oversluiting dekken).
   - Bestaande, behouden en externe leningdelen worden altijd uitgesloten van de 'totaal leningdelen' som in de waarschuwing.

---

## 7. Features: Application — Samenstellen: Max Hypotheek Berekening

In de sectie 'Samenstellen' (Aanvraag Stap 2) is een maximale hypotheekberekening geïntegreerd die gebruikmaakt van de NAT API.
1. Input: Gebaseerd op het huidige acceptatie-inkomen (vóór AOW), alle leningdelen (bestaand, behouden, nieuw), financiële verplichtingen (BKR-limieten, leningen, studieschuld, alimentatie), erfpachtcanon (maandbedrag) en verduurzamingsbudgetten (EBV/EBB).
2. AOW-logica voor API:
   - Alleenstaande: JA als AOW-leeftijd is bereikt.
   - Partners (beiden AOW): JA.
   - Partners (gemengd): JA indien het inkomen van de AOW-gerechtigde partner hoger is dan dat van de partner die de AOW-leeftijd nog niet heeft bereikt.
3. Energielabel: Prioriteit bij geselecteerd onderpand in Samenstellen, fallback naar inventarisatie.
4. Restant RVP: Voor bestaande, behouden of meegenomen leningdelen wordt de resterende rentevaste periode berekend als het exacte aantal maanden tussen de passeerdatum en de einddatum RVP (essentieel voor periodes < 120 maanden).
5. Restant Looptijd: Voor bestaande, behouden of meegenomen leningdelen wordt de resterende looptijd (`rest_lpt`) berekend als het aantal maanden tussen de passeerdatum en de einddatum. Indien de einddatum ontbreekt, wordt deze afgeleid van de `ingangsdatum` + `looptijd`.
6. UI Layout: Configuratie en resultatenkaart staan bovenaan in een twee-koloms grid (desktop) met sticky resultaten; leningdeel-blokken daaronder over de volledige breedte. Bestaande delen tonen 'Restant looptijd (mnd)' met de berekende waarde op basis van de passeerdatum.

---

## 8. Features: Application — Samenstellen: Max Hypotheek Over 10 Jaar

In de sectie 'Samenstellen' wordt een tweede maximale hypotheekberekening ('over 10 jaar') getoond indien één of beide partners de AOW-leeftijd bereikt binnen 10 jaar na de passeerdatum. Deze berekening hanteert een peildatum die gelijk is aan de eerste AOW-datum binnen dit venster. Voor de toetsing wordt uitsluitend rekening gehouden met inkomen dat na deze peildatum doorloopt (bijv. pensioen) en leningdelen met een restant looptijd van ten minste 120 maanden op de passeerdatum.

---

## 9. Features: Application — Samenstellen: Onderpand

De Onderpand-sectie in Samenstellen (Aanvraag) is context-afhankelijk en neemt gegevens over van Inventarisatie:
1. Layout: Wordt weergegeven op een halve schermbreedte (max-w-[50%]). Straat- en woonplaatsvelden tonen geen 'Automatisch' preview wanneer postcode en huisnummer leeg zijn.
2. Selectie: In modificatie-flows (Verhogen, Oversluiten, Partner uitkopen) begint de sectie met een woningselectie uit de inventarisatie. Als er slechts één woning aanwezig is, wordt deze automatisch geselecteerd.
3. Sync: Bij selectie worden adresgegevens, marktwaarde en erfpachtgegevens direct overgenomen van het woningitem in Inventarisatie.
4. Zichtbaarheid: Velden voor Energielabel en Erfpacht zijn alleen zichtbaar bij de bijbehorende bestedingsdoelen ('Verbetering eigen woning' of 'Afkoop erfpacht').
5. Eigendomsverdeling: Voor de doelstelling 'Partner uitkopen' wordt het blok 'Eigendomsverdeling nieuw' direct onder de geselecteerde woning getoond.
6. Marktwaarde: 'Marktwaarde na verbouwing' synchroniseert automatisch met de 'Marktwaarde' als deze laatste hoger wordt ingesteld.

---

## 10. Features: Application Structure

De hypotheekaanvraag (Aanvraag) is een 3-staps wizard:
1. Inventarisatie (met zijbalk-navigatie: Klantgegevens, Woning, Huidige hypotheek, Inkomen, Verplichtingen, Voorzieningen, Vermogen).
2. Samenstellen (met zijbalk-navigatie: Doelstelling, Samenstellen, Onderpand, Financieringsopzet).
3. Aanvragen (geen submenu).
Het laden van gegevens bevat een saneringslaag die ontbrekende geneste objecten initialiseert en een 'isInitialized' vlag gebruikt om herhalende effecten te voorkomen.

Default stap bij openen: 5 (Maandlasten). URL-parameter `?step=5` wordt ondersteund. Navigatie heeft vorige/volgende knoppen. Bij wijziging van doelstelling wordt een bevestigingsdialoog getoond als er downstream data is.

Aanvragen worden geprefilled vanuit dossiergegevens: contactgegevens (straat, woonplaats, telefoon, email) voor aanvrager en partner, doelstelling afgeleid van eerste berekening, financieringsopzet gekopieerd. Bij opslaan kan de gebruiker kiezen tussen "Overschrijven" of "Nieuw opslaan" (SaveChoiceDialog).

---

## 11. Features: Application — Verplichtingen

De sectie Verplichtingen beheert financiële lasten met type-specifieke logica:
- Doorlopend krediet: Maandbedrag staat vast op 2% van de limiet (niet aanpasbaar).
- Aflopend krediet: Gebruikt annuïteitenberekeningen. Peildatum staat standaard op de 1e van de maand.
- Private lease: 'Rente fiscaal aftrekbaar' is verborgen.
- Studieschuld: Vereenvoudigd naar handmatige invoer van 'Maandlast' en 'Uitstaande schuld'.
- Partneralimentatie: Bevat alleen type, data en maandbedrag.
- Maatschappij: De types 'Doorlopend krediet', 'Aflopend krediet' en 'Private lease' maken gebruik van een uitgebreide dropdownlijst (~200 opties) met Nederlandse financiële instellingen. Bij keuze 'Anders' verschijnt een extra veld voor handmatige invoer.
UI: Bedragen gebruiken een €-prefix en Nederlandse formattering. Labels voor berekende velden zijn niet onderstreept. Een 'Looptijd' sectie groepeert ingangsdatum, looptijd (selectie 1-10, 12, 15 of 35 year) en einddatum. Rente gebruikt twee decimalen (X,XX%) met natural typing. Statussen: 'Lopend', 'Aflossen tijdens passeren', 'Aflossen voor passeren'.

---

## 12. Features: Application — Voorzieningen

De sectie Voorzieningen is vereenvoudigd en context-bewust:
1. Veld-opschoning: Voor AOV zijn de velden 'Premieduur' en 'Deel-premie' verwijderd. Voor ORV, Levensverzekeringen en Lijfrente zijn diverse routinevelden (verpand, premiesplitsing, etc.) verwijderd.
2. Contextuele Defaults: Verzekerden en verzekeringsnemers volgen de 'eigenaar' van het record. Bij 'Aanvrager' als eigenaar staan de eerste verzekeringnemer/verzekerde op Aanvrager (en partner op de tweede plek). Bij 'Partner' als eigenaar is dit omgekeerd. Bij AOV staat de verzekerde standaard op Aanvrager.
3. UI: 'Aanbieder' maakt gebruik van een uitgebreide dropdownlijst (~150+ opties).
4. Producten: ORV ondersteunt diverse dekkingsvormen; Lijfrente staat standaard op 'Levenslang' uitkering.

---

## 13. Features: Core Flows and Wizard

De applicatie bevat twee hoofdstromen: 'Aankoop woning' en 'Aanpassen hypotheek'. Beide volgen een identieke 6-staps wizard: Klant, Haalbaarheid, Financieringsopzet (voorheen Investering), Berekening, Maandlasten en Samenvatting. Navigatiestijlen variëren per stap: Stap 2 (Haalbaarheid) en Stap 4 (Berekening) gebruiken paginabrede tabs voor meerdere scenario's; Stap 3 (Financieringsopzet) gebruikt een side-by-side grid voor directe vergelijking van scenario's. In Stap 2 worden namen automatisch gegenereerd: "Huidige situatie", "Toekomstige situatie", en daarna "Toekomstige situatie 1, 2, ...". In de 'Wijzigen' stroom heten scenario's standaard 'Bestaande hypotheek' en 'Nieuwe hypotheek'.

---

## 14. Features: Dossier Naming Logic

Dossiers volgen een intelligent naamgevingsformaat via de `formatCombinedNames` utility. Wanneer partners dezelfde achternaam hebben (of de achternaam van de partner ermee begint), worden de namen samengevoegd (bijv. 'Jos en Anita van Dijk'). Bij verschillende achternamen worden beide namen volledig getoond. Titels in de berekeningsflows gebruiken het formaat 'Klantnaam • D maand JJJJ' (bijv. 'Jos en Anita van Dijk • 4 februari 2026'), waarbij een bullet de pipe separator vervangt. De synchronisatie tussen de invoervelden in Stap 1 en de dossiernaam blijft actief totdat de gebruiker de titel handmatig aanpast. De Dossier Detail hub toont in de hoofdtitel uitsluitend de klantnamen zonder datum.

---

## 15. Features: Financieringsopzet UI and Terminology

Stap 3 (Financieringsopzet) vergelijkt scenario's in een side-by-side grid met subgrid-uitlijning (lg:[grid-template-rows:subgrid] en lg:[grid-row:span_7/8]) om horizontale symmetrie tussen de verschillende secties (Header, Aankoop/Type aanpassing, Kosten, NHG, Eigen middelen, WOZ-waarde, Samenvatting) te garanderen.
1. WOZ-waarde: In de 'Aankoop' stroom is dit een sectie onder Eigen middelen met een toggle (standaard uit); in de 'Wijzigen' stroom is het een direct invoerveld.
2. NHG: Hanteert de grens van € 470.000 (2026). In de 'Wijzigen' stroom wordt de tekst '(grens € 470.000)' weggelaten in het label.
3. Samenvatting: Titels "Totaal" en "Hypotheek" zijn vetgedrukt, evenals de bijbehorende bedragen.
4. Functies: Bevat overdrachtbelasting keuzes (nu bewerkbaar, niet meer auto-berekend) en calculators voor overbrugging en overwaarde (alleen bij Aankoop).
5. NHG-provisie: 0,4% (verlaagd van 0,6% op 2026-02-16).

---

## 16. Features: Haalbaarheid — Conditional Results

Resultaten in de Haalbaarheid-stap (Stap 2) volgen strikte logica:
1. Inkomen <= 0: Alle resultaten in 'Maximale hypotheek' en 'Ruimte en lasten' worden als € 0 getoond.
2. Inkomen > 0: Toont werkelijke (ook negatieve) waarden voor de maximale hypotheek en ruimte-onderdelen.
3. Kleurcodering: Positieve bedragen/percentages in 'Ruimte & Lasten' en bij LTV gebruiken de primaire kleur (groen); negatieve waarden gebruiken de kleur voor fouten (rood).
4. LTV Styling: De LTV-kaart gebruikt de primaire kleur voor tekst en randen om consistentie met de titel 'Maximale Hypotheek' te waarborgen.

---

## 17. Features: Haalbaarheid — NAT Functionaliteit

The "Haalbaarheid" (Feasibility) step is a full non-macro implementation of NAT-sheet 2026. It supports multiple comparative calculations per dossier and requires inputs for income, single-person status, AOW status, debts (student vs BKR), energy labels (EBV/EBB), and loan parts (Box 1/3, repayment types, interest rates). Outputs must show GHF annuity max mortgage vs. actual monthly load max mortgage.

---

## 18. Features: Haalbaarheid — State Management

Berekeningen in de Haalbaarheid-stap zijn volledig onafhankelijk. Elke tab (bijv. Berekening 1, 2) heeft zijn eigen unieke staat voor inkomen, financiële verplichtingen, onderpand en leningdelen. Het kopiëren van een berekening voert een diepe kopie (deep clone) uit van alle gegevens, terwijl de "+"-knop een nieuwe berekening met standaardwaarden initialiseert.

---

## 19. Features: Leningdeel Management UI

Beheerknoppen voor leningdelen en scenario-tabs (Stap 2 t/m 4) volgen een strikte, project-brede volgorde van links naar rechts: Toevoegen (+), Kopiëren, en Verwijderen (prullenbak). Verwijderknoppen zijn gedeactiveerd als er slechts één item overblijft. In de tab-interface van Stap 2 en 4 zijn de actieknoppen gegroepeerd aan de rechterkant van de tab-rij. In Stap 5 zijn beheerknoppen (+) en Copy/Delete voor scenario's niet aanwezig.

---

## 20. Features: Maandlasten UI Logic

Stap 5 (Maandlasten) synchroniseert tabs en titels met Stap 4. De titels zijn hier niet bewerkbaar.
1. Tabel-layout: Kolommen zijn Leningdeel (170px, bewerkbaar), Aflosvorm (160px), Looptijd (70px), Bedrag (100px), RVP (60px), Rente% (70px), Spacer (20px), Rente (90px), Aflossing (70px), Totaal (90px). De tabel heeft een min-breedte van 950px.
2. Terminologie: Aflosvormen gebruiken volledige namen (bijv. 'Annuïteitenhypotheek', 'Aflossingsvrije hypotheek'). De kolom 'Aflossing/inleg' is hernoemd naar 'Aflossing'.
3. Berekening: Bij een '(Bank)spaarhypotheek' wordt de inleg opgeteld bij de maandlast van het leningdeel en de totale bruto/netto maandlasten.
4. Samenvatting: Toont de labels 'Totaal', 'Renteaftrek' en 'Netto maandlast' in de eerste kolom. 'Totaal' heeft dezelfde font-weight en kleur als 'Netto maandlast'. 'Renteaftrek' heeft geen percentage-achtervoegsel.

---

## 21. Features: Scenario Sync and Constraints

In Stap 5 (Maandlasten) worden scenario-titels automatisch overgenomen van Stap 4 (Berekening) om synchronisatie te waarborgen. In tegenstelling tot Stap 3 en 4 zijn de titels in Stap 5 niet bewerkbaar (geen EditableTitle component). Daarnaast ondersteunt het veld 'Eigen geld' in Stap 3 negatieve waarden voor correcties, waarbij het label in de samenvatting dynamisch wisselt tussen 'Af:' (positief) en 'Bij:' (negatief).

---

## 22. Features: Workflow Phases

The application follows a central three-phase workflow: Calculation → Application → Advice. Users begin with a calculation (Aankoop or Wijzigen), which can be converted into a mortgage application (Aanvraag) once saved, eventually leading to a generated advice document. A dossier can contain multiple calculations, applications, and advice records.

---

## 23. Logic: Excel Engine Requirements

The application must match the calculation logic, formulas, and rounding of "Rekentool - 2026.xlsm" and "NAT-sheet 2026.xlsm" with cent-level precision. Core calculations include GHF annuity testing, actual monthly load-based maximum mortgage, and 120-month interest rate rules. Birth dates (defaulting to 01-01-2001 if empty) are used to determine AOW status (reached, within 10 years, or not) and impact tax deduction/net costs.

---

## 24. Logic: Excel Mapping and Constraints

The "Haalbaarheid" (Feasibility) implementation uses an explicit INPUT→CELL mapping table (defined in natCellMapping.ts) to link UI fields to specific Excel cells (e.g., income, student loans, BKR, energy labels, EBV, and loan parts Box 1/3). This ensures non-negotiable parity with NAT-sheet 2026 for student loan logic (dedicated input vs. generic debt), BKR forfait rules (24% yearly limit), and interest rate rules (<=119 months uses 5% fixed toetsrente; >=120 uses actual rate).

---

## 25. Logic: Fiscale Parameters 2026

De NHG-grens (Nationale Hypotheek Garantie) voor 2026 is vastgesteld op € 470.000. Dit bedrag wordt gebruikt als bovengrens voor de automatische berekening van NHG-kosten in de investeringsstap. De NHG-provisie is 0,4% (was 0,6%, verlaagd op 2026-02-16).

---

## 26. Logic: Monthly Costs API Integration

De renteaftrek (tax deduction) wordt berekend via een externe API (mortgage-monthly-costs.onrender.com) in zowel de 'Aankoop' als 'Wijzigen' stroom zodra de gebruiker Stap 5 (Maandlasten) opent.

Mapping-logica:
1. WOZ-waarde: Gebruikt een fallback-volgorde: Handmatige WOZ-waarde > Aankoopbedrag (alleen bij Aankoop) > Marktwaarde uit haalbaarheid > Benodigde hypotheek.
2. Partners: Belastbaar inkomen is de som van hoofdinkomen, lijfrente en ontvangen alimentatie, minus betaalde partneralimentatie (maandlast * 12).
3. Leningdelen: Elk leningdeel met een Box 3-deel wordt gesplitst in twee API-onderdelen (Box 1 en Box 3). Aflosvormen worden gemapt naar 'annuity' (ook voor spaarhypotheek), 'linear' of 'interest_only'.

Het veld "Renteaftrek" in de UI toont het netto belastingvoordeel (`net_tax_effect_monthly`) uit de API-response. Dit bedrag (inclusief EWF-verrekening) vervangt lokale berekeningen en wordt gebruikt om de netto maandlasten te bepalen in Stap 5 en de Samenvatting (Stap 6).

---

## 27. Logic: NAT API Integration

Berekeningen voor "Haalbaarheid" verlopen via de API. Mapping-regels:
1. Strings: `alleenstaande` en `ontvangt_aow` zijn "JA" of "NEE".
2. Maandbedrag: `jaarlast_overige_kredieten`, `erfpachtcanon_per_jaar` en `studievoorschot_studielening` worden als maandwaarden verstuurd.
3. Jaarbedrag: `te_betalen_partneralimentatie_aanvrager` wordt geconverteerd van maand naar jaar (* 12).
4. Energielabel: Gebruikt strikte API-strings, waaronder "A++++ met garantie".
5. EBV/EBB: Bedrag direct naar `verduurzamings_maatregelen`.
6. Outputs: UI toont `max_box1`, `ruimte_box1` en `ruimte_box3` uit `scenario1`.

---

## 28. Logic: Wijzigen Flow Logic

De 'Aanpassen hypotheek' stroom volgt de 6-staps wizard van de aankoopstroom.
1. Financieringsopzet (Stap 3): Begint standaard met één berekening genaamd 'Berekening 1'. Toont velden op basis van aanpassingstype: 'Verhogen' en 'Oversluiten' tonen 'Huidige hypotheek' en 'Verbouwing'; 'Partner uitkopen' toont 'Huidige hypotheek' en 'Uitkoop partner'. De velden 'Overbrugging', 'Overige investeringen' en 'Schenking/starterslening' zijn verwijderd. 'Boeterente/kosten' is verkort naar 'Boeterente'.
2. Berekening (Stap 4): Toont standaard altijd twee scenario's ('Bestaande hypotheek' en 'Nieuwe hypotheek'). De benodigde hypotheek voor 'Nieuwe hypotheek' is de som van de huidige hypotheek, investeringen en kosten minus eigen middelen uit de eerste berekening van Stap 3.
3. WOZ-waarde: In deze stroom is dit een direct invoerveld zonder toggle.
4. Terminologie: Scenario's in Stap 4 en 5 heten standaard 'Bestaande hypotheek' en 'Nieuwe hypotheek'. In de samenvatting (Stap 6) wordt de investeringssectie getoond als 'Financieringsopzet'.

---

## 29. Application Architecture

### Tech Stack
- React 18 + TypeScript + Vite
- Tailwind CSS + shadcn/ui
- Supabase (Lovable Cloud) for auth, profiles, dossiers & aanvragen
- localStorage als fallback + dual-write naar Supabase
- External APIs: NAT API, Monthly Costs API, Postcode Lookup

### Key Files
- `src/types/hypotheek.ts` — All TypeScript types and default values
- `src/utils/natCellMapping.ts` — NAT-sheet cell mapping
- `src/utils/berekeningen.ts` — Core calculation logic
- `src/utils/fiscaleParameters.ts` — Fiscal parameters 2026
- `src/utils/aowBerekeningen.ts` — AOW age calculations
- `src/utils/dossierStorage.ts` — localStorage CRUD + dual-write naar Supabase
- `src/utils/aanvraagStorage.ts` — Aanvraag state persistence + dual-write naar Supabase
- `src/config/apiConfig.ts` — NAT API URL, key en helper-functies (gecentraliseerd)
- `src/services/natApiService.ts` — NAT API integration
- `src/services/monthlyCostsService.ts` — Monthly costs API
- `src/services/supabaseDossierService.ts` — Supabase CRUD voor dossiers
- `src/services/supabaseAanvraagService.ts` — Supabase CRUD voor aanvragen
- `src/hooks/useNatConfig.ts` — NAT Config API hook (fiscaal, geldverstrekkers, dropdowns)
- `src/contexts/NatConfigContext.tsx` — React context voor NAT Config
- `src/hooks/useNatApiCalculation.ts` — NAT API hook (debounced)
- `src/hooks/useAOWData.ts` — AOW date calculations (via NAT API /aow-categorie)
- `src/hooks/useAowPropagation.ts` — Global AOW date propagation naar einddatums
- `src/hooks/useMonthlyCostsCalculation.ts` — Monthly costs hook
- `src/hooks/useAanvraagMaxHypotheek.ts` — Max mortgage (Aanvraag)
- `src/hooks/useAanvraagMaxHypotheekOver10Jaar.ts` — Max mortgage over 10 years
- `src/hooks/usePostcodeLookup.ts` — PDOK postcode → straat/woonplaats lookup
- `supabase/functions/postcode-lookup/index.ts` — Edge Function voor PDOK API

### Routes
- `/` — Home/Index
- `/aankoop` — Aankoop wizard (6 steps)
- `/aanpassen` — Aanpassen wizard (6 steps)
- `/dossiers` — Dossier overview
- `/dossier/:id` — Dossier detail hub
- `/aanvraag/:dossierId` — Aanvraag wizard (3 steps)
- `/admin-migratie` — Admin: localStorage → Supabase migratie
- `/profiel` — User settings
- `/auth` — Authentication

### External Services
- **NAT API** (`nat-hypotheek-api.onrender.com`) — Hypotheekberekening + AOW-categorie + config endpoints
- **Monthly Costs API** (`mortgage-monthly-costs.onrender.com`) — Bruto-netto maandlasten
- **PDOK API** (`api.pdok.nl/bzk/locatieserver/search/v3_1/free`) — Postcode → straat/woonplaats (via Supabase Edge Function)

---

## 30. Features: Dossier Creation Flow (2026-02-16)

Vanuit de indexpagina kan een nieuw dossier worden aangemaakt via een dialog met contactgegevens:
1. Drie kaarten op één rij: "Nieuw dossier", "Aankoop woning", "Aanpassen hypotheek".
2. Dialog vereist: postcode (gevalideerd formaat: 1234 AB), huisnummer, telefoonnummer, email.
3. Straat en woonplaats worden automatisch opgehaald via PDOK na invoer postcode + huisnummer (400ms debounce).
4. "Kopiëren van aanvrager" knop voor partner-contactgegevens.
5. Creëert een minimaal aankoop-dossier en navigeert naar de detailpagina.
6. Dossier `laatst_gewijzigd` wordt automatisch bijgewerkt bij het opslaan van een aanvraag.

---

## 31. Features: Overbrugging Leningtype (2026-02-16)

Een nieuw leningtype 'Overbrugging' (bridge loan) is toegevoegd aan de hypotheekdelen:
1. Type definitie: `aflossingsvorm: 'overbrugging'` in `src/types/hypotheek.ts`.
2. NAT API mapping: Wordt gemapt naar 'Aflossingsvrij' (interest-only) in `natApiService.ts`.
3. Monthly Costs API: Behandeld als 'interest_only' in `monthlyCostsService.ts`.
4. Defaults: 24 maanden looptijd, 12 maanden rentevaste periode, 4,30% rente.
5. Exclusies: Uitgesloten van totaalberekeningen en financieringswaarschuwingen.
6. Auto-fill: Overbruggingsbedrag wordt automatisch ingevuld vanuit `invoer.berekeningen[n].overbrugging`.

---

## 32. Features: Partner Burgerlijke Staat (2026-02-16)

Nieuwe conditionele velden in de Klantgegevens-sectie (Inventarisatie):
1. **Burgerlijke staat**: Dropdown, alleen zichtbaar als partner aanwezig. Opties: samenwonend, gehuwd, geregistreerd partner.
2. **Samenlevingsvorm**: Conditioneel op burgerlijke staat:
   - Samenwonend: met/zonder samenlevingscontract
   - Gehuwd: gemeenschap van goederen, beperkte gemeenschap, huwelijkse voorwaarden, buitenlands recht
   - Geregistreerd partner: gemeenschap van goederen, beperkte gemeenschap, partnerschapsvoorwaarden
3. Velden resetten bij verwijderen partner.
4. Opgeslagen in aanvragen JSONB (`data.burgerlijkeStaat`, `data.samenlevingsvorm`).

---

## 33. Features: Aanvraag Naming Logic (2026-02-16)

Aanvragen en berekeningen volgen een genummerde naamgevingslogica:
1. Aanvraagnamen worden afgeleid van de gekoppelde berekening: "Aanvraag – Aankoop: Bestaande bouw 1".
2. Berekeningen van hetzelfde type worden genummerd: "Bestaande bouw 1", "Bestaande bouw 2", etc.
3. Bij dupliceren: eerste kopie behoudt basisnaam, tweede krijgt "(kopie)", derde "(kopie 2)", etc.
4. Icons: Wijzigings-aanvragen krijgen secundaire kleur (bg-secondary/10), overige aanvragen primaire kleur (bg-primary/10).

---

## 34. Features: Overdrachtsbelasting Bewerkbaar (2026-02-16)

De overdrachtsbelasting in de Financieringsopzet is nu handmatig bewerkbaar:
1. Percentage-wijzigingen synchroniseren met het bedrag.
2. Automatisch herberekenen bij waarde-wijzigingen is verwijderd.
3. Gebruiker kan het bedrag handmatig aanpassen na initiële berekening.

---

## 35. Features: EBB Auto-fill Verwijderd (2026-02-16)

De automatische invulling van EBB (Energie Besparende Besteding) op basis van energielabel is verwijderd:
1. Het maximale EBB-bedrag wordt nog wel getoond in het label.
2. Gebruikers moeten het EBB-bedrag nu handmatig invoeren.

---

## 36. Features: PDOK Postcode Lookup (2026-02-16)

Automatische adres-lookup via de PDOK API (Publieke Dienstverlening Op de Kaart):
1. **Endpoint**: `api.pdok.nl/bzk/locatieserver/search/v3_1/free`
2. **Implementatie**: Supabase Edge Function `postcode-lookup` + hook `usePostcodeLookup.ts`
3. **Trigger**: 400ms debounce na invoer postcode + huisnummer
4. **Output**: Vult straat en woonplaats automatisch in
5. **Scope**: Werkt voor zowel aanvrager als partner contactgegevens
6. **Auth**: Geen authenticatie vereist (publieke Nederlandse overheids-API)

---

## 37. Data: Supabase Dual-Write Architecture (2026-02-13)

Dossiers en aanvragen worden nu naar zowel localStorage als Supabase geschreven (dual-write):
1. **Schrijven**: Elke save schrijft eerst naar localStorage (snel, offline-capable), daarna async naar Supabase.
2. **Lezen**: Supabase-first bij laden; valt terug op localStorage als Supabase niet bereikbaar is.
3. **Services**: `supabaseDossierService.ts` (CRUD dossiers) en `supabaseAanvraagService.ts` (CRUD aanvragen) met camelCase↔snake_case mapping.
4. **Audit trail**: Alle Supabase-operaties worden gelogd in de `audit_log` tabel (user, action, table, record_id, timestamp).
5. **RLS**: Row-Level Security actief — alle geauthenticeerde gebruikers kunnen lezen, alleen eigenaren mogen wijzigen.
6. **Cascading delete**: Verwijderen van een dossier verwijdert automatisch alle gekoppelde aanvragen (FK CASCADE).
7. **Timestamp-propagatie**: Bij opslaan van een aanvraag wordt `laatst_gewijzigd` van het parent-dossier automatisch bijgewerkt.

### Database-tabellen (Supabase)

| Tabel | Doel |
|-------|------|
| `dossiers` | Hypotheekdossiers met klantgegevens, scenario's, invoer |
| `aanvragen` | Hypotheekaanvragen gekoppeld aan dossiers (FK) |
| `audit_log` | Audit trail van alle data-operaties |
| `profiles` | Adviseursprofiel (bestaand) |

### Migraties
- `20260213072611`: Tabellen `dossiers`, `aanvragen`, `audit_log` + RLS + triggers
- `20260213081539`: Fix trigger-functie (`update_laatst_gewijzigd_column`)

---

## 38. Features: Admin Migratie Page (2026-02-13)

Een admin-pagina (`/admin-migratie`) voor het migreren van legacy localStorage-data naar Supabase:
1. Leest dossiers en aanvragen uit `hondsrug-dossiers-2026` en `hondsrug-aanvragen-2026` localStorage keys.
2. **Migreren**: Upsert elk item naar Supabase via de service-laag, met voortgangs-indicator.
3. **Owner toewijzing**: Wijst huidige ingelogde gebruiker toe als eigenaar als niet ingesteld.
4. **Opruimen**: Identificeert en verwijdert "wezen-aanvragen" (aanvragen zonder gekoppeld dossier) uit localStorage.
5. **Resultaat**: Toont aantal geslaagde migraties en eventuele fouten.

---

## 39. Features: Doelstelling Navigatie en Bevestiging (2026-02-16)

De Doelstelling-sectie in Samenstellen (Aanvraag) heeft nu een bevestigingsdialoog bij het wijzigen van de doelstelling als er al downstream data bestaat:
1. **Detectie**: Controleert of onderpand, financieringsopzet of samenstellen-data aanwezig is.
2. **Waarschuwing**: AlertDialog met tekst dat deze secties worden gewist bij wijziging.
3. **Knoppen**: "Annuleren" (behoud huidige keuze) of "Doorgaan" (wis downstream data).
4. **Doel**: Voorkomt onbedoeld verlies van ingevulde gegevens.

---

## 40. Features: NAT Config API Integratie (2026-02-16)

Alle hardcoded configuratiedata in de frontend wordt nu opgehaald uit de NAT API bij app-mount:
1. **Hook**: `useNatConfig.ts` fetcht parallel `/config/fiscaal-frontend`, `/config/geldverstrekkers`, `/config/dropdowns`.
2. **Context**: `NatConfigContext` maakt config beschikbaar in de hele app via `useNatConfigContext()`.
3. **Cache**: In-memory cache — config wordt één keer geladen per tab-sessie.
4. **Fallback**: Bij API-fout worden hardcoded defaults gebruikt + toast-melding aan gebruiker.
5. **Fiscaal**: `getFiscaleParameters(natConfig.fiscaal)` vervangt directe `FISCALE_PARAMETERS_2026` lookups in berekeningen.
6. **Dropdowns**: Beroepen, dienstverbanden, onderpandtypen, energielabels, geldverstrekkers en financiële instellingen komen uit de API.
7. **Scope**: 18 bestanden aangepast — alle pagina's, berekeningslogica en dropdown-componenten.

---

## 41. Features: API Config Externalisatie (2026-02-16)

API-configuratie is gecentraliseerd in `src/config/apiConfig.ts`:
1. **NAT API URL**: Leest `VITE_NAT_API_URL`, default `https://nat-hypotheek-api.onrender.com`.
2. **Monthly Costs API URL**: Leest `VITE_MONTHLY_COSTS_API_URL`, default `https://mortgage-monthly-costs.onrender.com`.
3. **API Key**: Leest `VITE_NAT_API_KEY`, met hardcoded fallback.
4. **Doel**: Eén plek om alle API-endpoints te configureren, per omgeving aanpasbaar via environment variables.
