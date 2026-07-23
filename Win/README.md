# Work Timer — Windows

Windows-версия трей-таймера. Логика и структура данных полностью совпадают с Linux-версией (см. корневой [README.md](../README.md), [GUIDE.md](../GUIDE.md) и [sql/migrations](../sql/migrations)) — это тот же таймер, адаптированный под платформу. Умеет работать и с Supabase, и с любой PostgreSQL напрямую — см. [«Настройка подключения к БД»](#настройка-подключения-к-бд).

## Чем отличается от Linux-версии

Linux-версия использует системные утилиты Cinnamon/GTK (`zenity`, `notify-send`, `wmctrl`, AppIndicator), которых на Windows нет. В этой версии их заменяет `tkinter` — входит в стандартную поставку Python, отдельно ставить не нужно:

| Linux | Windows |
|---|---|
| `zenity --entry` (ввод задачи) | окно `tkinter` |
| `zenity --list`/`--forms` (мастер настройки БД) | окна `tkinter` |
| `notify-send` (уведомления) | всплывающее окно `tkinter` в углу экрана |
| `zenity --text-info` (статистика) | окно `tkinter` со прокруткой |
| `zenity --file-selection` (сохранение отчёта) | стандартный диалог `tkinter.filedialog` |
| `wmctrl` (фокус окна) | не требуется — окна `tkinter` открываются поверх окон с фокусом |
| системный трей через AppIndicator | системный трей через `pystray` (win32-бэкенд) |
| `~/.config/work-timer/` | `%APPDATA%\WorkTimer\` |

Бизнес-логика (запуск/пауза/стоп, статистика, генерация `.md`-отчёта, доступ к БД через `db_backend.py`) — идентична Linux-версии, файл в файл.

## Установка

Требуется Python 3.10+ ([python.org](https://www.python.org/downloads/) — при установке отметьте **Add python.exe to PATH**).

```bat
install.bat
```

Скрипт создаст виртуальное окружение `.venv`, поставит зависимости из `requirements.txt` (включая `psycopg2-binary` для PostgreSQL) и скопирует `.env.example` в `.env`.

## Настройка подключения к БД

При первом запуске `run.bat`/`run_debug.bat` появится мастер настройки:

1. Выбор способа подключения — **Supabase** или **PostgreSQL** (прямое подключение).
2. **Supabase**: `SUPABASE_URL` и `SUPABASE_KEY` (Project Settings → API). Поле `DATABASE_URL` необязательно — если заполнить его строкой подключения к Postgres того же проекта (Project Settings → Database), миграции будут применяться автоматически.
3. **PostgreSQL**: строка подключения `DATABASE_URL` вида `postgresql://user:password@host:port/dbname` — используется и для обычной работы, и для автомиграций.

Введённые данные сохраняются в `.env` (`DB_BACKEND=supabase|postgres` + соответствующие поля), мастер больше не появляется. Если задан `DATABASE_URL`, при каждом запуске приложение само проверяет и применяет ещё не применённые файлы из `sql/migrations`.

Если `.env` уже содержит рабочие `SUPABASE_URL`/`SUPABASE_KEY` от версии до появления мастера — он не запустится, `DB_BACKEND=supabase` проставится автоматически.

## Запуск

```bat
run.bat
```

Запускает таймер в фоне без консольного окна (`pythonw.exe`). В трее появится зелёный кружок.

Если что-то не работает — запустите `run_debug.bat`: он открывает консоль с выводом ошибок.

## Автозапуск при входе в Windows

```bat
autostart.bat
```

Создаёт ярлык в папке автозагрузки (`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`). Чтобы отключить — удалите файл `WorkTimer.lnk` из этой папки.

## Сборка .exe / установщика

Готовые файлы для сборки `.exe` и Windows-инсталлятора находятся в [`../Release/windows`](../Release/windows).

## Структура

```
Win/
├── timer.py          — приложение (порт на tkinter)
├── db_backend.py     — доступ к БД (Supabase REST или прямой PostgreSQL) и автомиграции
├── sql/migrations/   — файлы миграций (копия корневых, применяются автоматически)
├── requirements.txt   — зависимости
├── .env.example       — шаблон конфигурации
├── install.bat        — установка venv + зависимостей
├── run.bat            — запуск без консоли
├── run_debug.bat       — запуск с консолью (для отладки)
└── autostart.bat      — настройка автозапуска
```
