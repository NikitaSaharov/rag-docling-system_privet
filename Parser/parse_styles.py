#!/usr/bin/env python3
"""
Парсер стилей и шрифтов с веб-сайта
Извлекает CSS, цвета, шрифты и создает файл с результатами
"""

import requests
from bs4 import BeautifulSoup
import re
import json
from collections import Counter
from urllib.parse import urljoin, urlparse

def fetch_page(url):
    """Получает HTML страницы"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Ошибка загрузки страницы: {e}")
        return None

def extract_colors(css_text):
    """Извлекает все цвета из CSS"""
    colors = []
    
    # HEX цвета
    hex_pattern = r'#(?:[0-9a-fA-F]{3}){1,2}\b'
    colors.extend(re.findall(hex_pattern, css_text))
    
    # RGB/RGBA
    rgb_pattern = r'rgba?\([^)]+\)'
    colors.extend(re.findall(rgb_pattern, css_text))
    
    return colors

def extract_fonts(css_text):
    """Извлекает шрифты из CSS"""
    fonts = []
    
    # font-family
    font_pattern = r'font-family:\s*([^;]+);'
    fonts.extend(re.findall(font_pattern, css_text, re.IGNORECASE))
    
    return fonts

def extract_font_sizes(css_text):
    """Извлекает размеры шрифтов"""
    sizes = []
    
    # font-size
    size_pattern = r'font-size:\s*([^;]+);'
    sizes.extend(re.findall(size_pattern, css_text, re.IGNORECASE))
    
    return sizes

def get_css_from_page(html, base_url):
    """Извлекает все CSS с страницы"""
    soup = BeautifulSoup(html, 'html.parser')
    all_css = ""
    
    # Inline styles
    style_tags = soup.find_all('style')
    for style in style_tags:
        all_css += style.string if style.string else ""
    
    # External CSS links
    css_links = soup.find_all('link', rel='stylesheet')
    for link in css_links:
        href = link.get('href')
        if href:
            css_url = urljoin(base_url, href)
            try:
                css_response = requests.get(css_url, timeout=10)
                if css_response.status_code == 200:
                    all_css += css_response.text
                    print(f"✓ Загружен CSS: {css_url}")
            except Exception as e:
                print(f"✗ Ошибка загрузки CSS {css_url}: {e}")
    
    return all_css

def analyze_styles(url):
    """Основная функция анализа стилей"""
    print(f"🔍 Парсинг стилей с {url}...\n")
    
    # Получаем HTML
    html = fetch_page(url)
    if not html:
        return None
    
    # Получаем весь CSS
    all_css = get_css_from_page(html, url)
    
    # Извлекаем данные
    colors = extract_colors(all_css)
    fonts = extract_fonts(all_css)
    font_sizes = extract_font_sizes(all_css)
    
    # Подсчитываем частоту использования
    color_counter = Counter(colors)
    font_counter = Counter(fonts)
    size_counter = Counter(font_sizes)
    
    # Формируем результат
    result = {
        'url': url,
        'colors': {
            'all': colors,
            'most_common': color_counter.most_common(15),
            'unique_count': len(set(colors))
        },
        'fonts': {
            'all': fonts,
            'most_common': font_counter.most_common(10),
            'unique_count': len(set(fonts))
        },
        'font_sizes': {
            'all': font_sizes,
            'most_common': size_counter.most_common(10),
            'unique_count': len(set(font_sizes))
        }
    }
    
    return result

def save_results(result, output_file='styles_analysis.json'):
    """Сохраняет результаты в JSON"""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\n💾 Результаты сохранены в {output_file}")

def print_summary(result):
    """Выводит краткую сводку"""
    print("\n" + "="*60)
    print("📊 СВОДКА ПО СТИЛЯМ")
    print("="*60)
    
    print(f"\n🎨 ЦВЕТА (найдено уникальных: {result['colors']['unique_count']})")
    print("\nТоп-10 наиболее используемых:")
    for color, count in result['colors']['most_common'][:10]:
        print(f"  {color:<20} - использован {count} раз")
    
    print(f"\n🔤 ШРИФТЫ (найдено уникальных: {result['fonts']['unique_count']})")
    print("\nНаиболее используемые:")
    for font, count in result['fonts']['most_common'][:5]:
        print(f"  {font[:50]:<50} - использован {count} раз")
    
    print(f"\n📏 РАЗМЕРЫ ШРИФТОВ (найдено уникальных: {result['font_sizes']['unique_count']})")
    print("\nНаиболее используемые:")
    for size, count in result['font_sizes']['most_common'][:8]:
        print(f"  {size:<20} - использован {count} раз")

def create_css_template(result, output_file='extracted_styles.css'):
    """Создает CSS файл с извлеченными стилями"""
    css_content = """/* Извлеченные стили с сайта */
/* Автоматически сгенерировано parse_styles.py */

:root {
    /* Основные цвета */
"""
    
    # Добавляем топ цвета
    for i, (color, count) in enumerate(result['colors']['most_common'][:10], 1):
        css_content += f"    --color-{i}: {color};\n"
    
    css_content += "\n    /* Шрифты */\n"
    
    # Добавляем топ шрифты
    for i, (font, count) in enumerate(result['fonts']['most_common'][:5], 1):
        css_content += f"    --font-{i}: {font};\n"
    
    css_content += "}\n\n/* Применение стилей */\nbody {\n"
    
    if result['fonts']['most_common']:
        main_font = result['fonts']['most_common'][0][0]
        css_content += f"    font-family: {main_font};\n"
    
    css_content += "}\n"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(css_content)
    
    print(f"💾 CSS шаблон сохранен в {output_file}")

if __name__ == "__main__":
    # URL для парсинга
    target_url = "https://globaldent.group/"
    
    print("🚀 Запуск парсера стилей...")
    print(f"🌐 Целевой сайт: {target_url}\n")
    
    # Анализируем стили
    result = analyze_styles(target_url)
    
    if result:
        # Выводим сводку
        print_summary(result)
        
        # Сохраняем результаты
        save_results(result, 'styles_analysis.json')
        
        # Создаем CSS шаблон
        create_css_template(result, 'extracted_styles.css')
        
        print("\n✅ Парсинг завершен успешно!")
    else:
        print("\n❌ Ошибка парсинга")
