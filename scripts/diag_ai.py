"""Chẩn đoán đường gọi ``claude -p``: đo thời gian và tách nguyên nhân lỗi.

Vấn đề cần tách: khi ``--record`` hết thời gian chờ, đó là vì prompt quá dài, vì
mô hình chậm, hay vì CLI không nhận nội dung qua stdin? Ba biến thể dưới đây thay
đổi mỗi lần một biến số.

    python scripts/diag_ai.py --variant tiny                    # gọi ngắn nhất
    python scripts/diag_ai.py --variant medium                  # stdin nhỏ
    python scripts/diag_ai.py --variant full --timeout 300      # đúng prompt thật

Thêm --model claude-sonnet-5 để thử mô hình nhanh hơn.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent import ai  # noqa: E402

CHI_THI_NGAN = 'Trả về đúng JSON này, không thêm gì khác: {"ok": true}'

CHI_THI_JSON = """\
Đọc tài liệu trong stdin. Trả về DUY NHẤT một khối JSON, không lời dẫn:
{"so_muc": <số mục có ký hiệu § đếm được>, "chu_de": "<chủ đề tài liệu, 5 từ>"}
"""


def dung_tai_lieu(variant: str) -> str:
    if variant == "tiny":
        return ""
    if variant == "medium":
        return "=== TÀI LIỆU ===\n" + (ROOT / "CLAUDE.md").read_text(
            encoding="utf-8"
        )[:1500]
    chinh_sach = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    ke_hoach = (ROOT / "docs" / "plan" / "v1-chuyen-tien.md").read_text(encoding="utf-8")
    return (
        "=== CHÍNH SÁCH BẢO MẬT DỰ ÁN ===\n" + chinh_sach
        + "\n\n=== BẢN KẾ HOẠCH CẦN RÀ SOÁT ===\n" + ke_hoach
    )


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--variant", choices=["tiny", "medium", "full"], default="tiny")
    p.add_argument("--timeout", type=int, default=180)
    p.add_argument("--model", default="")
    args = p.parse_args()

    claude = ai.find_claude()
    print(f"[claude]  {claude or 'KHÔNG TÌM THẤY'}")
    if not claude:
        return 1

    tai_lieu = dung_tai_lieu(args.variant)
    chi_thi = CHI_THI_NGAN if args.variant == "tiny" else CHI_THI_JSON

    print(f"[biến thể] {args.variant}")
    print(f"[stdin]    {len(tai_lieu):,} ký tự")
    print(f"[chỉ thị]  {len(chi_thi):,} ký tự")
    print(f"[mô hình]  {args.model or '(mặc định trong settings)'}")
    print(f"[timeout]  {args.timeout}s")
    print("[đang gọi] ...", flush=True)

    bat_dau = time.time()
    text, loi = ai._goi_claude(
        chi_thi, tai_lieu, timeout=args.timeout, model=args.model
    )
    giay = time.time() - bat_dau

    print(f"[xong sau] {giay:.1f}s")
    if loi:
        print(f"[LỖI]     {loi}")
        return 1
    print(f"[thô]     {len(text):,} ký tự")
    print(f"[đầu ra]  {text.strip()[:300]}")
    print(f"[bóc JSON] {ai.boc_json(text)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
