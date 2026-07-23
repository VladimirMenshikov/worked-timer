# Work Timer — установка на Linux

Готовый `.deb`-пакет для Linux Mint / Ubuntu / Debian.

## Установка

```bash
sudo apt install ./work-timer_1.0.0_all.deb
```

(`apt install ./...` сам подтянет недостающие системные зависимости — `python3-gi`, `zenity`, `libnotify-bin`, `wmctrl` и т.д.; при установке через `dpkg -i` их придётся доустанавливать вручную через `apt -f install`.)

Пакет разворачивается в `/opt/work-timer` и во время установки (`postinst`):

1. создаёт виртуальное окружение `/opt/work-timer/.venv`;
2. ставит Python-зависимости из `requirements.txt`;
3. создаёт `/opt/work-timer/.env` из шаблона (если ещё не существует).

## Настройка после установки

1. Отредактируйте `/opt/work-timer/.env` — укажите `SUPABASE_URL` и `SUPABASE_KEY`:
   ```bash
   sudo nano /opt/work-timer/.env
   ```
2. Выполните SQL-миграции из `/opt/work-timer/sql/migrations` по порядку (0000 → далее) в Supabase → SQL Editor.
3. Запустите Work Timer через меню приложений (пункт «Work Timer») либо командой:
   ```bash
   /opt/work-timer/.venv/bin/python /opt/work-timer/timer.py
   ```
4. Автозапуск при входе в систему:
   ```bash
   bash /opt/work-timer/autostart.sh
   ```

## Обновление

Установите новую версию `.deb` тем же способом — `postinst` переиспользует существующий `.env`.

## Удаление

```bash
sudo apt remove work-timer      # оставит .env и venv
sudo apt purge work-timer       # удалит также .env, venv и автозапуск
```

## Пересборка пакета

Исходники пакета лежат в корне проекта. Скрипт [`build_deb.sh`](build_deb.sh) собирает `.deb` заново (например, после изменения `timer.py` или версии).

```bash
bash Release/linux/build_deb.sh
```

> Собирать нужно на обычной Linux-файловой системе (не на смонтированном Windows-разделе) — `dpkg-deb` требует реальных unix-прав на файлы пакета.
