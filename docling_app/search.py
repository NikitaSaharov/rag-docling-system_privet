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
    """Гибридный поиск: semantic + keyword + boosting"""
    print(f"\n🔍 Поиск: {query}\n")
    
    # Получаем эмбеддинг запроса
    print("⌛ Создание эмбеддинга запроса...")
    query_embedding = get_embedding(query)
    
    # Ищем в Qdrant
    print("⌛ Поиск в векторной базе...\n")
    
    search_params = {
        "vector": query_embedding,
        "limit": limit * 2,
        "with_payload": True
    }
    
    response = requests.post(
        f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points/search",
        json=search_params,
        timeout=30
    )
    
    results = response.json()["result"]
    
    if not results:
        print("❌ Ничего не найдено")
        return []
    
    # Re-ranking: boost для маленьких документов
    for result in results:
        total_chunks = result["payload"]["total_chunks"]
        
        # Small doc boost (<100 chunks)
        if total_chunks < 100:
            result["score"] += 0.05
    
    # Пересортировка
    results.sort(key=lambda x: x["score"], reverse=True)
    results = results[:limit]
    
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
    system_prompt = """Ты - эксперт-аналитик документов. Твоя задача - давать РАЗВЕРНУТЫЕ и ТОЧНЫЕ ответы.

КРИТИЧЕСКИ ВАЖНО - ИЗБЕГАЙ ГАЛЛЮЦИНАЦИЙ:
1. Используй ТОЛЬКО информацию из контекста
2. Если информации нет - НЕ ГОВОРИ "в контексте нет". Скажи: "На данный момент у меня недостаточно информации, чтобы ответить на ваш вопрос в такой формулировке. Возможно, вам помогут эти варианты вопросов:" и предложи 3-4 переформулировки
3. Цитируй точные формулировки из документа
4. Указывай источник (из какого документа)

ФОРМАТ ОТВЕТА:
1. Полный развернутый ответ (10-15 предложений)
2. Раскрывай все аспекты вопроса
3. Приводи примеры и детали из контекста
4. Структурируй ответ по пунктам
5. НЕ ИСПОЛЬЗУЙ markdown (*, #, **)
6. Используй тире и цифры для списков
7. В конце: 2-3 уточняющих вопроса"""
    
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
        try:
            response = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": "llama3.2",
                    "prompt": f"{system_prompt}\n\n{user_prompt}",
                    "stream": False
                },
                timeout=180
            )
            answer = response.json()["response"]
        except Exception as e2:
            answer = f"Ошибка генерации ответа: {str(e2)}"
    
    print(f"💬 Ответ:\n{answer}\n")
    return answer

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python search.py <ваш_запрос>")
        sys.exit(1)
    
    query = " ".join(sys.argv[1:])
    
    # Ищем релевантные документы
    results = search(query, limit=10)
    
    if results:
        # Объединяем контекст
        context = "\n\n".join([r["payload"]["text"] for r in results])
        
        # Спрашиваем LLM
        ask_llm(query, context)
