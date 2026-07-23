#!/usr/bin/env python3
"""Work time tracker — system tray timer with Supabase logging."""

import os
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

MONTHS_RU = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
}
MONTHS_NOM_RU = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
    5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
    9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь",
}
DAYS_RU = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]

CONFIG_DIR = Path.home() / ".config" / "work-timer"
LAST_PATH_FILE = CONFIG_DIR / "last_report_path.txt"

import pystray
from PIL import Image, ImageDraw
from dotenv import load_dotenv, set_key

import db_backend

ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(ENV_PATH)


def _make_icon(r: int, g: int, b: int, size: int = 64) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    pad = 5
    draw.ellipse([pad, pad, size - pad, size - pad], fill=(r, g, b, 255))
    return img


ICON_IDLE    = _make_icon(55, 185, 55)    # зелёный — ожидание
ICON_RUNNING = _make_icon(215, 45, 45)   # красный — таймер работает
ICON_PAUSED  = _make_icon(230, 165, 20)  # жёлтый — таймер на паузе


def format_elapsed(total_seconds: int) -> str:
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    if h > 0:
        return f"{h} час. {m} мин. {s} сек."
    if m > 0:
        return f"{m} мин. {s} сек."
    return f"{s} сек."


def _session_status(events: list, now: datetime) -> tuple:
    """Считает суммарное активное время сессии по цепочке событий.

    events — записи одной session_id, отсортированные по event_time
    (operation ∈ start/pause/resume/stop). Паузы вычитаются из
    затраченного времени. Возвращает (elapsed_sec, status), где
    status ∈ 'running' | 'paused' | 'stopped'.
    """
    segment_start = None
    elapsed = 0.0
    status = "stopped"
    for ev in events:
        op = ev["operation"]
        t = ev["event_time"]
        if op in ("start", "resume"):
            segment_start = t
        elif op in ("pause", "stop"):
            if segment_start is not None:
                elapsed += (t - segment_start).total_seconds()
                segment_start = None
            status = "paused" if op == "pause" else "stopped"
    if segment_start is not None:
        elapsed += (now - segment_start).total_seconds()
        status = "running"
    return int(elapsed), status


def _zenity_env() -> dict:
    """Окружение для запуска zenity в обход сломанного сокета IBus.

    После очистки ~/.cache/ibus демон IBus остаётся запущен, но его
    unix-сокет исчезает — GTK-приложения пытаются подключиться к нему и
    не получают вообще никакого ввода с клавиатуры (ни печать, ни Ctrl+V).
    Принудительный gtk-im-context-simple не зависит от IBus.
    """
    env = os.environ.copy()
    env["GTK_IM_MODULE"] = "gtk-im-context-simple"
    return env


