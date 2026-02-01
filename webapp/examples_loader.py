"""
Модуль для загрузки и форматирования примеров вопрос-ответ
для few-shot learning в LLM
"""

import json
import os

def load_examples(max_examples=5):
    """
    Загружает примеры вопрос-ответ для few-shot learning
    
    Args:
        max_examples: максимальное количество примеров для загрузки
    
    Returns:
        list: список словарей с ключами 'question' и 'answer'
    """
    try:
        examples_path = os.path.join(os.path.dirname(__file__), 'examples.json')
        if not os.path.exists(examples_path):
            print(f"⚠️ Файл с примерами не найден: {examples_path}")
            return []
        
        with open(examples_path, 'r', encoding='utf-8') as f:
            examples = json.load(f)
        
        # Возвращаем первые max_examples примеров
        result = examples[:max_examples]
        print(f"✅ Загружено {len(result)} примеров для few-shot learning")
        return result
    
    except Exception as e:
        print(f"❌ Ошибка загрузки примеров: {e}")
        return []

def format_examples_for_prompt(examples):
    """
    Форматирует примеры для добавления в system prompt LLM
    
    Args:
        examples: список словарей с ключами 'question' и 'answer'
    
    Returns:
        str: отформатированный текст для добавления в prompt
    """
    if not examples:
        return ""
    
    formatted = "\n\n═══════════════════════════════════════════════════════════\n"
    formatted += "ПРИМЕРЫ ПРАВИЛЬНЫХ ОТВЕТОВ (ОБУЧАЮЩАЯ ВЫБОРКА)\n"
    formatted += "ОЧЕНЬ ВАЖНО: ОТВЕЧАЙ НА НОВЫЕ ВОПРОСЫ В ТАКОМ ЖЕ СТИЛЕ!\n"
    formatted += "═══════════════════════════════════════════════════════════\n\n"
    
    for i, ex in enumerate(examples, 1):
        formatted += f"───────────────────────────────────────────────────────────\n"
        formatted += f"ПРИМЕР {i}:\n\n"
        formatted += f"Вопрос:\n{ex['question']}\n\n"
        
        # Ограничим длину ответа до 600 символов, чтобы не переполнить prompt
        answer = ex['answer']
        if len(answer) > 600:
            answer = answer[:600] + "...\n[ответ сокращен для примера]"
        
        formatted += f"Ответ:\n{answer}\n\n"
    
    formatted += "═══════════════════════════════════════════════════════════\n"
    formatted += "ВНИМАНИЕ:\n"
    formatted += "- Используй ТОТ ЖЕ СТИЛЬ И СТРУКТУРУ ответов\n"
    formatted += "- НЕ используй звездочки ** или решетки ##\n"
    formatted += "- Всегда добавляй секцию 'Вопросы:' в конце\n"
    formatted += "- Объясняй формулы пошагово с расчетами\n"
    formatted += "═══════════════════════════════════════════════════════════\n\n"
    
    return formatted

def get_examples_summary():
    """Возвращает краткую статистику по примерам"""
    examples = load_examples(max_examples=100)  # Загружаем все
    if not examples:
        return "Примеры не загружены"
    
    avg_q_len = sum(len(ex['question']) for ex in examples) // len(examples)
    avg_a_len = sum(len(ex['answer']) for ex in examples) // len(examples)
    
    return f"""
    Статистика по примерам:
    - Всего примеров: {len(examples)}
    - Средняя длина вопроса: {avg_q_len} символов
    - Средняя длина ответа: {avg_a_len} символов
    """
