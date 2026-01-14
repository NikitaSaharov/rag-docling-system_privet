#!/usr/bin/env python3
"""
Скрипт для проверки всех файлов - какие обработаны, какие нет
"""

import requests
from pathlib import Path
import os

QDRANT_URL = "http://qdrant-docling:6333"
COLLECTION_NAME = "documents"
PROCESSED_DIR = "/shared/processed"

def get_processed_files():
    """Получает список всех обработанных файлов из Qdrant"""
    try:
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
        return {}

def get_all_md_files():
    """Получает список всех .md файлов в директории"""
    md_files = []
    if os.path.exists(PROCESSED_DIR):
        for file in os.listdir(PROCESSED_DIR):
            if file.endswith('.md'):
                md_files.append(file)
    return sorted(md_files)

if __name__ == "__main__":
    print("📚 Проверка всех документов")
    print("=" * 60)
    
    # Получаем все .md файлы
    all_files = get_all_md_files()
    
    if not all_files:
        print("❌ Не найдено .md файлов в /shared/processed")
        print("   Проверьте путь к директории")
    else:
        print(f"📄 Найдено файлов в директории: {len(all_files)}\n")
        
        # Получаем обработанные файлы из Qdrant
        processed = get_processed_files()
        
        print("📊 Статус обработки:\n")
        
        not_processed = []
        partially_processed = []
        fully_processed = []
        
        for filename in all_files:
            if filename in processed:
                info = processed[filename]
                chunks_done = info["chunks"]
                total = info["total_chunks"]
                
                if total > 0 and chunks_done == total:
                    status = "✅"
                    fully_processed.append(filename)
                    print(f"{status} {filename}")
                    print(f"   Обработано: {chunks_done}/{total} чанков (100%)")
                else:
                    status = "⚠️"
                    partially_processed.append(filename)
                    print(f"{status} {filename}")
                    if total > 0:
                        percentage = (chunks_done / total) * 100
                        print(f"   Обработано: {chunks_done}/{total} чанков ({percentage:.1f}%)")
                    else:
                        print(f"   Обработано: {chunks_done} чанков")
            else:
                status = "❌"
                not_processed.append(filename)
                print(f"{status} {filename}")
                print(f"   НЕ обработан")
            print()
        
        # Итоговая статистика
        print("=" * 60)
        print(f"✅ Полностью обработано: {len(fully_processed)}")
        print(f"⚠️  Частично обработано: {len(partially_processed)}")
        print(f"❌ Не обработано: {len(not_processed)}")
        
        if not_processed:
            print(f"\n📝 Необработанные файлы:")
            for f in not_processed:
                print(f"   - {f}")
        
        if partially_processed:
            print(f"\n⚠️  Частично обработанные файлы:")
            for f in partially_processed:
                print(f"   - {f}")
