"""
EP-Online Energielabel Client
==============================
Haalt energielabels op via de publieke EP-Online API (RVO).

API: https://public.ep-online.nl/api/v5/PandEnergielabel/Adres
Docs: https://public.ep-online.nl/swagger/index.html
API key aanvragen: https://apikey.ep-online.nl (gratis, KvK nodig)

Env var: EP_ONLINE_API_KEY
"""

import os
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

EP_ONLINE_BASE = "https://public.ep-online.nl/api/v5"

# Mapping van EP-Online labelklasse naar config/energielabel.json waarden
LABEL_MAPPING = {
    "A++++": "A++++",
    "A+++":  "A+++",
    "A++":   "A+,A++",
    "A+":    "A+,A++",
    "A":     "A,B",
    "B":     "A,B",
    "C":     "C,D",
    "D":     "C,D",
    "E":     "E,F,G",
    "F":     "E,F,G",
    "G":     "E,F,G",
}


class EPOnlineClient:
    """Client voor de EP-Online energielabel API (RVO)."""

    def __init__(self, api_key: Optional[str] = None, timeout: float = 15.0):
        self._api_key = api_key or os.environ.get("EP_ONLINE_API_KEY", "")
        self._timeout = timeout

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    def opvragen(
        self,
        postcode: str,
        huisnummer: int,
        huisletter: Optional[str] = None,
        toevoeging: Optional[str] = None,
    ) -> dict:
        """
        Haal energielabel op voor een adres.

        Retourneert dict met:
          - labelklasse: str (bijv. "A", "B", "C")
          - labelklasse_config: str (mapping naar energielabel.json, bijv. "A,B")
          - registratiedatum: str
          - geldig_tot: str | None
          - opnamedatum: str | None
          - gebouwtype: str | None
          - bouwjaar: int | None
          - energie_index: float | None
          - adres: {straat, huisnummer, postcode, plaats}
          - error: str (bij fout)
        """
        postcode_clean = postcode.replace(" ", "").upper()

        params = {
            "postcode": postcode_clean,
            "huisnummer": str(huisnummer),
        }
        if huisletter:
            params["huisletter"] = huisletter
        if toevoeging:
            params["huisnummertoevoeging"] = toevoeging

        try:
            resp = httpx.get(
                f"{EP_ONLINE_BASE}/PandEnergielabel/Adres",
                params=params,
                headers={"Authorization": self._api_key},
                timeout=self._timeout,
            )
        except httpx.TimeoutException:
            return {"error": "EP-Online timeout — probeer het later opnieuw"}
        except httpx.ConnectError:
            return {"error": "Kan geen verbinding maken met EP-Online"}

        if resp.status_code == 401:
            return {"error": "EP-Online API key ongeldig of verlopen"}
        if resp.status_code == 404:
            return {"error": f"Geen energielabel gevonden voor {postcode_clean} {huisnummer}"}
        if resp.status_code == 400:
            return {"error": f"Ongeldig adresformaat: {postcode_clean} {huisnummer}"}

        resp.raise_for_status()
        labels = resp.json()

        if not labels:
            return {"error": f"Geen energielabel gevonden voor {postcode_clean} {huisnummer}"}

        # Pak het meest recente label (sorteer op registratiedatum)
        if isinstance(labels, list):
            labels.sort(
                key=lambda l: l.get("registratiedatum", "") or "",
                reverse=True,
            )
            label = labels[0]
        else:
            label = labels

        return self._format_response(label)

    def _format_response(self, label: dict) -> dict:
        """Formateer EP-Online response naar gestandaardiseerd formaat."""
        labelklasse = label.get("labelLetter") or label.get("energieklasse") or ""
        labelklasse = labelklasse.strip()

        # Mapping naar onze config-waarden
        labelklasse_config = LABEL_MAPPING.get(labelklasse, "Geen (geldig) Label")

        result = {
            "labelklasse": labelklasse,
            "labelklasse_config": labelklasse_config,
            "registratiedatum": label.get("registratiedatum"),
            "geldig_tot": label.get("geldigTot"),
            "opnamedatum": label.get("opnamedatum"),
            "gebouwtype": label.get("gebouwtype"),
            "bouwjaar": label.get("bouwjaar"),
            "adres": {
                "straat": label.get("straatnaam", ""),
                "huisnummer": label.get("huisnummer"),
                "huisletter": label.get("huisletter"),
                "toevoeging": label.get("huisnummertoevoeging"),
                "postcode": label.get("postcode", ""),
                "plaats": label.get("plaatsnaam", ""),
            },
        }

        # Optionele velden
        energie_index = label.get("energieIndex")
        if energie_index is not None:
            try:
                result["energie_index"] = float(energie_index)
            except (ValueError, TypeError):
                pass

        energieprestatie = label.get("energieprestatie")
        if energieprestatie is not None:
            result["energieprestatie"] = energieprestatie

        return result
