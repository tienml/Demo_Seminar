"""Gọi dịch vụ ngoài (tỉ giá) và ký request nội bộ.

Module này quan trọng với kịch bản Chặng 4 của demo: nó import trực tiếp hằng số
`ADMIN_API_KEY` từ config. Khi agent vá lỗ hổng hardcoded secret bằng cách xoá
hằng số đó khỏi mã nguồn, module này sẽ gãy và bộ test đỏ. Agent phải tự đọc
traceback rồi chuyển sang đọc biến môi trường thì test mới xanh trở lại.

Đây là một tác dụng phụ có thật khi vá bảo mật, không phải tình huống dàn dựng.
"""

import requests

from .config import ADMIN_API_KEY, RATE_SERVICE_URL

DEFAULT_RATE = 25_400.0
REQUEST_TIMEOUT = 3


def internal_auth_header() -> dict:
    """Header dùng khi gọi các dịch vụ nội bộ khác."""
    return {"X-Internal-Key": ADMIN_API_KEY}


def get_usd_vnd_rate() -> float:
    """Lấy tỉ giá USD/VND. Luôn trả về giá trị mặc định nếu mạng lỗi."""
    try:
        resp = requests.get(RATE_SERVICE_URL, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return float(resp.json()["rates"]["VND"])
    except Exception:
        return DEFAULT_RATE
