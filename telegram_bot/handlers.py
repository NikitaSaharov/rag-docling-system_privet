import logging
import aiohttp
import os
import io
import re
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from keyboards import get_sources_keyboard, get_phone_request_keyboard, get_suggestions_keyboard

logger = logging.getLogger(__name__)

# Хранилище истории чатов (в памяти)
chat_history = {}

# Хранилище sources для кнопки
sources_cache = {}

# Хранилище suggestions для кнопок
suggestions_cache = {}

# === Детекция мета-вопросов о функционале бота ===
_META_PATTERNS = [
    r'расскажи.{0,10}(про|\u043e).{0,5}(функционал|возможност|себ)',
    r'что\s+ты\s+(умеешь|можешь|знаешь)',
    r'что\s+умеет\s+бот',
    r'что\s+может\s+бот',
    r'какой\s+функционал',
    r'что\s+ты\s+за\s+бот',
    r'как\s+(ты\s+)?(можешь\s+)?помо([чг]|щ)',
    r'как\s+пользоваться',
    r'какие\s+вопросы\s+(можно\s+)?(тебе\s+)?зада',
]
_META_RE = re.compile('|'.join(_META_PATTERNS), re.IGNORECASE)

def is_meta_question(text: str) -> bool:
    """Проверяет, спрашивает ли пользователь о функционале/возможностях бота"""
    return bool(_META_RE.search(text.strip()))

async def _safe_delete(msg):
    """Безопасное удаление сообщения (не бросает исключений)"""
    try:
        await msg.delete()
    except Exception:
        pass

def _escape_md(text: str) -> str:
    """Экранирует спецсимволы Markdown в тексте"""
    for ch in ('*', '_', '`', '['):
        text = text.replace(ch, f'\\{ch}')
    return text

BOT_DESCRIPTION = (
    "Я - бот-помощник VectorStom по управлению стоматологической клиникой.\n\n"
    "Мои возможности:\n"
    "1. Отвечаю на вопросы по управлению клиникой - финансы, показатели, KPI, формулы\n"
    "2. Помогаю с расчётами - нормочас, валовая выручка, загрузка докторов\n"
    "3. Подсказываю обязанности сотрудников - директор, координатор, администратор\n"
    "4. Принимаю голосовые сообщения - просто запишите вопрос голосом\n"
    "5. Помню контекст беседы - можно задавать уточняющие вопросы\n\n"
    "Просто напишите ваш вопрос, например:\n"
    "- Как рассчитать нормочас доктора?\n"
    "- Каковы обязанности директора клиники?\n"
    "- Как увеличить валовую выручку?\n\n"
    "Что именно вас интересует?"
)

def parse_suggestions(text):
    """Извлекает suggestions из секции 'Вопросы:' в ответе LLM"""
    # Ищем секцию "Вопросы:" (допускаем \r\n и \n)
    pattern = r'Вопросы:[\s\r]*\n((?:[\s\r]*\d+\..*?(?:\n|\r\n|$))+)'
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    
    if not match:
        # Пробуем старый формат [SUGGESTIONS] для обратной совместимости
        old_pattern = r'\[SUGGESTIONS\](.*?)\[/SUGGESTIONS\]'
        old_match = re.search(old_pattern, text, re.DOTALL)
        if old_match:
            suggestions_block = old_match.group(1)
            clean_text = re.sub(old_pattern, '', text, flags=re.DOTALL).strip()
            suggestions = []
            for line in suggestions_block.strip().split('\n'):
                line = line.strip()
                if line and re.match(r'^\d+\.\s*', line):
                    suggestion = re.sub(r'^\d+\.\s*', '', line).strip()
                    if suggestion:
                        suggestions.append(suggestion)
            return suggestions, clean_text
        return [], text
    
    suggestions_block = match.group(1)
    
    # Извлекаем список
    suggestions = []
    for line in suggestions_block.strip().split('\n'):
        line = line.strip()
        if line and re.match(r'^\d+\.\s*', line):
            # Убираем номер в начале
            suggestion = re.sub(r'^\d+\.\s*', '', line).strip()
            if suggestion:
                suggestions.append(suggestion)
    
    # Возвращаем полный текст (НЕ удаляем секцию "Вопросы:")
    return suggestions, text

