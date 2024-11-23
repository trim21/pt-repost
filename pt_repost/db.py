import sqlite3
from pathlib import Path
from typing import Any


class Database:
    def __init__(self, db: Path):
        self.db = db

    def execute(self, sql: str, args=()) -> Any:
        with sqlite3.connect(self.db) as conn:
            conn.execute(sql, args)

    def fetch_val(self, sql: str, args=()) -> Any:
        with sqlite3.connect(self.db) as conn:
            row = conn.execute(sql, args).fetchone()
            if row:
                return row[0]

    def fetch_one(self, sql: str, args=()) -> tuple[Any, ...]:
        with sqlite3.connect(self.db) as conn:
            return conn.execute(sql, args).fetchone()

    def fetch_all(self, sql: str, args=()) -> list[Any]:
        with sqlite3.connect(self.db) as conn:
            return conn.execute(sql, args).fetchall()
