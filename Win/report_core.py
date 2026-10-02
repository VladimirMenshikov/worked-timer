"""Общая логика подсчёта времени сессий — без UI и зависимостей от платформы.

Используется и треем (статистика, .md-отчёт), и локальным веб-интерфейсом.
"""

import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional


def parse_dt(value) -> datetime:
    """Разбирает timestamptz из Supabase/PostgreSQL.

    datetime.fromisoformat в Python 3.10 (Linux Mint 21) не понимает дробную
    часть секунд не из 3/6 цифр (Supabase отдаёт, например, '.12345'), 'Z'
    и короткое смещение '+00' — приводим строку к канонической форме.
    """
    if isinstance(value, datetime):
        return value
    s = str(value).strip().replace("Z", "+00:00")
    s = re.sub(r"\.(\d+)", lambda m: "." + m.group(1)[:6].ljust(6, "0"), s, count=1)
    if re.search(r"[+-]\d\d$", s):
        s += ":00"
    return datetime.fromisoformat(s)


def format_elapsed(total_seconds: int) -> str:
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    if h > 0:
        return f"{h} час. {m} мин. {s} сек."
    if m > 0:
        return f"{m} мин. {s} сек."
    return f"{s} сек."


def session_state(events: list, now: datetime) -> tuple:
    """Состояние сессии по цепочке событий (start/pause/resume/stop).

    events — записи одной session_id по возрастанию event_time.
    Возвращает (elapsed_sec, status, segment_start): status ∈ 'running' |
    'paused' | 'stopped'; segment_start — начало текущего отрезка работы
    (только для 'running'). Паузы из затраченного времени вычитаются.
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
    return int(elapsed), status, segment_start


def session_status(events: list, now: datetime) -> tuple:
    elapsed, status, _ = session_state(events, now)
    return elapsed, status


def group_events(rows: list) -> dict:
    by_session = defaultdict(list)
    for r in rows:
        by_session[r["session_id"]].append({
            "operation": r["operation"],
            "event_time": parse_dt(r["event_time"]),
        })
    return by_session


def fetch_sessions(db, from_utc: datetime, to_utc: Optional[datetime] = None) -> list:
    """Сессии, начатые в [from_utc, to_utc), с итоговым временем и статусом."""
    starts = db.select_starts_since(from_utc, to_utc)
    if not starts:
        return []
    events_by_session = group_events(
        db.select_events_for_sessions([r["session_id"] for r in starts])
    )
    now_utc = datetime.now(timezone.utc)
    sessions = []
    for start in starts:
        events = events_by_session.get(start["session_id"], [])
        elapsed_sec, status = session_status(events, now_utc)
        last_stop = next((e for e in reversed(events) if e["operation"] == "stop"), None)
        sessions.append({
            "session_id": start["session_id"],
            "task": (start["task"] or "").strip(),
            "start_dt": parse_dt(start["event_time"]).astimezone(),
            "stop_dt": last_stop["event_time"].astimezone() if last_stop else None,
            "elapsed_sec": elapsed_sec,
            "status": status,
        })
    return sessions


def find_active_session(db, lookback_from_utc: datetime) -> Optional[dict]:
    """Последняя незавершённая (running/paused) сессия — для восстановления после перезапуска."""
    starts = db.select_starts_since(lookback_from_utc)
    if not starts:
        return None
    events_by_session = group_events(
        db.select_events_for_sessions([r["session_id"] for r in starts])
    )
    now_utc = datetime.now(timezone.utc)
    for start in reversed(starts):
        events = events_by_session.get(start["session_id"], [])
        elapsed, status, segment_start = session_state(events, now_utc)
        if status in ("running", "paused"):
            return {
                "session_id": start["session_id"],
                "task": (start["task"] or "").strip(),
                "start_time": parse_dt(start["event_time"]),
                "status": status,
                "elapsed_sec": elapsed,
                "segment_start": segment_start,
            }
    return None
