# Скрипт для открытия порта 5000 в Windows Firewall
# Запускать от имени Администратора

Write-Host "Открываю порт 5000 для доступа с телефона..." -ForegroundColor Green

# Удаляем старое правило если есть
Remove-NetFirewallRule -DisplayName "RAG Docling WebApp" -ErrorAction SilentlyContinue

# Создаем новое правило
New-NetFirewallRule -DisplayName "RAG Docling WebApp" `
    -Direction Inbound `
    -Protocol TCP `
    -LocalPort 5000 `
    -Action Allow `
    -Profile Private,Domain `
    -Description "Разрешает доступ к веб-интерфейсу RAG системы с устройств в локальной сети"

Write-Host "`n✅ Порт 5000 открыт!" -ForegroundColor Green
Write-Host "`nТеперь с телефона можно подключиться по адресу:" -ForegroundColor Yellow
Write-Host "http://192.168.0.103:5000" -ForegroundColor Cyan
Write-Host "`n⚠️  Убедитесь что телефон в той же WiFi сети!" -ForegroundColor Yellow
