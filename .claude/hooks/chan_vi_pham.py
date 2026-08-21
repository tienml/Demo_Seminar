#!/usr/bin/env python3
"""Chốt chặn chính sách — chặn mã vi phạm trước khi nó nằm được trên đĩa.

Chặng 1 và 2 cho thấy AI *tìm ra* vi phạm sau khi mã đã tồn tại. File này là bước
sau: chính sách không còn là tài liệu để đọc mà thành một chốt chặn thật.

Hai cách dùng, cùng một bộ luật:

1. Hook PreToolUse của Claude Code. Claude Code gửi JSON của lời gọi công cụ qua
   stdin; thoát mã 2 nghĩa là chặn, và stderr được trả về cho mô hình đọc — nên
   thông báo dưới đây vừa giải thích cho người xem, vừa là chỉ dẫn để AI tự sửa
   rồi thử lại.

2. Quét file đã có trên đĩa, dùng trong pipeline hoặc chạy tay khi diễn:

       python .claude/hooks/chan_vi_pham.py --quet app/transfer.py
       python .claude/hooks/chan_vi_pham.py --quet app/

Nguyên tắc khi thêm luật: thà bỏ sót còn hơn chặn nhầm. Một lần chặn nhầm giữa
buổi diễn là mất nhịp, và tệ hơn, dạy người xem rằng chốt tự động hay báo bậy.
Mỗi mẫu dưới đây đều bám vào một dấu hiệu hẹp và đã có bộ ca thử đi kèm.
"""

from __future__ import annotations

import argparse
import ast
import io
import json
import re
import sys
import tokenize
from pathlib import Path

# Chỉ soi mã ứng dụng. Test và script diễn được phép chứa payload tấn công, chuỗi
# SQL xấu làm ví dụ, và số thẻ giả — chặn chúng thì không sửa được gì cả.
THU_MUC_SOI = ("app/",)

TU_KHOA_SQL = r"SELECT|INSERT\s+INTO|UPDATE\s+\w|DELETE\s+FROM"

# Mỗi luật: (tên, mẫu, mục chính sách, vì sao, sửa thế nào)
LUAT = [
    (
        "nối chuỗi vào câu SQL",
        # Hai hình dạng: f-string chứa câu lệnh SQL và có chỗ thay thế {...};
        # hoặc một chuỗi chứa câu lệnh SQL rồi được ghép bằng + hay % với biến.
        # Cửa sổ 200 ký tự có xuống dòng, vì câu lệnh thường trải nhiều dòng.
        re.compile(
            rf"""(?ixs)
              f(?P<nhay>["'])(?:(?!(?P=nhay)).){{0,200}}?
                (?:{TU_KHOA_SQL})
                (?:(?!(?P=nhay)).){{0,200}}?\{{
            |
              (?:{TU_KHOA_SQL})[\s\S]{{0,200}}?["']\s*(?:\+|%)\s*[A-Za-z_(]
            """
        ),
        "§2.1, §2.2",
        "Giá trị người dùng ghép thẳng vào câu lệnh thì dấu nháy trong dữ liệu "
        "trở thành cú pháp SQL.",
        "Dùng dấu ? và truyền giá trị qua tham số. Mẫu LIKE cũng phải bind: "
        'conn.execute("... LIKE ?", (f"%{q}%",)).',
    ),
    (
        "dùng float cho tiền",
        re.compile(r"(?i)float\s*\(\s*[^)]*(?:amount|tien|balance|so_du|gia)"),
        "§4.1",
        "Số thực dấu phẩy động không biểu diễn chính xác phần lẻ thập phân, sai "
        "số cộng dồn qua từng giao dịch.",
        "Nhận số tiền dạng chuỗi rồi chuyển sang Decimal, hoặc tính bằng số "
        "nguyên đơn vị nhỏ nhất.",
    ),
    (
        "ghi số thẻ vào log",
        # Lệnh log thường trải nhiều dòng nên phải cho phép xuống dòng. Bù lại,
        # chỉ nhận đúng các phương thức ghi log — getLogger đứng gần một cột
        # card_number trong lược đồ thì không tính.
        re.compile(
            r"(?is)(?:log|logger|logging)\."
            r"(?:info|debug|warning|warn|error|exception|critical)\s*\("
            r"[\s\S]{0,200}?card"
        ),
        "§6.1",
        "Log thường được sao sang hệ thống tập trung có phân quyền rộng hơn hệ "
        "thống lõi, ai đọc được log là thu hoạch được dữ liệu thẻ.",
        "Bỏ hẳn trường số thẻ khỏi log. Cần đối chiếu thì dùng mã tham chiếu nội bộ.",
    ),
    (
        "cột tiền kiểu REAL",
        re.compile(r"(?i)(?:amount|balance|so_du|tien)\w*\s+REAL\b"),
        "§4.1",
        "Cột REAL là số thực dấu phẩy động, sai số nằm sẵn trong lược đồ.",
        "Đổi sang INTEGER theo đơn vị nhỏ nhất, hoặc NUMERIC, và ghi rõ đơn vị.",
    ),
]


