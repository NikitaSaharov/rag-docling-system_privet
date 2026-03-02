#!/bin/bash
# ============================================================
# Автоматический бэкап SQLite базы данных
# Использование:
#   Ручной запуск: ./backup_db.sh
#   Установка в cron: ./backup_db.sh --install-cron
# ============================================================

set -e

# --- Конфигурация ---
PROJECT_DIR="${PROJECT_DIR:-/opt/docling}"
DB_SOURCE="$PROJECT_DIR/shared/db/docling.db"
BACKUP_DIR="$HOME/db_backups"
MAX_BACKUPS=30  # Хранить последние 30 бэкапов

# --- Цвета ---
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()  { echo -e "  ${GREEN}[OK]${NC} $1"; }
err() { echo -e "  ${RED}[!!]${NC} $1"; }

# --- Установка cron ---
install_cron() {
    # Бэкап каждые 6 часов (00:00, 06:00, 12:00, 18:00)
    CRON_CMD="0 */6 * * * $PROJECT_DIR/scripts/shell/backup_db.sh >> /var/log/docling_backup.log 2>&1"

    # Проверяем, не добавлен ли уже
    if crontab -l 2>/dev/null | grep -q "backup_db.sh"; then
        echo -e "${YELLOW}Cron задача уже установлена${NC}"
        crontab -l | grep "backup_db.sh"
        return
    fi

    # Добавляем в crontab
    (crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -
    ok "Cron задача установлена: бэкап каждые 6 часов"
    echo "  Лог: /var/log/docling_backup.log"
    echo "  Проверить: crontab -l"
    return
}

# --- Основной бэкап ---
do_backup() {
    local timestamp=$(date +"%Y-%m-%d_%H-%M-%S")
    local backup_file="$BACKUP_DIR/docling_${timestamp}.db"

    mkdir -p "$BACKUP_DIR"

    # Проверяем, что база существует
    if [ ! -f "$DB_SOURCE" ]; then
        err "База не найдена: $DB_SOURCE"
        exit 1
    fi

    # Безопасное копирование через SQLite backup API (учитывает WAL)
    if command -v sqlite3 &> /dev/null; then
        sqlite3 "$DB_SOURCE" ".backup '$backup_file'"
    else
        # Останавливаем webapp для консистентного копирования
        docker exec docling-webapp python -c "
import sqlite3
src = sqlite3.connect('/db/docling.db')
dst = sqlite3.connect('/tmp/backup.db')
src.backup(dst)
src.close()
dst.close()
" 2>/dev/null && docker cp docling-webapp:/tmp/backup.db "$backup_file" 2>/dev/null

        # Фолбэк: простое копирование
        if [ ! -f "$backup_file" ]; then
            cp "$DB_SOURCE" "$backup_file"
        fi
    fi

    # Проверяем, что бэкап создан и не пустой
    if [ -f "$backup_file" ] && [ -s "$backup_file" ]; then
        local size=$(du -h "$backup_file" | cut -f1)
        ok "Бэкап создан: $backup_file ($size)"
    else
        err "Бэкап не создан!"
        exit 1
    fi

    # Ротация: удаляем старые бэкапы
    local count=$(ls -1 "$BACKUP_DIR"/docling_*.db 2>/dev/null | wc -l)
    if [ "$count" -gt "$MAX_BACKUPS" ]; then
        local to_delete=$((count - MAX_BACKUPS))
        ls -1t "$BACKUP_DIR"/docling_*.db | tail -n "$to_delete" | xargs rm -f
        ok "Удалено $to_delete старых бэкапов (хранится $MAX_BACKUPS)"
    fi
}

# --- Маршрутизация ---
case "${1:-}" in
    --install-cron) install_cron ;;
    *)              do_backup ;;
esac
