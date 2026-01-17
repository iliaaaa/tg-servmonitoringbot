#!/bin/bash

# Скрипт для быстрой установки и настройки бота мониторинга

echo "🚀 Установка Telegram бота для мониторинга сервера"
echo "=================================================="
echo ""

# Проверка прав root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Этот скрипт должен запускаться с правами root (sudo)"
    exit 1
fi

# Запрос данных у пользователя
echo "📝 Введите необходимые данные:"
read -p "Telegram Bot Token (от @BotFather): " BOT_TOKEN
read -p "Ваш Telegram ID (от @userinfobot): " USER_ID
read -p "Сервисы для мониторинга через запятую (например: nginx,postgresql,redis): " SERVICES
read -p "Имя пользователя для запуска бота: " USERNAME

# Установка зависимостей
echo ""
echo "📦 Установка системных зависимостей..."
apt-get update
apt-get install -y python3 python3-pip python3-venv git

# Создание директории
INSTALL_DIR="/opt/tg-servmonitoringbot"
echo ""
echo "📁 Создание директории $INSTALL_DIR..."
mkdir -p $INSTALL_DIR
cd $INSTALL_DIR

# Если это новая установка, копируем файлы
# (предполагается, что скрипт запускается из директории с исходниками)
if [ -f "../bot.py" ]; then
    cp -r ../* .
fi

# Создание виртуального окружения
echo ""
echo "🐍 Создание виртуального окружения..."
python3 -m venv venv
source venv/bin/activate

# Установка зависимостей Python
echo ""
echo "📦 Установка зависимостей Python..."
pip install --upgrade pip
pip install -r requirements.txt

# Создание .env файла
echo ""
echo "⚙️  Создание конфигурации..."
cat > .env << EOF
BOT_TOKEN=$BOT_TOKEN
ALLOWED_USERS=$USER_ID
MONITORED_SERVICES=$SERVICES
SERVICE_CHECK_INTERVAL=60
DISK_CHECK_INTERVAL=300
UPTIME_CHECK_INTERVAL=30
DISK_WARNING_THRESHOLD=85
EOF

# Настройка прав
chown -R $USERNAME:$USERNAME $INSTALL_DIR

# Добавление пользователя в группу systemd-journal для чтения логов
echo ""
echo "🔐 Настройка прав доступа..."
usermod -aG systemd-journal $USERNAME

# Создание systemd сервиса
echo ""
echo "🔧 Создание systemd сервиса..."
cat > /etc/systemd/system/tg-monitor-bot.service << EOF
[Unit]
Description=Telegram Server Monitoring Bot
After=network.target

[Service]
Type=simple
User=$USERNAME
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin"
ExecStart=$INSTALL_DIR/venv/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Запуск сервиса
echo ""
echo "🚀 Запуск бота..."
systemctl daemon-reload
systemctl enable tg-monitor-bot
systemctl start tg-monitor-bot

# Проверка статуса
echo ""
echo "✅ Установка завершена!"
echo ""
echo "📊 Статус бота:"
systemctl status tg-monitor-bot --no-pager

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✨ Бот успешно установлен и запущен!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📱 Напишите боту в Telegram команду /start"
echo ""
echo "🔍 Полезные команды:"
echo "  • Статус: sudo systemctl status tg-monitor-bot"
echo "  • Логи: sudo journalctl -u tg-monitor-bot -f"
echo "  • Рестарт: sudo systemctl restart tg-monitor-bot"
echo "  • Остановка: sudo systemctl stop tg-monitor-bot"
echo ""
echo "📝 Конфигурация: $INSTALL_DIR/.env"
echo ""

