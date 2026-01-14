import requests

QDRANT_URL = 'http://qdrant-docling:6333'

# Get chunk with index 2 (3-й чанк, т.к. индексация с 0)
r = requests.post(
    f'{QDRANT_URL}/collections/documents/points/scroll',
    json={
        'limit': 100,
        'with_payload': True,
        'filter': {
            'must': [
                {
                    'key': 'filename',
                    'match': {'value': 'Справочник Мудрого Руководителя и Золотой Стандарт Аудита.md'}
                },
                {
                    'key': 'chunk_index',
                    'match': {'value': 2}
                }
            ]
        }
    },
    timeout=30
)

points = r.json()['result']['points']

if points:
    p = points[0]
    print(f"Chunk {p['payload']['chunk_index']+1}/{p['payload']['total_chunks']}:")
    print(f"\n{p['payload']['text']}\n")
else:
    print("Chunk not found")
