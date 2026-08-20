"""Chạy kiểm chứng thật cho bản vá.

Không có gì trong tệp này được mô phỏng. `pytest` được gọi như một tiến trình
con thật, mã nguồn được nạp lại từ đĩa, và payload tấn công được chạy lại lên
chính hàm xác thực của ứng dụng. Nếu bản vá sai, chỗ này sẽ đỏ thật.

Chạy trong tiến trình con là bắt buộc: tiến trình agent đã nạp phiên bản cũ của
`app.*` vào bộ nhớ từ trước, nên chỉ một tiến trình mới mới nhìn thấy mã đã vá.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_SUMMARY = re.compile(
    r"(?:(\d+) failed)?,?\s*(?:(\d+) passed)?(?:,\s*(\d+) error)?.*in [\d.]+s"
)


def python_exe() -> str:
    """Ưu tiên interpreter của môi trường ảo trong kho mã."""
    for candidate in (
        ROOT / ".venv" / "Scripts" / "python.exe",
        ROOT / ".venv" / "bin" / "python",
    ):
        if candidate.exists():
            return str(candidate)
    return sys.executable


def _env() -> dict:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


@dataclass
class TestResult:
    ok: bool
    passed: int
    failed: int
    errors: int
    summary: str
    key_error: str
    failed_tests: list[str]
    raw: str

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.errors


def _extract_key_error(output: str) -> str:
    """Lấy dòng lỗi có ý nghĩa nhất để in lên terminal."""
    for pattern in (
        r"^E\s+(ImportError:.*)$",
        r"^E\s+(ModuleNotFoundError:.*)$",
        r"^E\s+(AttributeError:.*)$",
        r"^E\s+(AssertionError:.*)$",
        r"^E\s+(TypeError:.*)$",
        r"^E\s+(\w+Error:.*)$",
    ):
        match = re.search(pattern, output, re.MULTILINE)
        if match:
            return match.group(1).strip()
    return ""


def _extract_failed_tests(output: str) -> list[str]:
    names = re.findall(r"^(?:FAILED|ERROR)\s+(\S+)", output, re.MULTILINE)
    if names:
        return names
    return re.findall(r"^_{5,}\s+(\S+)\s+_{5,}$", output, re.MULTILINE)


def _error_location(output: str) -> str:
    """Tệp và dòng nơi lỗi thực sự phát sinh."""
    match = re.search(r"^([\w./\\-]+\.py):(\d+): in ", output, re.MULTILINE)
    if match:
        return f"{match.group(1)}:{match.group(2)}"
    match = re.search(r'^\s*File "([^"]+)", line (\d+)', output, re.MULTILINE)
    if match:
        return f"{Path(match.group(1)).name}:{match.group(2)}"
    return ""


def run_pytest(targets: list[str] | None = None) -> TestResult:
    targets = targets or ["tests"]
    proc = subprocess.run(
        [python_exe(), "-m", "pytest", *targets, "-q", "--no-header", "-p", "no:cacheprovider"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_env(),
    )
    output = (proc.stdout or "") + (proc.stderr or "")

    passed = failed = errors = 0
    for token, count in re.findall(r"(\d+) (passed|failed|error|errors)", output):
        if count == "passed":
            passed = int(token)
        elif count == "failed":
            failed = int(token)
        else:
            errors = int(token)

    summary = ""
    for candidate in reversed(output.strip().splitlines()):
        if " in " in candidate and ("passed" in candidate or "failed" in candidate):
            summary = candidate.strip().strip("=").strip()
            break

    location = _error_location(output)
    key_error = _extract_key_error(output)
    if location and key_error:
        key_error = f"{location} — {key_error}"

    return TestResult(
        ok=proc.returncode == 0,
        passed=passed,
        failed=failed,
        errors=errors,
        summary=summary or "không đọc được dòng tổng kết của pytest",
        key_error=key_error,
        failed_tests=_extract_failed_tests(output),
        raw=output,
    )


def exploit_still_works() -> tuple[bool, str]:
    """Chạy lại payload SQL Injection lên hàm xác thực trong tiến trình mới.

    Đây là bằng chứng độc lập với bộ test: nó không đọc kết quả của pytest mà
    tự tấn công lại ứng dụng.
    """
    code = (
        "import json;"
        "from app import db; db.init_db();"
        "from app.auth import injection_succeeds, SQLI_PAYLOAD;"
        "print(json.dumps({'exploitable': injection_succeeds(), 'payload': SQLI_PAYLOAD}))"
    )
    proc = subprocess.run(
        [python_exe(), "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_env(),
    )
    out = (proc.stdout or "").strip().splitlines()
    if proc.returncode != 0 or not out:
        return True, f"không chạy được phép thử: {(proc.stderr or '').strip()[-200:]}"

    import json

    try:
        data = json.loads(out[-1])
    except json.JSONDecodeError:
        return True, "không đọc được kết quả phép thử"
    return bool(data["exploitable"]), data["payload"]


def secrets_removed() -> tuple[bool, list[str]]:
    """Kiểm tra mã nguồn không còn khoá bí mật nhúng cứng."""
    leftovers: list[str] = []
    for rel in ("app/config.py", "app/external.py", "app/main.py"):
        path = ROOT / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for marker in ("sk_live_", "ghp_", "labbank-flask-secret"):
            if marker in text:
                leftovers.append(f"{rel} còn chứa {marker}")
    return not leftovers, leftovers
