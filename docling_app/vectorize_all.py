#!/usr/bin/env python3
"""Векторизация всех markdown файлов ПИРы"""
import sys
import os
sys.path.insert(0, '/app')

from create_embeddings import process_file
from pathlib import Path

# Ищем файлы по паттерну
processed_dir = Path("/shared/processed")
files = list(processed_dir.glob("ПИРы*.md"))

if not files:
    print("⚠️  Файлы ПИРы*.md не найдены в /shared/processed/")
    sys.exit(1)

print("="*70)
print(f"🔄 Векторизация {len(files)} файлов ПИРы")
print("="*70)

for i, filepath in enumerate(files, 1):
    print(f"\n[{i}/{len(files)}] {filepath.name}")
    print("-"*70)
    try:
        process_file(str(filepath))
        print(f"✅ Файл обработан: {filepath.name}")
    except Exception as e:
        print(f"❌ Ошибка при обработке {filepath.name}: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "="*70)
print("✨ Обработка завершена!")
print("="*70)

# Проверяем результаты
try:
    import requests
    r = requests.get("http://qdrant-docling:6333/collections/documents", timeout=5)
    if r.status_code == 200:
        points = r.json()['result']['points_count']
        print(f"\n📊 Всего векторов в базе: {points}")
except Exception as e:
    print(f"\n⚠️  Не удалось проверить количество векторов: {e}")
