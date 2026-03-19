from flask import Flask, render_template, request, jsonify, send_from_directory
import requests
import os
import hashlib
from pathlib import Path
from werkzeug.utils import secure_filename
import json
import sys
sys.path.insert(0, '/docling_app')

# Импорты для админ-панели и Telegram бота
import database as db
from admin_routes import admin_bp
from auth_routes import auth_bp, jwt_required
from chat_routes import chat_bp
from examples_loader import load_examples, format_examples_for_prompt

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', os.urandom(24))

# CORS — разрешаем только наш домен
from flask_cors import CORS
CORS(app, origins=['https://gdgbaza.ru', 'https://www.gdgbaza.ru'], supports_credentials=True)

# Rate limiter
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
limiter = Limiter(get_remote_address, app=app, default_limits=[], storage_uri='memory://')

# Инициализируем БД при импорте (важно для Gunicorn, который не выполняет __main__)
db.init_db()

# Session configuration
from datetime import timedelta
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=3)  # Admin session lasts 3 hours

# Регистрируем Blueprint
app.register_blueprint(admin_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(chat_bp)

# Rate limits на аутентификацию (защита от brute-force)
limiter.limit('10/minute')(app.view_functions['auth.login'])
limiter.limit('5/hour')(app.view_functions['auth.register'])
limiter.limit('10/minute')(app.view_functions['auth.verify_email'])
limiter.limit('5/minute')(app.view_functions['auth.resend_verification'])
limiter.limit('5/minute')(app.view_functions['auth.forgot_password'])
limiter.limit('10/minute')(app.view_functions['auth.verify_password_reset_code'])
limiter.limit('10/minute')(app.view_functions['admin.admin_login'])

app.config['UPLOAD_FOLDER'] = '/documents'
app.config['PROCESSED_FOLDER'] = '/shared/processed'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max

import re as _re

def _clean_llm_response(text: str) -> str:
    """Strip markdown heading markers and raw HTML tags that LLM sometimes adds."""
    # '### Заголовок' -> 'Заголовок'
    text = _re.sub(r'^#{1,6}\s+', '', text, flags=_re.MULTILINE)
    # Strip raw HTML tags: <b>, </b>, <i>, </i>, <br>, etc.
    text = _re.sub(r'</?(?:b|i|em|strong|u|br|p|div|span)[^>]*>', '', text, flags=_re.IGNORECASE)
    # Remove lone '---' dividers
    text = _re.sub(r'^---+\s*$', '', text, flags=_re.MULTILINE)
    # Collapse 3+ blank lines to 2
    text = _re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

# === Детекция "demand" сообщений ("Ответь!", "Дай ответ" и т.п.) ===
_DEMAND_PATTERNS = [
    r'^\s*отв[её]ть',                 # ответь / ответь!
    r'^\s*ну\s+отв[её]ть',            # ну ответь
    r'дай\s+ответ',                    # дай ответ
    r'где\s+ответ',                    # где ответ
    r'где\s+мой\s+ответ',             # где мой ответ
    r'почему\s+не\s+отвеча',          # почему не отвечаешь
    r'отвечай',                        # отвечай!
    r'ответь\s+на\s+(заданный|мой|предыдущий)',  # ответь на заданный вопрос
    r'^\s*ответ\s*[!?.]*\s*$',        # просто "Ответ" / "Ответ!"
]
_DEMAND_RE = _re.compile('|'.join(_DEMAND_PATTERNS), _re.IGNORECASE)

def is_demand_message(text: str) -> bool:
    """Проверяет, является ли сообщение требованием дать ответ на предыдущий вопрос"""
    return bool(_DEMAND_RE.search(text.strip()))

OLLAMA_URL = "http://ollama:11434"
QDRANT_URL = "http://qdrant:6333"
COLLECTION_NAME = os.getenv('QDRANT_COLLECTION', 'Документы')

# Polza.ai API настройки (OpenAI-совместимый endpoint)
POLZA_API_KEY = os.getenv('POLZA_API_KEY', '')
POLZA_URL = "https://api.polza.ai/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

# Embedding API (тот же Polza.ai, OpenAI-compatible)
EMBEDDING_API_URL = os.getenv('EMBEDDING_API_URL', 'https://api.polza.ai/v1')
EMBEDDING_API_KEY = os.getenv('EMBEDDING_API_KEY', '') or os.getenv('POLZA_API_KEY', '')
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'baai/bge-m3')
EMBEDDING_VECTOR_SIZE = int(os.getenv('EMBEDDING_VECTOR_SIZE', '1024'))

# Speech-to-Text (Polza.ai)
POLZA_STT_API_KEY = os.getenv('POLZA_STT_API_KEY', '')
POLZA_STT_URL = "https://api.polza.ai/v1/audio/transcriptions"
POLZA_STT_MODEL = "openai/gpt-4o-mini-transcribe"

