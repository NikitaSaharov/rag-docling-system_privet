# VectorStom — Карта сервиса

> RAG-система для стоматологической практики. Поиск по документам с помощью AI.
> Обновлено: 01.03.2026

---

## Архитектура

```
┌─────────────────────────────────────────────────────────┐
│                      ИНТЕРНЕТ                           │
│                                                         │
│   Браузер ──→ :5000 ──→ [webapp]                        │
│   Telegram ─────────→ [telegram-bot] ──→ [webapp API]   │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────┼────────────────────────────────┐
│  Docker Network        │                                │
│                        ▼                                │
│  ┌──────────────────────────┐                           │
│  │  webapp (Flask)    :5000 │──→ Polza.ai (DeepSeek)    │
│  │  auth + admin + RAG      │                           │
│  │  + chat + API            │                           │
│  └──────┬───────┬───────────┘                           │
│         │       │                                       │
│         ▼       ▼                                       │
│  ┌──────────┐ ┌──────────┐  ┌──────────┐               │
│  │  Qdrant  │ │  Ollama  │  │  Docling  │               │
│  │  :6333   │ │  :11434  │  │ (спящий)  │               │
│  │ векторы  │ │ эмбеддинг│  │ PDF→MD    │               │
│  └──────────┘ └──────────┘  └───────────┘               │
│                                                         │
│  ┌──────────┐ ┌──────────┐                              │
│  │   n8n    │ │ Open     │  ← вспомогательные           │
│  │  :5678   │ │ WebUI    │                              │
│  │ workflow │ │  :3000   │                              │
│  └──────────┘ └──────────┘                              │
│                                                         │
│  [SQLite]  shared/db/docling.db  ← общая БД            │
└─────────────────────────────────────────────────────────┘
```

**Тип:** контейнеризованный модульный монолит (Docker Compose, 7 сервисов)

**Критичные сервисы** (нужны всегда):
- `webapp` — Flask, весь бэкенд + фронтенд
- `qdrant` — векторная БД, хранит эмбеддинги документов
- `DeepSeek API` — внешний LLM (через Polza.ai)

**Нужны при добавлении документов:**
- `ollama` — создание эмбеддингов (nomic-embed-text)
- `docling` — конвертация PDF/DOCX → Markdown

**Вспомогательные:**
- `n8n` — автоматизация (опционально)
- `open-webui` — альтернативный UI для LLM (опционально)

---

## Серверы и доступы

| Что | Где |
|-----|-----|
| **VPS сервер** | `root@5.129.194.184` (SSH ключ, без пароля) |
| **Проект на сервере** | `~/docling` (git clone) |
| **GitHub** | `github.com/NikitaSaharov/rag-docling-system_privet.git` (приватный) |
| **Веб-интерфейс** | `http://5.129.194.184:5000` |
| **Firewall** | Открыты: 22, 80, 443, 5000. Закрыты: 6333, 5678, 11434, 3000 |

---

## Структура файлов

```
проект/
├── manage.ps1              ← ГЛАВНЫЙ СКРИПТ (Windows)
├── manage.sh               ← ГЛАВНЫЙ СКРИПТ (сервер)
├── SERVICE_MAP.md          ← ЭТОТ ФАЙЛ
│
├── docker-compose.yml      ← основной compose (локальная разработка)
├── docker-compose.prod.yml ← production compose
├── .env.local              ← ВСЕ СЕКРЕТЫ (не в git!)
├── .env.prod               ← только POLZA_API_KEY (в git)
│
├── webapp/                 ← Flask приложение (ОСНОВНОЙ КОД)
│   ├── app.py              ← точка входа, маршруты
│   ├── database.py         ← все функции работы с SQLite
│   ├── auth_routes.py      ← регистрация, JWT, 2FA, email
│   ├── admin_routes.py     ← админ-панель, статистика
│   ├── requirements.txt    ← Python зависимости
│   └── templates/
│       ├── index.html      ← главная страница (чат)
│       └── admin.html      ← админ-панель
│
├── telegram_bot/           ← Telegram бот
│   ├── bot.py              ← основной код бота
│   └── Dockerfile          ← сборка контейнера
│
├── docling_app/            ← обработка документов
│   ├── process_documents.py   ← PDF/DOCX → Markdown
│   ├── create_embeddings.py   ← Markdown → векторы в Qdrant
│   └── search.py              ← поисковый движок
│
├── shared/                 ← общие данные между контейнерами
│   ├── db/docling.db       ← SQLite база данных
│   └── processed/          ← обработанные .md файлы
│
├── documents/              ← исходные документы (PDF, DOCX)
├── backups/                ← локальные бэкапы
├── nginx/                  ← конфиг Nginx
├── scripts/                ← старые скрипты (legacy)
└── docs/                   ← старая документация (legacy)
```

