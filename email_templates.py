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

<p>Zoals besproken stuur ik je hierbij de samenvatting van de hypotheekberekening.</p>

<p>In het document vind je een overzicht van de maximale hypotheek, de mogelijke financieringsopzet en de bijbehorende maandlasten. Hiermee krijg je een goed beeld van de financi\u00eble mogelijkheden in jouw situatie.</p>

<p>De berekening is gebaseerd op de huidige gegevens en hypotheeknormen en dient als eerste indicatie. De uiteindelijke mogelijkheden kunnen nog afhankelijk zijn van onder andere de definitieve toetsing van de gegevens en de actuele rentestand op het moment van aanvragen.</p>

<p>Wanneer je vragen hebt of bepaalde onderdelen wilt bespreken, neem gerust contact met mij op.</p>

<p>Met vriendelijke groet,<br>
{advisor_naam}<br>
Tel: +31 88 400 2700<br>
E-mail: Info@hondsrugfinance.nl</p>

<p style="font-size: 11px; color: #888;"><em>Dit bericht is automatisch gegenereerd.
De bijgevoegde samenvatting is een indicatieve berekening en vormt geen bindend aanbod.</em></p>"""
