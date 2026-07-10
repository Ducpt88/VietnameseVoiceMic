$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Venv = Join-Path $Root ".venv"
$Version = "1.1.1"
$ReleaseBaseUrl = "https://github.com/Ducpt88/VietnameseVoiceMic/releases/latest/download"

Set-Location $Root

if (-not (Test-Path $Venv)) {
  python -m venv $Venv
}

& "$Venv\Scripts\python.exe" -m pip install --upgrade pip
& "$Venv\Scripts\python.exe" -m pip install -r requirements.txt

& "$Venv\Scripts\python.exe" -m PyInstaller `
  --noconfirm `
  --clean `
  --noconsole `
  --onedir `
  --name VietnameseVoiceMic `
  --add-data "voice-mic-settings.json;." `
  --add-data "voice-context.json;." `
  voice_mic_icon.py

$Out = Join-Path $Root "dist\VietnameseVoiceMic"
Copy-Item (Join-Path $Root "README.md") $Out -Force
Copy-Item (Join-Path $Root "install-startup.ps1") $Out -Force
Copy-Item (Join-Path $Root "uninstall-startup.ps1") $Out -Force
Copy-Item (Join-Path $Root "updater.ps1") $Out -Force
Copy-Item (Join-Path $Root "voice-mic-settings.json") $Out -Force
Copy-Item (Join-Path $Root "voice-context.json") $Out -Force

$ReleaseDir = Join-Path $Root "releases"
New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
$Zip = Join-Path $ReleaseDir "VietnameseVoiceMic-windows.zip"
if (Test-Path $Zip) {
  Remove-Item $Zip -Force
}
Compress-Archive -Path (Join-Path $Out "*") -DestinationPath $Zip -Force
$Hash = (Get-FileHash -Algorithm SHA256 -Path $Zip).Hash.ToLowerInvariant()
$Manifest = [ordered]@{
  version = $Version
  zip_url = "VietnameseVoiceMic-windows.zip"
  sha256 = $Hash
  notes = "Vietnamese Voice Mic $Version"
  release_url = "$ReleaseBaseUrl/VietnameseVoiceMic-windows.zip"
}
$Manifest | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 -Path (Join-Path $ReleaseDir "version.json")

Write-Host ""
Write-Host "Build complete:" $Out
Write-Host "Run:" (Join-Path $Out "VietnameseVoiceMic.exe")
Write-Host "Zip:" $Zip
Write-Host "Manifest:" (Join-Path $ReleaseDir "version.json")
