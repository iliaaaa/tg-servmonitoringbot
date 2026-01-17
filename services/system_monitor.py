"""Мониторинг системных ресурсов"""
import psutil
import platform
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from utils import format_bytes, format_percentage, get_status_emoji


class SystemMonitor:
    """Класс для мониторинга системных ресурсов"""
    
    def __init__(self):
        self.boot_time = datetime.fromtimestamp(psutil.boot_time())
    
    def get_cpu_info(self) -> Dict:
        """Получает информацию о CPU"""
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_per_core = psutil.cpu_percent(interval=1, percpu=True)
        cpu_count = psutil.cpu_count()
        
        return {
            'total': cpu_percent,
            'per_core': cpu_per_core,
            'count': cpu_count,
            'freq': psutil.cpu_freq()
        }
    
    def get_memory_info(self) -> Dict:
        """Получает информацию о памяти"""
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        return {
            'total': mem.total,
            'available': mem.available,
            'used': mem.used,
            'percent': mem.percent,
            'swap_total': swap.total,
            'swap_used': swap.used,
            'swap_percent': swap.percent
        }
    
    def get_disk_info(self) -> List[Dict]:
        """Получает информацию о дисках"""
        disks = []
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                disks.append({
                    'device': partition.device,
                    'mountpoint': partition.mountpoint,
                    'fstype': partition.fstype,
                    'total': usage.total,
                    'used': usage.used,
                    'free': usage.free,
                    'percent': usage.percent
                })
            except PermissionError:
                continue
        return disks
    
    def get_network_info(self) -> Dict:
        """Получает информацию о сети"""
        net_io = psutil.net_io_counters()
        connections = len(psutil.net_connections())
        
        return {
            'bytes_sent': net_io.bytes_sent,
            'bytes_recv': net_io.bytes_recv,
            'packets_sent': net_io.packets_sent,
            'packets_recv': net_io.packets_recv,
            'connections': connections
        }
    
    def get_top_processes(self, limit: int = 10) -> List[Dict]:
        """Получает топ процессов по использованию CPU"""
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                pinfo = proc.info
                processes.append({
                    'pid': pinfo['pid'],
                    'name': pinfo['name'],
                    'cpu': pinfo['cpu_percent'],
                    'memory': pinfo['memory_percent']
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # Сортируем по CPU
        processes.sort(key=lambda x: x['cpu'], reverse=True)
        return processes[:limit]
    
    def get_uptime(self) -> timedelta:
        """Получает время работы системы"""
        return datetime.now() - self.boot_time
    
    def format_status_message(self) -> str:
        """Форматирует полное сообщение о статусе системы"""
        cpu = self.get_cpu_info()
        mem = self.get_memory_info()
        disks = self.get_disk_info()
        uptime = self.get_uptime()
        
        # Форматируем uptime
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        uptime_str = f"{days}д {hours}ч {minutes}м"
        
        message = f"📊 <b>Статус сервера</b>\n\n"
        
        # CPU
        message += f"🖥 <b>CPU:</b> {get_status_emoji(cpu['total'])}\n"
        message += f"{format_percentage(cpu['total'])}\n"
        message += f"Ядер: {cpu['count']}\n\n"
        
        # Memory
        message += f"💾 <b>RAM:</b> {get_status_emoji(mem['percent'])}\n"
        message += f"{format_percentage(mem['percent'])}\n"
        message += f"Использовано: {format_bytes(mem['used'])} / {format_bytes(mem['total'])}\n\n"
        
        # Disks
        message += f"💿 <b>Диски:</b>\n"
        for disk in disks:
            emoji = get_status_emoji(disk['percent'])
            message += f"{emoji} <code>{disk['mountpoint']}</code>\n"
            message += f"  {format_percentage(disk['percent'], 8)}\n"
            message += f"  {format_bytes(disk['free'])} свободно из {format_bytes(disk['total'])}\n"
        
        message += f"\n⏱ <b>Uptime:</b> {uptime_str}\n"
        message += f"🖥 <b>OS:</b> {platform.system()} {platform.release()}"
        
        return message
    
    def format_cpu_message(self) -> str:
        """Детальная информация о CPU"""
        cpu = self.get_cpu_info()
        
        message = f"🖥 <b>Информация о CPU</b>\n\n"
        message += f"<b>Общая загрузка:</b> {get_status_emoji(cpu['total'])}\n"
        message += f"{format_percentage(cpu['total'])}\n\n"
        
        message += f"<b>По ядрам:</b>\n"
        for i, percent in enumerate(cpu['per_core'], 1):
            message += f"Core {i}: {format_percentage(percent, 8)}\n"
        
        if cpu['freq']:
            message += f"\n<b>Частота:</b> {cpu['freq'].current:.0f} MHz"
        
        return message
    
    def format_memory_message(self) -> str:
        """Детальная информация о памяти"""
        mem = self.get_memory_info()
        
        message = f"💾 <b>Информация о памяти</b>\n\n"
        message += f"<b>RAM:</b> {get_status_emoji(mem['percent'])}\n"
        message += f"{format_percentage(mem['percent'])}\n"
        message += f"Всего: {format_bytes(mem['total'])}\n"
        message += f"Использовано: {format_bytes(mem['used'])}\n"
        message += f"Доступно: {format_bytes(mem['available'])}\n"
        
        if mem['swap_total'] > 0:
            message += f"\n<b>SWAP:</b> {get_status_emoji(mem['swap_percent'])}\n"
            message += f"{format_percentage(mem['swap_percent'])}\n"
            message += f"Использовано: {format_bytes(mem['swap_used'])} / {format_bytes(mem['swap_total'])}"
        
        return message
    
    def format_disk_message(self) -> str:
        """Детальная информация о дисках"""
        disks = self.get_disk_info()
        
        message = f"💿 <b>Информация о дисках</b>\n\n"
        
        for disk in disks:
            emoji = get_status_emoji(disk['percent'])
            message += f"{emoji} <b>{disk['mountpoint']}</b>\n"
            message += f"Устройство: <code>{disk['device']}</code>\n"
            message += f"ФС: {disk['fstype']}\n"
            message += f"{format_percentage(disk['percent'])}\n"
            message += f"Всего: {format_bytes(disk['total'])}\n"
            message += f"Использовано: {format_bytes(disk['used'])}\n"
            message += f"Свободно: {format_bytes(disk['free'])}\n\n"
        
        return message.rstrip()
    
    def format_processes_message(self) -> str:
        """Информация о топ процессах"""
        processes = self.get_top_processes(10)
        
        message = f"📋 <b>Топ-10 процессов по CPU</b>\n\n"
        
        for i, proc in enumerate(processes, 1):
            message += f"{i}. <b>{proc['name']}</b>\n"
            message += f"   PID: {proc['pid']} | CPU: {proc['cpu']:.1f}% | RAM: {proc['memory']:.1f}%\n"
        
        return message
    
    def format_network_message(self) -> str:
        """Информация о сети"""
        net = self.get_network_info()
        
        message = f"🌐 <b>Сетевая статистика</b>\n\n"
        message += f"📤 Отправлено: {format_bytes(net['bytes_sent'])}\n"
        message += f"📥 Получено: {format_bytes(net['bytes_recv'])}\n"
        message += f"📦 Пакетов отправлено: {net['packets_sent']:,}\n"
        message += f"📦 Пакетов получено: {net['packets_recv']:,}\n"
        message += f"🔌 Активных соединений: {net['connections']}"
        
        return message

