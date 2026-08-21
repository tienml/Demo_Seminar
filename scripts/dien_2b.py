"""Dựng và dọn hiện trường cho chặng 2b — chốt chặn ở tầng git.

Vì sao cần script này: `app/transfer.py` đã được commit trên nhánh
`feature/lb-214-chuyen-tien`, nên `git add app/transfer.py` không stage được gì và
chốt `pre-commit` sẽ không có gì để soi. Chốt chỉ soi **file đang được đưa vào
commit** — đúng như thiết kế, để lỗi có sẵn từ trước không chặn người đang sửa một
chỗ khác.

Nên hiện trường phải là một thay đổi thật: script thêm một hàm vi phạm vào cuối
`app/transfer.py`, giống hệt lúc lập trình viên vừa nhận mã do AI sinh và định
commit.

    python scripts/dien_2b.py --dung      # thêm hàm vi phạm rồi stage
    git commit -m "them tim kiem nguoi nhan"    # <- bị chặn, đây là beat
    python scripts/dien_2b.py --don        # trả file về nguyên trạng

`--don` gọi `git restore` nên nó xoá mọi thay đổi chưa commit của
`app/transfer.py`, không chỉ đoạn script này thêm. Đừng chạy khi đang sửa file đó
bằng tay.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DICH = ROOT / "app" / "transfer.py"

DAU = "# --- BEGIN dien-2b ---"

DOAN_VI_PHAM = f'''

{DAU}
def tim_giao_dich_theo_ghi_chu(conn, tu_khoa):
    """Tra cuu giao dich theo ghi chu nguoi dung nhap."""
    cau = (
        "SELECT idempotency_key, amount_minor, note FROM transfers "
        "WHERE note LIKE '%" + tu_khoa + "%' ORDER BY created_at DESC"
    )
    return [dict(r) for r in conn.execute(cau).fetchall()]


def tinh_phi_chuyen_tien(than):
    """Phi chuyen tien = 0.1% so tien, toi thieu 1000 dong."""
    so_tien = float(than.get("amount", 0))
    return max(1000.0, so_tien * 0.001)
# --- END dien-2b ---
'''


def _git(*doi_so: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *doi_so], cwd=str(ROOT), capture_output=True, text=True
    )


def dung() -> int:
    noi_dung = DICH.read_text(encoding="utf-8")
    if DAU in noi_dung:
        print("Hiện trường đã dựng sẵn. Chạy --don trước nếu muốn dựng lại.")
        return 1

    DICH.write_text(noi_dung.rstrip("\n") + "\n" + DOAN_VI_PHAM, encoding="utf-8")
    tt = _git("add", "app/transfer.py")
    if tt.returncode != 0:
        print(tt.stderr, file=sys.stderr)
        return tt.returncode

    print("Đã thêm hai hàm vi phạm vào app/transfer.py và stage sẵn:")
    print("  - tim_giao_dich_theo_ghi_chu  → nối chuỗi vào SQL (§2.1, §2.2)")
    print("  - tinh_phi_chuyen_tien        → float cho tiền (§4.1)")
    print()
    print("Giờ chạy lệnh này trên sân khấu:")
    print('  git commit -m "them tim kiem nguoi nhan"')
    print()
    print("Dọn sau khi diễn:  python scripts/dien_2b.py --don")
    return 0


def don() -> int:
    _git("reset", "-q", "--", "app/transfer.py")
    tt = _git("restore", "--", "app/transfer.py")
    if tt.returncode != 0:
        print(tt.stderr, file=sys.stderr)
        return tt.returncode

    if DAU in DICH.read_text(encoding="utf-8"):
        print("Vẫn còn đoạn dựng trong file — kiểm tra bằng tay.", file=sys.stderr)
        return 1

    print("Đã trả app/transfer.py về nguyên trạng và bỏ stage.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Dựng/dọn hiện trường chặng 2b")
    nhom = p.add_mutually_exclusive_group(required=True)
    nhom.add_argument("--dung", action="store_true", help="thêm mã vi phạm và stage")
    nhom.add_argument("--don", action="store_true", help="trả file về nguyên trạng")
    args = p.parse_args()
    return dung() if args.dung else don()


if __name__ == "__main__":
    raise SystemExit(main())
