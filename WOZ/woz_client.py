"""
WOZ Waardeloket Client
======================
Haalt WOZ-waarden op via de publieke Kadaster API (wozwaardeloket.nl).
Geen API key nodig. Rate limit: 60 req/min, 5.000 req/dag.

Flow:
  1. PDOK Locatieserver (postcode+huisnummer) → nummeraanduiding-ID
  2. Kadaster WOZ API (nummeraanduiding-ID)   → WOZ-waarden per peildatum
"""

import httpx
from typing import Optional

WOZ_BASE_URL = "https://api.kadaster.nl/lvwoz/wozwaardeloket-api/v1"
PDOK_LOCATIE_URL = "https://api.pdok.nl/bzk/locatieserver/search/v3_1/free"


class WOZClient:
    """Client voor het WOZ Waardeloket (Kadaster API)."""

    def __init__(self, timeout: float = 15.0):
        self._timeout = timeout

    # ------------------------------------------------------------------
    # Stap 1: Adres zoeken via PDOK Locatieserver
    # ------------------------------------------------------------------

    def zoek_adres(
        self,
        postcode: str,
        huisnummer: int,
        toevoeging: Optional[str] = None,
    ) -> list[dict]:
        """
        Zoek adressen via PDOK Locatieserver op postcode + huisnummer.
        Retourneert lijst van matches met nummeraanduiding_id.
        """
        postcode_clean = postcode.replace(" ", "").upper()
        q = f"postcode:{postcode_clean} AND huisnummer:{huisnummer}"
        if toevoeging:
            q += f" AND huisnummertoevoeging:{toevoeging}"

        resp = httpx.get(
            PDOK_LOCATIE_URL,
            params={
                "q": q,
                "fq": "type:adres",
                "rows": 10,
                "fl": "weergavenaam,nummeraanduiding_id,postcode,huisnummer,"
                      "huisnummertoevoeging,huisletter,straatnaam,woonplaatsnaam",
            },
            timeout=self._timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", {}).get("docs", [])

    # ------------------------------------------------------------------
    # Stap 2: WOZ-waarden ophalen via Kadaster API
    # ------------------------------------------------------------------

    def wozwaarde_by_nummeraanduiding(self, nummeraanduiding_id: str) -> dict:
        """Haal WOZ-waarden op via BAG nummeraanduiding-ID (16 cijfers)."""
        url = f"{WOZ_BASE_URL}/wozwaarde/nummeraanduiding/{nummeraanduiding_id}"
        resp = httpx.get(url, timeout=self._timeout)
        resp.raise_for_status()
        return resp.json()

    def wozwaarde_by_objectnummer(self, wozobjectnummer: int) -> dict:
        """Haal WOZ-waarden op via wozobjectnummer."""
        url = f"{WOZ_BASE_URL}/wozwaarde/wozobjectnummer/{wozobjectnummer}"
        resp = httpx.get(url, timeout=self._timeout)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Gecombineerde lookup: postcode + huisnummer → WOZ-waarden
    # ------------------------------------------------------------------

    def opvragen(
        self,
        postcode: str,
        huisnummer: int,
        toevoeging: Optional[str] = None,
    ) -> dict:
        """
        Haal WOZ-waarden op voor een adres (postcode + huisnummer).

        Retourneert dict met:
          - adres: {straat, huisnummer, postcode, woonplaats}
          - woz_waarden: [{peildatum, waarde}, ...]
          - meest_recente_waarde: int | None
          - meest_recente_peildatum: str | None
          - wozobjectnummer: int | None
          - error: str (bij fout)
        """
        # Stap 1: zoek adres via PDOK
        docs = self.zoek_adres(postcode, huisnummer, toevoeging)

        # Fallback: als toevoeging opgegeven maar geen resultaten,
        # probeer zonder toevoeging (toevoeging kan onjuist zijn)
        if not docs and toevoeging:
            docs = self.zoek_adres(postcode, huisnummer, None)

        if not docs:
            return {
                "error": f"Adres niet gevonden: {postcode} {huisnummer}"
                + (f" {toevoeging}" if toevoeging else "")
            }

        # Filter op exact huisnummer (PDOK kan fuzzy matchen)
        postcode_clean = postcode.replace(" ", "").upper()
        exact = [
            d for d in docs
            if d.get("huisnummer") == huisnummer
            and d.get("postcode", "").replace(" ", "").upper() == postcode_clean
        ]

        # Filter op toevoeging als opgegeven
        if toevoeging and exact:
            toev_upper = toevoeging.upper()
            toev_matches = [
                d for d in exact
                if (d.get("huisnummertoevoeging") or "").upper() == toev_upper
                or (d.get("huisletter") or "").upper() == toev_upper
            ]
            if toev_matches:
                exact = toev_matches

        doc = exact[0] if exact else docs[0]
        num_id = doc.get("nummeraanduiding_id")

        if not num_id:
            return {"error": "Geen nummeraanduiding-ID gevonden voor dit adres"}

        # Stap 2: WOZ-waarden ophalen
        try:
            woz_data = self.wozwaarde_by_nummeraanduiding(num_id)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return {
                    "error": f"Geen WOZ-waarde gevonden voor {doc.get('weergavenaam', postcode)}"
                }
            raise

        return self._format_response(woz_data)

    def _format_response(self, woz_data: dict) -> dict:
        """Formateer WOZ API response naar gestandaardiseerd formaat."""
        woz_obj = woz_data.get("wozObject", {})
        waarden = woz_data.get("wozWaarden", [])

        adres = {
            "straat": woz_obj.get("straatnaam", ""),
            "huisnummer": woz_obj.get("huisnummer"),
            "postcode": woz_obj.get("postcode", ""),
            "woonplaats": woz_obj.get("woonplaatsnaam", ""),
            "grondoppervlakte": woz_obj.get("grondoppervlakte"),
        }

        # Voeg toevoeging/huisletter toe als aanwezig
        huisletter = woz_obj.get("huisletter")
        toevoeging = woz_obj.get("huisnummertoevoeging")
        if huisletter:
            adres["huisletter"] = huisletter
        if toevoeging:
            adres["toevoeging"] = toevoeging

        woz_waarden = [
            {
                "peildatum": w.get("peildatum"),
                "waarde": w.get("vastgesteldeWaarde"),
            }
            for w in waarden
        ]

        # Sorteer op peildatum (nieuwste eerst)
        woz_waarden.sort(key=lambda w: w["peildatum"] or "", reverse=True)

        return {
            "adres": adres,
            "woz_waarden": woz_waarden,
            "meest_recente_waarde": woz_waarden[0]["waarde"] if woz_waarden else None,
            "meest_recente_peildatum": woz_waarden[0]["peildatum"] if woz_waarden else None,
            "wozobjectnummer": woz_obj.get("wozobjectnummer"),
        }
