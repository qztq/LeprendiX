# LeprendiX Companion (Android)

## Voraussetzungen

- Node.js 22 oder neuer
- Java Development Kit (JDK) 21
- Android SDK mit Plattform 36 und Build Tools 36.0.0
- Python 3 mit `npm`-Skripten ausführbar über den Befehl `python`
- Für Release-Updates: derselbe Android-Keystore und Schlüssel wie bei der
  bisherigen Release-APK

Die Android-Konfiguration verwendet Capacitor 8.6.0, Android Gradle Plugin
8.13.0 und den Gradle Wrapper 8.14.3. Die App-ID lautet
`com.qztq.leprendixcompanion`; als Mindestversion ist Android API 24 festgelegt.

## Debug-APK erstellen

Alle Befehle zunächst im Projektverzeichnis ausführen:

```powershell
npm ci
npm run android:stage

# Nur beim ersten Mal bzw. wenn der lokale Android-Ordner fehlt:
npx cap add android

npx cap sync android
npm run android:prepare -- --version-code 4 --version-name 2.0.1
Set-Location android
.\gradlew.bat assembleDebug
```

`android:stage` kopiert die Companion-Webdateien nach `build/companion-web`.
`android:prepare` setzt die Android-Version und richtet die nötigen Manifest-
Berechtigungen ein. Der `version-name` stammt standardmäßig aus `version.txt`
(aktuell `2.0.1`); `version-code` muss bei jedem Update größer als der vorherige
Wert sein. Im Beispiel ist `4` der nächste Code nach dem derzeit gespeicherten
Wert `3`.

Die Debug-APK befindet sich nach dem Build unter
`android/app/build/outputs/apk/debug/app-debug.apk`. Sie ist zum lokalen Testen
gedacht und kann keine installierte Release-APK ersetzen, wenn diese mit einem
anderen Schlüssel signiert ist.

## Release-APK erstellen

Release-Updates müssen mit demselben Keystore, Schlüsselalias und Passwort wie
die bisherige Release-App signiert werden. Die GitHub-Actions-Workflow-Datei
`.github/workflows/companion-android-release.yml` übernimmt Build und Signierung
für Release-Tags der Form `companion-v<version>`. Dafür müssen die Repository-
Secrets `ANDROID_KEYSTORE_BASE64`, `ANDROID_KEYSTORE_PASSWORD`,
`ANDROID_KEY_ALIAS` und `ANDROID_KEY_PASSWORD` eingerichtet sein. Ein lokaler
`assembleRelease`-Build ist ohne entsprechende Signierkonfiguration nicht als
installierbares Release-Update verwendbar.

Die APK darf ausschließlich von folgender Release-Adresse heruntergeladen werden:

<https://github.com/qztq/LeprendiX/releases/latest/download/LeprendiX_Mobile.apk>

## Verträge und Offline-Betrieb

- Vertrags-JSON-Dateien werden im Desktop-Installationsassistenten ausgewählt und
  unter `%LOCALAPPDATA%\LeprendiX\contracts` gespeichert, nicht im Repository.
- Die Companion-App erhält die Verträge bei einer Verbindung zum Praxis-PC über
  den QR-Code. Alternativ können die JSON-Dateien beim ersten Start direkt in der
  App importiert werden.
- Verträge und Patientendaten werden lokal auf dem Tablet gespeichert. Sie bleiben
  für die Offline-Nutzung verfügbar und werden erst nach ausdrücklichem Monats-Sync
  an die Hauptanwendung übertragen.
- APK-Updates werden höchstens monatlich geprüft. Android verlangt eine Bestätigung
  der Installation. Die App muss als Update über die vorhandene App installiert
  werden; nicht vorher deinstallieren. Android erhält die App-Daten beim Update,
  sofern Paket-ID und Signaturschlüssel gleich bleiben.
