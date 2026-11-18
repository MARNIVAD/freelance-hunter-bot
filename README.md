# 🎯 Freelance Hunter Bot

Telegram-бот-радар для автоматического поиска и анализа заказов и вакансий для Python-разработчиков с поддержкой деплоя на Render.

## 📋 Описание

Бот мониторит указанные Telegram-каналы с вакансиями и заказами, анализирует сообщения через OpenAI GPT-4o-mini и отправляет уведомления администратору только о релевантных предложениях.

### Ключевые возможности:

- 🔍 **Мониторинг каналов**: Telethon userbot отслеживает новые сообщения
- 🗑️ **Первичная фильтрация**: Автоматически отсекает мусор ДО отправки в AI
- 🤖 **AI-анализ**: OpenAI GPT-4o-mini анализирует релевантность
- 💾 **Дедупликация**: SQLite предотвращает повторную обработку
- ⚡ **Producer-Consumer**: Асинхронная архитектура через asyncio.Queue
- 🔔 **Уведомления**: aiogram отправляет красивые уведомления
- 🌐 **FastAPI веб-сервер**: Предотвращает засыпание на Render
- 🛡️ **Защита от банов**: Случайные паузы между запросами

## 🚀 Локальная установка

```bash
cd WORK_HUNTER
pip install -r requirements.txt
cp .env.example .env
# Заполните .env файл
python main.py
```

## ☁️ Деплой на Render

### 1. Создайте репозиторий на GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git push
```

### 2. Создайте Web Service на Render.com

- Подключите ваш GitHub репозиторий
- Render автоматически обнаружит `render.yaml`
- Добавьте переменные окружения:
  - API_ID
  - API_HASH
  - ADMIN_TELEGRAM_ID
  - BOT_TOKEN
  - OPENAI_API_KEY
  - TARGET_CHATS

### 3. Первая авторизация Telethon на Render

При первом запуске:
1. Зайдите в логи сервиса
2. Используйте Render Shell для ввода кода:

```bash
python
from telethon.sync import TelegramClient
client = TelegramClient('freelance_hunter', API_ID, API_HASH)
client.start()
```

3. Введите номер телефона и код
4. Перезапустите сервис

## 📊 API Эндпоинты

- **GET /** - Статус сервиса
- **GET /health** - Health check для мониторинга
- **GET /stats** - Статистика работы

## ⚙️ Конфигурация

### Настройка стека разработчика

В `main.py`:

```python
DEVELOPER_STACK = """Python 3.11+, aiogram 3, Telethon, FastAPI..."""
```

### Порог релевантности

```python
if analysis.type in ('order', 'vacancy') and analysis.relevance >= 70:
    # Измените 70 на нужное значение
```

## 📱 Формат уведомлений

```
💼 Вакансия | Релевантность: 85%

Канал: Python Jobs
Краткое описание:
Требуется Python-разработчик...

Стек: Python, Telethon, OpenAI API
Бюджет: 50,000 - 100,000 руб

Ссылка: https://t.me/python_vacancy/12345

📝 Черновик отклика:
Добрый день! Имею большой опыт...
```

## 🐛 Отладка

### Render не запускается
- Проверьте логи в Render Dashboard
- Убедитесь, что все переменные окружения заданы

### Telethon не авторизуется
```bash
rm freelance_hunter.session
python main.py
```

### Не приходят уведомления
- Проверьте ADMIN_TELEGRAM_ID
- Проверьте порог релевантности
- Проверьте логи бота

## 💰 Стоимость

### Render (Free Plan)
- ✅ Бесплатно
- ⚠️ 750 часов/месяц
- ✅ FastAPI предотвращает засыпание

### OpenAI (GPT-4o-mini)
- $0.150 / 1M входных токенов
- $0.600 / 1M выходных токенов
- ~$0.001 на анализ сообщения
- ~1000 сообщений = $1

## 📄 Лицензия

MIT License

---

**Удачи в поиске заказов! 🚀**
