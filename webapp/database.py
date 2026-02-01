import sqlite3
from datetime import datetime
from pathlib import Path
import os

# Путь к БД
DB_PATH = os.getenv('DB_PATH', '/db/docling.db')

def get_connection():
    """Создает подключение к БД"""
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Инициализирует базу данных"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Таблица пользователей (telegram)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT UNIQUE NOT NULL,
            telegram_id INTEGER UNIQUE,
            username TEXT,
            is_active INTEGER DEFAULT 1,
            user_type TEXT DEFAULT 'telegram',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица web-пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS web_users (
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
        )
    ''')
    
    # Таблица сессий чатов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            user_type TEXT NOT NULL,
            title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES web_users(id)
        )
    ''')
    
    # Таблица сообщений в чатах
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
        )
    ''')
    
    # Таблица логов запросов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS query_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            query TEXT NOT NULL,
            answer TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Таблица запросов на доступ
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS access_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT NOT NULL,
            telegram_id INTEGER NOT NULL,
            username TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMP,
            processed_by TEXT
        )
    ''')
    
    # Индексы для оптимизации
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone_number)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_type ON users(user_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_web_users_email ON web_users(email)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_web_users_type ON web_users(user_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_chat_sessions_user ON chat_sessions(user_id, user_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_query_logs_user_id ON query_logs(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_query_logs_timestamp ON query_logs(timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_access_requests_status ON access_requests(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_access_requests_telegram_id ON access_requests(telegram_id)')
    
    conn.commit()
    conn.close()
    print("✅ База данных инициализирована")

def add_user(phone_number, telegram_id=None, username=None):
    """
    Добавляет нового пользователя
    
    Args:
        phone_number: номер телефона (обязательный)
        telegram_id: Telegram ID (опционально, привязывается позже)
        username: имя пользователя в Telegram (опционально)
    
    Returns:
        user_id или None при ошибке
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO users (phone_number, telegram_id, username)
            VALUES (?, ?, ?)
        ''', (phone_number, telegram_id, username))
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        return user_id
    except sqlite3.IntegrityError as e:
        conn.close()
        print(f"Ошибка добавления пользователя: {e}")
        return None

def get_user_by_phone(phone_number):
    """Получает пользователя по номеру телефона"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE phone_number = ?', (phone_number,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None

def get_user_by_telegram_id(telegram_id):
    """Получает активного пользователя по Telegram ID"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM users 
        WHERE telegram_id = ? AND is_active = 1
    ''', (telegram_id,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None

def update_user_telegram_id(phone_number, telegram_id, username=None):
    """
    Привязывает Telegram ID к существующему пользователю по номеру телефона
    
    Args:
        phone_number: номер телефона пользователя
        telegram_id: Telegram ID для привязки
        username: имя пользователя в Telegram (опционально)
    
    Returns:
        True если успешно, False если пользователь не найден
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        if username:
            cursor.execute('''
                UPDATE users 
                SET telegram_id = ?, username = ?, updated_at = CURRENT_TIMESTAMP
                WHERE phone_number = ? AND is_active = 1
            ''', (telegram_id, username, phone_number))
        else:
            cursor.execute('''
                UPDATE users 
                SET telegram_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE phone_number = ? AND is_active = 1
            ''', (telegram_id, phone_number))
        
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        return success
    except sqlite3.IntegrityError as e:
        conn.close()
        print(f"Ошибка обновления telegram_id: {e}")
        return False

def list_users(limit=100, offset=0):
    """Получает список всех пользователей с пагинацией"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM users 
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
    ''', (limit, offset))
    users = cursor.fetchall()
    conn.close()
    return [dict(user) for user in users]

def deactivate_user(user_id):
    """Деактивирует пользователя"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users 
        SET is_active = 0, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (user_id,))
    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    return success

def delete_user(user_id):
    """Полностью удаляет пользователя из БД"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Сначала удаляем логи
    cursor.execute('DELETE FROM query_logs WHERE user_id = ?', (user_id,))
    # Затем пользователя
    cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
    
    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    return success

def log_query(user_id, query, answer):
    """Логирует запрос пользователя"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO query_logs (user_id, query, answer)
        VALUES (?, ?, ?)
    ''', (user_id, query, answer))
    conn.commit()
    conn.close()

def get_query_logs(user_id=None, limit=50, offset=0):
    """
    Получает логи запросов
    
    Args:
        user_id: если указан, возвращает логи только этого пользователя
        limit: максимальное количество записей
        offset: смещение для пагинации
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    if user_id:
        cursor.execute('''
            SELECT l.*, u.username, u.phone_number 
            FROM query_logs l
            JOIN users u ON l.user_id = u.id
            WHERE l.user_id = ?
            ORDER BY l.timestamp DESC
            LIMIT ? OFFSET ?
        ''', (user_id, limit, offset))
    else:
        cursor.execute('''
            SELECT l.*, u.username, u.phone_number 
            FROM query_logs l
            JOIN users u ON l.user_id = u.id
            ORDER BY l.timestamp DESC
            LIMIT ? OFFSET ?
        ''', (limit, offset))
    
    logs = cursor.fetchall()
    conn.close()
    return [dict(log) for log in logs]

def get_stats():
    """Возвращает статистику системы"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Общее количество пользователей
    cursor.execute('SELECT COUNT(*) as total FROM users WHERE is_active = 1')
    total_users = cursor.fetchone()['total']
    
    # Количество запросов сегодня
    cursor.execute('''
        SELECT COUNT(*) as total 
        FROM query_logs 
        WHERE DATE(timestamp) = DATE('now')
    ''')
    queries_today = cursor.fetchone()['total']
    
    # Количество запросов за неделю
    cursor.execute('''
        SELECT COUNT(*) as total 
        FROM query_logs 
        WHERE DATE(timestamp) >= DATE('now', '-7 days')
    ''')
    queries_week = cursor.fetchone()['total']
    
    # Всего запросов
    cursor.execute('SELECT COUNT(*) as total FROM query_logs')
    total_queries = cursor.fetchone()['total']
    
    # Активные пользователи (делали запросы за последнюю неделю)
    cursor.execute('''
        SELECT COUNT(DISTINCT user_id) as total 
        FROM query_logs 
        WHERE DATE(timestamp) >= DATE('now', '-7 days')
    ''')
    active_users = cursor.fetchone()['total']
    
    conn.close()
    
    return {
        'total_users': total_users,
        'active_users': active_users,
        'queries_today': queries_today,
        'queries_week': queries_week,
        'total_queries': total_queries
    }

# ===================== Web Users Functions =====================

def add_web_user(email, password_hash, username=None):
    """Добавляет нового web-пользователя"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO web_users (email, password_hash, username)
            VALUES (?, ?, ?)
        ''', (email, password_hash, username))
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        return user_id
    except sqlite3.IntegrityError as e:
        conn.close()
        print(f"Ошибка добавления web-пользователя: {e}")
        return None

def get_web_user_by_email(email):
    """Получает web-пользователя по email"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM web_users WHERE email = ?', (email,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None

def get_web_user_by_id(user_id):
    """Получает web-пользователя по ID"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM web_users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None

def set_verification_code(user_id, code, expires_at):
    """Устанавливает код верификации для web-пользователя"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE web_users 
        SET verification_code = ?, verification_code_expires_at = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (code, expires_at, user_id))
    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    return success

def verify_user(user_id, code):
    """Подтверждает email пользователя"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE web_users 
        SET is_verified = 1, is_active = 1, verification_code = NULL, 
            verification_code_expires_at = NULL, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND verification_code = ? AND verification_code_expires_at > CURRENT_TIMESTAMP
    ''', (user_id, code))
    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    return success

def set_two_fa_code(user_id, code, expires_at):
    """Устанавливает 2FA код для доступа в админ-панель"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE web_users 
        SET two_fa_code = ?, two_fa_code_expires_at = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (code, expires_at, user_id))
    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    return success

def verify_two_fa_code(user_id, code):
    """Проверяет 2FA код"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM web_users 
        WHERE id = ? AND two_fa_code = ? AND two_fa_code_expires_at > CURRENT_TIMESTAMP
    ''', (user_id, code))
    user = cursor.fetchone()
    
    if user:
        # Очищаем 2FA код после успешной проверки
        cursor.execute('''
            UPDATE web_users 
            SET two_fa_code = NULL, two_fa_code_expires_at = NULL
            WHERE id = ?
        ''', (user_id,))
        conn.commit()
    
    conn.close()
    return user is not None

def list_web_users(limit=100, offset=0):
    """Получает список web-пользователей"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, email, username, is_active, is_verified, user_type, created_at, updated_at
        FROM web_users 
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
    ''', (limit, offset))
    users = cursor.fetchall()
    conn.close()
    return [dict(user) for user in users]

def set_password_reset_code(user_id, code, expires_at):
    """Устанавливает код восстановления пароля"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE web_users 
        SET reset_code = ?, reset_code_expires_at = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (code, expires_at, user_id))
    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    return success

def verify_reset_code(email, code):
    """Проверяет код восстановления пароля"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM web_users 
        WHERE email = ? AND reset_code = ? AND reset_code_expires_at > CURRENT_TIMESTAMP
    ''', (email, code))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None

def update_password(user_id, password_hash):
    """Обновляет пароль пользователя и очищает код восстановления"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE web_users 
        SET password_hash = ?, reset_code = NULL, reset_code_expires_at = NULL, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (password_hash, user_id))
    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    return success

# ===================== Chat Sessions Functions =====================

def create_chat_session(user_id, user_type, title=None):
    """Создает новую сессию чата"""
    conn = get_connection()
    cursor = conn.cursor()
    if not title:
        title = f"Новый чат {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    
    cursor.execute('''
        INSERT INTO chat_sessions (user_id, user_type, title)
        VALUES (?, ?, ?)
    ''', (user_id, user_type, title))
    conn.commit()
    session_id = cursor.lastrowid
    conn.close()
    return session_id

def get_user_chat_sessions(user_id, user_type, limit=50):
    """Получает список сессий пользователя"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM chat_sessions 
        WHERE user_id = ? AND user_type = ?
        ORDER BY updated_at DESC
        LIMIT ?
    ''', (user_id, user_type, limit))
    sessions = cursor.fetchall()
    conn.close()
    return [dict(session) for session in sessions]

def update_chat_session(session_id, title):
    """Обновляет название сессии"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE chat_sessions 
        SET title = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (title, session_id))
    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    return success

