"""Makro aus Beschreibung erzeugen: erst offline (schnell, kostenlos), sonst KI. KI-Ausgabe wird IMMER geprüft."""
from core.i18n import tr

from . import dsl


class GenerateError(Exception):
    pass


def generate(description: str, ask=None) -> tuple[str, str]:
    """ask(messages) -> str (KI-Antwort) oder None, wenn keine KI verfügbar ist.
    Gibt (skript, quelle) zurück; quelle = 'offline' | 'ai'. Wirft GenerateError mit anzeigbarem Text."""
    description = (description or "").strip()
    if len(description) < 3:
        raise GenerateError(tr("Please describe what the macro should do."))
    if len(description) > 1000:
        raise GenerateError(tr("The description is too long (max. 1000 characters)."))
    off = dsl.generate_offline(description)
    if off:
        return off[0], "offline"
    if ask is None:
        raise GenerateError(tr("I did not understand that. Try e.g. 'click every 50 ms at 500 300', or sign in to a "
                               "cloud account to use the AI."))
    messages = [{"role": "user", "content": description}]
    last_err = ""
    for attempt in range(2):
        try:
            reply = ask(messages)
        except Exception as exc:
            raise GenerateError(str(exc)) from None
        script = dsl.extract_script(reply)
        try:
            dsl.parse(script)
            return script, "ai"
        except dsl.MacroError as exc:
            last_err = str(exc)
            messages = messages + [{"role": "assistant", "content": reply},
                                   {"role": "user", "content": f"Invalid: {exc.message}. Return only the corrected script."}]
    raise GenerateError(tr("The AI did not produce a valid macro ({err}). Please rephrase.", err=last_err))
