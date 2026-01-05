param(
    [Parameter(Mandatory=$true)]
    [string]$FilePath
)

Write-Host "📄 Добавление документа в базу знаний..." -ForegroundColor Cyan

# Копируем файл в documents
$fileName = Split-Path $FilePath -Leaf
Copy-Item $FilePath ".\documents\$fileName" -Force
Write-Host "✓ Файл скопирован: $fileName" -ForegroundColor Green

# Обработка через Docling
Write-Host "`n📝 Извлечение текста..." -ForegroundColor Yellow
docker exec docling-docling python /app/process_documents.py "/documents/$fileName"

# Создание эмбеддингов
Write-Host "`n🔢 Создание векторных эмбеддингов..." -ForegroundColor Yellow
docker exec docling-docling python /app/create_embeddings.py /shared/processed/

Write-Host "`n✅ Готово! Документ добавлен в базу знаний." -ForegroundColor Green
Write-Host "`nТеперь можете искать:" -ForegroundColor Cyan
Write-Host '  docker exec docling-docling python /app/search.py "ваш вопрос"' -ForegroundColor Gray
