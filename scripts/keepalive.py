"""Giữ cho service Render free không ngủ trong lúc seminar diễn ra.

Chạy:  python scripts/keepalive.py https://labbank-demo.onrender.com
Tuỳ chọn:
    --every 240     số giây giữa hai lần ping (mặc định 240)
    --quiet         chỉ in khi có bất thường

Gói free của Render cho service ngủ sau khoảng 15 phút không có request, và lần
đánh thức kế tiếp mất tầm 50 giây. Năm mươi giây im lặng ngay lúc ba mươi người
vừa quét QR là quãng chết dài nhất bạn có thể gặp trên bục.

Cách dùng: mở một cửa sổ terminal riêng, chạy script này khoảng 30 phút TRƯỚC
giờ bắt đầu, và cứ để nó chạy suốt buổi. Ctrl+C khi xong.

Script cũng theo dõi trạng thái vá của ứng dụng qua /version. Nếu trạng thái đổi
giữa chừng, nó in ra một dòng nổi bật — hữu ích ở đoạn cuối, vì đây là tín hiệu
độc lập cho biết bản vá đã thật sự lên tới production, không phải nghe agent tự
báo cáo.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

# Ngưỡng phân biệt "service đang thức" với "vừa phải đánh thức từ trạng thái ngủ".
COLD_START_SECONDS = 8.0


def ping(base: str, timeout: int) -> tuple[bool, float, bool | None, str]:
    """Trả về (thành công, số giây, đã vá hay chưa, ghi chú)."""
    started = time.monotonic()
    try:
        with urlopen(base + "/version", timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            status = resp.status
    except HTTPError as exc:
        return False, time.monotonic() - started, None, f"HTTP {exc.code}"
    except (URLError, TimeoutError, OSError) as exc:
        return False, time.monotonic() - started, None, str(exc)[:80]

    elapsed = time.monotonic() - started
    if status != 200:
        return False, elapsed, None, f"HTTP {status}"

    try:
        data = json.loads(raw)
    except ValueError:
        return True, elapsed, None, "phản hồi không phải JSON"

    return True, elapsed, bool(data.get("patched")), ""


def main() -> int:
    ap = argparse.ArgumentParser(description="Ping định kỳ để service không ngủ")
    ap.add_argument("url", help="địa chỉ công khai của ứng dụng")
    ap.add_argument("--every", type=int, default=240,
                    help="số giây giữa hai lần ping (mặc định 240)")
    ap.add_argument("--timeout", type=int, default=90,
                    help="thời gian chờ tối đa mỗi lần ping")
    ap.add_argument("--quiet", action="store_true",
                    help="chỉ in khi có bất thường hoặc khi trạng thái đổi")
    args = ap.parse_args()

    base = args.url.rstrip("/")
    if not base.startswith(("http://", "https://")):
        print(f"Địa chỉ phải bắt đầu bằng http:// hoặc https:// — nhận được {base!r}")
        return 2

    print(f"Giữ thức : {base}")
    print(f"Nhịp ping: {args.every} giây")
    print("Ctrl+C để dừng.\n")

    last_patched: bool | None = None
    fails = 0
    n = 0

    try:
        while True:
            n += 1
            ok, elapsed, patched, note = ping(base, args.timeout)
            stamp = datetime.now().strftime("%H:%M:%S")

            if not ok:
                fails += 1
                print(f"[{stamp}] LỖI  lần {n} — {note}  (hỏng liên tiếp: {fails})")
            else:
                fails = 0
                trang_thai = "đã vá" if patched else "còn khai thác được"
                cold = "  ← vừa đánh thức từ trạng thái ngủ" \
                    if elapsed >= COLD_START_SECONDS else ""
                if patched != last_patched and last_patched is not None:
                    print()
                    print(f"[{stamp}] *** TRẠNG THÁI ĐỔI: {trang_thai} ***")
                    print()
                elif not args.quiet:
                    print(f"[{stamp}] ok   {elapsed:5.2f}s  · {trang_thai}{cold}")
                last_patched = patched

            if fails == 3:
                print()
                print("Ba lần hỏng liên tiếp. Kiểm tra log deploy trên Render trước")
                print("khi lên bục — mã QR đang trỏ tới một địa chỉ không phản hồi.")
                print()

            time.sleep(args.every)
    except KeyboardInterrupt:
        print(f"\nĐã dừng sau {n} lần ping.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
