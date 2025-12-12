Set WshShell = CreateObject("WScript.Shell")

' Pfad zur Python-Umgebung und main.py anpassen:
projectDir = CreateObject("WScript.Shell").ExpandEnvironmentStrings("%USERPROFILE%\Documents\LeprendiX\LeprendiX")
venvPython = projectDir & "\venv\Scripts\python.exe"
mainPy = projectDir & "\main.py"

' Kommando ausführen unsichtbar
cmd = """" & venvPython & """ """ & mainPy & """"
WshShell.Run cmd, 0, False
