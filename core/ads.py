"""Werbefläche (Sidebar unten links).

STATUS: Platzhalter. Es wird KEINE Werbung geladen und KEIN Netzwerkverkehr erzeugt, solange AD_UNIT_ID leer ist.

Wichtig (siehe Fazit): Google AdMob ist für Mobile-Apps (Android/iOS) gedacht. Für Desktop-Programme gibt es
kein offizielles AdMob/Google-Ads-SDK. Für Windows/Linux wären Alternativen nötig (z. B. ein Werbebanner in einer
eingebetteten Webansicht, ein anderes Netzwerk oder eigene Banner). Dieses Modul kapselt deshalb alles hinter
dem Interface `AdProvider`, damit später ein echter Anbieter eingesetzt werden kann.
Außerdem: Google-Werberichtlinien untersagen Werbung in Software, die Cheating unterstützt. Das Recoil-Modul
kann die Freigabe verhindern. Vor dem Aktivieren Richtlinien und Datenschutz (Einwilligung, Art. 6/7 DSGVO) prüfen.
"""
from dataclasses import dataclass

from core.version import AD_UNIT_ID


@dataclass
class AdContent:
    title: str = ""
    text: str = ""
    url: str = ""            # Ziel beim Klick (nur https)
    image_path: str = ""     # lokale Bilddatei des Banners (optional)


class AdProvider:
    """Schnittstelle für einen Werbeanbieter."""

    name = "none"

    def available(self) -> bool:
        return False

    def load(self) -> AdContent | None:
        """Wird NICHT im UI-Thread aufgerufen. Gibt Banner-Inhalt oder None zurück."""
        return None


class PlaceholderProvider(AdProvider):
    name = "placeholder"


class GoogleAdsProvider(AdProvider):
    """Hier später die Anbindung eintragen:
    1. AD_UNIT_ID in core/version.py setzen (Format AdMob: ca-app-pub-XXXXXXXXXXXXXXXX/YYYYYYYYYY).
    2. load() implementieren (Anfrage an den Anbieter, Banner herunterladen, AdContent zurückgeben).
    3. Erst NACH Einwilligung des Nutzers (consent) laden und die Datenschutztexte aktualisieren (LEGAL_VERSION erhöhen).
    """
    name = "google"

    def __init__(self, ad_unit_id: str):
        self.ad_unit_id = ad_unit_id

    def available(self) -> bool:
        return bool(self.ad_unit_id)

    def load(self) -> AdContent | None:
        return None      # TODO: noch nicht implementiert (bewusst, siehe Modul-Hinweis)


def provider() -> AdProvider:
    return GoogleAdsProvider(AD_UNIT_ID) if AD_UNIT_ID else PlaceholderProvider()
