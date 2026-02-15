import requests

# Получаем все чанки
r = requests.post(
    'http://qdrant-docling:6333/collections/documents/points/scroll',
    json={'limit': 500, 'with_payload': True, 'with_vector': False}
)

points = r.json()['result']['points']
target = 'валовой выручке от завершенных комплексных планов'

matches = [p for p in points if target in p['payload']['text']]
print(f'Найдено чанков с текстом: {len(matches)}\n')

if matches:
    p = matches[0]
    print(f"ID: {p['id']}")
    print(f"Chunk index: {p['payload']['chunk_index']}")
    print(f"File: {p['payload']['filename']}")
    print(f"\nТекст чанка:\n{p['payload']['text'][:1000]}")
