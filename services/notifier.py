"""Сервис для отправки уведомлений"""
import asyncio
from typing import List
from aiogram import Bot


class Notifier:
    """Класс для отправки уведомлений пользователям"""
    
    def __init__(self, bot: Bot, user_ids: List[int]):
        self.bot = bot
        self.user_ids = user_ids
    
    async def send_notification(self, message: str):
        """Отправляет уведомление всем пользователям из whitelist"""
        tasks = []
        for user_id in self.user_ids:
            tasks.append(
                self.bot.send_message(
                    chat_id=user_id,
                    text=message,
                    parse_mode="HTML"
                )
            )
        
        # Отправляем все сообщения параллельно
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def process_notifications_queue(self, queue: asyncio.Queue):
        """Обрабатывает очередь уведомлений"""
        while True:
            notification = await queue.get()
            await self.send_notification(notification['message'])
            queue.task_done()

