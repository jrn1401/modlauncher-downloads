using System;
using System.IO;
using Avalonia.Controls;
using Avalonia.Interactivity;
using Avalonia.Platform;

namespace JOPML.Views;

public partial class LegalGateWindow : Window
{
    private bool _scrolledToEnd;
    public bool Accepted { get; private set; }

    public LegalGateWindow()
    {
        InitializeComponent();
        var uri = new Uri("avares://JOPML/Assets/legal_de.txt");   // Englisch: legal_en.txt je nach gewählter Sprache
        using var s = AssetLoader.Open(uri);
        LegalBox.Text = new StreamReader(s).ReadToEnd();
        // Schließen über das X zählt als Ablehnung.
        Closing += (_, e) => { if (!Accepted) Environment.Exit(0); };
    }

    // Barriere: Das Kontrollkästchen wird erst freigeschaltet, wenn ganz unten angekommen.
    private void OnScrolled(object? sender, ScrollChangedEventArgs e)
    {
        if (e.Source is ScrollViewer sv && sv.Offset.Y + sv.Viewport.Height >= sv.Extent.Height - 4)
        {
            _scrolledToEnd = true;
            AgreeBox.IsEnabled = true;
        }
    }

    // Akzeptieren erst nach Kontrollkästchen (und damit nach dem Scrollen bis ganz unten).
    private void OnChecked(object? sender, RoutedEventArgs e) =>
        AcceptBtn.IsEnabled = _scrolledToEnd && AgreeBox.IsChecked == true;

    private void OnAccept(object? sender, RoutedEventArgs e) { Accepted = true; Close(); }

    // Ablehnen beendet die Anwendung sofort.
    private void OnDecline(object? sender, RoutedEventArgs e) => Environment.Exit(0);
}