---

## Переменные окружения (.env.local)

Файл `.env.local` содержит ВСЕ секреты. **Не коммитится в git.**

```bash
# API для LLM (DeepSeek через Polza.ai)
POLZA_API_KEY=ak_...

# Telegram бот
TELEGRAM_BOT_TOKEN=8321374467:AAF...

# Email (отправка кодов верификации)
SMTP_HOST=smtp.mail.ru
SMTP_PORT=587
SMTP_USER=vectordirector@mail.ru
SMTP_PASSWORD=...
FROM_EMAIL=vectordirector@mail.ru
FROM_NAME=VectorStom RAG System

# Админ-панель
ADMIN_USERNAME=admin_vector
ADMIN_PASSWORD=...

# JWT и Flask
JWT_SECRET_KEY=...
FLASK_SECRET_KEY=...

# Yandex AI (эмбеддинги, альтернатива Ollama)
YANDEX_API_KEY=...
YANDEX_FOLDER_ID=...

# Пути (стандартные, менять не нужно)
DB_PATH=/db/docling.db
FLASK_API_URL=http://webapp:5000
```

---

## Команды управления

### На своём компьютере (PowerShell)

```powershell
# Статус
.\manage.ps1 status

# Запуск / остановка
.\manage.ps1 start
.\manage.ps1 stop

# Перезапуск одного сервиса
.\manage.ps1 restart webapp

# Логи
.\manage.ps1 logs webapp
.\manage.ps1 logs telegram

# Деплой на сервер (git push → SSH → pull → rebuild)
.\manage.ps1 deploy

# Быстрый деплой (только webapp + telegram, без rebuild)
.\manage.ps1 deploy-quick

# Статус сервера
.\manage.ps1 server-status

# Скачать бэкап с сервера
.\manage.ps1 backup

# Подключиться к серверу
.\manage.ps1 ssh

# Добавить документ
.\manage.ps1 add-doc C:\path\to\file.pdf
```

### На сервере (SSH → bash)

```bash
# Статус
./manage.sh status

# Обновить с GitHub + пересобрать
./manage.sh update

# Быстрое обновление (только рестарт webapp)
./manage.sh update-quick

# Перезапуск
./manage.sh restart webapp

# Логи
./manage.sh logs webapp

# Бэкап
./manage.sh backup

# Список бэкапов
./manage.sh backups

# Восстановить из бэкапа
./manage.sh restore 2026-03-01_10-30
```

---

## Процесс деплоя

### Обычный деплой (с компьютера)

```
1. Редактируешь код локально
2. .\manage.ps1 deploy
   → git add + commit + push
   → SSH на сервер
   → git pull + docker-compose up -d --build
3. .\manage.ps1 server-status  ← проверяем
```

### Быстрый деплой (без пересборки контейнеров)

```
Используй когда менял ТОЛЬКО код в webapp/ или telegram_bot/
(не трогал requirements.txt, Dockerfile, docker-compose.yml)

.\manage.ps1 deploy-quick
   → git push + на сервере: git pull + restart webapp telegram-bot
```

### Ручной деплой (через SSH)

