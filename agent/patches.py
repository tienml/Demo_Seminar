"""Định nghĩa và áp dụng các bản vá.

Mỗi bản vá ghi lại ba thứ: sửa tệp nào, vì sao sửa như vậy, và bản vá đó lan
sang chỗ nào khác trong dự án. Phần cuối cùng là điểm phân biệt quan trọng
giữa một trợ lý nhìn từng tệp rời rạc và một tác nhân hiểu cả đồ thị lời gọi:
một cảnh báo ở `app/auth.py:21` thực chất kéo theo ba nơi gọi chung hàm dựng
câu lệnh, còn bản vá khoá bí mật thì làm gãy một module hoàn toàn khác.

Trước lần ghi đầu tiên, tệp gốc được sao lưu vào `.demo-backup/` để
`scripts/reset_demo.py` đưa kho mã về đúng trạng thái ban đầu giữa các lần chạy
thử, không cần phụ thuộc vào Git.
"""

from __future__ import annotations

import difflib
import shutil
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = Path(__file__).resolve().parent / "patched"
BACKUP_DIR = ROOT / ".demo-backup"


@dataclass
class Change:
    """Một tệp bị thay đổi bởi bản vá."""

    path: str
    template: str = ""
    replacements: tuple[tuple[str, str], ...] = ()
    summary: str = ""


@dataclass
class Patch:
    id: str
    group: str
    title: str
    cwe: str
    reasoning: list[str]
    changes: list[Change]
    ripple: list[str] = field(default_factory=list)

    @property
    def files(self) -> list[str]:
        return [c.path for c in self.changes]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _backup(rel: str) -> None:
    src = ROOT / rel
    dst = BACKUP_DIR / rel
    if dst.exists() or not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _new_content(change: Change, before: str) -> str:
    if change.template:
        return _read(TEMPLATE_DIR / change.template)

    after = before
    for old, new in change.replacements:
        if old not in after:
            raise RuntimeError(
                f"Không tìm thấy đoạn cần sửa trong {change.path}. "
                f"Có thể kho mã chưa được reset về trạng thái ban đầu."
            )
        after = after.replace(old, new)
    return after


def unified_diff(path: str, before: str, after: str, context: int = 2) -> list[str]:
    return list(
        difflib.unified_diff(
            before.splitlines(),
            after.splitlines(),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="",
            n=context,
        )
    )


def apply_change(change: Change) -> tuple[list[str], int, int]:
    """Ghi thay đổi xuống đĩa. Trả về (diff, số dòng thêm, số dòng bớt)."""
    target = ROOT / change.path
    before = _read(target)
    after = _new_content(change, before)

    _backup(change.path)
    target.write_text(after, encoding="utf-8", newline="\n")

    diff = unified_diff(change.path, before, after)
    added = sum(1 for d in diff if d.startswith("+") and not d.startswith("+++"))
    removed = sum(1 for d in diff if d.startswith("-") and not d.startswith("---"))
    return diff, added, removed


# ---------------------------------------------------------------------------
# Năm bản vá chính, theo thứ tự agent xử lý sau bước phân loại.
# ---------------------------------------------------------------------------

