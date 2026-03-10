"""Afsluiting sectie — disclaimer tekst."""


def build_closing_section() -> dict:
    """Bouw de afsluiting/disclaimer sectie."""
    return {
        "id": "closing",
        "title": "Afsluiting",
        "visible": True,
        "narratives": [
            "Dit Persoonlijk Hypotheekadvies en de bijbehorende berekeningen "
            "zijn uitsluitend bedoeld als advies. Dit advies is geen aanbod "
            "voor het aangaan van een overeenkomst, u kunt hieraan geen rechten "
            "ontlenen. De berekeningen zijn gebaseerd op de persoonlijke en "
            "financiële gegevens die u ons heeft gegeven.",
            "Dit hypotheekadvies is gebaseerd op de gegevens die wij van u "
            "hebben ontvangen en op de relevante (fiscale) wet- en regelgeving "
            "die nu geldt. Van een totaal fiscaal advies is geen sprake. "
            "Daarvoor verwijzen wij u naar een fiscaal adviseur. Hondsrug "
            "Finance aanvaardt geen aansprakelijkheid voor eventuele toekomstige "
            "wijzigingen in de fiscale wet- en regelgeving.",
        ],
    }
