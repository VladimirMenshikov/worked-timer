"""Локальная PostgreSQL на Linux: проверка, установка, запуск, создание БД и пользователя.

Привилегированные шаги идут через pkexec (polkit-окно пароля пользователя) —
само приложение запускается без root.
"""

import glob
import shutil
import subprocess
from pathlib import Path

import db_backend

BOOTSTRAP_SQL = Path(__file__).parent / "sql" / "bootstrap" / "0000_CreateUserAndDatabase.sql"


def server_installed() -> bool:
    return bool(glob.glob("/usr/lib/postgresql/*/bin/postgres"))


def is_running() -> bool:
    return db_backend.port_open()


def _pkexec(args: list, stdin: str = "") -> subprocess.CompletedProcess:
    if not shutil.which("pkexec"):
        raise RuntimeError("Не найден pkexec (пакет policykit-1) — нужен для действий от root.")
    return subprocess.run(["pkexec", *args], input=stdin, capture_output=True, text=True, cwd="/")


def install_server() -> None:
    res = _pkexec(["apt-get", "install", "-y", "postgresql"])
    if res.returncode != 0:
        raise RuntimeError(f"Установка PostgreSQL не удалась:\n{res.stderr.strip() or res.stdout.strip()}")


def start_server() -> None:
    res = _pkexec(["systemctl", "start", "postgresql"])
    if res.returncode != 0:
        raise RuntimeError(f"Не удалось запустить PostgreSQL:\n{res.stderr.strip()}")


def bootstrap() -> str:
    """Создаёт пользователя и БД проекта, возвращает DATABASE_URL.

    Пароль и SQL передаются через stdin, а не аргументами — чтобы пароль не
    светился в списке процессов.
    """
    password = db_backend.generate_password()
    script = f"\\set app_password '{password}'\n" + BOOTSTRAP_SQL.read_text(encoding="utf-8")
    res = _pkexec(
        ["runuser", "-u", "postgres", "--", "psql", "-X", "-q",
         "-v", "ON_ERROR_STOP=1", "-d", "postgres", "-f", "-"],
        stdin=script,
    )
    if res.returncode != 0:
        raise RuntimeError(f"Не удалось создать БД и пользователя:\n{res.stderr.strip()}")
    return db_backend.build_local_dsn(password)
