"""Мониторинг сервисов systemd"""
import subprocess
import asyncio
from typing import Dict, List, Optional
from datetime import datetime


class ServiceMonitor:
    """Класс для мониторинга systemd сервисов"""
    
    def __init__(self, services: List[str]):
        self.services = services
        self.last_status: Dict[str, Dict] = {}
        self.notifications_queue = asyncio.Queue()
    
    async def check_service(self, service_name: str) -> Dict:
        """Проверяет статус одного сервиса"""
        try:
            # Проверяем статус сервиса
            result = await asyncio.create_subprocess_exec(
                'systemctl', 'is-active', service_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            is_active = stdout.decode().strip() == 'active'
            
            # Получаем детальную информацию
            result = await asyncio.create_subprocess_exec(
                'systemctl', 'show', service_name,
                '--property=ActiveState,SubState,MainPID,ExecMainStartTimestamp',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            
            info = {}
            for line in stdout.decode().split('\n'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    info[key] = value
            
            return {
                'name': service_name,
                'active': is_active,
                'state': info.get('ActiveState', 'unknown'),
                'substate': info.get('SubState', 'unknown'),
                'pid': info.get('MainPID', '0'),
                'start_time': info.get('ExecMainStartTimestamp', ''),
                'checked_at': datetime.now()
            }
        except Exception as e:
            return {
                'name': service_name,
                'active': False,
                'state': 'error',
                'substate': str(e),
                'pid': '0',
                'start_time': '',
                'checked_at': datetime.now()
            }
    
    async def check_all_services(self) -> List[Dict]:
        """Проверяет все сервисы"""
        tasks = [self.check_service(service) for service in self.services]
        return await asyncio.gather(*tasks)
    
    async def monitor_services(self):
        """Фоновая задача для мониторинга сервисов"""
        while True:
            current_status = await self.check_all_services()
            
            # Проверяем изменения
            for service in current_status:
                service_name = service['name']
                
                if service_name in self.last_status:
                    last = self.last_status[service_name]
                    
                    # Сервис упал
                    if last['active'] and not service['active']:
                        await self.notifications_queue.put({
                            'type': 'service_down',
                            'service': service_name,
                            'message': f"⚠️ <b>Сервис остановлен!</b>\n\n"
                                     f"🔴 <code>{service_name}</code>\n"
                                     f"Состояние: {service['state']}/{service['substate']}\n"
                                     f"Время: {service['checked_at'].strftime('%H:%M:%S')}"
                        })
                    
                    # Сервис восстановлен
                    elif not last['active'] and service['active']:
                        await self.notifications_queue.put({
                            'type': 'service_up',
                            'service': service_name,
                            'message': f"✅ <b>Сервис запущен!</b>\n\n"
                                     f"🟢 <code>{service_name}</code>\n"
                                     f"PID: {service['pid']}\n"
                                     f"Время: {service['checked_at'].strftime('%H:%M:%S')}"
                        })
                    
                    # Сервис перезапущен (изменился PID)
                    elif (last['active'] and service['active'] and 
                          last['pid'] != service['pid'] and service['pid'] != '0'):
                        await self.notifications_queue.put({
                            'type': 'service_restart',
                            'service': service_name,
                            'message': f"🔄 <b>Сервис перезапущен!</b>\n\n"
                                     f"🟡 <code>{service_name}</code>\n"
                                     f"Старый PID: {last['pid']} → Новый PID: {service['pid']}\n"
                                     f"Время: {service['checked_at'].strftime('%H:%M:%S')}"
                        })
                
                # Сохраняем текущий статус
                self.last_status[service_name] = service
            
            # Ждём до следующей проверки
            await asyncio.sleep(60)  # Проверяем каждую минуту
    
    def format_services_message(self) -> str:
        """Форматирует сообщение о статусе всех сервисов"""
        if not self.last_status:
            return "ℹ️ Статус сервисов ещё не проверен. Подождите немного..."
        
        message = f"🔧 <b>Статус сервисов</b>\n\n"
        
        for service_name in self.services:
            if service_name in self.last_status:
                service = self.last_status[service_name]
                
                if service['active']:
                    emoji = "🟢"
                    status = "активен"
                else:
                    emoji = "🔴"
                    status = "остановлен"
                
                message += f"{emoji} <b>{service_name}</b>\n"
                message += f"   Статус: {status}\n"
                
                if service['active'] and service['pid'] != '0':
                    message += f"   PID: {service['pid']}\n"
                
                message += f"   Проверено: {service['checked_at'].strftime('%H:%M:%S')}\n\n"
            else:
                message += f"⚪️ <b>{service_name}</b>\n"
                message += f"   Статус: неизвестен\n\n"
        
        return message.rstrip()
    
    async def get_service_logs(self, service_name: str, lines: int = 20) -> str:
        """Получает последние логи сервиса"""
        try:
            result = await asyncio.create_subprocess_exec(
                'journalctl', '-u', service_name, '-n', str(lines), '--no-pager',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                return f"❌ Ошибка получения логов: {stderr.decode()}"
            
            logs = stdout.decode()
            if not logs.strip():
                return f"ℹ️ Логи для сервиса <code>{service_name}</code> отсутствуют"
            
            # Ограничиваем длину сообщения Telegram (4096 символов)
            if len(logs) > 3800:
                logs = logs[-3800:]
                logs = "...\n" + logs
            
            return f"📄 <b>Логи сервиса {service_name}</b>\n\n<pre>{logs}</pre>"
        
        except Exception as e:
            return f"❌ Ошибка: {str(e)}"

