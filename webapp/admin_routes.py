from flask import Blueprint, jsonify, request, session, Response
import database as db
import csv
import io
from datetime import datetime
import re
import requests
import os
import secrets
import hashlib
from functools import wraps
from telegram_notify import notify_access_approved, notify_access_rejected

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

# Qdrant settings
QDRANT_URL = os.getenv('QDRANT_URL', 'http://qdrant:6333')
COLLECTION_NAME = "documents"

# Admin credentials (set via ADMIN_USERNAME / ADMIN_PASSWORD in .env.local)
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', '')
ADMIN_PASSWORD_HASH = hashlib.sha256(os.getenv('ADMIN_PASSWORD', '').encode()).hexdigest()
if not os.getenv('ADMIN_PASSWORD'):
    print('⚠️  WARNING: ADMIN_PASSWORD not set in environment!')

def admin_required(f):
    """Декоратор для защиты админ-эндпоинтов"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Проверяем сессию
        if not session.get('admin_logged_in'):
            return jsonify({'error': 'Требуется авторизация администратора', 'require_login': True}), 401
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/login', methods=['POST'])
def admin_login():
    """Авторизация администратора"""
    data = request.get_json()
    username = data.get('username', '')
    password = data.get('password', '')
    
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    if username == ADMIN_USERNAME and password_hash == ADMIN_PASSWORD_HASH:
        session['admin_logged_in'] = True
        session.permanent = True  # Сессия сохраняется 
        return jsonify({'success': True, 'message': 'Вход выполнен'})
    else:
        return jsonify({'error': 'Неверный логин или пароль'}), 401

@admin_bp.route('/logout', methods=['POST'])
def admin_logout():
    """Выход администратора"""
    session.pop('admin_logged_in', None)
    return jsonify({'success': True, 'message': 'Выход выполнен'})

@admin_bp.route('/check-auth', methods=['GET'])
def check_admin_auth():
    """Проверка авторизации админа"""
    return jsonify({'authorized': session.get('admin_logged_in', False)})

def validate_phone_number(phone):
    """Валидация номера телефона (международный формат)"""
    # Простая валидация: начинается с + и содержит 10-15 цифр
    pattern = r'^\+\d{10,15}$'
    return re.match(pattern, phone) is not None

@admin_bp.route('/users', methods=['GET'])
@admin_required
def get_users():
    """Получить список всех пользователей"""
    try:
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
        
        users = db.list_users(limit=limit, offset=offset)
        return jsonify({
            'success': True,
            'users': users,
            'count': len(users)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_bp.route('/users', methods=['POST'])
@admin_required
def add_user():
    """Добавить нового пользователя по номеру телефона"""
    try:
        data = request.json
        phone = data.get('phone_number', '').strip()
        
        if not phone:
            return jsonify({
                'success': False,
                'error': 'Номер телефона обязателен'
            }), 400
        
        if not validate_phone_number(phone):
            return jsonify({
                'success': False,
                'error': 'Неверный формат номера телефона. Используйте международный формат (+7XXXXXXXXXX)'
            }), 400
        
        # Проверяем, не существует ли уже такой пользователь
        existing_user = db.get_user_by_phone(phone)
        if existing_user:
            return jsonify({
                'success': False,
                'error': 'Пользователь с таким номером уже существует'
            }), 400
        
        user_id = db.add_user(phone)
        if user_id:
            return jsonify({
                'success': True,
                'message': f'Пользователь добавлен с ID {user_id}',
                'user_id': user_id
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Ошибка при добавлении пользователя'
            }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    """Удалить пользователя"""
    try:
        action = request.args.get('action', 'deactivate')
        
        if action == 'delete':
            # Полное удаление
            success = db.delete_user(user_id)
            message = 'Пользователь удален'
        else:
            # Деактивация (по умолчанию)
            success = db.deactivate_user(user_id)
            message = 'Пользователь деактивирован'
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Пользователь не найден'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_bp.route('/stats', methods=['GET'])
@admin_required
def get_stats():
    """Получить статистику системы"""
    try:
        stats = db.get_stats()
        
        # Добавляем статистику по документам из Qdrant
        # (предполагается, что функция для этого уже есть в app.py)
        # Здесь можно добавить импорт и вызов функции получения статистики Qdrant
        
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_bp.route('/logs', methods=['GET'])
@admin_required
def get_logs():
    """Получить логи запросов"""
    try:
        user_id = request.args.get('user_id', type=int)
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        
        logs = db.get_query_logs(user_id=user_id, limit=limit, offset=offset)
        
        return jsonify({
            'success': True,
            'logs': logs,
            'count': len(logs)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_bp.route('/access-requests', methods=['GET'])
@admin_required
def get_access_requests():
    """Получить список запросов на доступ"""
    try:
        requests = db.get_pending_access_requests()
        return jsonify({
            'success': True,
            'requests': requests,
            'count': len(requests)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_bp.route('/access-requests', methods=['POST'])
def create_access_request():
    """Создать запрос на доступ"""
    try:
        data = request.json
        phone = data.get('phone_number')
        telegram_id = data.get('telegram_id')
        username = data.get('username')
        
        if not phone or not telegram_id:
            return jsonify({
                'success': False,
                'error': 'Номер телефона и Telegram ID обязательны'
            }), 400
        
        result = db.create_access_request(phone, telegram_id, username)
        
        if result:
            return jsonify({
                'success': True,
                'message': 'Запрос на доступ создан',
                'request_id': result.get('id')
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Ошибка создания запроса'
            }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_bp.route('/web-users', methods=['GET'])
@admin_required
def get_web_users():
    """Получить список web-пользователей"""
    try:
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
        
        users = db.list_web_users(limit=limit, offset=offset)
        return jsonify({
            'success': True,
            'users': users,
            'count': len(users)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_bp.route('/web-users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_web_user(user_id):
    """Удалить web-пользователя"""
    try:
        success = db.delete_web_user(user_id)
        if success:
            return jsonify({
                'success': True,
                'message': 'Web-пользователь удален'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Пользователь не найден'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_bp.route('/web-users/<int:user_id>/sessions', methods=['GET'])
@admin_required
def get_web_user_sessions(user_id):
    """Получить сессии чатов web-пользователя"""
    try:
        sessions = db.get_user_chat_sessions(user_id, 'web', limit=100)
        return jsonify({
            'success': True,
            'sessions': sessions,
            'count': len(sessions)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_bp.route('/web-users/<int:user_id>/sessions/<int:session_id>/messages', methods=['GET'])
@admin_required
def get_web_user_session_messages(user_id, session_id):
    """Получить сообщения конкретной сессии"""
    try:
        messages = db.get_chat_messages(session_id, limit=100)
        return jsonify({
            'success': True,
            'messages': messages
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_bp.route('/web-users/<int:user_id>/toggle-active', methods=['POST'])
@admin_required
def toggle_web_user_active(user_id):
    """Активировать/деактивировать web-пользователя"""
    try:
        # Получаем текущего пользователя
        user = db.get_web_user_by_id(user_id)
        if not user:
            return jsonify({
                'success': False,
                'error': 'Пользователь не найден'
            }), 404
        
        # Меняем статус
        conn = db.get_connection()
        cursor = conn.cursor()
        new_status = 0 if user['is_active'] else 1
        cursor.execute('''
            UPDATE web_users 
            SET is_active = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (new_status, user_id))
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        
        if success:
            status_text = 'активирован' if new_status else 'деактивирован'
            return jsonify({
                'success': True,
                'message': f'Пользователь {status_text}',
                'is_active': new_status
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Ошибка обновления статуса'
            }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_bp.route('/documents', methods=['GET'])
@admin_required
def get_documents():
    """Получить список документов из Qdrant"""
    try:
        # Получаем все точки из коллекции
        all_points = []
        offset = None
        
        # Scroll через всю коллекцию
        for _ in range(100):  # Максимум 100 итераций
            scroll_params = {
                "limit": 100,
                "with_payload": True,
                "with_vector": False
            }
            if offset:
                scroll_params["offset"] = offset
            
            response = requests.post(
                f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points/scroll",
                json=scroll_params,
                timeout=10
            )
            
            if response.status_code != 200:
                break
            
            data = response.json()
            points = data.get("result", {}).get("points", [])
            
            if not points:
                break
            
            all_points.extend(points)
            offset = data.get("result", {}).get("next_page_offset")
            
            if not offset:
                break
        
        # Группируем по документам
        documents = {}
        for point in all_points:
            payload = point.get("payload", {})
            filename = payload.get("filename", "Unknown")
            
            if filename not in documents:
                documents[filename] = {
                    "filename": filename,
                    "chunks": 0,
                    "total_chunks": payload.get("total_chunks", 0)
                }
            
            documents[filename]["chunks"] += 1
        
        # Конвертируем в список
        docs_list = list(documents.values())
        docs_list.sort(key=lambda x: x["filename"])
        
        # Получаем общую статистику
        collection_info = requests.get(
            f"{QDRANT_URL}/collections/{COLLECTION_NAME}",
            timeout=10
        )
        
        vectors_count = 0
        if collection_info.status_code == 200:
            vectors_count = collection_info.json().get("result", {}).get("vectors_count", 0)
        
        return jsonify({
            'success': True,
            'documents': docs_list,
            'total_documents': len(docs_list),
            'total_vectors': vectors_count
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_bp.route('/access-requests/<int:request_id>/approve', methods=['POST'])
@admin_required
def approve_request(request_id):
    """Одобрить запрос на доступ"""
    try:
        result = db.approve_access_request(request_id)
        
        # Распаковываем результат (success, message, user_data)
        if len(result) == 3:
            success, message, user_data = result
        else:
            # Обратная совместимость
            success, message = result
            user_data = None
        
        if success:
            # Отправляем уведомление пользователю
            print(f"✅ Запрос {request_id} одобрен. user_data={user_data}")
            if user_data and user_data.get('telegram_id'):
                result_notify = notify_access_approved(
                    user_data['telegram_id'],
                    user_data.get('username')
                )
                print(f"📤 Результат уведомления: {result_notify}")
            else:
                print(f"⚠️ Нет user_data или telegram_id для уведомления")
            
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_bp.route('/access-requests/<int:request_id>/reject', methods=['POST'])
@admin_required
def reject_request(request_id):
    """Отклонить запрос на доступ"""
    try:
        success, user_data = db.reject_access_request(request_id)
        
        if success:
            # Отправляем уведомление пользователю
            if user_data and user_data.get('telegram_id'):
                notify_access_rejected(
                    user_data['telegram_id'],
                    user_data.get('username')
                )
            
            return jsonify({
                'success': True,
                'message': 'Запрос отклонен'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Запрос не найден или уже обработан'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ===================== Telegram Chat Endpoints =====================

@admin_bp.route('/telegram-users', methods=['GET'])
@admin_required
def get_telegram_users_with_stats():
    """Получить список telegram пользователей со статистикой чатов"""
    try:
        users = db.get_telegram_users_with_chat_stats()
        return jsonify({
            'success': True,
            'users': users,
            'count': len(users)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_bp.route('/telegram-sessions', methods=['GET'])
@admin_required
def get_telegram_sessions():
    """Получить все telegram сессии с информацией о пользователях"""
    try:
        limit = int(request.args.get('limit', 100))
        sessions = db.get_all_telegram_sessions_with_users(limit=limit)
        return jsonify({
            'success': True,
            'sessions': sessions,
            'count': len(sessions)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_bp.route('/telegram-users/<int:user_id>/sessions', methods=['GET'])
@admin_required
def get_telegram_user_sessions(user_id):
    """Получить сессии конкретного telegram пользователя"""
    try:
        sessions = db.get_telegram_user_sessions(user_id, limit=100)
        return jsonify({
            'success': True,
            'sessions': sessions,
            'count': len(sessions)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin_bp.route('/telegram-sessions/<int:session_id>/messages', methods=['GET'])
@admin_required
def get_telegram_session_messages(session_id):
    """Получить сообщения конкретной telegram сессии"""
    try:
        messages = db.get_chat_messages(session_id, limit=200)
        return jsonify({
            'success': True,
            'messages': messages
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ===================== Export Endpoints =====================

@admin_bp.route('/telegram-users/<int:user_id>/export', methods=['GET'])
@admin_required
def export_telegram_user_chats(user_id):
    """Экспорт всех диалогов Telegram пользователя в CSV"""
    try:
        # Получаем информацию о пользователе
        user = db.get_user_by_id(user_id)
        if not user:
            return jsonify({'success': False, 'error': 'Пользователь не найден'}), 404
        
        # Получаем все сессии пользователя
        sessions = db.get_telegram_user_sessions(user_id, limit=1000)
        
        # Создаем CSV в памяти
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_ALL)
        
        # Заголовок
        writer.writerow(['Дата', 'Время', 'Сессия', 'Роль', 'Сообщение'])
        
        # Собираем все сообщения из всех сессий
        for session in sessions:
            session_title = session.get('title', 'Диалог')
            messages = db.get_chat_messages(session['id'], limit=1000)
            
            for msg in messages:
                created_at = msg.get('created_at', '')
                if created_at:
                    try:
                        dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        date_str = dt.strftime('%Y-%m-%d')
                        time_str = dt.strftime('%H:%M:%S')
                    except:
                        date_str = created_at[:10] if len(created_at) >= 10 else ''
                        time_str = created_at[11:19] if len(created_at) >= 19 else ''
                else:
                    date_str = ''
                    time_str = ''
                
                role = 'Пользователь' if msg.get('role') == 'user' else 'Бот'
                content = msg.get('content', '').replace('\n', ' ').replace('\r', '')
                
                writer.writerow([date_str, time_str, session_title, role, content])
        
        # Подготавливаем ответ
        output.seek(0)
        username = user.get('username') or user.get('phone_number') or f'user_{user_id}'
        filename = f'telegram_{username}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        return Response(
            output.getvalue(),
            mimetype='text/csv; charset=utf-8',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Content-Type': 'text/csv; charset=utf-8'
            }
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/web-users/<int:user_id>/export', methods=['GET'])
@admin_required
def export_web_user_chats(user_id):
    """Экспорт всех диалогов Web пользователя в CSV"""
    try:
        # Получаем информацию о пользователе
        user = db.get_web_user_by_id(user_id)
        if not user:
            return jsonify({'success': False, 'error': 'Пользователь не найден'}), 404
        
        # Получаем все сессии пользователя
        sessions = db.get_user_chat_sessions(user_id, 'web', limit=1000)
        
        # Создаем CSV в памяти
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_ALL)
        
        # Заголовок
        writer.writerow(['Дата', 'Время', 'Сессия', 'Роль', 'Сообщение'])
        
        # Собираем все сообщения из всех сессий
        for session in sessions:
            session_title = session.get('title', 'Диалог')
            messages = db.get_chat_messages(session['id'], limit=1000)
            
            for msg in messages:
                created_at = msg.get('created_at', '')
                if created_at:
                    try:
                        dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        date_str = dt.strftime('%Y-%m-%d')
                        time_str = dt.strftime('%H:%M:%S')
                    except:
                        date_str = created_at[:10] if len(created_at) >= 10 else ''
                        time_str = created_at[11:19] if len(created_at) >= 19 else ''
                else:
                    date_str = ''
                    time_str = ''
                
                role = 'Пользователь' if msg.get('role') == 'user' else 'Бот'
                content = msg.get('content', '').replace('\n', ' ').replace('\r', '')
                
                writer.writerow([date_str, time_str, session_title, role, content])
        
        # Подготавливаем ответ
        output.seek(0)
        username = user.get('email') or user.get('username') or f'user_{user_id}'
        filename = f'web_{username}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        return Response(
            output.getvalue(),
            mimetype='text/csv; charset=utf-8',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Content-Type': 'text/csv; charset=utf-8'
            }
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/health', methods=['GET'])
def health_check():
    """Здоровье для админ API"""
    return jsonify({
        'success': True,
        'message': 'Admin API is running'
    })
