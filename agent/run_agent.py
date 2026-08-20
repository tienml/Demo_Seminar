"""Điều phối toàn bộ phần agent của buổi demo.

Chạy:  python agent/run_agent.py
Tuỳ chọn:
    --speed 0.6        chạy nhanh hơn khi tập (0 là bỏ hết độ trễ)
    --no-pause         không dừng ở checkpoint, dùng khi quay video hoặc kiểm thử
    --app-url URL      địa chỉ công khai; agent sẽ chờ bản vá xuất hiện ở đó
                       rồi mới dừng đồng hồ MTTR

Ranh giới cần nói rõ với khán giả: các bản vá ở đây là những thay đổi đã được
soạn sẵn và áp dụng theo kịch bản, còn toàn bộ phần XÁC MINH là thật — pytest
chạy trong tiến trình con trên mã vừa ghi xuống đĩa, payload tấn công được chạy
lại lên chính hàm xác thực, và bước cuối kiểm tra địa chỉ công khai thật.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent import console as c  # noqa: E402
from agent import dashboard  # noqa: E402
from agent import findings as fnd  # noqa: E402
from agent import patches as px  # noqa: E402
from agent import triage as tri  # noqa: E402
from agent import verify  # noqa: E402

STAGE_TOTAL = 6


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="AI Security Agent — demo seminar")
    p.add_argument("--speed", type=float, default=1.0,
                   help="hệ số độ trễ khi in log; 0 là chạy hết tốc lực")
    p.add_argument("--no-pause", action="store_true",
                   help="bỏ qua các checkpoint chờ Enter")
    p.add_argument("--app-url", default="",
                   help="địa chỉ công khai để xác minh bản vá đã lên production")
    return p.parse_args()


# ---------------------------------------------------------------------------


def stage_load() -> tuple[list[fnd.Finding], str]:
    dashboard.update(stage="Nạp kết quả quét từ pipeline", stage_index=1)
    c.section("CHẶNG 1 · NẠP KẾT QUẢ QUÉT")

    items, source = fnd.load()

    if source == "sarif":
        c.step("INPUT", f"đọc {len(list(fnd.FINDINGS_DIR.rglob('*.sarif')))} tệp SARIF "
                        f"trong findings/")
    else:
        c.warn("Không tìm thấy tệp SARIF nào trong findings/.")
        c.bullet("đang dùng bản kiểm kê dự phòng agent/baseline.json", symbol="!",
                 color=c.YELLOW)
        c.bullet("để lấy số liệu thật: gh run download <run-id> --dir findings",
                 symbol=" ", color=c.GREY)

    c.line()
    c.step("INPUT", "sáu công cụ, sáu định dạng báo cáo, một schema chung là SARIF")

    grouped = fnd.group_by_tool(items)
    rows = [[layer, str(len(fs)),
             ", ".join(sorted({f.tool for f in fs}))]
            for layer, fs in sorted(grouped.items(), key=lambda kv: -len(kv[1]))]
    c.line()
    c.table(["TẦNG", "SỐ CẢNH BÁO", "CÔNG CỤ"], rows, [14, 14, 30])

    counts = fnd.summarize(items)
    c.line()
    c.kv("Tổng số cảnh báo", str(len(items)), c.BOLD)
    c.kv("Nghiêm trọng (critical)", str(counts["critical"]), c.RED)
    c.kv("Cao (high)", str(counts["high"]), c.RED)
    c.kv("Trung bình (medium)", str(counts["medium"]), c.YELLOW)
    c.kv("Thấp / thông tin", str(counts["low"] + counts["info"]), c.GREY)

    dashboard.state().event(f"Nạp {len(items)} cảnh báo từ {source}")
    dashboard.update(total_findings=len(items))
    return items, source


def stage_triage(items: list[fnd.Finding]) -> tri.TriageResult:
    dashboard.update(stage="Phân loại theo khả năng khai thác", stage_index=2)
    c.section("CHẶNG 2 · PHÂN LOẠI THEO KHẢ NĂNG KHAI THÁC THỰC TẾ")

    c.step("TRIAGE", "dựng đồ thị lời gọi và đường đi của dữ liệu người dùng")
    c.step("TRIAGE", "đối chiếu từng cảnh báo với ba câu hỏi")
    c.bullet("cảnh báo này có trùng với công cụ khác không")
    c.bullet("đoạn mã có nằm trên đường đi từ input tới câu lệnh nguy hiểm không")
    c.bullet("thư viện đã có bản vá chưa, và có được nạp lúc chạy không")

    result = tri.run(items)

    c.line()
    c.line(f"  {c.BOLD}{result.total} cảnh báo{c.RESET} sau phân loại:", delay=0.2)
    c.line(f"    {c.GREEN}{len(result.nofix):>3}{c.RESET}  "
           f"{tri.BUCKET_LABELS[tri.NOFIX].lower()}")
    c.line(f"    {c.GREEN}{len(result.low):>3}{c.RESET}  "
           f"{tri.BUCKET_LABELS[tri.LOW].lower()}")
    c.line(f"    {c.RED}{len(result.actionable):>3}{c.RESET}  "
           f"{c.BOLD}{tri.BUCKET_LABELS[tri.ACT]}{c.RESET}")

    c.line()
    c.step("TRIAGE", "ví dụ vài quyết định loại bỏ, kèm lý do")
    for f in (result.nofix + result.low)[:4]:
        c.bullet(f"{c.GREY}{f.location:<28}{c.RESET} {f.rule_id}", symbol="·")
        c.bullet(f"{c.GREY}{f.triage_reason}{c.RESET}", symbol=" ")

    c.line()
    c.step("TRIAGE", "nhóm các cảnh báo cần xử lý theo bản vá chung")
    for group, items_in_group in result.groups.items():
        c.bullet(f"{tri.GROUP_TITLES[group]:<42} {len(items_in_group)} cảnh báo",
                 color=c.YELLOW)

    dashboard.state().event(
        f"Phân loại: {result.total} → {len(result.actionable)} cần xử lý"
    )
    dashboard.update(
        actionable=len(result.actionable),
        dismissed=len(result.nofix) + len(result.low),
    )
    return result


def _show_patch(patch: px.Patch) -> int:
    c.line()
    c.step(f"FIX {patch.id}", f"{c.BOLD}{patch.title}{c.RESET}  {c.GREY}({patch.cwe}){c.RESET}")
    for thought in patch.reasoning:
        c.bullet(thought, color=c.GREY)

    touched = 0
    for change in patch.changes:
        diff, added, removed = px.apply_change(change)
        touched += 1
        c.line()
        c.line(f"       {c.CYAN}{change.path}{c.RESET}  "
               f"{c.GREEN}+{added}{c.RESET} {c.RED}-{removed}{c.RESET}  "
               f"{c.GREY}{change.summary}{c.RESET}", delay=0.15)
        for row in diff[2:26]:
            if row.startswith("+"):
                c.line(f"         {c.GREEN}{row}{c.RESET}", delay=0.03)
            elif row.startswith("-"):
                c.line(f"         {c.RED}{row}{c.RESET}", delay=0.03)
            elif row.startswith("@@"):
                c.line(f"         {c.BLUE}{row}{c.RESET}", delay=0.03)
        if len(diff) > 26:
            c.line(f"         {c.GREY}... còn {len(diff) - 26} dòng khác trong diff{c.RESET}",
                   delay=0.05)

    for note in patch.ripple:
        c.line()
        c.line(f"       {c.YELLOW}⚠ tác động lan toả:{c.RESET} {note}", delay=0.2)

    return touched


def stage_fix() -> int:
    dashboard.update(stage="Áp dụng bản vá trên nhiều tầng", stage_index=3)
    c.section("CHẶNG 3 · ÁP DỤNG BẢN VÁ")

    files_touched = 0
    for patch in px.PATCHES:
        files_touched += _show_patch(patch)
        dashboard.update(fixed=int(patch.id.split("/")[0]))

    c.line()
    c.ok(f"Đã áp dụng {len(px.PATCHES)} bản vá trên {files_touched} tệp, "
         f"trải khắp mã ứng dụng, thư viện, container và hạ tầng.")
    dashboard.state().event(f"Áp dụng {len(px.PATCHES)} bản vá trên {files_touched} tệp")
    dashboard.render()
    return files_touched


def _run_and_report(label: str) -> verify.TestResult:
    c.step("VERIFY", f"{label}: chạy pytest trong tiến trình con trên mã vừa ghi")
    result = verify.run_pytest()
    tone = c.GREEN if result.ok else c.RED
    c.line(f"       {tone}{result.summary}{c.RESET}", delay=0.25)
    dashboard.update(tests_passed=result.passed, tests_failed=result.failed + result.errors)
    return result


def stage_verify() -> verify.TestResult:
    dashboard.update(stage="Kiểm thử và tự sửa lại", stage_index=4)
    c.section("CHẶNG 4 · KIỂM THỬ TRONG MÔI TRƯỜNG CÔ LẬP")

    result = _run_and_report("lần 1")

    if not result.ok:
        for name in result.failed_tests[:4]:
            c.fail(name)
        if result.key_error:
            c.line()
            c.line(f"       {c.RED}{result.key_error}{c.RESET}", delay=0.4)

        c.line()
        c.step("REFINE", "đọc traceback và truy nguyên nhân")
        for thought in px.REFINE_EXTERNAL.reasoning:
            c.bullet(thought, color=c.GREY)

        _show_patch(px.REFINE_EXTERNAL)
        dashboard.state().event("Bản vá đầu tiên làm đỏ test — agent tự sửa lại")

        c.line()
        result = _run_and_report("lần 2, sau khi tự sửa")

    if result.ok:
        c.ok(f"Toàn bộ {result.passed} bài kiểm thử đạt.")
    else:
        c.fail("Vẫn còn bài kiểm thử hỏng — cần người xem lại trước khi đi tiếp.")
        for name in result.failed_tests[:6]:
            c.bullet(name, color=c.RED)

    c.line()
    c.step("VERIFY", "chạy lại chính payload tấn công lên hàm xác thực")
    exploitable, payload = verify.exploit_still_works()
    c.line(f"       {c.GREY}payload:{c.RESET} {payload}", delay=0.2)
    if exploitable:
        c.fail("Payload VẪN đăng nhập được. Bản vá chưa đạt.")
    else:
        c.ok("Payload không còn đăng nhập được.")

    clean, leftovers = verify.secrets_removed()
    if clean:
        c.ok("Không còn khoá bí mật nhúng cứng trong mã nguồn.")
    else:
        for item in leftovers:
            c.fail(item)

    dashboard.update(exploitable=exploitable)
    dashboard.state().event(
        "Xác minh: test đạt, payload bị chặn" if result.ok and not exploitable
        else "Xác minh chưa đạt"
    )
    dashboard.render()
    return result


def stage_pull_request(result: verify.TestResult, triaged: tri.TriageResult) -> Path:
    dashboard.update(stage="Soạn Merge Request cho người duyệt", stage_index=5)
    c.section("CHẶNG 5 · SOẠN PULL REQUEST")

    body_path = ROOT / "artifacts" / "pull_request.md"
    body_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "## Tự động vá lỗ hổng bảo mật phát hiện trong pipeline",
        "",
        f"Agent xử lý {triaged.total} cảnh báo từ 6 công cụ quét, "
        f"xác định {len(triaged.actionable)} cảnh báo có đường khai thác thực tế, "
        f"và vá chúng bằng {len(px.PATCHES)} thay đổi.",
        "",
        "### Đã sửa",
        "",
    ]
    for patch in px.PATCHES:
        lines.append(f"- **{patch.title}** ({patch.cwe})")
        for change in patch.changes:
            lines.append(f"  - `{change.path}` — {change.summary}")
    lines += [
        f"- **{px.REFINE_EXTERNAL.title}** — `app/external.py`",
        "",
        "### Kết quả kiểm chứng",
        "",
        f"- pytest: {result.summary}",
        "- Payload `admin' OR '1'='1--` chạy lại lên hàm xác thực: không còn đăng nhập được",
        "- Không còn khoá bí mật nhúng cứng trong mã nguồn",
        "",
        "### Còn lại cho người duyệt",
        "",
        "- Ba khoá đã lộ phải được **thu hồi ở phía nhà cung cấp**; xoá khỏi mã nguồn",
        "  không làm chúng hết hiệu lực.",
        "- `var.admin_cidr` đang để mặc định `10.20.0.0/24`, cần đổi theo dải mạng thật.",
        "- Bản vá container và Terraform không được bộ test bắt lỗi, chỉ được xác minh",
        "  bởi Hadolint, Trivy và Checkov ở lần quét lại.",
    ]
    body = "\n".join(lines) + "\n"
    body_path.write_text(body, encoding="utf-8")

    for row in body.splitlines():
        c.line(f"  {c.GREY}│{c.RESET} {row}", delay=0.045)

    c.line()
    c.ok(f"Đã ghi nội dung MR ra {body_path.relative_to(ROOT)}")
    c.warn("Agent dừng ở đây. Việc merge và phê duyệt lên production là của con người.")
    dashboard.state().event("Soạn xong Pull Request, chờ người duyệt")
    dashboard.render()
    return body_path


def stage_production(app_url: str) -> None:
    dashboard.update(stage="Chờ bản vá lên địa chỉ công khai", stage_index=6)
    c.section("CHẶNG 6 · XÁC MINH TRÊN ĐỊA CHỈ CÔNG KHAI")

    if not app_url:
        c.warn("Không truyền --app-url nên bỏ qua bước kiểm tra production.")
        c.bullet("đồng hồ MTTR dừng tại mốc xác minh cục bộ", color=c.GREY)
        total = dashboard.stop_clock()
        dashboard.render()
        c.line()
        c.kv("MTTR (cục bộ)", dashboard.fmt(total), c.BOLD + c.GREEN)
        return

    url = app_url.rstrip("/") + "/version"
    c.step("DEPLOY", f"theo dõi {url}")
    c.bullet("bấm Approve trên GitHub Actions để mở cổng production", color=c.YELLOW)

    def patched_tolerant() -> bool:
        try:
            with urlopen(url, timeout=8) as resp:
                text = resp.read().decode("utf-8", "replace").lower()
            return '"patched"' in text and "true" in text.split('"patched"')[1][:12]
        except (URLError, TimeoutError, OSError, IndexError):
            return False

    reached = c.spinner_until("chờ bản vá xuất hiện trên production",
                              patched_tolerant, timeout=600)
    if not reached:
        c.fail("Hết thời gian chờ. Kiểm tra log deploy trên Render.")
        dashboard.render()
        return

    total = dashboard.stop_clock()
    dashboard.state().event("Bản vá đã lên production")
    dashboard.update(exploitable=False)

    c.line()
    c.ok("Địa chỉ công khai báo cáo trạng thái đã vá.")
    c.kv("MTTR toàn trình", dashboard.fmt(total), c.BOLD + c.GREEN)
    c.line()
    c.line(f"  {c.GREY}Mốc so sánh: báo cáo ngành ghi nhận thời gian vá trung bình "
           f"cho lỗ hổng mức High tính bằng tuần.{c.RESET}", delay=0.3)


# ---------------------------------------------------------------------------


def main() -> int:
    args = parse_args()
    c.configure(speed=args.speed, interactive=not args.no_pause)

    dashboard.update(stage="Khởi động", stage_index=0, stage_total=STAGE_TOTAL)

    c.banner("AI SECURITY AGENT", "LabBank · pipeline DevSecOps")
    c.kv("Kho mã", str(ROOT))
    c.kv("Bảng MTTR", str(dashboard.OUT_HTML.relative_to(ROOT)))
    c.kv("Chế độ", "dừng ở từng chặng" if not args.no_pause else "chạy liền mạch")
    if args.app_url:
        c.kv("Địa chỉ công khai", args.app_url)

    items, _ = stage_load()
    c.checkpoint("Nạp kết quả quét", "Phân loại theo khả năng khai thác")

    triaged = stage_triage(items)
    c.checkpoint("Phân loại cảnh báo", "Áp dụng bản vá trên năm tầng công nghệ")

    stage_fix()
    c.checkpoint("Áp dụng bản vá", "Chạy kiểm thử trong môi trường cô lập")

    result = stage_verify()
    c.checkpoint("Kiểm thử và tự sửa lại", "Soạn Pull Request cho người duyệt")

    stage_pull_request(result, triaged)
    c.checkpoint("Soạn Pull Request", "Xác minh bản vá trên địa chỉ công khai")

    stage_production(args.app_url)

    c.banner("KẾT THÚC PHẦN AGENT", "phần còn lại thuộc về con người", c.GREEN)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        c.line()
        c.warn("Đã dừng theo yêu cầu.")
        raise SystemExit(130)
