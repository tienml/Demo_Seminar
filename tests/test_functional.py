"""Bộ test chức năng — PHẢI xanh ở mọi thời điểm, kể cả trước khi vá.

Đây là lưới an toàn của Chặng 4: khi agent gỡ hằng số bí mật ra khỏi mã nguồn,
module app/external.py sẽ gãy và chính bộ test này chuyển đỏ. Agent phải tự đọc
traceback rồi chuyển sang đọc biến môi trường thì mới xanh trở lại.
"""

import pytest

from app import db
from app.auth import authenticate, find_user_for_reset
from app.main import create_app


@pytest.fixture()
def client():
    application = create_app()
    application.config.update(TESTING=True)
    with application.test_client() as c:
        yield c


def test_seed_data_loaded():
    db.init_db()
    users = db.list_users()
    assert len(users) == 4
    assert {u["username"] for u in users} == {"admin", "alice", "bob", "carol"}


def test_login_hop_le_thanh_cong():
    db.init_db()
    user = authenticate("alice", "alice-pass-2026")
    assert user is not None
    assert user["role"] == "user"


def test_login_sai_mat_khau_that_bai():
    db.init_db()
    assert authenticate("alice", "sai-mat-khau") is None


def test_quen_mat_khau_tim_duoc_user():
    db.init_db()
    assert find_user_for_reset("bob") is not None
    assert find_user_for_reset("khong-ton-tai") is None


def test_healthz(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_trang_chu_hien_thi_nut_tan_cong(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"hack-btn" in resp.data


def test_dang_nhap_hop_le_qua_http(client):
    resp = client.post(
        "/login",
        data={"username": "carol", "password": "carol-pass-2026"},
        follow_redirects=True,
    )
    assert resp.status_code == 200


# --- Các test dưới đây phụ thuộc vào app/external.py ---------------------------
# Chúng chính là chỗ gãy khi hằng số ADMIN_API_KEY bị gỡ khỏi config.


def test_header_noi_bo_co_khoa():
    from app.external import internal_auth_header

    header = internal_auth_header()
    assert "X-Internal-Key" in header
    assert header["X-Internal-Key"], "Khoá nội bộ không được rỗng"


def test_ti_gia_luon_tra_ve_so_duong():
    from app.external import get_usd_vnd_rate

    rate = get_usd_vnd_rate()
    assert isinstance(rate, float)
    assert rate > 0
