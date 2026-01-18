"""
Конфигурация бота для мониторинга сервера
"""
import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Telegram
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не установлен в .env файле!")

# Whitelist пользователей
ALLOWED_USERS_STR = os.getenv('ALLOWED_USERS', '')
ALLOWED_USERS = [int(uid.strip()) for uid in ALLOWED_USERS_STR.split(',') if uid.strip()]

if not ALLOWED_USERS:
    raise ValueError("ALLOWED_USERS не установлен в .env файле!")

# Дополнительных настроек не требуется

