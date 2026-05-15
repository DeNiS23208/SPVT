# Desktop shortcut for SPVT Admin (icon from embedded exe resource).
# Run:  cd spvt-admin; .\create_desktop_shortcut.ps1
# Optional: .\create_desktop_shortcut.ps1 -ExePath "D:\Tools\SPVT_Admin\SPVT_Admin.exe"

param(
  [string]$ExePath = ""
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not $ExePath) {
  $candidate = Join-Path $PSScriptRoot "dist\SPVT_Admin\SPVT_Admin.exe"
  if (Test-Path $candidate) { $ExePath = (Resolve-Path $candidate).Path }
}
if (-not $ExePath -or -not (Test-Path $ExePath)) {
  throw "SPVT_Admin.exe not found. Run .\build_win.ps1 first or pass -ExePath."
}

$workDir = Split-Path -Parent $ExePath
$desktop = [Environment]::GetFolderPath("Desktop")
$lnkPath = Join-Path $desktop "SPVT Admin.lnk"

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($lnkPath)
$shortcut.TargetPath = $ExePath
$shortcut.WorkingDirectory = $workDir
$shortcut.WindowStyle = 1
$shortcut.Description = "SPVT Admin - settings and test questions"
$shortcut.IconLocation = "$ExePath,0"
$shortcut.Save()

Write-Host "Shortcut created: $lnkPath"
