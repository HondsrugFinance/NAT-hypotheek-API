# Lovable Prompt E1: Dossier bewerkbaar + volledige berekening opslaan

> Kopieer deze prompt in Lovable om twee verbeteringen door te voeren: (1) klantgegevens bewerkbaar maken na opslaan dossier, en (2) stap 2 en 3 mee-opslaan bij het opslaan van een berekening.

---

## Achtergrond

Er zijn twee problemen met het opslaan van dossiers en berekeningen:

1. **Dossier-niveau gegevens niet meer bewerkbaar:** Nadat een volledig klantdossier is opgeslagen, kun je de klantgegevens (naam, telefoonnummer, adres, etc.) niet meer wijzigen. De gebruiker wil een bestaand dossier kunnen openen en de gegevens op dossierniveau kunnen aanpassen.

2. **Berekening slaat niet alles op:** Wanneer een berekening wordt opgeslagen, wordt alleen stap 4 (Berekening — leningdelen) opgeslagen. Stap 2 (Haalbaarheid — inkomen, verplichtingen, onderpand) en stap 3 (Financieringsopzet — investering, kosten, eigen middelen, WOZ) worden **niet** mee-opgeslagen. Hierdoor gaan die gegevens verloren bij het heropenen van een dossier.

---

## Deel 1: Klantgegevens bewerkbaar na opslaan dossier

### Stap 1: Bewerkknop op dossierpagina

Wanneer een gebruiker een bestaand dossier opent (vanuit de dossierlijst), moet er op de dossierpagina een manier zijn om de klantgegevens te bewerken. Dit kan via:

- Een "Bewerken" knop naast de klantgegevens (naam, adres, telefoonnummer, etc.)
- Of door de klantgegevens direct bewerkbaar te maken in een inline formulier / bewerkmodal

**Gewenst gedrag:**

1. Gebruiker opent een bestaand dossier vanuit de dossierlijst
2. De klantgegevens worden getoond (naam, adres, telefoonnummer, e-mail, etc.)
3. Er is een "Bewerken" knop (of potlood-icoon) zichtbaar
4. Bij klikken opent een bewerkformulier met alle klantgegevens-velden (dezelfde velden als in stap 1 "Klant")
5. Na opslaan worden de gewijzigde gegevens direct naar Supabase geschreven
6. De dossiernaam wordt automatisch bijgewerkt als de naam wijzigt (tenzij de gebruiker de dossiernaam handmatig had overschreven)

### Stap 2: Implementatie

Zoek het component dat de dossierpagina toont (waarschijnlijk de pagina waar je naartoe gaat vanuit de dossierlijst — met "Terug naar dossier" link). Dit is de pagina waar berekeningen en aanvragen onder het dossier worden getoond.

Voeg hier een bewerkfunctie toe voor de klantgegevens:

```
Optie A — Bewerkmodal (aanbevolen):
- Toon een "Bewerken" icoon/knop naast de klantnaam
- Bij klikken: open een Dialog/Sheet met de klantgegevens-velden
- Dezelfde velden als stap 1 (Klant): voornaam, achternaam, geboortedatum, telefoonnummer, e-mail, adres, etc.
- Als er een partner is: ook de partnervelden tonen
- "Opslaan" knop schrijft naar Supabase via bestaande dossier update service
- "Annuleren" sluit de modal zonder wijzigingen

Optie B — Inline bewerken:
- Maak de klantgegevens-sectie direct bewerkbaar
- Toon/verberg modus met een "Bewerken"/"Opslaan" toggle
```

**Belangrijk:**
- Hergebruik zoveel mogelijk de bestaande klantgegevens-velden uit stap 1 (KlantStep of vergelijkbaar component)
- Gebruik de bestaande Supabase dossier update functie (in `supabaseDossierService.ts` of `dossierStorage.ts`)
- Toon een success-toast na opslaan en een error-toast bij falen

---

## Deel 2: Stap 2 en 3 mee-opslaan bij berekening

### Stap 3: Onderzoek huidige opslag

De huidige "Opslaan" functie slaat alleen de `scenarios` (stap 4 — leningdelen) op in het `invoer` JSONB-veld van het dossier. Maar de volgende data uit stap 2 en 3 wordt **niet** opgeslagen:

- **Stap 2 (Haalbaarheid):** `invoer.haalbaarheidsBerekeningen[]` — bevat per tab: inkomengegevens (hoofdinkomen aanvrager/partner, overig inkomen, verplichtingen), onderpand (energielabel, EBV/EBB), en de NAT-resultaten
- **Stap 3 (Financieringsopzet):** `invoer.berekeningen[]` (bij Aankoop) of de wijziging-berekeningen (bij Aanpassen) — bevat per berekening: investering (aankoopsom, verbouwing, etc.), kosten (advies, notaris, taxatie), NHG, eigen middelen, WOZ-waarde

