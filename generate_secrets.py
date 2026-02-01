#!/usr/bin/env python3
"""
Генератор секретных ключей для .env файла
"""
import secrets

print("=" * 60)
print("Генератор секретных ключей для VectorStom")
print("=" * 60)
print()

# Генерируем JWT секрет (64 символа)
jwt_secret = secrets.token_hex(32)
print("JWT_SECRET_KEY (скопируйте в .env.local):")
print(jwt_secret)
print()

# Генерируем Flask секрет (64 символа)
flask_secret = secrets.token_hex(32)
print("FLASK_SECRET_KEY (скопируйте в .env.local):")
print(flask_secret)
print()

print("=" * 60)
print("✅ Скопируйте эти ключи в ваш .env.local файл")
print("=" * 60)
