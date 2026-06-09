"""
Bestemming opvragen via de Ruimtelijke Plannen API v4 (Informatiehuis Ruimte / DSO).
=====================================================================================
Flow:
  1. Adres → RD-coördinaat (PDOK locatieserver, gratis, geen key).
  2. POST plannen/_zoek (regelStatus=geldend) → geldende plannen op dat punt.
  3. POST plannen/{id}/bestemmingsvlakken/_zoek → bestemmingsvlakken op dat punt.
  4. Verzamel bestemmingen (enkelbestemming = primair, dubbelbestemming = overlay).

Headers: x-api-key + Content-Crs/Accept-Crs = epsg:28992 (RD New).
Env var: RUIMTELIJKE_PLANNEN_API_KEY
"""

import os
import re
import json
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

RP_BASE = "https://ruimte.omgevingswet.overheid.nl/ruimtelijke-plannen/api/opvragen/v4"
PDOK_FREE = "https://api.pdok.nl/bzk/locatieserver/search/v3_1/free"
ENV_KEY = "RUIMTELIJKE_PLANNEN_API_KEY"

# Max aantal plannen waarvoor we bestemmingsvlakken ophalen (kostenloos, maar wel calls).
MAX_PLANNEN = 8


class BestemmingClient:
    """Client voor de Ruimtelijke Plannen API (bestemming op adres)."""

    def __init__(self, api_key: Optional[str] = None, timeout: float = 20.0):
        self._api_key = api_key or os.environ.get(ENV_KEY, "")
        self._timeout = timeout

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    def _headers(self) -> dict:
        return {
            "x-api-key": self._api_key,
            "Content-Type": "application/json",
            "Content-Crs": "epsg:28992",
            "Accept-Crs": "epsg:28992",
        }

    @staticmethod
    def _json(resp: httpx.Response) -> dict:
        # Forceer UTF-8 (vermijdt mojibake bij accenten in plan-/bestemmingsnamen).
        return json.loads(resp.content.decode("utf-8-sig"))

    # ------------------------------------------------------------------
    # Stap 1: adres → RD-coördinaat via PDOK
    # ------------------------------------------------------------------

    def geocode_rd(self, postcode: str, huisnummer: int, toevoeging: Optional[str] = None):
        """Retourneert (x, y, adres) in RD (EPSG:28992) of (None, None, None)."""
        q = f"{postcode} {huisnummer}"
        if toevoeging:
            q += f" {toevoeging}"
        try:
            resp = httpx.get(
                PDOK_FREE,
                params={"fq": "type:adres", "q": q, "rows": 1},
                headers={"Accept": "application/json"},
                timeout=self._timeout,
            )
            resp.raise_for_status()
            docs = self._json(resp).get("response", {}).get("docs", [])
        except Exception as e:
            logger.warning("PDOK geocode mislukt: %s", e)
            return None, None, None

        if not docs:
            return None, None, None

        doc = docs[0]
        m = re.search(r"POINT\(([-\d.]+)\s+([-\d.]+)\)", doc.get("centroide_rd", ""))
        if not m:
            return None, None, None

        adres = {
            "straat": doc.get("straatnaam"),
            "huisnummer": doc.get("huisnummer"),
            "postcode": doc.get("postcode"),
            "plaats": doc.get("woonplaatsnaam"),
            "weergavenaam": doc.get("weergavenaam"),
        }
        return float(m.group(1)), float(m.group(2)), adres

    # ------------------------------------------------------------------
    # Stap 2 + 3: plannen en bestemmingsvlakken op punt
    # ------------------------------------------------------------------

    def _zoek_plannen(self, x: float, y: float) -> list:
        body = {"_geo": {"intersectAndNotTouches": {"type": "Point", "coordinates": [x, y]}}}
        resp = httpx.post(
            f"{RP_BASE}/plannen/_zoek",
            params={"pageSize": 20, "regelStatus": "geldend"},
            json=body,
            headers=self._headers(),
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return self._json(resp).get("_embedded", {}).get("plannen", [])

    def _zoek_bestemmingsvlakken(self, plan_id: str, x: float, y: float) -> list:
        body = {"_geo": {"intersectAndNotTouches": {"type": "Point", "coordinates": [x, y]}}}
        resp = httpx.post(
            f"{RP_BASE}/plannen/{plan_id}/bestemmingsvlakken/_zoek",
            json=body,
            headers=self._headers(),
            timeout=self._timeout,
        )
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        return self._json(resp).get("_embedded", {}).get("bestemmingsvlakken", [])

    # ------------------------------------------------------------------
    # Publiek: bestemming op adres
    # ------------------------------------------------------------------

    def bestemming_op_adres(self, postcode: str, huisnummer: int, toevoeging: Optional[str] = None) -> dict:
        x, y, adres = self.geocode_rd(postcode, huisnummer, toevoeging)
        if x is None:
            return {"gevonden": False, "error": "Adres niet gevonden", "adres": None,
                    "primair": None, "bestemmingen": [], "plannen": []}

        plannen = self._zoek_plannen(x, y)

        bestemmingen = []
        plan_info = []
        for plan in plannen[:MAX_PLANNEN]:
            plan_id = plan.get("id")
            plan_naam = plan.get("naam")
            plan_info.append({"id": plan_id, "naam": plan_naam, "type": plan.get("type")})
            if not plan_id:
                continue
            try:
                vlakken = self._zoek_bestemmingsvlakken(plan_id, x, y)
            except Exception as e:
                logger.warning("bestemmingsvlakken mislukt voor %s: %s", plan_id, e)
                continue
            for bv in vlakken:
                bestemmingen.append({
                    "naam": bv.get("naam"),
                    "hoofdgroep": bv.get("bestemmingshoofdgroep"),
                    "type": bv.get("type"),
                    "plan_naam": plan_naam,
                })

        # Primaire bestemming = eerste enkelbestemming, anders eerste gevonden.
        enkel = [b for b in bestemmingen if (b.get("type") or "").lower() == "enkelbestemming"]
        primair = (enkel[0]["naam"] if enkel else (bestemmingen[0]["naam"] if bestemmingen else None))

        return {
            "gevonden": bool(bestemmingen),
            "primair": primair,
            "bestemmingen": bestemmingen,
            "plannen": plan_info,
            "adres": adres,
        }
