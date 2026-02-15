# Архитектура проекта RAG Docling System

## Содержание
1. [Технологический стек](#технологический-стек)
2. [Структура базы данных](#структура-базы-данных)
3. [Ключевые функции](#ключевые-функции)
4. [Архитектура системы](#архитектура-системы)
5. [Workflow процессы](#workflow-процессы)

---

## Технологический стек

### Backend

#### Python Stack
- **Flask** - веб-фреймворк для создания REST API и веб-приложения
- **PyJWT** - работа с JWT токенами для аутентификации
- **bcrypt** - хеширование паролей пользователей
- **requests** - HTTP-клиент для запросов к внешним API

#### AI/ML & Embeddings
- **Docling** - конвертация документов (PDF, DOCX, PPTX) в Markdown с сохранением структуры
- **Ollama** - локальный запуск LLM моделей (llama3.2) и создание эмбеддингов (nomic-embed-text)
- **DeepSeek API (через Polza.ai)** - основная LLM для генерации ответов

#### Векторная БД и поиск
- **Qdrant** - векторная база данных для хранения эмбеддингов документов и семантического поиска
- **SQLite** - реляционная БД для хранения пользователей, сессий чатов, истории сообщений

#### Email
- **SMTP (Yandex)** - отправка верификационных кодов и уведомлений

---

### Frontend

#### Core
- **HTML5/CSS3** - структура и стилизация
- **Vanilla JavaScript** - интерактивность без фреймворков
- **Google Fonts (Open Sans)** - типографика

#### Design
- **Glassmorphism** - современный UI эффект размытия
- **Responsive Design** - адаптация под мобильные устройства
- **Burger Menu** - мобильная навигация

---

### DevOps & Infrastructure

#### Containerization
- **Docker** - контейнеризация всех сервисов
- **Docker Compose** - оркестрация multi-container приложения

#### Контейнеры в проекте:
- `docling-docling` - сервис обработки документов
- `qdrant-docling` - векторная БД
- `ollama-docling` - локальный LLM сервер
- `docling-webapp` - Flask веб-приложение
- `docling-telegram-bot` - Telegram бот
- `n8n-docling` - автоматизация workflow
- `open-webui` - альтернативный веб-интерфейс

---

### Telegram Bot

- **aiogram** - асинхронный фреймворк для Telegram ботов
- **aiohttp** - асинхронные HTTP-запросы

---

### Automation & Workflow

- **n8n** - no-code платформа для автоматизации и интеграций
- **Open WebUI** - альтернативный интерфейс для работы с LLM

---

### Version Control

- **Git** - система контроля версий
- **GitHub** - хостинг репозитория

---

## Структура базы данных

### База данных: SQLite

Путь к БД: `/db/docling.db` внутри Docker контейнера

---

### Таблицы

#### 1. users (Telegram пользователи)

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone_number TEXT UNIQUE NOT NULL,
    telegram_id INTEGER UNIQUE,
    username TEXT,
    is_active INTEGER DEFAULT 1,
    user_type TEXT DEFAULT 'telegram',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Назначение**: Хранение пользователей Telegram бота

**Особенности**:
- Номер телефона - основной идентификатор
- `telegram_id` привязывается позже (после первого входа)
- Поддержка деактивации через `is_active`

---

#### 2. web_users (Web пользователи)

```sql
CREATE TABLE web_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    username TEXT,
    is_active INTEGER DEFAULT 0,
    is_verified INTEGER DEFAULT 0,
    verification_code TEXT,
    verification_code_expires_at TIMESTAMP,
    two_fa_code TEXT,
    two_fa_code_expires_at TIMESTAMP,
    reset_code TEXT,
    reset_code_expires_at TIMESTAMP,
    user_type TEXT DEFAULT 'web',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Назначение**: Хранение пользователей веб-интерфейса

**Особенности**:
- Email как идентификатор
- Пароль хешируется через bcrypt
- Обязательная верификация email (`is_verified`)
- Временные коды с expiration для безопасности
- Отдельная 2FA для доступа к админ-панели

**Коды безопасности**:
- `verification_code` - 6-значный код для подтверждения email
- `two_fa_code` - код для доступа к админ-панели
- `reset_code` - код для восстановления пароля
- Все коды имеют срок действия (expires_at)

---

#### 3. chat_sessions (Сессии чатов)

```sql
CREATE TABLE chat_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    user_type TEXT NOT NULL,
    title TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES web_users(id)
);
```

**Назначение**: Хранение диалогов пользователей

**Особенности**:
- Поддержка обоих типов пользователей (`web` / `telegram`)
- `user_type` определяет, из какой таблицы брать пользователя
- Автоматическое название: "Новый чат DD.MM.YYYY HH:MM"
- `updated_at` обновляется при каждом новом сообщении

---

#### 4. chat_messages (Сообщения в чатах)

```sql
CREATE TABLE chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
);
```

**Назначение**: Хранение всех сообщений в диалогах

**Особенности**:
- `role`: `'user'` (вопрос пользователя) или `'assistant'` (ответ LLM)
- CASCADE удаление: при удалении сессии удаляются все сообщения
- Хронологический порядок через `created_at`

---

#### 5. query_logs (Логи запросов)

```sql
CREATE TABLE query_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    query TEXT NOT NULL,
    answer TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

**Назначение**: Логирование всех запросов к системе (для Telegram)

---

#### 6. access_requests (Запросы на доступ)

```sql
CREATE TABLE access_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone_number TEXT NOT NULL,
    telegram_id INTEGER NOT NULL,
    username TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP,
    processed_by TEXT
);
```

**Назначение**: Управление запросами на доступ для Telegram бота

**Статусы**:
- `pending` - ожидает рассмотрения
- `approved` - одобрено
- `rejected` - отклонено

**Workflow**:
1. Пользователь отправляет номер телефона
2. Создается запрос со статусом `'pending'`
3. Админ одобряет/отклоняет через админ-панель
4. При одобрении создается пользователь + отправляется уведомление

---

### Индексы для оптимизации

```sql
CREATE INDEX idx_users_telegram_id ON users(telegram_id);
CREATE INDEX idx_users_phone ON users(phone_number);
CREATE INDEX idx_users_type ON users(user_type);
CREATE INDEX idx_web_users_email ON web_users(email);
CREATE INDEX idx_web_users_type ON web_users(user_type);
CREATE INDEX idx_chat_sessions_user ON chat_sessions(user_id, user_type);
CREATE INDEX idx_chat_messages_session ON chat_messages(session_id);
CREATE INDEX idx_query_logs_user_id ON query_logs(user_id);
CREATE INDEX idx_query_logs_timestamp ON query_logs(timestamp);
CREATE INDEX idx_access_requests_status ON access_requests(status);
CREATE INDEX idx_access_requests_telegram_id ON access_requests(telegram_id);
```

---

## Ключевые функции

### Управление пользователями (Web)

#### Регистрация и аутентификация

```python
add_web_user(email, password_hash, username=None)
```
Создает нового web-пользователя с хешированным паролем.

```python
get_web_user_by_email(email)
```
Поиск пользователя по email для авторизации.

```python
get_web_user_by_id(user_id)
```
Получение пользователя по ID (для JWT токенов).

---

#### Верификация email

```python
set_verification_code(user_id, code, expires_at)
```
Устанавливает 6-значный код верификации с временем истечения.

```python
verify_user(user_id, code)
```
Проверяет код и активирует пользователя:
- `is_verified = 1`
- `is_active = 1`
- Очищает код верификации

---

#### Восстановление пароля

```python
set_password_reset_code(user_id, code, expires_at)
```
Генерирует код восстановления пароля.

```python
verify_reset_code(email, code)
```
Проверяет код восстановления и срок действия.

```python
update_password(user_id, password_hash)
```
Обновляет пароль и очищает reset_code.

---

#### 2FA для админ-панели

```python
set_two_fa_code(user_id, code, expires_at)
```
Генерирует код 2FA для доступа к админке.

```python
verify_two_fa_code(user_id, code)
```
Проверяет код и автоматически очищает его после успешной проверки.

---

### Управление чатами

#### Сессии

```python
create_chat_session(user_id, user_type, title=None)
```
Создает новую сессию чата с автоматическим названием.

**Пример**:
```python
session_id = create_chat_session(
    user_id=42, 
    user_type='web', 
    title='Вопросы о нормочасе'
)
```

```python
get_user_chat_sessions(user_id, user_type, limit=50)
```
Получает список всех диалогов пользователя, отсортированных по времени обновления.

```python
update_chat_session(session_id, title)
```
Переименовывает сессию чата.

```python
delete_chat_session(session_id)
```
Удаляет сессию и все связанные сообщения (CASCADE).

---

#### Сообщения

```python
add_chat_message(session_id, role, content)
```
Добавляет сообщение в чат и обновляет `updated_at` сессии.

**Параметры**:
- `role`: `'user'` или `'assistant'`
- `content`: текст сообщения

```python
get_chat_messages(session_id, limit=100)
```
Получает историю сообщений сессии в хронологическом порядке.

---

### Управление пользователями (Telegram)

```python
add_user(phone_number, telegram_id=None, username=None)
```
Создает Telegram пользователя. `telegram_id` может быть привязан позже.

```python
get_user_by_telegram_id(telegram_id)
```
Поиск активного пользователя по Telegram ID.

```python
update_user_telegram_id(phone_number, telegram_id, username=None)
```
Привязывает Telegram ID к существующему пользователю по номеру телефона.

```python
deactivate_user(user_id)
```
Деактивирует пользователя (soft delete).

```python
delete_user(user_id)
```
Полностью удаляет пользователя и его логи (hard delete).

---

### Запросы на доступ

```python
create_access_request(phone_number, telegram_id, username=None)
```
Создает запрос на доступ для Telegram бота.

```python
get_pending_access_requests()
```
Получает список всех ожидающих запросов для админ-панели.

```python
approve_access_request(request_id, admin_username='admin')
```
Одобряет запрос:
1. Создает/обновляет пользователя
2. Меняет статус на `'approved'`
3. Возвращает данные для отправки уведомления

```python
reject_access_request(request_id, admin_username='admin')
```
Отклоняет запрос и возвращает данные пользователя для уведомления.

---

### Логирование и статистика

```python
log_query(user_id, query, answer)
```
Логирует запрос пользователя (legacy, для Telegram).

```python
get_query_logs(user_id=None, limit=50, offset=0)
```
Получает логи запросов с пагинацией.

```python
get_stats()
```
Возвращает статистику системы:
- `total_users` - всего активных пользователей
- `active_users` - пользователи, делавшие запросы за неделю
- `queries_today` - запросов сегодня
- `queries_week` - запросов за неделю
- `total_queries` - всего запросов

---

## Архитектура системы

### RAG (Retrieval-Augmented Generation)

#### Компоненты RAG pipeline

1. **Document Processing**
   - Конвертация через Docling (PDF/DOCX/PPTX → Markdown)
   - Chunking с overlap (350 слов, overlap 70)
   - Сохранение metadata (filename, chunk_index, total_chunks)

2. **Embedding Creation**
   - Модель: `nomic-embed-text` через Ollama
   - Размерность векторов: 768
   - Хранение в Qdrant

3. **Hybrid Search**
   - **Semantic search**: векторный поиск в Qdrant
   - **Keyword matching**: текстовый поиск по ключевым словам
   - **Re-ranking**: бустинг по релевантности документа
   - **Context expansion**: добавление соседних чанков для формул

4. **Answer Generation**
   - LLM: DeepSeek через Polza.ai API
   - Temperature: 0.0 (для точности формул)
   - Max tokens: 4000
   - Few-shot learning с примерами

---

### Аутентификация и безопасность

#### JWT Authentication
- Stateless аутентификация
- Токены с ограниченным сроком жизни
- Bearer token в заголовке Authorization

#### Пароли
- Хеширование: bcrypt
- Salt: автоматически генерируется bcrypt
- Минимальная длина: 6 символов

#### Коды верификации
- Длина: 6 цифр
- Генерация: случайные числа
- Срок действия: 15 минут
- Автоматическая очистка после использования

---

### API Endpoints

#### Аутентификация
- `POST /api/auth/register` - регистрация
- `POST /api/auth/login` - вход
- `POST /api/auth/verify-email` - верификация email
- `POST /api/auth/resend-verification` - повторная отправка кода
- `POST /api/auth/forgot-password` - запрос на восстановление пароля
- `POST /api/auth/verify-reset-code` - проверка кода восстановления
- `POST /api/auth/reset-password` - сброс пароля
- `GET /api/auth/me` - информация о текущем пользователе

#### Чаты
- `GET /api/chat/sessions` - список диалогов
- `POST /api/chat/sessions` - создание диалога
- `GET /api/chat/sessions/:id` - сообщения диалога
- `PATCH /api/chat/sessions/:id` - переименование диалога
- `DELETE /api/chat/sessions/:id` - удаление диалога

#### Поиск
- `POST /api/search` - RAG поиск с историей чата

#### Telegram
- `POST /api/telegram/check_auth` - проверка авторизации
- `POST /api/telegram/link_phone` - привязка номера телефона
- `POST /api/telegram/search` - поиск для бота

#### Админ-панель
- `GET /api/admin/stats` - статистика системы
- `GET /api/admin/users` - список пользователей
- `GET /api/admin/access-requests` - запросы на доступ
- `POST /api/admin/access-requests` - создание запроса
- `POST /api/admin/access-requests/:id/approve` - одобрение
- `POST /api/admin/access-requests/:id/reject` - отклонение
- `POST /api/admin/2fa/send` - отправка 2FA кода
- `POST /api/admin/2fa/verify` - проверка 2FA кода

---

## Workflow процессы

### Регистрация и вход (Web)

#### Регистрация нового пользователя

```
1. Пользователь → POST /api/auth/register
   ├─ email, password, username
   └─ password → bcrypt.hashpw()

2. Создание записи в web_users
   ├─ is_verified = 0
   └─ is_active = 0

3. Генерация verification_code
   ├─ 6-значное случайное число
   └─ expires_at = now() + 15 минут

4. Отправка email через SMTP (Yandex)
   └─ Тема: "Код верификации VectorStom"

5. Ответ клиенту
   └─ {"success": true, "user_id": 42}
```

#### Верификация email

```
1. Пользователь вводит код → POST /api/auth/verify-email
   └─ user_id, code

2. Проверка кода и срока действия
   ├─ verification_code == code
   └─ verification_code_expires_at > now()

3. Активация пользователя
   ├─ is_verified = 1
   ├─ is_active = 1
   └─ verification_code = NULL

4. Генерация JWT токена
   └─ Payload: {user_id, email, exp}

5. Ответ клиенту
   └─ {"success": true, "token": "...", "user": {...}}
```

#### Вход в систему

```
1. Пользователь → POST /api/auth/login
   └─ email, password

2. Поиск пользователя
   └─ get_web_user_by_email(email)

3. Проверка пароля
   └─ bcrypt.checkpw(password, user['password_hash'])

4. Проверка is_verified
   ├─ Если false → отправка нового кода
   └─ Если true → генерация JWT

5. Ответ клиенту
   └─ {"success": true, "token": "...", "user": {...}}
```

---

### Восстановление пароля

```
1. Запрос кода → POST /api/auth/forgot-password
   └─ email

2. Генерация reset_code
   ├─ 6-значное число
   └─ expires_at = now() + 15 минут

3. Отправка email
   └─ "Код восстановления: 123456"

4. Проверка кода → POST /api/auth/verify-reset-code
   └─ email, code

5. Установка нового пароля → POST /api/auth/reset-password
   ├─ email, code, new_password
   ├─ password_hash = bcrypt.hashpw()
   └─ reset_code = NULL
```

---

### Создание и использование чата

#### Первый запрос (создание сессии)

```
1. Пользователь отправляет вопрос
   └─ POST /api/search
   └─ {query: "Что такое нормочас?", session_id: null}

2. Проверка авторизации (JWT)
   └─ Декодирование токена → user_id

3. Создание новой сессии
   └─ session_id = create_chat_session(user_id, 'web')
   └─ title = "Новый чат 07.02.2026 10:24"

4. RAG поиск
   ├─ Создание эмбеддинга запроса
   ├─ Semantic search в Qdrant
   ├─ Re-ranking + context expansion
   └─ Генерация ответа через DeepSeek

5. Сохранение сообщений
   ├─ add_chat_message(session_id, 'user', query)
   └─ add_chat_message(session_id, 'assistant', answer)

6. Ответ клиенту
   └─ {
       "answer": "...",
       "sources": [...],
       "session_id": 42
     }
```

#### Продолжение диалога

```
1. Пользователь отправляет следующий вопрос
   └─ POST /api/search
   └─ {query: "А какая норма?", session_id: 42}

2. Загрузка истории чата
   └─ messages = get_chat_messages(session_id=42)
   └─ Последние 5 пар (user/assistant)

3. RAG с учетом контекста
   └─ Контекст из истории + новый поиск

4. Сохранение новых сообщений
   └─ Обновление updated_at сессии

5. Ответ клиенту
```

---

### Telegram бот workflow

#### Запрос доступа

```
1. Пользователь → /start в боте

2. Проверка авторизации
   └─ POST /api/telegram/check_auth
   └─ {telegram_id: 123456}

3. Если не авторизован
   ├─ Запрос номера телефона (кнопка в боте)
   └─ contact.phone_number

4. Привязка телефона
   └─ POST /api/telegram/link_phone
   └─ {phone_number, telegram_id, username}

5. Поиск пользователя по номеру
   ├─ Если найден → update_user_telegram_id()
   └─ Если не найден → create_access_request()

6. Если создан access_request
   └─ Уведомление админу в Telegram
   └─ "Новый запрос на доступ от @username"
```

#### Одобрение доступа админом

```
1. Админ в админ-панели
   └─ POST /api/admin/access-requests/:id/approve

2. Создание пользователя
   └─ add_user(phone_number, telegram_id, username)

3. Изменение статуса запроса
   └─ status = 'approved'

4. Уведомление пользователя в Telegram
   └─ "✅ Доступ предоставлен! Можете пользоваться ботом."
```

#### Отправка запроса в боте

```
1. Пользователь отправляет текст в бота

2. Бот → POST /api/telegram/search
   └─ {telegram_id, query, history}

3. Проверка авторизации
   └─ get_user_by_telegram_id()

4. RAG поиск (аналогично Web)

5. Логирование
   └─ log_query(user_id, query, answer)

6. Ответ в Telegram
   └─ Текст ответа + кнопки suggestions
```

---

### RAG Pipeline детально

#### 1. Document Ingestion

```
1. Загрузка документа (PDF/DOCX/PPTX)
   └─ /api/admin/upload

2. Конвертация через Docling
   ├─ PDF → Markdown (с таблицами, формулами)
   ├─ DOCX → Markdown
   └─ PPTX → Markdown

3. Chunking
   ├─ Размер чанка: 350 слов
   ├─ Overlap: 70 слов
   └─ Сохранение metadata

4. Создание эмбеддингов
   └─ POST http://ollama:11434/api/embeddings
   └─ {model: "nomic-embed-text", prompt: chunk_text}

5. Загрузка в Qdrant
   └─ PUT /collections/documents/points
   └─ {
       id: hash(filename + chunk_idx),
       vector: embedding,
       payload: {
         text: chunk,
         filename: "Справочник.md",
         chunk_index: 5,
         total_chunks: 120
       }
     }
```

#### 2. Query Processing

```
1. Получение запроса пользователя
   └─ query = "Что такое нормочас терапевта?"

2. Создание эмбеддинга запроса
   └─ query_embedding = get_embedding(query)

3. Semantic Search в Qdrant
   └─ POST /collections/documents/points/search
   └─ {
       vector: query_embedding,
       limit: 10,
       with_payload: true
     }

4. Keyword Boost (если есть ключевые слова)
   ├─ "терапевт" → boost +0.3
   ├─ "нормочас" → boost +0.2
   └─ "справочник" → boost +0.3

5. Re-ranking
   └─ Сортировка по новому score

6. Context Expansion
   └─ Для каждого найденного чанка:
       ├─ Берем chunk_index - 1
       └─ Берем chunk_index + 1
```

#### 3. Answer Generation

```
1. Формирование контекста
   └─ context = "\n\n".join([chunk['text'] for chunk in top_results])

2. Загрузка few-shot примеров
   └─ examples = load_examples(max_examples=3)

3. Формирование промпта
   ├─ System prompt (правила ответа)
   ├─ Few-shot примеры
   ├─ Контекст из документов
   └─ Вопрос пользователя

4. Вызов LLM
   └─ POST https://api.polza.ai/v1/chat/completions
   └─ {
       model: "deepseek/deepseek-chat",
       messages: [
         {role: "system", content: system_prompt},
         {role: "user", content: user_prompt}
       ],
       temperature: 0.0,
       max_tokens: 4000
     }

5. Парсинг ответа
   ├─ Извлечение suggestions (секция "Вопросы:")
   └─ Формирование JSON с answer + sources + suggestions
```

---

## Преимущества архитектуры

### ✅ Разделение ответственности
- **Microservices**: каждый сервис в отдельном контейнере
- **Независимое масштабирование**: можно увеличить только нужные контейнеры
- **Изоляция сбоев**: падение одного сервиса не ломает систему

### ✅ Безопасность
- **Хеширование паролей**: bcrypt с автоматическим salt
- **JWT токены**: stateless аутентификация с expiration
- **Временные коды**: автоматическое истечение через 15 минут
- **2FA для админки**: дополнительная защита административных функций
- **Модерация доступа**: система одобрения для Telegram

### ✅ Масштабируемость
- **Индексы БД**: быстрый поиск по всем важным полям
- **Векторный поиск**: O(log n) через HNSW в Qdrant
- **Кеширование**: LRU кеш для эмбеддингов
- **Pagination**: для всех списков с большими данными

### ✅ Надежность
- **CASCADE удаление**: автоматическая очистка связанных данных
- **Foreign keys**: гарантия целостности данных
- **Транзакции**: атомарность сложных операций
- **Логирование**: полная история запросов

### ✅ User Experience
- **История диалогов**: продолжение с любого места
- **Multi-platform**: Web + Telegram с единой БД
- **Контекстные ответы**: учет истории чата
- **Suggestions**: умные предложения следующих вопросов
- **Responsive UI**: адаптация под все устройства

### ✅ Производительность
- **Hybrid search**: semantic + keyword = лучшая релевантность
- **Context expansion**: полный контекст для формул
- **Re-ranking**: дополнительная оптимизация результатов
- **Few-shot learning**: более точные ответы от LLM

---

## Технические детали

### Форматы данных

#### JWT Token Payload
```json
{
  "user_id": 42,
  "email": "user@example.com",
  "exp": 1707302400
}
```

#### Chat Message Format
```json
{
  "role": "user",
  "content": "Что такое нормочас?"
}
```

#### Search Response
```json
{
  "answer": "Нормочас доктора (НЧ) = ВВ доктора / количество часов...",
  "sources": [
    {
      "filename": "Справочник.md",
      "text": "Нормочас - это...",
      "score": 0.89,
      "chunk_index": 5,
      "total_chunks": 120
    }
  ],
  "session_id": 42
}
```

#### Qdrant Point Structure
```json
{
  "id": "a3c7f2e8...",
  "vector": [0.123, -0.456, ...],
  "payload": {
    "text": "Нормочас терапевта составляет 6500-9000 руб...",
    "filename": "Справочник Мудрого Руководителя.md",
    "chunk_index": 42,
    "total_chunks": 250
  }
}
```

---

## Environment Variables

```bash
# Database
DB_PATH=/db/docling.db

# API Keys
OPENROUTER_API_KEY=sk-...
POLZA_API_KEY=...

# LLM Settings
DEEPSEEK_MODEL=deepseek/deepseek-chat
OLLAMA_URL=http://ollama-docling:11434
QDRANT_URL=http://qdrant-docling:6333

# Email (SMTP)
SMTP_SERVER=smtp.yandex.ru
SMTP_PORT=587
SMTP_USERNAME=...
SMTP_PASSWORD=...

# Telegram
TELEGRAM_BOT_TOKEN=...
TELEGRAM_ADMIN_ID=...

# Flask
FLASK_SECRET_KEY=...
JWT_SECRET_KEY=...

# Services URLs
FLASK_API_URL=http://docling-webapp:5000
```

---

## Заключение

Данный проект представляет собой полноценную enterprise-grade RAG систему с:
- Multi-platform доступом (Web + Telegram)
- Продвинутой системой аутентификации и безопасности
- Гибридным поиском (semantic + keyword)
- Контекстно-зависимыми ответами
- Системой модерации доступа
- Полной историей диалогов
- Responsive UI с мобильной адаптацией

Архитектура спроектирована для масштабируемости, надежности и удобства использования.
