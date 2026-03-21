# Архитектура системы VectorStom RAG

> Последнее обновление: март 2026  
> Проект: ООО «Глобал Дент Университет» · ИНН 7453346120

---

## 1. Обзор системы

VectorStom — RAG-система (Retrieval-Augmented Generation) для ответов на вопросы по управлению стоматологической клиникой. Пользователь задаёт вопрос через веб-интерфейс или Telegram-бот, система ищет релевантные фрагменты в базе знаний и генерирует ответ с помощью LLM.

---

## 2. Инфраструктура

### Сервер
- **IP**: `5.129.194.184`
- **Пользователь**: `root`
- **Директория проекта**: `/root/docling/`
- **Деплой**: `docker-compose up -d --build` или `docker-compose restart webapp`

### Репозиторий
- **GitHub**: `NikitaSaharov/rag-docling-system_privet` (private)
- **Ветка**: `main`
- **Локальная копия**: `E:\СТОМПРАКТИКА ПРОЕКТЫ\Docling new service\`

### Docker Compose — сервисы
| Контейнер | Образ | Порт | Роль |
|---|---|---|---|
| `docling-webapp` | python:3.11-slim | 5000 | Flask/Gunicorn веб-приложение |
| `qdrant-docling` | qdrant/qdrant | 6333, 6334 | Векторная база данных |
| `ollama-docling` | ollama/ollama | 11434 | Локальная LLM (резерв) |
| `docling-docling` | python:3.11-slim | — | Обработка документов (Docling) |
| `docling-telegram-bot` | custom Dockerfile | — | Telegram-бот |
| `n8n-docling` | n8nio/n8n | 5678 | Автоматизация (n8n) |
| `open-webui` | open-webui | 3000 | UI для Ollama (резерв) |

### Тома (Volumes)
- `./webapp:/app` — код веб-приложения (монтируется напрямую, без Docker-образа)
- `./shared/db:/db` — **SQLite база данных** (персистентная, не теряется при рестарте)
- `./documents:/documents` — загруженные документы
- `./shared:/shared` — общие данные между сервисами

### Nginx
- Обратный прокси для `gdgbaza.ru`
- Конфиг: `nginx/gdgbaza.ru.conf`
- SSL через Let's Encrypt

---

## 3. Структура файлов

```
/root/docling/ (сервер) / E:\СТОМПРАКТИКА ПРОЕКТЫ\Docling new service\ (локально)
│
├── webapp/                      # Основное веб-приложение
│   ├── app.py                   # Flask app + весь pipeline RAG
│   ├── database.py              # SQLite: все операции с БД
│   ├── auth_routes.py           # Регистрация, вход, JWT, email-верификация
│   ├── admin_routes.py          # Админ-панель
│   ├── chat_routes.py           # Сессии чатов
│   ├── handlers.py              # Telegram handlers (используется ботом)
│   ├── examples_loader.py       # Загрузка few-shot примеров для LLM
│   ├── requirements.txt         # Python зависимости
│   ├── templates/
│   │   ├── index.html           # Главная страница (весь веб-чат)
│   │   └── doc_page.html        # Страница юридического документа
│   ├── static/
│   │   ├── auth.js              # JS: авторизация, модалки, popup
│   │   └── (другие статики)
│   └── docs_text/               # Юридические документы (.txt)
│       ├── Оферта Global Dent Университет.txt
│       ├── Политика обработки персональных данных.txt
│       ├── Согласие на ОПД .txt
│       └── Согласие на рассылку .txt
│
├── telegram_bot/                # Telegram-бот
│   ├── bot.py                   # Основной файл бота
│   └── Dockerfile
│
├── docling_app/                 # Обработка документов
│   └── (скрипты Docling)
│
├── documents/                   # Загруженные .pdf/.docx файлы
├── shared/
│   └── db/
│       └── docling.db           # SQLite БД (ПЕРСИСТЕНТНАЯ)
│
├── docker-compose.yml
├── nginx/gdgbaza.ru.conf
├── .env.local                   # API ключи и секреты
│
└── reextract.py                 # Скрипт переизвлечения .txt из .docx
```

---

## 4. База данных SQLite

**Путь**: `/db/docling.db` (внутри контейнера) = `/root/docling/shared/db/docling.db` (на сервере)

**Режим**: WAL (Write-Ahead Logging) — concurrent reads во время записи

### Таблицы

| Таблица | Содержимое |
|---|---|
| `web_users` | Зарегистрированные пользователи (email, хэш пароля, верификация) |
| `chat_sessions` | Сессии диалогов пользователей |
| `chat_messages` | Сообщения в сессиях |
| `users` | Telegram-пользователи (phone, telegram_id) |
| `query_logs` | Лог запросов |
| `access_requests` | Заявки на доступ (Telegram) |
| `answer_feedback` | Обратная связь (👍/👎) |

---

## 5. RAG Pipeline

```
Запрос пользователя
        │
        ▼
