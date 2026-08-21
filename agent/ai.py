"""Lớp gọi AI dùng chung cho mọi chặng của demo.

Ba chế độ, chọn bằng `--ai`:

* ``cache`` — đọc kết quả đã ghi sẵn trong ``agent/ai_cache/``. Đây là chế độ
  MẶC ĐỊNH khi diễn. Không phụ thuộc mạng, không phụ thuộc proxy, thời gian chạy
  bằng không.
* ``live``  — gọi ``claude -p`` thật, có timeout, và **tự động rơi về cache** nếu
  lỗi. Dùng cho đúng một khoảnh khắc trong buổi diễn.
* ``off``   — bỏ hẳn phần AI, chỉ chạy các bước xác minh.

Nguyên tắc bất di bất dịch của module này: **không bao giờ ném exception ra
ngoài**. Một lỗi mạng giữa buổi seminar không được phép làm chết demo. Mọi hàm
đều trả về ``(kết quả, nguồn)`` và người gọi luôn có đường đi tiếp.

Giá trị của ``nguồn`` cũng chính là nhãn hiện lên màn hình cho khán giả biết dòng
chữ họ đang đọc đến từ đâu. Đó là điều kiện để một demo có phần dàn dựng vẫn giữ
được uy tín với người xem kỹ thuật.

Lưu ý kỹ thuật: prompt của chặng rà soát kế hoạch dài khoảng 11KB, vượt giới hạn
8191 ký tự của dòng lệnh Windows. Vì vậy tài liệu luôn được đưa vào qua **stdin**,
còn tham số ``-p`` chỉ chứa phần chỉ thị ngắn.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = Path(__file__).resolve().parent / "ai_cache"

# Nguồn kết quả — dùng làm nhãn hiển thị.
LIVE = "live"
CACHE = "cache"
OFF = "off"
FAIL = "fail"

NHAN = {
    LIVE: "AI · trực tiếp",
    CACHE: "AI · đã ghi lại",
    OFF: "bỏ qua AI",
    FAIL: "AI không phản hồi",
}

# 120s là không đủ: mô hình mặc định trong settings.json là bản 1M context, chậm
# hơn đáng kể. Đo thực tế trên máy demo: gọi ngắn 8s, gọi kèm 8.4KB tài liệu bằng
# claude-sonnet-5 mất 21s, còn bản opus 1M vượt 120s. Để 300s cho có biên an toàn.
DEFAULT_TIMEOUT = 300


# ---------------------------------------------------------------------------
# Tìm chương trình claude


def find_claude() -> str | None:
    """Tìm CLI ``claude``. Trên Windows nó có thể là .cmd, .exe hoặc shim không
    phần mở rộng, nên phải thử vài dạng."""
    for ten in ("claude", "claude.cmd", "claude.exe", "claude.bat"):
        found = shutil.which(ten)
        if found:
            return found
    # Đường cài mặc định của bản standalone.
    for ung_vien in (
        Path.home() / ".local" / "bin" / "claude.exe",
        Path.home() / ".local" / "bin" / "claude.cmd",
        Path.home() / ".local" / "bin" / "claude",
    ):
        if ung_vien.exists():
            return str(ung_vien)
    return None


def kha_dung() -> bool:
    return find_claude() is not None


# ---------------------------------------------------------------------------
# Cache


def _duong_dan_cache(task: str) -> Path:
    return CACHE_DIR / f"{task}.json"


def _bam(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def doc_cache(task: str) -> dict | None:
    path = _duong_dan_cache(task)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def ghi_cache(task: str, ket_qua: dict, *, prompt: str, model: str = "") -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _duong_dan_cache(task)
    goi = {
        "task": task,
        "ghi_luc": datetime.now().isoformat(timespec="seconds"),
        "model": model,
        "prompt_sha": _bam(prompt),
        "ket_qua": ket_qua,
    }
    path.write_text(json.dumps(goi, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Bóc JSON ra khỏi câu trả lời


def boc_json(text: str) -> dict | None:
    """Lấy khối JSON đầu tiên trong một đoạn văn bản.

    Mô hình hay bọc JSON trong ```json ... ``` hoặc kèm một câu dẫn. Hàm này
    chịu được cả hai, nên người gọi không phải nhắc mô hình "chỉ trả JSON".
    """
    if not text:
        return None
    t = text.strip()

    if "```" in t:
        khoi = t.split("```")
        for phan in khoi:
            p = phan.strip()
            if p.startswith("json"):
                p = p[4:].strip()
            if p.startswith("{"):
                t = p
                break

    dau = t.find("{")
    cuoi = t.rfind("}")
    if dau == -1 or cuoi <= dau:
        return None
    try:
        return json.loads(t[dau : cuoi + 1])
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------------------
# Gọi AI


def _goi_claude(
    chi_thi: str,
    tai_lieu: str,
    *,
    timeout: int,
    model: str = "",
    thu_muc: str | Path | None = None,
) -> tuple[str, str]:
    """Gọi ``claude -p``. Trả về (văn bản kết quả, thông báo lỗi).

    ``thu_muc`` quyết định thư mục làm việc của tiến trình con, và điều này quan
    trọng hơn vẻ ngoài: Claude Code tự nạp ``CLAUDE.md`` tìm thấy ở thư mục làm
    việc làm bộ nhớ dự án. Đo thực tế trên máy demo: cùng một câu hỏi về §4.2,
    chạy trong repo thì trả lời đúng nội dung quy tắc, chạy ở thư mục tạm thì trả
    lời không biết. Nghĩa là muốn dựng lại tình huống "không có chính sách" thì
    phải đổi thư mục làm việc — bỏ chính sách khỏi stdin là không đủ.
    """
    claude = find_claude()
    if not claude:
        return "", "không tìm thấy chương trình claude trên PATH"

    cmd = [claude, "-p", chi_thi, "--output-format", "json"]
    if model:
        cmd += ["--model", model]

    moi_truong = dict(os.environ)
    # Tránh gọi lồng vào một phiên Claude Code đang chạy — đó là nguyên nhân treo.
    for bien in ("CLAUDECODE", "CLAUDE_CODE_CHILD_SESSION", "CLAUDE_CODE_SESSION_ID"):
        moi_truong.pop(bien, None)

    try:
        tien_trinh = subprocess.run(
            cmd,
            input=tai_lieu,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=moi_truong,
            cwd=str(thu_muc) if thu_muc else None,
        )
    except subprocess.TimeoutExpired:
        return "", f"hết {timeout}s chờ phản hồi"
    except OSError as loi:
        return "", f"không chạy được claude: {loi}"

    if tien_trinh.returncode != 0:
        loi = (tien_trinh.stderr or "").strip().splitlines()
        return "", f"claude thoát mã {tien_trinh.returncode}: {loi[0] if loi else 'không rõ'}"

    thô = (tien_trinh.stdout or "").strip()
    if not thô:
        return "", "claude không trả về gì"

    # --output-format json trả về một phong bì, nội dung nằm ở khoá result.
    try:
        phong_bi = json.loads(thô)
        if isinstance(phong_bi, dict) and "result" in phong_bi:
            return str(phong_bi["result"]), ""
    except json.JSONDecodeError:
        pass
    return thô, ""


def hoi_json(
    task: str,
    chi_thi: str,
    tai_lieu: str,
    *,
    mode: str = CACHE,
    timeout: int = DEFAULT_TIMEOUT,
    model: str = "",
    ghi: bool = False,
    thu_muc: str | Path | None = None,
) -> tuple[dict | None, str, str]:
    """Hỏi AI và mong đợi JSON.

    Trả về ``(kết quả, nguồn, ghi_chú)``. ``nguồn`` là một trong LIVE / CACHE /
    OFF / FAIL và dùng làm nhãn hiển thị. ``ghi_chú`` giải thích vì sao rơi về
    cache, để người trình bày nói được sự thật nếu bị hỏi.
    """
    if mode == OFF:
        return None, OFF, "chạy ở chế độ không dùng AI"

    if mode == LIVE:
        text, loi = _goi_claude(chi_thi, tai_lieu, timeout=timeout,
                                model=model, thu_muc=thu_muc)
        ket_qua = boc_json(text) if text else None
        if ket_qua is not None:
            if ghi:
                ghi_cache(task, ket_qua, prompt=chi_thi + tai_lieu, model=model)
            return ket_qua, LIVE, ""
        ly_do = loi or "không bóc được JSON từ câu trả lời"
        goi = doc_cache(task)
        if goi:
            return goi.get("ket_qua"), CACHE, f"gọi trực tiếp thất bại ({ly_do}), dùng bản đã ghi"
        return None, FAIL, ly_do

    goi = doc_cache(task)
    if goi:
        return goi.get("ket_qua"), CACHE, ""
    return None, FAIL, f"chưa có bản ghi nào cho '{task}' — chạy lại với --record để tạo"


# ---------------------------------------------------------------------------


def tu_kiem_tra() -> int:
    """Kiểm tra nhanh xem máy này gọi được claude hay không.

    Chạy:  python agent/ai.py
    """
    claude = find_claude()
    print("claude:", claude or "KHÔNG TÌM THẤY")
    if not claude:
        print("\nCài Claude Code rồi thử lại, hoặc chỉ dùng chế độ --ai cache.")
        return 1

    print("Đang thử một lời gọi ngắn...")
    text, loi = _goi_claude(
        'Trả về đúng JSON này, không thêm gì: {"ok": true}',
        "",
        timeout=90,
    )
    if loi:
        print("THẤT BẠI:", loi)
        print("\nDemo vẫn chạy được bằng --ai cache.")
        return 1
    print("Trả về:", (text or "").strip()[:200])
    print("Bóc JSON:", boc_json(text))
    return 0


if __name__ == "__main__":
    sys.exit(tu_kiem_tra())
