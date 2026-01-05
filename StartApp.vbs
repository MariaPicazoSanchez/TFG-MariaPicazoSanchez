Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)

' 0 = oculto
WshShell.Run "pythonw launcher.py", 0, False
Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
WshShell.CurrentDirectory = FSO.GetParentFolderName(WScript.ScriptFullName)

' Ajusta esta ruta a tu instalación
pythonwPath = "C:\Python312\pythonw.exe"

cmd = """" & pythonwPath & """ ""launcher.py"""
WshShell.Run cmd, 0, False
