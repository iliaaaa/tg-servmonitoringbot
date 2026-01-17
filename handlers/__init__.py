"""Обработчики команд бота"""
from .basic import router as basic_router
from .monitoring import router as monitoring_router
from .services import router as services_router, set_service_monitor

__all__ = ['basic_router', 'monitoring_router', 'services_router', 'set_service_monitor']

