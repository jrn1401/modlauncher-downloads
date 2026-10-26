"""Tests ohne Fenster und ohne Netzwerk (Attrappen für customtkinter/pynput unter tests/stubs).
Ausführen:  python tests/test_all.py        (Exit-Code 0 = alles in Ordnung)"""
import hashlib
import http.server
import json
import os
import sys
import tempfile
import threading
import time
import traceback
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = tempfile.mkdtemp(prefix="jopml-test-")
os.environ["XDG_CONFIG_HOME"] = TMP
os.environ["HOME"] = TMP
sys.path.insert(0, str(ROOT))
try:
    import customtkinter  # noqa: F401
    import pynput  # noqa: F401
except ImportError:
    sys.path.insert(0, str(ROOT / "tests" / "stubs"))

from core import accounts, i18n  # noqa: E402

RESULTS = []


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


def raises(exc, fn, *a, **k):
    try:
        fn(*a, **k)
    except exc as e:
        return e
    raise AssertionError(f"{exc.__name__} erwartet")


# ---------------------------------------------------------------- Konten
def test_accounts():
    d = Path(tempfile.mkdtemp(dir=TMP))
    st = accounts.AccountStore(d)
    u = st.register("Jaron", "", "", "geheim123")           # E-Mail leer = anonym
    check(u["username"] == "jaron" and u["email"] == "" and u["display_name"] == "jaron", "register anonym")
    raises(accounts.AccountError, st.register, "jaron", "", "", "geheim123")
    raises(accounts.AccountError, st.register, "ab", "", "", "geheim123")
    raises(accounts.AccountError, st.register, "okname", "", "keine-mail", "geheim123")
    raises(accounts.AccountError, st.register, "okname", "", "", "kurz")
    st.register("zwei", "Zwei", "a@b.de", "geheim123")
    raises(accounts.AccountError, st.register, "drei", "", "a@b.de", "geheim123")   # E-Mail doppelt
    st.register("vier", "", "", "geheim123")
    st.register("fuenf", "", "", "geheim123")                                        # mehrere ohne E-Mail ok
    check(st.authenticate("jaron", "geheim123")["username"] == "jaron", "login")
    raises(accounts.AccountError, st.authenticate, "jaron", "falsch")
    check(not hasattr(st, "change_password"), "Passwort darf nicht änderbar sein")
    for _ in range(5):
        raises(accounts.AccountError, st.authenticate, "jaron", "falsch")
    e = raises(accounts.AccountError, st.authenticate, "jaron", "geheim123")
    check("seconds" in str(e) or "Sekunden" in str(e), "Sperre nach Fehlversuchen")


def test_totp_and_sessions():
    d = Path(tempfile.mkdtemp(dir=TMP))
    st = accounts.AccountStore(d)
    st.register("anna", "", "", "geheim123")
    sec = st.begin_totp("anna")
    check(accounts.totp_code("JBSWY3DPEHPK3PXP", at=59) == accounts._hotp("JBSWY3DPEHPK3PXP", 1), "totp")
    st.confirm_totp("anna", accounts.totp_code(sec))
    raises(accounts.TotpRequired, st.authenticate, "anna", "geheim123")
    # Sitzungen: 24 h, für immer, abgelaufen
    st2 = accounts.AccountStore(Path(tempfile.mkdtemp(dir=TMP)))
    st2.register("bob", "", "", "geheim123")
    st2.create_session("bob", 1)
    check(st2.resume_session()["username"] == "bob", "session 24h")
    st2.create_session("bob", None)
    s = json.loads(st2.session_path.read_text())
    check(s["expires"] is None and st2.resume_session(), "session für immer")
    s["expires"] = int(time.time()) - 5
    st2.session_path.write_text(json.dumps(s))
    check(st2.resume_session() is None, "abgelaufene Sitzung")
    st2.create_session("bob", 7)
    st2.clear_session()
    check(st2.resume_session() is None, "clear_session")


