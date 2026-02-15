#!/bin/bash
set -e

echo "=== Настройка VectorStom ==="

# 1. Переменные окружения
echo "1. Создание .env..."
cat > .env << 'ENVEOF'
POLZA_API_KEY=ak_VdTnWuDz1CZGLuiiRH5qt34PlZQYx0NqROscaGPneIY
ENVEOF
export $(cat .env | xargs)

# 2. Восстановление векторов
echo "2. Восстановление векторов..."
docker volume create vectorstom_qdrant_data 2>/dev/null || true
docker run --rm -v vectorstom_qdrant_data:/qdrant/storage -v $(pwd)/qdrant-backup.tar.gz:/backup.tar.gz alpine sh -c "cd / && tar -xzf /backup.tar.gz"

# 3. Запуск
echo "3. Запуск системы..."
docker-compose -f docker-compose.simple-prod.yml up -d

# 4. Загрузка модели
echo "4. Загрузка модели Ollama..."
sleep 30
docker exec vectorstom-ollama ollama pull nomic-embed-text

echo ""
echo "=== Готово! ==="
echo "Откройте в браузере: http://95.163.226.177"