ALLOWED_EXTENSIONS = {'pdf', 'docx', 'pptx', 'txt', 'md', 'doc'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_embedding(text, model=None):
    """Получает эмбеддинг текста через Polza.ai API (OpenAI-compatible)"""
    try:
        response = requests.post(
            f"{EMBEDDING_API_URL}/embeddings",
            headers={
                "Authorization": f"Bearer {EMBEDDING_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": model or EMBEDDING_MODEL,
                "input": text,
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["data"][0]["embedding"]
    except Exception as e:
        print(f"Ошибка получения эмбеддинга: {e}")
        return None

def ensure_collection():
    """Создаёт Qdrant коллекцию с правильной размерностью если её нет"""
    try:
        check = requests.get(f"{QDRANT_URL}/collections/{COLLECTION_NAME}", timeout=5)
        if check.status_code == 200:
            return
        response = requests.put(
            f"{QDRANT_URL}/collections/{COLLECTION_NAME}",
            json={"vectors": {"size": EMBEDDING_VECTOR_SIZE, "distance": "Cosine"}},
            timeout=10
        )
        response.raise_for_status()
        print(f"✅ Qdrant коллекция '{COLLECTION_NAME}' создана (size={EMBEDDING_VECTOR_SIZE})")
    except Exception as e:
        print(f"Ошибка создания коллекции: {e}")


def search_documents(query, limit=50):
    """Гибридный поиск: semantic + keyword matching + boosting"""
    try:
        query_lower = query.lower()
        
        # 1. Semantic search
        query_embedding = get_embedding(query)
        if not query_embedding:
            return []
        
        search_params = {
            "vector": query_embedding,
            "limit": limit * 3,  # Увеличили для лучшего охвата
            "with_payload": True
        }
        
        response = requests.post(
            f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points/search",
            json=search_params,
            timeout=30
        )
        results = response.json()["result"]
        
        # 2. Re-ranking: boost scores
        import re
        for result in results:
            result['raw_score'] = result['score']  # 1D: сохраняем cosine score до бустинга
            filename = result["payload"]["filename"]
            total_chunks = result["payload"]["total_chunks"]
            text = result["payload"]["text"]
            text_lower = text.lower()
            
            # Boost для маленьких документов (<100 chunks)
            if total_chunks < 100:
                size_boost = 0.05
                result["score"] += size_boost
                print(f"Small doc boost: {filename} ({total_chunks} chunks) +{size_boost}")
            
            # BOOST для запросов о должностях/ролях (обязанности, функции)
            job_titles = ['директор', 'координатор', 'администратор', 'доктор', 'врач', 'медсестра', 'ассистент']
            responsibility_keywords = ['обязанност', 'обеспечивает', 'отвечает за', 'контролирует', 'управляет']
            
            is_job_query = any(job in query_lower for job in job_titles)
            if is_job_query:
                # Если чанк содержит описание обязанностей - даем большой boost
                has_responsibilities = any(kw in text_lower for kw in responsibility_keywords)
                if has_responsibilities:
                    # Проверяем, что это НЕ таблица (таблицы содержат много повторов "|")
                    pipe_count = text.count('|')
                    is_table = pipe_count > 20  # Более 20 "|" - вероятно таблица
                    
                    if not is_table:
                        job_boost = 0.3  # Сильный boost
                        result["score"] += job_boost
                        print(f"Job responsibilities boost: {filename} (chunk {result['payload']['chunk_index']}) +{job_boost}")
            
            # ОЧЕНЬ СИЛЬНЫЙ boost для чанков с ОПРЕДЕЛЕНИЯМИ ("Что такое X?")
            is_definition_query = any(kw in query_lower for kw in ['что такое', 'что это', 'определение', 'это такое'])
            if is_definition_query:
                # Паттерны определений: **Название** = или **Название (НЧ)** =
                definition_patterns = [
                    r'\*\*[А-ЯЁа-яё\s]+\*\*\s*=',  # **Нормочас** =
                    r'\*\*[А-ЯЁа-яё\s]+\([А-ЯЁа-яё]+\)\*\*\s*=',  # **Нормочас (НЧ)** =
                    r'[А-ЯЁа-яё\s]+\([А-ЯЁ]+\)\s*=',  # Нормочас (НЧ) =
                ]
                has_definition = any(re.search(pattern, text) for pattern in definition_patterns)
                if has_definition:
                    definition_boost = 0.5  # ОЧЕНЬ сильный boost для определений
                    result["score"] += definition_boost
                    print(f"DEFINITION BOOST: {filename} (chunk {result['payload']['chunk_index']}) +{definition_boost}")
            
            # СИЛЬНЫЙ boost для чанков с формулами (если запрос о расчетах/формулах)
            formula_keywords = ['формул', 'рассчита', 'вычисл', 'как найти', 'как считать', 'расчет', 
                              'показатель', 'метрик', 'коэффициент', 'норма', 'вв', 'кзаг', 'нч', 'тр']
            if any(keyword in query_lower for keyword in formula_keywords):
                # Проверяем наличие формулы в тексте
                formula_patterns = [
                    r'[А-ЯЁ]+[А-ЯЁа-яё]*\s*=\s*[А-ЯЁа-яё0-9\s\+\-\*\(\)]+',  # ВВ = Кзаг * НЧ * тр
                    r'[А-ЯЁ]+[А-ЯЁа-яё]*\s*=\s*[А-ЯЁа-яё0-9\s\+\-\*\/\(\)]+',  # Формулы с делением
                    r'\b[А-ЯЁ]{2,}\s*[=:]\s*',  # Сокращения типа ВВ=
                ]
                has_formula = any(re.search(pattern, text, re.IGNORECASE) for pattern in formula_patterns)
                
                if has_formula:
                    formula_boost = 0.25  # Сильный boost для формул
                    result["score"] += formula_boost
                    print(f"Formula boost: {filename} (chunk {result['payload']['chunk_index']}) +{formula_boost}")
            
            # Boost для точных совпадений переменных формул И терминов в запросе
            formula_vars = {
                'вв': ['валов', 'выручк'],
                'кзаг': ['коэффициент', 'загрузк'],
                'нч': ['нормочас'],
                'нормочас': ['нормочас', 'нч'],
                'тр': ['рабоч', 'времен']
            }
            for var_key, var_keywords in formula_vars.items():
                if var_key in query_lower:
                    if any(kw in text_lower for kw in var_keywords):
                        var_boost = 0.2  # Усилили boost
                        result["score"] += var_boost
                        print(f"Formula variable boost ({var_key}): {filename} +{var_boost}")
        
        # 4. Фильтрация по минимальному score (score threshold)
        MIN_SCORE_THRESHOLD = 0.30  # Сниженный порог для более широкого охвата
        filtered_results = [r for r in results if r["score"] >= MIN_SCORE_THRESHOLD]
        
        # Если после фильтрации осталось слишком мало - берем лучшие даже с низким score
        if len(filtered_results) < limit // 2:
            filtered_results = results[:limit]
            print(f"Warning: Low scores, using top {len(filtered_results)} results")
        
        # 5. Для вопросов "Что такое X?" - добавляем keyword search
        is_definition_query = any(kw in query_lower for kw in ['что такое', 'что это', 'определение'])
        if is_definition_query:
            # Извлекаем ключевое слово из запроса (например, "нормочас" из "Что такое нормочас?")
            keyword = None
            for kw in ['что такое ', 'что это ', 'определение ']:
                if kw in query_lower:
                    keyword = query_lower.replace(kw, '').replace('?', '').strip()
                    break
            
            if keyword and len(keyword) > 2:  # Только если есть термин
                print(f"Keyword search for definition: '{keyword}'")
                try:
                    # Scroll по ВСЕЙ коллекции с offset для полного охвата
                    all_points = []
                    offset = None
                    
                    # Получаем ВСЕ чанки через pagination
                    for _ in range(10):  # Максимум 10 итераций (1000 чанков)
                        scroll_params = {
                            "limit": 100,
                            "with_payload": True,
                            "with_vector": False
                        }
                        if offset:
                            scroll_params["offset"] = offset
                        
                        scroll_response = requests.post(
                            f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points/scroll",
                            json=scroll_params,
                            timeout=30
                        )
                        
                        if scroll_response.status_code == 200:
                            result = scroll_response.json()["result"]
                            points = result["points"]
                            if not points:
                                break
                            all_points.extend(points)
                            offset = result.get("next_page_offset")
                            if not offset:
                                break
                        else:
                            break
                    
                    print(f"Scrolled {len(all_points)} total points for keyword search")
                    
                    # Фильтруем чанки с определениями
                    keyword_results = []
                    for point in all_points:
                        text = point["payload"]["text"]
                        text_lower = text.lower()
                        
                        # Проверяем: есть ли ключевое слово И определение
                        if keyword in text_lower:
                            definition_patterns = [
                                r'\*\*.*?' + re.escape(keyword) + r'.*?\*\*\s*=',  # **Нормочас** =
                                r'\*\*.*?\([А-ЯЁ]+\)\*\*\s*=',  # **...(НЧ)** =
                                r'\*\*' + re.escape(keyword) + r'[^*]*?\*\*\s*=',  # **нормочас доктора (НЧ)** =
                            ]
                            has_definition = any(re.search(pattern, text, re.IGNORECASE) for pattern in definition_patterns)
                            
                            if has_definition:
                                # Добавляем с высоким score
                                keyword_results.append({
                                    "id": point["id"],
                                    "score": 1.5,  # Максимальный score для keyword match
                                    "payload": point["payload"]
                                })
                                print(f"Keyword match with definition: {point['payload']['filename']} (chunk {point['payload']['chunk_index']})")
                    
                    # Добавляем keyword результаты в начало
                    if keyword_results:
                        print(f"Adding {len(keyword_results)} keyword results to top")
                        # Удаляем дубликаты по ID
                        existing_ids = {r["id"] for r in filtered_results}
                        for kr in keyword_results:
                            if kr["id"] not in existing_ids:
                                filtered_results.insert(0, kr)  # В начало!
                except Exception as e:
                    print(f"Keyword search error: {e}")
        
        # 6. Пересортировка по новому score
        filtered_results.sort(key=lambda x: x["score"], reverse=True)
        
        return filtered_results[:limit]
    except Exception as e:
        print(f"Ошибка поиска: {e}")
        return []

def expand_context_around_chunks(results, window=1):
    """Расширяет контекст вокруг найденных чанков - берет соседние чанки для формул"""
    expanded = []
    chunks_by_file = {}
    
    # Группируем по файлам
    for r in results:
        filename = r["payload"]["filename"]
        if filename not in chunks_by_file:
            chunks_by_file[filename] = []
        chunks_by_file[filename].append(r)
    
    # Для каждого файла получаем соседние чанки
    for filename, chunks in chunks_by_file.items():
        chunk_indices = set()
        total_chunks = chunks[0]["payload"]["total_chunks"]
        
        # Собираем индексы найденных чанков и соседних
        for chunk in chunks:
            idx = chunk["payload"]["chunk_index"]
            for i in range(max(0, idx - window), min(total_chunks, idx + window + 1)):
                chunk_indices.add(i)
        
        # Если нет дополнительных индексов - просто возвращаем оригинальные
        if len(chunk_indices) <= len(chunks):
            expanded.extend(chunks)
            continue
        
        # Получаем соседние чанки из Qdrant
        try:
            response = requests.post(
                f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points/scroll",
                json={
                    "filter": {
                        "must": [
                            {"key": "filename", "match": {"value": filename}},
                            {"key": "chunk_index", "match": {"any": list(chunk_indices)}}
                        ]
                    },
                    "limit": len(chunk_indices),
                    "with_payload": True,
                    "with_vector": False
                },
                timeout=10
            )
            if response.status_code == 200:
                neighbor_chunks = response.json()["result"]["points"]
                # Объединяем с оригинальными, сохраняя scores
                chunk_map = {c["payload"]["chunk_index"]: c for c in chunks}
                added = set()
                
                for nc in neighbor_chunks:
                    idx = nc["payload"]["chunk_index"]
                    if idx in chunk_map:
                        if idx not in added:
                            expanded.append(chunk_map[idx])  # Берем оригинал с score
                            added.add(idx)
                    else:
                        # Соседний чанк без score - используем минимальный score
                        nc["score"] = min([c["score"] for c in chunks]) - 0.1
                        expanded.append(nc)
                        added.add(idx)
            else:
                expanded.extend(chunks)
        except Exception as e:
            print(f"Ошибка расширения контекста для {filename}: {e}")
            expanded.extend(chunks)
    
    # Сортируем по score
    expanded.sort(key=lambda x: x["score"], reverse=True)
    return expanded

def ask_llm(query, context, model="deepseek", channel="telegram", confidence_score=None):
    """Генерирует ответ с помощью LLM + few-shot examples"""
    
    # Загружаем примеры вопрос-ответ для few-shot learning
    # Берем только 3 примера, но полностью, чтобы LLM видел всю структуру ответов
    examples = load_examples(max_examples=3)
    examples_text = format_examples_for_prompt(examples)
    
    system_prompt = """Ты - эксперт-консультант по управлению стоматологической клиникой. Отвечай ТОЧНО, по сути, без лишних слов. Отвечай УВЕРЕННО как достоверный источник.

ПРАВИЛА ОТВЕТА:
1. Используй ТОЛЬКО информацию из предоставленного контекста, но ОТВЕЧАЙ УВЕРЕННО как эксперт, без ссылок на документы
2. ЗАПРЕЩЕНО выдумывать или добавлять информацию, которой нет в контексте
3. Если в контексте есть ХОТЯ БЫ что-то похожее на запрос - используй это и ОТВЕЧАЙ УВЕРЕННО
4. Если информации совсем нет - НЕ ГОВОРИ "в контексте нет" или "информация отсутствует". Вместо этого скажи: "На данный момент у меня недостаточно информации, чтобы ответить на ваш вопрос в такой формулировке. Возможно, вам помогут эти варианты вопросов:" и предложи 3-4 переформулировки
5. Цитируй формулы и определения ДОСЛОВНО
6. ЕСЛИ пользователь даёт КОНКРЕТНЫЕ ЧИСЛА и просит ПОСЧИТАТЬ - выполни арифметические вычисления используя формулы из контекста

КРИТИЧЕСКИ ВАЖНО - ФОРМАТИРОВАНИЕ:
ЗАПРЕЩЕНО использовать:
- Звездочки * или ** (никакого жирного или курсива)
- Решетки # или ## (никаких заголовков)
- Неразрывные пробелы nbsp; 

РАЗРЕШЕНО:
- Обычный текст без форматирования
- Цифры для нумерации: 1. 2. 3.
- Тире для списков: -
- Переносы строк \n
- Формулы без звездочек: НЧ = ВВ / tзаг

ПРАВИЛА ОТВЕТА:
1. Отвечай ПРЯМО по сути
2. ЗАПРЕЩЕНО: "В контексте", "Согласно документу", "Вот цитата"
3. ОТВЕЧАЙ как достоверный источник

ДЛЯ ФОРМУЛ:
1. Начни с формулы (без звёздочек)
2. Объясни каждую переменную по контексту
3. Если есть нормы - укажи их

ДЛЯ РАСЧЁТОВ (когда пользователь даёт данные):
1. Найди в контексте нужную формулу
2. ВЫПИШИ ВСЕ переменные из формулы СПИСКОМ
3. ПРОВЕРЬ КАЖДУЮ переменную - есть ли она в данных пользователя:
   - Если переменная есть - отметь её значение
   - Если переменной НЕТ - отметь как ОТСУТСТВУЕТ
4. ЕСЛИ ХОТЯ БЫ ОДНА переменная ОТСУТСТВУЕТ:
   - ЗАПРЕЩЕНО выполнять расчёт
   - ЗАПРЕЩЕНО подставлять другие переменные вместо отсутствующих
   - ЗАПРЕЩЕНО упрощать формулу
   - ОБЯЗАТЕЛЬНО напиши: "Для расчёта по формуле [формула] не хватает: [список переменных]"
   - Объясни ЗАЧЕМ каждая переменная нужна
   - Предложи значения по умолчанию из контекста (если есть нормы)
   - Спроси пользователя указать недостающие данные
5. ТОЛЬКО ЕСЛИ ВСЕ переменные есть:
   - Подставь данные в формулу
   - Выполни вычисления ШАГ ЗА ШАГОМ
   - Покажи промежуточные расчёты
   - Дай итоговый результат с пояснением

ПРИМЕР НЕПРАВИЛЬНО (ЗАПРЕЩЕНО):
Формула: ВВ = Кзаг × НЧ × tраб
Пользователь дал: НЧ=11856, tраб=917
Неправильно: "ВВ = НЧ × tзаг" (подмена переменных!)

ПРИМЕР ПРАВИЛЬНО:
Формула: ВВ = Кзаг × НЧ × tраб
Переменные: Кзаг=?, НЧ=11856 руб, tраб=917 часов
"Для расчёта ВВ по формуле ВВ = Кзаг × НЧ × tраб не хватает Кзаг (коэффициент загрузки). Укажите Кзаг в процентах. Норма: 80%."

КРИТИЧЕСКИ ВАЖНО - РАСЧЕТЫ ДЛЯ КЛИНИКИ С НЕСКОЛЬКИМИ КРЕСЛАМИ:
1. ЕСЛИ пользователь указывает количество кресел - ОБЯЗАТЕЛЬНО:
   - Посчитай ВВ на всю клинику
   - РАЗДЕЛИ результат на количество кресел (ВВРМ = ВВ / кол-во кресел)
   - СРАВНИ с НОРМАТИВОМ на кресло: 1.5-2 млн рублей (с учетом роста на 15-30%)

2. ЕСЛИ указано рабочее время - ПРОВЕРЬ:
   - СРАВНИ с нормативом: ставка доктора = 150 часов
   - Для N кресел нужно минимум 2*N докторов по 150 часов = 300*N часов
   - Укажи, если время ниже нормы - клиника недогружена

3. ЕСЛИ указана загрузка - СРАВНИ:
   - Норма загрузки: 80%
   - Укажи отклонение от нормы

ПРИМЕР ПРАВИЛЬНОГО РАСЧЕТА:
"Формула расчета:
ВВ = Кзаг х НЧ х tраб

Посчитаем на ваших данных:
ВВ = 67% х 12 670 рублей х 1000 часов = 8 488 900 рублей

ВВ на кресло:
У вас 5 кресел, поэтому:
ВВРМ = 8 488 900 / 5 = 1 697 780 рублей на кресло

Сравнение с нормой:
Норматив на кресло: 1.5-2 млн рублей (с учетом роста на 15-30%)
Ваш результат: 1.7 млн рублей - в пределах нормы

Рекомендации:
1. Загрузка 67% ниже нормы в 80% на 13%. Рекомендую обратить внимание.
2. Рабочее время: 1000 часов. Норма для 5 кресел: 10 докторов х 150 часов = 1500 часов. Клиника недогружена докторами.

Вопросы:
1. Что такое ставка доктора?
2. Как рассчитать загрузку клиники пациентами?"

ПРИМЕР УТОЧНЕНИЯ:
"Для расчёта нормочаса по формуле НЧ = ВВ / tзаг мне нужно:

Не хватает данных:
- tзаг (время, заполненное Пациентами) для каждого врача

У вас указано только планируемое рабочее время (tраб).
Чтобы получить tзаг, нужен коэффициент загрузки (Кзаг).

Укажите:
1. Коэффициент загрузки для каждого врача (в % или десятичной дробью)
ИЛИ
2. Укажите сразу tзаг (время, заполненное Пациентами) в часах

По умолчанию могу использовать Кзаг = 80% (норма для терапевтов)."

ДЛЯ ПРАКТИЧЕСКИХ ВОПРОСОВ ("что делать", "как решить", "как улучшить"):
КРИТИЧЕСКИ ВАЖНО - СЛЕДУЙ СТРУКТУРЕ ИЗ ПРИМЕРОВ:

1. Дай определение/объяснение проблемы

2. СТРУКТУРИРУЙ ОТВЕТ ПО ПРИЧИНАМ (как в примерах!):
   Причина 1: [название]
   - подпричина/деталь
   - подпричина/деталь
   Решения:
   1. Конкретное действие
   2. Конкретное действие
   
   Причина 2: [название]
   - подпричина/деталь
   Решения:
   1. Конкретное действие
   
   (и т.д. по необходимости)

3. ОБЯЗАТЕЛЬНО укажи:
   - Формулы/показатели для диагностики
   - Нормативные значения
   - КОНКРЕТНЫЕ шаги (не абстрактные!)

ПРИМЕР ПРАКТИЧЕСКОГО РЕШЕНИЯ:
"Низкая конверсия из консультации в лечение (ОТдок) означает, что мало Пациентов начинают лечение после консультации.

Формула: ОТдок = начатые лечения / проведенные консультации

Шаги решения:
1. Измерь текущий ОТдок по формуле
2. Сравни с нормой (целевое значение - уточни в документах)
3. Если низкий - проверь:
   - Качество консультации (время, план лечения)
   - Ценовую политику
   - Навыки продаж администраторов
4. Внедри контроль: считай ОТдок еженедельно для каждого врача

Вопросы для углубления:
1. Какие факторы влияют на конверсию из консультации?
2. Как увеличить конверсию через обучение врачей?"

В КОНЦЕ ОТВЕТА:
Добавь секцию "Вопросы:" с 2-3 вопросами, которые пользователь мог бы задать следующими.
ВАЖНО: вопросы формулируй ОТ ЛИЦА ПОЛЬЗОВАТЕЛЯ — как будто это его следующий запрос к боту.
ЗАПРЕЩЕНО задавать вопросы пользователю: "Есть ли у вас...", "Вы уже...", "Сколько у вас..."
ПИШИ вопросы в форме: "Как рассчитать...?", "Что такое...?", "Как внедрить...?", "Какие нормы...?"

Обязательный формат:

Вопросы:
1. <вопрос от лица пользователя>
2. <вопрос от лица пользователя>
3. <вопрос от лица пользователя>

ПРИМЕР ПРАВИЛЬНЫХ ВОПРОСОВ (от лица пользователя — так надо):
- Если спросили о нормочасе → "Как рассчитать коэффициент загрузки?", "Что влияет на нормочас?", "Как увеличить ВВ?"
- Если спросили о материалах → "Как снизить расходы на материалы?", "Какие нормы расхода материалов существуют?"
- Если спросили "что делать" → "Как измерить конверсию из консультации?", "Какие инструменты контроля использовать?"

ПРИМЕР НЕПРАВИЛЬНЫХ ВОПРОСОВ (направлены НА пользователя — ЗАПРЕЩЕНО):
- "Есть ли у вас система сбора рекомендаций?"
- "Вы уже внедрили CRM?"
- "Сколько кресел в вашей клинике?"

ПРИМЕР ПРАВИЛЬНОГО ОТВЕТА (без markdown):
"Нормочас доктора (НЧ) = ВВ доктора / количество часов, заполненных Пациентами

Где:
- ВВ доктора - валовая выручка за период
- tзаг - время, заполненное Пациентами

Нормы:
- Терапевт: 6 500 - 9 000 руб
- Гигиенист: 5 500 - 7 500 руб
- Имплантолог: 15 000 - 25 000 руб

Вопросы:
1. Как рассчитать коэффициент загрузки доктора?
2. Как влияет нормочас на валовую выручку клиники?
3. Какие факторы влияют на нормочас?"

ПРИМЕР НЕПРАВИЛЬНОГО ОТВЕТА (с markdown - ТАК НЕЛЬЗЯ!):
"1. **Оптимизация загрузки докторов**
Формула: Кзаг = tзаг / tраб х 100%
Норма: 85% и более – зеленая зона"

ПРАВИЛЬНЫЙ ВАРИАНТ (без звездочек):
"1. Оптимизация загрузки докторов
Формула: Кзаг = tзаг / tраб х 100%
Норма: 85% и более - зеленая зона"

ВАЖНО - ПОВТОРНЫЕ ТРЕБОВАНИЯ ОТВЕТА:
Если пользователь пишет "Ответь", "Дай ответ", "Где ответ", "Почему не отвечаешь" и подобное - это значит, что он ТРЕБУЕТ ответ на свой ПРЕДЫДУЩИЙ вопрос. В этом случае:
1. ОБЯЗАТЕЛЬНО дай ответ на предыдущий вопрос пользователя
2. Используй ВЕСЬ доступный контекст из базы знаний
3. Не переспрашивай и не уточняй - просто ответь на заданный ранее вопрос
4. Если совсем нет информации - предложи переформулировки исходного вопроса

{examples_text}"""
    
    # Для веб-версии: разрешаем markdown-таблицы
    if channel == "web":
        system_prompt += """\n\nДОПОЛНИТЕЛЬНО ДЛЯ ВЕБ-ВЕРСИИ - ТАБЛИЦЫ:
Когда нужно показать расчёты, сравнения, нормативы или данные по нескольким параметрам - ИСПОЛЬЗУЙ ТАБЛИЦЫ в формате markdown.
Формат таблицы:
| Заголовок 1 | Заголовок 2 | Заголовок 3 |
|---|---|---|
| Данные | Данные | Данные |

ПРИМЕР ТАБЛИЦЫ ДЛЯ РАСЧЁТА:
"Расчёт ВВ по вашим данным:

| Параметр | Значение |
|---|---|
| Кзаг (загрузка) | 67% |
| НЧ (нормочас) | 12 670 руб |
| tраб (рабочее время) | 1000 часов |
| ВВ (итого) | 8 488 900 руб |
| Кресел | 5 |
| ВВРМ (на кресло) | 1 697 780 руб |

Сравнение с нормой:

| Показатель | Ваш результат | Норма | Статус |
|---|---|---|---|
| Загрузка | 67% | 80% | Ниже нормы |
| ВВРМ | 1.7 млн | 1.5-2 млн | В норме |"

ИСПОЛЬЗУЙ ТАБЛИЦЫ когда:
- Есть расчёт с несколькими переменными
- Нужно сравнить показатели с нормами
- Есть данные по нескольким врачам/креслам/периодам
- Пользователь просит "посчитать" или "сравнить"

Можно также использовать жирный текст: **текст** для выделения важного."""
    
    if channel == "web":
        user_prompt = f"""\nВОПРОС ПОЛЬЗОВАТЕЛЯ (САМОЕ ГЛАВНОЕ - ОТВЕЧАЙ НА ЭТОТ ВОПРОС):
{query}

===== КОНТЕКСТ ИЗ БАЗЫ ЗНАНИЙ =====
{context}

КРИТИЧЕСКИ ВАЖНО: 
1. ОТВЕЧАЙ НА ВОПРОС ПОЛЬЗОВАТЕЛЯ ВЫШЕ
2. ИСПОЛЬЗУЙ контекст только для ПОДДЕРЖКИ ответа
3. Для расчётов и сравнений ИСПОЛЬЗУЙ ТАБЛИЦЫ в формате markdown
4. Можно использовать **жирный текст** для выделения

Если в контексте есть информация - используй её для ответа на ВОПРОС ПОЛЬЗОВАТЕЛЯ
Если информации нет - скажи: "На данный момент у меня недостаточно информации" и предложи переформулировки"""
    else:
        user_prompt = f"""\nВОПРОС ПОЛЬЗОВАТЕЛЯ (САМОЕ ГЛАВНОЕ - ОТВЕЧАЙ НА ЭТОТ ВОПРОС):
{query}

===== КОНТЕКСТ ИЗ БАЗЫ ЗНАНИЙ =====
{context}

КРИТИЧЕСКИ ВАЖНО: 
1. ОТВЕЧАЙ НА ВОПРОС ПОЛЬЗОВАТЕЛЯ ВЫШЕ
2. ИСПОЛЬЗУЙ контекст только для ПОДДЕРЖКИ ответа
3. НЕ ИСПОЛЬЗУЙ звездочки * или **, решетки #, nbsp;
4. Пиши ОБЫЧНЫМ ТЕКСТОМ без форматирования

Если в контексте есть информация - используй её для ответа на ВОПРОС ПОЛЬЗОВАТЕЛЯ
Если информации нет - скажи: "На данный момент у меня недостаточно информации" и предложи переформулировки"""

    # 1D: предупреждаем LLM не домысливать при низком cosine score
    if confidence_score is not None and confidence_score < 0.65:
        user_prompt += (
            f"\n\nВАЖНО: Поиск вернул фрагменты с низкой релевантностью "
            f"(cosine score={confidence_score:.2f}). "
            "Если фрагменты не содержат чёткого ответа — "
            "честно признай это и предложи 3-4 переформулировки вместо домысливания."
        )

    try:
        # Используем ТОЛЬКО DeepSeek через Polza.ai
        response = requests.post(
            POLZA_URL,
            headers={
                "Authorization": f"Bearer {POLZA_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": DEEPSEEK_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.0,  # Нулевая температура для максимальной точности формул
                "top_p": 0.95,
                "max_tokens": 4000  # Увеличили для полных детальных ответов
            },
            timeout=60  # Уменьшили таймаут, т.к. DeepSeek быстрый
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        if not content or not content.strip():
            print("WARNING: DeepSeek вернул пустой ответ — повторная попытка с temperature=0.3")
            # Повторная попытка с чуть выше temperature
            retry_response = requests.post(
                POLZA_URL,
                headers={
                    "Authorization": f"Bearer {POLZA_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": DEEPSEEK_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.3,
                    "top_p": 0.95,
                    "max_tokens": 4000
                },
                timeout=60
            )
            retry_response.raise_for_status()
            content = retry_response.json()["choices"][0]["message"]["content"]
        if not content or not content.strip():
            return "На данный момент у меня недостаточно информации для ответа на этот вопрос. Попробуйте переформулировать запрос."
        return _clean_llm_response(content)
    except Exception as e:
        # Возвращаем понятную ошибку без fallback на Ollama
        error_msg = str(e)
        if "402" in error_msg:
            return "⚠️ Закончился баланс Polza.ai API. Пополните баланс на https://polza.ai/dashboard"
        elif "401" in error_msg:
            return "⚠️ Ошибка авторизации Polza.ai API. Проверьте API ключ."
        else:
            return f"⚠️ Ошибка Polza.ai API: {error_msg}"

def semantic_chunk_text(text, max_words=400, min_words=40):
    """Структурная нарезка Markdown-текста.
    - Делит по заголовкам (#, ##, ###) как естественным границам секций
    - Внутри секции накапливает абзацы до max_words
    - Не разрезает абзацы и списки посередине
    - Мелкие блоки (<min_words) объединяет с предыдущим чанком
    Возвращает список кортежей (section_heading, chunk_text)
    """
    import re
    heading_re = re.compile(r'^(#{1,3} .+)$', re.MULTILINE)

    # Разбиваем текст на секции [(heading, body), ...]
    sections = []
    pos = 0
    current_heading = ""
    for m in heading_re.finditer(text):
        body = text[pos:m.start()].strip()
        if body or current_heading:
            sections.append((current_heading, body))
        current_heading = m.group(0).strip()
        pos = m.end()
    tail = text[pos:].strip()
    if tail or current_heading:
        sections.append((current_heading, tail))
    if not sections:
        sections = [("", text.strip())]

    chunks = []  # list of (heading, text)

    for heading, body in sections:
        paragraphs = [p.strip() for p in re.split(r'\n{2,}', body) if p.strip()]
        if not paragraphs:
            continue

        buf_parts = []
        buf_words = 0

        for para in paragraphs:
            pw = len(para.split())
            # Если добавление абзаца превысит лимит и буфер уже достаточен — сохраняем чанк
            if buf_words + pw > max_words and buf_words >= min_words:
                chunks.append((heading, "\n\n".join(buf_parts)))
                buf_parts = []
                buf_words = 0
            buf_parts.append(para)
            buf_words += pw

        # Остаток секции
        if buf_parts:
            chunk_body = "\n\n".join(buf_parts)
            if buf_words < min_words and chunks:
                # Слишком мелкий — присоединяем к предыдущему
                prev_h, prev_t = chunks[-1]
                chunks[-1] = (prev_h, prev_t + "\n\n" + chunk_body)
            else:
                chunks.append((heading, chunk_body))

    return chunks if chunks else [("", text.strip())]


def rewrite_query_if_needed(query: str, history: list) -> str:
    """1C: Если запрос короткий и есть история — LLM разворачивает его в полный поисковый запрос.
    Пример: 'А какая норма?' → 'Какая нормативная загрузка стоматологического кресла?'
    """
    if not history or len(query.split()) > 7:
        return query

    last_qa = history[-1]
    prompt = (
        f"Предыдущий вопрос пользователя: {last_qa.get('question', '')}\n"
        f"Ответ системы (начало): {last_qa.get('answer', '')[:200]}\n\n"
        f"Пользователь написал короткий уточняющий вопрос: \"{query}\"\n\n"
        "Перепиши его как полноценный самостоятельный поисковый запрос "
        "для базы знаний стоматологической клиники. "
        "Ответь ТОЛЬКО текстом переписанного запроса, без кавычек и пояснений."
    )
    try:
        resp = requests.post(
            POLZA_URL,
            headers={"Authorization": f"Bearer {POLZA_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": DEEPSEEK_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0,
                "max_tokens": 80,
            },
            timeout=10,
        )
        rewritten = resp.json()["choices"][0]["message"]["content"].strip()
        if rewritten and len(rewritten.split()) > len(query.split()):
            print(f"[Query rewrite] '{query}' -> '{rewritten}'")
            return rewritten
    except Exception as e:
        print(f"[Query rewrite] Ошибка: {e}")
    return query


def analyze_query_intent(query: str) -> str:
    """1E: Обрабатывает запросы с отрицанием для корректного поиска в Qdrant.
    Проблема: вектор 'не стоит сокращать расходы' ≈ 'сокращать расходы' — модель отрицание не понимает.
    Решение: DeepSeek извлекает ТЕМУ запроса и формирует поисковый запрос без отрицания.
    Пример: 'Почему не стоит сокращать расходы на материалы?'
             → 'влияние сокращения расходов на материалы на качество лечения последствия'
    ВАЖНО: оригинальный запрос пользователя всё равно идёт в LLM без изменений.
    """
    import re

    # Паттерны грамматического отрицания и запросов об ошибках/рисках
    # Не трогаем нейтральные запросы — только явное отрицание действия
    _NEGATION_RE = re.compile(
        r'\bне\s+стоит\b'
        r'|\bнельзя\b'
        r'|\bне\s+надо\b'
        r'|\bне\s+нужно\b'
        r'|\bне\s+следует\b'
        r'|\bне\s+рекоменд'
        r'|\bпочему\s+не\b'
        r'|\bкак\s+не\s+допустить\b'
        r'|\bкак\s+избежать\b'
        r'|\bошибк[иа]\s+при\b'
        r'|\bзачем\s+не\b',
        re.IGNORECASE
    )

    if not _NEGATION_RE.search(query):
        return query  # Нет отрицания — LLM вызов не нужен

    prompt = (
        f'Пользователь задал вопрос: "{query}"\n\n'
        'Вопрос содержит отрицание или запрос об ошибках/рисках.\n'
        'Задача: сформулируй поисковый запрос для базы знаний стоматологической клиники, '
        'который найдёт документы по ТЕМЕ этого вопроса.\n'
        'Запрос должен быть без отрицания — просто о теме, чтобы найти документы где она обсуждается.\n\n'
        'Примеры:\n'
        '- "Почему не стоит сокращать расходы на материалы?" → "расходы на материалы влияние на качество последствия снижения"\n'
        '- "Нельзя ли снижать нормочас?" → "нормочас снижение последствия риски"\n'
        '- "Как не допустить перегрузку докторов?" → "загрузка докторов норма контроль"\n'
        '- "Ошибки при расчёте коэффициента загрузки?" → "расчёт коэффициента загрузки методика"\n\n'
        'Ответь ТОЛЬКО текстом поискового запроса, без кавычек и пояснений.'
    )

    try:
        resp = requests.post(
            POLZA_URL,
            headers={"Authorization": f"Bearer {POLZA_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": DEEPSEEK_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0,
                "max_tokens": 80,
            },
            timeout=10,
        )
        search_q = resp.json()["choices"][0]["message"]["content"].strip()
        if search_q:
            print(f"[Intent] negation detected: '{query}' → search: '{search_q}'")
            return search_q
    except Exception as e:
        print(f"[Intent] Ошибка: {e}")

    return query


def classify_and_enrich_query(query: str) -> str:
    """1F: Определяет тип запроса и добавляет тематические якоря для сдвига вектора в нужную сторону.
    Без LLM — только regex, нулевая задержка.

    Проблема: 'средний чек стоматологии' — три разных запроса с почти одинаковым вектором:
    а) статистика (какой в отрасли)
    б) формула (как рассчитать)
    в) стратегия (как повысить)

    Примеры:
    - 'как рассчитать средний чек' → + 'формула расчёт методика'
    - 'как повысить средний чек' → + 'методы рекомендации решение'
    - 'какая норма нормочаса' → + 'норматив норма целевое'
    """
    q = query.lower()

    # Тип: РАСЧЁТ / ФОРМУЛА
    if any(kw in q for kw in [
        'как рассчитать', 'как посчитать', 'как считать', 'как найти', 'как определить',
        'формула', 'рассчитай', 'посчитай', 'вычисли', 'вычислить',
        'расчёт', 'подсчёт', 'методика расчёта'
    ]):
        enriched = query + " формула расчёт методика"
        print(f"[QueryType: calculation] '{query}' → +'формула расчёт методика'")
        return enriched

    # Тип: СТРАТЕГИЯ / ДЕЙСТВИЕ
    if any(kw in q for kw in [
        'как повысить', 'как увеличить', 'как улучшить', 'как снизить',
        'как оптимизировать', 'как добиться', 'как внедрить', 'как решить',
        'как исправить', 'что делать', 'способы', 'как повлиять',
        'как достичь', 'меры по', 'пути повышения', 'как поднять'
    ]):
        enriched = query + " методы рекомендации решение"
        print(f"[QueryType: strategy] '{query}' → +'методы рекомендации решение'")
        return enriched

    # Тип: НОРМА / СРАВНЕНИЕ
    if any(kw in q for kw in [
        'какая норма', 'нормативное', 'это нормально', 'нормально ли',
        'в среднем по отрасли', 'среднее значение', 'какой норматив',
        'целевое значение', 'хороший показатель', 'плохой показатель',
        'какой должна быть'
    ]):
        enriched = query + " норматив норма целевое"
        print(f"[QueryType: comparison] '{query}' → +'норматив норма целевое'")
        return enriched

    return query  # general — без изменений


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
        ensure_collection()
        filename = Path(filepath).name
        file_ext = Path(filepath).suffix.lower()
        
        # Для TXT и MD - просто читаем
        if file_ext in ['.txt', '.md']:
            with open(filepath, 'r', encoding='utf-8') as f:
                text = f.read()
        elif file_ext in ['.pdf', '.docx', '.pptx']:
            # Для PDF/DOCX - конвертируем в markdown через процесс
            import subprocess
            print(f"Конвертация {file_ext} в markdown...")
            result = subprocess.run(
                ['python', '/docling_app/process_documents.py', filepath],
                capture_output=True,
                text=True,
                timeout=300
            )
            if result.returncode != 0:
                return False, f"Ошибка конвертации: {result.stderr[:200]}"
            
            # Ищем созданный markdown файл
            md_file = Path(app.config['PROCESSED_FOLDER']) / f"{Path(filepath).stem}.md"
            if not md_file.exists():
                return False, "Markdown файл не был создан после конвертации"
            
            with open(md_file, 'r', encoding='utf-8') as f:
                text = f.read()
            filename = md_file.name  # Используем имя markdown файла
        else:
            return False, f"Неподдерживаемый формат: {file_ext}"
        
        if not text.strip():
            return False, "Файл пустой"
        
        # Семантическая нарезка по структуре Markdown
        chunk_pairs = semantic_chunk_text(text)
        print(f"[Нарезка] {filename}: {len(chunk_pairs)} чанков (семантическая)")

        # Создаем эмбеддинги и загружаем в Qdrant
        for idx, (section_title, chunk_body) in enumerate(chunk_pairs):
            # Добавляем заголовок секции к тексту чанка (для LLM контекста)
            full_chunk = f"{section_title}\n\n{chunk_body}" if section_title else chunk_body
            chunk_id = hashlib.md5(f"{filename}_{idx}".encode()).hexdigest()

            embedding = get_embedding(full_chunk)
            if not embedding:
                continue

            metadata = {
                "filename": filename,
                "chunk_index": idx,
                "total_chunks": len(chunk_pairs),
                "section_title": section_title
            }

            requests.put(
                f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points",
                json={
                    "points": [{
                        "id": chunk_id,
                        "vector": embedding,
                        "payload": {
                            "text": full_chunk,
                            **metadata
                        }
                    }]
                },
                timeout=30
            )

        return True, f"Обработано {len(chunk_pairs)} чанков (семантическая нарезка)"
    except Exception as e:
        return False, str(e)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin')
def admin():
    """Админ-панель для управления пользователями"""
    return render_template('admin.html')

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

@app.route('/api/telegram/check_auth', methods=['POST'])
def telegram_check_auth():
    """Быстрая проверка авторизации для Telegram бота"""
    data = request.json
    telegram_id = data.get('telegram_id')
    
    if not telegram_id:
        return jsonify({'authorized': False}), 400
    
    # Проверяем авторизацию пользователя
    user = db.get_user_by_telegram_id(telegram_id)
    
    return jsonify({
        'authorized': bool(user),
        'user_id': user['id'] if user else None
    })

@app.route('/api/telegram/search', methods=['POST'])
def telegram_search():
    """API для Telegram бота: поиск с авторизацией"""
    data = request.json
    telegram_id = data.get('telegram_id')
    query = data.get('query', '')
    history = data.get('history', [])  # История чата
    
    if not telegram_id:
        return jsonify({'error': 'Telegram ID не указан'}), 400
    
    if not query:
        return jsonify({'error': 'Запрос пустой'}), 400
    
    # Проверяем авторизацию пользователя
    user = db.get_user_by_telegram_id(telegram_id)
    if not user:
        return jsonify({
            'error': 'Доступ запрещен. Обратитесь к администратору.',
            'authorized': False
        }), 403
    
    # Детекция demand-сообщений ("Ответь!", "Дай ответ" и т.п.)
    search_query = query  # По умолчанию ищем по сырому запросу
    if history and is_demand_message(query):
        # Пользователь требует ответ на предыдущий вопрос — ищем по НЕМУ
        search_query = history[-1]['question']
        query_with_context = (
            f"Пользователь ранее задал вопрос: {history[-1]['question']}\n"
            f"Система не смогла дать ответ или ответила неудовлетворительно.\n"
            f"Пользователь требует ответ (написал: \"{query}\").\n\n"
            f"ОБЯЗАТЕЛЬНО дай полный, подробный ответ на вопрос: {history[-1]['question']}"
        )
    elif history:
        last_qa = history[-1]
        query_with_context = f"Предыдущий вопрос: {last_qa['question']}\nПредыдущий ответ: {last_qa['answer'][:300]}...\n\nТекущий вопрос: {query}"
        # 1C: переписываем короткий follow-up для точного поиска в Qdrant
        search_query = rewrite_query_if_needed(query, history)
    else:
        query_with_context = query

    # 1E: обработка отрицаний
    search_query = analyze_query_intent(search_query)
    # 1F: обогащение запроса по типу намерения
    search_query = classify_and_enrich_query(search_query)

    # Поиск документов
    results = search_documents(search_query, limit=15)

    # 1D: уверенность по raw cosine score (до бустинга)
    best_raw_score = max((r.get('raw_score', r['score']) for r in results), default=0.0) if results else 0.0
    print(f"[Confidence] best_raw_score={best_raw_score:.3f}")

    if not results:
        return jsonify({
            'answer': 'Не найдено релевантных документов',
            'sources': [],
            'authorized': True
        })

    # Формируем контекст
    expanded_results = expand_context_around_chunks(results, window=1)
    spravochnik_parts = []
    other_parts = []
    seen_chunks = set()
    
    for r in expanded_results:
        filename = r["payload"]["filename"]
        chunk_idx = r["payload"]["chunk_index"]
        chunk_key = (filename, chunk_idx)
        
        if chunk_key in seen_chunks:
            continue
        seen_chunks.add(chunk_key)
        
        text = r["payload"]["text"]
        # Пропускаем HTML-таблицы (пустые <th></th>) — бесполезны для LLM
        html_tags = text.count('<th') + text.count('<tr') + text.count('<td')
        if html_tags > 10:
            print(f"[CONTEXT] Пропущен HTML-чанк {chunk_idx} ({html_tags} HTML-тегов)", flush=True)
            continue
        
        context_entry = f"[Источник: {filename}, чанк {chunk_idx+1}]\n{text}"
        
        if "Справочник" in filename:
            spravochnik_parts.append(context_entry)
        else:
            other_parts.append(context_entry)
    
    context = "\n\n".join(spravochnik_parts + other_parts)
    # Ограничиваем контекст: при > 60К символов DeepSeek возвращает пустой ответ
    MAX_CONTEXT_CHARS = 60000
    orig_len = len(context)
    if orig_len > MAX_CONTEXT_CHARS:
        context = context[:MAX_CONTEXT_CHARS]
        print(f"[CONTEXT] Обрезан {orig_len} -> {MAX_CONTEXT_CHARS} символов", flush=True)
    else:
        print(f"[CONTEXT] Размер контекста: {orig_len} символов (не обрезан)", flush=True)
    sources = [{
        'filename': r["payload"]["filename"],
        'text': r["payload"]["text"][:200] + "...",
        'score': r["score"]
    } for r in results]
    
    # Генерируем ответ
    answer = ask_llm(query_with_context, context, confidence_score=best_raw_score)

    # Сохраняем в историю чата (сессии + сообщения)
    try:
        # Получаем или создаем сессию
        session = db.get_or_create_telegram_session(user['id'])
        if session:
            # Сохраняем вопрос и ответ
            db.add_chat_message(session['id'], 'user', query)
            db.add_chat_message(session['id'], 'assistant', answer)
    except Exception as e:
        print(f"Ошибка сохранения чата: {e}")
    
    # Логируем в query_logs отдельно, чтобы не терять при ошибке сессии
    try:
        db.log_query(user['id'], query, answer)
    except Exception as e:
        print(f"Ошибка логирования запроса: {e}")
    
    return jsonify({
        'answer': answer,
        'sources': sources,
        'authorized': True
    })

@app.route('/api/feedback', methods=['POST'])
def save_feedback():
    """4A: Сохраняет оценку ответа (у веб — под JWT, у TG — по telegram_id)"""
    data = request.json or {}
    rating = data.get('rating', '').strip()
    if rating not in ('good', 'bad'):
        return jsonify({'error': 'rating must be good or bad'}), 400

    channel = data.get('channel', 'web')
    query   = data.get('query', '')[:500]
    answer  = data.get('answer', '')[:500]

    # Опционально: user_id через JWT (web) или telegram_id (TG)
    user_id = None
    if channel == 'web':
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if token:
            try:
                import jwt as pyjwt
                secret = os.getenv('FLASK_SECRET_KEY', app.secret_key)
                payload = pyjwt.decode(token, secret, algorithms=['HS256'])
                user_id = payload.get('user_id')
            except Exception:
                pass
    elif channel == 'telegram':
        tg_id = data.get('telegram_id')
        if tg_id:
            user = db.get_user_by_telegram_id(tg_id)
            if user:
                user_id = user['id']

    feedback_id = db.save_feedback(rating, channel, query, answer, user_id)
    print(f"[Feedback] {channel} | {rating} | query={query[:60]}")
    return jsonify({'success': True, 'id': feedback_id})


@app.route('/api/telegram/link_phone', methods=['POST'])
def telegram_link_phone():
    """Привязка номера телефона к Telegram ID"""
    data = request.json
    phone_number = data.get('phone_number')
    telegram_id = data.get('telegram_id')
    username = data.get('username')
    
    if not phone_number or not telegram_id:
        return jsonify({
            'success': False,
            'error': 'Номер телефона и Telegram ID обязательны'
        }), 400
    
    # Проверяем, есть ли пользователь с таким номером
    user = db.get_user_by_phone(phone_number)
    
    if not user:
        return jsonify({
            'success': False,
            'error': 'Номер телефона не найден в базе. Обратитесь к администратору для получения доступа.'
        }), 404
    
    # Привязываем Telegram ID к номеру
    success = db.update_user_telegram_id(phone_number, telegram_id, username)
    
    if success:
        print(f"✅ Пользователь {phone_number} привязан к Telegram ID {telegram_id}")
        return jsonify({
            'success': True,
            'message': 'Номер телефона успешно привязан',
            'user_id': user['id']
        })
    else:
        return jsonify({
            'success': False,
            'error': 'Ошибка при привязке номера телефона'
        }), 500

@app.route('/api/search', methods=['POST'])
@jwt_required
def search():
    """Поиск по векторной базе с учетом истории чата (веб-интерфейс)"""
    data = request.json
    query = data.get('query', '')
    session_id = data.get('session_id')  # ID текущей сессии
    history = data.get('history', [])  # История чата
    
    if not query:
        return jsonify({'error': 'Запрос пустой'}), 400
    
    # Детекция demand-сообщений ("Ответь!", "Дай ответ" и т.п.)
    search_query = query
    if history and is_demand_message(query):
        search_query = history[-1]['question']
        query_with_context = (
            f"Пользователь ранее задал вопрос: {history[-1]['question']}\n"
            f"Система не смогла дать ответ или ответила неудовлетворительно.\n"
            f"Пользователь требует ответ (написал: \"{query}\").\n\n"
            f"ОБЯЗАТЕЛЬНО дай полный, подробный ответ на вопрос: {history[-1]['question']}"
        )
    elif history:
        last_qa = history[-1]
        query_with_context = f"Предыдущий вопрос: {last_qa['question']}\nПредыдущий ответ: {last_qa['answer'][:300]}...\n\nТекущий вопрос: {query}"
        # 1C: переписываем короткий follow-up для точного поиска в Qdrant
        search_query = rewrite_query_if_needed(query, history)
    else:
        query_with_context = query

    # 1E: обработка отрицаний
    search_query = analyze_query_intent(search_query)
    # 1F: обогащение запроса по типу намерения
    search_query = classify_and_enrich_query(search_query)

    # Поиск документов - увеличено для лучшего поиска формул
    results = search_documents(search_query, limit=15)

    # 1D: уверенность по raw cosine score (до бустинга)
    best_raw_score = max((r.get('raw_score', r['score']) for r in results), default=0.0) if results else 0.0
    print(f"[Confidence] best_raw_score={best_raw_score:.3f}")

    if not results:
        return jsonify({
            'answer': 'Не найдено релевантных документов',
            'sources': []
        })
    
    # Формируем контекст с указанием источника
    # Расширяем контекст вокруг найденных чанков (для формул)
    expanded_results = expand_context_around_chunks(results, window=1)
    
    # Приоритет Справочнику - ставим его чанки в начало
    spravochnik_parts = []
    other_parts = []
    seen_chunks = set()  # Для дедупликации
    
    for r in expanded_results:
        filename = r["payload"]["filename"]
        chunk_idx = r["payload"]["chunk_index"]
        chunk_key = (filename, chunk_idx)
        
        # Пропускаем дубликаты
        if chunk_key in seen_chunks:
            continue
        seen_chunks.add(chunk_key)
        
        text = r["payload"]["text"]
        # Пропускаем HTML-таблицы (пустые <th></th>) — бесполезны для LLM
        if text.count('<th') + text.count('<tr') + text.count('<td') > 10:
            continue
        context_entry = f"[Источник: {filename}, чанк {chunk_idx+1}]\n{text}"
        
        if "Справочник" in filename:
            spravochnik_parts.append(context_entry)
        else:
            other_parts.append(context_entry)
    
    # Справочник в начале, остальные - потом
    context = "\n\n".join(spravochnik_parts + other_parts)
    # Ограничиваем контекст: при > 60К символов DeepSeek возвращает пустой ответ
    MAX_CONTEXT_CHARS = 60000
    if len(context) > MAX_CONTEXT_CHARS:
        context = context[:MAX_CONTEXT_CHARS]
        print(f"[CONTEXT] Обрезан до {MAX_CONTEXT_CHARS} символов")
    sources = [{
        'filename': r["payload"]["filename"],
        'text': r["payload"]["text"][:200] + "...",
        'score': r["score"]
    } for r in results]
    
    # Генерируем ответ с учетом истории (web — с таблицами)
    answer = ask_llm(query_with_context, context, channel="web", confidence_score=best_raw_score)
    
    # Сохраняем в историю чата
    try:
        # Если нет сессии - создаем новую
        if not session_id:
            # Создаем название из первых 50 символов запроса
            title = query[:50] + ('...' if len(query) > 50 else '')
            session_id = db.create_chat_session(request.user_id, 'web', title)
        
        # Сохраняем вопрос и ответ
        db.add_chat_message(session_id, 'user', query)
        db.add_chat_message(session_id, 'assistant', answer)
    except Exception as e:
        print(f"Ошибка сохранения в историю: {e}")
    
    return jsonify({
        'answer': answer,
        'sources': sources,
        'session_id': session_id
    })

@app.route('/api/transcribe', methods=['POST'])
@jwt_required
def transcribe_audio():
    """Speech-to-Text: принимает аудио, возвращает текст"""
    if 'audio' not in request.files:
        return jsonify({'error': 'Аудио файл не передан'}), 400
    
    audio_file = request.files['audio']
    
    if not POLZA_STT_API_KEY:
        return jsonify({'error': 'STT API ключ не настроен'}), 500
    
    try:
        # Отправляем напрямую в Polza API (без сохранения на диск)
        response = requests.post(
            POLZA_STT_URL,
            headers={
                'Authorization': f'Bearer {POLZA_STT_API_KEY}'
            },
            files={
                'file': (audio_file.filename or 'audio.webm', audio_file.stream, audio_file.content_type or 'audio/webm')
            },
            data={
                'model': POLZA_STT_MODEL,
                'language': 'ru'
            },
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"STT API error: {response.status_code} {response.text}")
            return jsonify({'error': 'Ошибка распознавания речи'}), 500
        
        result = response.json()
        text = result.get('text', '').strip()
        
        if not text:
            return jsonify({'error': 'Речь не распознана'}), 400
        
        return jsonify({'text': text})
        
    except requests.exceptions.Timeout:
        return jsonify({'error': 'Таймаут распознавания'}), 504
    except Exception as e:
        print(f"STT error: {e}")
        return jsonify({'error': 'Ошибка распознавания речи'}), 500

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

# === Юридические документы ===
_DOCS_DIR = os.path.join(os.path.dirname(__file__), 'docs_text')

_DOC_FILES = {
    'oferta':             'Оферта Global Dent Университет.txt',
    'privacy':            'Политика обработки персональных данных.txt',
    'consent-data':       'Согласие на ОПД .txt',
    'consent-newsletter': 'Согласие на рассылку .txt',
}

_DOC_TITLES = {
    'oferta':             'Оферта',
    'privacy':            'Политика обработки персональных данных',
    'consent-data':       'Согласие на обработку персональных данных',
    'consent-newsletter': 'Согласие на рассылку',
}

def _load_doc(key):
    path = os.path.join(_DOCS_DIR, _DOC_FILES[key])
    try:
        with open(path, encoding='utf-8') as f:
            return f.read()
    except Exception:
        return ''

@app.route('/docs/oferta')
def doc_oferta():
    return render_template('doc_page.html', title=_DOC_TITLES['oferta'], content=_load_doc('oferta'))

@app.route('/docs/privacy')
def doc_privacy():
    return render_template('doc_page.html', title=_DOC_TITLES['privacy'], content=_load_doc('privacy'))

@app.route('/docs/consent-data')
def doc_consent_data():
    return render_template('doc_page.html', title=_DOC_TITLES['consent-data'], content=_load_doc('consent-data'))

@app.route('/docs/consent-newsletter')
def doc_consent_newsletter():
    return render_template('doc_page.html', title=_DOC_TITLES['consent-newsletter'], content=_load_doc('consent-newsletter'))

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return "OK", 200

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
    # Инициализируем базу данных при старте
    print("Инициализация базы данных...")
    db.init_db()
    
    app.run(host='0.0.0.0', port=5000, debug=True)
