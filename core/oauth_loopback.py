"""Fängt die Rückkehr einer Browser-Anmeldung (OAuth) auf http://127.0.0.1:<port>/callback ab."""
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

open_browser = webbrowser.open     # in Tests austauschbar

_DONE_HTML = ("<html><head><meta charset='utf-8'><title>JOPML</title></head>"
              "<body style='font-family:sans-serif;text-align:center;margin-top:15vh'>"
              "<h2>&#10003;</h2><p>You can close this window and return to the app.<br>"
              "Du kannst dieses Fenster schlie&szlig;en.</p></body></html>").encode("utf-8")


class LoopbackError(Exception):
    pass


def capture_redirect(build_url, port: int = 0, timeout: float = 180, cancel: threading.Event | None = None) -> dict:
    """Startet einen nur lokal erreichbaren Mini-Server, ruft build_url(redirect_uri) -> url auf, öffnet den
    Browser und wartet auf ?code=... oder ?error=.... Gibt die Query-Parameter als dict zurück."""
    result: dict = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if "code" in q or "error" in q:
                result.update({k: v[0] for k, v in q.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(_DONE_HTML)))
            self.end_headers()
            self.wfile.write(_DONE_HTML)

        def log_message(self, *args):
            pass

    try:
        server = HTTPServer(("127.0.0.1", port), Handler)    # nur lokal erreichbar
    except OSError:
        raise LoopbackError(f"Port {port} is already in use. Close other programs or try again.") from None
    server.timeout = 0.5
    redirect = f"http://127.0.0.1:{server.server_port}/callback"
    try:
        open_browser(build_url(redirect))
        deadline = time.time() + timeout
        while not result and time.time() < deadline:
            if cancel is not None and cancel.is_set():
                raise LoopbackError("Cancelled.")
            server.handle_request()
    finally:
        server.server_close()
    if not result:
        raise LoopbackError("Timed out: no answer from the browser.")
    result["redirect_uri"] = redirect
    return result
