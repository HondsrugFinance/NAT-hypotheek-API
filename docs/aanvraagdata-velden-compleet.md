# AanvraagData — Alle invulvelden (adviesroute)

Bron: `hondsrug-insight-repo/src/utils/aanvraagStorage.ts` + gerelateerde TypeScript bestanden.
Totaal: 200+ invulvelden.

---

## 1. Doelstelling

| Veld | Type |
|------|------|
| `doelstelling` | `aankoop_bestaande_bouw`, `aankoop_nieuwbouw_project`, `aankoop_nieuwbouw_eigen_beheer`, `hypotheek_verhogen`, `hypotheek_oversluiten`, `partner_uitkopen` |

---

## 2. Onderpand

| Veld | Type |
|------|------|
| `postcode` | string |
| `huisnummer` | string |
| `toevoeging` | string |
| `straat` | string |
| `woonplaats` | string |
| `typeWoning` | `woning`, `appartement`, `overig` |
| `soortOnderpand` | `2-onder-1-kap`, `benedenwoning`, `bovenwoning`, `galerijflat`, `hoekwoning`, `maisonnette`, `tussenwoning`, `vrijstaand`, `waterwoning`, `woon-winkelpand`, `woonwagen-stacaravan`, `woonboerderij` |
| `marktwaarde` | number |
| `marktwaardeNaVerbouwing` | number |
| `marktwaardeVastgesteldMet` | `taxatierapport`, `desktoptaxatie`, `verkoopcontract`, `verklaring_makelaar`, `woz_waarde`, `schatting`, `koop_aanneemovereenkomst` |
| `wozWaarde` | number |
| `energielabel` | `A++++ met garantie` t/m `G`, `geen_label` |
| `afgiftedatumEnergielabel` | datum |
| `erfpacht` | boolean |
| `jaarlijkseErfpacht` | number |
| `eeuwigdurend` | boolean |
| `einddatumErfpacht` | datum |
| `indexatieErfpacht` | number (%) |
| `eigendomAandeelAanvrager` | number (%) |
| `eigendomAandeelPartner` | number (%) |

---

## 3. Financieringsopzet (aankoop)

### Bestaande bouw
| Veld | Type |
|------|------|
| `aankoopsomWoning` | number |
| `overdrachtsbelastingPercentage` | 0.01, 0.02, 0.08, 0.104 |
| `overdrachtsbelasting` | number |
| `transportakte` | number |
| `verbouwing` | number |
| `ebv` (energiebesparende voorzieningen) | number |
| `ebb` (energiebespaarbudget) | number |
| `aankoopmakelaar` | number |

### Nieuwbouw project
| Veld | Type |
|------|------|
| `koopsomGrond` | number |
| `aanneemsom` | number |
| `meerwerkOpties` | number |
| `bouwrente` | number |

### Nieuwbouw eigen beheer
| Veld | Type |
|------|------|
| `koopsomKavel` | number |
| `sloopOudeWoning` | number |
| `bouwWoning` | number |
| `meerwerkEigenBeheer` | number |

### Alle typen
| Veld | Type |
|------|------|
| `consumptief` | number |
| `adviesBemiddeling` | number |
| `hypotheekakte` | number |
| `taxatiekosten` | number |
| `bankgarantie` | number |

### NHG
| Veld | Type |
|------|------|
| `nhgToepassen` | boolean |
| `nhgHypotheekBedrag` | number |
| `nhgKosten` | number |

### Eigen middelen
| Veld | Type |
|------|------|
| `overbrugging` | number |
| `overwaarde` | number |
| `eigenGeld` | number |
| `schenkingLening` | number |

---

## 4. Persoonsgegevens (aanvrager + partner)

### Persoon
| Veld | Type |
|------|------|
| `geslacht` | `man`, `vrouw`, `anders` |
| `voorletters` | string |
| `voornamen` | string |
| `roepnaam` | string |
| `tussenvoegsel` | string |
| `achternaam` | string |
| `geboortedatum` | datum |
| `geboorteplaats` | string |
| `geboorteland` | string |
| `nationaliteit` | string |
| `eerderGehuwd` | boolean |
| `datumEchtscheiding` | datum |
| `weduweWeduwnaar` | boolean |

### Adres & contact
| Veld | Type |
|------|------|
| `postcode` | string |
| `huisnummer` | string |
| `toevoeging` | string |
| `straat` | string |
| `woonplaats` | string |
| `land` | string |
| `email` | string |
| `telefoonnummer` | string |

### Identiteit
| Veld | Type |
|------|------|
| `legitimatiesoort` | `paspoort`, `europese_id`, `rijbewijs`, `visum` |
| `legitimatienummer` | string |
| `afgiftedatum` | datum |
| `geldigTot` | datum |
| `afgifteplaats` | string |
| `afgifteland` | string |