def delete_chat_session(session_id):
    """Удаляет сессию чата (сообщения удалятся автоматически)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM chat_sessions WHERE id = ?', (session_id,))
    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    return success

def add_chat_message(session_id, role, content):
    """Добавляет сообщение в чат"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO chat_messages (session_id, role, content)
        VALUES (?, ?, ?)
    ''', (session_id, role, content))
    
    # Обновляем время последнего обновления сессии
    cursor.execute('''
        UPDATE chat_sessions 
        SET updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (session_id,))
    
    conn.commit()
    message_id = cursor.lastrowid
    conn.close()
    return message_id

def get_chat_messages(session_id, limit=100):
    """Получает сообщения сессии"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM chat_messages 
        WHERE session_id = ?
        ORDER BY created_at ASC
        LIMIT ?
    ''', (session_id, limit))
    messages = cursor.fetchall()
    conn.close()
    return [dict(message) for message in messages]

# ===================== Access Requests Functions =====================

def create_access_request(phone_number, telegram_id, username=None):
    """Создает запрос на доступ"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Проверяем, нет ли уже активного запроса от этого пользователя
        cursor.execute('''
            SELECT * FROM access_requests 
            WHERE telegram_id = ? AND status = 'pending'
        ''', (telegram_id,))
        existing = cursor.fetchone()
        
        if existing:
            conn.close()
            return dict(existing)  # Возвращаем существующий запрос
        
        # Создаем новый запрос
        cursor.execute('''
            INSERT INTO access_requests (phone_number, telegram_id, username)
            VALUES (?, ?, ?)
        ''', (phone_number, telegram_id, username))
        conn.commit()
        request_id = cursor.lastrowid
        conn.close()
        return {'id': request_id, 'status': 'pending'}
    except Exception as e:
        conn.close()
        print(f"Ошибка создания запроса на доступ: {e}")
        return None

