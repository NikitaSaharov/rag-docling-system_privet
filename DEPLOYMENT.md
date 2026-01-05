# Production Deployment Guide

## Инструкция по развертыванию RAG системы на сервере

### 1. Подготовка сервера

#### Требования:
- Ubuntu 22.04 LTS / Debian 11+
- 4+ CPU, 8GB+ RAM, 50GB+ SSD
- Root или sudo доступ

#### Установка Docker:
```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Установка Docker Compose
sudo apt install docker-compose-plugin

# Добавление пользователя в группу docker
sudo usermod -aG docker $USER
newgrp docker

# Проверка установки
docker --version
docker compose version
```

#### Настройка firewall:
```bash
# UFW firewall
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw enable
sudo ufw status
```

### 2. Развертывание приложения

#### Клонирование проекта:
```bash
cd /opt
sudo git clone <your-repo-url> rag-system
cd rag-system
sudo chown -R $USER:$USER .
```

#### Настройка переменных окружения:
```bash
# Копируем шаблон
cp .env.example .env

# Редактируем переменные
nano .env

# Генерация безопасных ключей:
# QDRANT_API_KEY
openssl rand -hex 32

# SECRET_KEY
python3 -c "import secrets; print(secrets.token_hex(32))"

# POSTGRES_PASSWORD
openssl rand -base64 32

# REDIS_PASSWORD
openssl rand -base64 32
```

**Важно:** Заполните все переменные в .env файле!

### 3. Подготовка данных

#### Загрузка векторной базы:
```bash
# Если есть backup Qdrant данных
mkdir -p qdrant_data
# Распаковать backup в qdrant_data/

# Или создать новую коллекцию после запуска
```

#### Настройка SSL сертификатов:

**Вариант A: Let's Encrypt (рекомендуется)**
```bash
# Установка Certbot
sudo apt install certbot

# Получение сертификата (замените на ваш домен)
sudo certbot certonly --standalone -d your-domain.com -d www.your-domain.com

# Копирование сертификатов
sudo mkdir -p nginx/ssl
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem nginx/ssl/
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem nginx/ssl/
sudo chown -R $USER:$USER nginx/ssl
```

**Вариант B: Self-signed (для тестирования)**
```bash
mkdir -p nginx/ssl
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/privkey.pem \
  -out nginx/ssl/fullchain.pem
```

#### Обновление nginx конфигурации:
```bash
# Отредактируйте nginx/nginx.conf
nano nginx/nginx.conf

# Замените "your-domain.com" на ваш домен
```

### 4. Запуск системы

#### Сборка и запуск контейнеров:
```bash
# Сборка образов
docker compose -f docker-compose.prod.yml build

# Запуск в фоновом режиме
docker compose -f docker-compose.prod.yml up -d

# Проверка статуса
docker compose -f docker-compose.prod.yml ps

# Просмотр логов
docker compose -f docker-compose.prod.yml logs -f webapp
```

#### Инициализация базы данных:
```bash
# Создание таблиц в PostgreSQL
docker compose -f docker-compose.prod.yml exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB

# Выполнить SQL из плана (см. Production Deployment & Security Guide)
CREATE TABLE user_queries (...);
CREATE INDEX ...;
```

#### Загрузка модели Ollama (если нужна):
```bash
docker compose -f docker-compose.prod.yml exec ollama ollama pull nomic-embed-text
```

### 5. Проверка работоспособности

#### Healthchecks:
```bash
# Nginx
curl -I http://localhost/health

# Qdrant
docker compose -f docker-compose.prod.yml exec qdrant curl http://localhost:6333/health

# PostgreSQL
docker compose -f docker-compose.prod.yml exec postgres pg_isready

# Redis
docker compose -f docker-compose.prod.yml exec redis redis-cli ping
```

#### Открываем в браузере:
```
https://your-domain.com
```

### 6. Безопасность

#### Ограничение доступа к Docker API:
```bash
# Редактируем docker-compose.prod.yml - убедитесь что порты не exposed
# Только nginx должен быть доступен извне (80, 443)
```

#### Удаление исходных документов после обработки:
```bash
# После создания эмбеддингов удалить:
rm -rf documents/*
rm -rf shared/processed/*

# Или хранить на отдельном сервере с ограниченным доступом
```

#### Регулярное обновление:
```bash
# Обновление образов
docker compose -f docker-compose.prod.yml pull

# Перезапуск с новыми версиями
docker compose -f docker-compose.prod.yml up -d
```

