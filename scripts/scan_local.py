"""Chạy các công cụ quét ngay trên máy và ghi kết quả SARIF vào `findings/`.

Chạy:  python scripts/scan_local.py
Tuỳ chọn:
    --only semgrep,trivy    chỉ chạy vài công cụ
    --no-docker             không dùng container thay thế khi thiếu binary
    --clean                 xoá các tệp .local.sarif cũ trước khi quét

Vì sao cần script này: `agent/run_agent.py` ưu tiên đọc SARIF thật trong
`findings/`, và chỉ lùi về `agent/baseline.json` khi không có tệp nào. Số liệu
thật luôn thuyết phục hơn số liệu đóng hộp, nên hãy chạy script này (hoặc tải
SARIF từ pipeline) trước buổi demo.

Cách khác, không cần cài gì trên máy — lấy đúng SARIF mà GitHub Actions đã sinh:

    gh run download <run-id> --dir findings

Mỗi công cụ được thử theo hai đường: binary sẵn trên PATH trước, không có thì
chạy qua Docker. Thiếu cả hai thì script bỏ qua công cụ đó và nói rõ, chứ không
âm thầm sinh ra tệp rỗng — một tệp SARIF rỗng còn tệ hơn không có tệp nào, vì
agent sẽ tưởng đã có dữ liệu thật và không cảnh báo gì.

Tên tệp kết thúc bằng `.local.sarif` nên chúng nằm ngoài Git (xem .gitignore).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FINDINGS = ROOT / "findings"

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


@dataclass
class Scanner:
    """Một công cụ quét, kèm hai cách chạy và nơi nó nhả SARIF ra."""

    name: str
    layer: str
    binary: str
    docker_image: str
    native_args: list[str]
    docker_args: list[str]
    # Công cụ ghi thẳng ra tệp, hay in SARIF ra stdout để mình tự hứng?
    stdout_capture: bool = False
    # Vài công cụ ép tên tệp đầu ra; đổi tên lại sau khi chạy.
    renames_from: str = ""
    notes: str = ""
    env: dict[str, str] = field(default_factory=dict)

    @property
    def output(self) -> Path:
        return FINDINGS / f"{self.name}.local.sarif"


def _out(name: str) -> str:
    """Đường dẫn đầu ra theo góc nhìn của tiến trình đang chạy (luôn tương đối)."""
    return f"findings/{name}.local.sarif"


SCANNERS: list[Scanner] = [
    Scanner(
        name="semgrep",
        layer="SAST",
        binary="semgrep",
        docker_image="semgrep/semgrep",
        native_args=[
            "scan",
            "--config", ".semgrep.yml",
            "--config", "p/security-audit",
            "--config", "p/python",
            "--sarif",
            "--output", _out("semgrep"),
            "--metrics", "off",
        ],
        docker_args=[
            "semgrep", "scan",
            "--config", ".semgrep.yml",
            "--config", "p/security-audit",
            "--config", "p/python",
            "--sarif",
            "--output", _out("semgrep"),
            "--metrics", "off",
        ],
        notes="hai config từ registry cần mạng; .semgrep.yml chạy được offline",
    ),
    Scanner(
        name="trivy",
        layer="SCA",
        binary="trivy",
        docker_image="aquasec/trivy",
        native_args=[
            "fs", ".",
            "--scanners", "vuln,secret,misconfig",
            "--format", "sarif",
            "--output", _out("trivy"),
            "--severity", "CRITICAL,HIGH,MEDIUM",
        ],
        docker_args=[
            "fs", "/src",
            "--scanners", "vuln,secret,misconfig",
            "--format", "sarif",
            "--output", f"/src/{_out('trivy')}",
            "--severity", "CRITICAL,HIGH,MEDIUM",
        ],
        notes="lần chạy đầu phải tải cơ sở dữ liệu CVE, mất khoảng 1-2 phút",
    ),
    Scanner(
        name="gitleaks",
        layer="SECRET",
        binary="gitleaks",
        docker_image="zricethezav/gitleaks:latest",
        native_args=[
            "detect",
            "--source", ".",
            "--no-git",
            "--report-format", "sarif",
            "--report-path", _out("gitleaks"),
            "--exit-code", "0",
        ],
        docker_args=[
            "detect",
            "--source", "/src",
            "--no-git",
            "--report-format", "sarif",
            "--report-path", f"/src/{_out('gitleaks')}",
            "--exit-code", "0",
        ],
        notes="--no-git để quét cả cây thư mục, không chỉ lịch sử commit",
    ),
    Scanner(
        name="checkov",
        layer="IAC",
        binary="checkov",
        docker_image="bridgecrew/checkov",
        native_args=[
            "--directory", "infra",
            "--framework", "terraform",
            "--output", "sarif",
            "--output-file-path", "findings",
            "--soft-fail",
        ],
        docker_args=[
            "--directory", "/src/infra",
            "--framework", "terraform",
            "--output", "sarif",
            "--output-file-path", "/src/findings",
            "--soft-fail",
        ],
        renames_from="results.sarif",
        notes="checkov ép tên tệp là results.sarif nên phải đổi tên lại",
    ),
    Scanner(
        name="hadolint",
        layer="CONTAINER",
        binary="hadolint",
        docker_image="hadolint/hadolint",
        native_args=["--format", "sarif", "Dockerfile"],
        docker_args=["hadolint", "--format", "sarif", "/src/Dockerfile"],
        stdout_capture=True,
        notes="hadolint in SARIF ra stdout, script tự hứng và ghi tệp",
    ),
]


def _docker_available() -> bool:
    if not shutil.which("docker"):
        return False
    probe = subprocess.run(
        ["docker", "info"],
        capture_output=True,
        timeout=30,
        check=False,
    )
    return probe.returncode == 0


def _run(cmd: list[str], scanner: Scanner) -> tuple[int, str, str]:
    """Chạy lệnh, trả về (mã thoát, stdout, stderr).

    Không dùng check=True: gần như mọi scanner đều trả mã thoát khác 0 khi TÌM
    THẤY lỗ hổng. Với kho mã cố ý dính lỗi thì đó là kết quả mong đợi, không
    phải lỗi chạy.
    """
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def _build_command(scanner: Scanner, use_docker: bool) -> list[str]:
    if not use_docker:
        return [scanner.binary, *scanner.native_args]
    return [
        "docker", "run", "--rm",
        "-v", f"{ROOT}:/src",
        "-w", "/src",
        scanner.docker_image,
        *scanner.docker_args,
    ]


def scan_one(scanner: Scanner, allow_docker: bool, docker_ok: bool) -> tuple[str, str]:
    """Trả về (trạng thái, mô tả) — trạng thái là ok / skip / fail."""
    native = shutil.which(scanner.binary) is not None
    use_docker = not native

    if use_docker and not (allow_docker and docker_ok):
        thieu = "docker" if allow_docker else f"{scanner.binary} (đã tắt docker)"
        return "skip", f"không có {scanner.binary} trên PATH và không dùng được {thieu}"

    duong = "PATH" if native else f"docker · {scanner.docker_image}"
    print(f"  [{scanner.layer:<9}] {scanner.name:<9} chạy qua {duong}")
    if scanner.notes:
        print(f"              {scanner.notes}")

    code, out, err = _run(_build_command(scanner, use_docker), scanner)

    if scanner.stdout_capture:
        if out.strip().startswith("{"):
            scanner.output.write_text(out, encoding="utf-8")
        else:
            tail = (err or out).strip().splitlines()[-1:] or ["không rõ nguyên nhân"]
            return "fail", f"không nhận được SARIF từ stdout — {tail[0][:120]}"

    if scanner.renames_from:
        produced = FINDINGS / scanner.renames_from
        if produced.exists():
            produced.replace(scanner.output)

    if not scanner.output.exists():
        tail = (err or out).strip().splitlines()[-1:] or [f"mã thoát {code}"]
        return "fail", f"không sinh được tệp SARIF — {tail[0][:120]}"

    kb = scanner.output.stat().st_size / 1024
    return "ok", f"{scanner.output.name} ({kb:.1f} KB)"


def main() -> int:
    ap = argparse.ArgumentParser(description="Quét bảo mật cục bộ, xuất SARIF")
    ap.add_argument("--only", default="",
                    help="danh sách công cụ, cách nhau bằng dấu phẩy")
    ap.add_argument("--no-docker", action="store_true",
                    help="không dùng container thay thế khi thiếu binary")
    ap.add_argument("--clean", action="store_true",
                    help="xoá các tệp .local.sarif cũ trước khi quét")
    args = ap.parse_args()

    FINDINGS.mkdir(parents=True, exist_ok=True)

    if args.clean:
        for old in FINDINGS.glob("*.local.sarif"):
            old.unlink()
            print(f"  đã xoá {old.name}")
        print()

    chosen = SCANNERS
    if args.only:
        want = {n.strip().lower() for n in args.only.split(",") if n.strip()}
        chosen = [s for s in SCANNERS if s.name in want]
        unknown = want - {s.name for s in SCANNERS}
        if unknown:
            print(f"Không biết công cụ: {', '.join(sorted(unknown))}")
            return 2

    allow_docker = not args.no_docker
    docker_ok = allow_docker and _docker_available()

    print(f"Kho mã : {ROOT}")
    print(f"Đầu ra : {FINDINGS.relative_to(ROOT)}/")
    print(f"Docker : {'dùng được' if docker_ok else 'không dùng được'}")
    print()

    results: dict[str, list[str]] = {"ok": [], "skip": [], "fail": []}
    for scanner in chosen:
        status, detail = scan_one(scanner, allow_docker, docker_ok)
        results[status].append(f"{scanner.name}: {detail}")
        if status != "ok":
            print(f"  [{scanner.layer:<9}] {scanner.name:<9} bỏ qua — {detail}")
        else:
            print(f"              → {detail}")
        print()

    print("─" * 70)
    print(f"Xong: {len(results['ok'])} công cụ có kết quả, "
          f"{len(results['skip'])} bỏ qua, {len(results['fail'])} lỗi.")

    for line in results["fail"]:
        print(f"  lỗi   {line}")
    for line in results["skip"]:
        print(f"  thiếu {line}")

    if not results["ok"]:
        print()
        print("Không có tệp SARIF nào được sinh ra. Agent sẽ chạy bằng số liệu dự")
        print("phòng trong agent/baseline.json và in cảnh báo lên terminal.")
        print("Muốn có số thật mà không cài gì: đẩy code lên GitHub, để pipeline")
        print("chạy, rồi tải kết quả về bằng")
        print("    gh run download <run-id> --dir findings")
        return 1

    print()
    print("Chạy agent để nó đọc đúng những tệp này:")
    print("    python agent/run_agent.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
