import requests
import sys

# Получаем эмбеддинг для запроса
def get_embedding(text):
    try:
        response = requests.post(
            "http://ollama-docling:11434/api/embeddings",
            json={"model": "nomic-embed-text", "prompt": text},
            timeout=60
        )
        return response.json()["embedding"]
    except Exception as e:
        print(f"Ошибка получения эмбеддинга: {e}")
        return None

# Ищем в Qdrant
query = "Что такое нормочас?"
print(f"Запрос: {query}")
print("Получаем эмбеддинг...")

embedding = get_embedding(query)
if not embedding:
    sys.exit(1)

print(f"Эмбеддинг получен, размер: {len(embedding)}")

# Поиск в Qdrant
print("\nПоиск в Qdrant...")
response = requests.post(
    "http://qdrant-docling:6333/collections/documents/points/search",
    json={
        "vector": embedding,
        "limit": 10,
        "with_payload": True
    },
    timeout=30
)

results = response.json()["result"]
print(f"Найдено результатов: {len(results)}\n")

for i, result in enumerate(results[:5], 1):
    score = result["score"]
    text = result["payload"]["text"][:200]  # Первые 200 символов
    filename = result["payload"]["filename"]
    chunk_idx = result["payload"]["chunk_index"]
    
    print(f"{i}. Score: {score:.3f}")
    print(f"   Файл: {filename} (chunk {chunk_idx})")
    print(f"   Текст: {text}...")
    print()