def get_pending_access_requests():
    """Получает список ожидающих запросов на доступ"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM access_requests 
        WHERE status = 'pending'
        ORDER BY created_at DESC
    ''')
    requests = cursor.fetchall()
    conn.close()
    return [dict(req) for req in requests]

def approve_access_request(request_id, admin_username='admin'):
    """Одобряет запрос на доступ и создает пользователя"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Получаем запрос
        cursor.execute('SELECT * FROM access_requests WHERE id = ?', (request_id,))
        request = cursor.fetchone()
        
        if not request:
            conn.close()
            return False, "Запрос не найден"
        
        request_dict = dict(request)
        
        if request_dict['status'] != 'pending':
            conn.close()
            return False, "Запрос уже обработан"
        
        phone = request_dict['phone_number']
        telegram_id = request_dict['telegram_id']
        username = request_dict['username']
        
        # Создаем или обновляем пользователя
        existing_user = get_user_by_phone(phone)
        
        if existing_user:
            # Обновляем существующего пользователя
            success = update_user_telegram_id(phone, telegram_id, username)
        else:
            # Создаем нового пользователя
            user_id = add_user(phone, telegram_id, username)
            success = user_id is not None
        
        if success:
            # Обновляем статус запроса
            cursor.execute('''
                UPDATE access_requests 
                SET status = 'approved', 
                    processed_at = CURRENT_TIMESTAMP,
                    processed_by = ?
                WHERE id = ?
            ''', (admin_username, request_id))
            conn.commit()
            conn.close()
            # Возвращаем True, сообщение и данные пользователя для уведомления
            return True, "Доступ предоставлен", {'telegram_id': telegram_id, 'username': username}
        else:
            conn.close()
            return False, "Ошибка создания пользователя", None
    
    except Exception as e:
        conn.close()
        print(f"Ошибка одобрения запроса: {e}")
        return False, str(e)

