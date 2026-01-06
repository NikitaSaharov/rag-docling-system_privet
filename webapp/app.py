from flask import Flask, render_template, request, jsonify, send_from_directory
import requests
import os
import hashlib
from pathlib import Path
from werkzeug.utils import secure_filename
import json
import sys
sys.path.insert(0, '/docling_app')

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/documents'
app.config['PROCESSED_FOLDER'] = '/shared/processed'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max

OLLAMA_URL = "http://ollama-docling:11434"
QDRANT_URL = "http://qdrant-docling:6333"
COLLECTION_NAME = "documents"

# OpenRouter API настройки
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '')
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek/deepseek-chat"

ALLOWED_EXTENSIONS = {'pdf', 'docx', 'pptx', 'txt', 'md', 'doc'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_embedding(text, model="nomic-embed-text"):
    """Получает эмбеддинг текста"""
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": model, "prompt": text},
            timeout=60
        )
        return response.json()["embedding"]
    except Exception as e:
        print(f"Ошибка получения эмбеддинга: {e}")
        return None

def search_documents(query, limit=3):
    """Гибридный поиск: semantic + keyword matching + boosting"""
    try:
        query_lower = query.lower()
        
        # Проверяем, упомянут ли конкретный документ
        doc_filters = {
            'справочник': 'Справочник Мудрого Руководителя',
            'золотой стандарт': 'Золотой Стандарт Аудита',
            'директор': 'Директор'
        }
        
        # Если упомянут документ - фильтруем по нему
        search_filter = None
        for keyword, doc_pattern in doc_filters.items():
            if keyword in query_lower:
                search_filter = {
                    "must": [{
                        "key": "filename",
                        "match": {"text": doc_pattern}
                    }]
                }
                print(f"Forced filter: {doc_pattern}")
                break
        
        # 1. Semantic search
        query_embedding = get_embedding(query)
        if not query_embedding:
            return []
        
        search_params = {
            "vector": query_embedding,
            "limit": limit * 2 if not search_filter else limit,  # Если фильтр - не нужно больше
            "with_payload": True
        }
        if search_filter:
            search_params["filter"] = search_filter
        
        response = requests.post(
            f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points/search",
            json=search_params,
            timeout=30
        )
        results = response.json()["result"]
        
        # 2. Keyword matching - ищем упоминания документов в запросе
        query_lower = query.lower()
        keyword_boosts = {
            'справочник': ('Справочник', 0.3),  # Сильный boost
            'золотой стандарт': ('Золотой Стандарт', 0.3),
            'ссп': ('Справочник', 0.2),  # Аббревиатура
            'пир': ('ПИР', 0.05),
            'директор': ('Директор', 0.1)
        }
        
        # 3. Re-ranking: boost scores
        for result in results:
            filename = result["payload"]["filename"]
            total_chunks = result["payload"]["total_chunks"]
            
            # Boost для keyword match
            for keyword, (file_pattern, boost) in keyword_boosts.items():
                if keyword in query_lower and file_pattern in filename:
                    result["score"] += boost
                    print(f"Keyword boost: {filename} +{boost}")
            
            # Boost для маленьких документов (<100 chunks)
            if total_chunks < 100:
                size_boost = 0.05
                result["score"] += size_boost
                print(f"Small doc boost: {filename} ({total_chunks} chunks) +{size_boost}")
        
        # 4. Пересортировка по новому score
        results.sort(key=lambda x: x["score"], reverse=True)
        
        return results[:limit]
    except Exception as e:
        print(f"Ошибка поиска: {e}")
        return []

