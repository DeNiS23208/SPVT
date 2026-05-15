# SPVT Admin - Windows PyInstaller build (output: dist\SPVT_Admin\).
# Run:  cd spvt-admin; .\build_win.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function New-VenvIfMissing {
  if (Test-Path ".venv\Scripts\python.exe") { return }
  $ok = $false
  try {
    & py -3 -m venv .venv
    if (Test-Path ".venv\Scripts\python.exe") { $ok = $true }
  } catch { }
  if (-not $ok) {
    & python -m venv .venv
  }
  if (-not (Test-Path ".venv\Scripts\python.exe")) {
    throw "Could not create .venv. Install Python 3.11+ (py or python in PATH)."
  }
}

New-VenvIfMissing

& .\.venv\Scripts\pip.exe install -q -r requirements.txt
& .\.venv\Scripts\pip.exe install -q pyinstaller
& .\.venv\Scripts\python.exe make_icon.py

if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }

& .\.venv\Scripts\pyinstaller.exe SPVT-Admin-windows.spec --noconfirm

$destDir = Join-Path $PSScriptRoot "dist\SPVT_Admin"
$readme = Join-Path $PSScriptRoot "PORTABLE_README_RU.txt"
if ((Test-Path $readme) -and (Test-Path $destDir)) {
  Copy-Item -Force $readme (Join-Path $destDir "PROCHITAJ.txt")
}

$starter = @"
@echo off
cd /d "%~dp0"
start "" /D "%~dp0" "SPVT_Admin.exe"
"@
Set-Content -Path (Join-Path $destDir "START_SPVT_Admin.bat") -Value $starter -Encoding ASCII

Write-Host ""
Write-Host "Done: dist\SPVT_Admin\SPVT_Admin.exe"
Write-Host "Copy the whole folder dist\SPVT_Admin (DLLs + PySide6)."
Write-Host "USB zip: .\package_for_usb.ps1"
Write-Host "Desktop shortcut (this PC): .\create_desktop_shortcut.ps1"