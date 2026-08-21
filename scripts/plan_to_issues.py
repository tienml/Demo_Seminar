"""CHẶNG 1b — biến phát hiện ở tầng kế hoạch thành issue thật trên GitHub.

Đây là chỗ demo rời terminal lần đầu. Cùng một bộ phát hiện vừa hiện trên màn
hình đen giờ nằm trên bảng issue của repo công khai, có nhãn, có mức độ, có trích
dẫn quy tắc. Khán giả thấy AI không dừng ở việc "nói ra vấn đề" mà đẩy được vào
đúng công cụ mà đội ngũ vốn đã dùng.

Mặc định là CHẠY THỬ, không tạo gì:

    python scripts/plan_to_issues.py                        # xem trước
    python scripts/plan_to_issues.py --tao-that             # tạo issue thật
    python scripts/plan_to_issues.py --don-dep --tao-that   # đóng issue lần trước

Tạo issue là hành động công khai và khó rút lại — nội dung có thể đã bị index
trước khi kịp xoá. Vì vậy mặc định không tạo, và mỗi lần chạy đều in ra repo đích
để không bao giờ nhầm sang repo khác.

Mỗi issue đều ghi rõ ở cuối rằng nó do AI sinh ra từ bản kế hoạch và CHƯA có
người rà lại. Theo §1 của CLAUDE.md, "đã báo cáo" không được trình bày như "đã
kiểm chứng".
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent import console as c  # noqa: E402

CACHE = ROOT / "agent" / "ai_cache" / "plan_review.json"

# Dấu ẩn trong thân issue để biết issue nào do script này tạo, không đụng nhầm
# vào issue do người viết.
DAU = "<!-- lb214-plan-review -->"

# gh không nằm trên PATH của mọi shell trên máy này (PATH được sửa sau khi một số
# cửa sổ đã mở), nên dò thêm nơi đã cài thủ công.
NOI_CAI_GH = Path("D:/Seminar-DevSecOps/tools/bin/gh.exe")

NHAN_MUC_DO = {
    "nghiêm trọng": ("muc-do:nghiem-trong", "b60205", "Nghiêm trọng — chặn phát hành"),
    "cao": ("muc-do:cao", "d93f0b", "Cao"),
    "trung bình": ("muc-do:trung-binh", "fbca04", "Trung bình"),
    "thấp": ("muc-do:thap", "c2e0c6", "Thấp"),
}

NHAN_CHUNG = [
    ("bao-mat", "5319e7", "Phát hiện bảo mật"),
    ("chang:ke-hoach", "0e8a16", "Tìm ra ở tầng thiết kế, trước khi có mã"),
    ("can-nguoi-ra-lai", "e99695", "AI sinh ra, chưa có người xác nhận"),
]


def find_gh() -> str | None:
    for ten in ("gh", "gh.exe", "gh.cmd"):
        duong = shutil.which(ten)
        if duong:
            return duong
    return str(NOI_CAI_GH) if NOI_CAI_GH.exists() else None


def chay_gh(gh: str, doi_so: list[str], *, timeout: int = 60) -> tuple[bool, str]:
    try:
        tt = subprocess.run(
            [gh, *doi_so],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, f"hết {timeout}s chờ gh"
    except OSError as loi:
        return False, f"không chạy được gh: {loi}"
    if tt.returncode != 0:
        loi = (tt.stderr or tt.stdout or "").strip().splitlines()
        return False, loi[0] if loi else f"gh thoát mã {tt.returncode}"
    return True, (tt.stdout or "").strip()


def doc_ket_qua() -> dict | None:
    if not CACHE.exists():
        return None
    try:
        return json.loads(CACHE.read_text(encoding="utf-8")).get("ket_qua")
    except (OSError, json.JSONDecodeError):
        return None


def than_issue(f: dict, tieu_chi: list[dict]) -> str:
    """Dựng thân issue theo thứ tự người đọc cần: vấn đề gì, vì sao nguy hiểm, sẽ
    hỏng ra sao nếu cứ thế viết mã, sửa thế nào, bằng chứng nào là đã sửa xong."""
    ma = f.get("ma", "?")
    lien_quan = [t for t in tieu_chi if t.get("phat_hien") == ma]

    dong = [
        f"**Mức độ:** {f.get('muc_do', '?')}",
        f"**Quy tắc bị vi phạm:** {f.get('quy_tac') or '—'} (`CLAUDE.md`)",
        f"**CWE:** {f.get('cwe') or '—'}",
        f"**Mục trong bản kế hoạch:** {f.get('muc_ke_hoach') or '—'} "
        f"(`docs/plan/v1-chuyen-tien.md`)",
        "",
        "## Đường khai thác",
        "",
        str(f.get("ly_do", "")).strip() or "_không có mô tả_",
    ]

    if f.get("thanh_ma_gi"):
        dong += ["", "## Nếu cứ thế viết mã thì sẽ thành gì", "",
                 str(f["thanh_ma_gi"]).strip()]

    if f.get("cach_sua"):
        dong += ["", "## Sửa bản kế hoạch", "", str(f["cach_sua"]).strip()]

    if lien_quan:
        dong += ["", "## Tiêu chí nghiệm thu", "",
                 "Issue này chỉ được đóng khi các tiêu chí sau có test tự động "
                 "chứng minh, và test đó đã đỏ trước khi vá (§12.2):", ""]
        dong += [f"- [ ] **{t.get('ma', '?')}** — {t.get('noi_dung', '')}"
                 for t in lien_quan]

    dong += [
        "",
        "---",
        "",
        "Phát hiện ở tầng **thiết kế**, khi chưa có dòng mã nào tồn tại. Nguồn: "
        "`scripts/review_plan.py`, bản ghi tại `agent/ai_cache/plan_review.json`.",
        "",
        "> **Chưa được người rà lại.** Nội dung issue này do AI sinh ra từ bản kế "
        "hoạch. Theo §1 của `CLAUDE.md`, đây là *đã báo cáo*, không phải *đã kiểm "
        "chứng*. Gỡ nhãn `can-nguoi-ra-lai` sau khi có người xác nhận.",
        "",
        DAU,
    ]
    return "\n".join(dong)


def nhan_cua(f: dict) -> list[str]:
    ten = [n for n, _, _ in NHAN_CHUNG]
    muc = NHAN_MUC_DO.get(str(f.get("muc_do", "")).strip().lower())
    if muc:
        ten.append(muc[0])
    return ten


def dam_bao_nhan(gh: str) -> None:
    """Tạo nhãn nếu chưa có. gh label create báo lỗi khi nhãn đã tồn tại, nên
    dùng --force để lệnh chạy lại được nhiều lần mà không cần kiểm tra trước."""
    for ten, mau, mo_ta in list(NHAN_CHUNG) + list(NHAN_MUC_DO.values()):
        ok, loi = chay_gh(gh, ["label", "create", ten, "--color", mau,
                               "--description", mo_ta, "--force"])
        if ok:
            c.bullet(f"nhãn {ten}", symbol="·", color=c.GREY)
        else:
            c.warn(f"không tạo được nhãn {ten}: {loi}")


def tao_issue(gh: str, repo: str, args: argparse.Namespace) -> int:
    ket_qua = doc_ket_qua()
    if not ket_qua:
        c.fail(f"Chưa có bản ghi rà soát: {CACHE.relative_to(ROOT)}")
        c.bullet("chạy scripts/review_plan.py --record trước", color=c.GREY)
        return 1

    phat_hien = ket_qua.get("phat_hien", []) or []
    tieu_chi = ket_qua.get("tieu_chi_nghiem_thu", []) or []
    if args.gioi_han:
        phat_hien = phat_hien[: args.gioi_han]

    c.kv("Phát hiện", str(len(phat_hien)))
    c.kv("Chế độ", "TẠO THẬT" if args.tao_that else "xem trước, không tạo gì",
         c.RED if args.tao_that else c.GREEN)

    c.section("SẼ TẠO NHỮNG ISSUE SAU")
    c.table(
        ["MÃ", "MỨC ĐỘ", "QUY TẮC", "TIÊU ĐỀ"],
        [[f.get("ma", "?"), f.get("muc_do", "?"), f.get("quy_tac") or "—",
          f.get("tieu_de", "")] for f in phat_hien],
        [5, 15, 14, 44],
    )

    if not args.tao_that:
        c.line()
        c.ok("Chạy thử xong. Không có gì được tạo trên GitHub.")
        c.bullet("thêm --tao-that để tạo thật", color=c.GREY)
        return 0

    c.section("TẠO NHÃN")
    dam_bao_nhan(gh)

    c.section("TẠO ISSUE")
    da_tao: list[str] = []
    that_bai: list[tuple[str, str]] = []
    for f in phat_hien:
        ma = f.get("ma", "?")
        doi_so = ["issue", "create",
                  "--title", f"[{ma}] {f.get('tieu_de', '')}".strip(),
                  "--body", than_issue(f, tieu_chi)]
        for n in nhan_cua(f):
            doi_so += ["--label", n]

        ok, ket = chay_gh(gh, doi_so, timeout=90)
        if ok:
            da_tao.append(ket)
            c.ok(f"{ma}  {ket}")
        else:
            that_bai.append((ma, ket))
            c.fail(f"{ma}  {ket}")

    c.line()
    if da_tao:
        c.ok(f"{len(da_tao)} issue đã mở trên {repo}")
    if that_bai:
        c.fail(f"{len(that_bai)} issue không tạo được")
        for ma, loi in that_bai:
            c.bullet(f"{ma}: {loi}", color=c.GREY)
        return 1

    c.line()
    c.bullet("chiếu bảng issue:  gh issue list --label bao-mat --web", color=c.GREY)
    c.bullet("dọn sau khi tập:  python scripts/plan_to_issues.py --don-dep --tao-that",
             color=c.GREY)
    return 0


def don_dep(gh: str, args: argparse.Namespace) -> int:
    """Đóng issue của lần diễn trước. Đóng chứ không xoá: xoá không rút lại được,
    còn issue đã đóng thì đã biến khỏi bảng mặc định rồi."""
    c.section("DỌN ISSUE CỦA LẦN DIỄN TRƯỚC")

    ok, ket = chay_gh(gh, ["issue", "list", "--label", "chang:ke-hoach",
                           "--state", "open", "--limit", "100",
                           "--json", "number,title"])
    if not ok:
        c.fail(f"không liệt kê được issue: {ket}")
        return 1

    try:
        danh_sach = json.loads(ket or "[]")
    except json.JSONDecodeError:
        c.fail("gh trả về dữ liệu không đọc được")
        return 1

    if not danh_sach:
        c.ok("Không có issue nào cần dọn.")
        return 0

    c.kv("Sẽ đóng", f"{len(danh_sach)} issue")
    for i in danh_sach:
        c.bullet(f"#{i.get('number')} {i.get('title', '')}", symbol="·", color=c.GREY)

    if not args.tao_that:
        c.line()
        c.warn("Chạy thử — chưa đóng gì. Thêm --tao-that để đóng thật.")
        return 0

    c.line()
    for i in danh_sach:
        so = str(i.get("number"))
        ok, loi = chay_gh(gh, ["issue", "close", so, "--reason", "not planned",
                               "--comment", "Dọn sau buổi diễn tập."])
        if ok:
            c.ok(f"đã đóng #{so}")
        else:
            c.fail(f"#{so}: {loi}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(
        description="Đẩy phát hiện tầng kế hoạch lên GitHub thành issue")
    p.add_argument("--tao-that", action="store_true",
                   help="thật sự ghi lên GitHub (mặc định chỉ xem trước)")
    p.add_argument("--don-dep", action="store_true",
                   help="đóng các issue do script này tạo ở lần diễn trước")
    p.add_argument("--gioi-han", type=int, default=0,
                   help="chỉ xử lý N phát hiện đầu, dùng khi tập cho đúng nhịp")
    p.add_argument("--speed", type=float, default=1.0)
    args = p.parse_args()
    c.configure(speed=args.speed, interactive=False)

    c.banner("CHẶNG 1b · TỪ PHÁT HIỆN THÀNH ISSUE",
             "rời terminal, sang bảng công việc thật")

    gh = find_gh()
    if not gh:
        c.fail("Không tìm thấy gh trên máy.")
        c.bullet("cài rồi thì mở lại cửa sổ PowerShell để PATH có hiệu lực",
                 color=c.GREY)
        return 1

    ok, repo = chay_gh(gh, ["repo", "view", "--json", "nameWithOwner",
                            "--jq", ".nameWithOwner"])
    if not ok:
        c.fail(f"gh không đọc được repo: {repo}")
        return 1

    c.kv("gh", gh)
    c.kv("Repo đích", repo, c.YELLOW)

    return don_dep(gh, args) if args.don_dep else tao_issue(gh, repo, args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        c.warn("Đã dừng theo yêu cầu.")
        raise SystemExit(130)