def _vi_tri_dau_dong(van_ban: str) -> list[int]:
    """Bảng tra: dòng thứ n (đếm từ 1) bắt đầu ở ký tự thứ mấy."""
    vi_tri = [0, 0]
    for dong in van_ban.splitlines(keepends=True):
        vi_tri.append(vi_tri[-1] + len(dong))
    return vi_tri


def _khoang_docstring(van_ban: str) -> list[tuple[int, int, int, int]]:
    """Vị trí của các docstring THẬT — không phải mọi chuỗi ba nháy.

    Phân biệt này là toàn bộ điểm khó. ``SCHEMA = \"\"\"CREATE TABLE ... amount
    REAL\"\"\"`` cũng là chuỗi ba nháy nhưng là mã có tác dụng thật và phải bị
    chặn. Chỉ câu lệnh chuỗi đứng đầu module/hàm/lớp mới là docstring, và chỉ
    cây cú pháp phân biệt được — regex thì không.
    """
    try:
        cay = ast.parse(van_ban)
    except (SyntaxError, ValueError):
        return []

    khoang = []
    for nut in ast.walk(cay):
        if not isinstance(
            nut, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            continue
        than = getattr(nut, "body", None) or []
        if not than:
            continue
        dau = than[0]
        if (
            isinstance(dau, ast.Expr)
            and isinstance(dau.value, ast.Constant)
            and isinstance(dau.value.value, str)
            and dau.end_lineno is not None
        ):
            khoang.append(
                (dau.lineno, dau.col_offset, dau.end_lineno, dau.end_col_offset)
            )
    return khoang


def _khoang_chu_thich(van_ban: str) -> list[tuple[int, int, int, int]]:
    """Vị trí của các chú thích ``#``. Bỏ qua êm nếu văn bản chưa hợp cú pháp."""
    khoang = []
    try:
        for tk in tokenize.generate_tokens(io.StringIO(van_ban).readline):
            if tk.type == tokenize.COMMENT:
                khoang.append((tk.start[0], tk.start[1], tk.end[0], tk.end[1]))
    except (tokenize.TokenError, IndentationError, SyntaxError, ValueError):
        pass
    return khoang


def bo_chu_thich(van_ban: str) -> str:
    """Xoá chú thích và docstring trước khi soi luật, giữ nguyên độ dài và số dòng.

    Vì sao cần: một câu dặn *"KHÔNG được viết ``float(amount)``"* nằm trong
    docstring không phải mã chạy được. Chặn nó là chặn nhầm, và chính file này
    đặt nguyên tắc thà bỏ sót còn hơn chặn nhầm (xem đầu file). Đây là ca báo
    nhầm đã gặp thật: hook chặn đúng một chú thích đang dặn *đừng* làm điều đó.

    Đánh đổi phải nói ra: mã vi phạm bị cố tình giấu trong chú thích rồi
    ``exec`` ra thì lớp này bỏ sót. Đó là cái giá của việc không báo nhầm, và là
    lý do vẫn cần lớp AI đọc ý định ở trên.

    Văn bản chưa hợp cú pháp (thường gặp khi Edit ghi một đoạn rời) thì trả về
    gần như nguyên trạng — vẫn soi được, chỉ là không lọc được chú thích.
    """
    khoang = _khoang_docstring(van_ban) + _khoang_chu_thich(van_ban)
    if not khoang:
        return van_ban

    dau_dong = _vi_tri_dau_dong(van_ban)
    ky_tu = list(van_ban)
    for dong_dau, cot_dau, dong_cuoi, cot_cuoi in khoang:
        if dong_cuoi >= len(dau_dong):
            continue
        bat_dau = dau_dong[dong_dau] + cot_dau
        ket_thuc = dau_dong[dong_cuoi] + cot_cuoi
        for i in range(bat_dau, min(ket_thuc, len(ky_tu))):
            if ky_tu[i] != "\n":
                ky_tu[i] = " "
    return "".join(ky_tu)


def soi(van_ban: str) -> list[tuple[str, str, str, str]]:
    sach = bo_chu_thich(van_ban)
    return [(ten, muc, vi_sao, sua)
            for ten, mau, muc, vi_sao, sua in LUAT if mau.search(sach)]


def trong_pham_vi(duong: str) -> bool:
    chuan = duong.replace("\\", "/")
    return any(t in chuan for t in THU_MUC_SOI)


def in_vi_pham(ten_file: str, vi_pham: list, dau_de: str) -> None:
    print(f"{dau_de} {ten_file} — vi phạm chính sách CLAUDE.md\n", file=sys.stderr)
    for ten, muc, vi_sao, sua in vi_pham:
        print(f"  [{muc}] {ten}", file=sys.stderr)
        print(f"      {vi_sao}", file=sys.stderr)
        print(f"      Cách sửa: {sua}\n", file=sys.stderr)


def noi_dung_ghi(du_lieu: dict) -> tuple[str, str]:
    """Lấy (đường dẫn, phần văn bản sắp được ghi) từ lời gọi công cụ."""
    dau_vao = du_lieu.get("tool_input") or {}
    duong = str(dau_vao.get("file_path", ""))
    phan = [dau_vao.get("content", ""), dau_vao.get("new_string", "")]
    for sua in dau_vao.get("edits", []) or []:
        phan.append(sua.get("new_string", ""))
    return duong, "\n".join(str(p) for p in phan if p)


def che_do_hook() -> int:
    try:
        du_lieu = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0  # Không đọc được thì không chặn — hook hỏng không được cản việc.

    if du_lieu.get("tool_name") not in ("Write", "Edit", "MultiEdit"):
        return 0

    duong, van_ban = noi_dung_ghi(du_lieu)
    if not van_ban or not trong_pham_vi(duong):
        return 0

    vi_pham = soi(van_ban)
    if not vi_pham:
        return 0

    in_vi_pham(duong.replace("\\", "/").rsplit("/", 1)[-1], vi_pham, "CHẶN GHI FILE")
    print("Sửa lại đoạn mã cho đúng chính sách rồi ghi lại. Không có ngoại lệ nào "
          "cho mã trong app/.", file=sys.stderr)
    return 2  # 2 = chặn lời gọi, stderr được trả về cho mô hình.


def che_do_quet(muc_tieu: list[str]) -> int:
    files: list[Path] = []
    for m in muc_tieu:
        p = Path(m)
        files.extend(sorted(p.rglob("*.py")) if p.is_dir() else [p])

    tong = 0
    for f in files:
        if not f.exists() or not trong_pham_vi(str(f)):
            continue
        vi_pham = soi(f.read_text(encoding="utf-8", errors="replace"))
        if vi_pham:
            tong += len(vi_pham)
            in_vi_pham(str(f).replace("\\", "/"), vi_pham, "VI PHẠM TRONG")

    if tong:
        print(f"Tổng cộng {tong} vi phạm. Không được phát hành khi còn vi phạm.",
              file=sys.stderr)
        return 1
    print("Không có vi phạm nào trong phạm vi quét.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(add_help=True)
    p.add_argument("--quet", nargs="+", metavar="ĐƯỜNG_DẪN",
                   help="quét file hoặc thư mục đã có trên đĩa thay vì chạy làm hook")
    args = p.parse_args()
    return che_do_quet(args.quet) if args.quet else che_do_hook()


if __name__ == "__main__":
    raise SystemExit(main())
