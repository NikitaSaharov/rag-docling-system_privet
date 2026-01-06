# Скрипт для запуска RAG системы с онлайн доступом через ngrok

Write-Host "🚀 Запуск RAG системы..." -ForegroundColor Green

# Проверяем что ngrok установлен
$ngrokPath = Get-Command ngrok -ErrorAction SilentlyContinue
if (-not $ngrokPath) {
    Write-Host "❌ ngrok не установлен!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Установите через winget:" -ForegroundColor Yellow
    Write-Host "  winget install ngrok.ngrok" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Или скачайте: https://ngrok.com/download" -ForegroundColor Yellow
    exit 1
}

# Запускаем Docker контейнеры
Write-Host "📦 Запуск Docker контейнеров..." -ForegroundColor Yellow
docker-compose up -d

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Ошибка запуска Docker!" -ForegroundColor Red
    exit 1
}

# Ждем пока сервисы запустятся
Write-Host "⏳ Ожидание запуска сервисов (15 секунд)..." -ForegroundColor Yellow
Start-Sleep -Seconds 15

# Проверяем что webapp доступен
Write-Host "🔍 Проверка webapp..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:5000" -UseBasicParsing -TimeoutSec 5
    Write-Host "✅ WebApp запущен!" -ForegroundColor Green
} catch {
    Write-Host "⚠️  WebApp еще запускается, подождите..." -ForegroundColor Yellow
}

# Запускаем ngrok в новом окне
Write-Host ""
Write-Host "🌐 Запуск ngrok туннеля..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "ngrok http 5000"

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "✅ Система запущена!" -ForegroundColor Green
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""
Write-Host "📱 Откройте окно ngrok и скопируйте URL" -ForegroundColor Yellow
Write-Host "   Будет вида: https://xxxx-xxx.ngrok-free.app" -ForegroundColor Cyan
Write-Host ""
Write-Host "🔗 Этот URL можно открыть с ЛЮБОГО устройства" -ForegroundColor Yellow
Write-Host "   (телефон, планшет, другой компьютер)" -ForegroundColor Cyan
Write-Host ""
Write-Host "⚠️  ВАЖНО: Сейчас НЕТ пароля!" -ForegroundColor Red
Write-Host "   Не делитесь URL с посторонними" -ForegroundColor Yellow
Write-Host ""
Write-Host "🛑 Для остановки:" -ForegroundColor Yellow
Write-Host "   1. Закройте окно ngrok" -ForegroundColor Cyan
Write-Host "   2. docker-compose down" -ForegroundColor Cyan
Write-Host ""
