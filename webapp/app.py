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

# Регистрируем Blueprint
app.register_blueprint(admin_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(chat_bp)
app.config['UPLOAD_FOLDER'] = '/documents'
app.config['PROCESSED_FOLDER'] = '/shared/processed'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max

OLLAMA_URL = "http://ollama:11434"
QDRANT_URL = "http://qdrant:6333"
COLLECTION_NAME = "documents"

# Polza.ai API настройки (OpenAI-совместимый endpoint)
POLZA_API_KEY = os.getenv('POLZA_API_KEY', '')
POLZA_URL = "https://api.polza.ai/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

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

def search_documents(query, limit=50):
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
            "limit": limit * 3 if not search_filter else limit,  # Увеличили для лучшего охвата
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
        import re
        for result in results:
            filename = result["payload"]["filename"]
            total_chunks = result["payload"]["total_chunks"]
            text = result["payload"]["text"]
            text_lower = text.lower()
            
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
        MIN_SCORE_THRESHOLD = 0.40  # Снизили порог для более широкого охвата
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

def ask_llm(query, context, model="deepseek"):
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
2. ПРОВЕРЬ ВСЕ переменные формулы - есть ли они в данных пользователя
3. ЕСЛИ НЕ ХВАТАЕТ данных - СПРОСИ у пользователя:
   - Чётко укажи, КАКИХ данных не хватает
   - Объясни ЗАЧЕМ они нужны (какая переменная в формуле)
   - Предложи значения по умолчанию из контекста (если есть нормы)
   - НЕ ВЫПОЛНЯЙ расчёт без полных данных
4. ЕСЛИ все данные есть:
   - Подставь данные в формулу
   - Выполни вычисления ШАГ ЗА ШАГОМ
   - Покажи промежуточные расчёты
   - Дай итоговый результат с пояснением

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
Добавь секцию "Вопросы:" с 2-3 уточняющими вопросами.
Обязательный формат:

Вопросы:
1. <текст вопроса>
2. <текст вопроса>
3. <текст вопроса>

ПРИМЕР УТОЧНЯЮЩИХ ВОПРОСОВ:
- Если спросили о нормочасе → предложи узнать про коэффициент загрузки, рабочее время, ВВ
- Если спросили о материалах → предложи узнать конкретные расходы, стоимость, поставщиков
- Если спросили "что делать" → предложи конкретные метрики, инструменты контроля

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

{examples_text}"""
    
    user_prompt = f"""
{context}

Вопрос пользователя: {query}

КРИТИЧЕСКИ ВАЖНО: НЕ ИСПОЛЬЗУЙ ЗВЕЗДОЧКИ * ИЛИ **, РЕШЕТКИ #, nbsp;
Пиши ОБЫЧНЫМ ТЕКСТОМ без форматирования.

Инструкция: 
- Если в контексте есть прямой ответ - ответь УВЕРЕННО, цитируя формулы и определения ДОСЛОВНО
- Если есть что-то ПОХОЖЕЕ - используй и ответь ПО АНАЛОГИИ, чтобы помочь пользователю
- Если информации нет СОВСЕМ - НЕ упоминай "в контексте нет". Вместо этого скажи: "На данный момент у меня недостаточно информации, чтобы ответить на ваш вопрос в такой формулировке. Возможно, вам помогут эти варианты вопросов:" и предложи 3-4 переформулировки"""
    
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
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        # Возвращаем понятную ошибку без fallback на Ollama
        error_msg = str(e)
        if "402" in error_msg:
            return "⚠️ Закончился баланс Polza.ai API. Пополните баланс на https://polza.ai/dashboard"
        elif "401" in error_msg:
            return "⚠️ Ошибка авторизации Polza.ai API. Проверьте API ключ."
        else:
            return f"⚠️ Ошибка Polza.ai API: {error_msg}"

def chunk_text(text, chunk_size=350, overlap=70):
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
        
        # Разбиваем на чанки
        words = text.split()
        chunks = []
        chunk_size = 350  # Оптимизировано для формул
        overlap = 70      # Больший overlap для лучшего покрытия формул
        
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
    
    # Если есть история - добавляем контекст предыдущего вопроса
    if history:
        last_qa = history[-1]
        query_with_context = f"Предыдущий вопрос: {last_qa['question']}\nПредыдущий ответ: {last_qa['answer'][:300]}...\n\nТекущий вопрос: {query}"
    else:
        query_with_context = query
    
    # Поиск документов
    results = search_documents(query, limit=15)
    
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
        context_entry = f"[Источник: {filename}, чанк {chunk_idx+1}]\n{text}"
        
        if "Справочник" in filename:
            spravochnik_parts.append(context_entry)
        else:
            other_parts.append(context_entry)
    
    context = "\n\n".join(spravochnik_parts + other_parts)
    sources = [{
        'filename': r["payload"]["filename"],
        'text': r["payload"]["text"][:200] + "...",
        'score': r["score"]
    } for r in results]
    
    # Генерируем ответ
    answer = ask_llm(query_with_context, context)
    
    # Логируем запрос
    try:
        db.log_query(user['id'], query, answer)
    except Exception as e:
        print(f"Ошибка логирования запроса: {e}")
    
    return jsonify({
        'answer': answer,
        'sources': sources,
        'authorized': True
    })

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
    
    # Если есть история - добавляем контекст предыдущего вопроса
    if history:
        # Берем последний вопрос-ответ для контекста
        last_qa = history[-1]
        query_with_context = f"Предыдущий вопрос: {last_qa['question']}\nПредыдущий ответ: {last_qa['answer'][:300]}...\n\nТекущий вопрос: {query}"
    else:
        query_with_context = query
    
    # Поиск документов - увеличено для лучшего поиска формул
    results = search_documents(query, limit=15)
    
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
        context_entry = f"[Источник: {filename}, чанк {chunk_idx+1}]\n{text}"
        
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
