# TrelloDeep — обновление (Windows). Запуск:
#   powershell -ExecutionPolicy Bypass -File .\update.ps1
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location $root
Write-Host "=== Обновление плагина TrelloDeep ===" -ForegroundColor Cyan
Write-Host "Забираю свежую версию с GitHub..."
git pull
$venvPy = Join-Path $root ".venv\Scripts\python.exe"
if (Test-Path $venvPy) {
    Write-Host "Обновляю зависимости..."
    & $venvPy -m pip install --quiet --upgrade -r (Join-Path $root "mcp\requirements.txt")
} else {
    Write-Host "Внимание: .venv не найден — запусти сначала install.ps1." -ForegroundColor Yellow
}
Write-Host ""
Write-Host "=== ГОТОВО ===" -ForegroundColor Green
Write-Host "Теперь полностью перезапусти Claude (закрой из трея и открой заново),"
Write-Host "и набери /mcp — обновления подхватятся."
Read-Host "Enter для выхода"
