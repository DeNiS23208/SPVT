# Запуск SPVT: сайт доступен с других ПК в той же сети (Wi‑Fi / LAN).
# На этом ноутбуке откройте: http://127.0.0.1:8000
# С другого компа: http://<IP-этого-ноутбука>:8000  (IP — см. ipconfig, IPv4-адрес)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$port = 8000
Write-Host "Запуск на порту $port, интерфейс 0.0.0.0 (все сетевые интерфейсы)..." -ForegroundColor Cyan
Write-Host "Узнать IP ноутбука: ipconfig → IPv4-адрес" -ForegroundColor Yellow
Write-Host ""

& ".\.venv\Scripts\uvicorn.exe" app.main:app --host 0.0.0.0 --port $port --reload
