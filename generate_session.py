#!/usr/bin/env python3
"""
Скрипт для генерации StringSession для Telethon
Используется для деплоя на Render без файловой сессии
"""

import os
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')

if not API_ID or not API_HASH:
    print("❌ Ошибка: API_ID и API_HASH должны быть заданы в .env файле")
    exit(1)

print("🔐 Генерация StringSession для Telethon")
print("=" * 60)
print()
print("Этот скрипт создаст StringSession, который нужно добавить")
print("в переменные окружения на Render как SESSION_STRING")
print()
print("=" * 60)
print()

# Создание клиента с пустой StringSession
with TelegramClient(StringSession(), API_ID, API_HASH) as client:
    print("✅ Авторизация успешна!")
    print()
    print("=" * 60)
    print("📋 Ваш SESSION_STRING:")
    print("=" * 60)
    print()
    print(client.session.save())
    print()
    print("=" * 60)
    print()
    print("📝 Инструкции:")
    print("1. Скопируйте строку выше (весь текст)")
    print("2. Зайдите на Render.com → ваш сервис → Environment")
    print("3. Добавьте переменную SESSION_STRING с этим значением")
    print("4. Перезапустите сервис")
    print()
    print("⚠️  ВАЖНО: Не делитесь этой строкой! Она даёт полный доступ к аккаунту!")
    print()
