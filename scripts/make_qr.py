"""Sinh mã QR duy nhất cho buổi demo.

Chạy:  python scripts/make_qr.py https://labbank-demo.onrender.com
Tuỳ chọn:
    --no-check      bỏ qua bước gọi thử địa chỉ trước khi sinh QR
    --out-dir DIR   nơi ghi kết quả (mặc định artifacts/)

Sinh ra ba thứ trong artifacts/:
    qr.png          ảnh QR để dán vào slide
    qr.svg          bản vector, không vỡ khi phóng to hết cỡ máy chiếu
    qr_slide.html   một trang toàn màn hình, mở bằng trình duyệt rồi chiếu luôn

Ràng buộc quan trọng của kịch bản demo: **chỉ có đúng một mã QR** từ đầu đến
cuối. Khán giả quét một lần lúc mở màn, và cuối buổi bấm lại đúng cái nút đó
trên đúng trang đó để thấy lỗ hổng đã biến mất. Nếu giữa chừng xuất hiện mã QR
thứ hai, mọi người sẽ nghĩ đó là hai website khác nhau và toàn bộ hiệu ứng
"cùng một địa chỉ, trước và sau" sẽ mất.

Vì vậy script mặc định gọi thử địa chỉ trước khi vẽ QR. Một mã QR trỏ tới trang
lỗi, chiếu lên cho ba mươi người cùng quét, là kiểu hỏng không cứu được tại chỗ.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

SLIDE = """<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<title>LabBank · quét để tham gia</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; min-height: 100vh;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    background: #0a1226; color: #e8edf7;
    font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
    text-align: center; padding: 4vh 4vw;
  }}
  h1 {{ font-size: clamp(28px, 4.5vw, 60px); margin: 0 0 1.5vh; letter-spacing: -.02em; }}
  .sub {{ font-size: clamp(15px, 1.7vw, 24px); color: #8fa3c8; margin: 0 0 4vh; }}
  .qr {{
    background: #fff; padding: 2.4vh; border-radius: 20px;
    box-shadow: 0 0 80px rgba(80,140,255,.35);
  }}
  .qr img {{ display: block; width: min(46vh, 60vw); height: auto; }}
  .url {{
    margin-top: 3.5vh; font-family: "Cascadia Code", Consolas, monospace;
    font-size: clamp(15px, 1.9vw, 28px); color: #6ee7a8;
    background: rgba(110,231,168,.08); border: 1px solid rgba(110,231,168,.25);
    padding: .7em 1.2em; border-radius: 10px; word-break: break-all;
  }}
  .note {{
    margin-top: 3.5vh; max-width: 46em; font-size: clamp(13px, 1.4vw, 20px);
    line-height: 1.65; color: #8fa3c8;
  }}
  .note strong {{ color: #ffd166; font-weight: 600; }}
</style>
</head>
<body>
  <h1>Quét để cùng thử tấn công</h1>
  <p class="sub">Một địa chỉ duy nhất, dùng xuyên suốt buổi demo</p>

  <div class="qr"><img src="qr.png" alt="Mã QR dẫn tới ứng dụng demo"></div>

  <div class="url">{url}</div>

  <p class="note">
    Đầu buổi, bấm nút đỏ trên trang đó và bạn sẽ chiếm được quyền admin.
    Cuối buổi, sau khi AI tự vá lỗ hổng và bản vá được duyệt lên production,
    hãy bấm lại <strong>đúng cái nút đó, trên đúng địa chỉ này</strong>.
    Sẽ không có mã QR thứ hai.
  </p>
</body>
</html>
"""


def check_url(url: str) -> tuple[bool, str]:
    """Gọi thử /healthz rồi tới /version để biết địa chỉ có sống không."""
    base = url.rstrip("/")
    try:
        with urlopen(base + "/healthz", timeout=25) as resp:
            if resp.status != 200:
                return False, f"/healthz trả về HTTP {resp.status}"
    except HTTPError as exc:
        return False, f"/healthz trả về HTTP {exc.code}"
    except (URLError, TimeoutError, OSError) as exc:
        return False, f"không gọi được /healthz — {exc}"

    try:
        with urlopen(base + "/version", timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        return True, f"/healthz sống, nhưng không đọc được /version — {exc}"

    if data.get("patched"):
        return True, ("/version báo ĐÃ VÁ — địa chỉ này đang chạy bản vá. "
                      "Hãy deploy lại bản dính lỗ hổng trước khi demo.")
    return True, (f"/version báo còn khai thác được, payload "
                  f"{data.get('checked_payload', '?')} — đúng trạng thái mở màn.")


def main() -> int:
    ap = argparse.ArgumentParser(description="Sinh mã QR duy nhất cho buổi demo")
    ap.add_argument("url", help="địa chỉ công khai của ứng dụng, ví dụ https://...")
    ap.add_argument("--no-check", action="store_true",
                    help="không gọi thử địa chỉ trước khi sinh QR")
    ap.add_argument("--out-dir", default="artifacts",
                    help="thư mục ghi kết quả (mặc định artifacts/)")
    args = ap.parse_args()

    try:
        import segno
    except ImportError:
        print("Thiếu thư viện segno. Cài bằng:")
        print("    pip install segno")
        return 2

    url = args.url.strip()
    if not url.startswith(("http://", "https://")):
        print(f"Địa chỉ phải bắt đầu bằng http:// hoặc https:// — nhận được {url!r}")
        return 2

    out_dir = (ROOT / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Địa chỉ : {url}")

    if args.no_check:
        print("Kiểm tra: bỏ qua theo yêu cầu (--no-check)")
    else:
        print("Kiểm tra: đang gọi thử, lần đầu có thể mất ~50 giây vì Render ngủ...")
        alive, detail = check_url(url)
        print(f"          {'sống' if alive else 'KHÔNG SỐNG'} — {detail}")
        if not alive:
            print()
            print("Không sinh QR cho một địa chỉ không phản hồi. Sửa deploy trước,")
            print("hoặc chạy lại với --no-check nếu bạn chắc chắn địa chỉ đúng.")
            return 1

    # Mức sửa lỗi H chịu được khoảng 30% diện tích bị che — đủ để QR vẫn quét
    # được khi ai đó đứng chắn một góc máy chiếu.
    qr = segno.make(url, error="h")

    png = out_dir / "qr.png"
    svg = out_dir / "qr.svg"
    slide = out_dir / "qr_slide.html"

    qr.save(png, scale=16, border=4, dark="#0a1226", light="#ffffff")
    qr.save(svg, scale=16, border=4, dark="#0a1226", light="#ffffff")
    slide.write_text(SLIDE.format(url=url), encoding="utf-8")

    print()
    print(f"Đã ghi  : {png.relative_to(ROOT)}  ({png.stat().st_size / 1024:.0f} KB, "
          f"phiên bản QR {qr.version})")
    print(f"          {svg.relative_to(ROOT)}")
    print(f"          {slide.relative_to(ROOT)}")
    print()
    print("Mở trang chiếu bằng:")
    print(f"    start {slide}")
    print()
    print("Quét thử bằng chính điện thoại của bạn trước khi lên bục. Đây là mã QR")
    print("duy nhất của cả buổi — sẽ không có mã thứ hai xuất hiện sau đó.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