1C. rewrite_query_if_needed()
    — если запрос короткий (<7 слов) и есть история →
      DeepSeek разворачивает в полный поисковый запрос
        │
        ▼
1E. analyze_query_intent()
    — regex детектит отрицание ("не стоит", "нельзя", "как избежать")
    — если найдено → DeepSeek извлекает тему БЕЗ отрицания для поиска
        │
        ▼
1F. classify_and_enrich_query()
    — regex классифицирует тип запроса:
      • "расчёт/формула" → + "формула расчёт методика"
      • "стратегия/что делать" → + "методы рекомендации решение"
      • "сравнение/норма" → + "норматив норма целевое"
        │
        ▼
search_documents()
    — get_embedding() через Polza.ai API (baai/bge-m3, 1024 dim)
    — Qdrant cosine search (limit=50*3)
    — Re-ranking: boosting по должностям, определениям, размеру документа
    — best_raw_score трекинг (1D: если <0.65 — LLM предупреждается)
    — Расширение контекста: соседние чанки
        │
        ▼
ask_llm(original_query, context)
    — DeepSeek-chat через Polza.ai API
    — system_prompt: эксперт по стоматологическому менеджменту
    — few-shot примеры (examples_loader)
    — temperature=0.0
        │
        ▼
_clean_llm_response()
    — убирает ### ## # заголовки
    — убирает <b> <i> <em> HTML теги
    — убирает одиночные --- разделители
        │
        ▼
