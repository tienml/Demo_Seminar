"""Xác thực và tra cứu người dùng.

LỖ HỔNG CỐ Ý #1 — SQL Injection.
Câu truy vấn được dựng bằng cách nối chuỗi, nên payload `admin' OR '1'='1--`
sẽ vô hiệu hoá mệnh đề WHERE và trả về bản ghi đầu tiên trong bảng (tài khoản admin).

Hàm dựng chuỗi này được gọi ở BA nơi khác nhau (đăng nhập, quên mật khẩu,
tìm kiếm trong trang quản trị). Đây là chi tiết quan trọng của demo: một công cụ
chỉ so khớp mẫu sẽ báo ba cảnh báo rời rạc, còn agent hiểu call graph sẽ nhận ra
cả ba cùng bắt nguồn từ một hàm và sửa trọn gói.
"""

from .db import get_connection

SQLI_PAYLOAD = "admin' OR '1'='1--"


# --- BEGIN VULNERABLE QUERY BUILDER ---
def build_user_query(username: str, password: str | None = None) -> str:
    """Dựng câu SQL bằng nối chuỗi. Không escape, không tham số hoá."""
    query = "SELECT * FROM users WHERE username = '" + username + "'"
    if password is not None:
        query += " AND password = '" + password + "'"
    return query


def authenticate(username: str, password: str):
    """Đăng nhập. Call site #1 của build_user_query."""
    conn = get_connection()
    try:
        row = conn.execute(build_user_query(username, password)).fetchone()
        return dict(row) if row else None
    except Exception:
        return None
    finally:
        conn.close()


def find_user_for_reset(username: str):
    """Quên mật khẩu. Call site #2 của build_user_query."""
    conn = get_connection()
    try:
        row = conn.execute(build_user_query(username)).fetchone()
        return dict(row) if row else None
    except Exception:
        return None
    finally:
        conn.close()


def admin_search(keyword: str):
    """Ô tìm kiếm trong trang quản trị. Call site #3, cũng nối chuỗi."""
    conn = get_connection()
    try:
        sql = (
            "SELECT id, username, role, fullname, email FROM users "
            "WHERE username LIKE '%" + keyword + "%'"
        )
        rows = conn.execute(sql).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        conn.close()
# --- END VULNERABLE QUERY BUILDER ---


def injection_succeeds() -> bool:
    """Tự kiểm tra: thử chính payload SQLi lên hàm xác thực của ứng dụng.

    Endpoint /version dùng hàm này để báo cáo ứng dụng đang ở trạng thái
    dính lỗ hổng hay đã được vá. Nhờ vậy trạng thái là kết quả kiểm chứng
    thực tế chứ không phải một cờ cấu hình được bật tay.
    """
    try:
        return authenticate(SQLI_PAYLOAD, "bat_ky_mat_khau_nao") is not None
    except Exception:
        return False
