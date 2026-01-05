#!/usr/bin/env python3
"""
Скрипт для обработки документов с помощью Docling и создания векторных эмбеддингов
"""

import os
import sys
from pathlib import Path
from docling.document_converter import DocumentConverter

def process_document(file_path: str, output_dir: str = "/shared/processed"):
    """
    Обрабатывает документ и извлекает текст
    
    Args:
        file_path: путь к документу
        output_dir: директория для сохранения результатов
    """
    try:
        # Создаем конвертер
        converter = DocumentConverter()
        
        # Конвертируем документ
        print(f"Обработка документа: {file_path}")
        result = converter.convert(file_path)
        
        # Извлекаем текст
        text_content = result.document.export_to_markdown()
        
        # Сохраняем результат
        os.makedirs(output_dir, exist_ok=True)
        output_file = Path(output_dir) / f"{Path(file_path).stem}.md"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(text_content)
        
        print(f"Результат сохранен: {output_file}")
        return {
            "success": True,
            "output_file": str(output_file),
            "text": text_content
        }
        
    except Exception as e:
        print(f"Ошибка обработки документа: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def process_directory(input_dir: str, output_dir: str = "/shared/processed"):
    """
    Обрабатывает все документы в директории
    """
    supported_formats = ['.pdf', '.docx', '.pptx', '.html', '.md']
    
    for file_path in Path(input_dir).rglob('*'):
        if file_path.is_file() and file_path.suffix.lower() in supported_formats:
            process_document(str(file_path), output_dir)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python process_documents.py <путь_к_документу_или_папке>")
        sys.exit(1)
    
    input_path = sys.argv[1]
    
    if os.path.isdir(input_path):
        process_directory(input_path)
    else:
        process_document(input_path)
