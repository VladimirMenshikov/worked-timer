# Work Timer — сборка релиза для Windows

Здесь лежат скрипты, собирающие из [`../../Win`](../../Win) готовый `.exe` и установщик `Setup.exe`.

> **Важно:** сборку нужно запускать **на Windows**. PyInstaller собирает исполняемый файл только под ту ОС, на которой запущен (кросс-компиляция Windows-exe из Linux потребовала бы Wine + Windows-Python внутри него — ненадёжный путь), поэтому здесь только сами скрипты сборки, а не готовый бинарник.

## Требования

- Windows 10/11
- Python 3.10+ ([python.org](https://www.python.org/downloads/), отметить **Add python.exe to PATH**)
- [Inno Setup 6](https://jrsoftware.org/isdl.php) — только для сборки `Setup.exe` (шаг 2)

## Шаг 1 — собрать WorkTimer.exe

```bat
build_exe.bat
```

Скрипт создаёт временное окружение `build_venv`, ставит зависимости из `Win\requirements.txt` и `pyinstaller`, затем собирает `dist\WorkTimer.exe` по спецификации [`work-timer.spec`](work-timer.spec) (однофайловый exe без консоли, с иконкой из `assets\work-timer.ico`).

Результат: `dist\WorkTimer.exe` + `dist\.env.example` — этим можно пользоваться уже сейчас, просто скопировав папку `dist` на любой Windows-компьютер и заполнив `.env`.

## Шаг 2 — собрать установщик Setup.exe (необязательно)

```bat
build_installer.bat
```

Использует [Inno Setup](https://jrsoftware.org/isdl.php) и скрипт [`installer.iss`](installer.iss). Установщик:

- ставит приложение в `Program Files\WorkTimer`;
- создаёт ярлык в меню «Пуск»;
- по желанию пользователя — ярлык на рабочем столе и автозапуск при входе в Windows (флажки в мастере установки);
- не требует прав администратора (`PrivilegesRequired=lowest`).

Результат: `output\WorkTimerSetup-1.1.0.exe`.

## После установки

1. Запустите `WorkTimer.exe`.
2. При первом запуске появится мастер настройки — выберите Supabase или PostgreSQL и введите данные подключения (подробности — в [`../../Win/README.md`](../../Win/README.md#настройка-подключения-к-бд)). Они сохранятся в `.env` рядом с `WorkTimer.exe`.
3. Если указана строка подключения PostgreSQL (`DATABASE_URL`), таблицы создадутся автоматически — миграции (встроены в `WorkTimer.exe`) применяются при каждом запуске. Без неё выполните их вручную по порядку в Supabase → SQL Editor.
4. В трее появится зелёный кружок.

## Структура

```
Release/windows/
├── work-timer.spec       — спецификация PyInstaller
├── build_exe.bat         — сборка WorkTimer.exe
├── installer.iss         — скрипт Inno Setup
├── build_installer.bat   — сборка Setup.exe
├── assets/work-timer.ico — иконка приложения
├── dist/                 — результат build_exe.bat (появится после сборки)
└── output/               — результат build_installer.bat (появится после сборки)
```
