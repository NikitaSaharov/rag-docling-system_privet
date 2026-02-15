# AGENTS.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

**VectorStom** - RAG (Retrieval-Augmented Generation) система для поиска информации в документах стоматологических клиник с использованием AI. Система включает:
- Веб-интерфейс для интерактивного общения с документами
- Telegram бот для мобильного доступа
- Админ-панель для управления пользователями и контентом
- Векторный поиск с hybrid ranking (semantic + keyword matching)

## Architecture

### Core Services Stack
```
┌─────────────────────────────────────────────┐
│  User Interfaces                            │
│  - Web (Flask + Vanilla JS)                 │
│  - Telegram Bot (aiogram 3)                 │
└──────────────┬──────────────────────────────┘
               │
┌──────────────▼──────────────────────────────┐
│  Flask API (webapp/app.py)                  │
│  - Search endpoint (/api/search)            │
│  - Auth routes (JWT + bcrypt)               │
│  - Admin routes                             │
└──────────────┬──────────────────────────────┘
               │
┌──────────────▼──────────────────────────────┐
│  Data Layer                                 │
│  - Qdrant (vectors, 768-dim nomic-embed)    │
│  - SQLite (users, chat history, logs)       │
│  - Ollama (embeddings generation)           │
│  - DeepSeek/llama3.2 (LLM via Polza API)    │
└─────────────────────────────────────────────┘
```

### Document Processing Pipeline
```
PDF/DOCX → Docling → Markdown → Chunking → Ollama embeddings → Qdrant
```

**Key Point:** Docling и Ollama нужны только при добавлении новых документов. Для работы системы достаточно Qdrant, Flask webapp и DeepSeek API.

## Common Development Commands

### Starting the System
```bash
# Local development
docker compose up -d

# Production (with Nginx)
docker compose -f docker-compose.prod.yml up -d

# Check status
docker ps
docker logs -f docling-webapp
docker logs -f docling-telegram-bot
```

### Adding Documents
```bash
# 1. Process PDF/DOCX (converts to Markdown)
docker exec docling-docling python /app/process_documents.py /documents/filename.pdf

# 2. Create embeddings from Markdown (slow, with retries)
docker exec docling-docling python /app/create_embeddings_slow.py /shared/processed/filename.md

# Note: create_embeddings_slow.py uses adaptive chunking:
# - Small docs (<5k words): 300 words/chunk, 60 overlap
# - Medium docs (5-20k): 350 words/chunk, 70 overlap
# - Large docs (>20k): 300 words/chunk, 60 overlap
```

### Testing Search
```bash
# Web interface
http://localhost:5000

# API endpoint (with chat history)
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Что такое нормочас?", "history": []}'

# Direct Telegram bot test
# Use @VectorStom_bot in Telegram
```

### Database Management
```bash
# Backup SQLite database
docker exec docling-webapp sqlite3 /db/docling.db .dump > backup.sql

# Recreate database (WARNING: deletes all users)
rm shared/db/docling.db
docker compose restart webapp

# Backup Qdrant vectors
docker exec qdrant-docling qdrant-backup /qdrant/storage /backup
```

### Debugging
```bash
# Check Qdrant collection
curl http://localhost:6333/collections/documents

# Check Ollama models
curl http://localhost:11434/api/tags

# Test embeddings generation
docker exec ollama-docling ollama run nomic-embed-text "test query"
```

## Code Architecture Details

### Search Algorithm (webapp/app.py: search_documents)
Hybrid search with multi-stage ranking:

1. **Semantic Search** - Ollama nomic-embed-text (768-dim) через Qdrant
2. **Keyword Boosting** - упоминания документов в запросе:
   - "справочник" → boost +0.3 для "Справочник Мудрого Руководителя"
   - "золотой стандарт" → boost +0.3
   - "ссп" → boost +0.2 (аббревиатура)
3. **Definition Detection** - для вопросов "Что такое X?":
   - Поиск паттернов: `**Термин** =` или `**Термин (Аббр)** =`
   - Boost +0.5 для чанков с определениями
   - Keyword search по всей коллекции (scroll API)
4. **Formula Boosting** - для запросов о расчетах:
   - Поиск паттернов формул: `ВВ = Кзаг * НЧ * тр`
   - Boost +0.25 для чанков с формулами
   - Boost +0.2 за упоминание переменных (вв, кзаг, нч, тр)
5. **Size Boosting** - маленькие документы (<100 chunks) получают +0.05
6. **Score Threshold** - минимальный score 0.40 (если результатов мало - берутся топ N)

