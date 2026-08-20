"""Cấu hình ứng dụng.

LỖ HỔNG CỐ Ý #3 — Hardcoded secrets.
Khoá bí mật và API key được nhúng thẳng vào mã nguồn và commit lên Git.
Gitleaks sẽ bắt được ở stage `secrets` của pipeline.
Giá trị dưới đây là giả, chỉ dùng cho demo.
"""

import os

APP_NAME = "LabBank"

SECRET_KEY = "labbank-flask-secret-8f3b2a1c9d4e5f6a7b8c9d0e1f2a3b4c"
ADMIN_API_KEY = "sk_live_51LaBbAnKdEmO0000FaKeKeYFoRsEmInAr99"
INTERNAL_WEBHOOK_TOKEN = "ghp_FAKEfakeFAKEfakeFAKEfakeFAKEfake0000"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "labbank.db")

# Địa chỉ dịch vụ tỉ giá nội bộ (dùng ở app/external.py)
RATE_SERVICE_URL = os.environ.get(
    "RATE_SERVICE_URL", "https://api.exchangerate-api.com/v4/latest/USD"
)

# Bật/tắt các header bảo mật. Mặc định tắt -> LỖ HỔNG CỐ Ý #6 (thiếu security headers).
ENABLE_SECURITY_HEADERS = False
