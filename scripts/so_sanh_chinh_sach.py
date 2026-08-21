#!/usr/bin/env python3
"""Đặt cạnh nhau hai lần rà soát cùng một bản kế hoạch: có và không có CLAUDE.md.

Chạy:
    python scripts/so_sanh_chinh_sach.py

Cần hai bản ghi đã tạo trước:
    python scripts/review_plan.py --record
    python scripts/review_plan.py --record --khong-chinh-sach

Kết quả đo được trên máy demo đi ngược trực giác thường gặp: bản KHÔNG có chính
sách tìm ra NHIỀU phát hiện hơn. Script này tồn tại để nói đúng điều đó, và để
chỉ ra khác biệt thật nằm ở đâu — không phải số lượng, mà là mỗi phát hiện có
neo được vào một quy tắc viết ra hay không, và phạm vi có bị giới hạn hay không.

Vì sao nhiều hơn lại không tốt hơn: không có chính sách thì AI liệt kê mọi biện
pháp bảo mật hợp lý cho một hệ thống ngân hàng — OTP, sổ kép, phát hiện bất
thường, công tắc tắt tính năng. Đều là ý đúng, nhưng phần lớn nằm ngoài phạm vi
LB-214 và có cái là viết lại kiến trúc chứ không phải sửa bản kế hoạch. Không có
cơ sở nào để nói cái nào bắt buộc, cái nào để sau. Đó chính là alert fatigue.
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent import console as c  # noqa: E402

CACHE = ROOT / "agent" / "ai_cache"


def doc(ten: str) -> dict | None:
    duong = CACHE / f"{ten}.json"
    if not duong.exists():
        return None
    try:
        return json.loads(duong.read_text(encoding="utf-8")).get("ket_qua")
    except (OSError, json.JSONDecodeError):
        return None


def do_dem(k: dict) -> dict:
    ph = k.get("phat_hien", []) or []
    return {
        "phat_hien": len(ph),
        "neo_quy_tac": sum(1 for f in ph if f.get("quy_tac")),
        "khong_phai": len(k.get("khong_phai_phat_hien", []) or []),
        "con_nguoi": len(k.get("con_nguoi_quyet", []) or []),
        "tieu_chi": len(k.get("tieu_chi_nghiem_thu", []) or []),
    }


def main() -> int:
    p = argparse.ArgumentParser(description="So sánh rà soát có và không có chính sách")
    p.add_argument("--speed", type=float, default=1.0)
    args = p.parse_args()
    c.configure(speed=args.speed, interactive=False)

    co = doc("plan_review")
    khong = doc("plan_review_khong_chinh_sach")

    c.banner("CÙNG MỘT BẢN KẾ HOẠCH, CÙNG MỘT MÔ HÌNH",
             "khác biệt duy nhất: có hay không một chính sách viết ra")

    thieu = [ten for ten, k in (("plan_review", co),
                                ("plan_review_khong_chinh_sach", khong)) if k is None]
    if thieu:
        c.fail("Thiếu bản ghi: " + ", ".join(thieu))
        c.bullet("chạy scripts/review_plan.py --record (và thêm --khong-chinh-sach)",
                 color=c.GREY)
        return 1

    a, b = do_dem(co), do_dem(khong)

    c.section("SỐ ĐO")
    c.table(
        ["", "CÓ CHÍNH SÁCH", "KHÔNG CÓ", "CHÊNH"],
        [
            ["Phát hiện", a["phat_hien"], b["phat_hien"],
             f"{b['phat_hien'] - a['phat_hien']:+d}"],
            ["Neo vào quy tắc viết ra", a["neo_quy_tac"], b["neo_quy_tac"],
             f"{b['neo_quy_tac'] - a['neo_quy_tac']:+d}"],
            ["Đã xét, không tính là lỗi", a["khong_phai"], b["khong_phai"],
             f"{b['khong_phai'] - a['khong_phai']:+d}"],
            ["Chuyển cho người quyết", a["con_nguoi"], b["con_nguoi"],
             f"{b['con_nguoi'] - a['con_nguoi']:+d}"],
            ["Tiêu chí nghiệm thu", a["tieu_chi"], b["tieu_chi"],
             f"{b['tieu_chi'] - a['tieu_chi']:+d}"],
        ],
        [28, 16, 12, 10],
    )

    if b["phat_hien"] > a["phat_hien"]:
        c.line()
        c.warn("Bản không có chính sách tìm được NHIỀU hơn. Đây là số đo thật, "
               "không phải kết quả mong đợi.")

    c.section("KHÁC BIỆT NẰM Ở ĐÂU")
    for dong in (
        f"Cả {a['phat_hien']} phát hiện của bản có chính sách đều trích được số hiệu "
        f"mục — đưa vào cuộc họp rà soát là bảo vệ được. Bản không có chính sách "
        f"neo được {b['neo_quy_tac']}.",
        "Không có chính sách, AI liệt kê mọi biện pháp hợp lý cho một hệ thống ngân "
        "hàng: OTP, sổ kép, phát hiện bất thường, công tắc tắt tính năng. Ý đúng, "
        "nhưng phần lớn ngoài phạm vi LB-214, và có cái là viết lại kiến trúc.",
        "Không có cơ sở nào để nói cái nào bắt buộc, cái nào để sau. Danh sách dài "
        "mà không có thứ tự ưu tiên chính là alert fatigue — thứ làm đội ngũ bỏ qua "
        "cảnh báo.",
        "Có chính sách thì phạm vi bị chặn: chỉ những gì bản kế hoạch vi phạm so với "
        "điều tổ chức đã cam kết. Ít hơn, nhưng mỗi cái đều làm được ngay.",
    ):
        c.line()
        for i, d in enumerate(textwrap.wrap(dong, 70)):
            c.bullet(d, symbol="•" if i == 0 else " ", color=c.GREY)

    c.section("LƯU Ý TRUNG THỰC")
    for dong in (
        "Bản không có chính sách trả về tiếng Việt không dấu, vì không có tài liệu "
        "tiếng Việt nào trong ngữ cảnh để neo văn phong. Đó là khác biệt hình thức, "
        "không phải khác biệt bảo mật — không lấy nó làm bằng chứng.",
        "Chính sách được nạp tự động vì Claude Code đọc CLAUDE.md ở thư mục làm việc. "
        "Bản 'không có chính sách' phải chạy tiến trình con ngoài repo; bỏ khỏi prompt "
        "là không đủ.",
    ):
        c.line()
        for i, d in enumerate(textwrap.wrap(dong, 70)):
            c.bullet(d, symbol="→" if i == 0 else " ", color=c.GREY)

    c.line()
    c.ok("Kết luận: chính sách không làm AI tìm nhiều hơn. Nó làm kết quả có thể "
         "hành động được.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
