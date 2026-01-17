"""Утилиты для форматирования сообщений"""


def format_bytes(bytes_value: int) -> str:
    """Форматирует байты в читаемый формат"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f} PB"


def format_percentage(value: float, bar_length: int = 10) -> str:
    """Создаёт прогресс-бар для процентов"""
    filled = int(bar_length * value / 100)
    bar = '█' * filled + '░' * (bar_length - filled)
    return f"{bar} {value:.1f}%"


def get_status_emoji(percentage: float) -> str:
    """Возвращает эмодзи в зависимости от загрузки"""
    if percentage < 50:
        return "🟢"
    elif percentage < 80:
        return "🟡"
    else:
        return "🔴"

