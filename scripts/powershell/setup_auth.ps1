# Скрипт быстрой настройки авторизации для VectorStom
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Настройка системы авторизации VectorStom" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Шаг 1: Генерация секретных ключей
Write-Host "[Шаг 1/4] Генерация JWT и Flask секретов..." -ForegroundColor Yellow

function New-RandomSecret {
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes)
    return [System.BitConverter]::ToString($bytes).Replace('-','').ToLower()
}

$jwt_secret = New-RandomSecret
$flask_secret = New-RandomSecret

Write-Host "✓ Секреты сгенерированы" -ForegroundColor Green
Write-Host ""

# Шаг 2: Запрос email настроек
Write-Host "[Шаг 2/4] Настройка Email для отправки кодов верификации" -ForegroundColor Yellow
Write-Host ""
Write-Host "Для отправки кодов верификации нужен Gmail App Password." -ForegroundColor White
Write-Host "Если у вас его еще нет, следуйте инструкции:" -ForegroundColor White
Write-Host "1. Откройте: https://myaccount.google.com/apppasswords" -ForegroundColor Cyan
Write-Host "2. Включите 2FA если не включена" -ForegroundColor Cyan
Write-Host "3. Создайте App Password для приложения Mail" -ForegroundColor Cyan
Write-Host "4. Скопируйте 16-значный пароль (БЕЗ пробелов)" -ForegroundColor Cyan
Write-Host ""

$smtp_user = Read-Host "Введите ваш Gmail адрес (например: ivanov@gmail.com)"
$smtp_password = Read-Host "Введите Gmail App Password (БЕЗ пробелов, 16 символов)"

Write-Host ""
Write-Host "✓ Email настройки получены" -ForegroundColor Green
Write-Host ""

# Шаг 3: Обновление .env.local
Write-Host "[Шаг 3/4] Обновление .env.local файла..." -ForegroundColor Yellow

$env_content = @"
# Локальные переменные окружения (НЕ КОММИТИТЬ!)
POLZA_API_KEY=ak_VdTnWuDz1CZGLuiiRH5qt34PlZQYx0NqROscaGPneIY

# Telegram Bot
TELEGRAM_BOT_TOKEN=8321374467:AAFT1VFbblYTyxaXfDa6OSTdzRokXQDrpeg

# Database
DB_PATH=/db/docling.db

# Flask API URL
FLASK_API_URL=http://webapp:5000

# Email settings для отправки кодов верификации
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=$smtp_user
SMTP_PASSWORD=$smtp_password
FROM_EMAIL=$smtp_user
FROM_NAME=VectorStom RAG System

# JWT секреты (автоматически сгенерированы)
JWT_SECRET_KEY=$jwt_secret
FLASK_SECRET_KEY=$flask_secret
"@

Set-Content -Path ".env.local" -Value $env_content -Encoding UTF8
Write-Host "✓ .env.local обновлен" -ForegroundColor Green
Write-Host ""

# Шаг 4: Проверка настройки (опционально)
Write-Host "[Шаг 4/4] Проверка настройки (опционально)" -ForegroundColor Yellow
$test = Read-Host "Хотите отправить тестовое письмо для проверки? (y/n)"

if ($test -eq "y" -or $test -eq "Y") {
    Write-Host "Отправка тестового письма на $smtp_user..." -ForegroundColor Cyan
    
    # Запускаем Python скрипт для отправки тестового email
    $pythonCmd = "from webapp.email_service import send_verification_email; result = send_verification_email('$smtp_user', '123456'); print('✓ Тест успешен!' if result else '✗ Ошибка отправки')"
    
    try {
        & python -c $pythonCmd
    } catch {
        Write-Host "⚠ Python не найден или ошибка при отправке" -ForegroundColor Yellow
        Write-Host "Проверьте настройки вручную при запуске приложения" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  ✓ Настройка завершена!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Следующие шаги:" -ForegroundColor Cyan
Write-Host "1. Запустите приложение: python webapp/app.py" -ForegroundColor White
Write-Host "2. Откройте: http://localhost:5000" -ForegroundColor White
Write-Host "3. Нажмите 'Войти' → 'Зарегистрироваться'" -ForegroundColor White
Write-Host "4. Проверьте почту для получения кода" -ForegroundColor White
Write-Host ""
Write-Host "Полная документация: AUTH_SETUP.md или QUICK_SETUP.md" -ForegroundColor Cyan
Write-Host ""
