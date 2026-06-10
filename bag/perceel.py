"""
Perceeloppervlakte opvragen via de PDOK Kadastrale Kaart (BRK) WFS v5_0.
=======================================================================
GRATIS, geen API-key. Dit is dezelfde open dataset die we als WMS-overlay
(perceelgrenzen + perceelnummers) op de luchtfoto tekenen — maar de WFS geeft
ook de attributen, waaronder `kadastraleGrootteWaarde` (de officiële
kadastrale oppervlakte in m²).

Belangrijk: alleen de geometrie + oppervlakte is open. Eigenaar, hypotheken
en beslagen zitten achter KIK-Inzage (betaald) — die halen we hier NIET op.

We zoeken het perceel waar het BAG-adrespunt fysiek in valt (Intersects op een
punt). Dat is het "huisperceel". Een eigendom dat uit méér kadastrale eenheden
bestaat (bv. een losse tuinkavel ernaast) kan niet betrouwbaar uit open data
worden opgeteld — dat vereist de eigendomsinformatie (KIK-Inzage). We tonen
daarom bewust alleen het perceel waarop de woning staat.

Let op (uit empirische test op de service):
  - De geometrie-kolom heet `geom` (niet `begrenzingPerceel`).
  - `CQL_FILTER` wordt door deze service STIL GENEGEERD → gebruik de
    OGC XML `filter=<fes:Intersects>`, die exact 1 perceel teruggeeft.
"""

import json
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

WFS_BASE = "https://service.pdok.nl/kadaster/kadastralekaart/wfs/v5_0"
TYPE_NAME = "kadastralekaartv5:Perceel"
BRON = "PDOK Kadastrale Kaart (BRK), © Kadaster"


def _intersects_filter(rd_x: float, rd_y: float) -> str:
    """OGC FES 2.0 Intersects-filter: percelen die het RD-punt bevatten."""
    return (
        '<fes:Filter xmlns:fes="http://www.opengis.net/fes/2.0" '
        'xmlns:gml="http://www.opengis.net/gml/3.2">'
        "<fes:Intersects>"
        "<fes:ValueReference>geom</fes:ValueReference>"
        '<gml:Point srsName="urn:ogc:def:crs:EPSG::28992">'
        f"<gml:pos>{rd_x} {rd_y}</gml:pos>"
        "</gml:Point>"
        "</fes:Intersects>"
        "</fes:Filter>"
    )


def oppervlakte_op_punt(rd_x: float, rd_y: float, timeout: float = 15.0) -> Optional[dict]:
    """
    Zoek het kadastrale perceel waarin het RD-punt (epsg:28992) valt.

    Retourneert (of None bij geen treffer / fout):
      - oppervlakte_m2: int        — kadastrale grootte in m²
      - aanduiding: str            — bv. "Hilversum C 7017"
      - gemeente / sectie / perceelnummer
      - soort_grootte: str         — "Vastgesteld" (ingemeten) of "Voorlopig"
    """
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": TYPE_NAME,
        "outputFormat": "application/json",
        "srsName": "EPSG:28992",
        "count": "1",
        "filter": _intersects_filter(rd_x, rd_y),
    }
    try:
        resp = httpx.get(WFS_BASE, params=params, timeout=timeout)
        resp.raise_for_status()
        data = json.loads(resp.content.decode("utf-8-sig"))
    except httpx.HTTPError as e:
        logger.warning("Perceel-WFS ophalen mislukt: %s", e)
        return None
    except (ValueError, KeyError) as e:
        logger.warning("Perceel-WFS antwoord onleesbaar: %s", e)
        return None

    features = data.get("features") or []
    if not features:
        return None

    props = features[0].get("properties", {}) or {}
    grootte = props.get("kadastraleGrootteWaarde")
    if grootte is None:
        return None

    gemeente = props.get("kadastraleGemeenteWaarde")
    sectie = props.get("sectie")
    nummer = props.get("perceelnummer")
    aanduiding = " ".join(str(p) for p in (gemeente, sectie, nummer) if p)

    return {
        "oppervlakte_m2": int(round(float(grootte))),
        "aanduiding": aanduiding or None,
        "gemeente": gemeente,
        "sectie": sectie,
        "perceelnummer": nummer,
        "soort_grootte": props.get("soortGrootteWaarde"),
    }
