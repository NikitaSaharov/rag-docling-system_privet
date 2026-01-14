#!/usr/bin/env python3
"""
Скрипт для проверки, какие документы уже векторизованы в Qdrant
"""

import requests
import json

QDRANT_URL = "http://qdrant-docling:6333"
COLLECTION_NAME = "documents"

def get_processed_files():
    """Получает список всех обработанных файлов из Qdrant"""
    try:
        # Получаем все точки из коллекции
        response = requests.post(
            f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points/scroll",
            json={
                "limit": 10000,
                "with_payload": True,
                "with_vector": False
            },
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        # Извлекаем уникальные имена файлов
        files_dict = {}
        for point in data.get("result", {}).get("points", []):
            filename = point.get("payload", {}).get("filename")
            if filename:
                if filename not in files_dict:
                    files_dict[filename] = {
                        "chunks": 0,
                        "last_chunk_index": 0,
                        "total_chunks": 0
                    }
                files_dict[filename]["chunks"] += 1
                chunk_idx = point.get("payload", {}).get("chunk_index", 0)
                total = point.get("payload", {}).get("total_chunks", 0)
                if chunk_idx > files_dict[filename]["last_chunk_index"]:
                    files_dict[filename]["last_chunk_index"] = chunk_idx
                if total > files_dict[filename]["total_chunks"]:
                    files_dict[filename]["total_chunks"] = total
        
        return files_dict
    except Exception as e:
        print(f"Ошибка подключения к Qdrant: {e}")
        return None

if __name__ == "__main__":
    print("🔍 Проверка обработанных документов в Qdrant...")
    print("=" * 60)
    
    files = get_processed_files()
    
    if files is None:
        print("❌ Не удалось подключиться к Qdrant")
        print("   Убедитесь, что контейнеры запущены")
    elif not files:
        print("📭 Коллекция пуста - ни один документ не векторизован")
    else:
        print(f"📚 Найдено документов: {len(files)}\n")
        
        # Сортируем по последнему индексу чанка (последний обработанный)
        sorted_files = sorted(files.items(), key=lambda x: x[1]["last_chunk_index"], reverse=True)
        
        for filename, info in sorted_files:
            total_chunks = info["total_chunks"]
            chunks_done = info["chunks"]
            last_idx = info["last_chunk_index"]
            
            if total_chunks > 0:
                percentage = (chunks_done / total_chunks) * 100
                status = "✅" if chunks_done == total_chunks else "⚠️"
                print(f"{status} {filename}")
                print(f"   Прогресс: {chunks_done}/{total_chunks} чанков ({percentage:.1f}%)")
                print(f"   Последний индекс: {last_idx}")
            else:
                status = "⚠️"
                print(f"{status} {filename}")
                print(f"   Чанков: {chunks_done} (последний индекс: {last_idx})")
            print()
        
        # Определяем последний файл
        if sorted_files:
            last_file = sorted_files[0]
            print("=" * 60)
            print(f"📌 Последний обработанный документ: {last_file[0]}")
            print(f"   Обработано чанков: {last_file[1]['chunks']}")
            if last_file[1]['total_chunks'] > 0:
                print(f"   Всего должно быть: {last_file[1]['total_chunks']}")
                if last_file[1]['chunks'] < last_file[1]['total_chunks']:
                    print(f"   ⚠️  Обработка НЕ завершена!")
