"""
PDOK Luchtfoto (Beeldmateriaal Nederland) — WMS GetMap op RD-coördinaten.
=========================================================================
Gratis, geen API-key. We bouwen een GetMap-URL rond een RD-punt (epsg:28992)
en kunnen de PNG ook server-side proxyen (voor insluiten in PDF/adviesrapport).

We gebruiken WMS 1.1.1: bij EPSG:28992 is de as-volgorde dan altijd
minx,miny,maxx,maxy (x=oost, y=noord), wat de as-ambiguïteit van 1.3.0 omzeilt.

Layers (luchtfotorgb):
  - Actueel_orthoHR  : hoogste resolutie (~8 cm), standaard
  - Actueel_ortho25  : 25 cm
"""

from urllib.parse import urlencode
from typing import Optional

WMS_BASE = "https://service.pdok.nl/hwh/luchtfotorgb/wms/v1_0"
DEFAULT_LAYER = "Actueel_orthoHR"
BRON = "PDOK Luchtfoto (Beeldmateriaal Nederland), © Kadaster / Beeldmateriaal.nl"

# Kadastrale kaart (BRK) — perceelgrenzen + perceelnummers, als transparante overlay.
KADASTER_WMS = "https://service.pdok.nl/kadaster/kadastralekaart/wms/v5_0"
KADASTER_LAYERS = "KadastraleGrens,Label"

# Begrenzingen om misbruik/onzin te voorkomen.
MIN_GROOTTE_M = 20      # kleinste uitsnede (meter, breedte van de bbox)
MAX_GROOTTE_M = 1000    # grootste uitsnede
MIN_PIXELS = 64
MAX_PIXELS = 2048


def bbox_rond_punt(rd_x: float, rd_y: float, grootte_m: float) -> tuple:
    """Vierkante bbox (minx, miny, maxx, maxy) van `grootte_m` meter rond een punt."""
    half = grootte_m / 2.0
    return (rd_x - half, rd_y - half, rd_x + half, rd_y + half)


def _getmap_url(
    base: str,
    layers: str,
    rd_x: float,
    rd_y: float,
    grootte_m: float,
    breedte: int,
    hoogte: int,
    fmt: str = "image/png",
    transparent: bool = False,
) -> str:
    """Bouw een WMS 1.1.1 GetMap-URL (EPSG:28992) voor een vierkante uitsnede rond een punt."""
    grootte_m = max(MIN_GROOTTE_M, min(MAX_GROOTTE_M, grootte_m))
    breedte = max(MIN_PIXELS, min(MAX_PIXELS, breedte))
    hoogte = max(MIN_PIXELS, min(MAX_PIXELS, hoogte))

    minx, miny, maxx, maxy = bbox_rond_punt(rd_x, rd_y, grootte_m)
    params = {
        "SERVICE": "WMS",
        "VERSION": "1.1.1",
        "REQUEST": "GetMap",
        "LAYERS": layers,
        "STYLES": "",
        "SRS": "EPSG:28992",
        "BBOX": f"{minx:.3f},{miny:.3f},{maxx:.3f},{maxy:.3f}",
        "WIDTH": breedte,
        "HEIGHT": hoogte,
        "FORMAT": fmt,
    }
    if transparent:
        params["TRANSPARENT"] = "true"
    return f"{base}?{urlencode(params)}"


def wms_url(
    rd_x: float,
    rd_y: float,
    grootte_m: float = 80,
    breedte: int = 600,
    hoogte: int = 600,
    layer: str = DEFAULT_LAYER,
    fmt: str = "image/png",
) -> str:
    """Bouw een GetMap-URL voor een vierkante luchtfoto-uitsnede rond een RD-punt."""
    return _getmap_url(WMS_BASE, layer, rd_x, rd_y, grootte_m, breedte, hoogte, fmt)


def kadaster_wms_url(
    rd_x: float,
    rd_y: float,
    grootte_m: float = 80,
    breedte: int = 600,
    hoogte: int = 600,
) -> str:
    """Bouw een transparante GetMap-URL met perceelgrenzen + perceelnummers (zelfde bbox)."""
    return _getmap_url(
        KADASTER_WMS, KADASTER_LAYERS, rd_x, rd_y, grootte_m, breedte, hoogte,
        fmt="image/png", transparent=True,
    )


def clamp_grootte(grootte_m: Optional[float]) -> float:
    g = grootte_m if grootte_m else 80
    return max(MIN_GROOTTE_M, min(MAX_GROOTTE_M, g))


def clamp_pixels(px: Optional[int], default: int = 600) -> int:
    p = px if px else default
    return max(MIN_PIXELS, min(MAX_PIXELS, p))
