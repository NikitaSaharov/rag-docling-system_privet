#!/usr/bin/env python3
"""
Скрипт для создания эмбеддингов из обработанных документов и загрузки в Qdrant
"""

import os
import json
import requests
import hashlib
from pathlib import Path

OLLAMA_URL = "http://ollama-docling:11434"
QDRANT_URL = "http://qdrant-docling:6333"
COLLECTION_NAME = "documents"

def get_embedding(text: str, model: str = "nomic-embed-text"):
    """Получает эмбеддинг текста через Ollama"""
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": model, "prompt": text},
            timeout=60
        )
        response.raise_for_status()
        return response.json()["embedding"]
    except Exception as e:
        print(f"Ошибка получения эмбеддинга: {e}")
        return None

def chunk_text(text: str, chunk_size: int = 200, overlap: int = 50):
    """Разбивает текст на чанки с перекрытием (оптимизировано для формул и точного поиска)"""
    # Уменьшенный размер для более точного семантического поиска
    # Overlap 25% для сохранения контекста на границах
    words = text.split()
    chunks = []
    
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk:
            chunks.append(chunk)
    
    return chunks

def add_to_qdrant(doc_id: str, embedding: list, text: str, metadata: dict):
    """Добавляет вектор в Qdrant"""
    try:
        response = requests.put(
            f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points",
            json={
                "points": [{
                    "id": doc_id,
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
        print(f"Ошибка добавления в Qdrant: {e}")
        return False

def process_file(file_path: str):
    """Обрабатывает файл и создает эмбеддинги"""
    print(f"\n{'='*60}")
    print(f"Обработка: {file_path}")
    print(f"{'='*60}")
    
    # Читаем файл
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if not content.strip():
        print("⚠️  Файл пустой, пропускаем")
        return
    
    # Разбиваем на чанки
    chunks = chunk_text(content)
    print(f"📄 Создано чанков: {len(chunks)}")
    
    filename = Path(file_path).name
    
    # Обрабатываем каждый чанк
    for idx, chunk in enumerate(chunks):
        # Создаем уникальный ID
        chunk_id = hashlib.md5(f"{filename}_{idx}".encode()).hexdigest()
        
        # Получаем эмбеддинг
        print(f"  [{idx+1}/{len(chunks)}] Создание эмбеддинга... ", end="")
        embedding = get_embedding(chunk)
        
        if embedding:
            # Добавляем в Qdrant
            metadata = {
                "filename": filename,
                "chunk_index": idx,
                "total_chunks": len(chunks)
            }
            
            if add_to_qdrant(chunk_id, embedding, chunk, metadata):
                print("✅")
            else:
                print("❌")
        else:
            print("❌")
    
    print(f"✨ Обработка завершена!\n")

def process_directory(input_dir: str):
    """Обрабатывает все markdown файлы в директории"""
    files = list(Path(input_dir).glob("*.md"))
    
    if not files:
        print(f"⚠️  Нет .md файлов в {input_dir}")
        return
    
    print(f"\n🚀 Найдено файлов для обработки: {len(files)}")
    
    for file_path in files:
        process_file(str(file_path))

if __name__ == "__main__":
    import sys
    
    input_path = sys.argv[1] if len(sys.argv) > 1 else "/shared/processed"
    
    if os.path.isfile(input_path):
        process_file(input_path)
    else:
        process_directory(input_path)
