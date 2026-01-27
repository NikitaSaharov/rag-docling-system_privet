from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

def get_sources_keyboard(user_id, message_id):
    """
    Создает inline-клавиатуру с кнопкой "Показать источники"
    
    Args:
        user_id: ID пользователя
        message_id: ID сообщения для связи с источниками
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📄 Показать источники",
                callback_data=f"show_sources:{message_id}"
            )
        ]
    ])
    return keyboard

def get_phone_request_keyboard():
    """
    Создает клавиатуру с кнопкой запроса номера телефона
    """
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="📱 Поделиться номером телефона",
                    request_contact=True
                )
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    return keyboard
