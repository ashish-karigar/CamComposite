$ErrorActionPreference = "Stop"

Write-Host "CamComposite Windows build"
Write-Host ""

$VERSION = Read-Host "Enter version number (example: 1.0.0)"

if ([string]::IsNullOrWhiteSpace($VERSION)) {
    Write-Host "Version cannot be empty."
    exit 1
}

$APP_NAME = "CamComposite"
$FINAL_EXE = "release\CamComposite-win-v$VERSION.exe"
$INNO_SCRIPT = "packaging\win\CamComposite.iss"

# Adjust this only if your Inno Setup is installed somewhere else
$ISCC = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"

if (!(Test-Path $ISCC)) {
    Write-Host ""
    Write-Host "Inno Setup compiler not found here:"
    Write-Host $ISCC
    Write-Host "Install Inno Setup or update the ISCC path in build_win.ps1."
    exit 1
}

Write-Host ""
Write-Host "Cleaning old build files..."
Remove-Item build -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item dist -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "packaging\win\output" -Recurse -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Building app with PyInstaller..."
pyinstaller build-scripts\camcomposite_win.spec

if (!(Test-Path "dist\CamComposite\CamComposite.exe")) {
    Write-Host "PyInstaller build failed: dist\CamComposite\CamComposite.exe not found."
    exit 1
}

Write-Host ""
Write-Host "Preparing release folder..."
New-Item -ItemType Directory -Force -Path release | Out-Null

Write-Host ""
Write-Host "Building installer with Inno Setup..."
& $ISCC /Qp /O"packaging\win\output" /F"CamComposite-win-v$VERSION" $INNO_SCRIPT

$BUILT_INSTALLER = "packaging\win\output\CamComposite-win-v$VERSION.exe"

if (!(Test-Path $BUILT_INSTALLER)) {
    Write-Host "Installer build failed: $BUILT_INSTALLER not found."
    exit 1
}

Write-Host ""
Write-Host "Moving installer to release folder..."
Move-Item -Force $BUILT_INSTALLER $FINAL_EXE

Write-Host ""
Write-Host "Cleaning temporary build files..."
Remove-Item build -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item dist -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "packaging\win\output" -Recurse -Force -ErrorAction SilentlyContinue

Get-ChildItem -Path . -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path . -Recurse -Include *.pyc -File -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Build complete:"
Write-Host $FINAL_EXE

git add $FINAL_EXE