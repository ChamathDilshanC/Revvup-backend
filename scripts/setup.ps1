# RevvUp backend — Windows venv setup (stops locked Python processes first)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "Stopping Python processes that may lock .venv..." -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -like "*revvup-backend*" -or $_.CommandLine -match "uvicorn" } |
    Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

if (Test-Path .venv) {
    Remove-Item -Recurse -Force .venv
}

py -3.13 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe -m pip check

Write-Host "`nDone. Run the API with:" -ForegroundColor Green
Write-Host "  .\.venv\Scripts\activate"
Write-Host "  python -m uvicorn app.main:app --reload --port 8000"
