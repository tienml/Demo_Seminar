"""Bảng theo dõi MTTR chiếu song song với terminal.

Agent ghi lại một tệp HTML tĩnh sau mỗi chặng. Trang tự làm mới bằng thẻ meta
nên mở thẳng bằng đường dẫn tệp là chạy được, không cần dựng web server và
không vướng chính sách CORS của trình duyệt.

Đồng hồ MTTR là chi tiết đắt nhất của cả buổi demo: nó cho khán giả một con số
để so với mốc vài tuần của quy trình thủ công.
"""

from __future__ import annotations

import html
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "dashboard"
OUT_HTML = OUT_DIR / "index.html"
OUT_JSON = OUT_DIR / "state.json"


@dataclass
class State:
    started_at: float = field(default_factory=time.time)
    stopped_at: float | None = None
    stage: str = "Khởi động"
    stage_index: int = 0
    stage_total: int = 6
    total_findings: int = 0
    actionable: int = 0
    dismissed: int = 0
    fixed: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    exploitable: bool = True
    events: list[str] = field(default_factory=list)

    def event(self, text: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        self.events.insert(0, f"{stamp}  {text}")
        del self.events[12:]


_state = State()


def state() -> State:
    return _state


def stop_clock() -> float:
    _state.stopped_at = time.time()
    return _state.stopped_at - _state.started_at


def elapsed() -> float:
    end = _state.stopped_at or time.time()
    return end - _state.started_at


def fmt(seconds: float) -> str:
    return f"{int(seconds) // 60:02d}:{int(seconds) % 60:02d}"


def _tile(label: str, value: str, tone: str = "") -> str:
    return (
        f'<div class="tile {tone}"><div class="tile-value">{html.escape(value)}</div>'
        f'<div class="tile-label">{html.escape(label)}</div></div>'
    )


def render() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    s = _state
    running = s.stopped_at is None
    progress = int(100 * s.stage_index / max(1, s.stage_total))

    status_tone = "danger" if s.exploitable else "ok"
    status_text = "CÒN KHAI THÁC ĐƯỢC" if s.exploitable else "ĐÃ CHẶN"

    tiles = "".join(
        [
            _tile("Cảnh báo ban đầu", str(s.total_findings)),
            _tile("Cần xử lý", str(s.actionable), "warn"),
            _tile("Đã loại sau phân loại", str(s.dismissed), "muted"),
            _tile("Đã vá", str(s.fixed), "ok"),
            _tile("Test đạt", str(s.tests_passed), "ok"),
            _tile("Test hỏng", str(s.tests_failed), "danger" if s.tests_failed else "muted"),
        ]
    )

    events = "".join(
        f"<li>{html.escape(e)}</li>" for e in s.events
    ) or "<li>chưa có sự kiện</li>"

    OUT_HTML.write_text(
        f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="2">
<title>MTTR — AI-Augmented DevSecOps</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family: "Segoe UI", Inter, system-ui, sans-serif;
         background: radial-gradient(900px 420px at 50% -10%, #17224a, #0b1020 65%);
         color:#eef2ff; padding:28px; }}
  h1 {{ font-size:15px; letter-spacing:2px; color:#9aa6c7; margin:0 0 18px;
        text-transform:uppercase; font-weight:600; }}
  .clock {{ font-size:88px; font-weight:800; letter-spacing:3px; line-height:1;
            font-variant-numeric: tabular-nums; }}
  .clock.running {{ color:#ffd166; }}
  .clock.stopped {{ color:#2ee6a8; }}
  .clock-label {{ color:#9aa6c7; font-size:13px; margin-top:6px; }}
  .stage {{ margin:22px 0 10px; font-size:19px; font-weight:700; }}
  .bar {{ height:9px; border-radius:99px; background:#1e2740; overflow:hidden; }}
  .bar > i {{ display:block; height:100%; width:{progress}%;
              background:linear-gradient(90deg,#5b8cff,#2ee6a8); }}
  .grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin:22px 0; }}
  .tile {{ background:#171f36; border:1px solid #26304d; border-radius:14px; padding:14px; }}
  .tile-value {{ font-size:30px; font-weight:800; font-variant-numeric:tabular-nums; }}
  .tile-label {{ font-size:12px; color:#9aa6c7; margin-top:4px; }}
  .tile.ok .tile-value {{ color:#2ee6a8; }}
  .tile.warn .tile-value {{ color:#ffd166; }}
  .tile.danger .tile-value {{ color:#ff3b5c; }}
  .tile.muted .tile-value {{ color:#9aa6c7; }}
  .status {{ display:inline-block; padding:8px 16px; border-radius:99px;
             font-weight:700; font-size:14px; letter-spacing:.6px; }}
  .status.danger {{ background:#3a0d1a; color:#ffb3c1; border:1px solid #7c1c33; }}
  .status.ok {{ background:#06301f; color:#9ff5d6; border:1px solid #12694b; }}
  ul {{ list-style:none; padding:0; margin:16px 0 0; font-size:13px; color:#9aa6c7; }}
  li {{ padding:6px 0; border-bottom:1px solid #1e2740; font-variant-numeric:tabular-nums; }}
</style>
</head>
<body>
  <h1>Mean Time To Remediate</h1>
  <div class="clock {'running' if running else 'stopped'}" id="clock">{fmt(elapsed())}</div>
  <div class="clock-label">{'đang chạy' if running else 'đã dừng — toàn bộ lỗ hổng đã được vá và triển khai'}</div>

  <div class="stage">Chặng {s.stage_index}/{s.stage_total} · {html.escape(s.stage)}</div>
  <div class="bar"><i></i></div>

  <div class="grid">{tiles}</div>

  <span class="status {status_tone}">SQL Injection: {status_text}</span>

  <ul>{events}</ul>

<script>
  const started = {s.started_at!r};
  const stopped = {('null' if running else repr(s.stopped_at))};
  const el = document.getElementById("clock");
  function tick() {{
    const end = stopped === null ? Date.now() / 1000 : stopped;
    const secs = Math.max(0, Math.floor(end - started));
    el.textContent = String(Math.floor(secs / 60)).padStart(2, "0") + ":" +
                     String(secs % 60).padStart(2, "0");
  }}
  tick();
  if (stopped === null) setInterval(tick, 1000);
</script>
</body>
</html>
""",
        encoding="utf-8",
    )

    OUT_JSON.write_text(
        json.dumps(asdict(s) | {"elapsed_seconds": round(elapsed(), 1)},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def update(**kwargs) -> None:
    for key, value in kwargs.items():
        setattr(_state, key, value)
    render()
