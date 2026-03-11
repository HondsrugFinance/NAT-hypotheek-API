"""Align dual-column rows so bold totals line up across columns."""


def align_columns_at_totaal(columns: list[dict]) -> list[dict]:
    """Voeg spacer-rijen toe zodat bold-rijen op dezelfde hoogte staan.

    Splitst de rows per kolom in chunks (gescheiden door lege divider-rijen).
    Per chunk wordt de kortere kolom aangevuld met onzichtbare spacer-rijen
    zodat de bold-rij (totaal) op dezelfde hoogte uitkomt.

    Args:
        columns: Lijst van column dicts met minimaal {"rows": [...]}.

    Returns:
        Dezelfde columns met eventueel extra spacer-rijen ingevoegd.
    """
    if len(columns) < 2:
        return columns

    # Split elke kolom in chunks gescheiden door lege divider-rijen
    all_chunks = [_split_at_dividers(col["rows"]) for col in columns]

    # Zorg dat alle kolommen evenveel chunks hebben
    max_chunks = max(len(c) for c in all_chunks)
    for chunks in all_chunks:
        while len(chunks) < max_chunks:
            chunks.append([])

    # Per chunk: pad tot gelijke lengte, spacers vóór bold (totaal) of aan het eind
    aligned = [[] for _ in columns]
    for chunk_idx in range(max_chunks):
        chunk_rows = [all_chunks[ci][chunk_idx] for ci in range(len(columns))]
        max_size = max(len(cr) for cr in chunk_rows)

        for ci, cr in enumerate(chunk_rows):
            gap = max_size - len(cr)
            if gap > 0:
                # Zoek eerste bold-rij in het chunk
                bold_pos = next(
                    (i for i, row in enumerate(cr) if row.get("bold")),
                    None,
                )

                spacers = [{"label": "\u00a0", "value": "", "spacer": True}] * gap

                if bold_pos is not None and bold_pos > 0:
                    # Bold = totaalrij onderaan → spacers vóór de bold-rij
                    cr = cr[:bold_pos] + spacers + cr[bold_pos:]
                else:
                    # Bold = header bovenaan of geen bold → spacers aan het eind
                    cr = cr + spacers

            aligned[ci].extend(cr)
            # Divider terugplaatsen tussen chunks (behalve na laatste)
            if chunk_idx < max_chunks - 1:
                aligned[ci].append({"label": "", "value": ""})

    for ci in range(len(columns)):
        columns[ci]["rows"] = aligned[ci]

    return columns


def _split_at_dividers(rows: list[dict]) -> list[list[dict]]:
    """Splits rows in chunks bij lege divider-rijen (label='' en value='')."""
    chunks = []
    current: list[dict] = []
    for row in rows:
        if (
            not row.get("label")
            and not row.get("value")
            and not row.get("spacer")
            and not row.get("bold")
        ):
            # Lege divider-rij → chunk-grens
            chunks.append(current)
            current = []
        else:
            current.append(row)
    if current:
        chunks.append(current)
    return chunks
