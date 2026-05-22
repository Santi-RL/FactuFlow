Option Explicit

Dim fileSystem
Dim shell
Dim rootDir
Dim powerShellPath
Dim launcherPath
Dim command

Set fileSystem = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

rootDir = fileSystem.GetParentFolderName(WScript.ScriptFullName)
powerShellPath = shell.ExpandEnvironmentStrings("%SystemRoot%") & "\System32\WindowsPowerShell\v1.0\powershell.exe"
launcherPath = fileSystem.BuildPath(rootDir, "scripts\factuflow-local-tray.ps1")
command = Quote(powerShellPath) & " -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File " & Quote(launcherPath)

shell.Run command, 0, False

Function Quote(ByVal value)
    Quote = Chr(34) & value & Chr(34)
End Function
