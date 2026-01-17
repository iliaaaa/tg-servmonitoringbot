# 📋 Шпаргалка по командам бота

## 🚀 Быстрый старт

### 1. Установка
```bash
# Клонирование и переход в директорию
cd /opt
git clone <repo-url> tg-servmonitoringbot
cd tg-servmonitoringbot

# Создание venv и установка зависимостей
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Настройка
```bash
# Создайте .env файл
cp .env.example .env
nano .env

# Заполните:
# BOT_TOKEN=your_token
# ALLOWED_USERS=123456789
# MONITORED_SERVICES=nginx,postgresql,redis
```

### 3. Запуск через systemd
```bash
# Скопируйте сервис
sudo cp tg-monitor-bot.service /etc/systemd/system/
sudo nano /etc/systemd/system/tg-monitor-bot.service  # Замените YOUR_USER

# Запустите
sudo systemctl daemon-reload
sudo systemctl enable tg-monitor-bot
sudo systemctl start tg-monitor-bot
```

## 📱 Команды бота

### Системный мониторинг
- `/status` - общий обзор
- `/cpu` - загрузка CPU
- `/memory` - использование RAM
- `/disk` - информация о дисках
- `/processes` - топ процессов
- `/network` - сетевая статистика

### Сервисы
- `/services` - статус всех сервисов
- `/logs nginx` - логи сервиса

### Справка
- `/help` - помощь
- `/about` - о боте

## 🔧 Управление сервисом

```bash
# Статус
sudo systemctl status tg-monitor-bot

# Логи (в реальном времени)
sudo journalctl -u tg-monitor-bot -f

# Последние 50 строк логов
sudo journalctl -u tg-monitor-bot -n 50

# Перезапуск
sudo systemctl restart tg-monitor-bot

# Остановка
sudo systemctl stop tg-monitor-bot

# Запуск
sudo systemctl start tg-monitor-bot

# Отключить автозапуск
sudo systemctl disable tg-monitor-bot
```

## 🐛 Отладка

### Тестовый запуск (без systemd)
```bash
cd /opt/tg-servmonitoringbot
source venv/bin/activate
python bot.py
```

### Проверка конфигурации
```bash
cat .env
```

### Проверка доступа к сервисам
```bash
systemctl status nginx
journalctl -u nginx -n 10
```

### Добавить пользователя в группу для чтения логов
```bash
sudo usermod -aG systemd-journal your-user
# Перезайдите в систему
```

## 📊 Примеры конфигураций

### Web-сервер + БД
```env
MONITORED_SERVICES=nginx,postgresql,redis
```

### Python приложение
```env
MONITORED_SERVICES=nginx,gunicorn,celery,redis,postgresql
```

### Ruby приложение
```env
MONITORED_SERVICES=nginx,puma,sidekiq,postgresql,redis
```

### Docker приложение
```env
MONITORED_SERVICES=docker,nginx,postgresql
```

## 🔐 Безопасность

### Получить Telegram ID
1. Напишите [@userinfobot](https://t.me/userinfobot)
2. Скопируйте ID
3. Добавьте в ALLOWED_USERS

### Добавить нескольких пользователей
```env
ALLOWED_USERS=123456789,987654321,555555555
```

### Защита .env файла
```bash
chmod 600 .env
chown your-user:your-user .env
```

## 📈 Оптимизация

### Изменить интервалы проверок
```env
# Проверка сервисов каждые 30 секунд (чаще)
SERVICE_CHECK_INTERVAL=30

# Проверка дисков каждые 10 минут (реже)
DISK_CHECK_INTERVAL=600
```

### Изменить порог предупреждения о диске
```env
# Предупреждать при 90% заполнения
DISK_WARNING_THRESHOLD=90
```

## 🔄 Обновление

```bash
cd /opt/tg-servmonitoringbot
git pull
source venv/bin/activate
pip install -r requirements.txt --upgrade
sudo systemctl restart tg-monitor-bot
```

## 💡 Советы

1. **Тестируйте локально** перед деплоем на продакшн
2. **Следите за логами** после установки: `journalctl -u tg-monitor-bot -f`
3. **Не забудьте** добавить пользователя в группу `systemd-journal`
4. **Регулярно проверяйте** обновления зависимостей
5. **Используйте** сильные токены от BotFather

