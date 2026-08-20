"""Bộ test bảo mật — tiêu chí nghiệm thu của bản vá.

Trước khi vá: các test này ĐỎ (đó là điều bình thường và có chủ đích).
Sau khi agent vá xong: toàn bộ phải XANH. Đây là bằng chứng độc lập với
các công cụ quét, và độc lập với chính bộ test chức năng mà agent sửa.
"""

import pytest

from app import config, db
from app.auth import SQLI_PAYLOAD, admin_search, authenticate
from app.main import create_app


@pytest.fixture()
def client():
    application = create_app()
    application.config.update(TESTING=True)
    with application.test_client() as c:
        yield c


def test_sql_injection_khong_qua_duoc_dang_nhap():
    db.init_db()
    assert authenticate(SQLI_PAYLOAD, "bat_ky_mat_khau_nao") is None


def test_sql_injection_bien_the_union():
    db.init_db()
    assert authenticate("' OR 1=1--", "x") is None
    assert authenticate("admin'--", "x") is None


def test_o_tim_kiem_admin_khong_bi_injection():
    db.init_db()
    # Payload này nếu bị nối chuỗi sẽ trả về toàn bộ bảng.
    results = admin_search("%' OR '1'='1")
    assert results == [], "Ô tìm kiếm vẫn đang nối chuỗi SQL"


def test_khong_con_secret_hardcode_trong_ma_nguon():
    for ten_bien in ("SECRET_KEY", "ADMIN_API_KEY", "INTERNAL_WEBHOOK_TOKEN"):
        gia_tri = getattr(config, ten_bien, "")
        assert not str(gia_tri).startswith(("sk_live_", "ghp_", "labbank-flask-secret")), (
            f"{ten_bien} vẫn là giá trị bí mật nhúng cứng trong mã nguồn"
        )


def test_security_headers_duoc_bat(client):
    resp = client.get("/")
    for header in (
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Content-Security-Policy",
    ):
        assert header in resp.headers, f"Thiếu header {header}"


def test_endpoint_version_bao_cao_da_va(client):
    data = client.get("/version").get_json()
    assert data["patched"] is True
    assert data["sqli_exploitable"] is False
