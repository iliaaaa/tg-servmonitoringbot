# 🤖 Telegram Бот для Мониторинга Сервера (Go)

Минимальный бот для мониторинга с низким потреблением ресурсов.

## ✨ Возможности

- `/status` — краткий обзор CPU/RAM/дисков/uptime
- `/network` — детальная статистика по интерфейсам
- `/process` — 10 самых тяжёлых процессов
- `/stop` — остановка обновлений и удаление сообщения
- уведомление о перезагрузке сервера
- уведомления по каталогам процессов (см. `WATCH_DIRS`)
- уведомления по systemd unit (см. `WATCH_UNITS`)

## 🚀 Быстрый старт

1) Получите токен у [@BotFather](https://t.me/BotFather) и свой ID у [@userinfobot](https://t.me/userinfobot).

2) Сборка:
```bash
cd /opt
git clone <your-repo> tg-servmonitoringbot
cd tg-servmonitoringbot
go build -ldflags "-s -w" -o tg-monitor-bot
```

3) Создайте `.env`:
```env
BOT_TOKEN=ваш_токен_от_BotFather
ALLOWED_USERS=ваш_telegram_id
WATCH_DIRS=/opt/bots,/home/user/.rbenv
WATCH_UNITS=tg-monitor-bot.service,nginx.service
WATCH_UNIT_PREFIXES=my-,tg_
```

4) Запуск:
```bash
./tg-monitor-bot
```

## systemd

Используйте `tg-monitor-bot.service` (укажите `YOUR_USER`).

## 🛠 Устранение проблем

```bash
sudo systemctl status tg-monitor-bot
sudo journalctl -u tg-monitor-bot -n 50
```

## 🔒 Безопасность

1. **Никогда не публикуйте** `.env`
2. **Whitelist** — только доверенные пользователи