### Stap 4: Opslag uitbreiden

Zoek de functie die wordt aangeroepen bij het klikken op "Opslaan" (de opslaan-knop rechtsboven in de wizard). Deze functie schrijft de dossierdata naar Supabase.

Breid deze functie uit zodat bij het opslaan **alle** wizard-stappen worden mee-opgeslagen in het `invoer` JSONB-veld:

```
invoer: {
  klantGegevens: { ... },                    // Stap 1 — wordt al opgeslagen
  haalbaarheidsBerekeningen: [ ... ],         // Stap 2 — NIEUW: moet mee-opgeslagen worden
  berekeningen: [ ... ],                      // Stap 3 (Aankoop) — NIEUW: moet mee-opgeslagen worden
  // of wijziging-specifieke velden voor Aanpassen hypotheek
  scenarios: [ ... ],                         // Stap 4 — wordt al opgeslagen
}
```

**Concreet:**
1. Zoek waar de opslaan-actie de `invoer` payload opbouwt
2. Controleer of `haalbaarheidsBerekeningen` (stap 2 state) wordt mee-opgeslagen — zo niet, voeg het toe
3. Controleer of `berekeningen` of de wijziging-berekeningen (stap 3 state) worden mee-opgeslagen — zo niet, voeg het toe
4. Controleer dat bij het **laden** van een bestaand dossier de data van stap 2 en 3 correct wordt teruggelezen en in de wizard-state wordt gezet

### Stap 5: Laden van opgeslagen stap 2 en 3 data

Bij het openen van een bestaand dossier moeten stap 2 en 3 hun state terugkrijgen uit de opgeslagen `invoer`:

- **Stap 2:** De haalbaarheids-tabs moeten gevuld worden met de opgeslagen inkomengegevens, verplichtingen en onderpand-data
- **Stap 3:** De financieringsopzet-berekeningen moeten gevuld worden met de opgeslagen investering, kosten, eigen middelen en WOZ-waarden

Zoek de functie die een dossier laadt en de wizard-state initialiseert. Controleer dat:
1. `haalbaarheidsBerekeningen` uit de opgeslagen `invoer` wordt gelezen en in de stap 2 state wordt gezet
2. `berekeningen` (of wijziging-data) uit de opgeslagen `invoer` wordt gelezen en in de stap 3 state wordt gezet
3. Als er geen opgeslagen data is voor stap 2/3 (bij oudere dossiers), worden de standaard lege waarden gebruikt als fallback

---

## Verificatie

| # | Check | Verwacht resultaat |
|---|-------|--------------------|
| 1 | Open bestaand dossier vanuit dossierlijst | Klantgegevens zijn zichtbaar (naam, contact, etc.) |
| 2 | Klik "Bewerken" bij klantgegevens | Bewerkformulier opent met alle velden |
| 3 | Wijzig telefoonnummer → Opslaan | Wijziging wordt opgeslagen, success-toast verschijnt |
| 4 | Herlaad pagina | Gewijzigd telefoonnummer is nog steeds zichtbaar |
| 5 | Vul stap 2 (Haalbaarheid) volledig in | Inkomen, verplichtingen en onderpand worden getoond |
| 6 | Vul stap 3 (Financieringsopzet) volledig in | Investering, kosten, eigen middelen en WOZ worden getoond |
| 7 | Klik "Opslaan" | Dossier wordt opgeslagen (success-toast) |
| 8 | Sluit de berekening en open opnieuw vanuit dossierlijst | Stap 2 gegevens (inkomen, verplichtingen, onderpand) zijn bewaard |
| 9 | Navigeer naar stap 3 | Financieringsopzet data (investering, kosten, eigen middelen, WOZ) is bewaard |
| 10 | Navigeer naar stap 4 | Leningdelen (bestaand gedrag) zijn bewaard |
| 11 | Navigeer naar stap 6 (Samenvatting) | Alle secties tonen de correcte waarden |
| 12 | Test met een **nieuw** dossier (nog nooit opgeslagen) | Standaard lege waarden, geen errors |

---

## Samenvatting

| Onderdeel | Wijziging |
|-----------|-----------|
| Dossierpagina (overzicht) | Bewerkknop + bewerkformulier/modal voor klantgegevens |
| Supabase dossier update | Klantgegevens update functie (bestaande service hergebruiken) |
| Opslaan-functie (wizard) | `haalbaarheidsBerekeningen` (stap 2) en `berekeningen` (stap 3) mee-opslaan in `invoer` JSONB |
| Laden-functie (wizard) | Stap 2 en stap 3 state herstellen uit opgeslagen `invoer` data |

**Risico:** Laag-medium. De opslag-uitbreiding raakt de centrale `invoer` data-structuur, maar voegt alleen velden toe — bestaande velden worden niet gewijzigd.
