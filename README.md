# Work Timer

Трекер рабочего времени для Linux Mint. Живёт в системном трее — зелёный кружок в ожидании, красный во время работы. Сессии записываются в Supabase, отчёты выгружаются в Markdown.

## Возможности

- **Старт / пауза / стоп** — ввод названия задачи через диалог, логирование в Supabase; пауза не засчитывается в затраченное время
- **Статистика за сегодня** — таблица сессий с временем и итогом
- **Отчёт за неделю и месяц** — сохранение `.md`-файла с разбивкой по дням, запоминает последнюю папку сохранения
- **Автозапуск** — скрипт создаёт `~/.config/autostart/work-timer.desktop`

## Стек

Python 3.12 · pystray (ayatana-appindicator) · Pillow · supabase-py · python-dotenv · zenity · notify-send · wmctrl

## Быстрый старт

```bash
# 1. Системные зависимости
sudo apt install python3-gi python3-gi-cairo \
    gir1.2-ayatanaappindicator3-0.1 libayatana-appindicator3-1 \
    libnotify-bin zenity wmctrl

# 2. Виртуальное окружение
/usr/bin/python3 -m venv .venv --system-site-packages
.venv/bin/pip install -r requirements.txt

# 3. Настройка
cp .env.example .env
# отредактируйте .env — укажите SUPABASE_URL и SUPABASE_KEY

# 4. Создайте таблицу в Supabase (SQL Editor)
# → выполните create_table.sql

# 5. Запуск
.venv/bin/python timer.py
```

## Структура таблицы Supabase

Таблица `wh_work_log`. Каждая сессия — цепочка строк `start` → (`pause` / `resume`)* → `stop`, связанных по `session_id`.

| Поле | Тип | Описание |
|------|-----|----------|
| `session_id` | uuid | Связывает все события одной сессии |
| `operation` | varchar(6) | `start`, `pause`, `resume` или `stop` |
| `task` | text | Название задачи |
| `event_time` | timestamptz | Время события (UTC) |
| `elapsed_time` | text | Затраченное время без пауз (только у `stop`) |

## Безопасность

Проведён статический анализ кода. Уязвимостей не обнаружено.

| Область | Результат | Примечание |
|---------|-----------|------------|
| Инъекция команд | ✅ Безопасно | Все вызовы `subprocess` используют список аргументов, `shell=False` |
| SQL-инъекция | ✅ Безопасно | Запросы к Supabase через параметризованный API (`.eq()`, `.gte()`, `.in_()`) |
| Временные файлы | ✅ Безопасно | `NamedTemporaryFile` + удаление в `finally` |
| Пользовательский ввод | ✅ Безопасно | Текст задачи экранируется при записи в Markdown (`\|`) |
| Секреты | ✅ Безопасно | Credentials только через переменные окружения, `.env` исключён из git |

## Подробная документация

См. [GUIDE.md](GUIDE.md) — полная инструкция по установке, использованию, структуре данных и устранению неполадок.
