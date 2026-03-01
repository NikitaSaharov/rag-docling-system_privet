# ============================================================
# VectorStom - Управление проектом
# Использование: .\manage.ps1 <команда> [аргументы]
# ============================================================

param(
    [Parameter(Position=0)]
    [string]$Command = "help",

    [Parameter(Position=1, ValueFromRemainingArguments=$true)]
    [string[]]$CmdArgs
)

# --- Конфигурация ---
$SERVER = "root@5.129.194.184"
$SERVER_PATH = "~/docling"
$PROJECT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$COMPOSE_FILE = Join-Path $PROJECT_DIR "docker-compose.yml"

# Имена контейнеров
$SERVICES = @{
    "webapp"       = "docling-webapp"
    "qdrant"       = "qdrant-docling"
    "ollama"       = "ollama-docling"
    "docling"      = "docling-docling"
    "telegram"     = "docling-telegram-bot"
    "n8n"          = "n8n-docling"
    "webui"        = "open-webui"
}

# --- Цвета ---
function Write-OK($msg)      { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Err($msg)     { Write-Host "  [!!] $msg" -ForegroundColor Red }
function Write-Info($msg)    { Write-Host "  [..] $msg" -ForegroundColor Yellow }
function Write-Header($msg)  { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }

# ============================================================
# КОМАНДЫ
# ============================================================

function Show-Help {
    Write-Host ""
    Write-Host "  VectorStom - Управление проектом" -ForegroundColor Cyan
    Write-Host "  =================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Локальные команды:" -ForegroundColor Yellow
    Write-Host "    .\manage.ps1 status             Статус всех контейнеров"
    Write-Host "    .\manage.ps1 start              Запустить все сервисы"
    Write-Host "    .\manage.ps1 stop               Остановить все сервисы"
    Write-Host "    .\manage.ps1 restart [сервис]   Перезапустить (все или один)"
    Write-Host "    .\manage.ps1 logs [сервис]      Показать логи"
    Write-Host "    .\manage.ps1 add-doc <путь>     Добавить документ PDF/DOCX"
    Write-Host "    .\manage.ps1 add-md <путь>      Добавить .md напрямую (минуя Docling)"
    Write-Host ""
    Write-Host "  Серверные команды:" -ForegroundColor Yellow
    Write-Host "    .\manage.ps1 deploy             Деплой на сервер"
    Write-Host "    .\manage.ps1 deploy-quick       Быстрый деплой (только webapp)"
    Write-Host "    .\manage.ps1 server-status      Статус сервера"
    Write-Host "    .\manage.ps1 server-logs [серв] Логи на сервере"
    Write-Host "    .\manage.ps1 backup             Скачать бэкап с сервера"
    Write-Host "    .\manage.ps1 ssh                Подключиться к серверу"
    Write-Host ""
    Write-Host "  Сервисы: webapp, qdrant, ollama, docling, telegram, n8n, webui" -ForegroundColor DarkGray
    Write-Host ""
}

# --- Статус ---
function Show-Status {
    Write-Header "Статус контейнеров"

    $running = docker ps --format "{{.Names}}|{{.Status}}|{{.Ports}}" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Err "Docker не запущен!"
        return
    }

    foreach ($key in $SERVICES.Keys | Sort-Object) {
        $container = $SERVICES[$key]
        $found = $running | Where-Object { $_ -like "$container|*" }
        if ($found) {
            $parts = $found -split '\|'
            $status = $parts[1]
            Write-OK "$($key.PadRight(12)) $status"
        } else {
            Write-Err "$($key.PadRight(12)) не запущен"
        }
    }

    # Проверка здоровья webapp
    Write-Header "Проверка здоровья"
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:5000" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
        Write-OK "WebApp отвечает (HTTP $($response.StatusCode))"
    } catch {
        Write-Err "WebApp не отвечает на localhost:5000"
    }

    # Проверка Qdrant
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:6333/collections" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
        Write-OK "Qdrant отвечает"
    } catch {
        Write-Err "Qdrant не отвечает на localhost:6333"
    }

    Write-Host ""
}

# --- Запуск / Остановка ---
function Start-Services {
    Write-Header "Запуск сервисов"
    Push-Location $PROJECT_DIR
    docker-compose up -d
    Pop-Location
    if ($LASTEXITCODE -eq 0) { Write-OK "Все сервисы запущены" }
    else { Write-Err "Ошибка при запуске" }
}