# ---------------------------------------------------------------- Fake-Supabase
class FakeSupabase(http.server.BaseHTTPRequestHandler):
    users = {}        # email -> {"id","password","profile"}
    tokens = {}       # access/refresh token -> email
    codes = {}
    ai_calls = []

    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        raw = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _session(self, email):
        a, r = f"a-{len(self.tokens)}-{email}", f"r-{len(self.tokens)}-{email}"
        self.tokens[a] = self.tokens[r] = email
        return {"access_token": a, "refresh_token": r, "expires_in": 3600, "token_type": "bearer"}

    def do_GET(self):
        p = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(p.query)
        if p.path == "/auth/v1/authorize":
            email = "google-user@gmail.com"
            self.users.setdefault(email, {"id": "g1", "password": None, "profile": None})
            code = "code-" + q["code_challenge"][0][:8]
            self.codes[code] = email
            self.send_response(302)
            self.send_header("Location", f"{q['redirect_to'][0]}?code={code}")
            self.end_headers()
        else:
            self._send(404, {})

    def do_POST(self):
        p = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(p.query)
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0) or b"{}")
        auth = self.headers.get("Authorization", "").replace("Bearer ", "")
        if p.path == "/auth/v1/signup":
            if body["email"] in self.users:
                return self._send(422, {"msg": "User already registered"})
            self.users[body["email"]] = {"id": "u" + str(len(self.users)), "password": body["password"], "profile": None}
            return self._send(200, self._session(body["email"]))
        if p.path == "/auth/v1/token":
            gt = q["grant_type"][0]
            if gt == "password":
                u = self.users.get(body["email"])
                if not u or u["password"] != body["password"]:
                    return self._send(400, {"error_description": "Invalid login credentials"})
                return self._send(200, self._session(body["email"]))
            if gt == "refresh_token":
                email = self.tokens.get(body["refresh_token"])
                return self._send(200, self._session(email)) if email else self._send(400, {"error_description": "invalid_grant"})
            if gt == "pkce":
                email = self.codes.get(body["auth_code"])
                return self._send(200, self._session(email)) if email and body.get("code_verifier") else self._send(400, {"error": "bad code"})
        if p.path == "/auth/v1/logout":
            return self._send(204, {})
        if p.path.startswith("/rest/v1/rpc/"):
            email = self.tokens.get(auth)
            if not email:
                return self._send(401, {"message": "JWT expired"})
            u, name = self.users[email], p.path.rsplit("/", 1)[1]
            if name == "jopml_ensure_profile":
                if u["profile"] is None:
                    u["profile"] = {"username": body.get("p_username") or "g_" + u["id"], "display_name": body.get("p_display_name") or "Google User",
                                    "email": email if u["password"] is None else "", "settings": {}}
                return self._send(200, u["profile"])
            if name == "jopml_get_profile":
                return self._send(200, u["profile"])
            if name == "jopml_save_profile":
                for k, v in body["p"].items():
                    if k == "settings":
                        u["profile"]["settings"].update(v)
                    else:
                        u["profile"][k] = v
                return self._send(200, u["profile"])
            if name == "jopml_delete_account":
                self.users.pop(email)
                return self._send(200, True)
        if p.path == "/functions/v1/jopml-ai":
            self.ai_calls.append(body)
            if body["kind"] == "macro":
                return self._send(200, {"reply": "```\nrepeat 3\n  key e\n  wait 20ms\nend\n```"})
            return self._send(200, {"reply": "Use the Add macros page."})
        self._send(404, {"message": "not found"})


def fake_server():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeSupabase)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}"


def test_cloud_flow():
    from core import cloud, identity, oauth_loopback
    FakeSupabase.users.clear(), FakeSupabase.tokens.clear()
    srv, url = fake_server()
    try:
        ident = identity.CloudIdentity(cloud.CloudClient(url, "pub-key"))
        u = ident.register("Neu_Nutzer", "Neu", "", "geheim123")
        check(u["backend"] == "cloud" and u["email"] == "" and u["display_name"] == "Neu", "cloud register")
        raises(accounts.AccountError, ident.register, "neu_nutzer", "", "", "geheim123")
        raises(accounts.AccountError, ident.login, "neu_nutzer", "falsch")
        u = ident.login("neu_nutzer", "geheim123")
        u = ident.update_profile(u, "Neuer Name", "x@y.de")
        check(ident.client.get_profile()["display_name"] == "Neuer Name", "profil gespeichert")
        ident.push_settings(u, {"accent": "#ff0000", "language": "de", "legal_hash": "nicht-syncen"})
        time.sleep(0.4)
        saved = FakeSupabase.users[cloud.CloudClient.pseudo_email("neu_nutzer")]["profile"]["settings"]
        check(saved == {"accent": "#ff0000", "language": "de"}, f"nur SYNC_KEYS werden gespiegelt: {saved}")
        # angemeldet bleiben (7 Tage) + Wiederaufnahme mit rotiertem Token
        ident.remember(u, 7)
        ident2 = identity.CloudIdentity(cloud.CloudClient(url, "pub-key"))
        r = ident2.resume()
        check(r and r["display_name"] == "Neuer Name", "resume")
        ident2.remember(r, 0)
        check(identity.CloudIdentity(cloud.CloudClient(url, "pub-key")).resume() is None, "nicht angemeldet bleiben")
        # Export + Löschen
        data = ident.export(u)
        check(data["profile"]["display_name"] == "Neuer Name", "export")
        ident.delete(u, "")
        raises(accounts.AccountError, ident.login, "neu_nutzer", "geheim123")
        # Google (PKCE) über Loopback
        def fake_browser(auth_url):
            def go():
                opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler())
                opener.open(auth_url, timeout=10).read()
            threading.Thread(target=go, daemon=True).start()
        oauth_loopback.open_browser = fake_browser
        from core import version
        cloud.OAUTH_LOOPBACK_PORT = 0
        g = ident.google()
        check(g["google_linked"] and g["backend"] == "cloud", "google login")
    finally:
        srv.shutdown()


