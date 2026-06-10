"""
BAG-objectdata opvragen via de BAG API Individuele Bevragingen v2 (Kadaster).
============================================================================
Eén call op postcode + huisnummer (adressenuitgebreid) levert o.a. bouwjaar,
gebruiksoppervlakte en gebruiksdoel.

Headers: X-Api-Key + Accept-Crs = epsg:28992 (response bevat geometrie).
Env var: BAG_API_KEY (gratis aan te vragen bij het Kadaster).
Gratis, maar niet bedoeld voor bulk.
"""

import os
import json
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

BAG_BASE = "https://api.bag.kadaster.nl/lvbag/individuelebevragingen/v2"
ENV_KEY = "BAG_API_KEY"

# De 11 BAG-gebruiksdoelen → leesbare labels (zonder "functie").
GEBRUIKSDOEL_LABELS = {
    "woonfunctie": "Wonen",
    "kantoorfunctie": "Kantoor",
    "winkelfunctie": "Winkel",
    "industriefunctie": "Industrie",
    "logiesfunctie": "Logies",
    "bijeenkomstfunctie": "Bijeenkomst",
    "onderwijsfunctie": "Onderwijs",
    "sportfunctie": "Sport",
    "gezondheidszorgfunctie": "Gezondheidszorg",
    "celfunctie": "Detentie",
    "overige gebruiksfunctie": "Overig",
}


def gebruiksdoel_label(doel: str) -> str:
    """Maak een leesbaar label van een BAG-gebruiksdoel (zonder 'functie')."""
    d = doel.strip().lower()
    if d in GEBRUIKSDOEL_LABELS:
        return GEBRUIKSDOEL_LABELS[d]
    schoon = d.replace("functie", "").strip()
    return (schoon or d)[:1].upper() + (schoon or d)[1:]


def _rd_punt(adres: dict) -> Optional[tuple]:
    """Haal de RD-coördinaat (x, y in epsg:28992) uit een BAG-adres.

    De adressenuitgebreid-respons bevat `adresseerbaarObjectGeometrie` met een
    `punt` (Point) en/of `vlak` (Polygon). We pakken het punt; valt dat weg,
    dan het zwaartepunt van de eerste ring van het vlak.
    """
    geo = adres.get("adresseerbaarObjectGeometrie") or {}

    punt = geo.get("punt") or {}
    coords = punt.get("coordinates")
    if isinstance(coords, (list, tuple)) and len(coords) >= 2:
        try:
            return float(coords[0]), float(coords[1])
        except (TypeError, ValueError):
            pass

    vlak = geo.get("vlak") or {}
    ring = (vlak.get("coordinates") or [None])[0]
    if isinstance(ring, list) and ring:
        xs = [p[0] for p in ring if isinstance(p, (list, tuple)) and len(p) >= 2]
        ys = [p[1] for p in ring if isinstance(p, (list, tuple)) and len(p) >= 2]
        if xs and ys:
            return sum(xs) / len(xs), sum(ys) / len(ys)

    return None


