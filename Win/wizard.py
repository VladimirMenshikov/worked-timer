"""Мастер первого запуска (Windows, tkinter): выбор БД и сохранение подключения в .env."""

import os
import tkinter as tk
from tkinter import messagebox
from typing import Optional

import app_config
import db_backend

CHOICES = [
    ("local", "Локальная PostgreSQL на этом компьютере (рекомендуется)"),
    ("supabase", "Supabase"),
    ("postgres", "PostgreSQL на другом сервере"),
]

POSTGRES_DOWNLOAD = "https://www.postgresql.org/download/windows/"


class SetupCancelled(Exception):
    """Пользователь закрыл мастер — подключение к БД не задано."""


def _center(root: tk.Tk) -> None:
    root.update_idletasks()
    w, h = root.winfo_width(), root.winfo_height()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")


def _show_error(msg: str) -> None:
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    messagebox.showerror("Work Timer", msg, parent=root)
    root.destroy()


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


def _ask_choice() -> Optional[str]:
    result = {"value": None}
    root = tk.Tk()
    root.title("Work Timer — настройка подключения к БД")
    root.attributes("-topmost", True)
    root.resizable(False, False)

    tk.Label(root, text="Где хранить данные о рабочем времени?",
             padx=16, pady=(16, 8), anchor="w").pack(fill="x")
    var = tk.StringVar(value=CHOICES[0][0])
    for key, label in CHOICES:
        tk.Radiobutton(root, text=label, variable=var, value=key).pack(anchor="w", padx=24)

    def on_ok(event=None):
        result["value"] = var.get()
        root.destroy()

    btns = tk.Frame(root)
    btns.pack(pady=16)
    tk.Button(btns, text="Далее", width=10, command=on_ok).pack(side="left", padx=6)
    tk.Button(btns, text="Отмена", width=10, command=root.destroy).pack(side="left", padx=6)
    root.bind("<Return>", on_ok)
    _center(root)
    root.mainloop()
    return result["value"]


def _ask_form(title: str, prompt: str, fields: list, secret: tuple = ()) -> Optional[list]:
    """fields — подписи полей, secret — индексы полей-паролей.

    Поле можно задать как (подпись, значение по умолчанию).
    Возвращает введённые значения либо None при отмене.
    """
    result = {"value": None}
    root = tk.Tk()
    root.title(title)
    root.attributes("-topmost", True)
    root.resizable(False, False)

    tk.Label(root, text=prompt, padx=16, pady=(16, 8),
             justify="left", wraplength=460, anchor="w").pack(fill="x")

    entries = []
    for i, field in enumerate(fields):
        label, default = field if isinstance(field, tuple) else (field, "")
        tk.Label(root, text=label, padx=16, anchor="w").pack(fill="x")
        entry = tk.Entry(root, width=60, show="*" if i in secret else "")
        entry.insert(0, default)
        entry.pack(padx=16, pady=(0, 8))
        entries.append(entry)

    def on_ok(event=None):
        result["value"] = [e.get().strip() for e in entries]
        root.destroy()

    btns = tk.Frame(root)
    btns.pack(pady=(4, 16))
    tk.Button(btns, text="OK", width=10, command=on_ok).pack(side="left", padx=6)
    tk.Button(btns, text="Отмена", width=10, command=root.destroy).pack(side="left", padx=6)
    root.bind("<Return>", on_ok)
    root.bind("<Escape>", lambda e: root.destroy())
    _center(root)
    entries[0].focus_force()
    root.mainloop()
    return result["value"]


def _setup_local() -> bool:
    """Локальная PostgreSQL: нужен её суперпользователь (пароль задавался при установке)."""
    if not db_backend.port_open():
        raise RuntimeError(
            "PostgreSQL на этом компьютере не запущена (порт 5432 не отвечает).\n\n"
            f"Установите её: {POSTGRES_DOWNLOAD}\n"
            "и запустите мастер снова — либо выберите другой вариант."
        )
    values = _ask_form(
        "Work Timer — локальная PostgreSQL",
        "Укажите суперпользователя PostgreSQL (пароль задавался при её установке). "
        "Он нужен один раз — чтобы создать базу и отдельного пользователя для Work Timer; "
        "сам пароль нигде не сохраняется.",
        [("Пользователь", "postgres"), ("Пароль", ""), ("Порт", "5432")],
        secret=(1,),
    )
    if values is None:
        return False
    user, password, port = values
    if not user or not password or not port.isdigit():
        raise RuntimeError("Укажите пользователя, пароль и числовой порт.")
    dsn = db_backend.bootstrap_with_superuser("127.0.0.1", int(port), user, password)
    db_backend.check_dsn(dsn)
    app_config.set_value("DB_BACKEND", "postgres")
    app_config.set_value("DATABASE_URL", dsn)
    return True


def _setup_supabase() -> bool:
    values = _ask_form(
        "Work Timer — Supabase",
        "Данные подключения Supabase (Project Settings → API)",
        ["SUPABASE_URL", "SUPABASE_KEY (anon key)",
         "DATABASE_URL (необязательно — для автомиграций, Project Settings → Database)"],
    )
    if values is None:
        return False
    url, key, dsn = values
    if not url or not key:
        raise RuntimeError("SUPABASE_URL и SUPABASE_KEY обязательны.")
    app_config.set_value("DB_BACKEND", "supabase")
    app_config.set_value("SUPABASE_URL", url)
    app_config.set_value("SUPABASE_KEY", key)
    if dsn:
        app_config.set_value("DATABASE_URL", dsn)
    return True


def _setup_postgres() -> bool:
    values = _ask_form(
        "Work Timer — PostgreSQL", "Строка подключения PostgreSQL",
        ["DATABASE_URL (postgresql://user:password@host:port/dbname)"],
    )
    if values is None:
        return False
    if not values[0]:
        raise RuntimeError("DATABASE_URL обязателен.")
    db_backend.check_dsn(values[0])
    app_config.set_value("DB_BACKEND", "postgres")
    app_config.set_value("DATABASE_URL", values[0])
    return True


_SETUPS = {"local": _setup_local, "supabase": _setup_supabase, "postgres": _setup_postgres}


def run_setup_wizard() -> None:
    """Крутится, пока подключение не будет задано; ошибка шага возвращает к выбору."""
    while True:
        choice = _ask_choice()
        if not choice:
            raise SetupCancelled("Настройка БД не завершена — подключение не задано.")
        try:
            if _SETUPS[choice]():
                return
        except Exception as exc:
            _show_error(str(exc))