def _focus_window(title: str, timeout: float = 2.0) -> None:
    """Принудительно активирует окно по заголовку.

    Диалоги zenity, запущенные из фонового потока трея, не получают фокус
    из-за защиты от перехвата фокуса в Cinnamon/Mutter: окно видно, но
    поле ввода не реагирует на клавиатуру, пока фокус не передан вручную.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        found = subprocess.run(["wmctrl", "-l"], capture_output=True, text=True)
        if title in found.stdout:
            subprocess.run(["wmctrl", "-a", title], capture_output=True)
            return
        time.sleep(0.1)


def ask_task() -> Optional[str]:
    """Открывает диалог zenity для ввода задачи."""
    title = "Work Timer — новая задача"
    proc = subprocess.Popen(
        [
            "zenity", "--entry",
            f"--title={title}",
            "--text=Какую задачу вы сейчас решаете?",
            "--width=480",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        env=_zenity_env(),
    )
    _focus_window(title)
    stdout, _ = proc.communicate()
    if proc.returncode == 0:
        return stdout.strip() or None
    return None


def notify(title: str, body: str) -> None:
    subprocess.run(
        ["notify-send", "--urgency=low", "--icon=appointment-soon", title, body],
        capture_output=True,
    )


def fatal_error(msg: str) -> None:
    subprocess.run(
        ["zenity", "--error", "--title=Work Timer", f"--text={msg}", "--width=400"],
        capture_output=True,
        env=_zenity_env(),
    )
    sys.exit(1)


def _needs_db_setup() -> bool:
    backend = os.environ.get("DB_BACKEND", "").strip().lower()

    if backend not in ("supabase", "postgres"):
        # Обратная совместимость: .env уже содержит рабочие Supabase-креды
        # из версии приложения до появления DB_BACKEND — не переспрашиваем.
        if os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_KEY"):
            set_key(ENV_PATH, "DB_BACKEND", "supabase")
            load_dotenv(ENV_PATH, override=True)
            return False
        return True

    if backend == "supabase":
        return not (os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_KEY"))
    return not os.environ.get("DATABASE_URL")


def run_setup_wizard() -> None:
    """Мастер первого запуска: выбор Supabase или PostgreSQL, ввод реквизитов в .env."""
    choice = subprocess.run(
        [
            "zenity", "--list", "--radiolist",
            "--title=Work Timer — настройка подключения к БД",
            "--text=Выберите способ подключения к базе данных:",
            "--column=", "--column=Вариант",
            "--print-column=2", "--hide-header",
            "TRUE", "Supabase",
            "FALSE", "PostgreSQL (прямое подключение)",
            "--width=460", "--height=220",
        ],
        capture_output=True, text=True, env=_zenity_env(),
    )
    label = choice.stdout.strip()
    if choice.returncode != 0 or not label:
        fatal_error("Настройка БД не завершена — подключение не задано.")

    if label.startswith("Supabase"):
        form = subprocess.run(
            [
                "zenity", "--forms",
                "--title=Work Timer — Supabase",
                "--text=Данные подключения Supabase (Project Settings → API)",
                "--add-entry=SUPABASE_URL",
                "--add-entry=SUPABASE_KEY (anon key)",
                "--add-entry=DATABASE_URL (необязательно — для автомиграций, Project Settings → Database)",
                "--width=560",
            ],
            capture_output=True, text=True, env=_zenity_env(),
        )
        if form.returncode != 0:
            fatal_error("Настройка БД не завершена.")
        parts = (form.stdout.rstrip("\n").split("|") + ["", "", ""])[:3]
        url, key, dsn = (p.strip() for p in parts)
        if not url or not key:
            fatal_error("SUPABASE_URL и SUPABASE_KEY обязательны.")
        set_key(ENV_PATH, "DB_BACKEND", "supabase")
        set_key(ENV_PATH, "SUPABASE_URL", url)
        set_key(ENV_PATH, "SUPABASE_KEY", key)
        if dsn:
            set_key(ENV_PATH, "DATABASE_URL", dsn)
    else:
        form = subprocess.run(
            [
                "zenity", "--forms",
                "--title=Work Timer — PostgreSQL",
                "--text=Строка подключения PostgreSQL",
                "--add-entry=DATABASE_URL (postgresql://user:password@host:port/dbname)",
                "--width=560",
            ],
            capture_output=True, text=True, env=_zenity_env(),
        )
        if form.returncode != 0:
            fatal_error("Настройка БД не завершена.")
        dsn = form.stdout.strip()
        if not dsn:
            fatal_error("DATABASE_URL обязателен.")
        set_key(ENV_PATH, "DB_BACKEND", "postgres")
        set_key(ENV_PATH, "DATABASE_URL", dsn)

    load_dotenv(ENV_PATH, override=True)


class WorkTimer:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.running = False
        self.paused = False
        self.start_time: Optional[datetime] = None
        self.segment_start: Optional[datetime] = None
        self.accumulated_sec = 0.0
        self.task: Optional[str] = None
        self.session_id: Optional[str] = None
        self._busy = False

        try:
            self._db = db_backend.create_backend(os.environ)
        except RuntimeError as exc:
            fatal_error(str(exc))

    # ------------------------------------------------------------------ меню

    def _menu_items(self):
        if self.running:
            yield pystray.MenuItem(self.task or "...", None, enabled=False)
            if self.paused:
                yield pystray.MenuItem("▶  Продолжить", self._resume_action, default=True)
            else:
                yield pystray.MenuItem("⏸  Пауза", self._pause_action, default=True)
            yield pystray.MenuItem("⏹  Остановить таймер", self._stop_action)
        else:
            yield pystray.MenuItem("▶  Запустить таймер", self._start_action, default=True)
        yield pystray.MenuItem("📊  Статистика за сегодня", self._stats_action)
        yield pystray.MenuItem("📄  Сохранить отчёт (.md)", self._report_action)
        yield pystray.Menu.SEPARATOR
        yield pystray.MenuItem("Выход", lambda icon, _: icon.stop())

    # ---------------------------------------------------------------- хэндлеры

    def _start_action(self, icon: pystray.Icon, _) -> None:
        threading.Thread(target=self._do_start, args=(icon,), daemon=True).start()

    def _stop_action(self, icon: pystray.Icon, _) -> None:
        threading.Thread(target=self._do_stop, args=(icon,), daemon=True).start()

    def _pause_action(self, icon: pystray.Icon, _) -> None:
        threading.Thread(target=self._do_pause, args=(icon,), daemon=True).start()

    def _resume_action(self, icon: pystray.Icon, _) -> None:
        threading.Thread(target=self._do_resume, args=(icon,), daemon=True).start()

    def _stats_action(self, icon: pystray.Icon, _) -> None:
        threading.Thread(target=self._do_show_stats, daemon=True).start()

    def _report_action(self, icon: pystray.Icon, _) -> None:
        threading.Thread(target=self._do_generate_report, daemon=True).start()

    def _do_start(self, icon: pystray.Icon) -> None:
        with self._lock:
            if self.running or self._busy:
                return
            self._busy = True

        try:
            task = ask_task()
            if not task:
                return

            session_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)

            self._db.insert_event({
                "session_id": session_id,
                "operation": "start",
                "task": task,
                "event_time": now.isoformat(),
            })

            with self._lock:
                self.running = True
                self.paused = False
                self.start_time = now
                self.segment_start = now
                self.accumulated_sec = 0.0
                self.task = task
                self.session_id = session_id

            icon.icon = ICON_RUNNING
            icon.title = f"▶ {task}"
            icon.update_menu()
            notify("Таймер запущен", f"Задача: {task}")

        except Exception as exc:
            notify("Ошибка Work Timer", str(exc))
        finally:
            with self._lock:
                self._busy = False

    def _do_stop(self, icon: pystray.Icon) -> None:
        with self._lock:
            if not self.running or self._busy:
                return
            self._busy = True
            # захватываем значения пока держим лок
            task = self.task
            session_id = self.session_id
            segment_start = self.segment_start
            accumulated_sec = self.accumulated_sec

        try:
            now = datetime.now(timezone.utc)
            if segment_start is not None:
                accumulated_sec += (now - segment_start).total_seconds()
            elapsed_sec = int(accumulated_sec)
            elapsed_str = format_elapsed(elapsed_sec)

            self._db.insert_event({
                "session_id": session_id,
                "operation": "stop",
                "task": task,
                "event_time": now.isoformat(),
                "elapsed_time": elapsed_str,
            })

            with self._lock:
                self.running = False
                self.paused = False
                self.start_time = None
                self.segment_start = None
                self.accumulated_sec = 0.0
                self.task = None
                self.session_id = None

            icon.icon = ICON_IDLE
            icon.title = "Work Timer"
            icon.update_menu()
            notify("Таймер остановлен", f"Задача: {task}\nЗатрачено: {elapsed_str}")

        except Exception as exc:
            notify("Ошибка Work Timer", str(exc))
        finally:
            with self._lock:
                self._busy = False

    def _do_pause(self, icon: pystray.Icon) -> None:
        with self._lock:
            if not self.running or self.paused or self._busy:
                return
            self._busy = True
            task = self.task
            session_id = self.session_id
            segment_start = self.segment_start

        try:
            now = datetime.now(timezone.utc)
            accumulated_sec = self.accumulated_sec
            if segment_start is not None:
                accumulated_sec += (now - segment_start).total_seconds()

            self._db.insert_event({
                "session_id": session_id,
                "operation": "pause",
                "task": task,
                "event_time": now.isoformat(),
            })

            with self._lock:
                self.paused = True
                self.segment_start = None
                self.accumulated_sec = accumulated_sec

            icon.icon = ICON_PAUSED
            icon.title = f"⏸ {task}"
            icon.update_menu()
            notify("Таймер на паузе", f"Задача: {task}")

        except Exception as exc:
            notify("Ошибка Work Timer", str(exc))
        finally:
            with self._lock:
                self._busy = False

    def _do_resume(self, icon: pystray.Icon) -> None:
        with self._lock:
            if not self.running or not self.paused or self._busy:
                return
            self._busy = True
            task = self.task
            session_id = self.session_id

        try:
            now = datetime.now(timezone.utc)

            self._db.insert_event({
                "session_id": session_id,
                "operation": "resume",
                "task": task,
                "event_time": now.isoformat(),
            })

            with self._lock:
                self.paused = False
                self.segment_start = now

            icon.icon = ICON_RUNNING
            icon.title = f"▶ {task}"
            icon.update_menu()
            notify("Таймер продолжен", f"Задача: {task}")

        except Exception as exc:
            notify("Ошибка Work Timer", str(exc))
        finally:
            with self._lock:
                self._busy = False

    # ---------------------------------------------------------------- статистика

    def _do_show_stats(self) -> None:
        now_local = datetime.now()
        today_start_utc = (
            now_local.replace(hour=0, minute=0, second=0, microsecond=0)
            .astimezone(timezone.utc)
        )

        try:
            starts = self._db.select_starts_since(today_start_utc)
        except Exception as exc:
            notify("Ошибка статистики", str(exc))
            return

        if not starts:
            subprocess.run(
                ["zenity", "--info", "--title=Статистика",
                 "--text=Сегодня нет записей.", "--width=300"],
                capture_output=True,
                env=_zenity_env(),
            )
            return

        session_ids = [r["session_id"] for r in starts]
        try:
            all_events = self._db.select_events_for_sessions(session_ids)
        except Exception as exc:
            notify("Ошибка статистики", str(exc))
            return

        events_by_session = defaultdict(list)
        for r in all_events:
            events_by_session[r["session_id"]].append({
                "operation": r["operation"],
                "event_time": datetime.fromisoformat(r["event_time"]),
            })

        now_utc = datetime.now(timezone.utc)
        rows = []
        total_sec = 0

        for start in starts:
            sid = start["session_id"]
            task = (start["task"] or "").strip()
            start_dt = datetime.fromisoformat(start["event_time"])
            start_str = start_dt.astimezone().strftime("%H:%M:%S")

            events = events_by_session.get(sid, [])
            elapsed_sec, status = _session_status(events, now_utc)
            total_sec += elapsed_sec

            if status == "running":
                elapsed_str = f"▶ {format_elapsed(elapsed_sec)}"
                stop_str = "▶"
            elif status == "paused":
                elapsed_str = f"⏸ {format_elapsed(elapsed_sec)}"
                stop_str = "⏸"
            else:
                elapsed_str = format_elapsed(elapsed_sec)
                last_stop = next(
                    (e for e in reversed(events) if e["operation"] == "stop"), None
                )
                stop_str = (
                    last_stop["event_time"].astimezone().strftime("%H:%M:%S")
                    if last_stop else "—"
                )

            rows.append((task, start_str, stop_str, elapsed_str))

        task_w = max((len(r[0]) for r in rows), default=5)
        task_w = max(task_w, 10)

        col_task    = f"{'Задача':<{task_w}}"
        col_headers = f"  {col_task}  {'Начало':^10}  {'Конец':^10}  Затрачено"
        sep         = "  " + "─" * (task_w + 36)

        body = [
            f"  {task:<{task_w}}  {s:^10}  {e:^10}  {el}"
            for task, s, e, el in rows
        ]
        total_str = format_elapsed(total_sec) if total_sec else "—"
        total_row = f"  {'ИТОГО':<{task_w}}  {'':^10}  {'':^10}  {total_str}"

        date_str = f"{now_local.day} {MONTHS_RU[now_local.month]} {now_local.year}"
        text = "\n".join([
            f"  Статистика за {date_str}",
            "",
            col_headers,
            sep,
            *body,
            sep,
            total_row,
            "",
        ])

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write(text)
            tmp_path = f.name

        try:
            subprocess.run(
                [
                    "zenity", "--text-info",
                    "--title=Статистика за сегодня",
                    f"--filename={tmp_path}",
                    "--width=780", "--height=420",
                    "--ok-label=Закрыть",
                ],
                capture_output=True,
                env=_zenity_env(),
            )
        finally:
            os.unlink(tmp_path)

    # --------------------------------------------------------------- отчёт .md

    def _load_last_report_path(self) -> Optional[str]:
        if LAST_PATH_FILE.exists():
            return LAST_PATH_FILE.read_text(encoding="utf-8").strip() or None
        return None

    def _save_last_report_path(self, path: str) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        LAST_PATH_FILE.write_text(path, encoding="utf-8")

    def _ask_save_path(self, default_filename: str) -> Optional[str]:
        last = self._load_last_report_path()
        if last:
            default = str(Path(last).parent / default_filename)
        else:
            default = str(Path.home() / default_filename)

        proc = subprocess.run(
            [
                "zenity", "--file-selection", "--save", "--confirm-overwrite",
                f"--filename={default}",
                "--title=Сохранить отчёт",
            ],
            capture_output=True,
            text=True,
            env=_zenity_env(),
        )
        if proc.returncode != 0:
            return None
        path = proc.stdout.strip()
        if not path:
            return None
        if not path.endswith(".md"):
            path += ".md"
        return path

    def _fetch_sessions_since(self, from_dt_utc: datetime) -> list:
        starts = self._db.select_starts_since(from_dt_utc)
        if not starts:
            return []

        session_ids = [r["session_id"] for r in starts]
        all_events = self._db.select_events_for_sessions(session_ids)

        events_by_session = defaultdict(list)
        for r in all_events:
            events_by_session[r["session_id"]].append({
                "operation": r["operation"],
                "event_time": datetime.fromisoformat(r["event_time"]),
            })

        now_utc = datetime.now(timezone.utc)
        sessions = []
        for start in starts:
            sid = start["session_id"]
            task = (start["task"] or "").strip()
            start_dt = datetime.fromisoformat(start["event_time"]).astimezone()

            events = events_by_session.get(sid, [])
            elapsed_sec, status = _session_status(events, now_utc)
            last_stop = next(
                (e for e in reversed(events) if e["operation"] == "stop"), None
            )
            stop_dt = last_stop["event_time"].astimezone() if last_stop else None

            sessions.append({
                "task": task,
                "start_dt": start_dt,
                "stop_dt": stop_dt,
                "elapsed_sec": elapsed_sec,
                "status": status,
            })

        return sessions

    def _render_report_section(self, title: str, date_range: list, sessions: list) -> str:
        by_day: dict = defaultdict(list)
        for s in sessions:
            by_day[s["start_dt"].date()].append(s)

        lines = [f"## {title}", ""]
        section_total = 0

        for d in date_range:
            day_sessions = by_day.get(d, [])
            day_name = DAYS_RU[d.weekday()]
            day_label = f"{d.day} {MONTHS_RU[d.month]}"
            lines.append(f"### {day_name}, {day_label}")
            lines.append("")

            if not day_sessions:
                lines.append("*Нет записей*")
                lines.append("")
                continue

            lines.append("| Задача | Начало | Конец | Затрачено |")
            lines.append("|--------|:------:|:-----:|----------:|")

            day_total = 0
            for s in day_sessions:
                start_str = s["start_dt"].strftime("%H:%M")
                if s["status"] == "running":
                    stop_str = "▶"
                elif s["status"] == "paused":
                    stop_str = "⏸"
                elif s["stop_dt"]:
                    stop_str = s["stop_dt"].strftime("%H:%M")
                else:
                    stop_str = "—"

                elapsed = format_elapsed(s["elapsed_sec"])
                if s["status"] == "running":
                    elapsed = f"▶ {elapsed}"
                elif s["status"] == "paused":
                    elapsed = f"⏸ {elapsed}"
                day_total += s["elapsed_sec"]

                task = s["task"].replace("|", "\\|") or "—"
                lines.append(f"| {task} | {start_str} | {stop_str} | {elapsed} |")

            section_total += day_total
            lines.append("")
            lines.append(f"**Итого за день: {format_elapsed(day_total)}**")
            lines.append("")

        total_str = format_elapsed(section_total) if section_total else "—"
        lines.append(f"**Итого за период: {total_str}**")
        lines.append("")
        return "\n".join(lines)

    def _render_report_md(self, now_local: datetime, week_sessions: list, month_sessions: list) -> str:
        today = now_local.date()

        week_start = today - timedelta(days=today.weekday())
        week_dates = [week_start + timedelta(days=i) for i in range((today - week_start).days + 1)]

        month_start = today.replace(day=1)
        month_dates = [month_start + timedelta(days=i) for i in range((today - month_start).days + 1)]

        date_str = f"{today.day} {MONTHS_RU[today.month]} {today.year}"

        week_start_label = f"{week_start.day} {MONTHS_RU[week_start.month]}"
        week_end_label = f"{today.day} {MONTHS_RU[today.month]} {today.year}"
        week_title = f"Неделя: {week_start_label} — {week_end_label}"

        month_title = f"Месяц: {MONTHS_NOM_RU[today.month]} {today.year}"

        lines = [
            "# Отчёт по рабочему времени",
            "",
            f"Сформирован: {date_str}",
            "",
            "---",
            "",
            self._render_report_section(week_title, week_dates, week_sessions),
            "---",
            "",
            self._render_report_section(month_title, month_dates, month_sessions),
        ]
        return "\n".join(lines)

    def _do_generate_report(self) -> None:
        now_local = datetime.now()
        today = now_local.date()

        week_start = today - timedelta(days=today.weekday())
        week_start_utc = datetime(
            week_start.year, week_start.month, week_start.day,
            0, 0, 0,
        ).astimezone(timezone.utc)

        month_start = today.replace(day=1)
        month_start_utc = datetime(
            month_start.year, month_start.month, month_start.day,
            0, 0, 0,
        ).astimezone(timezone.utc)

        try:
            week_sessions = self._fetch_sessions_since(week_start_utc)
            month_sessions = self._fetch_sessions_since(month_start_utc)
        except Exception as exc:
            notify("Ошибка отчёта", str(exc))
            return

        default_filename = f"work_report_{today.strftime('%Y-%m-%d')}.md"
        path = self._ask_save_path(default_filename)
        if not path:
            return

        report = self._render_report_md(now_local, week_sessions, month_sessions)
        try:
            Path(path).write_text(report, encoding="utf-8")
            self._save_last_report_path(path)
            notify("Отчёт сохранён", path)
        except Exception as exc:
            notify("Ошибка сохранения", str(exc))

    # --------------------------------------------------------------------- запуск

    def run(self) -> None:
        icon = pystray.Icon(
            name="work-timer",
            icon=ICON_IDLE,
            title="Work Timer",
            menu=pystray.Menu(self._menu_items),
        )
        icon.run()


def main() -> None:
    if _needs_db_setup():
        run_setup_wizard()

    dsn = os.environ.get("DATABASE_URL", "").strip()
    if dsn:
        try:
            applied = db_backend.run_pending_migrations(dsn)
        except Exception as exc:
            fatal_error(f"Не удалось применить миграции БД:\n{exc}")
            return
        if applied:
            notify("Миграции БД применены", ", ".join(applied))

    WorkTimer().run()


if __name__ == "__main__":
    main()
