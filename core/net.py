"""Netzwerk-Hilfe: HTTPS mit eigenem Zertifikatspaket.

Ein per PyInstaller gebautes Python auf macOS findet oft keine Zertifikate des Systems
("CERTIFICATE_VERIFY_FAILED"). Dann scheitern Update-Prüfung, Google-Login und KI. Deshalb wird, wenn vorhanden,
das Paket `certifi` benutzt. Die Zertifikatsprüfung wird dabei NIE abgeschaltet.
"""
import ssl
import urllib.request

_CTX = None


def ssl_context() -> ssl.SSLContext:
    global _CTX
    if _CTX is None:
        try:
            import certifi
            _CTX = ssl.create_default_context(cafile=certifi.where())
        except Exception:
            _CTX = ssl.create_default_context()
    return _CTX


def urlopen(req, timeout: float = 20):
    return urllib.request.urlopen(req, timeout=timeout, context=ssl_context())
