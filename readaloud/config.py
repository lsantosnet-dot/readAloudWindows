"""Caminhos de dados do app (banco, cache de áudio, vozes, logs)."""

import os
import sys
from pathlib import Path

APP_NAME = "ReadAloud"


def data_dir() -> Path:
    """Pasta de dados do usuário.

    Windows: %LOCALAPPDATA%\\ReadAloud. Pode ser trocada pela variável READALOUD_HOME.
    """
    override = os.environ.get("READALOUD_HOME")
    if override:
        base = Path(override)
    elif sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / APP_NAME
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / APP_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base


def db_path() -> Path:
    return data_dir() / "cards.db"


def voices_dir() -> Path:
    path = data_dir() / "voices"
    path.mkdir(parents=True, exist_ok=True)
    return path


def audio_cache_dir() -> Path:
    path = data_dir() / "audio-cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_path() -> Path:
    return data_dir() / "readaloud.log"