### Werkgever
| Veld | Type |
|------|------|
| `naam` | string |
| `adres` | string |
| `postcode` | string |
| `plaats` | string |
| `telefoon` | string |
| `dienstverband` | string |
| `functie` | string |
| `inDienstSinds` | datum |
| `contractType` | string |
| `brutoJaarinkomen` | number |
| `vakantiegeld` | boolean |
| `dertiendeMaand` | boolean |

---

## 5. Huishouden

| Veld | Type |
|------|------|
| `heeftPartner` | boolean |
| `burgerlijkeStaat` | `samenwonend`, `gehuwd`, `geregistreerd_partner` |
| `samenlevingsvorm` | string |

### Kinderen (per kind)
| Veld | Type |
|------|------|
| `geboortedatum` | datum |
| `roepnaam` | string |
| `achternaam` | string |

---

## 6. Inkomen (aanvrager + partner)

### Basis per inkomenitem
| Veld | Type |
|------|------|
| `type` | `loondienst`, `onderneming`, `pensioen`, `uitkering`, `vermogen`, `ander_inkomen` |
| `soort` | string |
| `inkomstenbron` | string |
| `ingangsdatum` | datum |
| `einddatum` | datum |
| `jaarbedrag` | number |
| `isAOW` | boolean |

### Loondienst — dienstverband
| Veld | Type |
|------|------|
| `soortBerekening` | `inkomensbepaling_loondienst`, `werkgeversverklaring`, `flexibel_jaarinkomen`, `arbeidsmarktscan` |
| `beroepstype` | string |
| `functie` | string |
| `soortDienstverband` | string |
| `gemiddeldUrenPerWeek` | number |
| `directeurAandeelhouder` | string |
| `inDienstSinds` | datum |
| `dienstbetrekkingBijFamilie` | string |
| `proeftijd` | string |
| `proeftijdVerstreken` | string |
| `einddatumContract` | datum |
| `loonbeslag` | string |
| `onderhandseLening` | string |

### Loondienst — werkgever
| Veld | Type |
|------|------|
| `naamWerkgever` | string |
| `postcodeWerkgever` | string |
| `huisnummer` | string |
| `adresWerkgever` | string |
| `vestigingsplaats` | string |
| `vestigingsland` | string |
| `kvkNummer` | string |
| `rsin` | string |

### Loondienst — werkgeversverklaring berekening
| Veld | Type |
|------|------|
| `brutoSalaris` | number |
| `periode` | `jaar`, `maand`, `week`, `4_weken` |
| `vakantiegeldPercentage` | number |
| `vakantiegeldBedrag` | number |
| `eindejaarsuitkering` | number |
| `onregelmatigheidstoeslag` | number |
| `overwerk` | number |
| `provisie` | number |
| `structureelFlexibelBudget` | number |
| `vebAfgelopen12Maanden` | number |
| `dertiendeMaand` | number |
| `variabelBrutoJaarinkomen` | number |
| `vastToeslagOpHetInkomen` | number |

### Loondienst — flexibel jaarinkomen
| Veld | Type |
|------|------|
| `jaar1` | number |
| `jaar2` | number |
| `jaar3` | number |

### Loondienst — IBL (UWV)
| Veld | Type |
|------|------|
| `gemiddeldJaarToetsinkomen` | number |
| `maandelijksePensioenbijdrage` | number |
| `aantalWerkgevers` | number |

### Onderneming
| Veld | Type |
|------|------|
| `soort` | `inkomen_uit_onderneming`, `inkomensverklaring_ondernemer` |
| `rekenmethode` | `regulier`, `1_2_3_methode` |
| `nettoWinstJaar1` | number |
| `nettoWinstJaar2` | number |
| `nettoWinstJaar3` | number |
| `bedrijfsnaam` | string |
| `kvkNummer` | string |
| `type` | `Zelfstandige zonder personeel`, `Zelfstandige met personeel` |
| `rechtsvorm` | `Eenmanszaak`, `VOF`, `BV`, `Maatschap`, `CV`, `NV`, `Stichting` |
| `startdatumOnderneming` | datum |

### Pensioen
| Veld | Type |
|------|------|
| `ouderdomspensioen.ingangsdatum` | datum |
| `ouderdomspensioen.einddatum` | datum |
| `ouderdomspensioen.bedrag` | number |
| `ouderdomspensioen.standPer` | datum |
| `partnerpensioen.verzekerdVoor` | number |
| `wezenpensioen.verzekerd` | number |

