#!/usr/bin/env python3
"""Work time tracker — system tray timer with Supabase logging (Windows build)."""

import os
import sys
import threading
import uuid
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import tkinter as tk
from tkinter import messagebox, filedialog, scrolledtext

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

# На Windows конфиг хранится в %APPDATA%, а не в ~/.config
CONFIG_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "WorkTimer"
LAST_PATH_FILE = CONFIG_DIR / "last_report_path.txt"

import pystray
from PIL import Image, ImageDraw
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

TABLE = "wh_work_log"


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


def ask_task() -> Optional[str]:
    """Открывает диалог ввода задачи (замена zenity --entry)."""
    result = {"value": None}

    root = tk.Tk()
    root.title("Work Timer — новая задача")
    root.attributes("-topmost", True)
    root.resizable(False, False)

    def on_ok(event=None):
        result["value"] = entry.get().strip() or None
        root.destroy()

    def on_cancel(event=None):
        root.destroy()

    tk.Label(root, text="Какую задачу вы сейчас решаете?", padx=16, pady=(16, 8)).pack()
    entry = tk.Entry(root, width=50, font=("Segoe UI", 10))
    entry.pack(padx=16, pady=(0, 12))

    btns = tk.Frame(root)
    btns.pack(pady=(0, 16))
    tk.Button(btns, text="OK", width=10, command=on_ok).pack(side="left", padx=6)
    tk.Button(btns, text="Отмена", width=10, command=on_cancel).pack(side="left", padx=6)

    root.bind("<Return>", on_ok)
    root.bind("<Escape>", on_cancel)
    root.protocol("WM_DELETE_WINDOW", on_cancel)

    root.update_idletasks()
    w, h = root.winfo_width(), root.winfo_height()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")

    entry.focus_force()
    root.mainloop()
    return result["value"]


def notify(title: str, body: str) -> None:
    """Всплывающее уведомление (замена notify-send) — не блокирует вызывающий поток."""

    def _show() -> None:
        root = tk.Tk()
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        try:
            root.attributes("-alpha", 0.95)
        except tk.TclError:
            pass

        frame = tk.Frame(root, bg="#1e1e1e", padx=14, pady=10)
        frame.pack()
        tk.Label(
            frame, text=title, bg="#1e1e1e", fg="white",
            font=("Segoe UI", 10, "bold"), anchor="w", justify="left",
        ).pack(fill="x")
        tk.Label(
            frame, text=body, bg="#1e1e1e", fg="#dddddd",
            font=("Segoe UI", 9), anchor="w", justify="left", wraplength=320,
        ).pack(fill="x", pady=(4, 0))

        root.update_idletasks()
        w, h = root.winfo_width(), root.winfo_height()
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        margin = 16
        root.geometry(f"+{sw - w - margin}+{sh - h - margin - 48}")

        root.after(4000, root.destroy)
        root.mainloop()

    threading.Thread(target=_show, daemon=True).start()


def _show_text_window(title: str, text: str, width: int = 780, height: int = 420) -> None:
    """Окно с моноширинным текстом (замена zenity --text-info)."""
    root = tk.Tk()
    root.title(title)
    root.attributes("-topmost", True)
    root.geometry(f"{width}x{height}")

    txt = scrolledtext.ScrolledText(root, font=("Consolas", 10), wrap="none")
    txt.pack(fill="both", expand=True, padx=8, pady=8)
    txt.insert("1.0", text)
    txt.configure(state="disabled")

    tk.Button(root, text="Закрыть", width=12, command=root.destroy).pack(pady=(0, 10))
    root.mainloop()


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

        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_KEY", "")
        if not url or not key:
            self._fatal("Не заданы SUPABASE_URL и/или SUPABASE_KEY в файле .env")
        self._db = create_client(url, key)

    @staticmethod
    def _fatal(msg: str) -> None:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        messagebox.showerror("Work Timer", msg, parent=root)
        root.destroy()
        sys.exit(1)

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

            self._db.table(TABLE).insert({
                "session_id": session_id,
                "operation": "start",
                "task": task,
                "event_time": now.isoformat(),
            }).execute()

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

            self._db.table(TABLE).insert({
                "session_id": session_id,
                "operation": "stop",
                "task": task,
                "event_time": now.isoformat(),
                "elapsed_time": elapsed_str,
            }).execute()

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

            self._db.table(TABLE).insert({
                "session_id": session_id,
                "operation": "pause",
                "task": task,
                "event_time": now.isoformat(),
            }).execute()

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

            self._db.table(TABLE).insert({
                "session_id": session_id,
                "operation": "resume",
                "task": task,
                "event_time": now.isoformat(),
            }).execute()

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
            starts_res = (
                self._db.table(TABLE)
                .select("*")
                .eq("operation", "start")
                .gte("event_time", today_start_utc.isoformat())
                .order("event_time")
                .execute()
            )
        except Exception as exc:
            notify("Ошибка статистики", str(exc))
            return

        if not starts_res.data:
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            messagebox.showinfo("Статистика", "Сегодня нет записей.", parent=root)
            root.destroy()
            return

        session_ids = [r["session_id"] for r in starts_res.data]
        try:
            all_res = (
                self._db.table(TABLE)
                .select("*")
                .in_("session_id", session_ids)
                .order("event_time")
                .execute()
            )
        except Exception as exc:
            notify("Ошибка статистики", str(exc))
            return

        events_by_session = defaultdict(list)
        for r in all_res.data:
            events_by_session[r["session_id"]].append({
                "operation": r["operation"],
                "event_time": datetime.fromisoformat(r["event_time"]),
            })

        now_utc = datetime.now(timezone.utc)
        rows = []
        total_sec = 0

        for start in starts_res.data:
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

        _show_text_window("Статистика за сегодня", text)

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
        initial_dir = str(Path(last).parent) if last else str(Path.home())

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.asksaveasfilename(
            parent=root,
            title="Сохранить отчёт",
            initialdir=initial_dir,
            initialfile=default_filename,
            defaultextension=".md",
            filetypes=[("Markdown", "*.md"), ("Все файлы", "*.*")],
        )
        root.destroy()

        if not path:
            return None
        if not path.endswith(".md"):
            path += ".md"
        return path

    def _fetch_sessions_since(self, from_dt_utc: datetime) -> list:
        starts_res = (
            self._db.table(TABLE)
            .select("*")
            .eq("operation", "start")
            .gte("event_time", from_dt_utc.isoformat())
            .order("event_time")
            .execute()
        )
        if not starts_res.data:
            return []

        session_ids = [r["session_id"] for r in starts_res.data]
        all_res = (
            self._db.table(TABLE)
            .select("*")
            .in_("session_id", session_ids)
            .order("event_time")
            .execute()
        )

        events_by_session = defaultdict(list)
        for r in all_res.data:
            events_by_session[r["session_id"]].append({
                "operation": r["operation"],
                "event_time": datetime.fromisoformat(r["event_time"]),
            })

        now_utc = datetime.now(timezone.utc)
        sessions = []
        for start in starts_res.data:
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


if __name__ == "__main__":
    WorkTimer().run()
