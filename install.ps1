# TrelloDeep — установщик для команды (Windows PowerShell)
# Запуск: правой кнопкой по файлу -> "Выполнить с помощью PowerShell",
# либо в PowerShell:  powershell -ExecutionPolicy Bypass -File .\install.ps1
#
# Делает всё сам: создаёт venv, ставит зависимости, спрашивает токен,
# пишет .env и .mcp.json с правильными путями под этот компьютер.

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Write-Host "=== Установка плагина TrelloDeep ===" -ForegroundColor Cyan
Write-Host "Папка проекта: $root"
Write-Host ""

# 1. Ищем Python
$py = $null
foreach ($c in @("python", "py")) {
    try {
        & $c --version 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { $py = $c; break }
    } catch {}
}
if (-not $py) {
    Write-Host "Python не найден. Установи Python 3.10+ с https://python.org (галочка 'Add to PATH') и запусти снова." -ForegroundColor Red
    Read-Host "Enter для выхода"; exit 1
}
Write-Host "Python: $py — $(& $py --version)"

# 2. Виртуальное окружение
$venvPy = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-Host "Создаю виртуальное окружение (.venv)..."
    & $py -m venv (Join-Path $root ".venv")
}

# 3. Зависимости
Write-Host "Ставлю зависимости..."
& $venvPy -m pip install --quiet --upgrade pip
& $venvPy -m pip install --quiet -r (Join-Path $root "mcp\requirements.txt")
Write-Host "Зависимости установлены."
Write-Host ""

# 4. Ключ и токен
$defaultKey = "19182c221233719e958c9591183d3cee"
$key = Read-Host "Trello API KEY (просто Enter = общий ключ команды)"
if ([string]::IsNullOrWhiteSpace($key)) { $key = $defaultKey }

Write-Host ""
Write-Host "Теперь выпусти СВОЙ токен: открой ссылку в браузере, нажми Allow, скопируй токен:" -ForegroundColor Yellow
Write-Host "https://trello.com/1/authorize?expiration=30days&scope=read,write&response_type=token&name=TrelloDeep&key=$key" -ForegroundColor Yellow
Write-Host ""
$token = Read-Host "Вставь свой Trello TOKEN"
if ([string]::IsNullOrWhiteSpace($token)) {
    Write-Host "Токен пустой — установка прервана." -ForegroundColor Red
    Read-Host "Enter для выхода"; exit 1
}

# 5. .env (без BOM, иначе python-dotenv сломается)
$envContent = "TRELLO_KEY=$key`nTRELLO_TOKEN=$token`n"
[System.IO.File]::WriteAllText((Join-Path $root ".env"), $envContent)
Write-Host ".env создан."

# 6. .mcp.json с абсолютными путями под этот компьютер
$mcp = @{
    mcpServers = @{
        "trello-deep" = @{
            command = $venvPy
            args    = @( (Join-Path $root "mcp\server.py") )
        }
    }
}
$mcpPath = Join-Path $root ".mcp.json"
[System.IO.File]::WriteAllText($mcpPath, ($mcp | ConvertTo-Json -Depth 6))
Write-Host ".mcp.json создан: $mcpPath"

Write-Host ""
Write-Host "=== ГОТОВО ===" -ForegroundColor Green
Write-Host "Осталось:"
Write-Host "  1. Открой ЭТУ папку в Claude как проект"
Write-Host "     (или скопируй файл .mcp.json в папку своего рабочего проекта Claude)."
Write-Host "  2. Полностью перезапусти Claude."
Write-Host "  3. Набери /mcp — должен появиться trello-deep с 6 инструментами."
Write-Host ""
Read-Host "Enter для выхода"
