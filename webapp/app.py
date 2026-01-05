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
    """Поиск похожих документов"""
    try:
        query_embedding = get_embedding(query)
        if not query_embedding:
            return []
        
        response = requests.post(
            f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points/search",
            json={
                "vector": query_embedding,
                "limit": limit,
                "with_payload": True
            },
            timeout=30
        )
        return response.json()["result"]
    except Exception as e:
        print(f"Ошибка поиска: {e}")
        return []

def ask_llm(query, context, model="deepseek"):
    """Генерирует ответ с помощью LLM"""
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
    
    try:
        # Используем DeepSeek через OpenRouter
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
        # Fallback на Ollama если API не работает
        try:
            fallback_response = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": "llama3.2",
                    "prompt": f"{system_prompt}\n\n{user_prompt}",
                    "stream": False
                },
                timeout=120
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
    """Поиск по векторной базе"""
    data = request.json
    query = data.get('query', '')
    
    if not query:
        return jsonify({'error': 'Запрос пустой'}), 400
    
    # Поиск документов
    results = search_documents(query, limit=5)
    
    if not results:
        return jsonify({
            'answer': 'Не найдено релевантных документов',
            'sources': []
        })
    
    # Формируем контекст с указанием источника
    context_parts = []
    for r in results:
        filename = r["payload"]["filename"]
        text = r["payload"]["text"]
        context_parts.append(f"[Источник: {filename}]\n{text}")
    
    context = "\n\n".join(context_parts)
    sources = [{
        'filename': r["payload"]["filename"],
        'text': r["payload"]["text"][:200] + "...",
        'score': r["score"]
    } for r in results]
    
    # Генерируем ответ
    answer = ask_llm(query, context)
    
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
