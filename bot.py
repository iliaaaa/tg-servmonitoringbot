"""
Telegram бот для мониторинга сервера
"""
import asyncio
import logging
from datetime import datetime
import psutil

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

import config
from middleware import AuthMiddleware
from handlers import monitoring_router
from services import SystemMonitor

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def monitor_reboot(bot: Bot):
    """Фоновая задача: уведомление о перезагрузке сервера"""
    last_boot_ts = psutil.boot_time()
    first_check = True

    while True:
        try:
            current_boot_ts = psutil.boot_time()
            if current_boot_ts != last_boot_ts:
                if not first_check:
                    boot_time = datetime.fromtimestamp(current_boot_ts)
                    message = (
                        "🔄 <b>Обнаружена перезагрузка сервера!</b>\n\n"
                        f"⏱ Время перезагрузки: {boot_time.strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                    for user_id in config.ALLOWED_USERS:
                        await bot.send_message(user_id, message, parse_mode="HTML")
                    logger.warning("Обнаружена перезагрузка сервера")

                last_boot_ts = current_boot_ts
            first_check = False
            await asyncio.sleep(30)
        except Exception as e:
            logger.error(f"Ошибка при проверке перезагрузки: {e}")
            await asyncio.sleep(60)


async def main():
    """Главная функция"""
    # Создаём бота и диспетчер
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()
    
    # Подключаем middleware авторизации
    dp.message.middleware(AuthMiddleware())
    
    # Подключаем роутеры
    dp.include_router(monitoring_router)

    # Фоновая задача уведомлений о перезагрузке
    asyncio.create_task(monitor_reboot(bot))
    
    # Запускаем polling
    try:
        logger.info("Начинаем polling...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")

