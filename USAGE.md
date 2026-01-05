# Инструкция по использованию векторной базы знаний

## Быстрый старт

### 1. Добавьте документы

Поместите ваши документы (PDF, DOCX, PPTX и др.) в папку `shared/input/`:

```powershell
Copy-Item "C:\путь\к\документу.pdf" ".\shared\input\"
```

### 2. Запустите обработку

```powershell
docker exec docling-docling bash /app/pipeline.sh
```

Этот скрипт:
- Извлечет текст из документов через Docling
- Разобьет текст на чанки
- Создаст векторные эмбеддинги через Ollama
- Загрузит в Qdrant

### 3. Поиск по документам

```powershell
docker exec docling-docling python /app/search.py "ваш вопрос"
```

Пример:
```powershell
docker exec docling-docling python /app/search.py "какие основные функции описаны в документе"
```

## Пошаговая обработка

Если хотите контролировать каждый шаг:

### Шаг 1: Извлечение текста
```powershell
docker exec docling-docling python /app/process_documents.py /shared/input/
```

Результат сохранится в `shared/processed/` в формате Markdown.

### Шаг 2: Создание эмбеддингов
```powershell
docker exec docling-docling python /app/create_embeddings.py /shared/processed/
```

### Шаг 3: Поиск
```powershell
docker exec docling-docling python /app/search.py "ваш запрос"
```

## Проверка статуса

### Проверить содержимое Qdrant
```powershell
Invoke-WebRequest -Uri "http://localhost:6333/collections/documents" | Select-Object -ExpandProperty Content
```

### Проверить количество документов
```powershell
Invoke-WebRequest -Uri "http://localhost:6333/collections/documents" | ConvertFrom-Json | Select-Object -ExpandProperty result
```

### Тест Ollama
```powershell
docker exec -it ollama-docling ollama run llama3.2 "напиши короткое приветствие"
```

## Автоматизация через n8n

1. Откройте n8n: http://localhost:5678 (admin/admin123)

2. Создайте новый workflow:

**Trigger**: Manual Trigger или Webhook

**Node 1**: Execute Command
- Command: `python /app/process_documents.py /shared/input/`
- Container: `docling-docling`

**Node 2**: Execute Command  
- Command: `python /app/create_embeddings.py /shared/processed/`
- Container: `docling-docling`

**Node 3**: HTTP Request (поиск)
- Method: POST
- URL: `http://qdrant-docling:6333/collections/documents/points/search`
- Body: JSON с вектором запроса

## Полезные команды

### Очистка базы данных
```powershell
Invoke-WebRequest -Uri "http://localhost:6333/collections/documents" -Method DELETE
```

Потом пересоздайте коллекцию:
```powershell
Invoke-WebRequest -Uri "http://localhost:6333/collections/documents" -Method PUT -Headers @{"Content-Type"="application/json"} -Body '{"vectors": {"size": 768, "distance": "Cosine"}}'
```

### Просмотр логов
```powershell
docker logs docling-docling
docker logs ollama-docling
docker logs qdrant-docling
```

### Перезапуск контейнера
```powershell
docker-compose restart docling
```

## Примеры использования

### Обработка одного файла
```powershell
docker exec docling-docling python /app/process_documents.py /shared/input/mydoc.pdf
docker exec docling-docling python /app/create_embeddings.py /shared/processed/mydoc.md
```

### Массовая обработка
```powershell
# Скопируйте все PDF в input
Copy-Item "C:\Documents\*.pdf" ".\shared\input\"

# Запустите полный pipeline
docker exec docling-docling bash /app/pipeline.sh
```

### RAG (Retrieval-Augmented Generation)
```powershell
# Система автоматически найдет релевантные документы и сгенерирует ответ
docker exec docling-docling python /app/search.py "объясни ключевые концепции"
```

## Структура данных в Qdrant

Каждая точка содержит:
- **id**: MD5 хеш (filename_chunk_index)
- **vector**: 768-мерный эмбеддинг
- **payload**:
  - `text`: текст чанка
  - `filename`: имя исходного файла
  - `chunk_index`: номер чанка
  - `total_chunks`: всего чанков в документе

## Параметры настройки

### Размер чанков
Отредактируйте `create_embeddings.py`:
```python
chunk_size = 500  # слов в чанке
overlap = 50      # перекрытие между чанками
```

### Модели
Измените модели в скриптах:
```python
# Для эмбеддингов
model = "nomic-embed-text"  # или "mxbai-embed-large"

# Для генерации
model = "llama3.2"  # или "mistral", "phi3"
```

### Количество результатов
```python
search(query, limit=5)  # измените limit
```
