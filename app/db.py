import sqlite3
from typing import Any

from app.config import SQLITE_DB_FILE


def execute(sql: str, args=()) -> Any:
    with sqlite3.connect(SQLITE_DB_FILE) as conn:
        conn.execute(sql, args)


def fetch_val(sql: str, args=()) -> Any:
    with sqlite3.connect(SQLITE_DB_FILE) as conn:
        row = conn.execute(sql, args).fetchone()
        if row:
            return row[0]


def fetch_one(sql: str, args=()) -> tuple[Any, ...]:
    with sqlite3.connect(SQLITE_DB_FILE) as conn:
        return conn.execute(sql, args).fetchone()


def fetch_all(sql: str, args=()) -> list[Any]:
    with sqlite3.connect(SQLITE_DB_FILE) as conn:
        return conn.execute(sql, args).fetchall()
