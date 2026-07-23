# Work Timer — инструкция пользователя

Приложение для учёта рабочего времени в Linux Mint. Живёт в системном трее, записывает сессии в Supabase.

---

## Быстрый старт

```bash
cd /путь/к/ai-worked-timer
.venv/bin/python timer.py
```

После запуска в правом нижнем углу экрана появится **зелёный кружок**.

---

## Использование

### Начать работу

1. Нажмите на **зелёный кружок** в трее
2. Выберите **▶ Запустить таймер**
3. Введите название задачи в диалоговом окне и нажмите **OK**

Кружок станет **красным** — таймер идёт. В базу запишется:

| Поле | Значение |
|---|---|
| `operation` | `start` |
| `task` | введённая задача |
| `event_time` | текущее время (UTC) |

### Поставить на паузу

1. Нажмите на **красный кружок** в трее
2. Выберите **⏸ Пауза**

Кружок станет **жёлтым**. Время на паузе не засчитывается в итог задачи. В базу запишется:

| Поле | Значение |
|---|---|
| `operation` | `pause` |
| `task` | название задачи |
| `event_time` | время постановки на паузу (UTC) |

Чтобы продолжить — нажмите на **жёлтый кружок** и выберите **▶ Продолжить**. В базу запишется событие `resume`, кружок снова станет **красным**.

### Завершить работу

1. Нажмите на **красный** (или **жёлтый**, если на паузе) кружок в трее
2. Выберите **⏹ Остановить таймер**

Остановить таймер можно и находясь на паузе — досрочный `resume` не требуется. Кружок снова станет **зелёным**. Появится уведомление с итогом. В базу запишется:

| Поле | Значение |
|---|---|
| `operation` | `stop` |
| `task` | название задачи |
| `event_time` | время остановки (UTC) |
| `elapsed_time` | затраченное время (без учёта пауз) |

### Формат затраченного времени

| Ситуация | Пример |
|---|---|
| Есть часы | `2 час. 5 мин. 10 сек.` |
| Только минуты | `35 мин. 6 сек.` |
| Только секунды | `48 сек.` |

### Завершить приложение

Нажмите на кружок → **Выход**.

---

## Структура проекта

```
ai-worked-timer/
├── timer.py          — основное приложение
├── .env              — данные подключения к Supabase
├── requirements.txt  — Python-зависимости
├── create_table.sql  — SQL для создания таблицы
├── install.sh        — установка зависимостей
├── autostart.sh      — настройка автозапуска
└── .venv/            — виртуальное окружение Python
```

---

## Установка с нуля

### 1. Системные зависимости

```bash
sudo apt install python3-gi python3-gi-cairo \
    gir1.2-ayatanaappindicator3-0.1 \
    libayatana-appindicator3-1 \
    libnotify-bin zenity wmctrl
```

### 2. Виртуальное окружение

```bash
/usr/bin/python3 -m venv .venv --system-site-packages
curl -sS https://bootstrap.pypa.io/get-pip.py | .venv/bin/python
.venv/bin/pip install -r requirements.txt
```

> **Важно:** используется системный `/usr/bin/python3`, а не pyenv.  
> Флаг `--system-site-packages` нужен для доступа к системному модулю `gi` (PyGObject).

### 3. Настройка Supabase

Заполните файл `.env`:

```env
SUPABASE_URL=https://ваш-проект.supabase.co
SUPABASE_KEY=ваш-anon-key
```

### 4. Создание таблицы

Выполните запрос из `create_table.sql` в **Supabase → SQL Editor**:

```sql
CREATE TABLE wh_work_log (
    id           BIGSERIAL    PRIMARY KEY,
    session_id   UUID         NOT NULL,
    operation    VARCHAR(6)   NOT NULL CHECK (operation IN ('start', 'pause', 'resume', 'stop')),
    task         TEXT,
    event_time   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    elapsed_time TEXT
);
```

---

## Автозапуск

Чтобы таймер запускался автоматически при входе в систему:

```bash
bash autostart.sh
```

Скрипт создаёт файл `~/.config/autostart/work-timer.desktop`. При следующем входе в Linux Mint таймер запустится сам.

Чтобы **отключить** автозапуск:

```bash
rm ~/.config/autostart/work-timer.desktop
```

---

## Структура данных в Supabase

Таблица `wh_work_log`. Каждая рабочая сессия — цепочка строк с одним `session_id`: `start`, затем ноль и более пар `pause`/`resume`, и в конце `stop`.

| Поле | Тип | Описание |
|---|---|---|
| `id` | bigserial | Первичный ключ |
| `session_id` | uuid | Связывает все события одной сессии |
| `operation` | varchar(6) | `start`, `pause`, `resume` или `stop` |
| `task` | text | Название задачи |
| `event_time` | timestamptz | Время события (UTC) |
| `elapsed_time` | text | Затраченное время без учёта пауз (только у `stop`) |

Пример запроса для просмотра завершённых сессий (итог уже без пауз, т.к. считается приложением при остановке):

```sql
SELECT
    s.task,
    s.event_time AS started_at,
    e.event_time AS stopped_at,
    e.elapsed_time
FROM wh_work_log s
JOIN wh_work_log e ON e.session_id = s.session_id AND e.operation = 'stop'
WHERE s.operation = 'start'
ORDER BY s.event_time DESC;
```

---

## Устранение неполадок

**Иконка не появляется в трее**

Убедитесь, что установлены AppIndicator-библиотеки:
```bash
dpkg -l | grep ayatana
```
Должна быть строка с `gir1.2-ayatanaappindicator3-0.1`.

**Ошибка подключения к Supabase**

Проверьте файл `.env` — URL и ключ должны быть без пробелов и кавычек.

**Диалог ввода задачи не появляется**

Убедитесь, что установлен `zenity`:
```bash
which zenity || sudo apt install zenity
```

**Диалог ввода задачи виден, но окно не получает фокус**

Это защита от перехвата фокуса в Cinnamon/Mutter: окно, открытое фоновым процессом трея, не активируется автоматически. Таймер сам активирует окно через `wmctrl` — убедитесь, что пакет установлен:
```bash
which wmctrl || sudo apt install wmctrl
```

**Диалог в фокусе, курсор в поле, но клавиатура и Ctrl+V не работают вообще**

Обычно это сломанный IBus: после очистки `~/.cache` демон `ibus-daemon` продолжает работать, но его unix-сокет (на который указывает `~/.config/ibus/bus/*`) исчезает, и GTK-приложения (включая zenity) не могут достучаться до input method — ввод не проходит совсем. Проверить:
```bash
cat ~/.config/ibus/bus/*        # смотрим путь IBUS_ADDRESS=unix:path=...
ls -la "$(echo $(cat ~/.config/ibus/bus/* | grep IBUS_ADDRESS | sed 's/.*path=\([^,]*\).*/\1/'))"
# если файла нет — сокет мёртв
```
Таймер обходит эту проблему, принудительно запуская zenity с `GTK_IM_MODULE=gtk-im-context-simple` (не зависит от IBus). Если проблема всё же проявляется в других приложениях, помогает перезапуск IBus:
```bash
ibus-daemon -drxR
```

**Уведомления не показываются**

```bash
sudo apt install libnotify-bin
```
