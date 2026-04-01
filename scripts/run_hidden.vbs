Set WshShell = CreateObject("WScript.Shell")
' Obtém o diretório onde este script está localizado
strScriptPath = WScript.ScriptFullName
strScriptDir = Left(strScriptPath, InStrRev(strScriptPath, "\"))
' Executa o start_api.bat no mesmo diretório, escondido
WshShell.Run "cmd /c """ & strScriptDir & "start_api.bat""", 0
Set WshShell = Nothing
