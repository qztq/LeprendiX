# LeprendiX Companion (Android)

## APK erstellen

Im Projektverzeichnis ausführen:

```powershell
npm ci
npm run android:stage
npx cap add android   # nur beim ersten Mal
npx cap sync android
npm run android:prepare -- --version-code <neue-fortlaufende-Nummer>
cd android
.\gradlew.bat assembleDebug
```

`version-name` wird aus `version.txt` übernommen. Für ein veröffentlichbares Update
muss `version-code` erhöht und die APK mit demselben Release-Schlüssel wie die
bisherige APK signiert werden. Eine Debug-APK kann eine Release-APK nicht ersetzen.

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
