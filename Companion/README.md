# LeprendiX Companion (Android APK, Offline-First & Monats-Sync)

Die **LeprendiX Companion App** ist eine speziell für den **100% autarken Offline-Betrieb** auf günstigen Tablets im **Querformat (Landscape)** entwickelte App. Ihre Web-Oberfläche wird als installierbare Android-APK ausgeliefert. Sie ermöglicht das fortlaufende Erfassen von Patientendaten sowie das **DSGVO-konforme digitale Unterzeichnen von Behandlungs- und Datenschutzvereinbarungen** direkt im Wartezimmer – **völlig ohne Verbindung zum Haupt-PC oder Internet**.

Am Monatsende (oder bei Bedarf) werden alle neu hinzugekommenen Patientendaten in einem einzigen Schritt drahtlos via WLAN mit der Hauptanwendung `LeprendiX` synchronisiert. **Bereits synchronisierte Datensätze werden dabei automatisch erkannt und nicht erneut übertragen.**

---

## Android-APK als GitHub-Release veröffentlichen

Die Android-App wird direkt in eine APK verpackt; dafür muss die Web-App nicht auf einem Webserver bereitgestellt werden. Die APK enthält die benötigten App-Dateien, funktioniert offline und verbindet sich für die Synchronisation per WLAN mit dem LeprendiX-PC. Der APK-Build übernimmt `logo.png`, `index.html`, `manifest.json`, `favicon.ico`, `sw.js` sowie `css/`, `js/` und `res/`; lokale Dateien in `signatures/` werden ausdrücklich nicht in die APK aufgenommen.

### Einmalige Einrichtung

1. Erzeuge einen privaten Android-Signaturschlüssel und bewahre die Datei sicher auf. **Nicht ins Git-Repository hochladen.**
   ```powershell
   keytool -genkeypair -v -keystore companion-release.jks -alias leprendix-companion -keyalg RSA -keysize 2048 -validity 10000
   ```
2. Lege in den GitHub-Repository-Einstellungen unter **Settings → Secrets and variables → Actions** diese Repository-Secrets an:
   - `ANDROID_KEYSTORE_BASE64`: Base64-Inhalt von `companion-release.jks`, z. B. in PowerShell:
     ```powershell
     [Convert]::ToBase64String([IO.File]::ReadAllBytes(".\companion-release.jks"))
     ```
   - `ANDROID_KEYSTORE_PASSWORD`: Keystore-Passwort
   - `ANDROID_KEY_ALIAS`: `leprendix-companion` (oder der beim Erzeugen gewählte Alias)
   - `ANDROID_KEY_PASSWORD`: Passwort des Schlüssels

   Der Schlüssel wird für alle zukünftigen Releases benötigt. Geht er verloren, können installierte App-Versionen nicht regulär mit einer neuen APK aktualisiert werden.

### Release erstellen

Nach dem Push des Quellcodes einen eindeutigen Tag erstellen und pushen:

```powershell
git tag companion-v1.0.0
git push origin companion-v1.0.0
```

Der GitHub-Workflow `.github/workflows/companion-android-release.yml` baut eine signierte Release-APK und hängt sie an ein gleichnamiges GitHub-Release an. Android-Nutzer laden die APK dort herunter und installieren sie. Das ist ein signiertes APK für die Installation außerhalb des Play Stores; eine Veröffentlichung im Google Play Store benötigt zusätzlich ein AAB und den dafür vorgesehenen Play-Console-Workflow.

Die Versionsnummer im Tag muss pro Release erhöht werden. Android erhält für jeden Workflow-Lauf automatisch einen höheren `versionCode`.

---

## Kernfunktionen & Ablauf

### 1. Autarker Offline-Betrieb & Dashboard-Start
- **Dashboard als Startansicht:**
  - Zeigt auf einen Blick die Anzahl aller Datensätze (`Gesamt`, `Synchronisiert`, `Ausstehend`).
  - Schneller Start der Patientenerfassung über *"Neuen Patienten erfassen"*.
  - QR-Code-Scan der Hauptanwendung direkt aus dem Dashboard (Kamera oder manuelle Eingabe).
  - 1-Klick-Start der Monats-Synchronisation mit Statusanzeige.
