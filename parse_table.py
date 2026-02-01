"""Парсинг таблицы с примерами вопрос-ответ"""
from docx import Document
import json

docx_path = "/documents/таблица с парвильными вопрос-ответ для обучения.docx"

print(f"📖 Читаю файл: {docx_path}")
doc = Document(docx_path)

examples = []

# Проходим по всем таблицам
for table_idx, table in enumerate(doc.tables):
    print(f"\n📊 Таблица {table_idx + 1}: {len(table.rows)} строк, {len(table.columns)} столбцов")
    
    # Проверяем заголовки (первая строка)
    headers = [cell.text.strip() for cell in table.rows[0].cells]
    print(f"Заголовки: {headers}")
    
    # Парсим строки (пропускаем заголовок)
    for row_idx, row in enumerate(table.rows[1:], start=1):
        cells = [cell.text.strip() for cell in row.cells]
        
        # Столбец 1: Вопрос, Столбец 2: Ожидаемый ответ
        if len(cells) >= 3 and cells[1] and cells[2]:
            question = cells[1]  # Столбец "Вопрос"
            answer = cells[2]    # Столбец "Ожидаемый ответ"
            
            examples.append({
                "question": question,
                "answer": answer
            })
            
            print(f"\n  Строка {row_idx}:")
            print(f"    Q: {question[:100]}...")
            print(f"    A: {answer[:100]}...")

print(f"\n✅ Всего найдено примеров: {len(examples)}")

# Сохраняем в JSON
output_json = "/app/examples.json"
with open(output_json, 'w', encoding='utf-8') as f:
    json.dump(examples, f, ensure_ascii=False, indent=2)

print(f"💾 Сохранено в: {output_json}")

# Показываем статистику
print(f"\n📊 Статистика:")
print(f"  - Всего примеров: {len(examples)}")
print(f"  - Средняя длина вопроса: {sum(len(ex['question']) for ex in examples) // len(examples)} символов")
print(f"  - Средняя длина ответа: {sum(len(ex['answer']) for ex in examples) // len(examples)} символов")
