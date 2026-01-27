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

def get_suggestions_keyboard(suggestions):
    """
    Создает inline-клавиатуру с номерами вопросов (1, 2, 3)
    """
    buttons = []
    for idx in range(min(len(suggestions), 3)):  # Максимум 3 кнопки
        buttons.append(
            InlineKeyboardButton(
                text=f"{idx + 1}",
                callback_data=f"suggestion:{idx}"
            )
        )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[buttons])
    return keyboard