def test_ai_and_generator():
    from core import ai_client, assistant, cloud, identity
    from modules.macros import dsl, generator
    FakeSupabase.users.clear(), FakeSupabase.tokens.clear(), FakeSupabase.ai_calls.clear()
    srv, url = fake_server()
    try:
        class App: pass
        app = App()
        app.identity = identity.CloudIdentity(cloud.CloudClient(url, "k"))
        check(not ai_client.available(app), "ohne Anmeldung keine KI")
        raises(ai_client.AiUnavailable, ai_client.ask, app, "help", [])
        app.identity.register("kiuser", "", "", "geheim123")
        check(ai_client.available(app), "KI nach Anmeldung")
        text, via_ai = assistant.reply(app, "wie mache ich das?", [{"role": "user", "content": "x"}])
        check(via_ai and "Add macros" in text, "help via KI")
        ask = lambda m: ai_client.ask(app, "macro", m)
        script, src = generator.generate("mach etwas völlig Unklares mit Schleifen", ask)
        check(src == "ai" and dsl.parse(script), "macro via KI")
    finally:
        srv.shutdown()
    # offline vor KI; KI-Müll wird abgelehnt
    check(generator.generate("Klicke alle 50ms an Position 500 300", None)[1] == "offline", "offline zuerst")
    bad_calls = []
    def bad(m):
        bad_calls.append(m)
        return "os.system('rm -rf /')"
    err = raises(generator.GenerateError, generator.generate, "irgendwas unverständliches", bad)
    check(len(bad_calls) == 2, "genau ein Wiederholungsversuch")
    raises(generator.GenerateError, generator.generate, "", None)


# ---------------------------------------------------------------- Makro-Sprache
class Rec:
    def __init__(self): self.log = []
    def click(self, b, xy, n): self.log.append(("click", b, xy, n))
    def move(self, x, y): self.log.append(("move", x, y))
    def key(self, k): self.log.append(("key", k))
    def hold(self, k, s, r): self.log.append(("hold", k, s))
    def type(self, t): self.log.append(("type", t))
    def scroll(self, n): self.log.append(("scroll", n))


