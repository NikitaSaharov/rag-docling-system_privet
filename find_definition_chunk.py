import requests

# Ищем чанк с определением нормочаса
filename = "ПИРы №7,№8,№9_08.07.2025_готово.md"

print(f"Ищем определение нормочаса в файле: {filename}\n")

# Проверяем чанки от 0 до 10
for chunk_idx in range(0, 20):
    resp = requests.post(
        "http://qdrant-docling:6333/collections/documents/points/scroll",
        json={
            "filter": {
                "must": [
                    {"key": "filename", "match": {"text": filename}},
                    {"key": "chunk_index", "match": {"value": chunk_idx}}
                ]
            },
            "limit": 1,
            "with_payload": True,
            "with_vector": False
        },
        timeout=10
    )
    
    if resp.status_code == 200:
        points = resp.json()["result"]["points"]
        if points:
            text = points[0]["payload"]["text"]
            
            # Проверяем разные варианты определения
            patterns = [
                "Нормочас  доктора (НЧ) =",
                "**Нормочас",
                "НЧ)** = ВВ доктора"
            ]
            
            for pattern in patterns:
                if pattern in text:
                    print(f"✅ НАЙДЕНО В CHUNK {chunk_idx}!")
                    print(f"   Паттерн: {pattern}")
                    print(f"   Текст (500 символов):")
                    # Найдём позицию pattern
                    pos = text.find(pattern)
                    start = max(0, pos - 100)
                    end = min(len(text), pos + 400)
                    print(f"   ...{text[start:end]}...")
                    print()
                    break
