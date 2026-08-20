"""Đưa kho mã về đúng trạng thái trước khi demo.

Chạy:  python scripts/reset_demo.py

Khôi phục mọi tệp mà agent đã ghi đè (lấy từ `.demo-backup/`), xoá các sản phẩm
sinh ra trong lúc chạy, rồi kiểm chứng lại rằng ứng dụng đã dính lỗ hổng trở
lại. Bước kiểm chứng cuối là quan trọng: nó ngăn tình huống bạn lên bục với một
kho mã tưởng là đã reset nhưng thực ra vẫn còn bản vá của lần chạy trước.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Console Windows mặc định dùng cp1252 nên mọi log tiếng Việt sẽ ném
# UnicodeEncodeError. Ép UTF-8 ngay từ đầu, trước lần in đầu tiên.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

BACKUP = ROOT / ".demo-backup"

DISPOSABLE_FILES = [
    "app/labbank.db",
    "dashboard/index.html",
    "dashboard/state.json",
    "artifacts/pull_request.md",
]

DISPOSABLE_DIRS = [
    "app/__pycache__",
    "agent/__pycache__",
    "tests/__pycache__",
    ".pytest_cache",
]


def restore() -> list[str]:
    if not BACKUP.exists():
        return []
    restored: list[str] = []
    for src in sorted(BACKUP.rglob("*")):
        if src.is_dir():
            continue
        rel = src.relative_to(BACKUP)
        dst = ROOT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        restored.append(str(rel).replace("\\", "/"))
    shutil.rmtree(BACKUP, ignore_errors=True)
    return restored


def clean() -> list[str]:
    removed: list[str] = []
    for rel in DISPOSABLE_FILES:
        path = ROOT / rel
        if path.exists():
            path.unlink()
            removed.append(rel)
    for rel in DISPOSABLE_DIRS:
        path = ROOT / rel
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
            removed.append(rel + "/")
    return removed


def main() -> int:
    restored = restore()
    removed = clean()

    if restored:
        print(f"Đã khôi phục {len(restored)} tệp về bản gốc:")
        for rel in restored:
            print(f"  - {rel}")
    else:
        print("Không có tệp nào cần khôi phục (agent chưa chạy lần nào).")

    if removed:
        print(f"Đã xoá {len(removed)} mục sinh ra lúc chạy.")

    # Nạp verify SAU khi khôi phục để nó chạy trên mã đã về trạng thái gốc.
    from agent import verify

    exploitable, payload = verify.exploit_still_works()
    print()
    if exploitable:
        print(f"Kiểm chứng: payload {payload} đăng nhập được → ứng dụng đã trở lại")
        print("trạng thái dính lỗ hổng. Sẵn sàng cho lần demo tiếp theo.")
        return 0

    print("CẢNH BÁO: payload không còn đăng nhập được, nghĩa là kho mã VẪN đang ở")
    print("trạng thái đã vá. Kiểm tra lại app/auth.py trước khi lên trình bày.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
