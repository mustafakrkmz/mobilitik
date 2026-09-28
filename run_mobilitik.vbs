Option Explicit
Dim shell, fso, base, pythonExe, command
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
base = fso.GetParentFolderName(WScript.ScriptFullName)
pythonExe = fso.BuildPath(base, ".venv\Scripts\python.exe")

If Not fso.FileExists(pythonExe) Then
    MsgBox "Mobilitik kurulumu bulunamadi. Once install_windows.bat dosyasini calistirin.", 16, "Mobilitik"
    WScript.Quit 1
End If

shell.CurrentDirectory = base
command = Chr(34) & pythonExe & Chr(34) & " -m mobilitik.desktop"
shell.Run command, 0, False
