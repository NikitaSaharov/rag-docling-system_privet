# Развертывание VectorStom на VPS

## Выбор сервера

### Рекомендуемая конфигурация для тестирования (5-10 пользователей)
- **Тариф:** High C1-M2-D20 (1 100 ₽/мес)
- **CPU:** 1 vCPU
- **RAM:** 2 ГБ
- **Диск:** 20 ГБ NVMe
- **ОС:** Ubuntu 24.04 LTS

### Для продакшена (10-50 пользователей)
- **Тариф:** High C4-M8-D120 (4 880 ₽/мес)
- **CPU:** 4 vCPU
- **RAM:** 8 ГБ
- **Диск:** 120 ГБ NVMe

---

## Шаг 1: Подготовка локальной системы

### 1.1 Создать бэкап Qdrant векторов
```bash
# На вашем Windows компьютере
cd "E:\СТОМПРАКТИКА ПРОЕКТЫ\Docling"
docker compose exec qdrant tar -czf /tmp/qdrant-backup.tar.gz /qdrant/storage
docker compose cp qdrant:/tmp/qdrant-backup.tar.gz ./qdrant-backup.tar.gz
```

### 1.2 Создать .env файл для продакшена
```bash
# Создайте файл .env.prod
POLZA_API_KEY=ak_VdTnWuDz1CZGLuiiRH5qt34PlZQYx0NqROscaGPneIY
```

### 1.3 Упаковать проект
```bash
# Создайте архив проекта (исключая ненужное)
tar -czf vectorstom.tar.gz \
  --exclude=node_modules \
  --exclude=__pycache__ \
  --exclude=*.pyc \
  --exclude=.git \
  webapp/ \
  docker-compose.simple-prod.yml \
  nginx-simple.conf \
  .env.prod \
  qdrant-backup.tar.gz
```

---

## Шаг 2: Настройка VPS

### 2.1 Подключение к серверу
После создания VPS в панели управления получите:
- IP адрес сервера
- SSH ключ или пароль root

```bash
ssh root@<IP_АДРЕС_СЕРВЕРА>
```

### 2.2 Установка Docker и Docker Compose
```bash
# Обновление системы
apt update && apt upgrade -y

# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Установка Docker Compose
apt install docker-compose -y

# Проверка установки
docker --version
docker-compose --version
```

### 2.3 Настройка firewall
```bash
# Установка UFW
apt install ufw -y

# Разрешаем SSH и HTTP
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp

# Включаем firewall
ufw enable
```

---

## Шаг 3: Загрузка проекта на сервер

### 3.1 Копирование файлов
```bash
# С вашего компьютера (новый терминал)
scp vectorstom.tar.gz root@<IP_АДРЕС_СЕРВЕРА>:/root/

# Вернитесь в SSH сессию на сервере
cd /root
tar -xzf vectorstom.tar.gz
cd /root
```

### 3.2 Восстановление данных Qdrant
```bash
# Создаем volume для Qdrant
docker volume create vectorstom_qdrant_data

# Распаковываем бэкап во временный контейнер
docker run --rm -v vectorstom_qdrant_data:/qdrant/storage \
  -v /root/qdrant-backup.tar.gz:/backup.tar.gz \
  alpine sh -c "cd / && tar -xzf /backup.tar.gz"
```

---

## Шаг 4: Запуск приложения

### 4.1 Загрузка переменных окружения
```bash
# Экспортируем API ключ
export POLZA_API_KEY=ak_VdTnWuDz1CZGLuiiRH5qt34PlZQYx0NqROscaGPneIY
```

### 4.2 Запуск контейнеров
```bash
# Используем упрощенный продакшн compose
docker-compose -f docker-compose.simple-prod.yml up -d

# Проверка статуса
docker-compose -f docker-compose.simple-prod.yml ps
```

### 4.3 Загрузка модели Ollama
```bash
# Загружаем nomic-embed-text для эмбеддингов
docker exec vectorstom-ollama ollama pull nomic-embed-text

# Проверка
docker exec vectorstom-ollama ollama list
```

---

## Шаг 5: Проверка работы