def reject_access_request(request_id, admin_username='admin'):
    """Отклоняет запрос на доступ"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Получаем данные запроса до отклонения
        cursor.execute('SELECT * FROM access_requests WHERE id = ? AND status = "pending"', (request_id,))
        request = cursor.fetchone()
        
        if not request:
            conn.close()
            return False, None
        
        request_dict = dict(request)
        telegram_id = request_dict['telegram_id']
        username = request_dict['username']
        
        cursor.execute('''
            UPDATE access_requests 
            SET status = 'rejected', 
                processed_at = CURRENT_TIMESTAMP,
                processed_by = ?
            WHERE id = ?
        ''', (admin_username, request_id))
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        
        if success:
            return True, {'telegram_id': telegram_id, 'username': username}
        return False, None
    except Exception as e:
        conn.close()
        print(f"Ошибка отклонения запроса: {e}")
        return False, None

if __name__ == '__main__':
    # Тест базы данных
    print("Инициализация БД...")
    init_db()
    
    print("\nДобавление тестового пользователя...")
    user_id = add_user('+79991234567')
    if user_id:
        print(f"✅ Пользователь добавлен с ID: {user_id}")
        
        print("\nПривязка Telegram ID...")
        if update_user_telegram_id('+79991234567', 123456789, 'testuser'):
            print("✅ Telegram ID привязан")
        
        print("\nПроверка авторизации...")
        user = get_user_by_telegram_id(123456789)
        if user:
            print(f"✅ Пользователь найден: {user}")
        
        print("\nЛогирование запроса...")
        log_query(user_id, "Что такое нормочас?", "Нормочас - это...")
        
        print("\nСтатистика:")
        stats = get_stats()
        for key, value in stats.items():
            print(f"  {key}: {value}")
    else:
        print("❌ Ошибка добавления пользователя")