def register_handlers(dp, flask_api_url):
    """Регистрирует все обработчики"""
    router = Router()
    
    @router.message(Command("start"))
    async def cmd_start(message: Message):
        """Обработчик команды /start"""
        user_id = message.from_user.id
        username = message.from_user.username or "Пользователь"
        
        logger.info(f"Пользователь {username} (ID: {user_id}) запустил бота")
        
        # Проверяем авторизацию
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{flask_api_url}/api/telegram/check_auth",
                    json={'telegram_id': user_id},
                    timeout=aiohttp.ClientTimeout(total=3)
                ) as response:
                    result = await response.json()
                    
                    if not result.get('authorized'):
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
            logger.error(f"Ошибка проверки авторизации: {type(e).__name__}: {e}", exc_info=True)
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
    
    @router.message(F.voice)
    async def handle_voice_message(message: Message):
        """Обработчик голосовых сообщений — STT + поиск"""
        user_id = message.from_user.id
        
        logger.info(f"Голосовое сообщение от пользователя {user_id}, длительность: {message.voice.duration}с")
        
        # Проверяем авторизацию до транскрипции (экономим API вызовы)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{flask_api_url}/api/telegram/check_auth",
                    json={'telegram_id': user_id},
                    timeout=aiohttp.ClientTimeout(total=3)
                ) as response:
                    result = await response.json()
                    if not result.get('authorized'):
                        await message.answer(
                            "🔐 Для использования голосового ввода необходима авторизация.\n\n"
                            "Нажмите /start для авторизации."
                        )
                        return
        except Exception as e:
            logger.error(f"Ошибка проверки авторизации: {e}")
            await message.answer("❌ Ошибка подключения к серверу.")
            return
        
        processing_msg = await message.answer("🎤 Распознаю речь...")
        
        try:
            # Скачиваем голосовое в память
            bot = message.bot
            file = await bot.get_file(message.voice.file_id)
            file_bytes = io.BytesIO()
            await bot.download_file(file.file_path, file_bytes)
            file_bytes.seek(0)
            
            # Отправляем на Polza.ai для транскрипции
            stt_api_key = os.getenv('POLZA_STT_API_KEY', '')
            if not stt_api_key:
                await processing_msg.edit_text("❌ STT API ключ не настроен.")
                return
            
            form_data = aiohttp.FormData()
            form_data.add_field('file', file_bytes, filename='voice.ogg', content_type='audio/ogg')
            form_data.add_field('model', 'openai/gpt-4o-mini-transcribe')
            form_data.add_field('language', 'ru')
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    'https://api.polza.ai/v1/audio/transcriptions',
                    headers={'Authorization': f'Bearer {stt_api_key}'},
                    data=form_data,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as stt_response:
                    if stt_response.status != 200:
                        error_text = await stt_response.text()
                        logger.error(f"STT API error: {stt_response.status} {error_text}")
                        await processing_msg.edit_text("❌ Ошибка распознавания речи.")
                        return
                    
                    stt_result = await stt_response.json()
                    text = stt_result.get('text', '').strip()
            
            if not text:
                await processing_msg.edit_text("❌ Речь не распознана. Попробуйте ещё раз.")
                return
            
            logger.info(f"Распознано от {user_id}: {text[:80]}")
            await processing_msg.edit_text(f"🔍 Распознано: «{text}»\n\nИщу ответ...")
            
            # Отправляем распознанный текст как поисковый запрос
            history = chat_history.get(user_id, [])
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{flask_api_url}/api/telegram/search",
                    json={'telegram_id': user_id, 'query': text, 'history': history},
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    result = await response.json()
                    
                    await _safe_delete(processing_msg)
                    
                    if response.status == 403 or not result.get('authorized'):
                        await message.answer("🚫 Доступ запрещен.")
                        return
                    
                    if response.status != 200:
                        error_msg = result.get('error', 'Неизвестная ошибка')
                        await message.answer(f"❌ Ошибка: {error_msg}")
                        return
                    
                    answer = result.get('answer', 'Ответ не получен')
                    sources = result.get('sources', [])
                    
                    # Парсим suggestions
                    suggestions, _ = parse_suggestions(answer)
                    
                    # Сохраняем в историю
                    chat_history.setdefault(user_id, []).append({
                        'question': text,
                        'answer': answer
                    })
                    if len(chat_history[user_id]) > 5:
                        chat_history[user_id] = chat_history[user_id][-5:]
                    
                    # Кэшируем sources и suggestions
                    message_id = message.message_id + 1
                    sources_cache[f"{user_id}_{message_id}"] = sources
                    if suggestions:
                        suggestions_cache[user_id] = suggestions
                    
                    # Собираем inline-клавиатуру
                    inline_buttons = []
                    if sources:
                        inline_buttons.append([
                            InlineKeyboardButton(
                                text="📄 Показать источники",
                                callback_data=f"show_sources:{message_id}"
                            )
                        ])
                    if suggestions:
                        suggestion_row = []
                        for idx in range(min(len(suggestions), 3)):
                            suggestion_row.append(
                                InlineKeyboardButton(
                                    text=f"{idx + 1}",
                                    callback_data=f"suggestion:{idx}"
                                )
                            )
                        inline_buttons.append(suggestion_row)
                    
                    keyboard = InlineKeyboardMarkup(inline_keyboard=inline_buttons) if inline_buttons else None
                    
                    # Показываем распознанный текст + ответ
                    await message.answer(f"🎤 «{text}»")
                    await message.answer(answer, reply_markup=keyboard)
                    
                    logger.info(f"Голосовой ответ отправлен пользователю {user_id}")
        
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка подключения: {e}")
            await _safe_delete(processing_msg)
            await message.answer("❌ Ошибка подключения к серверу.")
        except Exception as e:
            logger.error(f"Ошибка обработки голосового: {e}", exc_info=True)
            await _safe_delete(processing_msg)
            await message.answer("❌ Ошибка при обработке голосового сообщения.")
    
    @router.message(F.text)
    async def handle_text_message(message: Message):
        """Обработчик текстовых сообщений"""
        user_id = message.from_user.id
        query = message.text
        
        logger.info(f"Запрос от пользователя {user_id}: {query[:50]}...")
        
        # Мета-вопрос о функционале бота - отвечаем напрямую без обращения к API
        if is_meta_question(query):
            logger.info(f"Мета-вопрос о функционале от {user_id}")
            await message.answer(BOT_DESCRIPTION)
            return
        
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
                    await _safe_delete(processing_msg)
                    
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
                    
                    # DEBUG: логируем последние 500 символов ответа
                    logger.info(f"Последние 500 символов ответа: ...{answer[-500:]}")
                    
                    # Парсим suggestions из ответа (НО ОСТАВЛЯЕМ ИХ В ТЕКСТЕ!)
                    suggestions, _ = parse_suggestions(answer)
                    logger.info(f"Парсинг suggestions: найдено {len(suggestions)} вопросов")
                    if suggestions:
                        for idx, s in enumerate(suggestions, 1):
                            logger.info(f"  {idx}. {s[:50]}...")
                    
                    # Сохраняем в историю (полный ответ с suggestions)
                    chat_history.setdefault(user_id, []).append({
                        'question': query,
                        'answer': answer  # Полный ответ
                    })
                    
                    # Ограничиваем историю последними 5 парами
                    if len(chat_history[user_id]) > 5:
                        chat_history[user_id] = chat_history[user_id][-5:]
                    
                    # Сохраняем sources в кэше
                    message_id = message.message_id + 1  # ID следующего сообщения
                    sources_cache[f"{user_id}_{message_id}"] = sources
                    
                    # Сохраняем suggestions в кэше
                    if suggestions:
                        suggestions_cache[user_id] = suggestions
                    
                    # Создаём комбинированную inline-клавиатуру
                    inline_buttons = []
                    
                    # Добавляем кнопку источников
                    if sources:
                        inline_buttons.append([
                            InlineKeyboardButton(
                                text="📄 Показать источники",
                                callback_data=f"show_sources:{message_id}"
                            )
                        ])
                    
                    # Добавляем кнопки suggestions (только номера)
                    if suggestions:
                        suggestion_row = []
                        for idx in range(min(len(suggestions), 3)):
                            suggestion_row.append(
                                InlineKeyboardButton(
                                    text=f"{idx + 1}",
                                    callback_data=f"suggestion:{idx}"
                                )
                            )
                        inline_buttons.append(suggestion_row)
                    
                    # Отправляем ответ с клавиатурой
                    keyboard = InlineKeyboardMarkup(inline_keyboard=inline_buttons) if inline_buttons else None
                    await message.answer(
                        answer,  # Полный ответ с [SUGGESTIONS]
                        reply_markup=keyboard
                    )
                    
                    logger.info(f"Ответ отправлен пользователю {user_id}")
        
        except aiohttp.ClientError as e:
            await _safe_delete(processing_msg)
            logger.error(f"Ошибка подключения к API: {e}")
            await message.answer(
                "❌ Ошибка подключения к серверу.\n"
                "Попробуйте позже."
            )
        except Exception as e:
            await _safe_delete(processing_msg)
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
            sources_text = "📚 Источники:\n\n"
            
            for idx, source in enumerate(sources[:5], 1):  # Показываем топ-5
                filename = source.get('filename', 'Неизвестно')
                text = source.get('text', '')[:150]  # Первые 150 символов
                score = source.get('score', 0)
                
                sources_text += (
                    f"{idx}. {filename} ({int(score * 100)}%)\n"
                    f"{text}...\n\n"
                )
            
            await callback.message.answer(sources_text)
            await callback.answer()
            
        except Exception as e:
            logger.error(f"Ошибка показа источников: {e}")
            await callback.answer("Ошибка при загрузке источников", show_alert=True)
    
    @router.callback_query(F.data.startswith("suggestion:"))
    async def suggestion_callback(callback: CallbackQuery):
        """Обработчик кнопок suggestions (1, 2, 3)"""
        user_id = callback.from_user.id
        
        try:
            # Извлекаем индекс suggestion
            _, idx_str = callback.data.split(":")
            idx = int(idx_str)
            
            # Проверяем наличие suggestions в кэше
            if user_id not in suggestions_cache:
                await callback.answer("Варианты устарели", show_alert=True)
                return
            
            suggestions = suggestions_cache[user_id]
            if idx >= len(suggestions):
                await callback.answer("Вариант не найден", show_alert=True)
                return
            
            # Получаем текст вопроса
            selected_query = suggestions[idx]
            logger.info(f"Пользователь {user_id} выбрал suggestion #{idx + 1}: {selected_query}")
            
            # Очищаем кэш suggestions
            del suggestions_cache[user_id]
            
            # Подтверждаем нажатие
            await callback.answer(f"Выбран: {selected_query[:30]}...")
            
            # Отправляем запрос от имени пользователя
            await callback.message.answer(f"👤 {selected_query}")
            
            # Показываем загрузку
            processing_msg = await callback.message.answer("🔍 Ищу ответ...")
            
            try:
                # Получаем историю чата
                history = chat_history.get(user_id, [])
                
                # Отправляем запрос к Flask API
                async with aiohttp.ClientSession() as session:
                    data = {
                        'telegram_id': user_id,
                        'query': selected_query,
                        'history': history
                    }
                    
                    async with session.post(
                        f"{flask_api_url}/api/telegram/search",
                        json=data,
                        timeout=aiohttp.ClientTimeout(total=60)
                    ) as response:
                        result = await response.json()
                        
                        # Удаляем сообщение о поиске
                        await _safe_delete(processing_msg)
                        
                        if response.status == 403 or not result.get('authorized'):
                            await callback.message.answer("🚫 Доступ запрещен.")
                            return
                        
                        if response.status != 200:
                            error_msg = result.get('error', 'Неизвестная ошибка')
                            await callback.message.answer(f"❌ Ошибка: {error_msg}")
                            return
                        
                        answer = result.get('answer', 'Ответ не получен')
                        sources = result.get('sources', [])
                        
                        # Парсим suggestions
                        suggestions_new, _ = parse_suggestions(answer)
                        
                        # Сохраняем в историю
                        chat_history.setdefault(user_id, []).append({
                            'question': selected_query,
                            'answer': answer
                        })
                        
                        if len(chat_history[user_id]) > 5:
                            chat_history[user_id] = chat_history[user_id][-5:]
                        
                        # Сохраняем sources
                        message_id = callback.message.message_id + 2
                        sources_cache[f"{user_id}_{message_id}"] = sources
                        
                        # Сохраняем новые suggestions
                        if suggestions_new:
                            suggestions_cache[user_id] = suggestions_new
                        
                        # Создаём клавиатуру
                        inline_buttons = []
                        
                        if sources:
                            inline_buttons.append([
                                InlineKeyboardButton(
                                    text="📄 Показать источники",
                                    callback_data=f"show_sources:{message_id}"
                                )
                            ])
                        
                        if suggestions_new:
                            suggestion_row = []
                            for i in range(min(len(suggestions_new), 3)):
                                suggestion_row.append(
                                    InlineKeyboardButton(
                                        text=f"{i + 1}",
                                        callback_data=f"suggestion:{i}"
                                    )
                                )
                            inline_buttons.append(suggestion_row)
                        
                        keyboard = InlineKeyboardMarkup(inline_keyboard=inline_buttons) if inline_buttons else None
                        await callback.message.answer(answer, reply_markup=keyboard)
                        
            except Exception as e:
                await _safe_delete(processing_msg)
                logger.error(f"Ошибка обработки suggestion: {e}", exc_info=True)
                await callback.message.answer("❌ Ошибка при обработке запроса.")
                
        except Exception as e:
            logger.error(f"Ошибка suggestion callback: {e}")
            await callback.answer("Ошибка", show_alert=True)
    
    # Регистрируем router
    dp.include_router(router)
    logger.info("Обработчики зарегистрированы")