- **Android-App ohne Webhosting:** Die Oberfläche ist direkt in der APK enthalten und läuft offline. Das PWA-Manifest und der Service Worker bleiben für den optionalen Browser-Betrieb erhalten.
- **Integrierte On-Screen-Tastatur:**
  - Vollwertige deutsche QWERTZ-Touch-Tastatur direkt im Web-Interface (`inputmode="none"` unterdrückt störende Betriebssystem-Tastaturen).
  - Verhindert Viewport-Verschiebungen und Ruckler auf schwachen Low-End-Tablets.
- **Lokale Queue auf dem Tablet (`localStorage`):** 
  - Jeder Patient durchläuft den 6-stufigen Wizard und unterschreibt digital.
  - Titel (`Dr.`, `Mag.`, `Dr. med.` etc.) werden direkt mit der Anrede kombiniert (z. B. *"Herr Dr."* oder *"Frau Mag. Dr."*).
  - Beim Klick auf *"Angaben & DSGVO sicher speichern"* wird der Datensatz sofort lokal mit Status `Ausstehend` (`synced: false`), Zeitstempel, Checkbox-Status und Signaturbild gesichert.
  - Das Tablet kehrt automatisch nach 10 Sekunden (oder per Klick) zum Dashboard zurück und ist bereit für den nächsten Patienten.
  - Der Praxis-PC mit LeprendiX muss währenddessen **weder eingeschaltet noch im WLAN erreichbar sein**.

### 2. Monats-Synchronisation (Pre-Sync Review & Batch-Übertragung)
- Am Monatsende startet das Praxisteam `LeprendiX` auf dem PC und klickt im Companion-Dashboard auf *"Monats-Synchronisation"*.
- **Pre-Sync Review (Ärztliche Prüfung pro Patient):**
  - Vor dem Versenden wird für jede neu erfasste Person eine Prüfkarte angezeigt.
  - **Hausbesuch-Schalter:** Die Ärztin/der Arzt kann mit einem Klick angeben, ob es sich um einen Hausbesuch handelt.
  - **Distanz- und Kilometergeld-Berechnung:** Die Entfernung von der Praxisadresse (`Triesterstraße 10/4, 2351 Wiener Neudorf`) zur Patientenadresse wird via `/calculate_distance` berechnet. Vorgeschlagen werden 1 € pro Kilometer für Hin- und Rückfahrt.
- **Batch-Übertragung mit Ladebalken:**
  - Ein Klick auf *"Jetzt alle Daten an LeprendiX senden"* startet die Übertragung.
  - Ein weich animierter Fortschrittsbalken visualisiert den Upload-Status.
  - LeprendiX legt die neuen Patienten automatisch in `patienten.db` an bzw. aktualisiert bestehende Datensätze (Vermeidung von Dubletten).
  - Alle unterzeichneten DSGVO-Einwilligungen werden als `.json` und die Signaturen als hochauflösendes `.png` in `/Companion/signatures/` archiviert.
  - Für jede importierte Person öffnet sich die Stammdaten-Leistungsmaske. Mit „Weiter“ wird die Leistung für die nächste Person erfasst; beim letzten Datensatz schließt das Fenster nach dem Speichern.
  - Erst wenn alle Leistungen gespeichert wurden, bestätigt LeprendiX den Sync. Bei Abbruch, Schließen oder Fehler bleiben die Datensätze auf dem Tablet ausstehend und werden nicht als `Synchronisiert` markiert.
- **Stammdaten-Leistungen in LeprendiX:**
  - Standard-Leistungen mit Kurzname, Beschreibung und Betrag werden wie im Tab „Stammdaten Leistungen“ erstellt oder bearbeitet.
  - Die neu gespeicherte Stammdaten-Leistung wird für die jeweilige Person als zuletzt ausgewählte Leistung hinterlegt.
  - Der Import legt keine Behandlung in der `leistungen`-Tabelle an.

