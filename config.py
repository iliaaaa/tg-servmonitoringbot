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

# Мониторинг сервисов
MONITORED_SERVICES_STR = os.getenv('MONITORED_SERVICES', '')
MONITORED_SERVICES = [s.strip() for s in MONITORED_SERVICES_STR.split(',') if s.strip()]

# Интервалы проверок (в секундах)
SERVICE_CHECK_INTERVAL = int(os.getenv('SERVICE_CHECK_INTERVAL', '60'))
DISK_CHECK_INTERVAL = int(os.getenv('DISK_CHECK_INTERVAL', '300'))
UPTIME_CHECK_INTERVAL = int(os.getenv('UPTIME_CHECK_INTERVAL', '30'))

# Пороги предупреждений
DISK_WARNING_THRESHOLD = int(os.getenv('DISK_WARNING_THRESHOLD', '85'))

# Версия бота
VERSION = "1.0.0"

