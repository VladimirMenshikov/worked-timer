"""Расположение и загрузка конфигурации (.env) пользователя.

Конфиг хранится в каталоге пользователя, а не рядом с программой: приложение
ставится в /opt/work-timer (Linux, владелец root) или Program Files (Windows)
и не должно писать в собственный каталог — ни chown, ни права администратора.
"""

import os
import shutil
import sys
from pathlib import Path

from dotenv import dotenv_values, load_dotenv, set_key


def app_dir() -> Path:
    """Каталог с программой (для PyInstaller — рядом с WorkTimer.exe)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def config_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", str(Path.home()))) / "WorkTimer"
    return Path.home() / ".config" / "work-timer"


CONFIG_DIR = config_dir()
ENV_PATH = CONFIG_DIR / ".env"
LEGACY_ENV_PATH = app_dir() / ".env"


def ensure_env_file() -> Path:
    """Создаёт пользовательский .env; переносит старый, лежавший рядом с программой."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not ENV_PATH.exists():
        if LEGACY_ENV_PATH.is_file() and any(dotenv_values(LEGACY_ENV_PATH).values()):
            shutil.copyfile(LEGACY_ENV_PATH, ENV_PATH)
        else:
            ENV_PATH.touch()
        try:
            ENV_PATH.chmod(0o600)
        except OSError:
            pass
    return ENV_PATH


def load_env() -> None:
    ensure_env_file()
    load_dotenv(ENV_PATH, override=True)


def set_value(key: str, value: str) -> None:
    ensure_env_file()
    set_key(ENV_PATH, key, value)
    os.environ[key] = value