def test_dsl():
    from modules.macros import dsl
    cmds = dsl.parse('# Kommentar\nrepeat 3\n  click right 10 20\n  wait 1s\nend\ntype "a # b"\nscroll -2')
    rec, waits = Rec(), []
    r = dsl.Runner(rec, sleep=waits.append)
    check(r.run(cmds) == "done", "run done")
    check(rec.log[:2] == [("click", "right", (10, 20), 1)] * 2 and rec.log[-2:] == [("type", "a # b"), ("scroll", -2)], rec.log)
    check(waits == [1.0, 1.0, 1.0], waits)
    check(dsl.parse_duration("50ms") == 0.05 and dsl.parse_duration("1,5s") == 1.5 and dsl.parse_duration("2m") == 120, "dauer")
    for bad, why in [("click left 1", "Position braucht 2 Zahlen"), ("foo", "unbekannt"), ("repeat 2\nclick", "ohne end"), ("end", "end ohne repeat"),
                     ("repeat forever\nclick\nend", "Endlosschleife ohne wait"), ("key notakey", "Taste"), ("wait 2h", "Dauer"),
                     ("repeat 1\nrepeat 1\nrepeat 1\nrepeat 1\nrepeat 1\nclick\nend\nend\nend\nend\nend", "zu tief"),
                     ("repeat 1000000\nrepeat 1000000\nclick\nend\nend", "zu viele Aktionen"), ("repeat 2\nrepeat forever\nwait 5ms\nend\nend", "forever innen"),
                     ("move 99999 1", "Koordinate"), ("", "leer"), ("\n".join(["click"] * 401), "zu viele Zeilen"), ('type "x', "Anführungszeichen")]:
        raises(dsl.MacroError, dsl.parse, bad)
    # sofort abbrechbar
    cmds = dsl.parse("repeat forever\n  key a\n  wait 5ms\nend")
    rec = Rec()
    runner = dsl.Runner(rec)
    t = threading.Thread(target=runner.run, args=(cmds,))
    t.start()
    time.sleep(0.15)
    runner.stop()
    t.join(2)
    check(not t.is_alive() and len(rec.log) > 3, "stop")
    # Offline-Generator
    g = lambda s: dsl.generate_offline(s)
    check(g("Klicke alle 50ms an Position 500 300")[0] == "repeat forever\n  click left 500 300\n  wait 50ms\nend", g("Klicke alle 50ms an Position 500 300"))
    check(g("click every 100 ms for 10 seconds")[0].startswith("repeat 100\n"), "for-Dauer")
    check("key e" in g("drücke die Taste e alle 2 sekunden")[0], "taste")
    check(g("tippe \"hallo\" dann warte 2 sekunden dann doppelklick")[0] == 'type "hallo"\nwait 2s\ndoubleclick left', "mehrere Sätze")
    check(g("scrolle runter 5")[0] == "scroll -5", "scroll")
    check(g("blablabla") is None, "unverständlich -> None")
    check(dsl.extract_script("Hier:\n```text\nclick\n```\nFertig") == "click", "codezaun")


# ---------------------------------------------------------------- Recoil
def test_recoil():
    from modules.recoil import engine
    cfg = engine.RecoilConfig.from_dict({"y": 999, "interval_ms": 1, "x": "abc"})
    check(cfg.y == 20 and cfg.interval_ms == 4 and cfg.x == 0.0, f"clamp {cfg}")
    c = engine.RecoilConfig(y=2.0, ramp_pct=50, ramp_ms=1000, delay_ms=100)
    check(engine.step(c, 50) == (0.0, 0.0), "delay")
    check(abs(engine.step(c, 1100)[1] - 3.0) < 1e-9, "ramp voll")
    comp = engine.Compensator()
    total = sum(comp.feed(0, 1.4)[1] for _ in range(10))
    check(total == 14, f"Bruchteile summieren sich: {total}")

    class B:
        def __init__(self): self.moves = []
        def move_relative(self, dx, dy): self.moves.append((dx, dy))
    b = B()
    eng = engine.RecoilEngine(b, engine.RecoilConfig(y=3, interval_ms=5, ramp_pct=0))
    eng.start()
    eng.set_pressed(True)
    time.sleep(0.15)
    check(not b.moves, "ohne enabled keine Bewegung")
    eng.enabled = True
    time.sleep(0.2)
    n = len(b.moves)
    check(n > 3 and all(m == (0, 3) for m in b.moves), f"bewegt {n}")
    eng.set_pressed(False)
    time.sleep(0.1)
    n2 = len(b.moves)
    time.sleep(0.15)
    check(len(b.moves) == n2, "Taste losgelassen -> Ruhe")
    eng.shutdown()


# ---------------------------------------------------------------- Extensions
def test_extensions():
    from modules.extensions import catalog
    settings, saves = {}, []
    st = catalog.Store(settings, lambda: saves.append(1))
    check(not st.added("notes"), "start leer")
    st.add("quicklinks"); st.add("websearch")
    check(st.enabled("quicklinks"), "add = aktiv")
    st.set_enabled("quicklinks", False)
    check(not st.enabled("quicklinks"), "aus")
    st.set_config("quicklinks", links=[["Meine Seite", "example.org"]])
    check(st.config("quicklinks")["links"] == [["Meine Seite", "https://example.org"]], st.config("quicklinks"))
    raises(ValueError, st.set_config, "quicklinks", links=[["x", "javascript:alert(1)"]])
    raises(ValueError, st.set_config, "quicklinks", links=[["x", "file:///etc/passwd"]])
    raises(ValueError, st.set_config, "websearch", engine="Evil")
    check(catalog.search_url("Google", "a b&c") == "https://www.google.com/search?q=a+b%26c", "such-URL")
    st.remove("websearch")
    check(not st.added("websearch") and saves, "remove")


