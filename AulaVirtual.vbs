Set ws = CreateObject("Wscript.Shell")
ws.Run "powershell -ExecutionPolicy Bypass -File """ & CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName) & "\AulaVirtual.ps1""", 0
