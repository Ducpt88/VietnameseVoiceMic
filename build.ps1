$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Venv = Join-Path $Root ".venv"

Set-Location $Root

if (-not (Test-Path $Venv)) {
  python -m venv $Venv
}

& "$Venv\Scripts\python.exe" -m pip install --upgrade pip
& "$Venv\Scripts\python.exe" -m pip install -r requirements.txt

& "$Venv\Scripts\python.exe" -m PyInstaller `
  --noconsole `
  --onedir `
  --name VietnameseVoiceMic `
  --add-data "voice-mic-settings.json;." `
  voice_mic_icon.py

$Out = Join-Path $Root "dist\VietnameseVoiceMic"
Copy-Item (Join-Path $Root "README.md") $Out -Force
Copy-Item (Join-Path $Root "install-startup.ps1") $Out -Force
Copy-Item (Join-Path $Root "uninstall-startup.ps1") $Out -Force

Write-Host ""
Write-Host "Build complete:" $Out
Write-Host "Run:" (Join-Path $Out "VietnameseVoiceMic.exe")
