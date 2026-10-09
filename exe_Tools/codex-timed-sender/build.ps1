$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name "CodexTimedSender" `
    --collect-all PIL `
    app.py

Write-Host "Build complete: $projectRoot\dist\CodexTimedSender.exe"
