# 🔐 Генерация StringSession для деплоя на Render

## Зачем нужен StringSession?

Telethon по умолчанию сохраняет сессию в файл. На Render файлы не сохраняются между перезапусками, поэтому нужно использовать **StringSession** - текстовое представление сессии, которое хранится в переменных окружения.

## Способ 1: Автоматический (Рекомендуется)

### 1. Локально сгенерируйте StringSession

```bash
cd WORK_HUNTER
python generate_session.py
```

Скрипт попросит:
1. Ваш номер телефона (с кодом страны): `+79991234567`
2. Код подтверждения из Telegram
3. Пароль 2FA (если включен)

### 2. Скопируйте полученную строку

Скрипт выведет что-то вроде:
```
1AgAOMTQ5LjE1NC4xNjcuNDEBuwYbCxaM3q...
```

**⚠️ Это секретный ключ! Не публикуйте его нигде!**

### 3. Добавьте в Render

1. Зайдите на Render.com → ваш сервис
2. Settings → Environment
3. Добавьте переменную:
   - Key: `SESSION_STRING`
   - Value: `<ваша длинная строка>`
4. Save Changes
5. Manual Deploy → Deploy latest commit

## Способ 2: Ручной (если generate_session.py не работает)

### 1. Локально создайте сессию

```bash
cd WORK_HUNTER
python
```

```python
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')

with TelegramClient(StringSession(), API_ID, API_HASH) as client:
    print(client.session.save())
```

### 2. Введите данные авторизации

- Номер телефона
- Код из Telegram
- Пароль 2FA (если есть)

### 3. Скопируйте строку и добавьте в Render

(как в способе 1, шаг 3)

## Способ 3: Конвертация существующей сессии

Если у вас уже есть файл `userbot_session`:

```bash
cd WORK_HUNTER
python
```

```python
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')

# Открываем существующую файловую сессию
with TelegramClient('userbot_session', API_ID, API_HASH) as client:
    # Конвертируем в StringSession
    string_session = StringSession.save(client.session)
    print("SESSION_STRING:")
    print(string_session)
```

## Проверка работы на Render

После добавления SESSION_STRING в Render:

1. **Проверьте логи:**
   ```
   INFO:__main__:Используется StringSession из переменной окружения
   INFO:__main__:Telethon userbot подключен
   ```

2. **Проверьте статус:**
   - Откройте `https://ваш-сервис.onrender.com/`
   - `bot_running` должно быть `true`

3. **Проверьте мониторинг:**
   - Напишите тестовое сообщение в один из каналов
   - Проверьте, что бот его обработал

## Локальная разработка

Локально бот использует файловую сессию `userbot_session` (если нет переменной SESSION_STRING).

При первом запуске:
```bash
python main.py
```

Введите номер телефона и код - файл `userbot_session` создастся автоматически.

## Troubleshooting

### Ошибка: "Could not stabilize entity"

**Решение:** Перегенерируйте SESSION_STRING

### Ошибка: "Session is unauthorized"

**Решение:** 
1. Удалите старую SESSION_STRING из Render
2. Сгенерируйте новую с помощью `generate_session.py`
3. Добавьте новую в Render

### Ошибка: "API ID invalid"

**Решение:** Проверьте правильность API_ID и API_HASH

### Бот постоянно переподключается

**Причина:** SESSION_STRING не задана или неверная

**Решение:** Проверьте переменную SESSION_STRING в Render Environment

## Безопасность

### ✅ Что делать:

1. **Храните SESSION_STRING в безопасности**
   - Это как пароль от вашего Telegram
   - Доступ к SESSION_STRING = полный доступ к аккаунту

2. **Не коммитьте SESSION_STRING в Git**
   - Уже добавлено в `.gitignore`
   - Храните только в Render Environment

3. **Регулярно обновляйте**
   - Если SESSION_STRING утек - немедленно перегенерируйте

### ❌ Что НЕ делать:

1. **НЕ публикуйте SESSION_STRING**
   - Не в коде
   - Не в логах
   - Не в документации

2. **НЕ используйте один SESSION для разных серверов**
   - Создайте отдельный SESSION_STRING для каждого деплоя

## Альтернативы

Если StringSession не подходит, можно:

1. **Использовать persistent storage на Render**
   - Render Free план не поддерживает
   - Нужен платный план

2. **Деплоить на другой платформе**
   - Heroku (платный)
   - Railway (бесплатный план есть)
   - VPS (DigitalOcean, Linode)

---

**При возникновении проблем создайте Issue в GitHub репозитории**
