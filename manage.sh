#!/bin/bash
# ============================================================
# VectorStom - Управление на сервере
# Использование: ./manage.sh <команда> [аргументы]
# ============================================================

set -e

# --- Конфигурация ---
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKUP_DIR="$HOME/backups"
DB_PATH="$PROJECT_DIR/shared/db/docling.db"

# Цвета
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

ok()     { echo -e "  ${GREEN}[OK]${NC} $1"; }
err()    { echo -e "  ${RED}[!!]${NC} $1"; }
info()   { echo -e "  ${YELLOW}[..]${NC} $1"; }
header() { echo -e "\n${CYAN}=== $1 ===${NC}"; }

# ============================================================
# КОМАНДЫ
# ============================================================

show_help() {
    echo ""
    echo -e "  ${CYAN}VectorStom - Управление на сервере${NC}"
    echo -e "  ${CYAN}===================================${NC}"
    echo ""
    echo -e "  ${YELLOW}Основные:${NC}"
    echo "    ./manage.sh status             Статус контейнеров + система"
    echo "    ./manage.sh restart [сервис]   Перезапустить (все или один)"
    echo "    ./manage.sh logs [сервис]      Показать логи (по умолч. webapp)"
    echo "    ./manage.sh stop               Остановить все"
    echo "    ./manage.sh start              Запустить все"
    echo ""
    echo -e "  ${YELLOW}Обновление:${NC}"
    echo "    ./manage.sh update             Git pull + пересборка контейнеров"
    echo "    ./manage.sh update-quick       Git pull + рестарт webapp и telegram"
    echo ""
    echo -e "  ${YELLOW}Бэкапы:${NC}"
    echo "    ./manage.sh backup             Создать бэкап БД + Qdrant"
    echo "    ./manage.sh restore <дата>     Восстановить из бэкапа"
    echo "    ./manage.sh backups            Список бэкапов"
    echo ""
    echo -e "  Сервисы: webapp, qdrant, ollama, docling, telegram-bot, n8n, open-webui"
    echo ""
}

# --- Статус ---
show_status() {
    header "Контейнеры"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "docling|qdrant|ollama|n8n|open-webui|NAMES"

    header "Проверка здоровья"

    # WebApp
    if curl -sf -o /dev/null -w "" http://localhost:5000 2>/dev/null; then
        ok "WebApp отвечает на :5000"
    else
        err "WebApp не отвечает на :5000"
    fi

    # Qdrant
    if curl -sf -o /dev/null http://localhost:6333/collections 2>/dev/null; then
        ok "Qdrant отвечает на :6333"
    else
        err "Qdrant не отвечает на :6333"
    fi

    header "Система"
    echo "  Диск:"
    df -h / | tail -1 | awk '{print "    Использовано: "$3" из "$2" ("$5")"}'
    echo "  Память:"
    free -h | grep Mem | awk '{print "    Использовано: "$3" из "$2}'
    echo "  Uptime:"
    echo "    $(uptime -p)"
    echo ""
}

# --- Запуск / Остановка ---
start_services() {
    header "Запуск сервисов"
    cd "$PROJECT_DIR"
    docker-compose up -d
    ok "Все сервисы запущены"
}

stop_services() {
    header "Остановка сервисов"
    cd "$PROJECT_DIR"
    docker-compose down
    ok "Все сервисы остановлены"
}

# --- Перезапуск ---
restart_service() {
    local svc="${1:-}"

    if [ -n "$svc" ]; then
        header "Перезапуск $svc"
        cd "$PROJECT_DIR"
        docker-compose restart "$svc"
    else
        header "Перезапуск всех сервисов"
        cd "$PROJECT_DIR"
        docker-compose restart
    fi
    ok "Готово"
}

# --- Логи ---
show_logs() {
    local svc="${1:-webapp}"
    info "Логи $svc (последние 100 строк, Ctrl+C для выхода)"
    cd "$PROJECT_DIR"
    docker-compose logs --tail 100 -f "$svc"
}

