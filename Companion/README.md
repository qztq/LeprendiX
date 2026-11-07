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
$versionName = (Get-Content .\version.txt -Raw).Trim()
$versionCodeMatch = Select-String -Path .\android\app\build.gradle -Pattern '^\s*versionCode\s+(\d+)\s*$'
if (-not $versionName) { throw "version.txt ist leer" }
if (-not $versionCodeMatch) { throw "versionCode in android\app\build.gradle nicht gefunden" }
$versionCode = [int]$versionCodeMatch.Matches[0].Groups[1].Value + 1
npm run android:prepare -- --version-code $versionCode --version-name $versionName
Set-Location android
.\gradlew.bat assembleDebug
```

`android:stage` kopiert die Companion-Webdateien nach `build/companion-web`.
`android:prepare` setzt die Android-Version und richtet die nötigen Manifest-
Berechtigungen ein. Die Befehle lesen den `version-name` automatisch aus
`version.txt` und erhöhen den `versionCode` aus der lokalen
`android/app/build.gradle` um eins. `android:prepare` speichert den neuen Code
dort, damit der nächste lokale Build ihn weiter erhöhen kann. Da der Android-
Ordner nicht eingecheckt wird, muss bei einer neu erzeugten Android-App zuerst
deren `versionCode` auf den Wert der zuletzt veröffentlichten APK gesetzt
werden. Jeder Update-Code muss größer als der zuletzt veröffentlichte sein.

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
