#!/usr/bin/env python3
"""
Скрипт для автоматической обработки всех DOCX файлов:
1. Конвертация в markdown
2. Создание векторов
"""
import os
import sys
from pathlib import Path

# Добавляем текущую директорию в путь
sys.path.insert(0, '/app')

from process_documents import process_document
from create_embeddings import process_file

DOCUMENTS_DIR = "/documents"
PROCESSED_DIR = "/shared/processed"

def main():
    print("="*70)
    print("🔄 Автоматическая обработка DOCX файлов")
    print("="*70)
    
    # Находим все DOCX файлы
    docx_files = []
    for ext in ['.docx', '.DOCX']:
        docx_files.extend(Path(DOCUMENTS_DIR).glob(f'*{ext}'))
    
    # Фильтруем только нужные файлы
    target_files = [
        f for f in docx_files 
        if 'ПИРы' in f.name or 'Справочник' in f.name
    ]
    
    if not target_files:
        print("⚠️  DOCX файлы не найдены")
        return
    
    print(f"\n📄 Найдено файлов для обработки: {len(target_files)}\n")
    
    for i, docx_file in enumerate(target_files, 1):
        print("="*70)
        print(f"📄 [{i}/{len(target_files)}] Обработка: {docx_file.name}")
        print("="*70)
        
        # Шаг 1: Конвертация DOCX -> Markdown
        print("\n1️⃣  Конвертация DOCX → Markdown...")
        result = process_document(str(docx_file), PROCESSED_DIR)
        
        if not result['success']:
            print(f"   ❌ Ошибка: {result.get('error', 'Unknown')}")
            continue
        
        md_file = result['output_file']
        print(f"   ✅ Сохранено: {Path(md_file).name}")
        
        # Шаг 2: Создание векторов
        print("\n2️⃣  Создание векторов (chunk_size=350, overlap=70)...")
        try:
            process_file(md_file)
            print(f"   ✅ Векторы созданы!")
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
            continue
        
        print()
    
    print("="*70)
    print("✨ Обработка завершена!")
    print("="*70)
    
    # Проверяем количество векторов
    print("\n📊 Проверка результатов...")
    try:
        import requests
        response = requests.get("http://qdrant-docling:6333/collections/documents", timeout=5)
        if response.status_code == 200:
            data = response.json()
            points = data['result']['points_count']
            print(f"   ✅ Всего векторов в базе: {points}")
    except Exception as e:
        print(f"   ⚠️  Не удалось проверить: {e}")

if __name__ == "__main__":
    main()
