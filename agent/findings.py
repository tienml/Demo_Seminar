"""Nạp và chuẩn hoá kết quả quét bảo mật.

Sáu công cụ trong pipeline có sáu định dạng báo cáo khác nhau, nhưng tất cả đều
xuất ra SARIF. Module này quy chúng về một cấu trúc duy nhất để agent chỉ phải
hiểu một schema — đây chính là lý do SARIF tồn tại, và là chi tiết đáng nói khi
thuyết trình.

Thứ tự ưu tiên nguồn dữ liệu:

1. File SARIF thật trong thư mục `findings/` (tải về từ GitHub Actions bằng
   `gh run download`, hoặc do `scripts/scan_local.py` sinh ra).
2. Nếu không có file nào, dùng bản kiểm kê dự phòng trong `agent/baseline.json`.
   Khi phải dùng tới nguồn này, agent in cảnh báo rõ ràng ra terminal để người
   trình bày đọc số trên màn hình thay vì đọc số đã thuộc lòng.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FINDINGS_DIR = ROOT / "findings"
BASELINE_FILE = Path(__file__).resolve().parent / "baseline.json"

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}

# Ánh xạ tên tool trong SARIF về nhãn ngắn hiển thị trên terminal.
TOOL_LABELS = {
    "semgrep": "SAST",
    "gitleaks": "SECRET",
    "trivy": "SCA",
    "hadolint": "CONTAINER",
    "checkov": "IAC",
    "zap": "DAST",
}


@dataclass
class Finding:
    rule_id: str
    tool: str
    severity: str
    message: str
    file: str
    line: int
    cwe: str = ""
    # Các trường do bước triage điền vào.
    reachable: bool | None = None
    triage_reason: str = ""
    group: str = ""
    extras: dict = field(default_factory=dict)

    @property
    def layer(self) -> str:
        return TOOL_LABELS.get(self.tool.lower(), self.tool.upper())

    @property
    def location(self) -> str:
        return f"{self.file}:{self.line}" if self.line else self.file

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "tool": self.tool,
            "severity": self.severity,
            "message": self.message,
            "file": self.file,
            "line": self.line,
            "cwe": self.cwe,
            "reachable": self.reachable,
            "triage_reason": self.triage_reason,
            "group": self.group,
        }


def _normalize_severity(raw: str) -> str:
    raw = (raw or "").lower()
    mapping = {
        "error": "high",
        "warning": "medium",
        "note": "low",
        "none": "info",
        "critical": "critical",
        "high": "high",
        "medium": "medium",
        "low": "low",
    }
    return mapping.get(raw, "medium")


def _tool_name(run: dict) -> str:
    driver = run.get("tool", {}).get("driver", {})
    name = (driver.get("name") or "unknown").lower()
    for key in TOOL_LABELS:
        if key in name:
            return key
    return name


def _rule_severity(run: dict, rule_id: str, result: dict) -> str:
    """SARIF cho phép mức độ nằm ở result hoặc ở định nghĩa rule."""
    if result.get("level"):
        return _normalize_severity(result["level"])

    driver = run.get("tool", {}).get("driver", {})
    for rule in driver.get("rules", []) or []:
        if rule.get("id") != rule_id:
            continue
        props = rule.get("properties", {}) or {}
        for key in ("security-severity", "severity", "problem.severity"):
            if key not in props:
                continue
            value = props[key]
            if key == "security-severity":
                try:
                    score = float(value)
                except (TypeError, ValueError):
                    continue
                if score >= 9.0:
                    return "critical"
                if score >= 7.0:
                    return "high"
                if score >= 4.0:
                    return "medium"
                return "low"
            return _normalize_severity(str(value))
        if rule.get("defaultConfiguration", {}).get("level"):
            return _normalize_severity(rule["defaultConfiguration"]["level"])
    return "medium"


def _rule_cwe(run: dict, rule_id: str) -> str:
    driver = run.get("tool", {}).get("driver", {})
    for rule in driver.get("rules", []) or []:
        if rule.get("id") != rule_id:
            continue
        props = rule.get("properties", {}) or {}
        for key in ("cwe", "tags"):
            value = props.get(key)
            if isinstance(value, str) and "CWE" in value.upper():
                return value
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and "CWE" in item.upper():
                        return item
    return ""


def parse_sarif_file(path: Path) -> list[Finding]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return []

    out: list[Finding] = []
    for run in data.get("runs", []) or []:
        tool = _tool_name(run)
        for result in run.get("results", []) or []:
            rule_id = result.get("ruleId") or result.get("rule", {}).get("id", "unknown")
            message = (result.get("message", {}) or {}).get("text", "").strip()

            locations = result.get("locations") or [{}]
            phys = locations[0].get("physicalLocation") or {}
            artifact = (phys.get("artifactLocation") or {}).get("uri", "")
            start_line = (phys.get("region") or {}).get("startLine", 0)

            out.append(
                Finding(
                    rule_id=rule_id,
                    tool=tool,
                    severity=_rule_severity(run, rule_id, result),
                    message=message.split("\n")[0][:160],
                    file=artifact.lstrip("./"),
                    line=int(start_line or 0),
                    cwe=_rule_cwe(run, rule_id),
                    extras={"source": "sarif", "sarif_file": path.name},
                )
            )
    return out


def load_from_sarif(directory: Path = FINDINGS_DIR) -> list[Finding]:
    if not directory.exists():
        return []
    out: list[Finding] = []
    for path in sorted(directory.rglob("*.sarif")):
        out.extend(parse_sarif_file(path))
    return out


def load_baseline() -> list[Finding]:
    data = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
    return [
        Finding(
            rule_id=item["rule_id"],
            tool=item["tool"],
            severity=item["severity"],
            message=item["message"],
            file=item["file"],
            line=item.get("line", 0),
            cwe=item.get("cwe", ""),
            extras=dict(item.get("evidence", {}), source="baseline"),
        )
        for item in data["findings"]
    ]


def load(prefer_sarif: bool = True) -> tuple[list[Finding], str]:
    """Trả về (danh sách finding đã sắp xếp, nguồn dữ liệu)."""
    if prefer_sarif:
        real = load_from_sarif()
        if real:
            return sort_findings(real), "sarif"
    return sort_findings(load_baseline()), "baseline"


def sort_findings(items: list[Finding]) -> list[Finding]:
    return sorted(
        items,
        key=lambda f: (SEVERITY_ORDER.get(f.severity, 9), f.tool, f.file, f.line),
    )


def summarize(items: list[Finding]) -> dict[str, int]:
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for f in items:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    return counts


def group_by_tool(items: list[Finding]) -> dict[str, list[Finding]]:
    out: dict[str, list[Finding]] = {}
    for f in items:
        out.setdefault(f.layer, []).append(f)
    return out
