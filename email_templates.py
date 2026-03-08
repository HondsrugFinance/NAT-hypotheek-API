"""E-mail body templates voor concept e-mails."""


def samenvatting_email_body(
    klant_naam: str,
    advisor_naam: str = "Hondsrug Finance",
) -> str:
    """
    Genereer de HTML body voor een samenvatting e-mail.

    Args:
        klant_naam: Naam van de klant (aanvrager)
        advisor_naam: Naam van de adviseur / bedrijf

    Returns:
        HTML string voor de e-mail body.
    """
    return f"""\
<p>Beste {klant_naam},</p>

<p>Hierbij ontvangt u de samenvatting van uw hypotheekberekening als bijlage bij dit bericht.</p>

<p>Heeft u vragen naar aanleiding van deze samenvatting? Neem dan gerust contact met ons op.</p>

<p>Met vriendelijke groet,<br>
{advisor_naam}<br>
Tel: +31 88 400 2700<br>
E-mail: Info@hondsrugfinance.nl</p>

<p style="font-size: 11px; color: #888;"><em>Dit bericht is automatisch gegenereerd.
De bijgevoegde samenvatting is een indicatieve berekening en vormt geen bindend aanbod.</em></p>"""
