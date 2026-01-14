#!/usr/bin/env python3
"""
Скрипт для завершения обработки недостающих чанков
"""

import os
import json
import requests
import hashlib
import time
from pathlib import Path

OLLAMA_URL = "http://ollama-docling:11434"
QDRANT_URL = "http://qdrant-docling:6333"
COLLECTION_NAME = "documents"

def get_embedding(text, model="nomic-embed-text", retries=5):
    """Получает эмбеддинг с повторными попытками"""
    import sys
    for attempt in range(retries):
        try:
            sys.stdout.flush()  # Принудительный вывод
            response = requests.post(
                f"{OLLAMA_URL}/api/embeddings",
                json={"model": model, "prompt": text},
                timeout=90  # Увеличенный таймаут
            )
            response.raise_for_status()
            sys.stdout.flush()
            return response.json()["embedding"]
        except Exception as e:
            sys.stdout.flush()
            if attempt < retries - 1:
                wait_time = (attempt + 1) * 3  # Прогрессивное ожидание
                print(f"    ⏳ Попытка {attempt + 2}/{retries} через {wait_time} сек...", flush=True)
                time.sleep(wait_time)
            else:
                print(f"    ❌ Ошибка после {retries} попыток: {e}", flush=True)
                return None

def chunk_text(text, chunk_size=300, overlap=60):
    """Разбивает текст на чанки"""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk:
            chunks.append(chunk)
    return chunks

def get_existing_chunks(filename):
    """Получает множество индексов существующих чанков"""
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
        print(f"Ошибка получения существующих чанков: {e}")
        return set(), 0

def add_to_qdrant(chunk_id, embedding, text, metadata):
    """Добавляет вектор в Qdrant"""
    try:
        response = requests.put(
            f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points",
            json={
                "points": [{
                    "id": chunk_id,
                    "vector": embedding,
                    "payload": {
                        "text": text,
                        **metadata
                    }
                }]
            },
            timeout=30
        )
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"    Ошибка добавления в Qdrant: {e}")
        return False

def complete_missing_chunks(file_path):
    """Доделывает недостающие чанки"""
    import sys
    filename = Path(file_path).name
    
    print(f"\n{'='*60}", flush=True)
    print(f"🔧 Завершение обработки: {filename}", flush=True)
    print(f"{'='*60}", flush=True)
    
    # Получаем существующие чанки
    print("📊 Загрузка информации о существующих чанках из Qdrant...", flush=True)
    existing_indices, total_chunks = get_existing_chunks(filename)
    print(f"✅ Загружено: {len(existing_indices)} чанков из {total_chunks}", flush=True)
    
    if total_chunks == 0:
        print("❌ Не найдено информации о документе в Qdrant")
        return
    
    # Читаем файл
    print(f"📖 Чтение файла: {file_path}...", flush=True)
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print("🔪 Разбиение на чанки...", flush=True)
    chunks = chunk_text(content)
    
    if len(chunks) != total_chunks:
        print(f"⚠️  Предупреждение: количество чанков в файле ({len(chunks)}) не совпадает с метаданными ({total_chunks})")
        total_chunks = len(chunks)
    
    # Находим недостающие
    all_indices = set(range(total_chunks))
    missing_indices = sorted(all_indices - existing_indices)
    
    if not missing_indices:
        print("✅ Все чанки уже обработаны!")
        return
    
    print(f"📊 Всего чанков: {total_chunks}")
    print(f"✅ Уже обработано: {len(existing_indices)}")
    print(f"❌ Недостаёт: {len(missing_indices)}")
    print(f"\n🔄 Обработка недостающих чанков...\n")
    
    success_count = 0
    
    import sys
    for idx in missing_indices:
        if idx >= len(chunks):
            print(f"  ⚠️  Чанк #{idx} вне диапазона", flush=True)
            continue
        
        chunk = chunks[idx]
        chunk_id = hashlib.md5(f"{filename}_{idx}".encode()).hexdigest()
        
        current_num = len(existing_indices) + success_count + 1
        print(f"  [{current_num}/{total_chunks}] Чанк #{idx}...", end=" ", flush=True)
        
        embedding = get_embedding(chunk)
        
        if embedding:
            metadata = {
                "filename": filename,
                "chunk_index": idx,
                "total_chunks": total_chunks
            }
            
            if add_to_qdrant(chunk_id, embedding, chunk, metadata):
                print("✅", flush=True)
                success_count += 1
            else:
                print("❌ Qdrant", flush=True)
        else:
            print("❌ Embedding", flush=True)
        
        # Пауза между чанками
        if idx < missing_indices[-1]:  # Не пауза после последнего
            time.sleep(2)  # Увеличенная пауза
    
    print(f"\n✨ Завершено! Обработано недостающих чанков: {success_count}/{len(missing_indices)}")
    print(f"📊 Итого обработано: {len(existing_indices) + success_count}/{total_chunks}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Использование: python complete_missing_chunks.py <путь_к_файлу>")
        sys.exit(1)
    
    complete_missing_chunks(sys.argv[1])
