"""Обработчики команд мониторинга системы"""
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from services import SystemMonitor

router = Router()
system_monitor = SystemMonitor()


@router.message(Command("status"))
async def cmd_status(message: Message):
    """Обработчик команды /status"""
    # Показываем индикатор "печатает"
    await message.bot.send_chat_action(message.chat.id, "typing")
    
    status_text = system_monitor.format_status_message()
    await message.answer(status_text, parse_mode="HTML")


@router.message(Command("cpu"))
async def cmd_cpu(message: Message):
    """Обработчик команды /cpu"""
    await message.bot.send_chat_action(message.chat.id, "typing")
    
    cpu_text = system_monitor.format_cpu_message()
    await message.answer(cpu_text, parse_mode="HTML")


@router.message(Command("memory"))
async def cmd_memory(message: Message):
    """Обработчик команды /memory"""
    await message.bot.send_chat_action(message.chat.id, "typing")
    
    memory_text = system_monitor.format_memory_message()
    await message.answer(memory_text, parse_mode="HTML")


@router.message(Command("disk"))
async def cmd_disk(message: Message):
    """Обработчик команды /disk"""
    await message.bot.send_chat_action(message.chat.id, "typing")
    
    disk_text = system_monitor.format_disk_message()
    await message.answer(disk_text, parse_mode="HTML")


@router.message(Command("processes"))
async def cmd_processes(message: Message):
    """Обработчик команды /processes"""
    await message.bot.send_chat_action(message.chat.id, "typing")
    
    processes_text = system_monitor.format_processes_message()
    await message.answer(processes_text, parse_mode="HTML")


@router.message(Command("network"))
async def cmd_network(message: Message):
    """Обработчик команды /network"""
    await message.bot.send_chat_action(message.chat.id, "typing")
    
    network_text = system_monitor.format_network_message()
    await message.answer(network_text, parse_mode="HTML")