Ответ пользователю
```

---

## 6. Веб-приложение (app.py)

### Ключевые эндпоинты

| Метод | URL | Описание |
|---|---|---|
| GET | `/` | Главная страница чата |
| POST | `/api/search` | Основной RAG-поиск (JWT required) |
| POST | `/api/telegram/search` | Поиск для Telegram-бота |
| POST | `/api/feedback` | Фидбэк 👍/👎 |
| GET/POST | `/api/auth/*` | Регистрация, вход, верификация email |
| GET | `/docs/oferta` | Публичная оферта |
| GET | `/docs/privacy` | Политика конфиденциальности |
| GET | `/docs/consent-data` | Согласие на ОПД |
| GET | `/docs/consent-newsletter` | Согласие на рассылку |
| GET | `/health` | Health check |
| GET | `/api/stats` | Статистика Qdrant |

### Blueprints (отдельные модули)
- `admin_bp` (admin_routes.py) — Панель администратора
- `auth_bp` (auth_routes.py) — Авторизация (JWT, bcrypt, email-код)
- `chat_bp` (chat_routes.py) — Управление сессиями чатов

### CORS
- Разрешено только с `https://gdgbaza.ru` и `https://www.gdgbaza.ru`

### Rate Limiting (Flask-Limiter)
- `/api/auth/login` — 10/minute
- `/api/auth/register` — 5/hour
- `/api/auth/verify-email` — 10/minute
- `/api/auth/forgot-password` — 5/minute

---

## 7. Поисковый движок

### Векторная база
- **Qdrant** в Docker на порту 6333
- **Коллекция**: `Документы` (или из env `QDRANT_COLLECTION`)
- **Модель эмбеддингов**: `baai/bge-m3` через Polza.ai API
- **Размерность**: 1024
- **Метрика**: Cosine

### Чанкинг документов (semantic_chunk_text)
- Разбивка по заголовкам Markdown (`#`, `##`, `###`)
- Максимум 400 слов на чанк
- Минимум 40 слов (мелкие блоки объединяются)
- Метаданные чанка: `filename`, `chunk_index`, `total_chunks`, `section_title`

### Re-ranking (бустинг)
- +0.05 для маленьких документов (<100 чанков)
- +0.3 для чанков с описанием должностей (при запросах про должности)
- Сильный буст для чанков с определениями (при вопросах "что такое")
- 1D: `best_raw_score` трекинг — если cosine <0.65, LLM предупреждается о низкой релевантности

---

## 8. LLM и API

### DeepSeek через Polza.ai
- **URL**: `https://api.polza.ai/v1/chat/completions`
- **Модель**: `deepseek-chat`
- **Температура**: 0.0 (максимальная точность)
- **max_tokens**: 4000
- **Timeout**: 60 сек

### Эмбеддинги через Polza.ai
- **URL**: `https://api.polza.ai/v1/embeddings`
- **Модель**: `baai/bge-m3`
- **Размерность**: 1024

### Speech-to-Text через Polza.ai
- **URL**: `https://api.polza.ai/v1/audio/transcriptions`
- **Модель**: `openai/gpt-4o-mini-transcribe`
- **Язык**: `ru`

### Env переменные (.env.local)
```
POLZA_API_KEY=...
POLZA_STT_API_KEY=...
EMBEDDING_API_URL=https://api.polza.ai/v1
EMBEDDING_API_KEY=...
EMBEDDING_MODEL=baai/bge-m3
EMBEDDING_VECTOR_SIZE=1024
QDRANT_COLLECTION=Документы
FLASK_SECRET_KEY=...
DB_PATH=/db/docling.db
```

---

## 9. Авторизация

- **JWT** (PyJWT) — токен в localStorage браузера
- **Хэш пароля** — bcrypt
- **Email верификация** — 6-значный код, отправляется при регистрации
- **Восстановление пароля** — 6-значный код на email
- **Сессия**: 3 часа (PERMANENT_SESSION_LIFETIME)
- **Принудительный login popup** — неавторизованный пользователь не может закрыть модалку входа

---

## 10. Веб-интерфейс (index.html)

### Ключевые компоненты
- **Сайдбар** — список сессий чатов, вход/выход
- **Чат** — сообщения с markdown-рендерингом (таблицы, жирный, курсив)
- **Голосовой ввод** — Web Audio API + MediaRecorder → STT Polza.ai
- **Фидбэк** — 👍/👎 на каждом ответе ассистента
- **Suggestions** — 3 вопроса в конце каждого ответа для продолжения диалога

### Форматирование ответов (formatMessage в JS)
- `**текст**` → **жирный**
- `***текст***` → ***жирный курсив***
- Markdown таблицы → HTML таблицы в `.table-scroll-wrapper` (горизонтальный скролл внутри)
- `pre-wrap` для переносов строк

### Футер
- Десктоп: одна строка с названием компании и ссылками на документы
- Мобильный: сворачиваемый — по умолчанию только название, тап → ссылки

---

## 11. Юридические документы

Документы извлечены из .docx файлов скриптом `reextract.py` в `webapp/docs_text/`.

### Маршруты
- `/docs/oferta` → `Оферта Global Dent Университет.txt`
- `/docs/privacy` → `Политика обработки персональных данных.txt`
- `/docs/consent-data` → `Согласие на ОПД .txt`
- `/docs/consent-newsletter` → `Согласие на рассылку .txt`

### Переизвлечение
Если нужно обновить тексты документов:
```bash
# Локально (Windows)
python reextract.py
git add webapp/docs_text/
git commit -m "update: re-extract legal docs"
git push && ssh root@5.129.194.184 "cd /root/docling && git pull --rebase origin main && docker-compose restart webapp"
```

---

## 12. Telegram-бот

- Отдельный контейнер `docling-telegram-bot`
- Обращается к webapp через `http://webapp:5000/api/telegram/search`
- Использует ту же SQLite БД (`/db/docling.db`)
- Канал `telegram` в `ask_llm` — другой формат ответа (без таблиц, без **жирного**)

---

## 13. Производительность и надёжность

### Gunicorn (production WSGI)
```
gunicorn --workers 2 --threads 4 --worker-class gthread --timeout 120 --bind 0.0.0.0:5000 app:app
```
- 2 воркера × 4 потока = **8 параллельных запросов**
- timeout 120 сек (LLM вызовы до 60 сек)

### SQLite
- WAL mode: concurrent reads не блокируют writes
- `timeout=30`: при конкурентной записи ждёт 30 сек вместо падения
- `check_same_thread=False`: безопасно с per-request connections

---

## 14. Деплой

### Стандартный деплой
```bash
git add .
git commit -m "feat: ..."
git push origin main
ssh root@5.129.194.184 "cd /root/docling && git pull --rebase origin main && docker-compose restart webapp"
```

### Полный пересоздать контейнер (если менялся docker-compose.yml)
```bash
ssh root@5.129.194.184 "cd /root/docling && git pull --rebase origin main && docker-compose up -d --force-recreate webapp"
```

### Проверка логов
```bash
ssh root@5.129.194.184 "docker logs docling-webapp --tail 30"
```

### Проверка работоспособности
```bash
ssh root@5.129.194.184 "curl -s -o /dev/null -w '%{http_code}' http://localhost:5000/health"
```
