import sys
sys.path.insert(0, '/app')

from app import search_documents

# Тестируем поиск с новой логикой
query = "Что такое нормочас?"
print(f"Запрос: {query}\n")

results = search_documents(query, limit=30)

print(f"Найдено результатов: {len(results)}\n")

# Ищем чанк с определением
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
        print(f"   Текст (первые 400 символов):")
        print(f"   {text[:400]}...")
        print()
        break
else:
    print("❌ Определение НЕ найдено в результатах")
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
