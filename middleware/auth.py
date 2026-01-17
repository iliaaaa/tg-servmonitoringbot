"""Middleware для аутентификации пользователей по whitelist"""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
import config


class AuthMiddleware(BaseMiddleware):
    """
    Middleware для проверки, что пользователь в whitelist
    """
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id
        
        # Проверяем whitelist
        if user_id not in config.ALLOWED_USERS:
            if isinstance(event, Message):
                await event.answer(
                    "❌ Доступ запрещён!\n\n"
                    f"Ваш ID: `{user_id}`\n"
                    "Обратитесь к администратору для получения доступа.",
                    parse_mode="Markdown"
                )
            return
        
        # Пользователь авторизован, продолжаем
        return await handler(event, data)

