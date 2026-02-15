#!/bin/bash
# Скрипт развертывания Docling на VPS сервере
# Запускать на сервере: bash deploy_to_vps.sh

set -e

echo "=========================================="
echo "  Развертывание Docling на VPS"
echo "=========================================="
echo ""

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Обновление системы
echo -e "${YELLOW}[1/8] Обновление системы...${NC}"
apt update && apt upgrade -y

# 2. Установка Docker
echo -e "${YELLOW}[2/8] Установка Docker...${NC}"
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
    echo -e "${GREEN}✓ Docker установлен${NC}"
else
    echo -e "${GREEN}✓ Docker уже установлен${NC}"
fi

# 3. Установка Docker Compose
echo -e "${YELLOW}[3/8] Установка Docker Compose...${NC}"
if ! command -v docker-compose &> /dev/null; then
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    echo -e "${GREEN}✓ Docker Compose установлен${NC}"
else
    echo -e "${GREEN}✓ Docker Compose уже установлен${NC}"
fi

# 4. Создание директории проекта
echo -e "${YELLOW}[4/8] Создание директории проекта...${NC}"
mkdir -p /opt/docling
cd /opt/docling
echo -e "${GREEN}✓ Директория создана: /opt/docling${NC}"

# 5. Клонирование проекта (если есть git репозиторий) или подготовка к загрузке файлов
echo -e "${YELLOW}[5/8] Подготовка к загрузке файлов...${NC}"
echo "Загрузите файлы проекта в /opt/docling через SCP:"
echo "  scp -r ./Docling/* root@168.222.192.52:/opt/docling/"
echo ""
echo "Или создайте Git репозиторий и клонируйте:"
echo "  git clone <ваш-репозиторий> /opt/docling"
echo ""
read -p "Файлы загружены? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Загрузите файлы и запустите скрипт снова"
    exit 1
fi

# 6. Создание .env файла
echo -e "${YELLOW}[6/8] Настройка переменных окружения...${NC}"
if [ ! -f /opt/docling/.env.local ]; then
    cat > /opt/docling/.env.local << 'EOF'
# Polza.ai API (для DeepSeek)
POLZA_API_KEY=your_polza_api_key_here

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# JWT
JWT_SECRET_KEY=$(openssl rand -hex 32)

# Flask
SECRET_KEY=$(openssl rand -hex 32)
FLASK_ENV=production

# Database
DB_PATH=/db/docling.db

# Flask API URL
FLASK_API_URL=http://webapp:5000

# Security
ALLOWED_HOSTS=168.222.192.52,docling.yourdomain.com
CORS_ORIGINS=https://docling.yourdomain.com
EOF
    echo -e "${GREEN}✓ Создан .env.local - отредактируйте его!${NC}"
    echo -e "${YELLOW}⚠ ВАЖНО: Отредактируйте /opt/docling/.env.local${NC}"
    echo "  nano /opt/docling/.env.local"
    read -p "Отредактировали .env.local? (y/n) " -n 1 -r
    echo
else
    echo -e "${GREEN}✓ .env.local уже существует${NC}"
fi

# 7. Настройка firewall
echo -e "${YELLOW}[7/8] Настройка firewall...${NC}"
if command -v ufw &> /dev/null; then
    ufw allow 22/tcp
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw allow 5000/tcp
    ufw --force enable
    echo -e "${GREEN}✓ Firewall настроен${NC}"
else
    echo -e "${YELLOW}⚠ UFW не установлен, пропускаем${NC}"
fi

# 8. Запуск Docker Compose
echo -e "${YELLOW}[8/8] Запуск приложения...${NC}"
cd /opt/docling
docker-compose up -d

echo ""
echo "=========================================="
echo -e "${GREEN}✓ Развертывание завершено!${NC}"
echo "=========================================="
echo ""
echo "Приложение доступно по адресу:"
echo "  http://168.222.192.52:5000"
echo ""
echo "Проверка статуса:"
echo "  docker-compose ps"
echo ""
echo "Логи:"
echo "  docker-compose logs -f webapp"
echo ""
echo "Остановка:"
echo "  docker-compose down"
echo ""
echo "=========================================="
