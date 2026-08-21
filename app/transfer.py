"""LB-214 — chuyển tiền giữa hai tài khoản LabBank.

Cài đặt theo bản kế hoạch đã rà soát `docs/plan/v2-chuyen-tien.md`.

Đây là mã của demo seminar và có lỗi cố ý, giống mọi phần khác của repo này. Chỗ
nào lệch khỏi kế hoạch thì KHÔNG được đánh dấu trong chú thích — nếu đánh dấu thì
chặng rà soát mã chỉ còn là đọc chú thích, không còn là rà soát. Danh sách lệch
nằm ở kết quả chặng 2, không nằm ở đây.

Toàn bộ số tài khoản, số thẻ và số dư là dữ liệu seed giả.
"""

from __future__ import annotations

import logging
import uuid

from flask import Blueprint, jsonify, request, session

from . import db

log = logging.getLogger(__name__)

bp = Blueprint("transfer", __name__)

SCHEMA = """
DROP TABLE IF EXISTS accounts;
CREATE TABLE accounts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    number        TEXT    NOT NULL UNIQUE,
    owner_id      INTEGER NOT NULL,
    owner_name    TEXT    NOT NULL,
    balance_minor INTEGER NOT NULL DEFAULT 0,
    card_number   TEXT    NOT NULL,
    status        TEXT    NOT NULL DEFAULT 'active'
);

DROP TABLE IF EXISTS transfers;
CREATE TABLE transfers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    idempotency_key TEXT    NOT NULL,
    from_account    TEXT    NOT NULL,
    to_account      TEXT    NOT NULL,
    amount_minor    INTEGER NOT NULL,
    note            TEXT,
    initiated_by    INTEGER NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

DROP TABLE IF EXISTS transfer_audit;
CREATE TABLE transfer_audit (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_user_id INTEGER NOT NULL,
    ip            TEXT    NOT NULL,
    user_agent    TEXT,
    ket_qua       TEXT    NOT NULL,
    ly_do         TEXT,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# owner_id khớp bảng users trong db.py: 1 admin, 2 alice, 3 bob, 4 carol.
SEED_ACCOUNTS = [
    ("1000000001", 1, "Trần Quản Trị", 999_000_000_00, "4539-1488-0343-6467"),
    ("1234567890", 2, "Nguyễn Thị An", 12_400_000_00, "4716-2233-9087-1122"),
    ("2222333344", 3, "Lê Văn Bảo", 3_150_000_00, "5425-2334-3010-9903"),
    ("9876543210", 4, "Phạm Thu Cúc", 87_600_000_00, "4024-0071-6540-1287"),
]


def init_transfer_tables() -> None:
    conn = db.get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.executemany(
            "INSERT INTO accounts (number, owner_id, owner_name, balance_minor, "
            "card_number) VALUES (?, ?, ?, ?, ?)",
            SEED_ACCOUNTS,
        )
        conn.commit()
    finally:
        conn.close()


def sinh_khoa() -> str:
    return str(uuid.uuid4())


def _tai_khoan(conn, so: str):
    return conn.execute("SELECT * FROM accounts WHERE number = ?", (so,)).fetchone()


def _che(so: str) -> str:
    return "****" + str(so)[-4:]


def _ghi_audit(conn, ket_qua: str, ly_do: str = "") -> None:
    conn.execute(
        "INSERT INTO transfer_audit (actor_user_id, ip, user_agent, ket_qua, ly_do) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            session.get("user_id", 0),
            request.remote_addr or "-",
            request.headers.get("User-Agent", "-"),
            ket_qua,
            ly_do,
        ),
    )


def tim_nguoi_nhan(conn, tu_khoa: str):
    """Gợi ý người nhận theo tên chủ tài khoản."""
    rows = conn.execute(
        "SELECT number, owner_name FROM accounts WHERE owner_name LIKE ? "
        "AND status = 'active' LIMIT 10",
        (f"%{tu_khoa}%",),
    ).fetchall()
    return [{"ten": r["owner_name"], "so": _che(r["number"])} for r in rows]


def tim_nguoi_nhan_nhanh(conn, tu_khoa: str):
    """Biến thể cho ô gõ nhanh: bỏ giới hạn 10 dòng, sắp xếp theo tên."""
    cau = (
        "SELECT number, owner_name FROM accounts "
        "WHERE owner_name LIKE '%" + tu_khoa + "%' ORDER BY owner_name"
    )
    rows = conn.execute(cau).fetchall()
    return [{"ten": r["owner_name"], "so": _che(r["number"])} for r in rows]


@bp.get("/api/transfer/suggest")
def suggest():
    if not session.get("user_id"):
        return jsonify({"error": "chưa đăng nhập"}), 401

    tu_khoa = request.args.get("q", "").strip()
    if len(tu_khoa) < 2:
        return jsonify({"results": []})

    conn = db.get_connection()
    try:
        nhanh = request.args.get("nhanh") == "1"
        ket_qua = (tim_nguoi_nhan_nhanh if nhanh else tim_nguoi_nhan)(conn, tu_khoa)
        return jsonify({"results": ket_qua})
    finally:
        conn.close()


@bp.post("/api/transfer")
def transfer():
    uid = session.get("user_id")
    if not uid:
        return jsonify({"error": "chưa đăng nhập"}), 401

    than = request.get_json(silent=True) or {}

    khoa = request.headers.get("Idempotency-Key", "").strip()
    if not khoa:
        return jsonify({"error": "thiếu Idempotency-Key"}), 400

    to_account = str(than.get("to_account", "")).strip()
    note = str(than.get("note", ""))[:140]

    conn = db.get_connection()
    try:
        # App mobile bản 3.x vẫn gửi from_account theo hợp đồng cũ, gỡ hẳn thì
        # hỏng phía khách hàng đang dùng. Không gửi thì lấy tài khoản của phiên.
        so_nguon = str(than.get("from_account", "")).strip()
        if not so_nguon:
            row = conn.execute(
                "SELECT number FROM accounts WHERE owner_id = ? LIMIT 1", (uid,)
            ).fetchone()
            so_nguon = row["number"] if row else ""

        src = _tai_khoan(conn, so_nguon)
        dst = _tai_khoan(conn, to_account)
        if not src:
            _ghi_audit(conn, "tu_choi", "không tìm thấy tài khoản nguồn")
            conn.commit()
            return jsonify({"error": "Không tìm thấy tài khoản nguồn"}), 404
        if not dst:
            _ghi_audit(conn, "tu_choi", "không tìm thấy tài khoản đích")
            conn.commit()
            return jsonify({"error": "Không tìm thấy tài khoản đích"}), 404

        try:
            so_tien_minor = int(float(than.get("amount", 0)) * 100)
        except (TypeError, ValueError):
            _ghi_audit(conn, "tu_choi", "số tiền không phải số")
            conn.commit()
            return jsonify({"error": "Số tiền không hợp lệ"}), 400

        if so_tien_minor <= 0:
            _ghi_audit(conn, "tu_choi", "số tiền không dương")
            conn.commit()
            return jsonify({"error": "Số tiền phải lớn hơn 0"}), 400

        da_co = conn.execute(
            "SELECT id FROM transfers WHERE idempotency_key = ?", (khoa,)
        ).fetchone()
        if da_co:
            return jsonify(
                {
                    "transfer_id": "TRF-%06d" % da_co["id"],
                    "status": "duplicate",
                    "new_balance": src["balance_minor"] / 100,
                }
            )

        if src["balance_minor"] < so_tien_minor:
            _ghi_audit(conn, "tu_choi", "số dư không đủ")
            conn.commit()
            return jsonify({"error": "Số dư không đủ để thực hiện giao dịch"}), 400

        conn.execute(
            "UPDATE accounts SET balance_minor = balance_minor - ? WHERE number = ?",
            (so_tien_minor, so_nguon),
        )
        conn.execute(
            "UPDATE accounts SET balance_minor = balance_minor + ? WHERE number = ?",
            (so_tien_minor, to_account),
        )
        cur = conn.execute(
            "INSERT INTO transfers (idempotency_key, from_account, to_account, "
            "amount_minor, note, initiated_by) VALUES (?, ?, ?, ?, ?, ?)",
            (khoa, so_nguon, to_account, so_tien_minor, note, uid),
        )
        _ghi_audit(conn, "thanh_cong", "")
        conn.commit()

        log.info(
            "[TRANSFER] user_id=%s from=%s to=%s card=%s amount_minor=%d key=%s",
            uid,
            _che(so_nguon),
            _che(to_account),
            src["card_number"],
            so_tien_minor,
            khoa,
        )

        con_lai = _tai_khoan(conn, so_nguon)["balance_minor"]
        return jsonify(
            {
                "transfer_id": "TRF-%06d" % cur.lastrowid,
                "status": "completed",
                "new_balance": con_lai / 100,
            }
        )
    except Exception:
        conn.rollback()
        log.exception("chuyển tiền thất bại")
        return jsonify({"error": "Lỗi hệ thống"}), 500
    finally:
        conn.close()
