$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $Python)) {
  $Python = Join-Path $Root ".venv\Scripts\python.exe"
}
if (-not (Test-Path $Python)) {
  $message = "Missing Python virtual environment. Run: python -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
  Set-Content -Path (Join-Path $Root "voice-mic-crash.log") -Value $message -Encoding UTF8
  throw $message
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

$stdoutLog = Join-Path $Root "voice-mic-start.log"
$stderrLog = Join-Path $Root "voice-mic-crash.log"
Set-Content -Path $stdoutLog -Value "" -Encoding UTF8
Set-Content -Path $stderrLog -Value "" -Encoding UTF8
$env:PYTHONWARNINGS = "ignore"
$pythonArgs = @(
  "-X", "utf8",
  "-W", "ignore",
  ".\voice_mic_icon.py"
)

Start-Process -FilePath $Python `
  -WorkingDirectory $Root `
  -WindowStyle Hidden `
  -ArgumentList $pythonArgs `
  -RedirectStandardOutput $stdoutLog `
  -RedirectStandardError $stderrLog
