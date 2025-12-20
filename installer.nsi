; NSIS Installer Script für LeprendiX
; Kompatibel mit NSIS 3.11

;--------------------------------
; Inkludiere Modern UI
!include "MUI2.nsh"

;--------------------------------
; Allgemeine Einstellungen

  ; Name der Applikation und der Installer-Datei
  Name "LeprendiX"
  OutFile "LeprendiX_Installer.exe"
  
  ; Standard-Installationsverzeichnis (Program Files für 64-bit, sonst Program Files (x86))
  InstallDir "$PROGRAMFILES64\LeprendiX"
  
  ; Installationspfad aus der Registry lesen, falls vorhanden (für Updates)
  InstallDirRegKey HKCU "Software\LeprendiX" ""

  ; Admin-Rechte anfordern (nötig für Schreibzugriff auf Programme-Ordner)
  RequestExecutionLevel admin

  ; Unicode-Unterstützung aktivieren
  Unicode True

;--------------------------------
; Interface Einstellungen (MUI2)

  !define MUI_ABORTWARNING
  ; Icon für den Installer (optional, Pfad anpassen oder auskommentieren)
  ; !define MUI_ICON "dein_icon.ico" 
  ; !define MUI_UNICON "dein_icon.ico"

;--------------------------------
; Seiten (Pages)

  !insertmacro MUI_PAGE_WELCOME
  ; !insertmacro MUI_PAGE_LICENSE "LICENSE.txt" ; Lizenzdatei falls vorhanden
  !insertmacro MUI_PAGE_DIRECTORY
  !insertmacro MUI_PAGE_INSTFILES
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

Section "Installieren" SecInstall

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

  ; Startmenü-Verknüpfungen erstellen
  CreateDirectory "$SMPROGRAMS\LeprendiX"
  CreateShortcut "$SMPROGRAMS\LeprendiX\LeprendiX.lnk" "$INSTDIR\LeprendiX.exe"
  CreateShortcut "$SMPROGRAMS\LeprendiX\Deinstallieren.lnk" "$INSTDIR\Uninstall.exe"

SectionEnd

;--------------------------------
; Uninstaller Sektion

Section "Uninstall"

  ; Lösche Installationsordner rekursiv
  ; ACHTUNG: RMDir /r löscht alles. Um die DB zu behalten, löschen wir selektiv.
  
  ; Lösche Verknüpfungen
  RMDir /r "$SMPROGRAMS\LeprendiX"

  ; Lösche Registry-Schlüssel
  DeleteRegKey HKCU "Software\LeprendiX"

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