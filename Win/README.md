# Work Timer — Windows

Windows-версия трей-таймера. Логика и структура данных в Supabase полностью совпадают с Linux-версией (см. корневой [README.md](../README.md), [GUIDE.md](../GUIDE.md) и [sql/migrations](../sql/migrations)) — это тот же таймер, адаптированный под платформу.

## Чем отличается от Linux-версии

Linux-версия использует системные утилиты Cinnamon/GTK (`zenity`, `notify-send`, `wmctrl`, AppIndicator), которых на Windows нет. В этой версии их заменяет `tkinter` — входит в стандартную поставку Python, отдельно ставить не нужно:

| Linux | Windows |
|---|---|
| `zenity --entry` (ввод задачи) | окно `tkinter` |
| `notify-send` (уведомления) | всплывающее окно `tkinter` в углу экрана |
| `zenity --text-info` (статистика) | окно `tkinter` со прокруткой |
| `zenity --file-selection` (сохранение отчёта) | стандартный диалог `tkinter.filedialog` |
| `wmctrl` (фокус окна) | не требуется — окна `tkinter` открываются поверх окон с фокусом |
| системный трей через AppIndicator | системный трей через `pystray` (win32-бэкенд) |
| `~/.config/work-timer/` | `%APPDATA%\WorkTimer\` |

Бизнес-логика (запуск/пауза/стоп, статистика, генерация `.md`-отчёта, работа с Supabase) — идентична Linux-версии, файл в файл.

## Установка

Требуется Python 3.10+ ([python.org](https://www.python.org/downloads/) — при установке отметьте **Add python.exe to PATH**).

```bat
install.bat
```

Скрипт создаст виртуальное окружение `.venv`, поставит зависимости из `requirements.txt` и скопирует `.env.example` в `.env`.

Откройте `.env` и укажите те же `SUPABASE_URL` и `SUPABASE_KEY`, что и в Linux-версии (таблица `wh_work_log` общая).

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
├── requirements.txt   — зависимости
├── .env.example       — шаблон конфигурации
├── install.bat        — установка venv + зависимостей
├── run.bat            — запуск без консоли
├── run_debug.bat       — запуск с консолью (для отладки)
└── autostart.bat      — настройка автозапуска
```
