#!/usr/bin/env python3
"""
Скрипт для поиска недостающих чанков в документе
"""

import requests
import hashlib
from pathlib import Path

QDRANT_URL = "http://qdrant-docling:6333"
COLLECTION_NAME = "documents"

def get_existing_chunks(filename):
    """Получает список индексов существующих чанков"""
    try:
        response = requests.post(
            f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points/scroll",
            json={
                "limit": 10000,
                "with_payload": True,
                "filter": {
                    "must": [{
                        "key": "filename",
                        "match": {"value": filename}
                    }]
                }
            },
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        existing_indices = set()
        total_chunks = 0
        
        for point in data.get("result", {}).get("points", []):
            payload = point.get("payload", {})
            idx = payload.get("chunk_index")
            if idx is not None:
                existing_indices.add(idx)
            total = payload.get("total_chunks", 0)
            if total > total_chunks:
                total_chunks = total
        
        return existing_indices, total_chunks
    except Exception as e:
        print(f"Ошибка: {e}")
        return set(), 0

def chunk_text(text, chunk_size=300, overlap=60):
    """Разбивает текст на чанки"""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk:
            chunks.append(chunk)
    return chunks

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Использование: python find_missing_chunks.py <путь_к_файлу>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    filename = Path(file_path).name
    
    print(f"🔍 Поиск недостающих чанков для: {filename}")
    print("=" * 60)
    
    # Получаем существующие чанки
    existing_indices, total_chunks = get_existing_chunks(filename)
    
    if total_chunks == 0:
        print("❌ Не найдено информации о документе в Qdrant")
        sys.exit(1)
    
    print(f"📊 Всего чанков должно быть: {total_chunks}")
    print(f"✅ Обработано: {len(existing_indices)}")
    
    # Находим недостающие
    all_indices = set(range(total_chunks))
    missing_indices = sorted(all_indices - existing_indices)
    
    if not missing_indices:
        print("✅ Все чанки обработаны!")
    else:
        print(f"❌ Недостающие чанки: {len(missing_indices)}")
        print(f"\n📋 Список недостающих индексов:")
        
        # Показываем первые и последние
        if len(missing_indices) <= 20:
            print(f"   {missing_indices}")
        else:
            print(f"   Первые 10: {missing_indices[:10]}")
            print(f"   ...")
            print(f"   Последние 10: {missing_indices[-10:]}")
        
        # Читаем файл и показываем содержимое недостающих чанков
        print(f"\n📄 Читаем файл для анализа недостающих чанков...")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            chunks = chunk_text(content)
            
            print(f"\n📝 Содержимое недостающих чанков:")
            print("=" * 60)
            
            for idx in missing_indices[:5]:  # Показываем первые 5
                if idx < len(chunks):
                    chunk_text_preview = chunks[idx][:200].replace('\n', ' ')
                    print(f"\nЧанк #{idx}:")
                    print(f"  {chunk_text_preview}...")
            
            if len(missing_indices) > 5:
                print(f"\n... и ещё {len(missing_indices) - 5} чанков")
            
        except Exception as e:
            print(f"⚠️  Не удалось прочитать файл: {e}")
