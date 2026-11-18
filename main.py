#!/usr/bin/env python3
"""
Freelance Hunter Bot - Telegram-бот-радар для поиска заказов и вакансий
Архитектура: Producer (Telethon) -> Queue -> Consumer (AI Analysis) -> Notifier (aiogram)
С встроенным FastAPI веб-сервером для деплоя на Render
"""

import asyncio
import logging
import os
import random
from typing import Optional, List
from datetime import datetime
from contextlib import asynccontextmanager

import aiosqlite
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from telethon import TelegramClient, events
from telethon.tl.types import Message as TelethonMessage
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from openai import AsyncOpenAI
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Константы из окружения
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
ADMIN_TELEGRAM_ID = int(os.getenv('ADMIN_TELEGRAM_ID', '0'))
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
TARGET_CHATS = os.getenv('TARGET_CHATS', '').split(',')
PORT = int(os.getenv('PORT', '8000'))  # Порт для Render

# Фильтры мусора
MIN_MESSAGE_LENGTH = 20
SPAM_KEYWORDS = {
    'плюс', '+', 'спасибо', 'привет', 'ок', 'окей', 'понял', 
    'го', 'пон', 'ясно', 'хорошо', 'отлично', 'супер', '👍', '✅'
}

# Стек разработчика для AI
DEVELOPER_STACK = """Python 3.11+, aiogram 3, Telethon, FastAPI, PostgreSQL, SQLAlchemy, Playwright, OpenAI API"""

# Глобальная переменная для экземпляра бота
bot_instance: Optional['FreelanceHunterBot'] = None

# Pydantic модели для AI-анализа
class AnalysisResult(BaseModel):
    """Результат AI-анализа сообщения"""
    type: str = Field(..., description="Тип: order/vacancy/flood")
    relevance: int = Field(..., ge=0, le=100, description="Релевантность 0-100")
    summary: str = Field(..., description="Краткое описание")
    stack: List[str] = Field(default_factory=list, description="Технологический стек")
    budget: Optional[str] = Field(None, description="Бюджет/зарплата")
    draft_response: Optional[str] = Field(None, description="Черновик отклика")


class MessageData(BaseModel):
    """Данные сообщения для обработки"""
    message_id: int
    chat_id: int
    chat_title: str
    text: str
    link: str
    timestamp: datetime


class DeduplicationDB:
    """Управление базой данных для дедупликации"""
    
    def __init__(self, db_path: str = "deduplication.db"):
        self.db_path = db_path
        self.db: Optional[aiosqlite.Connection] = None
    
    async def init(self):
        """Инициализация базы данных"""
        self.db = await aiosqlite.connect(self.db_path)
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS processed_messages (
                message_id INTEGER,
                chat_id INTEGER,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (message_id, chat_id)
            )
        """)
        await self.db.commit()
        logger.info(f"База данных {self.db_path} инициализирована")
    
    async def is_processed(self, message_id: int, chat_id: int) -> bool:
        """Проверка, обработано ли сообщение"""
        async with self.db.execute(
            "SELECT 1 FROM processed_messages WHERE message_id = ? AND chat_id = ?",
            (message_id, chat_id)
        ) as cursor:
            result = await cursor.fetchone()
            return result is not None
    
    async def mark_processed(self, message_id: int, chat_id: int):
        """Пометить сообщение как обработанное"""
        try:
            await self.db.execute(
                "INSERT INTO processed_messages (message_id, chat_id) VALUES (?, ?)",
                (message_id, chat_id)
            )
            await self.db.commit()
        except aiosqlite.IntegrityError:
            pass  # Уже существует
    
    async def close(self):
        """Закрытие соединения"""
        if self.db:
            await self.db.close()


class PrimaryFilter:
    """Первичная фильтрация мусорных сообщений"""
    
    @staticmethod
    def is_spam(text: str) -> bool:
        """Проверка на спам"""
        if len(text) < MIN_MESSAGE_LENGTH:
            return True
        
        text_lower = text.lower().strip()
        
        # Проверка на односложные ответы
        if text_lower in SPAM_KEYWORDS:
            return True
        
        # Проверка на очень короткие сообщения с ключевыми словами
        words = text_lower.split()
        if len(words) <= 2 and any(word in SPAM_KEYWORDS for word in words):
            return True
        
        return False


class AIAnalyzer:
    """AI-анализатор сообщений через OpenAI"""
    
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)
    
    async def analyze(self, message_data: MessageData) -> Optional[AnalysisResult]:
        """Анализ сообщения через GPT-4o-mini"""
        try:
            prompt = f"""Проанализируй сообщение из Telegram-канала с вакансиями/заказами.

