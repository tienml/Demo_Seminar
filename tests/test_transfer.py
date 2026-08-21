"""Bộ test cho LB-214 chuyển tiền.

Viết theo mục §8 của bản kế hoạch v1: chuyển tiền thành công, số dư không đủ,
tài khoản đích không tồn tại, hiển thị mã giao dịch. Toàn bộ đều xanh.

Bản kế hoạch v2 yêu cầu 13 tiêu chí nghiệm thu AC-1…AC-13, mỗi tiêu chí phải có
ít nhất một test âm và phải đỏ trước khi vá (§12.1, §12.2). Bộ test này không có
tiêu chí nào trong số đó.
"""

import pytest

from app import db, transfer
from app.main import create_app


@pytest.fixture()
def client():
    application = create_app()
    application.config.update(TESTING=True)
    with application.test_client() as c:
        yield c


@pytest.fixture()
def alice(client):
    """Đăng nhập sẵn bằng alice — chủ tài khoản 1234567890."""
    with client.session_transaction() as s:
        s["user_id"] = 2
        s["role"] = "user"
    return client


def so_du(so: str) -> int:
    conn = db.get_connection()
    try:
        return conn.execute(
            "SELECT balance_minor FROM accounts WHERE number = ?", (so,)
        ).fetchone()["balance_minor"]
    finally:
        conn.close()


def test_chuyen_tien_thanh_cong_so_du_hai_ben_doi_dung(alice):
    truoc_nguon = so_du("1234567890")
    truoc_dich = so_du("9876543210")

    r = alice.post(
        "/api/transfer",
        json={"to_account": "9876543210", "amount": 250000, "note": "tra tien an trua"},
        headers={"Idempotency-Key": transfer.sinh_khoa()},
    )

    assert r.status_code == 200
    assert r.get_json()["status"] == "completed"
    assert so_du("1234567890") == truoc_nguon - 250000_00
    assert so_du("9876543210") == truoc_dich + 250000_00


def test_so_du_khong_du_thi_bi_tu_choi(alice):
    truoc = so_du("1234567890")

    r = alice.post(
        "/api/transfer",
        json={"to_account": "9876543210", "amount": 999_000_000},
        headers={"Idempotency-Key": transfer.sinh_khoa()},
    )

    assert r.status_code == 400
    assert "Số dư không đủ" in r.get_json()["error"]
    assert so_du("1234567890") == truoc


def test_tai_khoan_dich_khong_ton_tai_tra_404(alice):
    r = alice.post(
        "/api/transfer",
        json={"to_account": "0000000000", "amount": 10000},
        headers={"Idempotency-Key": transfer.sinh_khoa()},
    )

    assert r.status_code == 404


def test_phan_hoi_co_ma_giao_dich_dung_dinh_dang(alice):
    r = alice.post(
        "/api/transfer",
        json={"to_account": "9876543210", "amount": 15000},
        headers={"Idempotency-Key": transfer.sinh_khoa()},
    )

    ma = r.get_json()["transfer_id"]
    assert ma.startswith("TRF-")
    assert len(ma) == 10


def test_o_goi_y_tra_ve_ten_nguoi_nhan(alice):
    r = alice.get("/api/transfer/suggest?q=Ph")

    assert r.status_code == 200
    ten = [x["ten"] for x in r.get_json()["results"]]
    assert "Phạm Thu Cúc" in ten