### 7. Мониторинг

#### Просмотр логов:
```bash
# Все контейнеры
docker compose -f docker-compose.prod.yml logs -f

# Конкретный сервис
docker compose -f docker-compose.prod.yml logs -f webapp

# Логи Nginx
docker compose -f docker-compose.prod.yml exec nginx tail -f /var/log/nginx/access.log
docker compose -f docker-compose.prod.yml exec nginx tail -f /var/log/nginx/error.log
```

#### Мониторинг ресурсов:
```bash
# Использование ресурсов контейнерами
docker stats

# Дисковое пространство
df -h
docker system df
```

### 8. Backup

#### Создание backup скрипта:
```bash
cat > /opt/rag-system/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/backups/rag-system"
DATE=$(date +%Y%m%d_%H%M%S)

# Создаем директорию
mkdir -p $BACKUP_DIR

# Backup Qdrant
docker compose -f /opt/rag-system/docker-compose.prod.yml exec -T qdrant \
  tar czf - /qdrant/storage > $BACKUP_DIR/qdrant_$DATE.tar.gz

# Backup PostgreSQL
docker compose -f /opt/rag-system/docker-compose.prod.yml exec -T postgres \
  pg_dump -U $POSTGRES_USER $POSTGRES_DB | gzip > $BACKUP_DIR/postgres_$DATE.sql.gz

# Удаляем старые backup'ы (старше 7 дней)
find $BACKUP_DIR -type f -mtime +7 -delete

echo "Backup completed: $DATE"
EOF

chmod +x /opt/rag-system/backup.sh
```

#### Настройка cron для автоматического backup:
```bash
# Добавляем в crontab
crontab -e

# Добавить строку (backup каждый день в 3:00 AM):
0 3 * * * /opt/rag-system/backup.sh >> /var/log/rag-backup.log 2>&1
```

### 9. Обслуживание

#### Перезапуск сервисов:
```bash
# Перезапуск всех
docker compose -f docker-compose.prod.yml restart

# Перезапуск конкретного сервиса
docker compose -f docker-compose.prod.yml restart webapp
```

#### Обновление кода:
```bash
cd /opt/rag-system
git pull
docker compose -f docker-compose.prod.yml build webapp
docker compose -f docker-compose.prod.yml up -d webapp
```

#### Очистка:
```bash
# Очистка неиспользуемых образов и контейнеров
docker system prune -a

# Очистка логов (если слишком большие)
truncate -s 0 /var/lib/docker/containers/*/*-json.log
```

### 10. Troubleshooting

#### Webapp не запускается:
```bash
# Проверка логов
docker compose -f docker-compose.prod.yml logs webapp

# Проверка переменных окружения
docker compose -f docker-compose.prod.yml exec webapp env | grep OPENROUTER
```

#### Qdrant недоступен:
```bash
# Проверка статуса
docker compose -f docker-compose.prod.yml exec qdrant curl localhost:6333/health

# Проверка данных
docker compose -f docker-compose.prod.yml exec qdrant ls -la /qdrant/storage
```

#### Высокая нагрузка:
```bash
# Увеличить количество Gunicorn workers
# Отредактировать webapp/Dockerfile.prod: --workers 8

# Или через environment в docker-compose.prod.yml:
GUNICORN_WORKERS=8
```

#### SSL сертификат истек:
```bash
# Обновление Let's Encrypt
sudo certbot renew

# Копирование новых сертификатов
sudo cp /etc/letsencrypt/live/your-domain.com/* nginx/ssl/

# Перезагрузка nginx
docker compose -f docker-compose.prod.yml restart nginx
```

### 11. Масштабирование

#### Увеличение количества webapp инстансов:
```bash
docker compose -f docker-compose.prod.yml up -d --scale webapp=3
```

#### Мониторинг производительности:
```bash
# Установка htop
sudo apt install htop

# Мониторинг в реальном времени
htop
```

---

## Дополнительные ресурсы

- См. `Production Deployment & Security Guide` (план) для детальной информации
- Документация Docker: https://docs.docker.com/
- Документация Qdrant: https://qdrant.tech/documentation/
- Nginx best practices: https://nginx.org/en/docs/

## Поддержка

При возникновении проблем проверьте:
1. Логи контейнеров
2. Статус healthchecks
3. Переменные окружения
4. Firewall правила
5. SSL сертификаты