### Uitkering
| Veld | Type |
|------|------|
| `soortUitkering` | `ANW`, `IVA`, `Nabestaandenpensioen`, `Verzekering`, `WGA`, `Wajong` |
| `jaarlijksBrutoInkomen` | number |
| `startdatum` | datum |
| `einddatum` | datum |

### Ander inkomen
| Veld | Type |
|------|------|
| `soortAnderInkomen` | `Anders`, `Box 2`, `Partneralimentatie`, `Resultaat uit overige werkzaamheden`, `Schenking` |
| `jaarlijksBrutoInkomen` | number |
| `startdatum` | datum |
| `einddatum` | datum |

---

## 7. Verplichtingen (per verplichting)

| Veld | Type |
|------|------|
| `type` | `doorlopend_krediet`, `aflopend_krediet`, `private_lease`, `studieschuld`, `partneralimentatie` |
| `kredietnummer` | string |
| `ingangsdatum` | datum |
| `einddatum` | datum |
| `maatschappij` | string |
| `renteFiscaalAftrekbaar` | `ja`, `nee` |
| `status` | `lopend`, `aflossen_tijdens_passeren`, `aflossen_voor_passeren` |
| `kredietbedrag` | number |
| `maandbedrag` | number |
| `saldo` | number |
| `rentepercentage` | number |
| `nogTeBetalen` | number |
| `nogAfTeLossen` | number |

---

## 8. Bestaande hypotheken

### Inschrijving
| Veld | Type |
|------|------|
| `geldverstrekker` | string |
| `inschrijving` | number (bedrag) |
| `rangorde` | number |
| `eigenaar` | `gezamenlijk`, `aanvrager`, `partner` |
| `nhg` | boolean |

### Leningdeel
| Veld | Type |
|------|------|
| `leningdeelnummer` | string |
| `aflosvorm` | `annuitair`, `lineair`, `aflossingsvrij`, `bankspaarhypotheek`, `spaarhypotheek`, `beleggingshypotheek`, `levensverzekering`, `krediet` |
| `bedrag` | number |
| `rentePercentage` | number |
| `fiscaalRegime` | `box1_na_2013`, `box1_voor_2013`, `box3` |
| `ingangsdatum` | datum |
| `looptijd` | number (maanden) |
| `einddatum` | datum |
| `ingangsdatumRvp` | datum |
| `renteVastPeriode` | number (jaren) |
| `einddatumRvp` | datum |
| `renteAftrekTot` | datum |

---

## 9. Nieuwe hypotheeksamenstelling

| Veld | Type |
|------|------|
| `geldverstrekker` | string |
| `productlijn` | string |
| `passeerdatum` | datum |
| `nhg` | boolean |
| `nieuweLeningdelen[]` | HypotheekLeningdeel (zie sectie 8) |
| `meenemenLeningdelen[]` | HypotheekLeningdeel |
| `leningdelenElders[]` | HypotheekLeningdeel |
| `bestaandeLeningdelen[]` | HypotheekLeningdeel |

---

## 10. Voorzieningen (verzekeringen)

### Per verzekering
| Veld | Type |
|------|------|
| `type` | `levensverzekering`, `overlijdensrisicoverzekering`, `lijfrenteverzekering`, `woonlastenverzekering`, `aov` |
| `eigenaar` | `aanvrager`, `partner`, `gezamenlijk` |
| `aanbieder` | string |
| `polisnummer` | string |
| `ingangsdatum` | datum |
| `einddatum` | datum |
| `soortDekking` | `gelijkblijvend`, `annuitair_dalend`, `lineair_dalend` |
| `premieType` | `maandelijks`, `kwartaal`, `halfjaarlijks`, `jaarlijks`, `koopsom` |
| `premieBedrag` | number |

### Per verzekerde persoon
| Veld | Type |
|------|------|
| `orvDekking` | number |
| `dekkingAO` | number |
| `dekkingWW` | number |
| `dekkingAOV` | number |

### Werkgeversverzekeringen
| Veld | Type |
|------|------|
| `type` | `wga_hiaat_basis`, `wga_hiaat_uitgebreid`, `wia_excedent`, `loon_doorbetaling_ziekte` |
| `eersteJaar` | percentage |
| `tweedeJaar` | percentage |

---

## 11. Vermogen

### IBAN
| Veld | Type |
|------|------|
| `ibanAanvrager` | string |
| `ibanPartner` | string |

### Vermogen items (per item)
| Veld | Type |
|------|------|
| `type` | `spaargeld`, `beleggingen`, `schenking`, `overig` |
| `saldo` | number |
| `eigenaar` | `gezamenlijk`, `aanvrager`, `partner` |
| `maatschappij` | string |
| `isIncassorekening` | boolean |
