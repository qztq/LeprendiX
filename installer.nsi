; NSIS Installer Script für LeprendiX
; Kompatibel mit NSIS 3.11

;--------------------------------
; Inkludiere Modern UI
!include "MUI2.nsh"

;--------------------------------
; Allgemeine Einstellungen

  ; Version automatisch aus version.txt auslesen
  !searchparse /file "version.txt" "" APP_VERSION

  ; Name der Applikation und der Installer-Datei
  Name "LeprendiX"
  OutFile "LeprendiX_Installer_v${APP_VERSION}.exe"
  
  ; Standard-Installationsverzeichnis (Program Files für 64-bit, sonst Program Files (x86))
  InstallDir "$PROGRAMFILES64\LeprendiX"
  
  ; Installationspfad aus der Registry lesen, falls vorhanden (für Updates)
  InstallDirRegKey HKCU "Software\LeprendiX" ""

  ; Admin-Rechte anfordern (nötig für Schreibzugriff auf Programme-Ordner)
  RequestExecutionLevel admin

  ; Unicode-Unterstützung aktivieren
  Unicode True

  ; Version Information
  VIProductVersion "${APP_VERSION}.0"
  VIAddVersionKey "ProductName" "LeprendiX"
  VIAddVersionKey "FileVersion" "${APP_VERSION}"
  VIAddVersionKey "FileDescription" "LeprendiX Installer"
  VIAddVersionKey "LegalCopyright" "LeprendiX"

;--------------------------------
; Interface Einstellungen (MUI2)

  !define MUI_ABORTWARNING
  ; Icon für den Installer (optional, Pfad anpassen oder auskommentieren)
  !define MUI_ICON "favicon.ico" 
  !define MUI_UNICON "favicon.ico"
  
  ; --- STYLE ANPASSUNGEN (LeprendiX Style) ---
  !define MUI_FONT "Segoe UI"
  !define MUI_INSTALLCOLORS "00f2ff 1a1a1a" ; Neon Text auf dunklem Grund (Installations-Log)
  ; Hinweis: Für den kompletten Dark-Mode sollten Sie 'sidebar.bmp' und 'header.bmp' dunkel gestalten.
  ; !define MUI_HEADERIMAGE_BITMAP "header.bmp"
  ; !define MUI_WELCOMEFINISHPAGE_BITMAP "sidebar.bmp"
  
  ; Finish Page Settings
  !define MUI_FINISHPAGE_RUN "$INSTDIR\LeprendiX.exe"
  !define MUI_FINISHPAGE_RUN_TEXT "LeprendiX starten"

;--------------------------------
; Seiten (Pages)

  !define MUI_PAGE_CUSTOMFUNCTION_SHOW "WelcomePageShow"
  !insertmacro MUI_PAGE_WELCOME

  !insertmacro MUI_PAGE_LICENSE "LICENSE.txt"
  !insertmacro MUI_PAGE_COMPONENTS
  !insertmacro MUI_PAGE_DIRECTORY
  !insertmacro MUI_PAGE_INSTFILES

  !define MUI_PAGE_CUSTOMFUNCTION_SHOW "FinishPageShow"
  !insertmacro MUI_PAGE_FINISH

  !insertmacro MUI_UNPAGE_WELCOME
  !insertmacro MUI_UNPAGE_CONFIRM
  !insertmacro MUI_UNPAGE_INSTFILES
  !insertmacro MUI_UNPAGE_FINISH

;--------------------------------
; Sprachen

  !insertmacro MUI_LANGUAGE "German"

;--------------------------------
; Installer Sektion

