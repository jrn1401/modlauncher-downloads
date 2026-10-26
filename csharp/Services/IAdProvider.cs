namespace JOPML.Services;

/// <summary>
/// Schnittstelle für das Werbefenster unten links in der Sidebar.
///
/// WICHTIG: AdMob (Ad Unit IDs "ca-app-pub-XXXXXXXXXXXXXXXX/YYYYYYYYYY") gibt es nur für Android/iOS-Apps. Für Windows/Linux
/// gibt es kein offizielles Google-Ads-SDK. Auf dem Desktop wären Alternativen: ein Web-Banner (Google AdSense/Ad Manager in einem
/// eingebetteten WebView) oder ein anderes Netzwerk. Außerdem verbieten die Google-Richtlinien Werbung in Cheat-/Hack-Tools;
/// vor dem Aktivieren Richtlinien prüfen, sonst droht Kontosperrung.
/// </summary>
public interface IAdProvider
{
    bool IsActive { get; }
    /// <summary>Wird einmal beim Start mit der Ad Unit ID aufgerufen.</summary>
    void Initialize(string adUnitId);
    /// <summary>Liefert ein Avalonia-Control (z. B. WebView oder Platzhalter) für den Werbeplatz.</summary>
    object CreateView();
}

public sealed class PlaceholderAdProvider : IAdProvider
{
    // >>> HIER die Ad Unit ID eintragen, sobald ein Werbenetzwerk gewählt und freigeschaltet ist: <<<
    // Beispielformat AdMob (mobil):      "ca-app-pub-3940256099942544/6300978111"   (Google-Testbanner)
    // Beispielformat AdSense (Web):      "ca-pub-XXXXXXXXXXXXXXXX" + Slot-ID
    public const string AdUnitId = "";

    public bool IsActive => !string.IsNullOrWhiteSpace(AdUnitId);
    public void Initialize(string adUnitId) { /* Netzwerk-SDK hier initialisieren */ }
    public object CreateView() => new Avalonia.Controls.TextBlock { Text = "Ad", Opacity = 0.4 };
}
