"""
SVG Chart Generator voor risico-analyse in adviesrapport.

Genereert inline SVG grafieken die direct in Jinja2 HTML templates
embedded worden. Geen JavaScript, geen externe bestanden — compatibel
met WeasyPrint.

Grafiek-types:
- Pensioen: verticale staven (max hypotheek per jaar) + lijn (restschuld)
- Overlijden / AO / WW: horizontale staven (max hypotheek per scenario)
"""


# --- Hondsrug Finance kleurenpalet ---
COLOR_GREEN = "#2E5644"
COLOR_RED = "#C0392B"
COLOR_LABEL = "#5C4A6E"
COLOR_VALUE = "#2B1E39"
COLOR_GRID = "#E5DFC8"
COLOR_BG = "#FEFDF8"
COLOR_LINE = "#2B1E39"


def _escape(text: str) -> str:
    """Escape XML-speciale tekens."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _format_bedrag(value: float) -> str:
    """Format bedrag als '€ 280.000' (Nederlands)."""
    return f"\u20ac {value:,.0f}".replace(",", ".")


def _format_bedrag_kort(value: float) -> str:
    """Format bedrag kort: '€ 280k'."""
    if value >= 1_000_000:
        return f"\u20ac {value / 1_000_000:.1f}M"
    return f"\u20ac {value / 1_000:.0f}k"


# ═══════════════════════════════════════════════════════════════════════
# Pensioen-grafiek: verticale staven + restschuld-lijn over 30 jaar
# ═══════════════════════════════════════════════════════════════════════

def genereer_pensioen_chart_svg(
    jaren: list[dict],
    geadviseerd_hypotheekbedrag: float,
    aow_markers: list[dict] | None = None,
    width: int = 480,
    height: int = 230,
    margin_left: int = 50,
    margin_right: int = 10,
    margin_top: int = 25,
    margin_bottom: int = 30,
) -> str:
    """
    Genereer een pensioen-grafiek als inline SVG.

    Verticale staven per jaar met max hypotheek (trapfunctie), plus een
    lijn voor de resterende hypotheekschuld. Verticale stippellijnen
    markeren AOW-momenten.

    Args:
        jaren: List van dicts met:
            - 'jaar': int (kalenderjaar)
            - 'max_hypotheek': float
            - 'restschuld': float
        geadviseerd_hypotheekbedrag: Referentiewaarde (stippellijn)
        aow_markers: Optioneel, lijst van dicts met:
            - 'jaar': int (kalenderjaar van AOW-moment)
            - 'label': str (bijv. "AOW aanvr." of "AOW partner")
        width, height: SVG afmetingen

    Returns:
        SVG string klaar voor inline embedding.
    """
    if not jaren:
        return ""

    n = len(jaren)
    chart_w = width - margin_left - margin_right
    chart_h = height - margin_top - margin_bottom

    # Y-as max: rond omhoog naar dichtstbijzijnde 50k
    all_values = [j.get("max_hypotheek", 0) for j in jaren]
    all_values += [j.get("restschuld", 0) for j in jaren]
    max_val = max(v for v in all_values if v > 0) if any(v > 0 for v in all_values) else 100_000
    y_max = ((int(max_val) // 50_000) + 1) * 50_000
    if y_max == 0:
        y_max = 100_000

    y_scale = chart_h / y_max
    bar_width = max(4, (chart_w / n) - 2)
    bar_step = chart_w / n

    svg = []
    svg.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" '
        f'style="font-family: Inter, Helvetica, Arial, sans-serif;">'
    )

    # Achtergrond
    svg.append(f'<rect width="{width}" height="{height}" fill="{COLOR_BG}" rx="4"/>')

    # Y-as grid-lijnen en labels
    y_step = 100_000 if y_max > 300_000 else 50_000
    y_val = y_step
    while y_val < y_max:
        y_pos = margin_top + chart_h - (y_val * y_scale)
        svg.append(
            f'<line x1="{margin_left}" y1="{y_pos:.1f}" '
            f'x2="{width - margin_right}" y2="{y_pos:.1f}" '
            f'stroke="{COLOR_GRID}" stroke-width="0.5"/>'
        )
        svg.append(
            f'<text x="{margin_left - 4}" y="{y_pos + 3:.1f}" '
            f'font-size="6.5" fill="{COLOR_LABEL}" text-anchor="end">'
            f'{_format_bedrag_kort(y_val)}</text>'
        )
        y_val += y_step

    # Staven (max hypotheek per jaar + tekort)
    for i, j in enumerate(jaren):
        x = margin_left + i * bar_step + (bar_step - bar_width) / 2
        max_hyp = j.get("max_hypotheek", 0)
        restschuld = j.get("restschuld", 0)

        # Groene balk: max haalbare hypotheek
        bar_h = max(1, max_hyp * y_scale)
        y = margin_top + chart_h - bar_h
        svg.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" '
            f'width="{bar_width:.1f}" height="{bar_h:.1f}" '
            f'fill="{COLOR_GREEN}" rx="1" opacity="0.7"/>'
        )

        # Rode balk: tekort (gestapeld boven groene balk)
        if max_hyp < restschuld:
            tekort_h = (restschuld - max_hyp) * y_scale
            tekort_y = y - tekort_h
            svg.append(
                f'<rect x="{x:.1f}" y="{tekort_y:.1f}" '
                f'width="{bar_width:.1f}" height="{tekort_h:.1f}" '
                f'fill="{COLOR_RED}" rx="1" opacity="0.7"/>'
            )

        # X-as labels (elk 5e jaar)
        if i % 5 == 0 or i == n - 1:
            label_x = margin_left + i * bar_step + bar_step / 2
            svg.append(
                f'<text x="{label_x:.1f}" y="{margin_top + chart_h + 12}" '
                f'font-size="6.5" fill="{COLOR_LABEL}" text-anchor="middle">'
                f'{j.get("jaar", "")}</text>'
            )

    # Restschuld-lijn (de werkelijke hypotheek over tijd)
    points = []
    for i, j in enumerate(jaren):
        x = margin_left + i * bar_step + bar_step / 2
        restschuld = j.get("restschuld", 0)
        y = margin_top + chart_h - (restschuld * y_scale)
        points.append(f"{x:.1f},{y:.1f}")

    if points:
        svg.append(
            f'<polyline points="{" ".join(points)}" '
            f'fill="none" stroke="{COLOR_LINE}" stroke-width="1.5"/>'
        )

    # AOW-markeringslijnen (verticale stippellijnen)
    if aow_markers and jaren:
        jaar_start = jaren[0].get("jaar", 0)
        for mi, marker in enumerate(aow_markers):
            m_jaar = marker.get("jaar", 0)
            m_label = _escape(marker.get("label", "AOW"))
            # Bereken x-positie op basis van jaarindex
            idx = m_jaar - jaar_start
            if 0 <= idx < n:
                m_x = margin_left + idx * bar_step + bar_step / 2
                svg.append(
                    f'<line x1="{m_x:.1f}" y1="{margin_top}" '
                    f'x2="{m_x:.1f}" y2="{margin_top + chart_h:.1f}" '
                    f'stroke="{COLOR_LABEL}" stroke-width="0.8" '
                    f'stroke-dasharray="3,2"/>'
                )
                # Label boven de grafiek, licht verschoven bij meerdere markers
                label_y = margin_top - 3 + mi * 8
                svg.append(
                    f'<text x="{m_x:.1f}" y="{label_y:.1f}" '
                    f'font-size="5.5" fill="{COLOR_LABEL}" text-anchor="middle">'
                    f'{m_label}</text>'
                )

    # Legenda
    legend_y = margin_top + chart_h + 22
    svg.append(
        f'<rect x="{margin_left}" y="{legend_y}" width="8" height="8" '
        f'fill="{COLOR_GREEN}" rx="1" opacity="0.7"/>'
    )
    svg.append(
        f'<text x="{margin_left + 11}" y="{legend_y + 7}" '
        f'font-size="6" fill="{COLOR_LABEL}">Max. hypotheek</text>'
    )
    svg.append(
        f'<rect x="{margin_left + 80}" y="{legend_y}" width="8" height="8" '
        f'fill="{COLOR_RED}" rx="1" opacity="0.7"/>'
    )
    svg.append(
        f'<text x="{margin_left + 91}" y="{legend_y + 7}" '
        f'font-size="6" fill="{COLOR_LABEL}">Tekort</text>'
    )
    svg.append(
        f'<line x1="{margin_left + 130}" y1="{legend_y + 4}" '
        f'x2="{margin_left + 142}" y2="{legend_y + 4}" '
        f'stroke="{COLOR_LINE}" stroke-width="1.5"/>'
    )
    svg.append(
        f'<text x="{margin_left + 145}" y="{legend_y + 7}" '
        f'font-size="6" fill="{COLOR_LABEL}">Hypotheek</text>'
    )

    svg.append("</svg>")
    return "\n".join(svg)


# ═══════════════════════════════════════════════════════════════════════
# Overlijden vergelijking: 2 verticale staven (huidig vs na overlijden)
# ═══════════════════════════════════════════════════════════════════════

def genereer_overlijden_vergelijk_svg(
    huidig_max_hypotheek: float,
    max_hypotheek_na_overlijden: float,
    geadviseerd_hypotheekbedrag: float,
    width: int = 310,
    height: int = 165,
    margin_left: int = 46,
    margin_right: int = 8,
    margin_top: int = 10,
    margin_bottom: int = 28,
    label_bar1: str = "Huidig",
    label_bar2: str = "Na overlijden",
) -> str:
    """
    Vergelijkingsgrafiek: 2 verticale balken (huidig vs scenario).

    Groene balk = max hypotheek. Rode balk gestapeld als tekort t.o.v.
    geadviseerd. Vaste lijn = geadviseerd hypotheekbedrag.

    Args:
        huidig_max_hypotheek: Max hypotheek huidige situatie
        max_hypotheek_na_overlijden: Max hypotheek na scenario
        geadviseerd_hypotheekbedrag: Referentiebedrag (lijn)
        label_bar1: Label onder eerste balk (default "Huidig")
        label_bar2: Label onder tweede balk (default "Na overlijden")

    Returns:
        SVG string klaar voor inline embedding.
    """
    chart_w = width - margin_left - margin_right
    chart_h = height - margin_top - margin_bottom

    # Y-as max: rond omhoog naar dichtstbijzijnde 50k
    all_values = [huidig_max_hypotheek, max_hypotheek_na_overlijden,
                  geadviseerd_hypotheekbedrag]
    max_val = max(v for v in all_values if v > 0) if any(v > 0 for v in all_values) else 100_000
    y_max = ((int(max_val) // 50_000) + 1) * 50_000
    if y_max == 0:
        y_max = 100_000

    y_scale = chart_h / y_max
    bar_width = chart_w * 0.28
    bar1_x = margin_left + chart_w * 0.14
    bar2_x = margin_left + chart_w * 0.58

    svg = []
    svg.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" '
        f'style="font-family: Inter, Helvetica, Arial, sans-serif;">'
    )
    svg.append(f'<rect width="{width}" height="{height}" fill="{COLOR_BG}" rx="4"/>')

    # Y-as grid-lijnen en labels
    y_step = 100_000 if y_max > 300_000 else 50_000
    y_val = y_step
    while y_val < y_max:
        y_pos = margin_top + chart_h - (y_val * y_scale)
        svg.append(
            f'<line x1="{margin_left}" y1="{y_pos:.1f}" '
            f'x2="{width - margin_right}" y2="{y_pos:.1f}" '
            f'stroke="{COLOR_GRID}" stroke-width="0.5"/>'
        )
        svg.append(
            f'<text x="{margin_left - 4}" y="{y_pos + 3:.1f}" '
            f'font-size="6.5" fill="{COLOR_LABEL}" text-anchor="end">'
            f'{_format_bedrag_kort(y_val)}</text>'
        )
        y_val += y_step

    # Balk 1: Huidig
    bar1_h = max(1, huidig_max_hypotheek * y_scale)
    bar1_y = margin_top + chart_h - bar1_h
    svg.append(
        f'<rect x="{bar1_x:.1f}" y="{bar1_y:.1f}" '
        f'width="{bar_width:.1f}" height="{bar1_h:.1f}" '
        f'fill="{COLOR_GREEN}" rx="2" opacity="0.8"/>'
    )

    # Balk 2: Na overlijden (groen + evt rood tekort)
    bar2_h = max(1, max_hypotheek_na_overlijden * y_scale)
    bar2_y = margin_top + chart_h - bar2_h
    svg.append(
        f'<rect x="{bar2_x:.1f}" y="{bar2_y:.1f}" '
        f'width="{bar_width:.1f}" height="{bar2_h:.1f}" '
        f'fill="{COLOR_GREEN}" rx="2" opacity="0.8"/>'
    )

    # Rode tekort-balk als max na overlijden < geadviseerd
    if max_hypotheek_na_overlijden < geadviseerd_hypotheekbedrag:
        tekort = geadviseerd_hypotheekbedrag - max_hypotheek_na_overlijden
        tekort_h = tekort * y_scale
        tekort_y = bar2_y - tekort_h
        svg.append(
            f'<rect x="{bar2_x:.1f}" y="{tekort_y:.1f}" '
            f'width="{bar_width:.1f}" height="{tekort_h:.1f}" '
            f'fill="{COLOR_RED}" rx="2" opacity="0.7"/>'
        )

    # Hypotheek referentielijn (horizontaal, vast)
    ref_y = margin_top + chart_h - (geadviseerd_hypotheekbedrag * y_scale)
    svg.append(
        f'<line x1="{margin_left}" y1="{ref_y:.1f}" '
        f'x2="{width - margin_right}" y2="{ref_y:.1f}" '
        f'stroke="{COLOR_LINE}" stroke-width="1.5"/>'
    )

    # X-as labels
    svg.append(
        f'<text x="{bar1_x + bar_width / 2:.1f}" y="{margin_top + chart_h + 14}" '
        f'font-size="7.5" fill="{COLOR_LABEL}" text-anchor="middle">{_escape(label_bar1)}</text>'
    )
    svg.append(
        f'<text x="{bar2_x + bar_width / 2:.1f}" y="{margin_top + chart_h + 14}" '
        f'font-size="7.5" fill="{COLOR_LABEL}" text-anchor="middle">{_escape(label_bar2)}</text>'
    )

    # Legenda
    legend_y = margin_top + chart_h + 22
    svg.append(
        f'<line x1="{margin_left}" y1="{legend_y + 3}" '
        f'x2="{margin_left + 14}" y2="{legend_y + 3}" '
        f'stroke="{COLOR_LINE}" stroke-width="1.5"/>'
    )
    svg.append(
        f'<text x="{margin_left + 17}" y="{legend_y + 6}" '
        f'font-size="6" fill="{COLOR_LABEL}">Hypotheek</text>'
    )

    svg.append("</svg>")
    return "\n".join(svg)


# ═══════════════════════════════════════════════════════════════════════
# Vergelijking N fasen: verticale staven (bijv. AO-fasen)
# ═══════════════════════════════════════════════════════════════════════

def genereer_vergelijk_chart_svg(
    fasen: list[dict],
    geadviseerd_hypotheekbedrag: float,
    width: int = 310,
    height: int = 170,
    margin_left: int = 46,
    margin_right: int = 8,
    margin_top: int = 10,
    margin_bottom: int = 32,
) -> str:
    """
    Vergelijkingsgrafiek: N verticale balken (bijv. AO-fasen).

    Groene balk = max hypotheek. Rode balk gestapeld als tekort t.o.v.
    geadviseerd. Vaste lijn = geadviseerd hypotheekbedrag.

    Args:
        fasen: List van dicts met 'label' en 'max_hypotheek'.
        geadviseerd_hypotheekbedrag: Referentiebedrag (lijn).

    Returns:
        SVG string klaar voor inline embedding.
    """
    if not fasen:
        return ""

    n = len(fasen)
    chart_w = width - margin_left - margin_right
    chart_h = height - margin_top - margin_bottom

    # Y-as max: rond omhoog naar dichtstbijzijnde 50k
    all_values = [f.get("max_hypotheek", 0) for f in fasen]
    all_values.append(geadviseerd_hypotheekbedrag)
    max_val = max(v for v in all_values if v > 0) if any(v > 0 for v in all_values) else 100_000
    y_max = ((int(max_val) // 50_000) + 1) * 50_000
    if y_max == 0:
        y_max = 100_000

    y_scale = chart_h / y_max
    slot_w = chart_w / n
    bar_width = slot_w * 0.65

    svg = []
    svg.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" '
        f'style="font-family: Inter, Helvetica, Arial, sans-serif;">'
    )
    svg.append(f'<rect width="{width}" height="{height}" fill="{COLOR_BG}" rx="4"/>')

    # Y-as grid-lijnen en labels
    y_step = 100_000 if y_max > 300_000 else 50_000
    y_val = y_step
    while y_val < y_max:
        y_pos = margin_top + chart_h - (y_val * y_scale)
        svg.append(
            f'<line x1="{margin_left}" y1="{y_pos:.1f}" '
            f'x2="{width - margin_right}" y2="{y_pos:.1f}" '
            f'stroke="{COLOR_GRID}" stroke-width="0.5"/>'
        )
        svg.append(
            f'<text x="{margin_left - 4}" y="{y_pos + 3:.1f}" '
            f'font-size="6.5" fill="{COLOR_LABEL}" text-anchor="end">'
            f'{_format_bedrag_kort(y_val)}</text>'
        )
        y_val += y_step

    # Balken
    for i, fase in enumerate(fasen):
        max_hyp = fase.get("max_hypotheek", 0)
        label = fase.get("label", "")
        bar_x = margin_left + i * slot_w + (slot_w - bar_width) / 2

        # Groene balk
        bar_h = max(1, max_hyp * y_scale)
        bar_y = margin_top + chart_h - bar_h
        svg.append(
            f'<rect x="{bar_x:.1f}" y="{bar_y:.1f}" '
            f'width="{bar_width:.1f}" height="{bar_h:.1f}" '
            f'fill="{COLOR_GREEN}" rx="2" opacity="0.8"/>'
        )

        # Rode tekort-balk
        if max_hyp < geadviseerd_hypotheekbedrag:
            tekort = geadviseerd_hypotheekbedrag - max_hyp
            tekort_h = tekort * y_scale
            tekort_y = bar_y - tekort_h
            svg.append(
                f'<rect x="{bar_x:.1f}" y="{tekort_y:.1f}" '
                f'width="{bar_width:.1f}" height="{tekort_h:.1f}" '
                f'fill="{COLOR_RED}" rx="2" opacity="0.7"/>'
            )

        # X-as label
        label_x = margin_left + i * slot_w + slot_w / 2
        svg.append(
            f'<text x="{label_x:.1f}" y="{margin_top + chart_h + 12}" '
            f'font-size="6.5" fill="{COLOR_LABEL}" text-anchor="middle">'
            f'{_escape(label)}</text>'
        )

    # Hypotheek referentielijn (horizontaal, vast)
    ref_y = margin_top + chart_h - (geadviseerd_hypotheekbedrag * y_scale)
    svg.append(
        f'<line x1="{margin_left}" y1="{ref_y:.1f}" '
        f'x2="{width - margin_right}" y2="{ref_y:.1f}" '
        f'stroke="{COLOR_LINE}" stroke-width="1.5"/>'
    )

    # Legenda
    legend_y = margin_top + chart_h + 22
    svg.append(
        f'<line x1="{margin_left}" y1="{legend_y + 3}" '
        f'x2="{margin_left + 14}" y2="{legend_y + 3}" '
        f'stroke="{COLOR_LINE}" stroke-width="1.5"/>'
    )
    svg.append(
        f'<text x="{margin_left + 17}" y="{legend_y + 6}" '
        f'font-size="6" fill="{COLOR_LABEL}">Hypotheek</text>'
    )

    svg.append("</svg>")
    return "\n".join(svg)


# ═══════════════════════════════════════════════════════════════════════
# Horizontale staafgrafiek (WW)
# ═══════════════════════════════════════════════════════════════════════

def genereer_risico_chart_svg(
    scenarios: list[dict],
    geadviseerd_hypotheekbedrag: float,
    width: int = 480,
    bar_height: int = 20,
    bar_gap: int = 7,
    label_width: int = 175,
) -> str:
    """
    Genereer een horizontale staafgrafiek als inline SVG string.

    Args:
        scenarios: List van dicts met 'naam', 'max_hypotheek', 'tekort'.
        geadviseerd_hypotheekbedrag: Referentiewaarde (stippellijn).

    Returns:
        SVG string klaar voor inline embedding.
    """
    if not scenarios:
        return ""

    n = len(scenarios)
    chart_area = width - label_width
    total_height = n * (bar_height + bar_gap) + 30

    # X-as max: rond omhoog naar dichtstbijzijnde 50k
    all_values = [s.get("max_hypotheek", 0) for s in scenarios]
    all_values.append(geadviseerd_hypotheekbedrag)
    max_val = max(v for v in all_values if v > 0) if any(v > 0 for v in all_values) else 100_000
    axis_max = ((int(max_val) // 50_000) + 1) * 50_000

    scale = chart_area / axis_max

    svg = []
    svg.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{total_height}" '
        f'viewBox="0 0 {width} {total_height}" '
        f'style="font-family: Inter, Helvetica, Arial, sans-serif;">'
    )

    # Achtergrond
    svg.append(f'<rect width="{width}" height="{total_height}" fill="{COLOR_BG}" rx="4"/>')

    # Grid-lijnen (elke 100k)
    step = 100_000
    x = step
    while x < axis_max:
        gx = label_width + x * scale
        svg.append(
            f'<line x1="{gx:.1f}" y1="0" x2="{gx:.1f}" '
            f'y2="{n * (bar_height + bar_gap)}" '
            f'stroke="{COLOR_GRID}" stroke-width="0.5"/>'
        )
        x += step

    # Balken
    for i, scenario in enumerate(scenarios):
        y = i * (bar_height + bar_gap) + 4
        max_hyp = scenario.get("max_hypotheek", 0)
        tekort = scenario.get("tekort", 0)
        naam = scenario.get("naam", "")
        bar_color = COLOR_RED if tekort > 0 else COLOR_GREEN

        bar_w = max(3, max_hyp * scale)

        # Label (links)
        svg.append(
            f'<text x="4" y="{y + bar_height * 0.72}" '
            f'font-size="7.5" fill="{COLOR_LABEL}">'
            f'{_escape(naam)}</text>'
        )

        # Balk
        svg.append(
            f'<rect x="{label_width}" y="{y}" '
            f'width="{bar_w:.1f}" height="{bar_height}" '
            f'fill="{bar_color}" rx="2" opacity="0.85"/>'
        )

        # Bedrag (rechts van balk)
        svg.append(
            f'<text x="{label_width + bar_w + 5}" y="{y + bar_height * 0.72}" '
            f'font-size="7" fill="{COLOR_VALUE}">'
            f'{_format_bedrag(max_hyp)}</text>'
        )

    # Referentielijn (geadviseerd bedrag)
    ref_x = label_width + geadviseerd_hypotheekbedrag * scale
    bar_area_bottom = n * (bar_height + bar_gap)
    svg.append(
        f'<line x1="{ref_x:.1f}" y1="0" x2="{ref_x:.1f}" y2="{bar_area_bottom}" '
        f'stroke="{COLOR_GREEN}" stroke-width="1.5" stroke-dasharray="4,3"/>'
    )

    # Referentie-label
    svg.append(
        f'<text x="{ref_x:.1f}" y="{bar_area_bottom + 13}" '
        f'font-size="7" fill="{COLOR_GREEN}" text-anchor="middle" font-weight="700">'
        f'Geadviseerd: {_format_bedrag(geadviseerd_hypotheekbedrag)}</text>'
    )

    svg.append("</svg>")
    return "\n".join(svg)
