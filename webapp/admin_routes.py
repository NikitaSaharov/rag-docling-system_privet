from flask import Blueprint, jsonify, request
import database as db
import re
import requests
import os

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

# Qdrant settings
QDRANT_URL = os.getenv('QDRANT_URL', 'http://qdrant:6333')
COLLECTION_NAME = "documents"

def validate_phone_number(phone):
    """Валидация номера телефона (международный формат)"""
    # Простая валидация: начинается с + и содержит 10-15 цифр
    pattern = r'^\+\d{10,15}$'
    return re.match(pattern, phone) is not None

@admin_bp.route('/users', methods=['GET'])
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

@admin_bp.route('/documents', methods=['GET'])
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
def approve_request(request_id):
    """Одобрить запрос на доступ"""
    try:
        success, message = db.approve_access_request(request_id)
        
        if success:
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
def reject_request(request_id):
    """Отклонить запрос на доступ"""
    try:
        success = db.reject_access_request(request_id)
        
        if success:
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

@admin_bp.route('/health', methods=['GET'])
def health_check():
    """Здоровье для админ API"""
    return jsonify({
        'success': True,
        'message': 'Admin API is running'
    })
