# Скрипт для обработки документов и создания векторной базы знаний

param(
    [string]$DocumentPath = ".\documents\",
    [string]$Query = ""
)

Write-Host "🚀 Векторная база знаний - Docling + Ollama" -ForegroundColor Cyan
Write-Host "=" * 60

# Проверка готовности контейнера
Write-Host "`n✓ Проверка готовности контейнера..." -ForegroundColor Yellow
$result = docker exec docling-docling python -c "import docling, requests; print('OK')" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Контейнер ещё не готов. Зависимости устанавливаются..." -ForegroundColor Red
    Write-Host "   Проверьте статус: docker logs docling-docling --tail 5" -ForegroundColor Gray
    exit 1
}
Write-Host "   ✅ Контейнер готов!" -ForegroundColor Green

# Режим поиска
if ($Query -ne "") {
    Write-Host "`n🔍 Режим поиска" -ForegroundColor Cyan
    docker exec docling-docling python /app/search.py $Query
    exit 0
}

# Обработка документов
Write-Host "`n📝 Шаг 1: Извлечение текста из документов..." -ForegroundColor Yellow
docker exec docling-docling python /app/process_documents.py /documents/

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Ошибка обработки документов" -ForegroundColor Red
    exit 1
}

Write-Host "`n🔢 Шаг 2: Создание векторных эмбеддингов..." -ForegroundColor Yellow
docker exec docling-docling python /app/create_embeddings.py /shared/processed/

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Ошибка создания эмбеддингов" -ForegroundColor Red
    exit 1
}

Write-Host "`n✅ Готово! Документы обработаны и загружены в векторную базу." -ForegroundColor Green
Write-Host "`nТеперь можно искать:" -ForegroundColor Cyan
Write-Host "  .\process.ps1 -Query `"ваш вопрос`"" -ForegroundColor Gray