# ---------------------------------------------------------------- i18n, Recht, Theme, Icon, Verknüpfungen
def test_i18n_coverage():
    sys.path.insert(0, str(ROOT / "tools"))
    import extract_strings
    keys = [k for k in extract_strings.all_strings() if k not in ("not added", "unknown extension", "unknown search engine")]
    for code in ("de", "es", "ru", "fr", "zh"):
        i18n.set_language(code)
        T = i18n._table
        short = [k for k in keys if len(k) <= 110]
        miss = [k for k in short if k not in T]
        check(len(miss) <= len(short) * 0.03, f"{code}: {len(miss)} kurze Texte ohne Übersetzung, z. B. {miss[:3]}")
        for k, v in T.items():                                # Platzhalter müssen übereinstimmen
            import re
            check(sorted(re.findall(r"\{\w+\}", k)) == sorted(re.findall(r"\{\w+\}", v)), f"{code}: Platzhalter in {k!r}")
    de_miss = [k for k in keys if k not in i18n._load("de")]
    check(not de_miss, f"de unvollständig: {de_miss[:3]}")
    i18n.set_language("de")
    check(i18n.tr("Welcome, {name}!", name="Jaron") == "Willkommen, Jaron!", "tr mit Platzhalter")
    check(i18n.tr("Unbekannter Text {x}", x=1) == "Unbekannter Text 1", "Fallback")
    i18n.set_language("xx")
    check(i18n.get_language() == "en", "unbekannte Sprache -> Englisch")
    from modules.recoil.plugin import WARNING
    i18n.set_language("de")
    check(i18n.tr(WARNING) == "ACHTUNG: Dieses Tool kann sehr leicht von modernen Anti-Cheat-Systemen erkannt werden. "
                              "Die Nutzung wird ausdrücklich nur in Offline-Spielen zu Bildungs- und Testzwecken empfohlen!", "exakte Warnung")
    i18n.set_language("en")


def test_legal_and_firstrun():
    from core import config, firstrun_view, legal_text, version
    de = legal_text.legal_text("de")
    check(len(de) > 20000, f"Rechtstext lang genug ({len(de)})")
    for needle in ["§ 1 ", "§ 2 ", "§ 3 ", "§ 4 ", "§ 5 ", "§ 6 ", "§ 7 ", "§ 521 BGB", "§ 276 Abs. 3 BGB", "§ 303a StGB", "§ 278 BGB",
                   "Easy Anti-Cheat", "Ricochet", "Vanguard", "BattlEye", "Valve Anti-Cheat", "Art. 11", "Art. 15", "Art. 17", "Art. 20",
                   "CISG", "EGBGB", "Brüssel-Ia", "Lugano", "§ 54 BGB", "§ 705 BGB", "§ 50 ZPO", "Public Domain", "Claude", "Gemini", "Supabase"]:
        check(needle in de, f"Rechtstext enthält {needle}")
    check(legal_text.legal_text("fr") == legal_text.legal_text("en"), "andere Sprachen -> Englisch")
    check(len(legal_text.legal_hash()) == 64, "hash")
    s = config.load_settings()
    s["legal_version"] = ""
    check(firstrun_view.needs_legal(s), "erster Start braucht Zustimmung")
    firstrun_view.record_acceptance(s)
    s2 = config.load_settings()
    check(s2["legal_version"] == version.LEGAL_VERSION and s2["legal_accepted_at"] > 0 and not firstrun_view.needs_legal(s2), "Zustimmung gespeichert")
    check(firstrun_view.at_bottom((0.4, 1.0)) and not firstrun_view.at_bottom((0.0, 0.5)), "Scroll-Barriere")
    check(config.DEFAULT_SETTINGS["language"] == "en" and config.DEFAULT_SETTINGS["first_run_done"] is False, "Start auf Englisch")
    check(version.GOOGLE_CLIENT_ID == "473834634054-ipmvjinmo40ik00jf9trspvqniugi8q8.apps.googleusercontent.com", "Client-ID")


