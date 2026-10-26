"""KI-Zugriff des Launchers (Hilfe-Assistent und Makro-Generator).

Der Gemini-Schlüssel liegt NIE im Programm, sondern nur als Secret der Supabase-Edge-Function `jopml-ai`.
Der Launcher spricht ausschließlich mit dieser Funktion (angemeldetes Cloud-Konto nötig).
Der Google OAuth Client ID (GOOGLE_CLIENT_ID) ist KEIN Gemini-Schlüssel und kann nicht für die Gemini-API genutzt werden.
"""
from core.cloud import CloudError
from core.i18n import get_language


class AiUnavailable(Exception):
    """Text darf dem Nutzer angezeigt werden."""


def available(app) -> bool:
    ident = getattr(app, "identity", None)
    client = getattr(ident, "client", None)
    return bool(client and client.configured and getattr(client, "session", None))


def ask(app, kind: str, messages: list[dict]) -> str:
    """kind: 'help' | 'macro'. Blockierend; im Thread aufrufen."""
    if not available(app):
        raise AiUnavailable("The AI needs a cloud account (sign in with a JOPMakro account or Google while the "
                            "server is set up).")
    try:
        return app.identity.client.ai(kind, messages, get_language())
    except CloudError as exc:
        raise AiUnavailable(str(exc)) from None
