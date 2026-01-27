import logging
import aiohttp
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from keyboards import get_sources_keyboard, get_phone_request_keyboard

logger = logging.getLogger(__name__)

# Хранилище истории чатов (в памяти)
chat_history = {}

# Хранилище sources для кнопки
sources_cache = {}

def register_handlers(dp, flask_api_url):
    """Регистрирует все обработчики"""
    router = Router()
    
    @router.message(Command("start"))
    async def cmd_start(message: Message):
        """Обработчик команды /start"""
        user_id = message.from_user.id
        username = message.from_user.username or "Пользователь"
        
        logger.info(f"Пользователь {username} (ID: {user_id}) запустил бота")
        
        # Проверяем авторизацию через тестовый запрос
        try:
            async with aiohttp.ClientSession() as session:
                test_data = {
                    'telegram_id': user_id,
                    'query': 'тест',
                    'history': []
                }
                async with session.post(
                    f"{flask_api_url}/api/telegram/search",
                    json=test_data,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    result = await response.json()
                    
                    if response.status == 403 or not result.get('authorized'):
                        # Пользователь не авторизован - запрашиваем номер телефона
                        logger.warning(f"Пользователь {user_id} не авторизован, запрашиваем номер телефона")
                        
                        keyboard = get_phone_request_keyboard()
                        await message.answer(
                            "👋 Привет!\n\n"
                            "Для использования бота необходима авторизация.\n\n"
                            "📱 Пожалуйста, поделитесь вашим номером телефона, "
                            "нажав кнопку ниже. Это нужно для проверки доступа.",
                            reply_markup=keyboard
                        )
                        return
        except Exception as e:
            logger.error(f"Ошибка проверки авторизации: {e}")
            await message.answer(
                "❌ Ошибка подключения к серверу.\n"
                "Попробуйте позже."
            )
            return
        
        # Инициализируем историю чата
        chat_history[user_id] = []
        
        await message.answer(
            f"👋 Привет, {username}!\n\n"
            "Я - бот-помощник VectorStom. Задавайте мне вопросы по документам, "
            "и я найду для вас ответы.\n\n"
            "Просто напишите ваш вопрос.",
            reply_markup=ReplyKeyboardRemove()
        )
    
    @router.message(Command("help"))
    async def cmd_help(message: Message):
        """Обработчик команды /help"""
        await message.answer(
            "📚 *Как пользоваться ботом:*\n\n"
            "1️⃣ Просто напишите свой вопрос\n"
            "2️⃣ Получите ответ на основе документов\n"
            "3️⃣ Нажмите кнопку \"📄 Показать источники\", чтобы увидеть источники\n\n"
            "Бот запоминает последние 5 вопросов для контекста.\n\n"
            "*Команды:*\n"
            "/start - Начать работу\n"
            "/help - Показать справку\n"
            "/clear - Очистить историю чата",
            parse_mode="Markdown"
        )
    
    @router.message(Command("clear"))
    async def cmd_clear(message: Message):
        """Очистка истории чата"""
        user_id = message.from_user.id
        if user_id in chat_history:
            chat_history[user_id] = []
        await message.answer("🧹 История чата очищена.")
    
    @router.message(F.contact)
    async def handle_contact(message: Message):
        """Обработчик получения контакта (номера телефона)"""
        user_id = message.from_user.id
        
        if not message.contact:
            await message.answer("❌ Не удалось получить контакт")
            return
        
        # Проверяем, что пользователь отправил свой собственный номер
        if message.contact.user_id != user_id:
            await message.answer(
                "⚠️ Пожалуйста, отправьте ваш собственный номер телефона, "
                "а не контакт другого пользователя.",
                reply_markup=get_phone_request_keyboard()
            )
            return
        
        phone_number = message.contact.phone_number
        # Нормализуем номер (добавляем + если нет)
        if not phone_number.startswith('+'):
            phone_number = '+' + phone_number
        
        logger.info(f"Получен номер телефона {phone_number} от пользователя {user_id}")
        
        # Отправляем запрос на привязку
        try:
            async with aiohttp.ClientSession() as session:
                data = {
                    'phone_number': phone_number,
                    'telegram_id': user_id,
                    'username': message.from_user.username
                }
                
                async with session.post(
                    f"{flask_api_url}/api/telegram/link_phone",
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    result = await response.json()
                    
                    if response.status == 200 and result.get('success'):
                        # Успешная привязка
                        await message.answer(
                            "✅ Отлично! Ваш номер телефона подтвержден.\n\n"
                            "Теперь вы можете пользоваться ботом. Задавайте вопросы!",
                            reply_markup=ReplyKeyboardRemove()
                        )
                        
                        # Инициализируем историю
                        chat_history[user_id] = []
                        
                        logger.info(f"Пользователь {user_id} успешно авторизован с номером {phone_number}")
                    elif response.status == 404:
                        # Номер не найден - создаем запрос на доступ
                        logger.info(f"Создание запроса на доступ для {phone_number} (ID: {user_id})")
                        
                        # Создаем запрос на доступ
                        async with session.post(
                            f"{flask_api_url}/api/admin/access-requests",
                            json=data,
                            timeout=aiohttp.ClientTimeout(total=10)
                        ) as req_response:
                            req_result = await req_response.json()
                            
                            if req_response.status == 200 and req_result.get('success'):
                                await message.answer(
                                    "📝 Ваш запрос на доступ отправлен администратору.\n\n"
                                    "⛳ Пожалуйста, ожидайте одобрения. Вам придет уведомление, "
                                    "когда доступ будет предоставлен.\n\n"
                                    f"Ваш номер: `{phone_number}`\n"
                                    f"Ваш Telegram ID: `{user_id}`",
                                    parse_mode="Markdown",
                                    reply_markup=ReplyKeyboardRemove()
                                )
                                logger.info(f"Запрос на доступ создан для {user_id}")
                            else:
                                await message.answer(
                                    "❌ Ошибка при создании запроса.\n"
                                    "Пожалуйста, обратитесь к администратору напрямую.\n\n"
                                    f"Ваш номер: `{phone_number}`\n"
                                    f"Ваш Telegram ID: `{user_id}`",
                                    parse_mode="Markdown",
                                    reply_markup=ReplyKeyboardRemove()
                                )
                    else:
                        # Другая ошибка
                        error_msg = result.get('error', 'Неизвестная ошибка')
                        await message.answer(
                            f"❌ {error_msg}\n\n"
                            f"Ваш номер: `{phone_number}`\n"
                            f"Ваш Telegram ID: `{user_id}`",
                            parse_mode="Markdown",
                            reply_markup=ReplyKeyboardRemove()
                        )
                        logger.warning(f"Ошибка для пользователя {user_id}: {error_msg}")
        
        except Exception as e:
            logger.error(f"Ошибка при привязке номера телефона: {e}")
            await message.answer(
                "❌ Ошибка при проверке номера телефона.\n"
                "Попробуйте позже или обратитесь к администратору.",
                reply_markup=ReplyKeyboardRemove()
            )
    
    @router.message(F.text)
    async def handle_text_message(message: Message):
        """Обработчик текстовых сообщений"""
        user_id = message.from_user.id
        query = message.text
        
        logger.info(f"Запрос от пользователя {user_id}: {query[:50]}...")
        
        # Отправляем уведомление о начале обработки
        processing_msg = await message.answer("🔍 Ищу ответ...")
        
        try:
            # Получаем историю чата
            history = chat_history.get(user_id, [])
            
            # Отправляем запрос к Flask API
            async with aiohttp.ClientSession() as session:
                data = {
                    'telegram_id': user_id,
                    'query': query,
                    'history': history
                }
                
                async with session.post(
                    f"{flask_api_url}/api/telegram/search",
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    result = await response.json()
                    
                    # Удаляем сообщение о поиске
                    await processing_msg.delete()
                    
                    if response.status == 403 or not result.get('authorized'):
                        await message.answer(
                            "🚫 Доступ запрещен. Обратитесь к администратору."
                        )
                        return
                    
                    if response.status != 200:
                        error_msg = result.get('error', 'Неизвестная ошибка')
                        await message.answer(f"❌ Ошибка: {error_msg}")
                        return
                    
                    answer = result.get('answer', 'Ответ не получен')
                    sources = result.get('sources', [])
                    
                    # Сохраняем в историю
                    chat_history.setdefault(user_id, []).append({
                        'question': query,
                        'answer': answer
                    })
                    
                    # Ограничиваем историю последними 5 парами
                    if len(chat_history[user_id]) > 5:
                        chat_history[user_id] = chat_history[user_id][-5:]
                    
                    # Сохраняем sources в кэше
                    message_id = message.message_id + 1  # ID следующего сообщения
                    sources_cache[f"{user_id}_{message_id}"] = sources
                    
                    # Отправляем ответ с кнопкой
                    if sources:
                        keyboard = get_sources_keyboard(user_id, message_id)
                        await message.answer(
                            answer,
                            reply_markup=keyboard
                        )
                    else:
                        await message.answer(answer)
                    
                    logger.info(f"Ответ отправлен пользователю {user_id}")
        
        except aiohttp.ClientError as e:
            await processing_msg.delete()
            logger.error(f"Ошибка подключения к API: {e}")
            await message.answer(
                "❌ Ошибка подключения к серверу.\n"
                "Попробуйте позже."
            )
        except Exception as e:
            await processing_msg.delete()
            logger.error(f"Ошибка обработки запроса: {e}", exc_info=True)
            await message.answer(
                "❌ Произошла ошибка при обработке запроса.\n"
                "Попробуйте переформулировать вопрос."
            )
    
    @router.callback_query(F.data.startswith("show_sources:"))
    async def show_sources_callback(callback: CallbackQuery):
        """Обработчик кнопки 'Показать источники'"""
        user_id = callback.from_user.id
        
        # Извлекаем message_id из callback_data
        try:
            _, msg_id = callback.data.split(":")
            cache_key = f"{user_id}_{msg_id}"
            
            sources = sources_cache.get(cache_key, [])
            
            if not sources:
                await callback.answer("Источники не найдены", show_alert=True)
                return
            
            # Формируем сообщение с источниками
            sources_text = "📚 *Источники:*\n\n"
            
            for idx, source in enumerate(sources[:5], 1):  # Показываем топ-5
                filename = source.get('filename', 'Неизвестно')
                text = source.get('text', '')[:150]  # Первые 150 символов
                score = source.get('score', 0)
                
                sources_text += (
                    f"{idx}. *{filename}* ({int(score * 100)}%)\n"
                    f"{text}...\n\n"
                )
            
            await callback.message.answer(
                sources_text,
                parse_mode="Markdown"
            )
            await callback.answer()
            
        except Exception as e:
            logger.error(f"Ошибка показа источников: {e}")
            await callback.answer("Ошибка при загрузке источников", show_alert=True)
    
    # Регистрируем router
    dp.include_router(router)
    logger.info("Обработчики зарегистрированы")
