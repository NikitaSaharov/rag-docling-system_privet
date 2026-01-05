#!/usr/bin/env python3
"""
Скрипт для создания эмбеддингов с паузами между запросами
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

def get_embedding(text, model="nomic-embed-text", retries=3):
    """Получает эмбеддинг с повторными попытками"""
    for attempt in range(retries):
        try:
            response = requests.post(
                f"{OLLAMA_URL}/api/embeddings",
                json={"model": model, "prompt": text},
                timeout=60
            )
            response.raise_for_status()
            return response.json()["embedding"]
        except Exception as e:
            if attempt < retries - 1:
                print(f"    ⏳ Попытка {attempt + 2}/{retries} через 3 сек...")
                time.sleep(3)
            else:
                print(f"    ❌ Ошибка после {retries} попыток")
                return None

def chunk_text(text, chunk_size=200, overlap=30):
    """Разбивает текст на чанки"""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk:
            chunks.append(chunk)
    return chunks

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
        return False

def process_file(file_path):
    """Обрабатывает файл и создает эмбеддинги"""
    print(f"\n{'='*60}")
    print(f"Обработка: {file_path}")
    print(f"{'='*60}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if not content.strip():
        print("⚠️  Файл пустой")
        return
    
    chunks = chunk_text(content)
    print(f"📄 Создано чанков: {len(chunks)}\n")
    
    filename = Path(file_path).name
    success_count = 0
    
    for idx, chunk in enumerate(chunks):
        chunk_id = hashlib.md5(f"{filename}_{idx}".encode()).hexdigest()
        
        print(f"  [{idx+1}/{len(chunks)}] Чанк {idx+1}...", end=" ")
        
        embedding = get_embedding(chunk)
        
        if embedding:
            metadata = {
                "filename": filename,
                "chunk_index": idx,
                "total_chunks": len(chunks)
            }
            
            if add_to_qdrant(chunk_id, embedding, chunk, metadata):
                print("✅")
                success_count += 1
            else:
                print("❌ Qdrant")
        
        # Пауза между чанками
        if idx < len(chunks) - 1:
            time.sleep(1)
    
    print(f"\n✨ Обработка завершена! Успешно: {success_count}/{len(chunks)}\n")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Использование: python create_embeddings_slow.py <путь_к_файлу>")
        sys.exit(1)
    
    process_file(sys.argv[1])