Текст сообщения:
{message_data.text}

Определи:
1. type: "order" (заказ/проект), "vacancy" (вакансия), "flood" (мусор/нерелевантное)
2. relevance: 0-100 (насколько подходит для разработчика со стеком: {DEVELOPER_STACK})
3. summary: краткое описание (1-2 предложения)
4. stack: список технологий (["Python", "FastAPI", ...])
5. budget: бюджет/зарплата (если указано)
6. draft_response: черновик отклика (только если relevance > 60)

Критерии релевантности:
- Высокая (80-100): прямое совпадение со стеком, интересная задача
- Средняя (60-79): частичное совпадение, подходит с оговорками
- Низкая (0-59): не подходит, другой стек, мусор

Верни ТОЛЬКО валидный JSON без дополнительного текста."""

            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Ты эксперт по анализу вакансий и заказов для Python-разработчиков. Отвечай только в формате JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=1000
            )
            
            json_result = response.choices[0].message.content
            logger.info(f"AI ответ получен: {json_result[:100]}...")
            
            # Парсинг через Pydantic
            import json
            result_dict = json.loads(json_result)
            analysis = AnalysisResult(**result_dict)
            
            logger.info(f"Анализ завершен: type={analysis.type}, relevance={analysis.relevance}")
            return analysis
            
        except Exception as e:
            logger.error(f"Ошибка AI-анализа: {e}", exc_info=True)
            return None


class NotificationBot:
    """Бот для отправки уведомлений администратору"""
    
    def __init__(self, token: str, admin_id: int):
        self.bot = Bot(token=token)
        self.admin_id = admin_id
        self.dp = Dispatcher()
    
    async def send_notification(
        self, 
        message_data: MessageData, 
        analysis: AnalysisResult
    ):
        """Отправка уведомления администратору"""
        try:
            # Формирование уведомления
            emoji = "💼" if analysis.type == "vacancy" else "🎯"
            type_name = "Вакансия" if analysis.type == "vacancy" else "Заказ"
            
            notification = f"""{emoji} <b>{type_name}</b> | Релевантность: {analysis.relevance}%

<b>Канал:</b> {message_data.chat_title}
<b>Краткое описание:</b>
{analysis.summary}

<b>Стек:</b> {', '.join(analysis.stack) if analysis.stack else 'Не указано'}
<b>Бюджет:</b> {analysis.budget or 'Не указано'}

<b>Ссылка:</b> {message_data.link}
"""
            
            if analysis.draft_response:
                notification += f"""