### 5.1 Проверка health endpoints
```bash
# Nginx
curl http://localhost/health

# Webapp
curl http://localhost/api/stats

# Qdrant
docker exec vectorstom-qdrant curl http://localhost:6333/health
```

### 5.2 Проверка векторов
```bash
curl http://localhost/api/documents
# Должно вернуть 3 документа с 902 векторами
```

### 5.3 Тестирование из браузера
Откройте: `http://<IP_АДРЕС_СЕРВЕРА>`

---

## Шаг 6: Настройка домена (опционально)

### 6.1 Добавление A-записи
В DNS вашего домена (например, vectorstom.ru):
```
A  @  <IP_АДРЕС_СЕРВЕРА>
```

### 6.2 Установка SSL сертификата (Let's Encrypt)
```bash
# Установка Certbot
apt install certbot python3-certbot-nginx -y

# Получение сертификата
certbot --nginx -d vectorstom.ru

# Автопродление
certbot renew --dry-run
```

---

## Мониторинг и обслуживание

### Просмотр логов
```bash
# Все сервисы
docker-compose -f docker-compose.simple-prod.yml logs -f

# Конкретный сервис
docker logs -f vectorstom-webapp
docker logs -f vectorstom-nginx
```

### Перезапуск сервисов
```bash
docker-compose -f docker-compose.simple-prod.yml restart webapp
```

### Обновление приложения
```bash
# Остановка
docker-compose -f docker-compose.simple-prod.yml down

# Копирование нового кода
scp -r webapp/ root@<IP>:/root/webapp/

# Пересборка и запуск
docker-compose -f docker-compose.simple-prod.yml up -d --build
```

### Бэкап данных
```bash
# Бэкап Qdrant
docker exec vectorstom-qdrant tar -czf /tmp/backup.tar.gz /qdrant/storage
docker cp vectorstom-qdrant:/tmp/backup.tar.gz ./qdrant-backup-$(date +%Y%m%d).tar.gz

# Копирование на локальный компьютер
scp root@<IP>:/root/qdrant-backup-*.tar.gz ./
```

---

## Производительность

### Ожидаемые показатели на C1-M2-D20:
- **Одновременные пользователи:** 5-10
- **Время ответа LLM:** 3-5 секунд
- **Время поиска векторов:** <100 мс
- **RAM usage:** ~1.5 ГБ (Qdrant ~400 МБ, Ollama ~500 МБ, webapp ~200 МБ)

### Узкие места:
- **CPU** - при >10 пользователях может быть задержка на Ollama эмбеддинги
- **Сеть** - DeepSeek API через Polza.ai (~2-3 секунды на запрос)

### Рекомендации по масштабированию:
- 10-20 пользователей → C4-M8 (4 ядра, 8 ГБ RAM)
- 20-50 пользователей → C8-M16 (8 ядер, 16 ГБ RAM)
- Кеширование частых запросов (Redis)

---

## Безопасность

✅ **Реализовано:**
- Rate limiting (10 req/s для API, 30 req/s общий)
- HTTP security headers
- Docker network isolation
- Закрытые внутренние порты

⚠️ **Рекомендуется добавить:**
- SSL сертификат (Let's Encrypt)
- Базовую авторизацию или API ключи
- Мониторинг (Prometheus + Grafana)
- Регулярные бэкапы (cron job)

---

## Стоимость эксплуатации

### Сервер
- **Тестирование:** 1 100 ₽/мес (C1-M2-D20)
- **Продакшн:** 4 880 ₽/мес (C4-M8-D120)

### API
- **DeepSeek через Polza.ai:** ~$0.002 за запрос
- **Ожидаемо:** 1000 запросов/мес = $2 (≈180 ₽)

### Итого для тестирования: ~1 300 ₽/мес

---

## Поддержка

При возникновении проблем:
1. Проверьте логи: `docker logs -f vectorstom-webapp`
2. Проверьте статус: `docker ps`
3. Проверьте health: `curl http://localhost/health`
4. Перезапустите: `docker-compose -f docker-compose.simple-prod.yml restart`
