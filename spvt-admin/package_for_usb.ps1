# Build SPVT Admin then pack dist\SPVT_Admin into a zip for USB.
# Run:  cd spvt-admin; .\package_for_usb.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

& .\build_win.ps1

$stamp = Get-Date -Format "yyyyMMdd_HHmm"
$zipName = "SPVT_Admin_for_USB_$stamp.zip"
$zipPath = Join-Path $PSScriptRoot $zipName
$folder = Join-Path $PSScriptRoot "dist\SPVT_Admin"

if (-not (Test-Path (Join-Path $folder "SPVT_Admin.exe"))) {
  throw "Build output missing: dist\SPVT_Admin\SPVT_Admin.exe"
}

if (Test-Path $zipPath) {
  Remove-Item -Force $zipPath
}

Compress-Archive -Path $folder -DestinationPath $zipPath -CompressionLevel Optimal

Write-Host ""
Write-Host "USB archive ready:"
Write-Host $zipPath
Write-Host "Copy this zip to flash drive. On another PC: extract the whole folder, then run SPVT_Admin.exe."
