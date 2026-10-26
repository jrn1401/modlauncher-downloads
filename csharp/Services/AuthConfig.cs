namespace JOPML.Services;

/// <summary>Feste Anmelde-Konfiguration. Muss mit core/version.py übereinstimmen.</summary>
public static class AuthConfig
{
    // Google OAuth Client ID (öffentlich, KEIN Geheimnis). Das Client-SECRET gehört nie in die App, nur in Supabase.
    public const string GoogleClientId = "473834634054-ipmvjinmo40ik00jf9trspvqniugi8q8.apps.googleusercontent.com";

    // Supabase: nach dem Anlegen des Projekts eintragen. Der "publishable key" ist öffentlich; nie den service_role-Key eintragen!
    public const string SupabaseUrl = "";
    public const string SupabasePublishableKey = "";

    // Lokaler Rückkehr-Port für den Google-Login (PKCE, Loopback). Muss in Supabase als Redirect-URL erlaubt sein.
    public const int OAuthLoopbackPort = 53682;
    public static string RedirectUri => $"http://127.0.0.1:{OAuthLoopbackPort}/callback";

    // Anmeldeadresse bei Supabase (Google-Provider, PKCE).
    public static string GoogleAuthorizeUrl(string codeChallenge) =>
        $"{SupabaseUrl}/auth/v1/authorize?provider=google&redirect_to={System.Uri.EscapeDataString(RedirectUri)}" +
        $"&code_challenge={codeChallenge}&code_challenge_method=s256";
}
