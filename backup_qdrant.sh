#!/bin/bash
# Скрипт для создания бэкапа Qdrant коллекции

BACKUP_DIR="./qdrant_backup"
COLLECTION_NAME="docling_vectors"

echo "Создание бэкапа Qdrant..."

# Создаем директорию для бэкапа
mkdir -p $BACKUP_DIR

# Создаем снэпшот через API
docker compose exec qdrant curl -X POST "http://localhost:6333/collections/${COLLECTION_NAME}/snapshots"

# Копируем данные Qdrant
docker compose cp qdrant:/qdrant/storage $BACKUP_DIR/

echo "Бэкап создан в $BACKUP_DIR"
echo "Размер бэкапа:"
du -sh $BACKUP_DIR
