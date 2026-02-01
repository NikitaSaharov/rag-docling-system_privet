from flask import Blueprint, request, jsonify, session
import bcrypt
import jwt
import os
import secrets
from datetime import datetime, timedelta
from functools import wraps

from database import (
    add_web_user, get_web_user_by_email, get_web_user_by_id,
    set_verification_code, verify_user, set_two_fa_code, verify_two_fa_code,
    set_password_reset_code, verify_reset_code, update_password
)
from email_service import send_verification_email, send_two_fa_email, send_password_reset_email

auth_bp = Blueprint('auth', __name__)

# JWT Configuration
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', secrets.token_hex(32))
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24

# Bcrypt cost factor
BCRYPT_ROUNDS = 12

def generate_code(length=6):
    """Генерирует случайный числовой код"""
    return ''.join([str(secrets.randbelow(10)) for _ in range(length)])

def hash_password(password):
    """Хеширует пароль с помощью bcrypt"""
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password, hashed):
    """Проверяет пароль"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_jwt_token(user_id, email, user_type='web'):
    """Создает JWT токен"""
    payload = {
        'user_id': user_id,
        'email': email,
        'user_type': user_type,
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

def decode_jwt_token(token):
    """Декодирует JWT токен"""
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def jwt_required(f):
    """Декоратор для защиты эндпоинтов"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        
        # Убираем "Bearer " если есть
        if token.startswith('Bearer '):
            token = token[7:]
        
        payload = decode_jwt_token(token)
        if not payload:
            return jsonify({'error': 'Invalid or expired token'}), 401
        
        # Добавляем данные пользователя в request
        request.user_id = payload['user_id']
        request.user_email = payload['email']
        request.user_type = payload['user_type']
        
        return f(*args, **kwargs)
    
    return decorated_function

@auth_bp.route('/api/auth/register', methods=['POST'])
def register():
    """
    Регистрация нового пользователя
    
    Ожидает JSON:
    {
        "email": "user@example.com",
        "password": "password123",
        "username": "User Name" (опционально)
    }
    """
    data = request.get_json()
    
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Email and password are required'}), 400
    
    email = data['email'].lower().strip()
    password = data['password']
    username = data.get('username', '')
    
    # Проверяем, нет ли уже такого email
    existing_user = get_web_user_by_email(email)
    if existing_user:
        return jsonify({'error': 'User with this email already exists'}), 400
    
    # Хешируем пароль
    password_hash = hash_password(password)
    
    # Создаем пользователя
    user_id = add_web_user(email, password_hash, username)
    if not user_id:
        return jsonify({'error': 'Failed to create user'}), 500
    
    # Генерируем код верификации
    code = generate_code(6)
    expires_at = datetime.now() + timedelta(minutes=15)
    
    if not set_verification_code(user_id, code, expires_at):
        return jsonify({'error': 'Failed to set verification code'}), 500
    
    # Отправляем email
    if not send_verification_email(email, code):
        return jsonify({'error': 'Failed to send verification email'}), 500
    
    return jsonify({
        'message': 'Registration successful. Please check your email for verification code.',
        'user_id': user_id,
        'email': email
    }), 201

