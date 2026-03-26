"""
KVK Handelsregister Client
===========================
Haalt bedrijfsgegevens op via de KVK API (Kamer van Koophandel).

API docs: https://developers.kvk.nl/documentation
Basisprofiel: GET /api/v1/basisprofielen/{kvkNummer}
Zoeken:       GET /api/v2/zoeken?naam=...

Authenticatie: header `apikey`
Kosten: Zoeken = gratis, Basisprofiel = EUR 0,02/call
API key aanvragen: https://developers.kvk.nl/nl/apply-for-apis

Env var: KVK_API_KEY
"""

import os
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

KVK_BASE = "https://api.kvk.nl/api"


class KVKClient:
    """Client voor de KVK Handelsregister API."""

    def __init__(self, api_key: Optional[str] = None, timeout: float = 15.0):
        self._api_key = api_key or os.environ.get("KVK_API_KEY", "")
        self._timeout = timeout

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    def _headers(self) -> dict:
        return {"apikey": self._api_key}

    # ------------------------------------------------------------------
    # Zoeken (gratis)
    # ------------------------------------------------------------------

    def zoeken(
        self,
        *,
        kvk_nummer: Optional[str] = None,
        naam: Optional[str] = None,
        postcode: Optional[str] = None,
        huisnummer: Optional[int] = None,
        plaats: Optional[str] = None,
        pagina: int = 1,
        resultaten_per_pagina: int = 10,
    ) -> dict:
        """
        Zoek bedrijven in het handelsregister.

        Minimaal 1 zoekparameter vereist: kvk_nummer, naam, postcode, of plaats.
        Gratis endpoint (geen kosten per call).

        Retourneert dict met:
          - resultaten: list[dict] met kvkNummer, naam, adres, type, etc.
          - totaal: int
          - pagina: int
          - error: str (bij fout)
        """
        params = {
            "pagina": pagina,
            "resultatenPerPagina": resultaten_per_pagina,
        }
        if kvk_nummer:
            params["kvkNummer"] = kvk_nummer
        if naam:
            params["naam"] = naam
        if postcode:
            params["postcode"] = postcode.replace(" ", "").upper()
        if huisnummer:
            params["huisnummer"] = huisnummer
        if plaats:
            params["plaats"] = plaats

        if len(params) <= 2:
            return {"error": "Minimaal 1 zoekparameter vereist (kvk_nummer, naam, postcode, of plaats)"}

        try:
            resp = httpx.get(
                f"{KVK_BASE}/v2/zoeken",
                params=params,
                headers=self._headers(),
                timeout=self._timeout,
            )
        except httpx.TimeoutException:
            return {"error": "KVK API timeout — probeer het later opnieuw"}
        except httpx.ConnectError:
            return {"error": "Kan geen verbinding maken met KVK API"}

        if resp.status_code == 401:
            return {"error": "KVK API key ongeldig of ontbreekt"}
        if resp.status_code == 404:
            return {"error": "Geen resultaten gevonden"}
        if resp.status_code == 400:
            body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            return {"error": f"Ongeldig verzoek: {body.get('fout', resp.text[:200])}"}

        resp.raise_for_status()
        data = resp.json()

        resultaten = data.get("resultaten", [])
        return {
            "resultaten": [self._format_zoek_resultaat(r) for r in resultaten],
            "totaal": data.get("totaal", 0),
            "pagina": data.get("pagina", pagina),
        }

    def _format_zoek_resultaat(self, item: dict) -> dict:
        """Formateer een zoekresultaat naar een compact formaat."""
        adres = item.get("adres", {})
        return {
            "kvkNummer": item.get("kvkNummer"),
            "vestigingsnummer": item.get("vestigingsnummer"),
            "naam": item.get("naam"),
            "type": item.get("type"),
            "actief": item.get("actief", "Ja"),
            "adres": {
                "straat": adres.get("binnenlandsAdres", {}).get("straatnaam", ""),
                "huisnummer": adres.get("binnenlandsAdres", {}).get("huisnummer"),
                "postcode": adres.get("binnenlandsAdres", {}).get("postcode", ""),
                "plaats": adres.get("binnenlandsAdres", {}).get("plaats", ""),
            },
        }

    # ------------------------------------------------------------------
    # Basisprofiel (EUR 0,02 per call)
    # ------------------------------------------------------------------

    def basisprofiel(self, kvk_nummer: str) -> dict:
        """
        Haal basisprofiel op voor een KVK-nummer.

        Retourneert dict met:
          - kvkNummer, naam, statutaireNaam, rechtsvorm
          - formeleRegistratiedatum
          - sbiActiviteiten: list[{code, omschrijving}]
          - hoofdvestiging: {vestigingsnummer, naam, adres, ...}
          - totaalWerkzamePersonen
          - handelsnamen: list[str]
          - error: str (bij fout)
        """
        kvk_clean = kvk_nummer.strip().replace(" ", "")
        if not kvk_clean.isdigit() or len(kvk_clean) != 8:
            return {"error": f"Ongeldig KVK-nummer: '{kvk_nummer}' (moet 8 cijfers zijn)"}

        try:
            resp = httpx.get(
                f"{KVK_BASE}/v1/basisprofielen/{kvk_clean}",
                headers=self._headers(),
                timeout=self._timeout,
            )
        except httpx.TimeoutException:
            return {"error": "KVK API timeout — probeer het later opnieuw"}
        except httpx.ConnectError:
            return {"error": "Kan geen verbinding maken met KVK API"}

        if resp.status_code == 401:
            return {"error": "KVK API key ongeldig of ontbreekt"}
        if resp.status_code == 404:
            return {"error": f"Geen bedrijf gevonden voor KVK-nummer {kvk_clean}"}
        if resp.status_code == 400:
            return {"error": f"Ongeldig verzoek voor KVK-nummer {kvk_clean}"}

        resp.raise_for_status()
        data = resp.json()

        return self._format_basisprofiel(data)

    def _format_basisprofiel(self, data: dict) -> dict:
        """Formateer basisprofiel naar gestandaardiseerd formaat."""
        embedded = data.get("_embedded", {})
        hoofdvestiging = embedded.get("hoofdvestiging", {})
        eigenaar = embedded.get("eigenaar", {})

        # Adres uit hoofdvestiging
        adressen = hoofdvestiging.get("adressen", [])
        bezoekadres = next(
            (a for a in adressen if a.get("type") == "bezoekadres"),
            adressen[0] if adressen else {},
        )

        # SBI activiteiten
        sbi = data.get("sbiActiviteiten", [])

        # Handelsnamen
        handelsnamen = [h.get("naam") for h in data.get("handelsnamen", []) if h.get("naam")]

        result = {
            "kvkNummer": data.get("kvkNummer"),
            "naam": data.get("naam"),
            "statutaireNaam": data.get("statutaireNaam"),
            "formeleRegistratiedatum": data.get("formeleRegistratiedatum"),
            "totaalWerkzamePersonen": data.get("totaalWerkzamePersonen"),
            "handelsnamen": handelsnamen,
            "sbiActiviteiten": [
                {"code": s.get("sbiCode"), "omschrijving": s.get("sbiOmschrijving")}
                for s in sbi
            ],
            "adres": {
                "straat": bezoekadres.get("straatnaam", ""),
                "huisnummer": bezoekadres.get("huisnummer"),
                "huisletter": bezoekadres.get("huisletter"),
                "toevoeging": bezoekadres.get("huisnummerToevoeging"),
                "postcode": bezoekadres.get("postcode", ""),
                "plaats": bezoekadres.get("plaats", ""),
            },
            "hoofdvestiging": {
                "vestigingsnummer": hoofdvestiging.get("vestigingsnummer"),
                "naam": hoofdvestiging.get("eersteHandelsnaam"),
            },
        }

        # Rechtsvorm uit eigenaar (indien aanwezig)
        if eigenaar:
            result["rechtsvorm"] = eigenaar.get("uitgebreideRechtsvorm") or eigenaar.get("rechtsvorm")

        return result