PATCHES: list[Patch] = [
    Patch(
        id="1/5",
        group="sqli",
        title="SQL Injection ở tầng xác thực",
        cwe="CWE-89",
        reasoning=[
            "đọc đồ thị lời gọi quanh app/auth.py:21",
            "build_user_query được gọi từ 3 nơi, không phải 1 như cảnh báo chỉ ra",
            "cả 3 đều nhận chuỗi thô từ request và đẩy thẳng vào sqlite3.execute",
            "chuyển hàm dựng câu lệnh sang trả về cặp (placeholder, tham số)",
            "ô tìm kiếm dùng LIKE nên phải escape thêm ký tự đại diện % và _",
        ],
        changes=[
            Change(
                path="app/auth.py",
                template="auth.py.txt",
                summary="tham số hoá cả 3 nơi gọi, thêm escape cho mệnh đề LIKE",
            )
        ],
        ripple=[
            "POST /login, POST /forgot-password và GET /api/admin/search cùng dùng "
            "một hàm dựng câu lệnh nên được vá trọn gói trong một lần",
        ],
    ),
    Patch(
        id="2/5",
        group="secret",
        title="Khoá bí mật nhúng cứng trong mã nguồn",
        cwe="CWE-798",
        reasoning=[
            "3 khoá nằm trong app/config.py và đã đi vào lịch sử Git",
            "hằng số cấp module chỉ đọc một lần lúc import nên không nhận được "
            "khoá xoay vòng — gỡ hẳn thay vì chỉ đổi sang os.environ",
            "giữ lại SECRET_KEY dạng biến môi trường vì Flask cần nó lúc khởi tạo",
            "bật luôn ENABLE_SECURITY_HEADERS trong cùng tệp",
        ],
        changes=[
            Change(
                path="app/config.py",
                template="config.py.txt",
                summary="gỡ 2 hằng số khoá, chuyển SECRET_KEY sang biến môi trường",
            )
        ],
        ripple=[
            "xoá khoá khỏi mã nguồn không thu hồi được khoá cũ — cả 3 vẫn phải "
            "được thu hồi ở phía nhà cung cấp",
        ],
    ),
    Patch(
        id="3/5",
        group="deps",
        title="Lỗ hổng thư viện phụ thuộc",
        cwe="CVE-2023-32681, CVE-2024-35195",
        reasoning=[
            "requests 2.25.1 dính 2 CVE, bản vá thấp nhất là 2.32.0",
            "chọn 2.32.3 để kéo theo idna 3.7 đã vá CVE-2024-3651",
            "đối chiếu CHANGELOG: không có breaking change ở các API app đang dùng",
        ],
        changes=[
            Change(
                path="requirements.txt",
                replacements=(
                    (
                        "# Cố ý ghim phiên bản dính CVE-2023-32681 (rò rỉ header "
                        "Proxy-Authorization qua redirect).\n"
                        "# Đây là \"lỗ hổng tầng thư viện\" mà Trivy/Grype sẽ bắt "
                        "được ở stage SCA.\n"
                        "requests==2.25.1",
                        "# Đã nâng lên bản vá CVE-2023-32681 và CVE-2024-35195.\n"
                        "requests==2.32.3",
                    ),
                ),
                summary="requests 2.25.1 → 2.32.3",
            )
        ],
        ripple=[
            "app/external.py là nơi duy nhất import requests, cần chạy lại test "
            "để chắc chắn hành vi không đổi",
        ],
    ),
    Patch(
        id="4/5",
        group="idor",
        title="Thiếu kiểm tra quyền và thiếu header bảo mật",
        cwe="CWE-639, CWE-693",
        reasoning=[
            "GET /api/user/<id>/profile trả về bản ghi bất kỳ theo id trên URL",
            "thêm kiểm tra phiên đăng nhập và quyền sở hữu bản ghi",
            "GET /api/admin/search cũng thiếu kiểm tra quyền quản trị",
            "app.run trong khối __main__ đang lắng nghe 0.0.0.0, thu về 127.0.0.1",
        ],
        changes=[
            Change(
                path="app/main.py",
                template="main.py.txt",
                summary="chặn IDOR, khoá endpoint quản trị, thu hẹp địa chỉ lắng nghe",
            ),
            Change(
                path="app/__init__.py",
                replacements=(('__version__ = "1.0.0"', '__version__ = "1.1.0"'),),
                summary="đánh phiên bản 1.1.0 cho bản vá",
            ),
        ],
        ripple=[
            "header bảo mật do cờ trong app/config.py điều khiển, đã bật ở bản vá 2/5",
        ],
    ),
    Patch(
        id="5/5",
        group="container",
        title="Cấu hình container và hạ tầng dưới dạng mã",
        cwe="CWE-250, CWE-284, CWE-732",
        reasoning=[
            "Dockerfile chạy quyền root trên base image python:3.9.7-slim đã cũ",
            "nâng base image, tạo appuser, chỉ copy thư mục app thay vì cả kho mã",
            "Terraform mở SSH và toàn dải cổng ra 0.0.0.0/0",
            "thu SSH về dải quản trị, chặn public access và bật mã hoá cho bucket",
        ],
        changes=[
            Change(
                path="Dockerfile",
                template="Dockerfile.txt",
                summary="chạy bằng appuser, nâng base image, thêm HEALTHCHECK",
            ),
            Change(
                path="infra/main.tf",
                template="main.tf.txt",
                summary="thu hẹp security group, khoá bucket, bật mã hoá",
            ),
        ],
        ripple=[
            "hai tệp này không được bộ test bắt lỗi — chúng chỉ được xác minh bởi "
            "Hadolint, Trivy và Checkov ở lần quét lại",
        ],
    ),
]


# ---------------------------------------------------------------------------
# Bản vá bổ sung, chỉ được áp dụng khi bộ kiểm thử đỏ.
# ---------------------------------------------------------------------------

REFINE_EXTERNAL = Patch(
    id="refine",
    group="secret",
    title="Sửa lại tác động lan toả của bản vá khoá bí mật",
    cwe="CWE-798",
    reasoning=[
        "traceback chỉ vào app/external.py dòng 17: ImportError ADMIN_API_KEY",
        "nguyên nhân: bản vá 2/5 đã gỡ hằng số này khỏi app/config.py",
        "không đưa hằng số quay lại — đọc biến môi trường ngay tại chỗ dùng",
    ],
    changes=[
        Change(
            path="app/external.py",
            template="external.py.txt",
            summary="đọc ADMIN_API_KEY từ biến môi trường tại thời điểm gọi",
        )
    ],
    ripple=[],
)
