"""Обработчики команд мониторинга системы"""
import asyncio
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from services import SystemMonitor

router = Router()
system_monitor = SystemMonitor()
status_update_tasks: dict[int, asyncio.Task] = {}
network_update_tasks: dict[int, asyncio.Task] = {}
process_update_tasks: dict[int, asyncio.Task] = {}
last_monitor_message_id: dict[int, int] = {}
MAX_UPDATE_SECONDS = 600


def _stop_task(task_map: dict[int, asyncio.Task], chat_id: int) -> None:
    task = task_map.pop(chat_id, None)
    if task and not task.done():
        task.cancel()


async def _delete_last_message(message: Message) -> None:
    msg_id = last_monitor_message_id.pop(message.chat.id, None)
    if msg_id:
        try:
            await message.bot.delete_message(message.chat.id, msg_id)
        except Exception:
            pass


def _stop_all(chat_id: int) -> None:
    _stop_task(status_update_tasks, chat_id)
    _stop_task(network_update_tasks, chat_id)
    _stop_task(process_update_tasks, chat_id)


@router.message(Command("status"))
async def cmd_status(message: Message):
    """Обработчик команды /status"""
    await message.bot.send_chat_action(message.chat.id, "typing")

    # Останавливаем предыдущий цикл обновления для этого чата
    _stop_all(message.chat.id)
    await _delete_last_message(message)

    status_text = system_monitor.format_status_message()
    sent = await message.answer(status_text, parse_mode="HTML")
    last_monitor_message_id[message.chat.id] = sent.message_id

    async def updater():
        try:
            start_ts = asyncio.get_running_loop().time()
            while True:
                if asyncio.get_running_loop().time() - start_ts >= MAX_UPDATE_SECONDS:
                    break
                await asyncio.sleep(2)
                updated_text = system_monitor.format_status_message()
                await sent.edit_text(updated_text, parse_mode="HTML")
        except asyncio.CancelledError:
            pass
        except Exception:
            # Если сообщение нельзя обновить (удалено/изменено), прекращаем цикл
            pass

    status_update_tasks[message.chat.id] = asyncio.create_task(updater())


@router.message(Command("process"))
async def cmd_process(message: Message):
    """Обработчик команды /process"""
    await message.bot.send_chat_action(message.chat.id, "typing")

    _stop_all(message.chat.id)
    await _delete_last_message(message)

    processes_text = system_monitor.format_processes_message()
    sent = await message.answer(processes_text, parse_mode="HTML")
    last_monitor_message_id[message.chat.id] = sent.message_id

    async def updater():
        try:
            start_ts = asyncio.get_running_loop().time()
            while True:
                if asyncio.get_running_loop().time() - start_ts >= MAX_UPDATE_SECONDS:
                    break
                await asyncio.sleep(2)
                updated_text = system_monitor.format_processes_message()
                await sent.edit_text(updated_text, parse_mode="HTML")
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    process_update_tasks[message.chat.id] = asyncio.create_task(updater())


@router.message(Command("network"))
async def cmd_network(message: Message):
    """Обработчик команды /network"""
    await message.bot.send_chat_action(message.chat.id, "typing")

    _stop_all(message.chat.id)
    await _delete_last_message(message)

    network_text = system_monitor.format_network_message()
    sent = await message.answer(network_text, parse_mode="HTML")
    last_monitor_message_id[message.chat.id] = sent.message_id

    async def updater():
        try:
            start_ts = asyncio.get_running_loop().time()
            while True:
                if asyncio.get_running_loop().time() - start_ts >= MAX_UPDATE_SECONDS:
                    break
                await asyncio.sleep(2)
                updated_text = system_monitor.format_network_message()
                await sent.edit_text(updated_text, parse_mode="HTML")
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    network_update_tasks[message.chat.id] = asyncio.create_task(updater())


@router.message(Command("stop"))
async def cmd_stop(message: Message):
    """Останавливает обновления сообщений"""
    _stop_all(message.chat.id)
    await _delete_last_message(message)

