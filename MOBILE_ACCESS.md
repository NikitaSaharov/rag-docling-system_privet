# Доступ с телефона

## Быстрый старт

### 1. Откройте порт (один раз)
Запустите PowerShell **от имени Администратора** и выполните:
```powershell
.\open_port_5000.ps1
```

Или вручную:
```powershell
New-NetFirewallRule -DisplayName "RAG Docling WebApp" -Direction Inbound -Protocol TCP -LocalPort 5000 -Action Allow -Profile Private,Domain
```

### 2. Узнайте IP вашего ПК
```powershell
ipconfig | Select-String "IPv4"
```

Ищите адрес вида `192.168.X.X` (не 127.0.0.1, не 172.X.X.X)

### 3. Подключитесь с телефона

**Ваш текущий IP:** `192.168.0.103`

На телефоне откройте браузер и введите:
```
http://192.168.0.103:5000
```

## Требования

✅ Телефон и ПК в одной WiFi сети  
✅ Docker контейнеры запущены (`docker ps`)  
✅ Порт 5000 открыт в firewall

## Проверка доступности

На ПК проверьте что webapp работает:
```powershell
curl http://localhost:5000
```

Если не работает - перезапустите:
```powershell
docker restart docling-webapp
```

## Возможные проблемы

### Телефон не подключается
1. Проверьте что в одной WiFi сети
2. Проверьте firewall: `Get-NetFirewallRule -DisplayName "RAG Docling WebApp"`
3. Попробуйте пинг с телефона: установите Network Tools и пингуйте `192.168.0.103`

### IP изменился
После перезагрузки ПК или роутера IP может измениться. Проверьте заново:
```powershell
ipconfig | Select-String "IPv4"
```

### Медленная работа
Это нормально - LLM работает на ПК, ответы могут занимать 10-30 секунд.

## Безопасность

⚠️ **Важно:** Не открывайте порт для доступа из Интернета!  
Текущие настройки разрешают доступ только из локальной сети (Profile Private,Domain).

Для доступа из Интернета нужны:
- HTTPS (SSL сертификаты)
- Авторизация (логин/пароль)
- Реверс-прокси (nginx)
- Статический IP или DDNS

См. `DEPLOYMENT.md` для production настроек.