---

## Datenfelder

Die Companion App erfasst alle für LeprendiX erforderlichen Daten mit minimalem Tippaufwand:
- **Titel:** Mehrfachauswahl über Chips (`Dr.`, `Dr. med.`, `Mag.`, `Dipl.-Ing.`, `BSc`, `MSc`, `PhD` etc. + Freitext), wird direkt mit der Anrede kombiniert (z. B. `Herr Dr.`, `Frau Mag. Dr.`)
- **Anrede:** Kachelauswahl (`Frau`, `Herr`, `Divers / Keine`)
- **Vorname & Nachname:** Erfassung über die integrierte Touch-Tastatur
- **Sozialversicherungsnummer:** Großes On-Screen Touch-Numpad inklusive **österreichischer Prüfziffernvalidierung (Modulo 11)** und Geburtsdatum-Erkennung
- **Wohnadresse:** Straße, Hausnummer, Adresszusatz (Top/Stiege), PLZ & Ort (mit automatischer Ortsvervollständigung anhand der österreichischen PLZ-Datenbank)
- **Krankenkasse:** Auswahl zwischen ÖGK, SVS, BVAEB, KFA, Privat/Selbstzahler und Sonstige; wird beim Sync am Patienten gespeichert
- **DSGVO & Verträge:** Frei konfigurierbare Vertragstexte aus `/Companion/res/` mit Pflicht-Einwilligungs-Checkboxen und digitaler Unterschrift

---

## Ordnerstruktur

```text
/Companion/
├── index.html                     # Patienten-Wizard, Admin & Monats-Sync
├── manifest.json                  # Web App Manifest (PWA, Landscape)
├── sw.js                          # Service Worker für 100% Offline-Betrieb
├── favicon.ico                    # App-Icon
├── css/
│   └── style.css                  # Landscape-Split-Design, Quick-Sync Banner, Touch-Buttons
├── js/
│   ├── app.js                     # Offline-Speicher, Queue-Verwaltung, Batch-Sync
│   ├── contracts.js               # Verträge laden, rendern & Checkbox-Validierung
│   ├── signature.js               # HTML5-Canvas Unterschriftenfeld (Bézier-Glättung)
│   └── austria_plz.js             # Österreichische PLZ-Datenbank & City-Autofill
├── res/                           # Vertragsvorlagen
│   ├── contracts_index.json       # Index & Aktivierungsstatus der Verträge
│   ├── dsgvo_datenverarbeitung.json # DSGVO-Einwilligung (Pflicht)
│   ├── behandlungsvertrag.json    # Behandlungsvereinbarung (Wahlarzt)
│   └── telemedizin_einwilligung.json # Telemedizin & E-Mail (Optional)
├── signatures/                    # Automatische Archivierung (Signatur-PNGs & Verträge)
├── server.py                      # Standalone-Testserver (Port 5050)
└── README.md                      # Dokumentation
```

---

## Admin-Bereich (PIN: `1234`)

Über die Einstellungen oben links in der Seitenleiste gelangen Sie in den Admin-Bereich:
1. **Monats-Synchronisation:**
   - Übersicht der erfassten Datensätze (Gesamt / Ausstehend / Synchronisiert).
   - Manuelles Auslösen der Synchronisation (`POST /sync_batch`).
2. **Verbindung:**
   - Host-IP und Token des Praxis-PCs (wird beim Scannen des QR-Codes automatisch gesetzt).
   - Verbindungstest (`/verify` und `/pong`).
3. **Verträge:**
   - Verträge in `/Companion/res/` per Schieberegler ein- oder ausschalten.
4. **Verlauf & DSGVO:**
   - Filterbare Liste ("Alle", "Nur Ausstehend", "Synchronisiert").
   - Möglichkeit, Datensätze bei Bedarf manuell als synchronisiert zu markieren oder den Verlauf DSGVO-konform zu leeren.
