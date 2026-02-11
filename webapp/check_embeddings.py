import requests

# Проверяем общее количество
r = requests.get('http://qdrant-docling:6333/collections/documents')
total = r.json()['result']['points_count']
print(f'Всего точек в коллекции: {total}')

# Проверяем новый файл
r2 = requests.post(
    'http://qdrant-docling:6333/collections/documents/points/scroll',
    json={
        'limit': 100,
        'with_payload': True,
        'with_vector': False,
        'filter': {
            'must': [{
                'key': 'filename',
                'match': {'text': 'LlamaCloude_pir7.md'}
            }]
        }
    }
)
points = r2.json()['result']['points']
print(f'\nТочек с LlamaCloude_pir7.md: {len(points)}')

if points:
    print(f'\nПример чанка:')
    print(f"Chunk {points[0]['payload']['chunk_index']} из {points[0]['payload']['total_chunks']}")
    print(f"Текст: {points[0]['payload']['text'][:200]}...")
