import requests

QDRANT_URL = 'http://qdrant-docling:6333'
OLLAMA_URL = 'http://ollama-docling:11434'
query = 'что такое система сбалансированных показателей'

# Get embedding
r1 = requests.post(
    f'{OLLAMA_URL}/api/embeddings',
    json={'model': 'nomic-embed-text', 'prompt': query},
    timeout=60
)
embedding = r1.json()['embedding']

# Search ONLY in Справочник
r2 = requests.post(
    f'{QDRANT_URL}/collections/documents/points/search',
    json={
        'vector': embedding,
        'limit': 5,
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
results = r2.json()['result']

print(f"Query: {query}\n")
print(f"Found {len(results)} chunks from Справочник:\n")
for i, r in enumerate(results, 1):
    score = r['score']
    chunk_idx = r['payload']['chunk_index']
    total = r['payload']['total_chunks']
    text = r['payload']['text'][:300]
    
    print(f"{i}. Score: {score:.3f}, Chunk: {chunk_idx+1}/{total}")
    print(f"   {text}...")
    print()
