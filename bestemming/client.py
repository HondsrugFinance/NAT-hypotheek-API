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

# Max aantal plannen waarvoor we vlakken ophalen (kostenloos, maar wel calls).
# Ruim genoeg: binnenstad-adressen stapelen veel facet-/parapluplannen bovenop
# het onderliggende buurtbestemmingsplan dat de echte 'Wonen'-bestemming bevat.
MAX_PLANNEN = 20

# Nette labels voor enkele meerledige/afwijkende hoofdgroepen; de rest krijgt
# gewoon een hoofdletter. Alles dat met "won" begint → "Wonen".
SIMPELE_LABELS = {
    "agrarisch met waarden": "Agrarisch",
    "cultuur en ontspanning": "Cultuur en ontspanning",
    "verkeer - verblijfsgebied": "Verkeer",
    "verkeer - railverkeer": "Verkeer",
    # Gemengde bestemmingen waar wonen is toegestaan → hint voor de adviseur.
    "centrum": "Centrum (incl. wonen)",
    "gemengd": "Gemengd (incl. wonen)",
}


def vereenvoudig_bestemming(hoofdgroep: Optional[str], naam: Optional[str]) -> Optional[str]:
    """Maak van een hoofdgroep/naam een korte, leesbare waarde (bv. 'Wonen')."""
    hg = (hoofdgroep or "").strip().lower()
    nm = (naam or "").strip()
    # "wonen" begint met "wonen"; "woongebied"/"woondoeleinden" met "woon".
    woon = lambda s: s.startswith("wonen") or s.startswith("woon")
    if woon(hg) or woon(nm.lower()):
        return "Wonen"
    if hg:
        return SIMPELE_LABELS.get(hg, hg[:1].upper() + hg[1:])
    if nm:
        # Geen hoofdgroep (oud plan): strip eventuele nummering ("- 1").
        return re.sub(r"\s*[-–]?\s*\d+\s*$", "", nm).strip() or nm
    return None


# Namen/typen die een overlay (dubbelbestemming) aanduiden i.p.v. de hoofdbestemming.
_OVERLAY_PREFIXES = ("waarde", "leiding", "dubbel", "vrijwaringszone", "veiligheidszone", "geluidzone")


def _is_overlay(b: dict) -> bool:
    """True voor dubbelbestemmingen/overlays (Waarde, Leiding, ...) — geen woonbestemming."""
    naam = (b.get("naam") or "").strip().lower()
    typ = (b.get("type") or "").strip().lower()
    return typ == "dubbelbestemming" or naam.startswith(_OVERLAY_PREFIXES)


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

    def _zoek_vlakken(self, plan_id: str, resource: str, x: float, y: float) -> list:
        """Zoek vlakken van een type (bestemmingsvlakken / besluitvlakken) op een punt."""
        body = {"_geo": {"intersectAndNotTouches": {"type": "Point", "coordinates": [x, y]}}}
        resp = httpx.post(
            f"{RP_BASE}/plannen/{plan_id}/{resource}/_zoek",
            json=body,
            headers=self._headers(),
            timeout=self._timeout,
        )
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        return self._json(resp).get("_embedded", {}).get(resource, [])

    # ------------------------------------------------------------------
    # Publiek: bestemming op adres
    # ------------------------------------------------------------------

    def bestemming_op_adres(self, postcode: str, huisnummer: int, toevoeging: Optional[str] = None) -> dict:
        x, y, adres = self.geocode_rd(postcode, huisnummer, toevoeging)
        if x is None:
            return {"gevonden": False, "error": "Adres niet gevonden", "adres": None,
                    "primair": None, "bestemmingen": [], "plannen": []}

        plannen = self._zoek_plannen(x, y)

        # Structuurvisies/omgevingsvisies hebben geen bestemmingsvlakken — eruit
        # filteren vóór de limiet, zodat het echte bestemmingsplan niet wegvalt.
        relevant = [p for p in plannen if (p.get("type") or "").lower() != "structuurvisie"]

        bestemmingen = []
        plan_info = []
        for plan in relevant[:MAX_PLANNEN]:
            plan_id = plan.get("id")
            plan_naam = plan.get("naam")
            plan_info.append({"id": plan_id, "naam": plan_naam, "type": plan.get("type")})
            if not plan_id:
                continue
            try:
                # Bestemmingsplannen hebben bestemmingsvlakken; een beheersverordening
                # (en sommige inpassingsplannen) hebben in plaats daarvan besluitvlakken.
                # Probeer eerst bestemmingsvlakken; bij niets → besluitvlakken, maar alleen
                # voor niet-bestemmingsplannen (die hebben nooit besluitvlakken).
                vlakken = self._zoek_vlakken(plan_id, "bestemmingsvlakken", x, y)
                if not vlakken and (plan.get("type") or "").lower() != "bestemmingsplan":
                    vlakken = self._zoek_vlakken(plan_id, "besluitvlakken", x, y)
            except Exception as e:
                logger.warning("vlakken ophalen mislukt voor %s: %s", plan_id, e)
                continue
            for bv in vlakken:
                bestemmingen.append({
                    "naam": bv.get("naam"),
                    "hoofdgroep": bv.get("bestemmingshoofdgroep"),
                    "type": bv.get("type"),
                    "plan_naam": plan_naam,
                })

        # Primaire bestemming = eerste enkelbestemming/besluitvlak dat geen overlay is
        # (Waarde-/Leiding-dubbelbestemmingen zijn geen woonbestemming);
        # vereenvoudigd tot een korte waarde (bv. "Wonen").
        niet_overlay = [b for b in bestemmingen if not _is_overlay(b)]
        bron = niet_overlay[0] if niet_overlay else (bestemmingen[0] if bestemmingen else None)
        primair = vereenvoudig_bestemming(bron.get("hoofdgroep"), bron.get("naam")) if bron else None

        return {
            "gevonden": bool(bestemmingen),
            "primair": primair,
            "bestemmingen": bestemmingen,
            "plannen": plan_info,
            "adres": adres,
        }
