"""E-mail body templates voor concept e-mails."""

LOGO_URL = "https://raw.githubusercontent.com/HondsrugFinance/NAT-hypotheek-API/main/static/logo-hondsrug-finance.jpg"

# Adviseur-gegevens per e-mailadres
ADVISORS = {
    "alex@hondsrugfinance.nl": {
        "naam": "Alex Kuijper CFP\u00ae",
        "mobiel": "+31 6 1292 6573",
    },
    "quido@hondsrugfinance.nl": {
        "naam": "Quido Kok",
        "mobiel": "+31 6 5438 4048",
    },
    "stephan@hondsrugfinance.nl": {
        "naam": "Stephan Bakker CFP\u00ae",
        "mobiel": "+31 6 4675 6226",
    },
}


def _signature_html(sender_email: str) -> str:
    """Genereer de HTML-handtekening op basis van het e-mailadres van de afzender."""
    advisor = ADVISORS.get(sender_email)

    if not advisor:
        # Fallback: generieke handtekening zonder persoonlijke gegevens
        return (
            '<p>Met vriendelijke groet,<br>'
            'Hondsrug Finance<br>'
            'Tel: +31 88 400 2700<br>'
            'E-mail: Info@hondsrugfinance.nl</p>'
        )

    naam = advisor["naam"]
    mobiel = advisor["mobiel"]
    email = sender_email

    return f"""\
<p>Met vriendelijke groet,</p>

<table cellpadding="0" cellspacing="0" border="0" style="border-collapse: collapse; font-family: Calibri, sans-serif;">
<tr>
<td style="width: 180px; border-right: 1px solid #7B818B; padding: 0 12px 0 0; vertical-align: top;">
<img src="{LOGO_URL}" alt="Hondsrug Finance" width="154" style="display: block;" />
</td>
<td style="padding: 0 0 0 16px; vertical-align: top;">
<p style="margin: 0 0 2px 0; font-size: 14pt; line-height: 1.2;"><b style="color: #558E76;">{naam}</b></p>
<p style="margin: 0 0 10px 0; font-size: 11pt; color: gray; line-height: 1.2;">Hypotheken | Verzekeringen | Ondernemers</p>
<p style="margin: 0; font-size: 11pt; color: gray; line-height: 1.6;">
<b style="color: #558E76;">M:</b> {mobiel}\u00a0|\u00a0<b style="color: #558E76;">E:</b> <a href="mailto:{email}" style="color: gray;">{email}</a><br>
<b style="color: #558E76;">A:</b> Marktstraat 21, Assen\u00a0|\u00a0<a href="http://www.hondsrugfinance.nl/" style="color: gray;">www.hondsrugfinance.nl</a><br>
<span style="color: gray;">KVK 93276699</span>
</p>
</td>
</tr>
</table>"""


def samenvatting_email_body(
    klant_naam: str,
    sender_email: str = "",
    has_partner: bool = False,
) -> str:
    """
    Genereer de HTML body voor een samenvatting e-mail.

    Args:
        klant_naam: Naam van de klant (aanvrager, of "Naam & Naam" bij stel)
        sender_email: E-mailadres van de afzender (voor persoonlijke handtekening)
        has_partner: True als er een partner is (jullie-vorm), False = je-vorm

    Returns:
        HTML string voor de e-mail body.
    """
    signature = _signature_html(sender_email)

    if has_partner:
        return f"""\
<p>Beste {klant_naam},</p>

<p>Zoals besproken stuur ik jullie hierbij de samenvatting van de hypotheekberekening.</p>

<p>In het document vinden jullie een overzicht van de maximale hypotheek, de mogelijke financieringsopzet en de bijbehorende maandlasten. Hiermee krijgen jullie een goed beeld van de financi\u00eble mogelijkheden in jullie situatie.</p>

<p>De berekening is gebaseerd op de huidige gegevens en hypotheeknormen en dient als eerste indicatie. De uiteindelijke mogelijkheden kunnen nog afhankelijk zijn van onder andere de definitieve toetsing van de gegevens en de actuele rentestand op het moment van aanvragen.</p>

<p>Wanneer jullie vragen hebben of bepaalde onderdelen willen bespreken, neem gerust contact met mij op.</p>

{signature}

<p style="font-size: 11px; color: #888;"><em>Dit bericht is automatisch gegenereerd.
De bijgevoegde samenvatting is een indicatieve berekening en vormt geen bindend aanbod.</em></p>"""
    else:
        return f"""\
<p>Beste {klant_naam},</p>

<p>Zoals besproken stuur ik je hierbij de samenvatting van de hypotheekberekening.</p>

<p>In het document vind je een overzicht van de maximale hypotheek, de mogelijke financieringsopzet en de bijbehorende maandlasten. Hiermee krijg je een goed beeld van de financi\u00eble mogelijkheden in jouw situatie.</p>

<p>De berekening is gebaseerd op de huidige gegevens en hypotheeknormen en dient als eerste indicatie. De uiteindelijke mogelijkheden kunnen nog afhankelijk zijn van onder andere de definitieve toetsing van de gegevens en de actuele rentestand op het moment van aanvragen.</p>

<p>Wanneer je vragen hebt of bepaalde onderdelen wilt bespreken, neem gerust contact met mij op.</p>

{signature}

<p style="font-size: 11px; color: #888;"><em>Dit bericht is automatisch gegenereerd.
De bijgevoegde samenvatting is een indicatieve berekening en vormt geen bindend aanbod.</em></p>"""
