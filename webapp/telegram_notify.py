"""
Модуль для отправки уведомлений через Telegram Bot API
"""
import os
import requests
import logging

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

def send_telegram_message(chat_id, text, parse_mode='Markdown'):
    """
    Отправляет сообщение пользователю в Telegram
    
    Args:
        chat_id: Telegram ID пользователя
        text: текст сообщения
        parse_mode: режим парсинга (Markdown, HTML)
    
    Returns:
        True если успешно, False если ошибка
    """
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN не установлен")
        return False
    
    try:
        response = requests.post(
            f"{TELEGRAM_API_URL}/sendMessage",
            json={
                'chat_id': chat_id,
                'text': text,
                'parse_mode': parse_mode
            },
            timeout=10
        )
        
        if response.status_code == 200:
            logger.info(f"✅ Уведомление отправлено пользователю {chat_id}")
            return True
        else:
            logger.error(f"❌ Ошибка отправки уведомления: {response.status_code} - {response.text}")
            return False
    
    except Exception as e:
        logger.error(f"❌ Исключение при отправке уведомления: {e}")
        return False

def notify_access_approved(telegram_id, username=None):
    """
    Уведомляет пользователя об одобрении доступа
    
    Args:
        telegram_id: Telegram ID пользователя
        username: имя пользователя (опционально)
    
    Returns:
        True если успешно, False если ошибка
    """
    greeting = f"{username}" if username else "Пользователь"
    
    message = (
        f"✅ *Доступ предоставлен!*\n\n"
        f"Привет, {greeting}!\n\n"
        f"Ваш запрос на доступ был одобрен администратором.\n"
        f"Теперь вы можете пользоваться ботом!\n\n"
        f"Отправьте /start чтобы начать работу."
    )
    
    return send_telegram_message(telegram_id, message)

def notify_access_rejected(telegram_id, username=None, reason=None):
    """
    Уведомляет пользователя об отклонении доступа
    
    Args:
        telegram_id: Telegram ID пользователя
        username: имя пользователя (опционально)
        reason: причина отклонения (опционально)
    
    Returns:
        True если успешно, False если ошибка
    """
    greeting = f"{username}" if username else "Пользователь"
    
    message = (
        f"❌ *Запрос отклонен*\n\n"
        f"Привет, {greeting}!\n\n"
        f"К сожалению, ваш запрос на доступ был отклонен."
    )
    
    if reason:
        message += f"\n\nПричина: {reason}"
    
    message += "\n\nЕсли у вас есть вопросы, обратитесь к администратору."
    
    return send_telegram_message(telegram_id, message)
