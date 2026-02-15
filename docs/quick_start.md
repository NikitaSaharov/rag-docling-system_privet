# Быстрая инструкция

## Для TXT/MD файлов
Загружайте напрямую через веб-интерфейс http://localhost:5000

## Для PDF/DOCX файлов

### Вариант 1: Автоматический скрипт
```powershell
.\add_document.ps1 "путь\к\вашему\файлу.pdf"
```

### Вариант 2: Вручную
```powershell
# Шаг 1: Обработать PDF
docker exec docling-docling python /app/process_documents.py /documents/имя_файла.pdf

# Шаг 2: Создать эмбеддинги
docker exec docling-docling python /app/create_embeddings.py /shared/processed/

# Шаг 3: Обновите страницу и спрашивайте!
```

### Пример
Если у вас файл `Книга.pdf` в папке `documents`:
```powershell
docker exec docling-docling python /app/process_documents.py /documents/Книга.pdf
docker exec docling-docling python /app/create_embeddings.py /shared/processed/
```

## После обработки
Обновите http://localhost:5000 и задавайте вопросы по документу! 🚀
