# Проверка статуса установки зависимостей

Write-Host "🔍 Проверка статуса контейнера docling-docling..." -ForegroundColor Cyan
Write-Host ""

# Проверяем запущен ли контейнер
$running = docker ps --filter "name=docling-docling" --filter "status=running" --format "{{.Names}}"
if ($running -ne "docling-docling") {
    Write-Host "❌ Контейнер не запущен!" -ForegroundColor Red
    Write-Host "   Запустите: docker-compose up -d" -ForegroundColor Gray
    exit 1
}

Write-Host "✅ Контейнер запущен" -ForegroundColor Green

# Проверяем последние логи
Write-Host "`n📋 Последние логи установки:" -ForegroundColor Yellow
docker logs docling-docling --tail 5

Write-Host ""

# Проверяем готовность Python пакетов
Write-Host "🐍 Проверка Python пакетов..." -ForegroundColor Yellow
$result = docker exec docling-docling python -c "import docling, requests; print('✅ Все пакеты установлены!')" 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host $result -ForegroundColor Green
    Write-Host "`n🎉 Система готова к работе!" -ForegroundColor Cyan
    Write-Host "`nИспользуйте:" -ForegroundColor White
    Write-Host "  .\process.ps1              - Обработать документы" -ForegroundColor Gray
    Write-Host "  .\process.ps1 -Query `"..`"  - Поиск по базе" -ForegroundColor Gray
} else {
    Write-Host "⏳ Установка ещё не завершена..." -ForegroundColor Yellow
    Write-Host "   Подождите ещё 1-2 минуты" -ForegroundColor Gray
    Write-Host "`n   Запустите этот скрипт снова для проверки:" -ForegroundColor Gray
    Write-Host "   .\check_status.ps1" -ForegroundColor White
}
