import requests

resp = requests.post(
    "http://qdrant-docling:6333/collections/documents/points/scroll",
    json={
        "filter": {
            "must": [{"key": "filename", "match": {"text": "ПИРы №7,№8,№9_08.07.2025_готово.md"}}]
        },
        "limit": 500,
        "with_payload": True,
        "with_vector": False
    },
    timeout=30
)

points = resp.json()["result"]["points"]
print(f"Total chunks: {len(points)}\n")

# Ищем чанки с определением
found = []
for p in points:
    text = p["payload"]["text"]
    if "Нормочас  доктора (НЧ) =" in text or "**Нормочас" in text:
        found.append(p)
        print(f"✅ Chunk {p['payload']['chunk_index']}:")
        # Найдём фрагмент с определением
        if "Нормочас  доктора (НЧ) =" in text:
            pos = text.find("Нормочас  доктора (НЧ) =")
            print(f"   {text[max(0,pos-50):pos+200]}")
        print()

print(f"\nНайдено чанков с определением: {len(found)}")