function Stop-Services {
    Write-Header "Остановка сервисов"
    Push-Location $PROJECT_DIR
    docker-compose down
    Pop-Location
    if ($LASTEXITCODE -eq 0) { Write-OK "Все сервисы остановлены" }
    else { Write-Err "Ошибка при остановке" }
}

# --- Перезапуск ---
function Restart-Service($svc) {
    if ($svc) {
        if ($SERVICES.ContainsKey($svc)) {
            Write-Header "Перезапуск $svc"
            docker restart $SERVICES[$svc]
        } else {
            Write-Err "Неизвестный сервис: $svc"
            Write-Info "Доступные: $($SERVICES.Keys -join ', ')"
        }
    } else {
        Write-Header "Перезапуск всех сервисов"
        Push-Location $PROJECT_DIR
        docker-compose restart
        Pop-Location
    }
}

# --- Логи ---
function Show-Logs($svc) {
    if (-not $svc) { $svc = "webapp" }

    if ($SERVICES.ContainsKey($svc)) {
        Write-Info "Логи $svc - последние 50 строк, Ctrl+C для выхода"
        docker logs $SERVICES[$svc] --tail 50 -f
    } else {
        Write-Err "Неизвестный сервис: $svc"
        Write-Info "Доступные: $($SERVICES.Keys -join ', ')"
    }
}

# --- Деплой ---
function Deploy-Full {
    Write-Header "Деплой на сервер"

    # 1. Git push
    Write-Info "Git push..."
    Push-Location $PROJECT_DIR
    git add -A
    $date = Get-Date -Format "dd.MM.yyyy HH:mm"
    git commit -m "deploy: $date" --allow-empty
    git push origin main
    Pop-Location

    if ($LASTEXITCODE -ne 0) {
        Write-Err "Git push не удался"
        return
    }
    Write-OK "Git push выполнен"

    # 2. SSH: pull + rebuild
    Write-Info "Обновление на сервере..."
    $remoteCmd = 'cd ~/docling && git pull origin main && docker-compose up -d --build'
    ssh $SERVER $remoteCmd

    if ($LASTEXITCODE -eq 0) {
        Write-OK "Деплой завершён!"
        Write-Info "Проверьте: .\manage.ps1 server-status"
    } else {
        Write-Err "Ошибка на сервере"
    }
}

function Deploy-Quick {
    Write-Header "Быстрый деплой (только webapp + telegram)"

    Push-Location $PROJECT_DIR
    git add -A
    $date = Get-Date -Format "dd.MM.yyyy HH:mm"
    git commit -m "quick deploy: $date" --allow-empty
    git push origin main
    Pop-Location

    if ($LASTEXITCODE -ne 0) {
        Write-Err "Git push не удался"
        return
    }

    $remoteCmd = 'cd ~/docling && git pull origin main && docker-compose restart webapp telegram-bot'
    ssh $SERVER $remoteCmd

    if ($LASTEXITCODE -eq 0) {
        Write-OK "Быстрый деплой завершён!"
    } else {
        Write-Err "Ошибка на сервере"
    }
}

# --- Статус сервера ---
function Show-ServerStatus {
    Write-Header "Статус сервера"
    Write-Info "Контейнеры:"
    ssh $SERVER 'docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"'
    Write-Info "Диск:"
    ssh $SERVER 'df -h /'
    Write-Info "Память:"
    ssh $SERVER 'free -h'
}

# --- Логи сервера ---
function Show-ServerLogs($svc) {
    if (-not $svc) { $svc = "webapp" }

    if ($SERVICES.ContainsKey($svc)) {
        Write-Info "Логи $svc на сервере - последние 100 строк"
        $container = $SERVICES[$svc]
        ssh $SERVER "docker logs $container --tail 100"
    } else {
        Write-Err "Неизвестный сервис: $svc"
    }
}

