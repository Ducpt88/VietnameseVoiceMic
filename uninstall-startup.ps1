$ErrorActionPreference = "Stop"
$Startup = [Environment]::GetFolderPath("Startup")
$Link = Join-Path $Startup "Vietnamese Voice Mic.lnk"

if (Test-Path $Link) {
  Remove-Item $Link -Force
  Write-Host "Removed startup shortcut:" $Link
} else {
  Write-Host "Startup shortcut not found."
}