```bash
ssh root@5.129.194.184
cd ~/docling
git pull origin main
docker-compose up -d --build   # полная пересборка
# или
docker-compose restart webapp  # только рестарт
```

---

## Бэкапы

### Что нужно бэкапить
1. **`shared/db/docling.db`** — вся база (пользователи, чаты, логи)
2. **`.env.local`** — все секреты
3. **Qdrant** — векторные данные (снэпшоты через API)

### Как делать бэкап
```powershell
# С компьютера — скачает БД + .env.local + создаст снэпшот Qdrant
.\manage.ps1 backup
# Сохранит в: backups/2026-03-01_10-30/

# На сервере
./manage.sh backup
# Сохранит в: ~/backups/2026-03-01_10-30/
```

### Восстановление (на сервере)
```bash
./manage.sh backups              # список бэкапов
./manage.sh restore 2026-03-01_10-30  # восстановить
```

---

## Решение проблем

### WebApp не отвечает
```bash
# Проверить логи
docker logs docling-webapp --tail 50

# Перезапустить
docker restart docling-webapp

# Проверить что порт слушается
curl http://localhost:5000
```

### Telegram бот не работает
```bash
docker logs docling-telegram-bot --tail 50
docker restart docling-telegram-bot
```

### Qdrant не отвечает
```bash
docker logs qdrant-docling --tail 20
docker restart qdrant-docling

# Проверить коллекции
curl http://localhost:6333/collections
```

### Нет места на диске
```bash
# Проверить
df -h /

# Почистить Docker (неиспользуемые образы)
docker system prune -f

# Почистить логи Docker (могут занимать гигабайты)
truncate -s 0 /var/lib/docker/containers/*/*-json.log
```

### После деплоя всё сломалось
```bash
# 1. Посмотреть что именно сломалось
./manage.sh status
docker logs docling-webapp --tail 100

# 2. Откатить код
cd ~/docling
git log --oneline -5        # найти предыдущий коммит
git checkout <commit_hash>  # откатиться

# 3. Пересобрать
docker-compose up -d --build

# 4. Или восстановить БД из бэкапа
./manage.sh restore 2026-03-01_10-30
```

### Забыл пароль от админки
Пароль в `.env.local` → переменная `ADMIN_PASSWORD`. Поменять и перезапустить webapp.

---

## База данных

**Тип:** SQLite, путь: `shared/db/docling.db`

**Таблицы:**
- `users` — Telegram пользователи (phone, telegram_id)
- `web_users` — Web пользователи (email, password_hash, JWT)
- `chat_sessions` — сессии диалогов
- `chat_messages` — сообщения в диалогах
- `query_logs` — логи запросов (для Telegram)
- `access_requests` — заявки на доступ к боту

**Посмотреть БД:**
```bash
# На сервере
sqlite3 ~/docling/shared/db/docling.db

# Полезные запросы
.tables                              -- список таблиц
SELECT COUNT(*) FROM web_users;      -- кол-во web пользователей
SELECT COUNT(*) FROM users;          -- кол-во telegram пользователей
SELECT * FROM access_requests WHERE status='pending';  -- ожидающие заявки
```

---

## API Endpoints (основные)

**Аутентификация:**
- `POST /api/auth/register` — регистрация
- `POST /api/auth/login` — вход
- `POST /api/auth/verify-email` — подтверждение email
- `GET /api/auth/me` — текущий пользователь

**Чат:**
- `GET /api/chat/sessions` — список диалогов
- `POST /api/chat/sessions` — новый диалог
- `DELETE /api/chat/sessions/:id` — удалить диалог

**Поиск (RAG):**
- `POST /api/search` — поиск с генерацией ответа (требует JWT)

**Админка:**
- `GET /api/admin/stats` — статистика
- `GET /api/admin/users` — список пользователей
- `POST /api/admin/access-requests/:id/approve` — одобрить заявку

**Telegram:**
- `POST /api/telegram/search` — поиск для бота
- `POST /api/telegram/check_auth` — проверка авторизации