def ask_llm(query, context, model="deepseek"):
    """Генерирует ответ с помощью LLM"""
    system_prompt = """Ты - эксперт-аналитик документов. Твоя задача - давать РАЗВЕРНУТЫЕ и ТОЧНЫЕ ответы.

КРИТИЧЕСКИ ВАЖНО - ИЗБЕГАЙ ГАЛЛЮЦИНАЦИЙ:
1. Используй ТОЛЬКО информацию из контекста
2. Если информации нет - так и скажи, НЕ ДОМЫШЛЯЙ
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
    
    try:
        # Используем DeepSeek через OpenRouter (качественнее)
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
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"Ошибка DeepSeek API: {e}")
        # Fallback на бесплатный Ollama
        try:
            print("Переключение на Ollama...")
            fallback_response = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": "llama3.2",
                    "prompt": f"{system_prompt}\n\n{user_prompt}",
                    "stream": False
                },
                timeout=180
            )
            return fallback_response.json()["response"]
        except:
            return f"Ошибка генерации ответа: {str(e)}"

def chunk_text(text, chunk_size=500, overlap=50):
    """Разбивает текст на чанки"""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk:
            chunks.append(chunk)
    return chunks

def add_to_qdrant(chunk_id, embedding, text, metadata):
    """Добавляет вектор в Qdrant"""
    try:
        response = requests.put(
            f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points",
            json={
                "points": [{
                    "id": chunk_id,
                    "vector": embedding,
                    "payload": {
                        "text": text,
                        **metadata
                    }
                }]
            },
            timeout=30
        )
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Ошибка добавления в Qdrant: {e}")
        return False

def process_and_embed_document(filepath):
    """Обрабатывает документ и создает эмбеддинги"""
    try:
        filename = Path(filepath).name
        file_ext = Path(filepath).suffix.lower()
        
        # Для TXT и MD - просто читаем
        if file_ext in ['.txt', '.md']:
            with open(filepath, 'r', encoding='utf-8') as f:
                text = f.read()
        else:
            # Для PDF/DOCX - сообщаем что нужно использовать CLI
            return False, "Для PDF/DOCX используйте: docker exec docling-docling python /app/process_documents.py /documents/ИМЯ_ФАЙЛА"
        
        if not text.strip():
            return False, "Файл пустой"
        
        # Разбиваем на чанки
        words = text.split()
        chunks = []
        chunk_size = 500
        overlap = 50
        
        for i in range(0, len(words), chunk_size - overlap):
            chunk = " ".join(words[i:i + chunk_size])
            if chunk:
                chunks.append(chunk)
        
        # Создаем эмбеддинги и загружаем в Qdrant
        for idx, chunk in enumerate(chunks):
            chunk_id = hashlib.md5(f"{filename}_{idx}".encode()).hexdigest()
            
            # Получаем эмбеддинг
            embedding = get_embedding(chunk)
            if not embedding:
                continue
            
            # Добавляем в Qdrant
            metadata = {
                "filename": filename,
                "chunk_index": idx,
                "total_chunks": len(chunks)
            }
            
            requests.put(
                f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points",
                json={
                    "points": [{
                        "id": chunk_id,
                        "vector": embedding,
                        "payload": {
                            "text": chunk,
                            **metadata
                        }
                    }]
                },
                timeout=30
            )
        
        return True, f"Обработано {len(chunks)} чанков"
    except Exception as e:
        return False, str(e)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Загрузка и обработка документа"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'Файл не найден'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Файл не выбран'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Неподдерживаемый формат файла'}), 400
        
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Обработка документа и создание эмбеддингов
        success, message = process_and_embed_document(filepath)
        if not success:
            print(f"ERROR: {message}")
            return jsonify({'error': message}), 500
        
        return jsonify({
            'success': True,
            'message': f'Документ {filename} успешно добавлен в базу знаний. {message}'
        })
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"EXCEPTION in upload: {error_trace}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/search', methods=['POST'])
def search():
    """Поиск по векторной базе с учетом истории чата"""
    data = request.json
    query = data.get('query', '')
    history = data.get('history', [])  # История чата
    
    if not query:
        return jsonify({'error': 'Запрос пустой'}), 400
    
    # Если есть история - добавляем контекст предыдущего вопроса
    if history:
        # Берем последний вопрос-ответ для контекста
        last_qa = history[-1]
        query_with_context = f"Предыдущий вопрос: {last_qa['question']}\nПредыдущий ответ: {last_qa['answer'][:300]}...\n\nТекущий вопрос: {query}"
    else:
        query_with_context = query
    
    # Поиск документов
    results = search_documents(query, limit=10)
    
    if not results:
        return jsonify({
            'answer': 'Не найдено релевантных документов',
            'sources': []
        })
    
    # Формируем контекст с указанием источника
    # Приоритет Справочнику - ставим его чанки в начало
    spravochnik_parts = []
    other_parts = []
    
    for r in results:
        filename = r["payload"]["filename"]
        text = r["payload"]["text"]
        context_entry = f"[Источник: {filename}]\n{text}"
        
        if "Справочник" in filename:
            spravochnik_parts.append(context_entry)
        else:
            other_parts.append(context_entry)
    
    # Справочник в начале, остальные - потом
    context = "\n\n".join(spravochnik_parts + other_parts)
    sources = [{
        'filename': r["payload"]["filename"],
        'text': r["payload"]["text"][:200] + "...",
        'score': r["score"]
    } for r in results]
    
    # Генерируем ответ с учетом истории
    answer = ask_llm(query_with_context, context)
    
    return jsonify({
        'answer': answer,
        'sources': sources
    })

@app.route('/api/documents', methods=['GET'])
def list_documents():
    """Список документов в базе"""
    try:
        response = requests.get(
            f"{QDRANT_URL}/collections/{COLLECTION_NAME}",
            timeout=10
        )
        data = response.json()
        
        # Получаем все документы
        points_response = requests.post(
            f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points/scroll",
            json={"limit": 100, "with_payload": True},
            timeout=10
        )
        
        points = points_response.json()["result"]["points"]
        
        # Уникальные файлы
        files = {}
        for point in points:
            filename = point["payload"]["filename"]
            if filename not in files:
                files[filename] = {
                    'filename': filename,
                    'chunks': point["payload"]["total_chunks"]
                }
        
        return jsonify({
            'total_vectors': data["result"]["points_count"],
            'documents': list(files.values())
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def stats():
    """Статистика системы"""
    try:
        qdrant_resp = requests.get(f"{QDRANT_URL}/collections/{COLLECTION_NAME}", timeout=10)
        qdrant_data = qdrant_resp.json()
        
        return jsonify({
            'qdrant': {
                'vectors_count': qdrant_data["result"]["points_count"],
                'status': qdrant_data["result"]["status"]
            },
            'ollama': {
                'status': 'online'
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
