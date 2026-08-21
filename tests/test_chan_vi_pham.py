"""Bộ ca thử cho chốt chặn chính sách `.claude/hooks/chan_vi_pham.py`.

Một chốt chặn báo nhầm còn tệ hơn không có chốt: giữa buổi diễn nó làm mất nhịp,
và nó dạy người xem rằng kiểm tra tự động hay báo bậy. Vì vậy mỗi luật đều phải
có cả ca PHẢI CHẶN lẫn ca PHẢI CHO QUA, và ca cho qua mới là phần quan trọng.

    python -m pytest tests/test_chan_vi_pham.py -q
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".claude" / "hooks" / "chan_vi_pham.py"

_spec = importlib.util.spec_from_file_location("chan_vi_pham", HOOK)
chan_vi_pham = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(chan_vi_pham)


PHAI_CHAN = [
    (
        "SQL nối chuỗi bằng f-string",
        'cau = f"SELECT * FROM accounts WHERE owner_name LIKE \'%{q}%\'"\n'
        "rows = conn.execute(cau).fetchall()",
    ),
    (
        "SQL nối chuỗi bằng dấu cộng",
        'conn.execute("SELECT * FROM users WHERE name = \'" + ten + "\'")',
    ),
    (
        # Đúng hình dạng của tim_nguoi_nhan_nhanh trong app/transfer.py: câu lệnh
        # trải nhiều dòng nên mẫu regex phải cho phép xuống dòng.
        "SQL nối chuỗi vắt qua nhiều dòng",
        "cau = (\n"
        '    "SELECT number, owner_name FROM accounts "\n'
        '    "WHERE owner_name LIKE \'%" + tu_khoa + "%\' ORDER BY owner_name"\n'
        ")",
    ),
    ("float cho tiền", 'so_tien_minor = int(float(than.get("amount", 0)) * 100)'),
    (
        "log có số thẻ",
        'log.info("[TRANSFER] user=%s card=%s", uid, src["card_number"])',
    ),
    (
        "log có số thẻ, trải nhiều dòng",
        "log.info(\n"
        '    "[TRANSFER] user_id=%s from=%s card=%s",\n'
        '    uid, _che(so_nguon), src["card_number"],\n'
        ")",
    ),
    ("cột tiền kiểu REAL", "CREATE TABLE transfers (amount REAL NOT NULL)"),
]

PHAI_CHO_QUA = [
    (
        "SQL truyền tham số",
        'conn.execute("SELECT * FROM accounts WHERE number = ?", (so,))',
    ),
    (
        "mẫu LIKE truyền tham số",
        'conn.execute("SELECT number FROM accounts WHERE owner_name LIKE ?",\n'
        '             (f"%{tu_khoa}%",))',
    ),
    ("cột tiền kiểu INTEGER", "CREATE TABLE transfers (amount_minor INTEGER NOT NULL)"),
    (
        "log đã che số tài khoản",
        'log.info("[TRANSFER] user=%s from=%s", uid, _che(so_nguon))',
    ),
    (
        # getLogger đứng gần một cột tên card_number trong lược đồ không phải là
        # ghi số thẻ vào log; đây là ca báo nhầm dễ mắc nhất.
        "getLogger đứng gần cột card_number",
        "log = logging.getLogger(__name__)\n"
        'SCHEMA = """\n'
        "CREATE TABLE accounts (\n"
        "    card_number   TEXT    NOT NULL\n"
        ');\n"""',
    ),
    ("Decimal cho tiền", 'so_tien = Decimal(str(than.get("amount", "0")))'),
    ("float cho thứ không phải tiền", 'ty_le = float(cau_hinh.get("ty_le", 0))'),
]


@pytest.mark.parametrize("ten,ma", PHAI_CHAN, ids=[t for t, _ in PHAI_CHAN])
def test_chan_duoc_ma_vi_pham(ten, ma):
    assert chan_vi_pham.soi(ma), f"bỏ sót: {ten}"


@pytest.mark.parametrize("ten,ma", PHAI_CHO_QUA, ids=[t for t, _ in PHAI_CHO_QUA])
def test_khong_bao_nham_ma_dung(ten, ma):
    vi_pham = chan_vi_pham.soi(ma)
    assert not vi_pham, f"báo nhầm {ten}: {[v[0] for v in vi_pham]}"


@pytest.mark.parametrize(
    "duong,trong",
    [
        ("app/transfer.py", True),
        ("D:\\Seminar-DevSecOps\\devsecops-ai-demo\\app\\auth.py", True),
        # Test và script diễn được phép chứa payload tấn công làm ví dụ.
        ("tests/test_transfer.py", False),
        ("scripts/review_plan.py", False),
        ("docs/plan/v1-chuyen-tien.md", False),
    ],
)
def test_pham_vi_chi_gom_ma_ung_dung(duong, trong):
    assert chan_vi_pham.trong_pham_vi(duong) is trong


def _goi_hook(duong: str, noi_dung: str) -> int:
    goi = json.dumps(
        {"tool_name": "Write", "tool_input": {"file_path": duong, "content": noi_dung}}
    )
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=goi,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).returncode


def test_hook_thoat_ma_2_khi_chan():
    """Claude Code chỉ coi là chặn khi mã thoát đúng bằng 2."""
    assert _goi_hook("app/transfer.py", 'x = float(than["amount"])') == 2


def test_hook_thoat_ma_0_khi_cho_qua():
    assert _goi_hook("app/transfer.py", "x = 1") == 0


def test_hook_khong_gay_can_khi_dau_vao_hong():
    """Hook hỏng không được cản việc: stdin không phải JSON thì cho qua."""
    tt = subprocess.run(
        [sys.executable, str(HOOK)],
        input="khong phai json",
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert tt.returncode == 0


def test_quet_bat_duoc_vi_pham_trong_transfer():
    """Chế độ quét là đường dự phòng khi hook của Claude Code không kích hoạt."""
    tt = subprocess.run(
        [sys.executable, str(HOOK), "--quet", "app/"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert tt.returncode == 1
    assert "transfer.py" in tt.stderr
