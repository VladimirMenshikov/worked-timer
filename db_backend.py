"""Уровень доступа к БД: Supabase (REST) или прямое подключение PostgreSQL.

Не содержит платформенного кода (никаких zenity/tkinter) — используется
без изменений и в Linux-, и в Windows-версии таймера.
"""

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

TABLE = "wh_work_log"
PLAN_TABLE = "wh_plan_work_hourses"
MIGRATIONS_DIR = Path(__file__).parent / "sql" / "migrations"


def _plan_row(r) -> dict:
    return {"year": int(r["year"]), "month": int(r["month"]),
            "work_days": int(r["work_days"]), "work_hours": float(r["work_hours"])}


class SupabaseBackend:
    def __init__(self, url: str, key: str) -> None:
        from supabase import create_client
        self._client = create_client(url, key)

    def insert_event(self, row: dict) -> None:
        self._client.table(TABLE).insert(row).execute()

    def select_starts_since(self, from_dt_utc: datetime, to_dt_utc: Optional[datetime] = None) -> list:
        query = (
            self._client.table(TABLE)
            .select("*")
            .eq("operation", "start")
            .gte("event_time", from_dt_utc.isoformat())
        )
        if to_dt_utc is not None:
            query = query.lt("event_time", to_dt_utc.isoformat())
        return query.order("event_time").execute().data

    def select_plan_hours(self, year: int, month: int) -> Optional[float]:
        res = (
            self._client.table(PLAN_TABLE)
            .select("work_hours")
            .eq("year", year)
            .eq("month", month)
            .execute()
        )
        return float(res.data[0]["work_hours"]) if res.data else None

    def select_plan_year(self, year: int) -> list:
        res = (
            self._client.table(PLAN_TABLE)
            .select("year,month,work_days,work_hours")
            .eq("year", year)
            .order("month")
            .execute()
        )
        return [_plan_row(r) for r in res.data]

    def upsert_plan_hours(self, rows: list) -> None:
        if rows:
            self._client.table(PLAN_TABLE).upsert(rows, on_conflict="year,month").execute()

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

    def select_starts_since(self, from_dt_utc: datetime, to_dt_utc: Optional[datetime] = None) -> list:
        import psycopg2.extras
        with self._connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    f"SELECT * FROM {TABLE} WHERE operation = 'start' "
                    "AND event_time >= %s AND (%s::timestamptz IS NULL OR event_time < %s) "
                    "ORDER BY event_time",
                    (from_dt_utc, to_dt_utc, to_dt_utc),
                )
                rows = cur.fetchall()
        return [_row_to_dict(r) for r in rows]

    def select_plan_hours(self, year: int, month: int) -> Optional[float]:
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT work_hours FROM {PLAN_TABLE} WHERE year = %s AND month = %s",
                    (year, month),
                )
                row = cur.fetchone()
        return float(row[0]) if row else None

    def select_plan_year(self, year: int) -> list:
        import psycopg2.extras
        with self._connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    f"SELECT year, month, work_days, work_hours FROM {PLAN_TABLE} "
                    "WHERE year = %s ORDER BY month",
                    (year,),
                )
                return [_plan_row(r) for r in cur.fetchall()]

    def upsert_plan_hours(self, rows: list) -> None:
        with self._connection() as conn:
            with conn.cursor() as cur:
                for r in rows:
                    cur.execute(
                        f"INSERT INTO {PLAN_TABLE} (year, month, work_days, work_hours) "
                        "VALUES (%s, %s, %s, %s) "
                        "ON CONFLICT (year, month) DO UPDATE SET "
                        "work_days = EXCLUDED.work_days, work_hours = EXCLUDED.work_hours",
                        (r["year"], r["month"], r["work_days"], r["work_hours"]),
                    )
            conn.commit()

    def select_events_for_sessions(self, session_ids: list) -> list:
        if not session_ids:
            return []
        import psycopg2.extras
        with self._connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    f"SELECT * FROM {TABLE} WHERE session_id = ANY(%s::uuid[]) "
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
        # Миграции 0001/0002 выдают политики роли anon (в Supabase она есть всегда).
        # В обычной PostgreSQL её нет — создаём без прав и входа; если у пользователя
        # нет CREATEROLE, пропускаем (роль могла быть создана при bootstrap).
        with conn.cursor() as cur:
            cur.execute(
                "DO $$ BEGIN CREATE ROLE anon NOLOGIN; "
                "EXCEPTION WHEN duplicate_object OR insufficient_privilege THEN NULL; END $$"
            )
        conn.commit()
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


# ---------------------------------------------------------- локальная PostgreSQL

LOCAL_DB = "work_timer"
LOCAL_ROLE = "work_timer_app"


def port_open(host: str = "127.0.0.1", port: int = 5432, timeout: float = 1.0) -> bool:
    import socket
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def generate_password() -> str:
    import secrets
    return secrets.token_hex(16)


def build_local_dsn(password: str, host: str = "127.0.0.1", port: int = 5432) -> str:
    return f"postgresql://{LOCAL_ROLE}:{password}@{host}:{port}/{LOCAL_DB}"


def bootstrap_with_superuser(host: str, port: int, user: str, password: str) -> str:
    """Создаёт роль и БД проекта от имени суперпользователя PostgreSQL.

    Аналог sql/bootstrap/0000_CreateUserAndDatabase.sql для случая, когда есть
    TCP-доступ с паролем (Windows). Идемпотентно. Возвращает DATABASE_URL
    созданного пользователя проекта.
    """
    import psycopg2
    from psycopg2 import sql

    app_password = generate_password()

    def connect(dbname: str):
        conn = psycopg2.connect(host=host, port=port, user=user, password=password,
                                dbname=dbname, connect_timeout=5)
        conn.autocommit = True  # CREATE DATABASE нельзя выполнять в транзакции
        return conn

    conn = connect("postgres")
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (LOCAL_ROLE,))
            verb = "ALTER" if cur.fetchone() else "CREATE"
            cur.execute(sql.SQL(verb + " ROLE {} WITH LOGIN PASSWORD {}").format(
                sql.Identifier(LOCAL_ROLE), sql.Literal(app_password)))
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (LOCAL_DB,))
            if not cur.fetchone():
                cur.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(
                    sql.Identifier(LOCAL_DB), sql.Identifier(LOCAL_ROLE)))
            cur.execute(sql.SQL("GRANT ALL PRIVILEGES ON DATABASE {} TO {}").format(
                sql.Identifier(LOCAL_DB), sql.Identifier(LOCAL_ROLE)))
            cur.execute(
                "DO $$ BEGIN CREATE ROLE anon NOLOGIN; "
                "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
            )
    finally:
        conn.close()

    conn = connect(LOCAL_DB)
    try:
        with conn.cursor() as cur:
            cur.execute(sql.SQL("ALTER SCHEMA public OWNER TO {}").format(
                sql.Identifier(LOCAL_ROLE)))
            cur.execute(sql.SQL("GRANT ALL ON SCHEMA public TO {}").format(
                sql.Identifier(LOCAL_ROLE)))
    finally:
        conn.close()

    return build_local_dsn(app_password, host, port)


def check_dsn(dsn: str) -> None:
    """Бросает исключение, если по DSN нельзя подключиться."""
    import psycopg2
    psycopg2.connect(dsn, connect_timeout=5).close()
