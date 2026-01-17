"""
Telegram бот для мониторинга сервера
"""
import asyncio
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

import config
from middleware import AuthMiddleware
from handlers import basic_router, monitoring_router, services_router, set_service_monitor
from services import SystemMonitor, ServiceMonitor, Notifier
from utils import format_bytes

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def check_disk_space(system_monitor: SystemMonitor, notifier: Notifier):
    """Фоновая задача для проверки свободного места на диске"""
    logger.info("Запущена задача мониторинга дисков")
    notified_disks = set()
    
    while True:
        try:
            disks = system_monitor.get_disk_info()
            
            for disk in disks:
                disk_key = disk['mountpoint']
                
                # Если заполнение превышает порог
                if disk['percent'] >= config.DISK_WARNING_THRESHOLD:
                    # Отправляем уведомление только один раз
                    if disk_key not in notified_disks:
                        message = (
                            f"⚠️ <b>Предупреждение о дисковом пространстве!</b>\n\n"
                            f"🔴 Диск <code>{disk['mountpoint']}</code> заполнен на {disk['percent']:.1f}%\n"
                            f"Свободно: {format_bytes(disk['free'])} из {format_bytes(disk['total'])}\n\n"
                            f"Рекомендуется освободить место!"
                        )
                        await notifier.send_notification(message)
                        notified_disks.add(disk_key)
                        logger.warning(f"Отправлено предупреждение о диске {disk_key}")
                else:
                    # Если место освободилось, убираем из списка уведомлённых
                    if disk_key in notified_disks:
                        notified_disks.discard(disk_key)
            
            await asyncio.sleep(config.DISK_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Ошибка при проверке дисков: {e}")
            await asyncio.sleep(60)


async def check_server_uptime(system_monitor: SystemMonitor, notifier: Notifier):
    """Фоновая задача для отслеживания перезагрузок сервера"""
    logger.info("Запущена задача мониторинга uptime")
    
    # Запоминаем время загрузки
    last_boot_time = system_monitor.boot_time
    first_check = True
    
    while True:
        try:
            current_boot_time = datetime.fromtimestamp(system_monitor.boot_time.timestamp())
            
            # Если время загрузки изменилось - сервер перезагрузился
            if current_boot_time != last_boot_time:
                if not first_check:  # Не уведомляем при первом запуске бота
                    message = (
                        f"🔄 <b>Обнаружена перезагрузка сервера!</b>\n\n"
                        f"⏱ Время перезагрузки: {current_boot_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"⏰ Текущее время: {datetime.now().strftime('%H:%M:%S')}"
                    )
                    await notifier.send_notification(message)
                    logger.warning("Обнаружена перезагрузка сервера")
                
                last_boot_time = current_boot_time
            
            first_check = False
            await asyncio.sleep(config.UPTIME_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Ошибка при проверке uptime: {e}")
            await asyncio.sleep(60)


async def on_startup(bot: Bot, service_monitor: ServiceMonitor, notifier: Notifier):
    """Действия при запуске бота"""
    logger.info("Бот запущен!")
    
    # Уведомляем пользователей о запуске
    startup_message = (
        f"✅ <b>Бот мониторинга запущен!</b>\n\n"
        f"⏰ Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"🔧 Отслеживаемых сервисов: {len(config.MONITORED_SERVICES)}\n"
        f"📊 Интервал проверки: {config.SERVICE_CHECK_INTERVAL}с\n\n"
        f"Используйте /help для просмотра команд"
    )
    await notifier.send_notification(startup_message)


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
    dp.include_router(basic_router)
    dp.include_router(monitoring_router)
    dp.include_router(services_router)
    
    # Создаём сервисы
    system_monitor = SystemMonitor()
    service_monitor = ServiceMonitor(config.MONITORED_SERVICES)
    notifier = Notifier(bot, config.ALLOWED_USERS)
    
    # Передаём service_monitor в обработчики
    set_service_monitor(service_monitor)
    
    # Запускаем фоновые задачи
    asyncio.create_task(service_monitor.monitor_services())
    asyncio.create_task(notifier.process_notifications_queue(service_monitor.notifications_queue))
    asyncio.create_task(check_disk_space(system_monitor, notifier))
    asyncio.create_task(check_server_uptime(system_monitor, notifier))
    
    # Действия при запуске
    await on_startup(bot, service_monitor, notifier)
    
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

