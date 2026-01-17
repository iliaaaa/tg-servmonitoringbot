# ⚡ Быстрый старт

Установка и запуск бота за 5 минут!

## 1️⃣ Получите токен бота

1. Откройте [@BotFather](https://t.me/BotFather)
2. Отправьте `/newbot`
3. Следуйте инструкциям
4. Сохраните токен: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`

## 2️⃣ Узнайте свой ID

1. Откройте [@userinfobot](https://t.me/userinfobot)
2. Сохраните ID: `123456789`

## 3️⃣ Установите на сервер

```bash
cd /opt
git clone <your-repo> tg-servmonitoringbot
cd tg-servmonitoringbot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 4️⃣ Настройте

```bash
cp .env.example .env
nano .env
```

Заполните:
```env
BOT_TOKEN=ваш_токен_от_BotFather
ALLOWED_USERS=ваш_telegram_id
MONITORED_SERVICES=nginx,postgresql,redis
```

## 5️⃣ Запустите

### Тестовый запуск
```bash
python bot.py
```

### Запуск как сервис (рекомендуется)
```bash
# Отредактируйте сервис (замените YOUR_USER)
sudo nano tg-monitor-bot.service

# Скопируйте и запустите
sudo cp tg-monitor-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable tg-monitor-bot
sudo systemctl start tg-monitor-bot
```

## 6️⃣ Проверьте

```bash
sudo systemctl status tg-monitor-bot
```

## 7️⃣ Используйте

Откройте бота в Telegram и напишите:
```
/start
/status
/services
```

---

## 🆘 Проблемы?

### Бот не отвечает
```bash
sudo journalctl -u tg-monitor-bot -n 50
```

### Ошибка доступа к сервисам
```bash
sudo usermod -aG systemd-journal ваш_пользователь
# Перезайдите в систему
```

---

## 📚 Подробная документация

- [README.md](README.md) - полная документация
- [CHEATSHEET.md](CHEATSHEET.md) - шпаргалка по командам
- [EXAMPLES.md](EXAMPLES.md) - примеры использования
- [OUTPUT_EXAMPLES.md](OUTPUT_EXAMPLES.md) - примеры вывода

---

**Всё готово! Бот работает 24/7 и будет уведомлять вас о проблемах! 🎉**

