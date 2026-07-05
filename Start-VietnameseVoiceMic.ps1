$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
  $Python = "python"
}

# Close the old browser-based mic app if it is still around.
Get-CimInstance Win32_Process |
  Where-Object {
    $_.Name -match '^(python|chrome|msedge)\.exe$' -and (
      $_.CommandLine -like '*voice_drop_server*' -or
      $_.CommandLine -like '*127.0.0.1:8877*' -or
      $_.CommandLine -like '*VI Mic Drop*' -or
      $_.CommandLine -like '*VietnameseVoiceMic*chrome-profile*'
    )
  } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

# Keep only one native mic icon instance.
Get-CimInstance Win32_Process |
  Where-Object {
    (
      $_.Name -match '^pythonw?\.exe$' -and
      $_.CommandLine -like '*voice_mic_icon.py*'
    ) -or (
      $_.Name -eq 'VietnameseVoiceMic.exe'
    )
  } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Start-Process powershell.exe -WindowStyle Hidden -ArgumentList @(
  "-NoProfile",
  "-ExecutionPolicy",
  "Bypass",
  "-Command",
  "Set-Location '$Root'; & '$Python' .\voice_mic_icon.py"
)