class BAGClient:
    """Client voor de BAG API (objectdata op adres)."""

    def __init__(self, api_key: Optional[str] = None, timeout: float = 15.0):
        self._api_key = api_key or os.environ.get(ENV_KEY, "")
        self._timeout = timeout

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    def _headers(self) -> dict:
        return {
            "X-Api-Key": self._api_key,
            "Accept": "application/hal+json",
            "Accept-Crs": "epsg:28992",
        }

    @staticmethod
    def _json(resp: httpx.Response) -> dict:
        return json.loads(resp.content.decode("utf-8-sig"))

    def adres_uitgebreid(self, postcode: str, huisnummer: int, toevoeging: Optional[str] = None) -> dict:
        """
        Haal objectdata op voor een adres.

        Retourneert:
          - gevonden: bool
          - bouwjaar: str | None
          - oppervlakte: int | None (m²)
          - gebruiksdoel: str | None (bv. "Woonfunctie")
          - objecttype: str | None (Verblijfsobject/Ligplaats/Standplaats)
          - status: str | None
          - error: str (bij fout)
        """
        params = {"postcode": postcode, "huisnummer": huisnummer}
        if not toevoeging:
            params["exacteMatch"] = "true"

        try:
            resp = httpx.get(
                f"{BAG_BASE}/adressenuitgebreid",
                params=params,
                headers=self._headers(),
                timeout=self._timeout,
            )
        except httpx.TimeoutException:
            return {"gevonden": False, "error": "BAG API timeout"}
        except httpx.ConnectError:
            return {"gevonden": False, "error": "Kan geen verbinding maken met BAG API"}

        if resp.status_code == 401:
            return {"gevonden": False, "error": "BAG API key ongeldig of ontbreekt"}
        if resp.status_code == 404:
            return {"gevonden": False, "error": "Adres niet gevonden in BAG"}
        resp.raise_for_status()

        embedded = self._json(resp).get("_embedded", {})
        adressen = embedded.get("adressen") or next(
            (v for v in embedded.values() if isinstance(v, list)), []
        )
        if not adressen:
            return {"gevonden": False, "error": "Adres niet gevonden in BAG"}

        # Bij een toevoeging het beste matchende adres kiezen, anders het eerste.
        adres = adressen[0]
        if toevoeging:
            t = toevoeging.strip().lower()
            for a in adressen:
                combi = f"{a.get('huisletter', '') or ''}{a.get('huisnummertoevoeging', '') or ''}".lower()
                if combi == t:
                    adres = a
                    break

        # Bouwjaar: oorspronkelijkBouwjaar is een lijst (meestal 1 pand).
        bouwjaren = [str(b) for b in (adres.get("oorspronkelijkBouwjaar") or []) if b]
        bouwjaar = " / ".join(dict.fromkeys(bouwjaren)) or None

        # Gebruiksdoel(en) → leesbare labels (zonder "functie"), gededupliceerd.
        labels = [gebruiksdoel_label(str(d)) for d in (adres.get("gebruiksdoelen") or []) if d]
        gebruiksdoel = ", ".join(dict.fromkeys(labels)) or None

        punt = _rd_punt(adres)

        return {
            "gevonden": True,
            "bouwjaar": bouwjaar,
            "oppervlakte": adres.get("oppervlakte"),
            "gebruiksdoel": gebruiksdoel,
            "objecttype": adres.get("typeAdresseerbaarObject"),
            "status": adres.get("adresseerbaarObjectStatus"),
            "pand_ids": [str(p) for p in (adres.get("pandIdentificaties") or []) if p],
            "rd_x": round(punt[0], 3) if punt else None,
            "rd_y": round(punt[1], 3) if punt else None,
        }

    def is_gestapeld(self, pand_ids: list) -> bool:
        """
        True als het pand meerdere woon-verblijfsobjecten bevat (gestapeld =
        appartement/flat). Bij zo'n pand delen de woningen één grondperceel, dus
        de perceeloppervlakte zou misleidend zijn → bovenliggend tonen we 'n.v.t.'.

        Best-effort: telt de woon-VBO's in het eerste pand via één extra
        BAG-call. Faalt die call, dan gaan we ervan uit dat het géén appartement
        is (we tonen liever de oppervlakte dan onterecht niets).

        Kanttekening: een 2-onder-1-kap of rij die in BAG als één pand is
        gemodelleerd telt ook als 'gestapeld' (vals-positief, veilige kant).
        """
        if not pand_ids:
            return False

        params = {"pandIdentificatie": pand_ids[0], "pageSize": 50}
        try:
            resp = httpx.get(
                f"{BAG_BASE}/adressenuitgebreid",
                params=params,
                headers=self._headers(),
                timeout=self._timeout,
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.warning("Pand-telling (gestapeld) mislukt: %s", e)
            return False

        embedded = self._json(resp).get("_embedded", {})
        adressen = embedded.get("adressen") or next(
            (v for v in embedded.values() if isinstance(v, list)), []
        )
        woon = [
            a for a in adressen
            if any("woon" in str(d).lower() for d in (a.get("gebruiksdoelen") or []))
        ]
        return len(woon) > 1
