"""Klantprofiel sectie — doelstelling, kennis/ervaring, risicobereidheid."""

from adviesrapport_v2.schemas import AdviesrapportOptions


# Labels voor risicobereidheid tabel
RISICO_LABELS = {
    "pensioen": "Pensioen",
    "overlijden": "Overlijden",
    "arbeidsongeschiktheid": "Arbeidsongeschiktheid",
    "werkloosheid": "Werkloosheid",
    "relatiebeeindiging": "Relatiebeëindiging",
    "waardedaling_woning": "Waardedaling woning",
    "rentestijging": "Rentestijging",
    "aflopen_hypotheekrenteaftrek": "Aflopen hypotheekrenteaftrek",
}

# Welke risico-items tonen per situatie
RISICO_KEYS_ALLEENSTAAND = [
    "pensioen", "overlijden", "arbeidsongeschiktheid", "werkloosheid",
    "waardedaling_woning", "rentestijging", "aflopen_hypotheekrenteaftrek",
]
RISICO_KEYS_STEL = [
    "pensioen", "overlijden", "arbeidsongeschiktheid", "werkloosheid",
    "relatiebeeindiging", "waardedaling_woning", "rentestijging",
    "aflopen_hypotheekrenteaftrek",
]


def build_client_profile_section(
    options: AdviesrapportOptions,
    alleenstaand: bool,
    alle_personen_aow: bool = False,
) -> dict:
    """Bouw de klantprofiel sectie."""
    # Rows: doel, ervaring, kennis
    rows = [
        {"label": "Doel van de hypotheek", "value": options.doel_hypotheek},
        {"label": "Ervaring met een hypotheek", "value": options.ervaring_hypotheek},
        {"label": "Kennis van hypotheekvormen", "value": options.kennis_hypotheekvormen},
        {"label": "Kennis van fiscale regels", "value": options.kennis_fiscale_regels},
    ]

    # Risicobereidheid tabel
    risico_keys = list(RISICO_KEYS_ALLEENSTAAND if alleenstaand else RISICO_KEYS_STEL)

    # Bij AOW-gerechtigden: pensioen, AO en WW niet tonen (niet meer van toepassing)
    if alle_personen_aow:
        risico_keys = [k for k in risico_keys if k not in ("pensioen", "arbeidsongeschiktheid", "werkloosheid")]
    risico_rows = []
    for key in risico_keys:
        label = RISICO_LABELS.get(key, key.replace("_", " ").title())
        waarde = options.risicobereidheid.get(key, "Risico aanvaarden")
        risico_rows.append([label, waarde])

    return {
        "id": "client-profile",
        "title": "Klantprofiel",
        "visible": True,
        "narratives": [],
        "rows": rows,
        "tables": [{
            "headers": ["Financiële risico's", "Risicobereidheid"],
            "rows": risico_rows,
        }],
    }
