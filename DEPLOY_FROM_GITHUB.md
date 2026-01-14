# Развертывание VectorStom с GitHub

## 🚀 Быстрое развертывание на VPS с GitHub

### Шаг 1: Создать VPS
- Тариф: **C1-M2-D20** (1 100 ₽/мес)
- ОС: **Ubuntu 24.04 LTS**
- Регион: Москва-2

Получите IP адрес и подключитесь:
```bash
ssh root@<IP_АДРЕС>
```

---

### Шаг 2: Установить Docker на сервере

```bash
# Обновление системы
apt update && apt upgrade -y

# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Установка Docker Compose
apt install docker-compose -y

# Установка Git
apt install git -y

# Проверка
docker --version
git --version
```

---

### Шаг 3: Клонировать проект с GitHub

```bash
cd /root
git clone https://github.com/NikitaSaharov/rag-docling-system_privet.git vectorstom
cd vectorstom
```

---

### Шаг 4: Настроить переменные окружения

```bash
# Создать .env файл
cat > .env << 'EOF'
POLZA_API_KEY=ak_VdTnWuDz1CZGLuiiRH5qt34PlZQYx0NqROscaGPneIY
EOF

# Загрузить переменные
export $(cat .env | xargs)
```

---

### Шаг 5: Загрузить векторы Qdrant

#### Вариант А: Скачать с вашего компьютера
```bash
# На вашем Windows компьютере создайте бэкап (если еще не создали):
docker compose exec qdrant tar -czf /tmp/qdrant-backup.tar.gz /qdrant/storage
docker compose cp qdrant:/tmp/qdrant-backup.tar.gz ./qdrant-backup.tar.gz

# Загрузите на сервер (с вашего компьютера):
scp qdrant-backup.tar.gz root@<IP>:/root/vectorstom/
```

#### Вариант Б: Загрузить из облачного хранилища
Если вы выгрузили бэкап в облако (Google Drive, Яндекс.Диск и т.д.):
```bash
# Получите прямую ссылку и скачайте
wget "<ССЫЛКА_НА_БЭКАП>" -O qdrant-backup.tar.gz
```

#### Восстановление векторов
```bash
# Создаем volume
docker volume create vectorstom_qdrant_data

# Восстанавливаем из бэкапа
docker run --rm \
  -v vectorstom_qdrant_data:/qdrant/storage \
  -v /root/vectorstom/qdrant-backup.tar.gz:/backup.tar.gz \
  alpine sh -c "cd / && tar -xzf /backup.tar.gz"
```

---

### Шаг 6: Запустить систему

```bash
# Запуск всех сервисов
docker-compose -f docker-compose.simple-prod.yml up -d

# Проверка статуса
docker ps

# Ожидаем 30 секунд для инициализации
sleep 30

# Загружаем модель Ollama для эмбеддингов
docker exec vectorstom-ollama ollama pull nomic-embed-text
```

---

### Шаг 7: Проверка работы

```bash
# Health check
curl http://localhost/health
# Ожидаем: OK

# Статистика
curl http://localhost/api/stats
# Ожидаем: {"qdrant":{"vectors_count":902,...}}

# Список документов
curl http://localhost/api/documents
# Ожидаем: {"total_vectors":902,"documents":[...]}
```

Откройте в браузере: `http://<IP_АДРЕС>`

---

### Шаг 8: Настройка firewall

```bash
apt install ufw -y
ufw allow 22/tcp   # SSH
ufw allow 80/tcp   # HTTP
ufw enable
```

---

## 🎉 Готово!

Система доступна по адресу: `http://<IP_АДРЕС>`

Отправьте эту ссылку коллегам для тестирования.

---

## 📊 Мониторинг

### Логи
```bash
# Все сервисы
docker-compose -f docker-compose.simple-prod.yml logs -f

# Только webapp
docker logs -f vectorstom-webapp

# Последние 100 строк
docker logs --tail 100 vectorstom-webapp
```

### Статистика ресурсов
```bash
docker stats
```

### Перезапуск при проблемах
```bash
docker-compose -f docker-compose.simple-prod.yml restart
```

---

## 🔄 Обновление системы

### Получить последние изменения с GitHub
```bash
cd /root/vectorstom
git pull origin main

# Пересобрать и перезапустить
docker-compose -f docker-compose.simple-prod.yml down
docker-compose -f docker-compose.simple-prod.yml up -d --build
```

---

## 💰 Стоимость

- VPS C1-M2-D20: **1 100 ₽/мес**
- API Polza.ai (~1000 запросов): **~180 ₽/мес**
- **ИТОГО: ~1 300 ₽/мес**

---

## 📚 Дополнительная документация

- `DEPLOY.md` - полная документация по развертыванию
- `DEPLOY_CHECKLIST.md` - чеклист с галочками
- `CONCURRENCY.md` - подробно о параллельной обработке
- `QUICK_ANSWER.md` - быстрый FAQ

---

## 🆘 Проблемы?

### Порты заняты
```bash
# Проверить какие порты заняты
netstat -tulpn | grep :80

# Остановить конфликтующий сервис
systemctl stop apache2  # или nginx, если установлен глобально
```

### Нет векторов после восстановления
```bash
# Проверить volume
docker volume inspect vectorstom_qdrant_data

# Проверить Qdrant
docker exec vectorstom-qdrant ls -la /qdrant/storage
```

### Ошибка "Out of memory"
Сервер C1-M2-D20 имеет только 2 ГБ RAM. Если не хватает:
```bash
# Добавить swap
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

---

## 📞 Поддержка

GitHub Issues: https://github.com/NikitaSaharov/rag-docling-system_privet/issues

---

## ✅ Тест параллельности

После развертывания:
1. Откройте 3 вкладки браузера
2. Задайте вопросы одновременно
3. Все должны получить ответ за ~5 секунд

**Система поддерживает 4 параллельных запроса благодаря Gunicorn!**