### Authentication System
- **Telegram users** (database.py: users table) - авторизация по telegram_id
- **Web users** (database.py: web_users table) - email/password с JWT токенами
- **Admin 2FA** - временные коды через email (auth_routes.py)

### Chat History Management
- **Web** - сохраняется в chat_sessions и chat_messages
- **Telegram** - хранится в памяти бота (handlers.py: user_histories)
- **Context window** - последние 3-5 пар вопрос-ответ передаются в LLM

### LLM Integration
- **DeepSeek** через Polza.ai API (OpenAI-compatible)
- **Context assembly**:
  1. System prompt с примерами ответов (examples_loader.py)
  2. История чата (последние 3 пары)
  3. Релевантные чанки из Qdrant (топ 5-10)
  4. Текущий вопрос
- **Suggestions** - LLM генерирует 3 follow-up вопроса в формате "Вопросы:\n1. ...\n2. ...\n3. ..."

## Configuration Files

### Environment Variables (.env.local)
```bash
# Critical for production
POLZA_API_KEY=xxx           # DeepSeek API access
TELEGRAM_BOT_TOKEN=xxx      # Telegram bot
FLASK_SECRET_KEY=xxx        # Session security
JWT_SECRET_KEY=xxx          # JWT tokens

# Optional (for web auth)
SMTP_HOST=smtp.gmail.com
SMTP_USER=xxx
SMTP_PASSWORD=xxx
```

### Docker Compose Structure
- **docker-compose.yml** - development (Flask debug mode, ports exposed)
- **docker-compose.prod.yml** - production (Gunicorn, Nginx, no debug)
- **docker-compose.simple-prod.yml** - minimal production (without Nginx)

## Important Conventions

### Error Handling
- Все ошибки логируются в stdout/stderr (видны через `docker logs`)
- API возвращает JSON с ключом "error" при ошибках
- Telegram bot отправляет пользователю дружественные сообщения об ошибках

### Database Schema Changes
При изменении схемы БД:
1. Обновить `database.py: init_db()`
2. Создать миграционный скрипт (если prod содержит данные)
3. Проверить индексы для новых полей

### Adding New Dependencies
1. Добавить в `webapp/requirements.txt` или `telegram_bot/requirements.txt`
2. Перезапустить контейнер: `docker compose restart webapp`
3. Или пересобрать: `docker compose build webapp`

### Frontend Changes (index.html, admin.html)
- Нет сборщиков - чистый HTML/CSS/JS
- Стили inline в `<style>` теге
- Цветовая палитра: `--primary-gold: #bfab8a` (GlobalDent branding)
- Используется Glassmorphism для header

### Testing Search Quality
Используйте тестовые скрипты:
- `webapp/test_search.py` - базовый поиск
- `webapp/test_normochas_search.py` - поиск определения "нормочас"
- `webapp/test_webapp_search.py` - тест с историей чата

## Known Issues & Quirks

### Qdrant Scroll Limitations
- Scroll API требует `offset` для полного охвата коллекции
- Лимит на один scroll: 10000 точек
- Для больших коллекций (>50k) нужно делать несколько scroll запросов

### Ollama Memory Usage
- nomic-embed-text занимает ~500MB RAM
- При падении Ollama - embeddings перестают создаваться
- Проверка: `curl http://localhost:11434/api/tags`

### SQLite Concurrency
- SQLite не поддерживает множественные писатели
- Для production с высокой нагрузкой - мигрировать на PostgreSQL
- Текущая схема совместима с PostgreSQL (нужно только изменить connection string)

### Telegram Bot Webhook vs Polling
- Сейчас используется polling (aiogram: `start_polling`)
- Для production - настроить webhook через ngrok или домен с SSL

## Production Checklist

Before deploying:
1. ✅ Set all environment variables in `.env.prod`
2. ✅ Remove old database: `rm shared/db/docling.db`
3. ✅ Disable Flask debug mode
4. ✅ Add Nginx rate limiting
5. ✅ Set up SSL certificates (Let's Encrypt)
6. ✅ Configure backup automation (Qdrant + SQLite)
7. ✅ Add monitoring (Prometheus + Grafana or similar)
8. ⚠️ Remove original documents from `/documents` folder after processing
9. ⚠️ Restrict Qdrant API access (only from webapp container)

## Contact & Support

- Web interface: http://localhost:5000
- Admin panel: http://localhost:5000/admin
- Telegram bot: @VectorStom_bot
- Qdrant dashboard: http://localhost:6333/dashboard

For issues, check logs:
```bash
docker logs docling-webapp
docker logs docling-telegram-bot
docker logs qdrant-docling
```
