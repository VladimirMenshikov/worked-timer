"""Уровень доступа к БД: Supabase (REST) или прямое подключение PostgreSQL.

Не содержит платформенного кода (никаких zenity/tkinter) — используется
без изменений и в Linux-, и в Windows-версии таймера.
"""

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

TABLE = "wh_work_log"
MIGRATIONS_DIR = Path(__file__).parent / "sql" / "migrations"


class SupabaseBackend:
    def __init__(self, url: str, key: str) -> None:
        from supabase import create_client
        self._client = create_client(url, key)

    def insert_event(self, row: dict) -> None:
        self._client.table(TABLE).insert(row).execute()

    def select_starts_since(self, from_dt_utc: datetime) -> list:
        res = (
            self._client.table(TABLE)
            .select("*")
            .eq("operation", "start")
            .gte("event_time", from_dt_utc.isoformat())
            .order("event_time")
            .execute()
        )
        return res.data

    def select_events_for_sessions(self, session_ids: list) -> list:
        if not session_ids:
            return []
        res = (
            self._client.table(TABLE)
            .select("*")
            .in_("session_id", session_ids)
            .order("event_time")
            .execute()
        )
        return res.data


def _row_to_dict(row) -> dict:
    """Приводит строку psycopg2 (RealDictRow) к тому же виду, что отдаёт Supabase REST."""
    d = dict(row)
    if d.get("session_id") is not None:
        d["session_id"] = str(d["session_id"])
    if isinstance(d.get("event_time"), datetime):
        d["event_time"] = d["event_time"].isoformat()
    return d


class PostgresBackend:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    @contextmanager
    def _connection(self):
        import psycopg2
        conn = psycopg2.connect(self._dsn)
        try:
            yield conn
        finally:
            conn.close()

    def insert_event(self, row: dict) -> None:
        cols = ", ".join(row.keys())
        placeholders = ", ".join(["%s"] * len(row))
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"INSERT INTO {TABLE} ({cols}) VALUES ({placeholders})",
                    list(row.values()),
                )
            conn.commit()

    def select_starts_since(self, from_dt_utc: datetime) -> list:
        import psycopg2.extras
        with self._connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    f"SELECT * FROM {TABLE} WHERE operation = 'start' "
                    "AND event_time >= %s ORDER BY event_time",
                    (from_dt_utc,),
                )
                rows = cur.fetchall()
        return [_row_to_dict(r) for r in rows]

    def select_events_for_sessions(self, session_ids: list) -> list:
        if not session_ids:
            return []
        import psycopg2.extras
        with self._connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    f"SELECT * FROM {TABLE} WHERE session_id = ANY(%s) "
                    "ORDER BY event_time",
                    (session_ids,),
                )
                rows = cur.fetchall()
        return [_row_to_dict(r) for r in rows]


def create_backend(env: dict):
    """env — os.environ или совместимый dict с DB_BACKEND и данными подключения."""
    backend = (env.get("DB_BACKEND") or "").strip().lower()

    if backend == "postgres":
        dsn = env.get("DATABASE_URL", "")
        if not dsn:
            raise RuntimeError("DB_BACKEND=postgres, но DATABASE_URL не задан в .env")
        return PostgresBackend(dsn)

    if backend == "supabase":
        url = env.get("SUPABASE_URL", "")
        key = env.get("SUPABASE_KEY", "")
        if not url or not key:
            raise RuntimeError("DB_BACKEND=supabase, но SUPABASE_URL/SUPABASE_KEY не заданы в .env")
        return SupabaseBackend(url, key)

    raise RuntimeError(f"Неизвестный DB_BACKEND: {backend!r} (ожидается 'supabase' или 'postgres')")


def run_pending_migrations(dsn: str) -> list:
    """Применяет ещё не применённые файлы sql/migrations по порядку имён.

    Каждый файл миграции сам пишет отметку о себе в public.schema_migrations
    (см. соглашение проекта), поэтому источник истины о том, что уже
    применено — эта таблица, а не локальное состояние приложения.
    Возвращает список имён миграций, применённых в этом вызове.
    """
    import psycopg2

    applied = []
    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.schema_migrations')")
            has_tracking = cur.fetchone()[0] is not None
            already = set()
            if has_tracking:
                cur.execute("SELECT name FROM public.schema_migrations")
                already = {row[0] for row in cur.fetchall()}
        conn.commit()

        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            name = path.stem
            if name in already:
                continue
            sql = path.read_text(encoding="utf-8")
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
            applied.append(name)
    finally:
        conn.close()

    return applied
