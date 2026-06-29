$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Startup = [Environment]::GetFolderPath("Startup")
$Link = Join-Path $Startup "Vietnamese Voice Mic.lnk"

$Exe = Join-Path $Root "VietnameseVoiceMic.exe"
$Cmd = Join-Path $Root "Start Vietnamese Voice Mic.cmd"

if (Test-Path $Exe) {
  $Target = $Exe
  $WorkingDirectory = $Root
} elseif (Test-Path $Cmd) {
  $Target = $Cmd
  $WorkingDirectory = $Root
} else {
  throw "Cannot find VietnameseVoiceMic.exe or Start Vietnamese Voice Mic.cmd in $Root"
}

$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($Link)
$Shortcut.TargetPath = $Target
$Shortcut.WorkingDirectory = $WorkingDirectory
$Shortcut.Description = "Start Vietnamese Voice Mic in background"
$Shortcut.Save()

Write-Host "Installed startup shortcut:"
Write-Host $Link
