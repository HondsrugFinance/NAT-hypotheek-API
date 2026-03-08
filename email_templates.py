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

<p>Met vriendelijke groet,</p>

<table cellpadding="0" cellspacing="0" border="0" style="font-family: Arial, sans-serif; font-size: 14px; color: #333;">
<tr>
<td style="padding-right: 15px; vertical-align: top;">
<img src="https://raw.githubusercontent.com/HondsrugFinance/NAT-hypotheek-API/main/static/logo-hondsrug-finance.jpg" alt="Hondsrug Finance" width="80" height="80" style="display: block;" />
</td>
<td style="vertical-align: top;">
<p style="margin: 0 0 2px 0;"><strong>Alex Kuijper CFP\u00ae</strong></p>
<p style="margin: 0 0 8px 0; font-size: 12px; color: #666;">Hypotheken | Verzekeringen | Ondernemers</p>
<p style="margin: 0; font-size: 12px; line-height: 1.6;">
<strong>M:</strong> +31 6 1292 6573 | <strong>E:</strong> <a href="mailto:alex@hondsrugfinance.nl" style="color: #2E5644;">alex@hondsrugfinance.nl</a><br>
<strong>A:</strong> Marktstraat 21, Assen | <a href="http://www.hondsrugfinance.nl/" style="color: #2E5644;">www.hondsrugfinance.nl</a><br>
KVK 93276699
</p>
</td>
</tr>
</table>

<p style="font-size: 11px; color: #888;"><em>Dit bericht is automatisch gegenereerd.
De bijgevoegde samenvatting is een indicatieve berekening en vormt geen bindend aanbod.</em></p>"""
