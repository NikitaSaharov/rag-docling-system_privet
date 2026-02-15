# Инструкция по настройке системы авторизации

## Что реализовано

### Backend ✅
1. **Восстановление пароля** (`database.py`, `auth_routes.py`, `email_service.py`)
   - `/api/auth/forgot-password` - запрос кода восстановления
   - `/api/auth/verify-reset-code` - проверка кода
   - `/api/auth/reset-password` - установка нового пароля

2. **История чатов** (`chat_routes.py`, `app.py`)
   - Создана таблица `chat_sessions` и `chat_messages`
   - API для работы с сессиями: GET/POST/PATCH/DELETE `/api/chat/sessions`
   - `/api/search` теперь требует JWT и сохраняет диалоги автоматически

3. **Админ-панель** (`admin_routes.py`)
   - `/api/admin/web-users` - список web-пользователей
   - `/api/admin/web-users/<id>/sessions` - сессии пользователя
   - `/api/admin/web-users/<id>/toggle-active` - активация/деактивация

### Frontend ✅
1. **Авторизация** (`index.html`, `auth.js`)
   - Pop-up окна: вход, регистрация, верификация email, восстановление пароля
   - JWT токены в localStorage
   - Автоматическая проверка авторизации при загрузке

2. **Боковая панель с историей** (`index.html`, `auth.js`)
   - Отображение email пользователя
   - Список всех диалогов
   - Кнопки: новый чат, переименовать, удалить
   - Загрузка истории сообщений

3. **Админ-панель** (`admin.html`, `admin-web-users.js`)
   - Вкладка "Web Пользователи"
   - Просмотр всех пользователей, их статуса и диалогов
   - Активация/деактивация пользователей

## Настройка

### 1. Переменные окружения
Добавьте в `.env.local` и `.env.prod`:

```bash
# Email settings для отправки кодов
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password  # Не обычный пароль, а App Password!
FROM_EMAIL=your-email@gmail.com
FROM_NAME=VectorStom RAG System

# JWT секрет (сгенерируйте случайную строку)
JWT_SECRET_KEY=your-super-secret-jwt-key-here
FLASK_SECRET_KEY=your-flask-secret-key-here

# БД
DB_PATH=/db/docling.db
```

### 2. Настройка Gmail App Password
Для отправки email через Gmail нужен App Password:

1. Перейдите: https://myaccount.google.com/apppasswords
2. Войдите в аккаунт Gmail
3. Создайте App Password для приложения
4. Используйте этот пароль в `SMTP_PASSWORD`

⚠️ **Важно**: Обычный пароль Gmail не работает! Нужен именно App Password.

### 3. Инициализация БД
При первом запуске БД автоматически создаст новые таблицы:
- `web_users` - пользователи с авторизацией через email
- `chat_sessions` - сессии чатов
- `chat_messages` - сообщения в чатах

```bash
# Запустить приложение (БД инициализируется автоматически)
python webapp/app.py
```

### 4. Проверка работы
1. Откройте http://localhost:5000
2. Нажмите "Войти" → "Зарегистрироваться"
3. Введите email и пароль
4. Проверьте почту - должен прийти код верификации
5. После верификации откроется боковая панель с историей

## Структура файлов

```
webapp/
├── app.py                    # Главный файл Flask, добавлен @jwt_required для /api/search
├── auth_routes.py            # Эндпоинты авторизации + восстановление пароля
├── chat_routes.py            # NEW: API для работы с сессиями чатов
├── admin_routes.py           # Админ-панель + эндпоинты для web-users
├── database.py               # БД функции + таблицы web_users, chat_sessions
├── email_service.py          # Отправка email (верификация + восстановление)
├── static/
│   ├── auth.js               # NEW: Логика авторизации и истории чатов
│   └── admin-web-users.js    # NEW: Управление web-пользователями в админке
└── templates/
    ├── index.html            # Добавлены: sidebar, модальные окна, кнопка "Войти"
    └── admin.html            # Подключен admin-web-users.js

requirements.txt              # Добавлены: PyJWT, bcrypt, Flask-JWT-Extended
```

## Использование

### Для пользователей
1. **Регистрация**: Email → Код из письма → Готово
2. **Вход**: Email + Пароль
3. **Восстановление пароля**: "Забыли пароль?" → Email → Код → Новый пароль
4. **Чаты**: 
   - Автоматически создаются при первом вопросе
   - Сохраняются в боковой панели
   - Можно переименовывать и удалять

### Для админов
1. Войдите в систему через `/admin`
2. Перейдите на вкладку "Web Пользователи"
3. Просмотр всех пользователей, их диалогов
4. Активация/деактивация пользователей

## Безопасность

✅ **Реализовано:**
- Пароли хешируются с bcrypt (12 раундов)
- JWT токены для авторизации (срок действия 24ч)
- Коды верификации истекают через 15 минут
- Email-подтверждение обязательно
- Проверка авторизации для всех защищенных эндпоинтов

⚠️ **Рекомендации:**
- Используйте HTTPS в продакшене
- Регулярно обновляйте JWT_SECRET_KEY
- Не храните SMTP пароль в git (используйте .env)

## Troubleshooting

### Email не приходят
- Проверьте `SMTP_USER` и `SMTP_PASSWORD` в `.env`
- Убедитесь, что используете App Password, а не обычный
- Проверьте спам-папку

### Токен невалиден
- Очистите localStorage в браузере
- Проверьте, что JWT_SECRET_KEY одинаковый на сервере

### Sidebar не появляется
- Откройте консоль браузера (F12)
- Проверьте, что `auth.js` загружается
- Убедитесь, что пользователь авторизован

### БД ошибки
```bash
# Пересоздать БД
rm /db/docling.db  # или путь из DB_PATH
python webapp/app.py  # БД создастся заново
```

## Следующие шаги (опционально)

- [ ] OAuth авторизация (Google, GitHub)
- [ ] Rate limiting для защиты от спама
- [ ] Email-уведомления о новых диалогах
- [ ] Экспорт истории чатов в PDF/JSON
- [ ] Разделение ролей (user/admin/superadmin)
- [ ] 2FA через Google Authenticator
