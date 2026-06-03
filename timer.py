#!/usr/bin/env python3
"""Work time tracker — system tray timer with Supabase logging."""

import os
import subprocess
import sys
import tempfile
import threading
import uuid
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


def format_elapsed(total_seconds: int) -> str:
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    if h > 0:
        return f"{h} час. {m} мин. {s} сек."
    if m > 0:
        return f"{m} мин. {s} сек."
    return f"{s} сек."


def ask_task() -> Optional[str]:
    """Открывает диалог zenity для ввода задачи."""
    proc = subprocess.run(
        [
            "zenity", "--entry",
            "--title=Work Timer",
            "--text=Какую задачу вы сейчас решаете?",
            "--width=480",
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode == 0:
        return proc.stdout.strip() or None
    return None


def notify(title: str, body: str) -> None:
    subprocess.run(
        ["notify-send", "--urgency=low", "--icon=appointment-soon", title, body],
        capture_output=True,
    )


class WorkTimer:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.running = False
        self.start_time: Optional[datetime] = None
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
        subprocess.run(
            ["zenity", "--error", "--title=Work Timer", f"--text={msg}", "--width=400"],
            capture_output=True,
        )
        sys.exit(1)

    # ------------------------------------------------------------------ меню

    def _menu_items(self):
        if self.running:
            yield pystray.MenuItem(self.task or "...", None, enabled=False)
            yield pystray.MenuItem("⏹  Остановить таймер", self._stop_action, default=True)
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
                self.start_time = now
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
            start_time = self.start_time
            task = self.task
            session_id = self.session_id

        try:
            now = datetime.now(timezone.utc)
            elapsed_sec = int((now - start_time).total_seconds())
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
                self.start_time = None
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
            subprocess.run(
                ["zenity", "--info", "--title=Статистика",
                 "--text=Сегодня нет записей.", "--width=300"],
                capture_output=True,
            )
            return

        session_ids = [r["session_id"] for r in starts_res.data]
        try:
            stops_res = (
                self._db.table(TABLE)
                .select("*")
                .eq("operation", "stop")
                .in_("session_id", session_ids)
                .execute()
            )
        except Exception as exc:
            notify("Ошибка статистики", str(exc))
            return

        stops = {r["session_id"]: r for r in stops_res.data}

        rows = []
        total_sec = 0

        for start in starts_res.data:
            sid = start["session_id"]
            task = (start["task"] or "").strip()
            start_dt = datetime.fromisoformat(start["event_time"])
            start_str = start_dt.astimezone().strftime("%H:%M:%S")

            stop = stops.get(sid)
            if stop:
                stop_dt = datetime.fromisoformat(stop["event_time"])
                elapsed_sec = int((stop_dt - start_dt).total_seconds())
                total_sec += elapsed_sec
                elapsed_str = format_elapsed(elapsed_sec)
                stop_str = stop_dt.astimezone().strftime("%H:%M:%S")
            elif sid == self.session_id and self.start_time:
                cur_sec = int((datetime.now(timezone.utc) - self.start_time).total_seconds())
                total_sec += cur_sec
                elapsed_str = f"▶ {format_elapsed(cur_sec)}"
                stop_str = "—"
            else:
                elapsed_str = "?"
                stop_str = "—"

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
        stops_res = (
            self._db.table(TABLE)
            .select("*")
            .eq("operation", "stop")
            .in_("session_id", session_ids)
            .execute()
        )
        stops = {r["session_id"]: r for r in stops_res.data}

        sessions = []
        for start in starts_res.data:
            sid = start["session_id"]
            task = (start["task"] or "").strip()
            start_dt = datetime.fromisoformat(start["event_time"]).astimezone()
            stop = stops.get(sid)

            if stop:
                stop_dt = datetime.fromisoformat(stop["event_time"]).astimezone()
                elapsed_sec = int((stop_dt - start_dt).total_seconds())
                active = False
            elif sid == self.session_id and self.start_time is not None:
                stop_dt = None
                elapsed_sec = int((datetime.now(timezone.utc) - self.start_time).total_seconds())
                active = True
            else:
                stop_dt = None
                elapsed_sec = None
                active = False

            sessions.append({
                "task": task,
                "start_dt": start_dt,
                "stop_dt": stop_dt,
                "elapsed_sec": elapsed_sec,
                "active": active,
            })

        return sessions

    def _render_report_section(self, title: str, date_range: list, sessions: list) -> str:
        from collections import defaultdict
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
                if s["stop_dt"]:
                    stop_str = s["stop_dt"].strftime("%H:%M")
                elif s["active"]:
                    stop_str = "▶"
                else:
                    stop_str = "—"

                if s["elapsed_sec"] is not None:
                    elapsed = format_elapsed(s["elapsed_sec"])
                    if s["active"]:
                        elapsed = f"▶ {elapsed}"
                    day_total += s["elapsed_sec"]
                else:
                    elapsed = "?"

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