# --- Бэкап ---
function Download-Backup {
    Write-Header "Бэкап с сервера"

    $backupDir = Join-Path $PROJECT_DIR "backups"
    $date = Get-Date -Format "yyyy-MM-dd_HH-mm"
    $localDir = Join-Path $backupDir $date

    if (-not (Test-Path $backupDir)) { New-Item -ItemType Directory -Path $backupDir | Out-Null }
    New-Item -ItemType Directory -Path $localDir | Out-Null

    # 1. Бэкап БД
    Write-Info "Скачивание БД..."
    scp "${SERVER}:${SERVER_PATH}/shared/db/docling.db" "$localDir\docling.db"
    if ($LASTEXITCODE -eq 0) { Write-OK "БД скачана" }
    else { Write-Err "Ошибка скачивания БД" }

    # 2. Бэкап .env.local
    Write-Info "Скачивание .env.local..."
    scp "${SERVER}:${SERVER_PATH}/.env.local" "$localDir\.env.local"
    if ($LASTEXITCODE -eq 0) { Write-OK ".env.local скачан" }
    else { Write-Err "Ошибка скачивания .env.local" }

    # 3. Снэпшот Qdrant
    Write-Info "Создание снэпшота Qdrant..."
    ssh $SERVER 'curl -s -X POST http://localhost:6333/collections/documents/snapshots' | Out-Null

    Write-OK "Бэкап сохранён в: $localDir"
    Write-Host ""
}

# --- SSH ---
function Connect-SSH {
    Write-Info "Подключение к серверу..."
    ssh $SERVER
}

# --- Добавление документа ---
function Add-Document($filePath) {

    if (-not $filePath) {
        Write-Err "Укажите путь к файлу: .\manage.ps1 add-doc C:\path\to\file.pdf"
        return
    }

    if (-not (Test-Path $filePath)) {
        Write-Err "Файл не найден: $filePath"
        return
    }

    $fileName = Split-Path $filePath -Leaf
    $docsDir = Join-Path $PROJECT_DIR "documents"

    Write-Header "Добавление документа: $fileName"

    # 1. Копируем в documents/
    Write-Info "Копирование файла..."
    Copy-Item $filePath (Join-Path $docsDir $fileName) -Force
    Write-OK "Файл скопирован в documents/"

    # 2. Обработка через Docling
    Write-Info "Извлечение текста (Docling)..."
    docker exec docling-docling python /app/process_documents.py "/documents/$fileName"

    if ($LASTEXITCODE -ne 0) {
        Write-Err "Ошибка обработки документа"
        return
    }
    Write-OK "Текст извлечён"

    # 3. Создание эмбеддингов
    Write-Info "Создание эмбеддингов..."
    docker exec docling-docling python /app/create_embeddings.py /shared/processed/

    if ($LASTEXITCODE -eq 0) {
        Write-OK "Документ добавлен в базу знаний!"
    } else {
        Write-Err "Ошибка создания эмбеддингов"
    }
}

# --- Добавление MD напрямую ---
function Add-Markdown($filePath) {

    if (-not $filePath) {
        Write-Err "Укажите путь к файлу: .\manage.ps1 add-md C:\path\to\file.md"
        return
    }

    if (-not (Test-Path $filePath)) {
        Write-Err "Файл не найден: $filePath"
        return
    }

    $fileName = Split-Path $filePath -Leaf
    $processedDir = Join-Path $PROJECT_DIR "shared\processed"

    Write-Header "Добавление MD: $fileName"

    # 1. Копируем в shared/processed/
    if (-not (Test-Path $processedDir)) { New-Item -ItemType Directory -Path $processedDir | Out-Null }
    Copy-Item $filePath (Join-Path $processedDir $fileName) -Force
    Write-OK "Файл скопирован в shared/processed/"

    # 2. Создание эмбеддингов (минуя Docling)
    Write-Info "Создание эмбеддингов..."
    docker exec docling-docling python /app/create_embeddings.py "/shared/processed/$fileName"

    if ($LASTEXITCODE -eq 0) {
        Write-OK "Документ $fileName добавлен в базу знаний!"
    } else {
        Write-Err "Ошибка создания эмбеддингов"
    }
}

# ============================================================
# МАРШРУТИЗАЦИЯ КОМАНД
# ============================================================

switch ($Command.ToLower()) {
    "help"           { Show-Help }
    "status"         { Show-Status }
    "start"          { Start-Services }
    "stop"           { Stop-Services }
    "restart"        { Restart-Service $CmdArgs[0] }
    "logs"           { Show-Logs $CmdArgs[0] }
    "deploy"         { Deploy-Full }
    "deploy-quick"   { Deploy-Quick }
    "server-status"  { Show-ServerStatus }
    "server-logs"    { Show-ServerLogs $CmdArgs[0] }
    "backup"         { Download-Backup }
    "ssh"            { Connect-SSH }
    "add-doc"        { Add-Document $CmdArgs[0] }
    "add-md"         { Add-Markdown $CmdArgs[0] }
    default {
        Write-Err "Неизвестная команда: $Command"
        Show-Help
    }
}
