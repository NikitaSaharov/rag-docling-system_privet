# AI Context — Быстрый справочник для восстановления проекта

> Этот файл для AI-ассистента. Читай его первым если контекст потерян.

---

## Что это за проект

**VectorStom** — чат-бот с базой знаний для управления стоматологической клиникой.
- Компания: ООО «Глобал Дент Университет», ИНН 7453346120
- Домен: `gdgbaza.ru`
- Пользователи задают вопросы по управлению клиникой → система ищет в документах → DeepSeek генерирует ответ

---

## Где всё лежит

| Что | Где |
|---|---|
| Код (локально) | `E:\СТОМПРАКТИКА ПРОЕКТЫ\Docling new service\` |
| Git репо | `NikitaSaharov/rag-docling-system_privet` (private, ветка main) |
| Сервер | `root@5.129.194.184`, путь `/root/docling/` |
| БД (не трогать!) | `/root/docling/shared/db/docling.db` |
| Shell пользователя | PowerShell (Windows) — использовать `;` вместо `&&` |

---

## Стек технологий

### Backend
- **Python 3.11** + **Flask 3.0** + **Gunicorn 21** (gthread, 2w×4t)
- **SQLite** с WAL-режимом — пользователи, сессии, история чатов
- **Qdrant** — векторная БД (cosine, 1024 dim)

### LLM / AI
- **DeepSeek-chat** через **Polza.ai** API (`https://api.polza.ai/v1/chat/completions`)
- **baai/bge-m3** эмбеддинги через **Polza.ai** API
- **openai/gpt-4o-mini-transcribe** STT через **Polza.ai** API
- Ключи в `.env.local` на сервере: `POLZA_API_KEY`, `EMBEDDING_API_KEY`, `POLZA_STT_API_KEY`

### Frontend
- Чистый HTML/CSS/JS (без фреймворков) в `webapp/templates/index.html`
- `webapp/static/auth.js` — авторизация, JWT, модалки

### Инфраструктура
- **Docker Compose** — все сервисы в контейнерах
- **Nginx** — reverse proxy + SSL для gdgbaza.ru
- Webapp монтируется как volume (`./webapp:/app`), не копируется в образ

---

## Ключевые файлы

| Файл | Зачем |
|---|---|
| `webapp/app.py` | Весь RAG pipeline, все маршруты Flask |
| `webapp/database.py` | SQLite операции, `get_connection()` |
| `webapp/auth_routes.py` | JWT, bcrypt, email верификация |
| `webapp/static/auth.js` | Login/register popups, authRequired логика |
| `webapp/templates/index.html` | Весь веб-интерфейс (5000+ строк) |
| `webapp/templates/doc_page.html` | Страницы юридических документов |
| `webapp/docs_text/*.txt` | Извлечённые тексты документов |
| `docker-compose.yml` | Все сервисы, порты, volumes |
| `reextract.py` | Переизвлечь .txt из .docx (`python reextract.py`) |

---

## Деплой (самое важное)

webapp монтируется как том — **образ НЕ пересобирается** при деплое:
```
git push origin main
ssh root@5.129.194.184 "cd /root/docling && git pull --rebase origin main && docker-compose restart webapp"
```

Если менялся `docker-compose.yml` — нужен `--force-recreate`:
```
ssh root@5.129.194.184 "cd /root/docling && git pull --rebase origin main && docker-compose up -d --force-recreate webapp"
```

---

## RAG Pipeline (кратко)

```
query → rewrite (1C) → intent (1E) → enrich (1F)
      → Qdrant search + re-ranking
      → ask_llm (DeepSeek, temp=0)
      → _clean_llm_response (убрать ###, <b>, ---)
      → ответ
```

Все функции в `webapp/app.py`. Pipeline вызывается в `/api/search` и `/api/telegram/search`.

---

## Авторизация

- JWT в `localStorage` браузера
- При загрузке страницы без токена → сразу показывается `loginModal`, закрыть нельзя
- `authRequired` флаг в `auth.js` управляет этим поведением
- После успешного входа: `showAuthenticatedUI()` → `authRequired=false` → `closeAllModals()`

---

## SQLite — осторожно

БД на хосте в `./shared/db/docling.db`. Монтируется в контейнер как `/db/docling.db`.
**Никогда не удалять этот файл** — там все пользователи.
Резервная копия: `/root/docling/shared/db/docling.db.backup_20260201_174955`

---

## Юридические документы

4 маршрута: `/docs/oferta`, `/docs/privacy`, `/docs/consent-data`, `/docs/consent-newsletter`
Тексты в `webapp/docs_text/` извлечены скриптом `reextract.py` из .docx файлов.
Если надо обновить — запустить `python reextract.py` и задеплоить.

---

## Типичные проблемы и решения

| Проблема | Решение |
|---|---|
| 404 на новых маршрутах | `docker-compose restart webapp` (подхватит новый app.py) |
| "No services to build" | Нормально — webapp это volume, не образ |
| LLM выдаёт `###` в ответе | `_clean_llm_response()` в app.py должна их убирать |
| SQLite "database is locked" | WAL mode + timeout=30 должны решать; если нет — проверить `get_connection()` |
| Пути с кириллицей в PowerShell | Использовать относительные пути `.\file.py` или скрипт-файл |

---

## Что реализовано (история фаз)

- **1A** — semantic_chunk_text() по заголовкам Markdown
- **1C** — rewrite_query_if_needed() — разворот коротких follow-up запросов
- **1E** — analyze_query_intent() — обработка отрицаний в запросе
- **1F** — classify_and_enrich_query() — дополнение запроса тематическими якорями
- **1D** — best_raw_score трекинг, предупреждение LLM при низкой релевантности
- **4A** — фидбэк 👍/👎 (веб + Telegram), таблица `answer_feedback` в БД
- **Footer** — юридические документы + сворачиваемый мобильный футер
- **Auth** — JWT, email верификация, принудительный login popup
- **Gunicorn** — production WSGI вместо dev server
- **Mobile fixes** — overflow-x, min-width:0, table scroll wrapper
