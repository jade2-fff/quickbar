Set WshShell = CreateObject("WScript.Shell")
scriptDir = WshShell.CurrentDirectory
WshShell.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
CreateObject("WScript.Shell").Run "pythonw.exe game_bar.py", 0, False
