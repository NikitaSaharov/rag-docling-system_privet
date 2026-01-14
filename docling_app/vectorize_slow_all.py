#!/usr/bin/env python3
"""Векторизация через медленный скрипт (экономит память)"""
import sys
import os
sys.path.insert(0, '/app')

from create_embeddings_slow import process_file
from pathlib import Path

processed_dir = Path("/shared/processed")
files = list(processed_dir.glob("ПИРы*.md"))

if not files:
    print("⚠️  Файлы не найдены")
    sys.exit(1)

print("="*70)
print(f"🔄 Векторизация {len(files)} файлов (медленный режим)")
print("="*70)

for i, filepath in enumerate(files, 1):
    print(f"\n[{i}/{len(files)}] {filepath.name}")
    print("-"*70)
    try:
        process_file(str(filepath))
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

print("\n✨ Готово!")
