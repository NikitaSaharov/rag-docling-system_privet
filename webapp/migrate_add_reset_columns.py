#!/usr/bin/env python3
"""
Миграция: добавление колонок для восстановления пароля в таблицу web_users
"""
import sqlite3
import os

DB_PATH = os.getenv('DB_PATH', '/db/docling.db')

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Проверяем, существуют ли уже колонки
        cursor.execute("PRAGMA table_info(web_users)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'reset_code' not in columns:
            print("Adding reset_code column...")
            cursor.execute('''
                ALTER TABLE web_users 
                ADD COLUMN reset_code TEXT
            ''')
            print("✅ reset_code column added")
        else:
            print("ℹ️  reset_code column already exists")
        
        if 'reset_code_expires_at' not in columns:
            print("Adding reset_code_expires_at column...")
            cursor.execute('''
                ALTER TABLE web_users 
                ADD COLUMN reset_code_expires_at TIMESTAMP
            ''')
            print("✅ reset_code_expires_at column added")
        else:
            print("ℹ️  reset_code_expires_at column already exists")
        
        conn.commit()
        print("\n✅ Migration completed successfully!")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    print("Running migration: add reset columns to web_users table\n")
    migrate()
