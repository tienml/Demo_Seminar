"""CHẶNG 1 — rà soát bản kế hoạch bằng AI, trước khi có dòng mã nào.

Đây là chặng trả lời cho câu hỏi đắt nhất của cả buổi: rẻ nhất thì nên tìm ra lỗ
hổng ở đâu? Không phải ở production, không phải ở pipeline, mà ở bản kế hoạch —
nơi việc sửa chỉ tốn công gõ lại một đoạn văn.

Trên sân khấu, chặng này chạy bằng một phiên claude tương tác (xem
docs/prompts/01-ra-soat-ke-hoach.md). Script này là lưới an toàn khi mạng hoặc
proxy chết giữa buổi, và là công cụ ghi lại kết quả AI thật ở nhà.

Chạy khi diễn (đọc bản đã ghi, tức thời, không cần mạng):
    python scripts/review_plan.py

Chạy ở nhà để ghi lại kết quả AI thật:
    python scripts/review_plan.py --record

Diễn với lời gọi AI trực tiếp, tự rơi về bản ghi nếu proxy chết:
    python scripts/review_plan.py --ai live

Chạy thêm một lần không có chính sách, để so sánh:
    python scripts/review_plan.py --record --khong-chinh-sach

Cờ đó cho tiến trình con chạy ở một thư mục tạm, vì Claude Code tự nạp CLAUDE.md
theo thư mục làm việc — bỏ chính sách khỏi prompt thôi là không đủ.

Số đo thực tế đi ngược trực giác và không được nói khác đi: bản KHÔNG có chính
sách tìm ra NHIỀU phát hiện hơn, 20 so với 13. Khác biệt thật nằm ở chỗ 13/13
phát hiện của bản có chính sách neo được vào một quy tắc viết ra, còn bản kia là
0/20. Xem scripts/so_sanh_chinh_sach.py.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import tempfile
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent import ai  # noqa: E402
from agent import console as c  # noqa: E402

TASK = "plan_review"

CHINH_SACH = ROOT / "CLAUDE.md"
KE_HOACH_MAC_DINH = ROOT / "docs" / "plan" / "v1-chuyen-tien.md"

CHI_THI = """\
Bạn rà soát bảo mật ở tầng THIẾT KẾ. Đầu vào qua stdin gồm hai phần: CHÍNH SÁCH \
bảo mật của dự án, và một BẢN KẾ HOẠCH tính năng chưa được triển khai.

Chưa có dòng mã nào tồn tại. Chỉ tìm những gì bản kế hoạch bỏ sót hoặc quy định \
sai so với chính sách. Mỗi phát hiện phải trích đúng số hiệu mục trong chính sách.

Theo mục §1 của chính sách, phải nêu cả những chỗ bản kế hoạch làm ĐÚNG mà bạn đã \
xem xét rồi quyết định không tính là phát hiện, và những việc bạn KHÔNG đủ dữ kiện \
để quyết theo §13.

Trả về DUY NHẤT một khối JSON, không kèm lời dẫn, theo đúng schema sau:

{
  "phat_hien": [
    {
      "ma": "F1",
      "tieu_de": "một câu ngắn dưới 60 ký tự",
      "muc_ke_hoach": "mục nào của bản kế hoạch, ví dụ §3.4",
      "quy_tac": "mục nào của chính sách, ví dụ §3.1",
      "cwe": "CWE-639",
      "muc_do": "nghiêm trọng | cao | trung bình | thấp",
      "ly_do": "đường khai thác thực tế, 1-3 câu",
      "thanh_ma_gi": "lỗi thiết kế này sẽ biến thành đoạn mã sai như thế nào",
      "cach_sua": "sửa bản kế hoạch ra sao, 1-2 câu"
    }
  ],
  "khong_phai_phat_hien": [
    { "muc": "mục nào của bản kế hoạch", "ly_do": "vì sao đã đạt yêu cầu" }
  ],
  "con_nguoi_quyet": [
    "việc mà AI không đủ dữ kiện để quyết, kèm lý do ngắn"
  ],
  "tieu_chi_nghiem_thu": [
    { "ma": "AC-1", "noi_dung": "phát biểu kiểm chứng được bằng test tự động", "phat_hien": "F1" }
  ]
}
"""

# Biến thể cho --khong-chinh-sach. Phải là một chỉ thị riêng chứ không dùng lại
# CHI_THI: bản trên nói rõ stdin có hai phần và bắt trích số hiệu mục chính sách,
# nên khi bỏ chính sách đi thì chỉ thị tự mâu thuẫn và AI trả về văn xuôi thay vì
# JSON. Quan trọng hơn, phép so sánh trên sân khấu phải công bằng: cùng bản kế
# hoạch, cùng mô hình, cùng schema, cùng yêu cầu về độ kỹ — khác biệt duy nhất là
# có hay không một tài liệu chính sách viết ra. Không được cố tình làm yếu bản này.
CHI_THI_KHONG_CHINH_SACH = """\
Bạn rà soát bảo mật ở tầng THIẾT KẾ. Đầu vào qua stdin là một BẢN KẾ HOẠCH tính \
năng chưa được triển khai. Không có tài liệu chính sách nào kèm theo.

