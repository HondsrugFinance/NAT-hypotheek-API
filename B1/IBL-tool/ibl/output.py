"""Geformateerde output voor IBL-berekeningsresultaten."""

from decimal import Decimal
from .models import IBLResultaat


def _fmt(val: "Decimal | None") -> str:
    """Formatteer een Decimal als EUR bedrag."""
    if val is None:
        return "-"
    return f"EUR {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(val: "Decimal | None") -> str:
    """Formatteer een Decimal als percentage."""
    if val is None:
        return "-"
    return f"{val:.2f}%"


def formatteer_resultaat(resultaat: IBLResultaat, verbose: bool = False) -> str:
    """Genereer een leesbare samenvatting van het IBL-resultaat."""
    lines = []
    lines.append("=" * 60)
    lines.append("IBL Toetsinkomen Berekening")
    lines.append("=" * 60)
    lines.append(f"Aanvrager:       {resultaat.aanvrager_naam}")
    lines.append(f"Aanmaakdatum:    {resultaat.aanmaakdatum}")
    lines.append(f"Werkgever:       {resultaat.werkgever_naam}")
    lines.append(f"Berekening:      {resultaat.berekening_type.value}-berekening")
    lines.append("-" * 60)
    lines.append(f"TOETSINKOMEN:    {_fmt(resultaat.toetsinkomen)}")
    lines.append("=" * 60)

    if resultaat.waarschuwingen:
        lines.append("")
        lines.append("Waarschuwingen:")
        for w in resultaat.waarschuwingen:
            lines.append(f"  - {w}")

    if verbose:
        tr = resultaat.tussenresultaat
        lines.append("")
        lines.append("--- Tussenberekeningen ---")

        # Uren
        if tr.u3 is not None:
            lines.append(f"U3:              {tr.u3}")
            lines.append(f"Ujr:             {tr.ujr}")
            lines.append(f"Urenpercentage:  {_pct(tr.urenpercentage)}")

        if tr.parttimepercentage is not None:
            lines.append(f"PT%:             {_pct(tr.parttimepercentage)}")

        # Bestendigheid
        if tr.bestendigheid_criterium1_ratio is not None:
            lines.append("")
            lines.append("--- Bestendigheidstoets ---")
            lines.append(f"Criterium 1 ratio: {_pct(tr.bestendigheid_criterium1_ratio)}")
            lines.append(f"Criterium 1:       {'Geslaagd' if tr.bestendigheid_criterium1_geslaagd else 'Gefaald'}")
            if tr.bestendigheid_criterium2_geslaagd is not None:
                lines.append(f"Criterium 2:       {'Geslaagd' if tr.bestendigheid_criterium2_geslaagd else 'Gefaald'}")

        # Inkomensdelen
        lines.append("")
        lines.append("--- Inkomensdelen ---")
        if tr.i3 is not None:
            lines.append(f"I3:              {_fmt(tr.i3)}")
        if tr.i9 is not None:
            lines.append(f"I9:              {_fmt(tr.i9)}")
        if tr.i21 is not None:
            lines.append(f"I21:             {_fmt(tr.i21)}")
        if tr.i_jr is not None:
            lines.append(f"I (jaar):        {_fmt(tr.i_jr)}")
        if tr.i_2jr is not None:
            lines.append(f"I (2 jaar):      {_fmt(tr.i_2jr)}")

        # C-berekening specifiek
        if tr.i33 is not None:
            lines.append(f"I33:             {_fmt(tr.i33)}")
        if tr.i_3jr is not None:
            lines.append(f"I (3 jaar):      {_fmt(tr.i_3jr)}")

        # Auto
        if tr.z_jr is not None:
            lines.append("")
            lines.append("--- Auto van de zaak ---")
            lines.append(f"Z (jaar):        {_fmt(tr.z_jr)}")
        if tr.z_2jr is not None:
            lines.append(f"Z (2 jaar):      {_fmt(tr.z_2jr)}")
        if tr.z_3jr is not None:
            lines.append(f"Z (3 jaar):      {_fmt(tr.z_3jr)}")

        # Pieken
        if tr.gemiddeld_periode_inkomen is not None:
            lines.append("")
            lines.append("--- Piekanalyse ---")
            lines.append(f"GPI:             {_fmt(tr.gemiddeld_periode_inkomen)}")
        if tr.gemiddeld_jaarinkomen is not None:
            lines.append(f"GJI:             {_fmt(tr.gemiddeld_jaarinkomen)}")

        # Pensioen
        if tr.eigen_bijdrage_pensioen_jaar is not None:
            lines.append("")
            lines.append("--- Pensioen ---")
            lines.append(f"Per maand:       {_fmt(tr.eigen_bijdrage_pensioen_maand)}")
            lines.append(f"Per jaar:        {_fmt(tr.eigen_bijdrage_pensioen_jaar)}")

    return "\n".join(lines)