@auth_bp.route('/api/auth/verify-email', methods=['POST'])
def verify_email():
    """
    Верификация email по коду
    
    Ожидает JSON:
    {
        "user_id": 1,
        "code": "123456"
    }
    """
    data = request.get_json()
    
    if not data or not data.get('user_id') or not data.get('code'):
        return jsonify({'error': 'User ID and code are required'}), 400
    
    user_id = data['user_id']
    code = data['code']
    
    if verify_user(user_id, code):
        user = get_web_user_by_id(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Создаем JWT токен
        token = create_jwt_token(user_id, user['email'])
        
        return jsonify({
            'message': 'Email verified successfully',
            'token': token,
            'user': {
                'id': user['id'],
                'email': user['email'],
                'username': user['username']
            }
        }), 200
    else:
        return jsonify({'error': 'Invalid or expired verification code'}), 400

@auth_bp.route('/api/auth/resend-verification', methods=['POST'])
def resend_verification():
    """
    Повторная отправка кода верификации
    
    Ожидает JSON:
    {
        "email": "user@example.com"
    }
    """
    data = request.get_json()
    
    if not data or not data.get('email'):
        return jsonify({'error': 'Email is required'}), 400
    
    email = data['email'].lower().strip()
    user = get_web_user_by_email(email)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    if user['is_verified']:
        return jsonify({'error': 'User is already verified'}), 400
    
    # Генерируем новый код
    code = generate_code(6)
    expires_at = datetime.now() + timedelta(minutes=15)
    
    if not set_verification_code(user['id'], code, expires_at):
        return jsonify({'error': 'Failed to set verification code'}), 500
    
    # Отправляем email
    if not send_verification_email(email, code):
        return jsonify({'error': 'Failed to send verification email'}), 500
    
    return jsonify({'message': 'Verification code sent'}), 200

@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    """
    Авторизация пользователя
    
    Ожидает JSON:
    {
        "email": "user@example.com",
        "password": "password123"
    }
    """
    data = request.get_json()
    
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Email and password are required'}), 400
    
    email = data['email'].lower().strip()
    password = data['password']
    
    user = get_web_user_by_email(email)
    
    if not user:
        return jsonify({'error': 'Invalid email or password'}), 401
    
    if not user['is_verified']:
        return jsonify({'error': 'Email not verified'}), 401
    
    if not user['is_active']:
        return jsonify({'error': 'Account is not active'}), 401
    
    # Проверяем пароль
    if not verify_password(password, user['password_hash']):
        return jsonify({'error': 'Invalid email or password'}), 401
    
    # Создаем JWT токен
    token = create_jwt_token(user['id'], user['email'])
    
    return jsonify({
        'message': 'Login successful',
        'token': token,
        'user': {
            'id': user['id'],
            'email': user['email'],
            'username': user['username']
        }
    }), 200

@auth_bp.route('/api/auth/request-admin-2fa', methods=['POST'])
@jwt_required
def request_admin_2fa():
    """
    Запрос 2FA кода для доступа в админ-панель
    Требует JWT токен в заголовке Authorization
    """
    user = get_web_user_by_id(request.user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Генерируем 2FA код
    code = generate_code(6)
    expires_at = datetime.now() + timedelta(minutes=5)
    
    if not set_two_fa_code(user['id'], code, expires_at):
        return jsonify({'error': 'Failed to set 2FA code'}), 500
    
    # Отправляем email
    if not send_two_fa_email(user['email'], code):
        return jsonify({'error': 'Failed to send 2FA email'}), 500
    
    return jsonify({'message': '2FA code sent to your email'}), 200

@auth_bp.route('/api/auth/verify-admin-2fa', methods=['POST'])
@jwt_required
def verify_admin_2fa():
    """
    Верификация 2FA кода для доступа в админ-панель
    
    Ожидает JSON:
    {
        "code": "123456"
    }
    """
    data = request.get_json()
    
    if not data or not data.get('code'):
        return jsonify({'error': 'Code is required'}), 400
    
    code = data['code']
    
    if verify_two_fa_code(request.user_id, code):
        # Создаем специальный токен с admin флагом
        user = get_web_user_by_id(request.user_id)
        payload = {
            'user_id': user['id'],
            'email': user['email'],
            'user_type': 'web',
            'is_admin': True,
            'exp': datetime.utcnow() + timedelta(hours=2),  # Админ токен на 2 часа
            'iat': datetime.utcnow()
        }
        admin_token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        
        return jsonify({
            'message': '2FA verified',
            'admin_token': admin_token
        }), 200
    else:
        return jsonify({'error': 'Invalid or expired 2FA code'}), 400

@auth_bp.route('/api/auth/me', methods=['GET'])
@jwt_required
def get_current_user():
    """
    Получает информацию о текущем пользователе
    Требует JWT токен в заголовке Authorization
    """
    user = get_web_user_by_id(request.user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify({
        'id': user['id'],
        'email': user['email'],
        'username': user['username'],
        'user_type': user['user_type'],
        'is_verified': user['is_verified'],
        'is_active': user['is_active'],
        'created_at': user['created_at']
    }), 200

@auth_bp.route('/api/auth/logout', methods=['POST'])
@jwt_required
def logout():
    """
    Выход пользователя (на клиенте нужно удалить токен)
    """
    return jsonify({'message': 'Logout successful'}), 200

@auth_bp.route('/api/auth/forgot-password', methods=['POST'])
def forgot_password():
    """
    Запрос на восстановление пароля
    
    Ожидает JSON:
    {
        "email": "user@example.com"
    }
    """
    data = request.get_json()
    
    if not data or not data.get('email'):
        return jsonify({'error': 'Email is required'}), 400
    
    email = data['email'].lower().strip()
    user = get_web_user_by_email(email)
    
    if not user:
        # Не сообщаем, что пользователь не найден (безопасность)
        return jsonify({'message': 'If email exists, reset code has been sent'}), 200
    
    # Генерируем код восстановления
    code = generate_code(6)
    expires_at = datetime.now() + timedelta(minutes=15)
    
    if not set_password_reset_code(user['id'], code, expires_at):
        return jsonify({'error': 'Failed to set reset code'}), 500
    
    # Отправляем email
    if not send_password_reset_email(email, code):
        return jsonify({'error': 'Failed to send reset email'}), 500
    
    return jsonify({'message': 'Reset code sent to your email'}), 200

@auth_bp.route('/api/auth/verify-reset-code', methods=['POST'])
def verify_password_reset_code():
    """
    Проверка кода восстановления пароля
    
    Ожидает JSON:
    {
        "email": "user@example.com",
        "code": "123456"
    }
    """
    data = request.get_json()
    
    if not data or not data.get('email') or not data.get('code'):
        return jsonify({'error': 'Email and code are required'}), 400
    
    email = data['email'].lower().strip()
    code = data['code']
    
    user = verify_reset_code(email, code)
    
    if user:
        return jsonify({
            'message': 'Code verified',
            'user_id': user['id']
        }), 200
    else:
        return jsonify({'error': 'Invalid or expired reset code'}), 400

@auth_bp.route('/api/auth/reset-password', methods=['POST'])
def reset_password():
    """
    Установка нового пароля
    
    Ожидает JSON:
    {
        "email": "user@example.com",
        "code": "123456",
        "new_password": "newpassword123"
    }
    """
    data = request.get_json()
    
    if not data or not data.get('email') or not data.get('code') or not data.get('new_password'):
        return jsonify({'error': 'Email, code and new password are required'}), 400
    
    email = data['email'].lower().strip()
    code = data['code']
    new_password = data['new_password']
    
    # Проверяем код
    user = verify_reset_code(email, code)
    
    if not user:
        return jsonify({'error': 'Invalid or expired reset code'}), 400
    
    # Хешируем новый пароль
    password_hash = hash_password(new_password)
    
    # Обновляем пароль
    if not update_password(user['id'], password_hash):
        return jsonify({'error': 'Failed to update password'}), 500
    
    return jsonify({'message': 'Password updated successfully'}), 200
