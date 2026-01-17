"""Обработчики команд мониторинга сервисов"""
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()
service_monitor = None  # Будет установлен в main


def set_service_monitor(monitor):
    """Устанавливает экземпляр ServiceMonitor"""
    global service_monitor
    service_monitor = monitor


@router.message(Command("services"))
async def cmd_services(message: Message):
    """Обработчик команды /services"""
    await message.bot.send_chat_action(message.chat.id, "typing")
    
    if service_monitor is None:
        await message.answer("❌ Мониторинг сервисов не настроен")
        return
    
    services_text = service_monitor.format_services_message()
    await message.answer(services_text, parse_mode="HTML")


@router.message(Command("logs"))
async def cmd_logs(message: Message):
    """Обработчик команды /logs <service>"""
    await message.bot.send_chat_action(message.chat.id, "typing")
    
    if service_monitor is None:
        await message.answer("❌ Мониторинг сервисов не настроен")
        return
    
    # Получаем аргументы команды
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        await message.answer(
            "ℹ️ Использование: <code>/logs &lt;service&gt;</code>\n\n"
            f"Доступные сервисы:\n" + 
            "\n".join([f"• <code>{s}</code>" for s in service_monitor.services]),
            parse_mode="HTML"
        )
        return
    
    service_name = args[1].strip()
    
    # Проверяем, что сервис в списке мониторинга
    if service_name not in service_monitor.services:
        await message.answer(
            f"❌ Сервис <code>{service_name}</code> не отслеживается.\n\n"
            f"Доступные сервисы:\n" + 
            "\n".join([f"• <code>{s}</code>" for s in service_monitor.services]),
            parse_mode="HTML"
        )
        return
    
    # Получаем логи
    logs_text = await service_monitor.get_service_logs(service_name)
    await message.answer(logs_text, parse_mode="HTML")

