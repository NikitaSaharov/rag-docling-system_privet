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
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT UNIQUE NOT NULL,
            telegram_id INTEGER UNIQUE,
            username TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            return True, "Доступ предоставлен"
        else:
            conn.close()
            return False, "Ошибка создания пользователя"
    
    except Exception as e:
        conn.close()
        print(f"Ошибка одобрения запроса: {e}")
        return False, str(e)

def reject_access_request(request_id, admin_username='admin'):
    """Отклоняет запрос на доступ"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            UPDATE access_requests 
            SET status = 'rejected', 
                processed_at = CURRENT_TIMESTAMP,
                processed_by = ?
            WHERE id = ? AND status = 'pending'
        ''', (admin_username, request_id))
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        return success
    except Exception as e:
        conn.close()
        print(f"Ошибка отклонения запроса: {e}")
        return False

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