Section "LeprendiX (Erforderlich)" SecCore
  SectionIn RO

  SetOutPath "$INSTDIR"
  
  ; --- SCHUTZ FÜR patienten.db ---
  ; SetOverwrite off bewirkt, dass existierende Dateien NICHT überschrieben werden.
  SetOverwrite off
  
  ; Versuche die Datenbank zu installieren. 
  ; Wenn sie schon da ist, wird dieser Schritt ignoriert (Daten bleiben erhalten).
  ; Pfad anpassen: "output\LeprendiX\patienten.db"
  File "output\LeprendiX\patienten.db"
  
  ; --- RESTLICHE DATEIEN ---
  ; Ab hier wieder überschreiben erlauben (für Updates der .exe etc.)
  SetOverwrite on
  
  ; Alle Dateien aus dem auto-py-to-exe Output Ordner installieren
  ; /x schließt die patienten.db hier aus, da wir sie oben schon behandelt haben
  ; Pfad anpassen: "output\LeprendiX\*.*"
  File /r /x "patienten.db" "output\LeprendiX\*.*"

  ; Registry-Einträge für Installationspfad und Uninstaller
  WriteRegStr HKCU "Software\LeprendiX" "" $INSTDIR
  WriteUninstaller "$INSTDIR\Uninstall.exe"

  ; Eintrag in "Programme und Features" (Systemsteuerung) mit Icon und Details
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\LeprendiX" "DisplayName" "LeprendiX"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\LeprendiX" "UninstallString" "$\"$INSTDIR\Uninstall.exe$\""
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\LeprendiX" "DisplayIcon" "$INSTDIR\LeprendiX.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\LeprendiX" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\LeprendiX" "Publisher" "LeprendiX"

  ; Startmenü-Verknüpfungen erstellen
  CreateDirectory "$SMPROGRAMS\LeprendiX"
  CreateShortcut "$SMPROGRAMS\LeprendiX\LeprendiX.lnk" "$INSTDIR\LeprendiX.exe"
  CreateShortcut "$SMPROGRAMS\LeprendiX\Deinstallieren.lnk" "$INSTDIR\Uninstall.exe"

SectionEnd

Section "Desktop-Verknüpfung" SecDesktop
  CreateShortcut "$DESKTOP\LeprendiX.lnk" "$INSTDIR\LeprendiX.exe"
SectionEnd

;--------------------------------
; Uninstaller Sektion

Section "Uninstall"

  ; Lösche Installationsordner rekursiv
  ; ACHTUNG: RMDir /r löscht alles. Um die DB zu behalten, löschen wir selektiv.
  
  ; Lösche Verknüpfungen
  RMDir /r "$SMPROGRAMS\LeprendiX"
  Delete "$DESKTOP\LeprendiX.lnk"

  ; Lösche Registry-Schlüssel
  DeleteRegKey HKCU "Software\LeprendiX"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\LeprendiX"

  ; Lösche Haupt-Executable und Uninstaller
  Delete "$INSTDIR\LeprendiX.exe"
  Delete "$INSTDIR\Uninstall.exe"
  
  ; Lösche alle anderen Dateien außer der Datenbank
  ; Dies ist sicherer als RMDir /r, wenn die DB im selben Ordner liegt.
  Delete "$INSTDIR\*.pyd"
  Delete "$INSTDIR\*.dll"
  Delete "$INSTDIR\python*.dll"
  ; Füge hier weitere Dateitypen hinzu oder nutze RMDir /r mit Vorsicht
  
  ; Alternativ: Alles löschen, aber vorher prüfen (riskant für Automatisierung)
  ; Wenn du sicher bist, dass der User bei Deinstallation ALLES weg haben will:
  ; RMDir /r "$INSTDIR" 
  
  ; Sicherer Weg: Ordner nur löschen, wenn er leer ist (d.h. wenn DB nicht mehr da ist)
  RMDir "$INSTDIR"

SectionEnd

;--------------------------------
; Splash Screen (Optional)

Function .onInit
  ; Laufende Instanzen beenden, um Dateikonflikte zu vermeiden
  nsExec::Exec 'taskkill /F /IM "LeprendiX.exe"'
  Pop $0 ; Rückgabewert vom Stack entfernen
  Sleep 1000 ; Kurz warten, damit das System die Dateizugriffe freigibt
FunctionEnd

;--------------------------------
; Style Funktionen (Farben setzen)

Function WelcomePageShow
  ; Setzt Textfarben passend zum Dark-Mode (benötigt dunkle sidebar.bmp für guten Kontrast)
  ; Wir suchen das innere Dialog-Fenster (#32770) innerhalb des Hauptfensters ($HWNDPARENT)
  FindWindow $1 "#32770" "" $HWNDPARENT

  ; 1201 = Titel, 1202 = Text
  GetDlgItem $0 $1 1201
  SetCtlColors $0 "00f2ff" "transparent" ; Neon Titel (#00f2ff)
  GetDlgItem $0 $1 1202
  SetCtlColors $0 "FFFFFF" "transparent" ; Weißer Text
FunctionEnd

Function FinishPageShow
  FindWindow $1 "#32770" "" $HWNDPARENT
  ; 1201 = Titel, 1202 = Text
  GetDlgItem $0 $1 1201
  SetCtlColors $0 "00f2ff" "transparent"
  GetDlgItem $0 $1 1202
  SetCtlColors $0 "FFFFFF" "transparent"
FunctionEnd