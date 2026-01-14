import requests

QDRANT_URL = 'http://qdrant-docling:6333'

# Scroll through Справочник chunks
r = requests.post(
    f'{QDRANT_URL}/collections/documents/points/scroll',
    json={
        'limit': 100,
        'with_payload': True,
        'filter': {
            'must': [{
                'key': 'filename',
                'match': {'value': 'Справочник Мудрого Руководителя и Золотой Стандарт Аудита.md'}
            }]
        }
    },
    timeout=30
)

points = r.json()['result']['points']

# Sort by chunk_index
sorted_points = sorted(points, key=lambda p: p['payload']['chunk_index'])

print(f"Total chunks from Справочник: {len(sorted_points)}\n")
print("First 7 chunks:\n")
for p in sorted_points[:7]:
    idx = p['payload']['chunk_index']
    total = p['payload']['total_chunks']
    text = p['payload']['text'][:300]
    
    print(f"Chunk {idx+1}/{total}:")
    print(f"{text}...\n")
    print("-" * 80)
