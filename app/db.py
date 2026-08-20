"""Lớp truy cập dữ liệu SQLite cho demo.

Toàn bộ dữ liệu là seed giả, không có thông tin thật của bất kỳ ai.
CSDL được dựng lại mỗi lần tiến trình khởi động để demo luôn ở trạng thái sạch.
"""

import os
import sqlite3

from . import config

SCHEMA = """
DROP TABLE IF EXISTS users;
CREATE TABLE users (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    role     TEXT NOT NULL DEFAULT 'user',
    fullname TEXT NOT NULL,
    balance  INTEGER NOT NULL DEFAULT 0,
    email    TEXT NOT NULL,
    phone    TEXT NOT NULL
);
"""

SEED_USERS = [
    ("admin", "S3cur3-Adm1n-P@ss-2026", "admin", "Trần Quản Trị", 999_000_000,
     "admin@labbank.test", "0900-000-001"),
    ("alice", "alice-pass-2026", "user", "Nguyễn Thị An", 12_400_000,
     "alice@labbank.test", "0900-000-002"),
    ("bob", "bob-pass-2026", "user", "Lê Văn Bảo", 3_150_000,
     "bob@labbank.test", "0900-000-003"),
    ("carol", "carol-pass-2026", "user", "Phạm Thu Cúc", 87_600_000,
     "carol@labbank.test", "0900-000-004"),
]


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(force: bool = True) -> None:
    """Dựng lại schema và nạp seed data."""
    if force and os.path.exists(config.DATABASE_PATH):
        try:
            os.remove(config.DATABASE_PATH)
        except OSError:
            pass

    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.executemany(
            "INSERT INTO users (username, password, role, fullname, balance, email, phone) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            SEED_USERS,
        )
        conn.commit()
    finally:
        conn.close()


def get_user_by_id(user_id):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, username, role, fullname, balance, email, phone "
            "FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_users():
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, username, role, fullname, balance, email FROM users ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
