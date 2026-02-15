# 🚀 Развертывание на сервере Timeweb

## Данные сервера
- **IP:** 5.129.194.184
- **Пароль root:** cB^Aqq8LXpcaog
- **ОС:** Ubuntu 24.04 LTS

## Шаг 1: Установка Docker (на сервере)

```bash
# Подключиться к серверу
ssh root@5.129.194.184

# Установить Docker
curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh

# Установить Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Проверить
docker --version
docker-compose --version
```

## Шаг 2: Клонировать проект

```bash
cd /opt
git clone https://github.com/NikitaSaharov/rag-docling-system_privet.git docling
cd docling
```

## Шаг 3: Загрузить эмбеддинги (с локальной машины)

```powershell
# С вашего компьютера выполните:
scp qdrant-embeddings.zip root@5.129.194.184:/opt/docling/
```

## Шаг 4: Распаковать эмбеддинги (на сервере)

```bash
cd /opt/docling
apt install -y unzip
unzip qdrant-embeddings.zip -d qdrant_restore
```

## Шаг 5: Настроить .env

```bash
cd /opt/docling
cp .env.example .env.local

# Отредактировать файл
nano .env.local
```

Добавить ключи:
```
POLZA_API_KEY=ваш_ключ_polza
TELEGRAM_BOT_TOKEN=ваш_токен_бота
```

## Шаг 6: Запустить контейнеры

```bash
docker-compose up -d
```

## Шаг 7: Восстановить эмбеддинги в Qdrant

```bash
# Дождаться запуска Qdrant (30 сек)
sleep 30

# Скопировать данные в volume
docker cp qdrant_restore/. qdrant-docling:/qdrant/storage/

# Перезапустить Qdrant
docker restart qdrant-docling
```

## Шаг 8: Проверка

```bash
# Проверить статус
docker-compose ps

# Проверить логи
docker-compose logs webapp

# Проверить эмбеддинги
curl http://localhost:6333/collections/documents
```

## Шаг 9: Доступ

Приложение доступно по адресу:
- http://5.129.194.184:5000

## Настройка HTTPS (опционально)

См. файл `setup_nginx_ssl.md`
