#!/usr/bin/env python3
"""
Скрипт для поиска по векторной базе знаний
"""

import sys
import os
import requests

OLLAMA_URL = "http://ollama-docling:11434"
QDRANT_URL = "http://qdrant-docling:6333"
COLLECTION_NAME = "documents"

# OpenRouter API
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '')
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek/deepseek-chat"

def get_embedding(text: str, model: str = "nomic-embed-text"):
    """Получает эмбеддинг текста"""
    response = requests.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": model, "prompt": text},
        timeout=60
    )
    return response.json()["embedding"]

def search(query: str, limit: int = 5):
    """Поиск похожих документов"""
    print(f"\n🔍 Поиск: {query}\n")
    
    # Получаем эмбеддинг запроса
    print("⏳ Создание эмбеддинга запроса...")
    query_embedding = get_embedding(query)
    
    # Ищем в Qdrant
    print("⏳ Поиск в векторной базе...\n")
    response = requests.post(
        f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points/search",
        json={
            "vector": query_embedding,
            "limit": limit,
            "with_payload": True
        },
        timeout=30
    )
    
    results = response.json()["result"]
    
    if not results:
        print("❌ Ничего не найдено")
        return []
    
    # Выводим результаты
    print(f"✅ Найдено результатов: {len(results)}\n")
    print("="*80)
    
    for idx, result in enumerate(results, 1):
        score = result["score"]
        payload = result["payload"]
        
        print(f"\n📄 Результат #{idx} (релевантность: {score:.3f})")
        print(f"   Файл: {payload.get('filename', 'N/A')}")
        print(f"   Чанк: {payload.get('chunk_index', 0) + 1}/{payload.get('total_chunks', 1)}")
        print(f"\n   {payload['text'][:300]}...")
        print("\n" + "-"*80)
    
    return results

def ask_llm(query: str, context: str, model: str = "deepseek"):
    """Спрашивает LLM с контекстом"""
    system_prompt = """Ты - помощник по анализу документов.

ПРАВИЛА ОТВЕТА:
1. Пиши КРАТКО и ПО СУТИ - максимум 5-7 предложений
2. Используй ТОЛЬКО информацию из контекста (никаких додомыслов!)
3. Пиши на чистом русском, без иностранных слов
4. НЕ ИСПОЛЬЗУЙ markdown символы (*, #, ###, **)
5. Разбивай ответ на короткие абзацы (2-3 строки)
6. Для списков используй тире и цифры (1., 2., -)
7. В конце предложи 2-3 уточняющих вопроса

ФОРМАТ ОТВЕТА:
Короткий ответ на вопрос.

Основные пункты с пояснениями.

Уточняющие вопросы:
- Вопрос 1?
- Вопрос 2?"""
    
    user_prompt = f"""Контекст:
{context}

Вопрос: {query}

Ответь на основе контекста:"""
    
    print("\n🤖 Генерация ответа (DeepSeek)...\n")
    
    try:
        response = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": DEEPSEEK_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            },
            timeout=120
        )
        response.raise_for_status()
        answer = response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"⚠️  Ошибка DeepSeek API: {e}")
        print("🔄 Fallback на Ollama...\n")
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": "llama3.2",
                "prompt": f"{system_prompt}\n\n{user_prompt}",
                "stream": False
            },
            timeout=120
        )
        answer = response.json()["response"]
    
    print(f"💬 Ответ:\n{answer}\n")
    return answer

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python search.py <ваш_запрос>")
        sys.exit(1)
    
    query = " ".join(sys.argv[1:])
    
    # Ищем релевантные документы
    results = search(query, limit=3)
    
    if results:
        # Объединяем контекст
        context = "\n\n".join([r["payload"]["text"] for r in results])
        
        # Спрашиваем LLM
        ask_llm(query, context)