<b>📝 Черновик отклика:</b>
<i>{analysis.draft_response}</i>
"""
            
            await self.bot.send_message(
                chat_id=self.admin_id,
                text=notification,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            
            logger.info(f"Уведомление отправлено администратору: {type_name}")
            
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления: {e}", exc_info=True)
    
    async def close(self):
        """Закрытие бота"""
        await self.bot.session.close()


class FreelanceHunterBot:
    """Главный класс бота-радара"""
    
    def __init__(self):
        # Инициализация компонентов
        self.db = DeduplicationDB()
        self.filter = PrimaryFilter()
        self.analyzer = AIAnalyzer(OPENAI_API_KEY)
        self.notifier = NotificationBot(BOT_TOKEN, ADMIN_TELEGRAM_ID)
        
        # Telethon userbot с поддержкой StringSession
        from telethon.sessions import StringSession
        
        session_string = os.getenv('SESSION_STRING', '')
        if session_string:
            # Используем StringSession из переменной окружения (для Render)
            logger.info("Используется StringSession из переменной окружения")
            session = StringSession(session_string)
        else:
            # Используем файловую сессию (для локальной разработки)
            logger.info("Используется файловая сессия userbot_session")
            session = 'userbot_session'
        
        self.userbot = TelegramClient(session, API_ID, API_HASH)
        
        # Очередь для Producer-Consumer
        self.queue: asyncio.Queue[MessageData] = asyncio.Queue(maxsize=100)
        
        # Флаг работы
        self.running = False
    
    async def init(self):
        """Инициализация бота"""
        logger.info("Инициализация Freelance Hunter Bot...")
        
        # Инициализация базы данных
        await self.db.init()
        
        # Подключение userbot
        await self.userbot.start()
        logger.info("Telethon userbot подключен")
        
        # Регистрация обработчика новых сообщений
        @self.userbot.on(events.NewMessage(chats=TARGET_CHATS))
        async def handler(event: events.NewMessage.Event):
            await self.on_new_message(event)
        
        logger.info(f"Мониторинг чатов: {TARGET_CHATS}")
    
    async def on_new_message(self, event: events.NewMessage.Event):
        """Producer: обработка нового сообщения из Telegram"""
        try:
            message: TelethonMessage = event.message
            
            # Игнорируем пустые сообщения
            if not message.text:
                return
            
            chat_id = event.chat_id
            message_id = message.id
            
            # Проверка дедупликации
            if await self.db.is_processed(message_id, chat_id):
                logger.debug(f"Сообщение {message_id} уже обработано")
                return
            
            # Первичная фильтрация мусора
            if self.filter.is_spam(message.text):
                logger.info(f"Сообщение {message_id} отфильтровано как спам")
                await self.db.mark_processed(message_id, chat_id)
                return
            
            # Получение информации о чате
            chat = await event.get_chat()
            chat_title = getattr(chat, 'title', 'Unknown')
            
            # Формирование ссылки на сообщение
            if hasattr(chat, 'username') and chat.username:
                link = f"https://t.me/{chat.username}/{message_id}"
            else:
                link = f"https://t.me/c/{str(chat_id)[4:]}/{message_id}"
            
            # Создание данных сообщения
            message_data = MessageData(
                message_id=message_id,
                chat_id=chat_id,
                chat_title=chat_title,
                text=message.text,
                link=link,
                timestamp=datetime.now()
            )
            
            # Добавление в очередь (с таймаутом)
            try:
                await asyncio.wait_for(
                    self.queue.put(message_data), 
                    timeout=5.0
                )
                logger.info(f"Сообщение {message_id} добавлено в очередь")
            except asyncio.TimeoutError:
                logger.warning("Очередь переполнена, сообщение пропущено")
            
            # Пометка как обработанное
            await self.db.mark_processed(message_id, chat_id)
            
        except Exception as e:
            logger.error(f"Ошибка обработки сообщения: {e}", exc_info=True)
    
    async def worker(self, worker_id: int):
        """Consumer: обработка сообщений из очереди"""
        logger.info(f"Worker {worker_id} запущен")
        
        while self.running:
            try:
                # Получение сообщения из очереди
                message_data = await asyncio.wait_for(
                    self.queue.get(),
                    timeout=1.0
                )
                
                logger.info(f"Worker {worker_id} обрабатывает сообщение {message_data.message_id}")
                
                # AI-анализ
                analysis = await self.analyzer.analyze(message_data)
                
                if not analysis:
                    logger.warning("AI-анализ не дал результата")
                    continue
                
                # Проверка на релевантность и тип
                if analysis.type in ('order', 'vacancy') and analysis.relevance >= 70:
                    logger.info(f"Найдено релевантное сообщение: {analysis.type}, {analysis.relevance}%")
                    await self.notifier.send_notification(message_data, analysis)
                else:
                    logger.info(f"Сообщение не прошло фильтр: type={analysis.type}, relevance={analysis.relevance}")
                
                # Пауза для защиты от флуда
                await asyncio.sleep(random.uniform(0.5, 2.0))
                
                # Отметка задачи как выполненной
                self.queue.task_done()
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Ошибка в worker {worker_id}: {e}", exc_info=True)
                await asyncio.sleep(1.0)
        
        logger.info(f"Worker {worker_id} остановлен")
    
    async def run(self, num_workers: int = 2):
        """Запуск бота"""
        self.running = True
        
        # Инициализация
        await self.init()
        
        logger.info(f"Запуск {num_workers} воркеров...")
        
        # Создание воркеров
        workers = [
            asyncio.create_task(self.worker(i))
            for i in range(num_workers)
        ]
        
        try:
            # Запуск userbot
            logger.info("🚀 Freelance Hunter Bot запущен!")
            logger.info("Нажмите Ctrl+C для остановки")
            
            await self.userbot.run_until_disconnected()
            
        except KeyboardInterrupt:
            logger.info("Получен сигнал остановки...")
        finally:
            # Остановка воркеров
            self.running = False
            
            # Ожидание завершения воркеров
            await asyncio.gather(*workers, return_exceptions=True)
            
            # Закрытие соединений
            await self.db.close()
            await self.notifier.close()
            
            logger.info("Бот остановлен")


async def start_bot():
    """Запуск бота в фоновом режиме"""
    global bot_instance
    
    # Проверка переменных окружения
    if not all([API_ID, API_HASH, ADMIN_TELEGRAM_ID, BOT_TOKEN, OPENAI_API_KEY]):
        logger.error("Не все переменные окружения заданы! Проверьте .env файл")
        return
    
    if not TARGET_CHATS or TARGET_CHATS == ['']:
        logger.error("TARGET_CHATS не задан! Добавьте каналы для мониторинга")
        return
    
    # Создание экземпляра бота
    bot_instance = FreelanceHunterBot()
    
    # Запуск бота в фоновой задаче
    asyncio.create_task(bot_instance.run(num_workers=2))
    logger.info("Бот запущен в фоновом режиме")


# Lifespan context manager для FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    # Запуск при старте
    logger.info("Запуск FastAPI приложения и бота...")
    await start_bot()
    yield
    # Завершение при остановке
    logger.info("Завершение работы...")
    if bot_instance:
        bot_instance.running = False
        await bot_instance.db.close()
        await bot_instance.notifier.close()


# FastAPI приложение
app = FastAPI(
    title="Freelance Hunter Bot",
    description="Telegram-бот-радар для поиска заказов и вакансий",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def root():
    """Корневой эндпоинт для health check"""
    return JSONResponse({
        "status": "ok",
        "service": "Freelance Hunter Bot",
        "bot_running": bot_instance is not None and bot_instance.running,
        "message": "Bot is running" if (bot_instance and bot_instance.running) else "Bot is starting..."
    })


@app.get("/health")
async def health_check():
    """Health check для мониторинга"""
    if bot_instance and bot_instance.running:
        return JSONResponse({
            "status": "healthy",
            "bot_status": "running",
            "queue_size": bot_instance.queue.qsize()
        })
    else:
        return JSONResponse({
            "status": "starting",
            "bot_status": "initializing"
        }, status_code=503)


@app.get("/stats")
async def get_stats():
    """Статистика работы бота"""
    if not bot_instance:
        return JSONResponse({"error": "Bot not initialized"}, status_code=503)
    
    return JSONResponse({
        "bot_running": bot_instance.running,
        "queue_size": bot_instance.queue.qsize(),
        "target_chats": TARGET_CHATS,
        "monitoring": "active" if bot_instance.running else "inactive"
    })


if __name__ == "__main__":
    # Запуск Uvicorn веб-сервера
    logger.info(f"🚀 Запуск Freelance Hunter Bot на порту {PORT}")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level="info"
    )