# --- Обновление ---
update_full() {
    header "Полное обновление"

    info "Git pull..."
    cd "$PROJECT_DIR"
    git pull origin main
    ok "Код обновлён"

    info "Пересборка контейнеров..."
    docker-compose up -d --build
    ok "Контейнеры пересобраны"

    echo ""
    show_status
}

update_quick() {
    header "Быстрое обновление (webapp + telegram)"

    cd "$PROJECT_DIR"
    git pull origin main
    ok "Код обновлён"

    docker-compose restart webapp telegram-bot
    ok "webapp и telegram-bot перезапущены"
}

# --- Бэкап ---
create_backup() {
    header "Создание бэкапа"

    local date_str=$(date +"%Y-%m-%d_%H-%M")
    local backup_path="$BACKUP_DIR/$date_str"
    mkdir -p "$backup_path"

    # 1. БД
    info "Копирование БД..."
    if [ -f "$DB_PATH" ]; then
        cp "$DB_PATH" "$backup_path/docling.db"
        ok "БД скопирована"
    else
        err "БД не найдена: $DB_PATH"
    fi

    # 2. .env.local
    info "Копирование .env.local..."
    if [ -f "$PROJECT_DIR/.env.local" ]; then
        cp "$PROJECT_DIR/.env.local" "$backup_path/.env.local"
        ok ".env.local скопирован"
    fi

    # 3. Снэпшот Qdrant
    info "Создание снэпшота Qdrant..."
    local snap_result=$(curl -sf -X POST http://localhost:6333/collections/documents/snapshots 2>/dev/null)
    if [ $? -eq 0 ]; then
        echo "$snap_result" > "$backup_path/qdrant_snapshot_info.json"
        ok "Снэпшот Qdrant создан"
    else
        err "Не удалось создать снэпшот Qdrant"
    fi

    # Размер
    local size=$(du -sh "$backup_path" | cut -f1)
    ok "Бэкап сохранён: $backup_path ($size)"
    echo ""
}

# --- Восстановление ---
restore_backup() {
    local date_str="${1:-}"

    if [ -z "$date_str" ]; then
        err "Укажите дату бэкапа: ./manage.sh restore 2026-03-01_10-30"
        echo ""
        list_backups
        return 1
    fi

    local backup_path="$BACKUP_DIR/$date_str"
    if [ ! -d "$backup_path" ]; then
        err "Бэкап не найден: $backup_path"
        list_backups
        return 1
    fi

    header "Восстановление из $date_str"

    # Останавливаем webapp
    info "Остановка webapp..."
    cd "$PROJECT_DIR"
    docker-compose stop webapp telegram-bot

    # Восстанавливаем БД
    if [ -f "$backup_path/docling.db" ]; then
        info "Восстановление БД..."
        cp "$backup_path/docling.db" "$DB_PATH"
        ok "БД восстановлена"
    fi

    # Запускаем обратно
    info "Запуск сервисов..."
    docker-compose up -d
    ok "Восстановление завершено!"
    echo ""
}

# --- Список бэкапов ---
list_backups() {
    header "Доступные бэкапы"

    if [ ! -d "$BACKUP_DIR" ]; then
        info "Бэкапов нет"
        return
    fi

    for dir in "$BACKUP_DIR"/*/; do
        if [ -d "$dir" ]; then
            local name=$(basename "$dir")
            local size=$(du -sh "$dir" | cut -f1)
            local has_db="нет"
            [ -f "$dir/docling.db" ] && has_db="да"
            echo "  $name  (размер: $size, БД: $has_db)"
        fi
    done
    echo ""
}

# ============================================================
# МАРШРУТИЗАЦИЯ
# ============================================================

case "${1:-help}" in
    help)          show_help ;;
    status)        show_status ;;
    start)         start_services ;;
    stop)          stop_services ;;
    restart)       restart_service "$2" ;;
    logs)          show_logs "$2" ;;
    update)        update_full ;;
    update-quick)  update_quick ;;
    backup)        create_backup ;;
    restore)       restore_backup "$2" ;;
    backups)       list_backups ;;
    *)
        err "Неизвестная команда: $1"
        show_help
        ;;
esac
