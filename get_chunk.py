import requests

# Получаем чанк 45 из файла "ПИРы №10 и СУ_09.07.2025_готово.md"
response = requests.post(
    "http://qdrant-docling:6333/collections/documents/points/scroll",
    json={
        "filter": {
            "must": [
                {"key": "filename", "match": {"text": "ПИРы №10 и СУ_09.07.2025_готово.md"}},
                {"key": "chunk_index", "match": {"value": 45}}
            ]
        },
        "limit": 1,
        "with_payload": True,
        "with_vector": False
    },
    timeout=10
)

if response.status_code == 200:
    points = response.json()["result"]["points"]
    if points:
        text = points[0]["payload"]["text"]
        print("=== CHUNK 45 ===")
        print(text)
        print("\n" + "="*50)
        
        # Проверим также соседние чанки
        for idx in [44, 46]:
            resp = requests.post(
                "http://qdrant-docling:6333/collections/documents/points/scroll",
                json={
                    "filter": {
                        "must": [
                            {"key": "filename", "match": {"text": "ПИРы №10 и СУ_09.07.2025_готово.md"}},
                            {"key": "chunk_index", "match": {"value": idx}}
                        ]
                    },
                    "limit": 1,
                    "with_payload": True,
                    "with_vector": False
                },
                timeout=10
            )
            if resp.status_code == 200:
                pts = resp.json()["result"]["points"]
                if pts:
                    print(f"\n=== CHUNK {idx} ===")
                    print(pts[0]["payload"]["text"])
    else:
        print("Чанк не найден")
else:
    print(f"Ошибка: {response.status_code}")