def test_theme_icon_shortcuts():
    from core import appicon, shortcuts, theme
    theme.apply({"appearance_mode": "dark", "accent": "#112233", "colors": {"main": "#101010", "text": "#eeeeee", "card": "nope"}})
    check(theme.c("main") == ("#101010", "#101010") and theme.accent() == "#112233" and theme.c("card") == theme.DEFAULT_PALETTE["card"], "theme")
    theme.apply({})
    check(theme.accent() == theme.DEFAULT_ACCENT, "theme reset")
    try:
        from PIL import Image
    except ImportError:
        return
    for bg, img in [("#4f8cff", None), ("#ffffff", None), ("#000000", None)]:
        im = appicon.render(128, bg, img)
        check(im.size == (128, 128), "icon größe")
    im1, im2 = appicon.render(128, "#ff0000"), appicon.render(128, "#00ff00")
    check(im1.tobytes() != im2.tobytes(), "Hintergrund änderbar")
    # JOPML-Text ist immer sichtbar: Mitte des Icons unterscheidet sich vom reinen Hintergrund
    plain = Image.new("RGBA", (128, 128), "#ff0000")
    check(im1.crop((20, 40, 108, 88)).tobytes() != plain.crop((20, 40, 108, 88)).tobytes(), "JOPML sichtbar")
    pic = Path(TMP) / "bg.png"
    Image.new("RGB", (50, 30), "#00aa00").save(pic)
    check(appicon.render(128, "#000", str(pic)).size == (128, 128), "Hintergrundbild")
    if sys.platform.startswith("linux"):
        os.environ["XDG_DESKTOP_DIR"] = str(Path(TMP) / "Desktop")
        shortcuts._desktop_dir = lambda: Path(TMP) / "Desktop"
        shortcuts.create_desktop_shortcut()
        check(shortcuts.has_desktop_shortcut(), "Verknüpfung")
        shortcuts.remove_desktop_shortcut()
        check(not shortcuts.has_desktop_shortcut(), "Verknüpfung entfernt")
        shortcuts.set_autostart(True)
        check(shortcuts.is_autostart(), "autostart an")
        shortcuts.set_autostart(False)
        check(not shortcuts.is_autostart(), "autostart aus")


def test_ads_and_limits():
    from core import ads
    p = ads.provider()
    check(p.name == "placeholder" and not p.available() and p.load() is None, "Werbung ist inaktiv")
    g = ads.GoogleAdsProvider("ca-app-pub-0000000000000000/0000000000")
    check(g.available() and g.load() is None, "Schnittstelle vorhanden")


def test_dsl_translations_dont_crash():
    from modules.macros import dsl
    for code in ("de", "es", "ru", "fr", "zh"):
        i18n.set_language(code)
        e = raises(dsl.MacroError, dsl.parse, "click left 1")
        check(str(e), "Fehlertext")
    i18n.set_language("en")


# ---------------------------------------------------------------- GUI-Smoke (Attrappen)
def _local_only(fn):
    """Die Oberflächen-Tests laufen ohne Netzwerk: Cloud-Konfiguration aus version.py abschalten."""
    def wrapper():
        import types
        from core import identity as ident
        orig = ident.CloudClient
        ident.CloudClient = lambda: types.SimpleNamespace(configured=False)
        try:
            fn()
        finally:
            ident.CloudClient = orig
    wrapper.__name__ = fn.__name__
    return wrapper


@_local_only
def test_gui_smoke():
    from core import app as app_mod, config
    s = config.load_settings()
    s.update({"first_run_done": True, "legal_version": "2026-10-26"})
    config.save_settings(s)
    for lang in ("en", "de", "zh"):
        s["language"] = lang
        config.save_settings(s)
        a = app_mod.LauncherApp()
        if "smoke" not in a.accounts.users:
            a.accounts.register("smoke", "Smoke", "", "geheim123")
        a.login_done(a.identity.login("smoke", "geheim123"), None)
        for pid in ["dashboard", "autoclicker", "macros", "extensions", "recoil", "assistant", "contact", "settings"]:
            a.show(pid)
        for section in ["Account", "Appearance", "Language", "System", "Performance", "Legal & sources"]:
            a.settings_section = section
            a.pages.pop("settings", None)
            a.show("settings")
        a.apply_look({"accent": "#abcdef"})
        a.set_language("de")
        a.logout()
        a.close()
    s["first_run_done"] = False
    config.save_settings(s)
    a = app_mod.LauncherApp()          # zeigt das Erststart-Fenster
    check(a.root_frame is not None, "gate")


def main():
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  ok   {name}")
        except Exception:
            failed += 1
            print(f"  FAIL {name}\n{traceback.format_exc()}")
    print(f"\n{len(tests) - failed}/{len(tests)} Tests bestanden")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
