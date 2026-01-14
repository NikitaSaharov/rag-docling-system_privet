from qdrant_client import QdrantClient

client = QdrantClient(host='localhost', port=6333)

# Search by text content
print("=== Searching for chunks with 'ССП' ===")
results = client.scroll(
    collection_name='documents',
    limit=10,
    scroll_filter={
        'must': [
            {
                'key': 'text',
                'match': {'text': 'ССП'}
            }
        ]
    },
    with_payload=True
)

print(f"Found: {len(results[0])} points\n")
for i, point in enumerate(results[0], 1):
    filename = point.payload.get('filename', 'N/A')
    text_preview = point.payload.get('text', '')[:100]
    print(f"{i}. File: {filename}")
    print(f"   Text: {text_preview}...")
    print()

# Also try semantic search with actual question
print("\n=== Semantic search: 'что такое система сбалансированных показателей' ===")
query_embedding = client.query(
    collection_name='documents',
    query_text='что такое система сбалансированных показателей',
    limit=5
)
print(f"Found: {len(query_embedding)} results\n")
for i, result in enumerate(query_embedding, 1):
    filename = result.document.get('filename', 'N/A')
    score = result.score
    text_preview = result.document.get('text', '')[:100]
    print(f"{i}. Score: {score:.4f}, File: {filename}")
    print(f"   Text: {text_preview}...")
    print()
