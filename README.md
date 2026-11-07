<p align="center">
  <img src="assets/logo.png" alt="LeprendiX logo" width="180">
</p>

<h1 align="center">LeprendiX</h1>

<p align="center">
  A desktop practice-management application with an optional mobile companion.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-2.0.1-blue" alt="Version 2.0.1">
  <a href="LICENSE.txt">
    <img src="https://img.shields.io/badge/license-CC%20BY--NC--ND%204.0-lightgrey" alt="CC BY-NC-ND 4.0 License">
  </a>
  <a href="https://wundpraxis-moedling.at/">
    <img src="https://img.shields.io/badge/website-wundpraxis--moedling.at-2c7a7b" alt="Wundpraxis Mödling website">
  </a>
</p>

LeprendiX brings patient records, service documentation, billing workflows, and
mobile-assisted contract capture together in one application. It is built for
local use in a practice and keeps its desktop data on the practice computer.

## Features

- Manage patient records, services, and archived patients.
- Prepare invoices and manage material-order documents.
- Use custom word and PDF documents for generation.
- The mobile Companion app features a offline check-in system for new patients.
- Use custom contracts that patients need to sign via a in-app sinnig process.
- Keep patient and configuration data under the practice's control with encrypted databases and login sequence.
- Teamup calender integration for auto-importing appointments.

The Companion app transfers data only when the user initiates a sync. See the
[Companion documentation](Companion/README.md) for its data handling and Android
installation details.

## Getting started

### Windows

Download the latest Windows release from
[GitHub Releases](https://github.com/qztq/LeprendiX/releases/latest). Extract or
run the provided package and start LeprendiX. The Install Wizard guides you through the initial setup.

### From source

Use Windows with Python 3.10 or later. Make sure the Python installation
includes Tcl/Tk, which provides the standard-library `tkinter` GUI module.

Install the desktop application's third-party packages:

```powershell
python -m pip install Flask geopy Pillow PyMuPDF python-docx qrcode requests
```

Then start the application from the project root:

```powershell
python start.py
```

### Package the Windows application

Install auto-py-to-exe:

```powershell
python -m pip install auto-py-to-exe
```

The project includes [exe_config.json](exe_config.json) with the PyInstaller
options and bundled files. All input paths are relative to the project root, so
run the packager from that directory:

```powershell
auto-py-to-exe --config exe_config.json
```

The configuration builds the GUI launcher `start.py` as a windowed,
one-directory application. You can also open auto-py-to-exe and load
`exe_config.json` from its configuration-file control.

### Build the Android Companion

The Android build uses Node.js 22 or later, Java 21, and Android SDK platform
36 with Build Tools 36.0.0. Capacitor Android, Capacitor Core, and the Capacitor
CLI are pinned to 8.6.0 in `package.json`; the Gradle wrapper is 8.14.3 and
Android Gradle Plugin is 8.13.0.

From the project root, install the locked npm dependencies and prepare the
Companion web assets:

```powershell
npm ci
npm run android:stage
```

The Android project is generated locally and is not included in source control.
Create it once, then synchronize the staged web app:

```powershell
npx cap add android
npx cap sync android
```

To create a debug APK, the commands below read the app version from
`version.txt` and increment the version code in the local Android project:

```powershell
$versionName = (Get-Content .\version.txt -Raw).Trim()
$versionCodeMatch = Select-String -Path .\android\app\build.gradle -Pattern '^\s*versionCode\s+(\d+)\s*$'
if (-not $versionName) { throw "version.txt is empty" }
if (-not $versionCodeMatch) { throw "Could not read versionCode from android\app\build.gradle" }
$versionCode = [int]$versionCodeMatch.Matches[0].Groups[1].Value + 1
npm run android:prepare -- --version-code $versionCode --version-name $versionName
Set-Location android
.\gradlew.bat assembleDebug
```

`android:prepare` writes the incremented code back to the local Gradle file, so
the next build will increment it again. The Android project is not checked in;
when creating a fresh Android project, first set its `versionCode` to the latest
code used for a distributed APK. Android requires each update's code to be
higher than the previous one.

The debug APK is written to
`android/app/build/outputs/apk/debug/app-debug.apk`. For release signing,
installation, and update requirements, see the complete
[Android Companion build guide](Companion/README.md).

## Project layout

| Path | Contents |
| --- | --- |
| `src/` | Desktop application modules |
| `assets/` | Shared application images and document template |
| `Companion/` | Mobile Companion web application and local server |
| `scripts/` | Companion staging and Android preparation scripts |
| `android/` | Capacitor Android project |

## Data and privacy

LeprendiX is designed for local practice use. The desktop database, configuration,
and patient documents are stored locally. The Companion app connects to the
desktop application on the local network; contracts and patient data remain on
the mobile device for offline use until an explicit sync is started. Back up
application and patient data regularly and protect access to the devices that
store it.

## License

See [LICENSE.txt](LICENSE.txt) for the license terms.

## Support

For bug reports, questions, or feature requests, use the
[GitHub issue tracker](https://github.com/qztq/LeprendiX/issues).

## Use of AI in LeprendiX

Ai was used to quickly generate a moderate part of code, especially the new versions. The original program was however entirely programmed by me.
