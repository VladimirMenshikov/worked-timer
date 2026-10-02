"""Мастер первого запуска (Linux, zenity): выбор БД и сохранение подключения в .env."""

import os
import subprocess
import time

import app_config
import db_backend
import local_pg_linux

CHOICES = [
    ("local", "Локальная PostgreSQL на этом компьютере (рекомендуется)"),
    ("supabase", "Supabase"),
    ("postgres", "PostgreSQL на другом сервере"),
]


class SetupCancelled(Exception):
    """Пользователь закрыл мастер — подключение к БД не задано."""


def zenity_env() -> dict:
    """Окружение для запуска zenity в обход сломанного сокета IBus.

    После очистки ~/.cache/ibus демон IBus остаётся запущен, но его
    unix-сокет исчезает — GTK-приложения пытаются подключиться к нему и
    не получают вообще никакого ввода с клавиатуры (ни печать, ни Ctrl+V).
    Принудительный gtk-im-context-simple не зависит от IBus.
    """
    env = os.environ.copy()
    env["GTK_IM_MODULE"] = "gtk-im-context-simple"
    return env


def _zenity(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["zenity", *args], capture_output=True, text=True, env=zenity_env())


def _show_error(msg: str) -> None:
    _zenity("--error", "--title=Work Timer", f"--text={msg}", "--width=420")


def _confirm(text: str) -> bool:
    return _zenity("--question", "--title=Work Timer", f"--text={text}", "--width=420").returncode == 0


def needs_db_setup() -> bool:
    backend = os.environ.get("DB_BACKEND", "").strip().lower()

    if backend not in ("supabase", "postgres"):
        # Обратная совместимость: .env уже содержит рабочие Supabase-креды
        # из версии приложения до появления DB_BACKEND — не переспрашиваем.
        if os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_KEY"):
            app_config.set_value("DB_BACKEND", "supabase")
            return False
        return True

    if backend == "supabase":
        return not (os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_KEY"))
    return not os.environ.get("DATABASE_URL")


def _ask_choice() -> str:
    args = ["--list", "--radiolist", "--title=Work Timer — настройка подключения к БД",
            "--text=Где хранить данные о рабочем времени?",
            "--column=", "--column=key", "--column=Вариант",
            "--hide-column=2", "--print-column=2", "--width=520", "--height=260"]
    for i, (key, label) in enumerate(CHOICES):
        args += ["TRUE" if i == 0 else "FALSE", key, label]
    res = _zenity(*args)
    key = res.stdout.strip()
    if res.returncode != 0 or not key:
        raise SetupCancelled("Настройка БД не завершена — подключение не задано.")
    return key


def _setup_local() -> bool:
    """Локальная PostgreSQL: установка (при необходимости), запуск, создание БД и пользователя."""
    if not local_pg_linux.server_installed():
        if not _confirm("PostgreSQL на этом компьютере не найден.\n\n"
                        "Установить её сейчас (apt install postgresql)?\n"
                        "Потребуется пароль администратора."):
            return False
        local_pg_linux.install_server()
    if not local_pg_linux.is_running():
        local_pg_linux.start_server()
        for _ in range(20):
            if local_pg_linux.is_running():
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("PostgreSQL установлена, но не отвечает на порту 5432.")

    dsn = local_pg_linux.bootstrap()
    db_backend.check_dsn(dsn)
    app_config.set_value("DB_BACKEND", "postgres")
    app_config.set_value("DATABASE_URL", dsn)
    return True


def _setup_supabase() -> bool:
    form = _zenity(
        "--forms", "--title=Work Timer — Supabase", "--separator=\t",
        "--text=Данные подключения Supabase (Project Settings → API)",
        "--add-entry=SUPABASE_URL",
        "--add-entry=SUPABASE_KEY (anon key)",
        "--add-entry=DATABASE_URL (необязательно — для автомиграций, Project Settings → Database)",
        "--width=560",
    )
    if form.returncode != 0:
        return False
    parts = (form.stdout.rstrip("\n").split("\t") + ["", "", ""])[:3]
    url, key, dsn = (p.strip() for p in parts)
    if not url or not key:
        raise RuntimeError("SUPABASE_URL и SUPABASE_KEY обязательны.")
    app_config.set_value("DB_BACKEND", "supabase")
    app_config.set_value("SUPABASE_URL", url)
    app_config.set_value("SUPABASE_KEY", key)
    if dsn:
        app_config.set_value("DATABASE_URL", dsn)
    return True


def _setup_postgres() -> bool:
    form = _zenity(
        "--forms", "--title=Work Timer — PostgreSQL", "--text=Строка подключения PostgreSQL",
        "--add-entry=DATABASE_URL (postgresql://user:password@host:port/dbname)", "--width=560",
    )
    if form.returncode != 0:
        return False
    dsn = form.stdout.strip()
    if not dsn:
        raise RuntimeError("DATABASE_URL обязателен.")
    db_backend.check_dsn(dsn)
    app_config.set_value("DB_BACKEND", "postgres")
    app_config.set_value("DATABASE_URL", dsn)
    return True


_SETUPS = {"local": _setup_local, "supabase": _setup_supabase, "postgres": _setup_postgres}


def run_setup_wizard() -> None:
    """Крутится, пока подключение не будет задано; ошибка шага возвращает к выбору."""
    while True:
        choice = _ask_choice()
        try:
            if _SETUPS[choice]():
                return
        except Exception as exc:
            _show_error(str(exc))
