// Beispiel: KI-Assistent als Cloudflare Worker (kostenloser Tarif reicht zum Start). NICHT getestet.
// Der API-Schlüssel liegt als Secret im Worker (ANTHROPIC_API_KEY), niemals im Programm.
//
// Einrichtung: dash.cloudflare.com -> Workers -> Worker erstellen -> diesen Code einfügen ->
// Settings -> Variables -> Secret "ANTHROPIC_API_KEY" anlegen -> Worker-Adresse in core/version.py
// bei ASSISTANT_URL eintragen.
//
// WICHTIG gegen hohe Kosten: Im Anthropic-Console-Konto ein monatliches Ausgabenlimit setzen und in
// Cloudflare unter Security -> WAF -> Rate limiting eine Regel anlegen (z. B. 20 Anfragen/Minute pro IP).

const SYSTEM = `Du bist der Hilfe-Assistent von "Jaron's OP Makro", einem Windows-Programm mit einem Auto-Clicker/Auto-Keyer ` +
  `(Modul "Jaron Op Makro"). Antworte kurz, freundlich und auf Deutsch. Funktionen: beliebige Maus-/Tastaturtaste, ` +
  `Intervall in ms/s/min, Wiederholungen oder Timer, globale Start/Stop-Hotkeys, Profile als JSON, Konto mit 2FA, ` +
  `Design-Einstellungen, Download-Drosselung. Wenn du etwas nicht sicher weißt, sag das und verweise auf "Kontakt".`;

export default {
  async fetch(request, env) {
    if (request.method !== "POST") return new Response("POST only", { status: 405 });
    let body;
    try { body = await request.json(); } catch { return new Response("bad json", { status: 400 }); }

    let msgs = (Array.isArray(body.messages) ? body.messages : [])
      .filter(m => m && (m.role === "user" || m.role === "assistant") && typeof m.content === "string")
      .slice(-10)
      .map(m => ({ role: m.role, content: m.content.slice(0, 1000) }));
    while (msgs.length && msgs[0].role !== "user") msgs.shift();
    if (!msgs.length || msgs[msgs.length - 1].role !== "user") return new Response("bad messages", { status: 400 });

    const r = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "x-api-key": env.ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
      },
      body: JSON.stringify({ model: "claude-sonnet-5-5", max_tokens: 500, system: SYSTEM, messages: msgs }),
    });
    const data = await r.json().catch(() => ({}));
    const reply = data?.content?.[0]?.text ?? "Der Assistent ist gerade nicht erreichbar.";
    return new Response(JSON.stringify({ reply }), { headers: { "content-type": "application/json" } });
  },
};
