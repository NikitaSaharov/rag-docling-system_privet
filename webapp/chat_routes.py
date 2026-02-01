from flask import Blueprint, request, jsonify
from auth_routes import jwt_required
import database as db

chat_bp = Blueprint('chat', __name__, url_prefix='/api/chat')

@chat_bp.route('/sessions', methods=['GET'])
@jwt_required
def get_sessions():
    """Получить список сессий текущего пользователя"""
    try:
        sessions = db.get_user_chat_sessions(request.user_id, 'web', limit=50)
        return jsonify({
            'success': True,
            'sessions': sessions
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@chat_bp.route('/sessions', methods=['POST'])
@jwt_required
def create_session():
    """Создать новую сессию чата"""
    try:
        data = request.json
        title = data.get('title')
        
        session_id = db.create_chat_session(request.user_id, 'web', title)
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'message': 'Session created'
        }), 201
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@chat_bp.route('/sessions/<int:session_id>', methods=['GET'])
@jwt_required
def get_session_messages(session_id):
    """Получить сообщения сессии"""
    try:
        messages = db.get_chat_messages(session_id, limit=100)
        
        # Проверка, что сессия принадлежит пользователю
        if messages and len(messages) > 0:
            # Получаем сессию для проверки владельца
            sessions = db.get_user_chat_sessions(request.user_id, 'web', limit=1000)
            session_ids = [s['id'] for s in sessions]
            
            if session_id not in session_ids:
                return jsonify({
                    'success': False,
                    'error': 'Access denied'
                }), 403
        
        return jsonify({
            'success': True,
            'messages': messages
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@chat_bp.route('/sessions/<int:session_id>', methods=['PATCH'])
@jwt_required
def update_session(session_id):
    """Обновить название сессии"""
    try:
        data = request.json
        title = data.get('title')
        
        if not title:
            return jsonify({
                'success': False,
                'error': 'Title is required'
            }), 400
        
        # Проверка, что сессия принадлежит пользователю
        sessions = db.get_user_chat_sessions(request.user_id, 'web', limit=1000)
        session_ids = [s['id'] for s in sessions]
        
        if session_id not in session_ids:
            return jsonify({
                'success': False,
                'error': 'Access denied'
            }), 403
        
        success = db.update_chat_session(session_id, title)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Session updated'
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to update session'
            }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@chat_bp.route('/sessions/<int:session_id>', methods=['DELETE'])
@jwt_required
def delete_session(session_id):
    """Удалить сессию чата"""
    try:
        # Проверка, что сессия принадлежит пользователю
        sessions = db.get_user_chat_sessions(request.user_id, 'web', limit=1000)
        session_ids = [s['id'] for s in sessions]
        
        if session_id not in session_ids:
            return jsonify({
                'success': False,
                'error': 'Access denied'
            }), 403
        
        success = db.delete_chat_session(session_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Session deleted'
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to delete session'
            }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
