"""Lớp hiển thị terminal cho demo seminar.

Hai thứ quan trọng nhất ở đây phục vụ nhịp thuyết trình chứ không phải kỹ thuật:

* `checkpoint()` dừng agent lại giữa các chặng và chờ người trình bày bấm Enter.
  Nhờ vậy nhịp demo do người nói cầm, không do tốc độ của máy cầm.
* `line()` in ra có độ trễ chủ động để mắt khán giả cuối phòng kịp bám theo.
  Đặt `--speed 0` khi chạy thử để bỏ toàn bộ độ trễ.
"""

from __future__ import annotations

import os
import sys
import time

# Bật xử lý mã màu ANSI trên Windows Terminal / conhost đời cũ.
if os.name == "nt":
    os.system("")

# Console Windows mặc định dùng cp1252 nên mọi log tiếng Việt sẽ ném
# UnicodeEncodeError. Ép UTF-8 ngay khi nạp module, trước lần in đầu tiên.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

RESET = "\033[0m"
DIM = "\033[2m"
BOLD = "\033[1m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
GREY = "\033[90m"

WIDTH = 78

_settings = {"speed": 1.0, "interactive": True}


def configure(speed: float = 1.0, interactive: bool = True) -> None:
    _settings["speed"] = max(0.0, speed)
    _settings["interactive"] = interactive


def _pause(seconds: float) -> None:
    delay = seconds * _settings["speed"]
    if delay > 0:
        time.sleep(delay)


def line(text: str = "", color: str = "", delay: float = 0.05) -> None:
    """In một dòng log rồi nghỉ một nhịp ngắn."""
    sys.stdout.write(f"{color}{text}{RESET}\n" if color else f"{text}\n")
    sys.stdout.flush()
    _pause(delay)


def typed(text: str, color: str = CYAN, cps: int = 90) -> None:
    """Gõ từng ký tự. Dành cho các dòng cần nhấn mạnh, không dùng tràn lan."""
    if _settings["speed"] == 0:
        line(text, color, delay=0)
        return
    sys.stdout.write(color)
    for ch in text:
        sys.stdout.write(ch)
        sys.stdout.flush()
        time.sleep(1.0 / cps)
    sys.stdout.write(RESET + "\n")
    sys.stdout.flush()


def banner(title: str, subtitle: str = "", color: str = BLUE) -> None:
    line()
    line("╔" + "═" * WIDTH + "╗", color, delay=0)
    line("║" + title.center(WIDTH) + "║", color + BOLD, delay=0)
    if subtitle:
        line("║" + subtitle.center(WIDTH) + "║", color, delay=0)
    line("╚" + "═" * WIDTH + "╝", color, delay=0.3)


def section(text: str, color: str = CYAN) -> None:
    line()
    line(f"── {text} " + "─" * max(0, WIDTH - len(text) - 4), color, delay=0.15)


def step(tag: str, text: str, color: str = "") -> None:
    line(f"  {GREY}[{tag}]{RESET} {color}{text}{RESET}", delay=0.12)


def bullet(text: str, symbol: str = "→", color: str = "") -> None:
    line(f"       {symbol} {color}{text}{RESET}", delay=0.1)


def ok(text: str) -> None:
    line(f"  {GREEN}✓{RESET} {text}", delay=0.12)


def fail(text: str) -> None:
    line(f"  {RED}✗{RESET} {text}", delay=0.18)


def warn(text: str) -> None:
    line(f"  {YELLOW}!{RESET} {text}", delay=0.12)


def kv(label: str, value: str, color: str = "") -> None:
    line(f"  {GREY}{label:.<34}{RESET} {color}{value}{RESET}", delay=0.08)


def progress(label: str, seconds: float, width: int = 40) -> None:
    """Thanh tiến trình cho các bước chờ thật (cài đặt, chạy test, deploy).

    Có thứ gì đó chuyển động trên màn hình là điều kiện đủ để khán giả kiên nhẫn;
    màn hình đứng yên mới là thứ làm họ mất tập trung.
    """
    total = seconds * _settings["speed"]
    if total <= 0:
        ok(label)
        return
    start = time.time()
    while True:
        elapsed = time.time() - start
        ratio = min(1.0, elapsed / total)
        filled = int(width * ratio)
        bar = "█" * filled + "░" * (width - filled)
        sys.stdout.write(f"\r  {CYAN}{bar}{RESET} {label} {int(ratio * 100):3d}%")
        sys.stdout.flush()
        if ratio >= 1.0:
            break
        time.sleep(0.05)
    sys.stdout.write("\r" + " " * (width + len(label) + 16) + "\r")
    ok(label)


def spinner_until(label: str, is_done, timeout: float = 300.0) -> bool:
    """Quay vòng chờ một điều kiện thật trở thành đúng (dùng khi chờ deploy)."""
    frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    start = time.time()
    i = 0
    while time.time() - start < timeout:
        if is_done():
            sys.stdout.write("\r" + " " * (len(label) + 24) + "\r")
            ok(f"{label} — sau {int(time.time() - start)}s")
            return True
        sys.stdout.write(
            f"\r  {CYAN}{frames[i % len(frames)]}{RESET} {label} "
            f"{GREY}[{int(time.time() - start)}s]{RESET}"
        )
        sys.stdout.flush()
        i += 1
        time.sleep(0.4)
    sys.stdout.write("\r" + " " * (len(label) + 24) + "\r")
    fail(f"{label} — hết thời gian chờ")
    return False


def checkpoint(done: str, nxt: str) -> None:
    """Dừng lại chờ người trình bày. Đây là cơ chế giữ nhịp của cả buổi demo."""
    line()
    line("  " + "═" * (WIDTH - 2), GREEN, delay=0)
    line(f"  ✓ ĐÃ XONG    {done}", GREEN + BOLD, delay=0)
    line(f"  → TIẾP THEO  {nxt}", GREY, delay=0)
    line("  " + "═" * (WIDTH - 2), GREEN, delay=0)
    if not _settings["interactive"]:
        line(f"  {GREY}(chế độ không dừng — chạy tiếp){RESET}", delay=0.4)
        return
    try:
        input(f"  {BOLD}Nhấn Enter để tiếp tục...{RESET} ")
    except (EOFError, KeyboardInterrupt):
        line()
        raise SystemExit(130)


def table(headers: list[str], rows: list[list[str]], widths: list[int]) -> None:
    head = "  " + "".join(h.ljust(w) for h, w in zip(headers, widths))
    line(head, GREY + BOLD, delay=0.05)
    line("  " + "─" * sum(widths), GREY, delay=0.05)
    for row in rows:
        line("  " + "".join(str(c).ljust(w) for c, w in zip(row, widths)), delay=0.09)