Chưa có dòng mã nào tồn tại. Hãy tìm mọi vấn đề bảo mật mà bản kế hoạch bỏ sót \
hoặc quy định sai, dựa trên hiểu biết chung của bạn về bảo mật ứng dụng. Rà thật \
kỹ, đừng bỏ qua vấn đề nào bạn thấy được.

Nêu cả những chỗ bản kế hoạch làm ĐÚNG mà bạn đã xem xét rồi quyết định không \
tính là phát hiện, và những việc bạn KHÔNG đủ dữ kiện để quyết.

Trả về DUY NHẤT một khối JSON, không kèm lời dẫn, theo đúng schema sau. Trường \
"quy_tac" đặt là null vì không có chính sách để trích dẫn:

{
  "phat_hien": [
    {
      "ma": "F1",
      "tieu_de": "một câu ngắn dưới 60 ký tự",
      "muc_ke_hoach": "mục nào của bản kế hoạch, ví dụ §3.4",
      "quy_tac": null,
      "cwe": "CWE-639",
      "muc_do": "nghiêm trọng | cao | trung bình | thấp",
      "ly_do": "đường khai thác thực tế, 1-3 câu",
      "thanh_ma_gi": "lỗi thiết kế này sẽ biến thành đoạn mã sai như thế nào",
      "cach_sua": "sửa bản kế hoạch ra sao, 1-2 câu"
    }
  ],
  "khong_phai_phat_hien": [
    { "muc": "mục nào của bản kế hoạch", "ly_do": "vì sao đã đạt yêu cầu" }
  ],
  "con_nguoi_quyet": [
    "việc mà AI không đủ dữ kiện để quyết, kèm lý do ngắn"
  ],
  "tieu_chi_nghiem_thu": [
    { "ma": "AC-1", "noi_dung": "phát biểu kiểm chứng được bằng test tự động", "phat_hien": "F1" }
  ]
}
"""


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Rà soát bản kế hoạch bằng AI")
    p.add_argument("--ai", choices=[ai.CACHE, ai.LIVE, ai.OFF], default=ai.CACHE,
                   help="cache: đọc bản đã ghi (mặc định khi diễn); live: gọi thật")
    p.add_argument("--record", action="store_true",
                   help="gọi AI thật rồi ghi kết quả vào agent/ai_cache/")
    p.add_argument("--plan", default=str(KE_HOACH_MAC_DINH),
                   help="đường dẫn bản kế hoạch cần rà soát")
    p.add_argument("--khong-chinh-sach", action="store_true",
                   help="cố tình bỏ CLAUDE.md ra khỏi prompt, để so sánh trên sân khấu")
    p.add_argument("--model", default="", help="ghi đè mô hình, ví dụ claude-sonnet-5")
    p.add_argument("--timeout", type=int, default=ai.DEFAULT_TIMEOUT)
    p.add_argument("--speed", type=float, default=1.0)
    return p.parse_args()


def _bọc(text: str, thut: int = 9, rong: int = 66) -> list[str]:
    return textwrap.wrap(str(text), width=rong) or [""]


def _gon_cwe(gia_tri: object) -> str:
    """Lấy đúng mã CWE cho cột bảng, bỏ phần diễn giải dài.

    Có phát hiện thuộc quy trình chứ không thuộc lỗ hổng kỹ thuật (thiếu test âm,
    thiếu chốt phê duyệt), khi đó AI trả về cả một câu giải thích thay cho mã.
    Câu đó vẫn hiện đầy đủ ở khối chi tiết bên dưới, còn trong bảng thì thu về
    dấu gạch cho khỏi phá cột.
    """
    van_ban = str(gia_tri).strip()
    khop = re.search(r"CWE-\d+", van_ban)
    return khop.group(0) if khop else "—"


def _in_nhan(nguon: str, ghi_chu: str) -> None:
    mau = {ai.LIVE: c.GREEN, ai.CACHE: c.BLUE, ai.OFF: c.GREY, ai.FAIL: c.RED}
    c.line(f"  {mau.get(nguon, '')}[{ai.NHAN.get(nguon, nguon)}]{c.RESET}", delay=0.15)
    if ghi_chu:
        c.bullet(ghi_chu, symbol="!", color=c.YELLOW)


MAU_MUC_DO = {
    "nghiêm trọng": c.RED,
    "cao": c.RED,
    "trung bình": c.YELLOW,
    "thấp": c.GREY,
}


def main() -> int:
    args = parse_args()
    c.configure(speed=args.speed, interactive=False)

    ke_hoach = Path(args.plan)
    if not ke_hoach.exists():
        c.fail(f"Không tìm thấy bản kế hoạch: {ke_hoach}")
        return 1

    c.banner("CHẶNG 1 · RÀ SOÁT BẢN KẾ HOẠCH", "chưa có dòng mã nào tồn tại")

    van_ban_ke_hoach = ke_hoach.read_text(encoding="utf-8")
    c.kv("Bản kế hoạch", str(ke_hoach.relative_to(ROOT)))
    c.kv("Độ dài", f"{len(van_ban_ke_hoach.splitlines())} dòng")

    if args.khong_chinh_sach:
        van_ban_chinh_sach = ""
        c.kv("Chính sách", "KHÔNG NẠP (chế độ so sánh)", c.YELLOW)
    else:
        if not CHINH_SACH.exists():
            c.fail("Không tìm thấy CLAUDE.md")
            return 1
        van_ban_chinh_sach = CHINH_SACH.read_text(encoding="utf-8")
        so_quy_tac = sum(1 for d in van_ban_chinh_sach.splitlines() if d.startswith("**§"))
        c.kv("Chính sách", f"CLAUDE.md — {so_quy_tac} quy tắc", c.GREEN)

    phan = ["=== BẢN KẾ HOẠCH CẦN RÀ SOÁT ===", van_ban_ke_hoach]
    if van_ban_chinh_sach:
        phan = ["=== CHÍNH SÁCH BẢO MẬT DỰ ÁN ===", van_ban_chinh_sach] + phan
    tai_lieu = "\n\n".join(phan)

    mode = ai.LIVE if args.record else args.ai
    task = TASK if not args.khong_chinh_sach else TASK + "_khong_chinh_sach"

    c.line()
    if mode == ai.LIVE:
        c.step("AI", f"gọi claude trực tiếp, tối đa {args.timeout}s "
                     f"({len(tai_lieu):,} ký tự qua stdin)")
    else:
        c.step("AI", "đọc kết quả đã ghi lại")

    # Chạy tiến trình con ngoài repo khi diễn tình huống "không có chính sách".
    # Claude Code tự nạp CLAUDE.md ở thư mục làm việc, nên nếu vẫn để cwd là repo
    # thì chính sách vẫn vào ngữ cảnh dù ta đã bỏ nó khỏi stdin — và bảng kết quả
    # vẫn trích dẫn đúng số hiệu §, tức là phép so sánh trên sân khấu thành vô nghĩa.
    thu_muc_con: Path | None = None
    if args.khong_chinh_sach:
        thu_muc_con = Path(tempfile.mkdtemp(prefix="lb214-khong-chinh-sach-"))

    try:
        chi_thi = CHI_THI_KHONG_CHINH_SACH if args.khong_chinh_sach else CHI_THI
        ket_qua, nguon, ghi_chu = ai.hoi_json(
            task, chi_thi, tai_lieu,
            mode=mode, timeout=args.timeout, model=args.model, ghi=args.record,
            thu_muc=thu_muc_con,
        )
    finally:
        if thu_muc_con:
            shutil.rmtree(thu_muc_con, ignore_errors=True)

    _in_nhan(nguon, ghi_chu)

    if not ket_qua:
        c.fail("Không có kết quả để hiển thị.")
        if nguon == ai.FAIL:
            c.bullet("chạy lại với --record ở nơi có mạng để tạo bản ghi", color=c.GREY)
        return 1

    phat_hien = ket_qua.get("phat_hien", []) or []
    khong_phai = ket_qua.get("khong_phai_phat_hien", []) or []
    con_nguoi = ket_qua.get("con_nguoi_quyet", []) or []
    tieu_chi = ket_qua.get("tieu_chi_nghiem_thu", []) or []

    c.section(f"{len(phat_hien)} PHÁT HIỆN Ở TẦNG THIẾT KẾ")
    c.table(
        ["MÃ", "MỨC ĐỘ", "QUY TẮC", "CWE", "PHÁT HIỆN"],
        [[f.get("ma", "?"), f.get("muc_do", "?"), f.get("quy_tac") or "—",
          _gon_cwe(f.get("cwe", "")), f.get("tieu_de", "")] for f in phat_hien],
        [5, 15, 14, 9, 33],
    )

    for f in phat_hien:
        mau = MAU_MUC_DO.get(str(f.get("muc_do", "")).lower(), "")
        # Không có chính sách thì không có mục nào để "vi phạm" — bỏ hẳn cụm đó
        # thay vì in ra chữ None.
        quy_tac = f.get("quy_tac")
        cum_quy_tac = f" · vi phạm {quy_tac}" if quy_tac else ""
        c.line()
        c.step(f.get("ma", "?"),
               f"{c.BOLD}{f.get('tieu_de', '')}{c.RESET}  "
               f"{mau}{f.get('muc_do', '')}{c.RESET}  "
               f"{c.GREY}{f.get('cwe', '')}{cum_quy_tac}"
               f" · mục {f.get('muc_ke_hoach', '')}{c.RESET}")
        for dong in _bọc(f.get("ly_do", "")):
            c.bullet(dong, symbol=" ", color=c.GREY)
        if f.get("thanh_ma_gi"):
            for i, dong in enumerate(_bọc(f["thanh_ma_gi"])):
                c.bullet(dong, symbol="→" if i == 0 else " ", color=c.YELLOW)
        if f.get("cach_sua"):
            for i, dong in enumerate(_bọc(f["cach_sua"])):
                c.bullet(dong, symbol="✎" if i == 0 else " ", color=c.CYAN)

    if khong_phai:
        c.section("ĐÃ XEM XÉT NHƯNG KHÔNG TÍNH LÀ PHÁT HIỆN")
        c.line(f"  {c.GREY}Theo §1: không cảnh báo nào bị loại trong im lặng.{c.RESET}")
        for k in khong_phai:
            c.line()
            c.bullet(f"{c.GREEN}{k.get('muc', '')}{c.RESET}", symbol="✓")
            for dong in _bọc(k.get("ly_do", "")):
                c.bullet(dong, symbol=" ", color=c.GREY)

    if con_nguoi:
        c.section("AI KHÔNG ĐỦ DỮ KIỆN — NGƯỜI PHẢI QUYẾT")
        for viec in con_nguoi:
            for i, dong in enumerate(_bọc(viec)):
                c.bullet(dong, symbol="?" if i == 0 else " ", color=c.YELLOW)

    if tieu_chi:
        c.section(f"{len(tieu_chi)} TIÊU CHÍ NGHIỆM THU — ĐẦU VÀO CHO CHẶNG KIỂM THỬ")
        for t in tieu_chi:
            c.bullet(f"{c.BOLD}{t.get('ma', '?')}{c.RESET} {t.get('noi_dung', '')}"
                     f"  {c.GREY}({t.get('phat_hien', '-')}){c.RESET}", symbol="□")

    c.line()
    if nguon == ai.LIVE and args.record:
        c.ok(f"Đã ghi kết quả vào agent/ai_cache/{task}.json")
    c.ok(f"{len(phat_hien)} lỗ hổng tìm ra khi chưa tốn một dòng mã nào.")
    c.line()
    c.line(f"  {c.GREY}Bước tiếp: scripts/plan_to_issues.py để mở issue thật "
           f"trên GitHub.{c.RESET}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        c.warn("Đã dừng theo yêu cầu.")
        raise SystemExit(130)
