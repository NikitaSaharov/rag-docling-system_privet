import requests

# Получаем эмбеддинг
def get_embedding(text):
    response = requests.post(
        "http://ollama-docling:11434/api/embeddings",
        json={"model": "nomic-embed-text", "prompt": text},
        timeout=60
    )
    return response.json()["embedding"]

query = "Что такое нормочас?"
print(f"Запрос: {query}\n")

embedding = get_embedding(query)

# Поиск в Qdrant с большим лимитом
response = requests.post(
    "http://qdrant-docling:6333/collections/documents/points/search",
    json={
        "vector": embedding,
        "limit": 20,
        "with_payload": True
    },
    timeout=30
)

results = response.json()["result"]

print(f"Найдено результатов: {len(results)}\n")

# Ищем чанк с определением (строки 1162-1169 из файла №7,№8,№9)
for i, result in enumerate(results, 1):
    filename = result["payload"]["filename"]
    chunk_idx = result["payload"]["chunk_index"]
    score = result["score"]
    text = result["payload"]["text"]
    
    # Проверяем, это ли наш чанк с определением
    if "НЧ)** = ВВ доктора" in text or "Нормочас  доктора (НЧ) =" in text:
        print(f"✅ НАШЛИ ОПРЕДЕЛЕНИЕ! Позиция: #{i}")
        print(f"   Score: {score:.3f}")
        print(f"   Файл: {filename} (chunk {chunk_idx})")
        print(f"   Текст (первые 300 символов):")
        print(f"   {text[:300]}...")
        print()
        break
else:
    print("❌ Определение НЕ найдено в топ-20 результатах")
    print("\nПоказываем топ-5 результатов:\n")
    for i, result in enumerate(results[:5], 1):
        filename = result["payload"]["filename"]
        chunk_idx = result["payload"]["chunk_index"]
        score = result["score"]
        text = result["payload"]["text"][:200]
        
        print(f"{i}. Score: {score:.3f}")
        print(f"   Файл: {filename} (chunk {chunk_idx})")
        print(f"   Текст: {text}...")
        print()
