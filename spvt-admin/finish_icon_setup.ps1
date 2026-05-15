# Full pipeline: icon -> exe with embedded icon -> desktop shortcut.
# Run:  cd spvt-admin; .\finish_icon_setup.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

& "$PSScriptRoot\build_win.ps1"
& "$PSScriptRoot\create_desktop_shortcut.ps1"

Write-Host ""
Write-Host "Done: desktop shortcut SPVT Admin; exe: dist\SPVT_Admin\SPVT_Admin.exe"
