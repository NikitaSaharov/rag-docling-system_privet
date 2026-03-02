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
LOCAL_BACKUP_DIR="$HOME/db_backups"
GIT_BACKUP_DIR="$PROJECT_DIR/db_backups"
MAX_LOCAL_BACKUPS=30   # Локально: 30 последних
MAX_GIT_BACKUPS=10     # В git: 10 последних (чтобы не раздувать репо)

# --- Цвета ---
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()  { echo -e "  ${GREEN}[OK]${NC} $1"; }
err() { echo -e "  ${RED}[!!]${NC} $1"; }
info() { echo -e "  ${YELLOW}[..]${NC} $1"; }

# --- Установка cron ---
install_cron() {
    CRON_CMD="0 */6 * * * $PROJECT_DIR/scripts/shell/backup_db.sh >> /var/log/docling_backup.log 2>&1"

    if crontab -l 2>/dev/null | grep -q "backup_db.sh"; then
        echo -e "${YELLOW}Cron задача уже установлена${NC}"
        crontab -l | grep "backup_db.sh"
        return
    fi

    (crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -
    ok "Cron задача установлена: бэкап каждые 6 часов"
    echo "  Лог: /var/log/docling_backup.log"
}

# --- Создание бэкапа ---
do_backup() {
    local timestamp=$(date +"%Y-%m-%d_%H-%M-%S")

    mkdir -p "$LOCAL_BACKUP_DIR" "$GIT_BACKUP_DIR"

    if [ ! -f "$DB_SOURCE" ]; then
        err "База не найдена: $DB_SOURCE"
        exit 1
    fi

    # === 1. Локальный бэкап (бинарный .db) ===
    local local_file="$LOCAL_BACKUP_DIR/docling_${timestamp}.db"
    if command -v sqlite3 &> /dev/null; then
        sqlite3 "$DB_SOURCE" ".backup '$local_file'"
    else
        docker exec docling-webapp python -c "
import sqlite3
src = sqlite3.connect('/db/docling.db')
dst = sqlite3.connect('/tmp/backup.db')
src.backup(dst)
src.close()
dst.close()
" 2>/dev/null && docker cp docling-webapp:/tmp/backup.db "$local_file" 2>/dev/null
        if [ ! -f "$local_file" ]; then
            cp "$DB_SOURCE" "$local_file"
        fi
    fi

    if [ -f "$local_file" ] && [ -s "$local_file" ]; then
        ok "Локальный бэкап: $local_file ($(du -h "$local_file" | cut -f1))"
    else
        err "Локальный бэкап не создан!"
        exit 1
    fi

    # Ротация локальных
    local count=$(ls -1 "$LOCAL_BACKUP_DIR"/docling_*.db 2>/dev/null | wc -l)
    if [ "$count" -gt "$MAX_LOCAL_BACKUPS" ]; then
        local to_delete=$((count - MAX_LOCAL_BACKUPS))
        ls -1t "$LOCAL_BACKUP_DIR"/docling_*.db | tail -n "$to_delete" | xargs rm -f
        ok "Ротация: удалено $to_delete старых локальных"
    fi

    # === 2. Git бэкап (SQL-дамп, сжатый) ===
    local git_file="$GIT_BACKUP_DIR/docling_${timestamp}.sql.gz"

    if command -v sqlite3 &> /dev/null; then
        sqlite3 "$DB_SOURCE" .dump | gzip > "$git_file"
    else
        docker exec docling-webapp python -c "
import sqlite3, sys
conn = sqlite3.connect('/db/docling.db')
for line in conn.iterdump():
    print(line)
conn.close()
" 2>/dev/null | gzip > "$git_file"
    fi

    if [ -f "$git_file" ] && [ -s "$git_file" ]; then
        ok "Git бэкап: $git_file ($(du -h "$git_file" | cut -f1))"
    else
        err "Git бэкап не создан!"
        return
    fi

    # Ротация git-бэкапов
    local git_count=$(ls -1 "$GIT_BACKUP_DIR"/docling_*.sql.gz 2>/dev/null | wc -l)
    if [ "$git_count" -gt "$MAX_GIT_BACKUPS" ]; then
        local git_del=$((git_count - MAX_GIT_BACKUPS))
        ls -1t "$GIT_BACKUP_DIR"/docling_*.sql.gz | tail -n "$git_del" | xargs rm -f
        ok "Ротация git: удалено $git_del старых"
    fi

    # === 3. Пуш в git ===
    info "Пуш в git..."
    cd "$PROJECT_DIR"
    git add db_backups/
    if git diff --cached --quiet; then
        ok "Git: изменений нет"
    else
        git commit -m "backup: DB $(date +'%Y-%m-%d %H:%M')"
        git push origin main 2>/dev/null && ok "Git: запушено" || err "Git push не удался"
    fi
}

# --- Маршрутизация ---
case "${1:-}" in
    --install-cron) install_cron ;;
    *)              do_backup ;;
esac
