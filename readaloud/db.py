"""Armazenamento local dos cards e configurações em SQLite."""

import json
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import Any, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS cards (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    text       TEXT    NOT NULL,
    lang       TEXT    NOT NULL,
    voice      TEXT,
    source     TEXT,
    created_at REAL    NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

CARD_COLUMNS = "id, text, lang, voice, source, created_at"


class Database:
    def __init__(self, path: Path):
        self.path = path
        with closing(self._connect()) as conn, conn:
            conn.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    # ----------------------------------------------------------------- cards

    def list_cards(self) -> list[dict]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                f"SELECT {CARD_COLUMNS} FROM cards ORDER BY created_at DESC, id DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_card(self, card_id: int) -> Optional[dict]:
        with closing(self._connect()) as conn:
            row = conn.execute(
                f"SELECT {CARD_COLUMNS} FROM cards WHERE id = ?", (card_id,)
            ).fetchone()
        return dict(row) if row else None

    def add_card(self, text: str, lang: str, source: Optional[str]) -> dict:
        with closing(self._connect()) as conn, conn:
            cur = conn.execute(
                "INSERT INTO cards (text, lang, source, created_at) VALUES (?, ?, ?, ?)",
                (text, lang, source, time.time()),
            )
            card_id = cur.lastrowid
        return self.get_card(card_id)

    def update_card(self, card_id: int, **fields: Any) -> Optional[dict]:
        allowed = {k: v for k, v in fields.items() if k in ("voice", "lang")}
        if allowed:
            assignments = ", ".join(f"{k} = ?" for k in allowed)
            with closing(self._connect()) as conn, conn:
                conn.execute(
                    f"UPDATE cards SET {assignments} WHERE id = ?",
                    (*allowed.values(), card_id),
                )
        return self.get_card(card_id)

    def delete_card(self, card_id: int) -> bool:
        with closing(self._connect()) as conn, conn:
            cur = conn.execute("DELETE FROM cards WHERE id = ?", (card_id,))
        return cur.rowcount > 0

    def delete_all_cards(self) -> int:
        with closing(self._connect()) as conn, conn:
            cur = conn.execute("DELETE FROM cards")
        return cur.rowcount

    # -------------------------------------------------------------- settings

    def get_settings(self) -> dict:
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return {row["key"]: json.loads(row["value"]) for row in rows}

    def set_settings(self, values: dict) -> dict:
        with closing(self._connect()) as conn, conn:
            conn.executemany(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                [(k, json.dumps(v)) for k, v in values.items()],
            )
        return self.get_settings()
