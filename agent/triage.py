"""Phân loại cảnh báo theo khả năng khai thác thực tế.

Đây là chặng trả lời trực tiếp cho nỗi đau Alert Fatigue: công cụ quét truyền
thống so khớp mẫu nên báo mọi thứ khớp mẫu, còn agent thì hỏi thêm ba câu:

1. Cảnh báo này có trùng với cảnh báo của một công cụ khác không?
2. Đoạn mã bị báo có nằm trên đường đi từ dữ liệu người dùng tới câu lệnh nguy
   hiểm không, hay nó là nhánh chết trong bản triển khai thật?
3. Nếu là lỗ hổng thư viện, nhà phát hành đã có bản vá chưa, và gói đó có thực
   sự được nạp lúc chạy không?

Mỗi quyết định đều kèm lý do bằng chữ. Không có cảnh báo nào bị loại trong im
lặng — đó là điều kiện để một hệ thống tự động được phép giảm khối lượng việc.
"""

from __future__ import annotations

from dataclasses import dataclass

from .findings import SEVERITY_ORDER, Finding

# Ba rổ kết quả.
ACT = "act"      # cần xử lý ngay
NOFIX = "nofix"  # không kích hoạt được, hoặc chưa có bản vá từ nhà phát hành
LOW = "low"      # rủi ro thấp, trùng lặp, hoặc thuần chất lượng mã

BUCKET_LABELS = {
    ACT: "CẦN XỬ LÝ NGAY",
    NOFIX: "KHÔNG KÍCH HOẠT ĐƯỢC / CHƯA CÓ BẢN VÁ",
    LOW: "RỦI RO THẤP HOẶC TRÙNG LẶP",
}

# Đường dẫn không đi vào artifact được triển khai.
NON_SHIPPED = (".venv/", "venv/", "tests/", "test_", "node_modules/", ".github/")

# Nhóm sửa chữa: nhiều cảnh báo rời rạc nhưng chung một bản vá.
FIX_GROUPS = [
    ("sqli", ("labbank-sql-string-concat", "labbank-sqlite-execute-non-parameterized",
              "sqli", "sql-injection", "formatted-string-sql")),
    ("secret", ("generic-api-key", "github-pat", "flask-secret-key",
                "labbank-hardcoded-secret", "hardcoded", "secret")),
    ("deps", ("cve-",)),
    ("idor", ("labbank-missing-authorization-check", "missing-authorization",
              "broken-access")),
    ("headers", ("missing-security-headers", "security-headers")),
    ("container", ("ds002", "ds026", "dl3")),
    ("iac", ("ckv_",)),
]

GROUP_TITLES = {
    "sqli": "SQL Injection ở tầng xác thực",
    "secret": "Khoá bí mật nhúng cứng trong mã nguồn",
    "deps": "Lỗ hổng thư viện phụ thuộc",
    "idor": "Thiếu kiểm tra quyền truy cập bản ghi",
    "headers": "Thiếu header bảo mật HTTP",
    "container": "Cấu hình container không an toàn",
    "iac": "Hạ tầng dưới dạng mã bị cấu hình sai",
    "other": "Khác",
}

# Thứ tự agent bắt tay vào sửa: nguy hiểm nhất và gần người dùng nhất trước.
GROUP_ORDER = ["sqli", "secret", "deps", "idor", "container", "iac", "headers", "other"]


@dataclass
class TriageResult:
    actionable: list[Finding]
    nofix: list[Finding]
    low: list[Finding]
    total: int

    @property
    def groups(self) -> dict[str, list[Finding]]:
        out: dict[str, list[Finding]] = {}
        for f in self.actionable:
            out.setdefault(f.group, []).append(f)
        return {g: out[g] for g in GROUP_ORDER if g in out}


def classify_group(finding: Finding) -> str:
    haystack = f"{finding.rule_id} {finding.cwe}".lower()
    for name, needles in FIX_GROUPS:
        if any(n in haystack for n in needles):
            return name
    return "other"


def _dedupe_key(finding: Finding) -> tuple:
    return (finding.file, finding.line, classify_group(finding))


def _is_os_package(finding: Finding) -> bool:
    if finding.extras.get("component") == "os-pkg":
        return True
    # Với SARIF thật, Trivy đặt tên image vào trường vị trí thay vì đường dẫn file.
    return ":" in finding.file and "/" not in finding.file and finding.line == 0


def _is_shipped(finding: Finding) -> bool:
    path = finding.file.replace("\\", "/").lower()
    return not any(marker in path for marker in NON_SHIPPED)


def _decide(finding: Finding, seen: dict) -> tuple[str, str]:
    ev = finding.extras

    # Trùng lặp thật là khi HAI công cụ khác nhau cùng chỉ vào một dòng mã.
    # Hai CVE khác nhau trên cùng một dòng requirements.txt thì không phải trùng.
    other = seen.get(_dedupe_key(finding))
    if other is not None and other.tool != finding.tool:
        return LOW, f"trùng với phát hiện của {other.tool} ({other.rule_id}) tại cùng vị trí"
    if ev.get("duplicate_of"):
        return LOW, f"trùng với {ev['duplicate_of']}"

    if not _is_shipped(finding):
        return NOFIX, "nằm ngoài artifact được triển khai (mã kiểm thử hoặc môi trường ảo)"

    if _is_os_package(finding):
        pkg = ev.get("package", "gói hệ điều hành")
        if not ev.get("fixed_version"):
            return NOFIX, f"{pkg}: nhà phát hành chưa có bản vá, gói không được ứng dụng nạp"
        return ACT, f"{pkg}: đã có bản vá {ev['fixed_version']}"

    if ev.get("component") == "app-dep":
        pkg = ev.get("package", "thư viện")
        fixed = ev.get("fixed_version")
        if not fixed:
            return NOFIX, f"{pkg}: chưa có phiên bản vá"
        via = "" if ev.get("direct_dependency") else f", kéo theo bởi {ev.get('pulled_by', 'gói khác')}"
        return ACT, f"{pkg} {ev.get('installed_version', '')} → {fixed}{via}"

    if ev.get("component") == "secret":
        return ACT, "khoá nằm trong lịch sử Git, phải thu hồi và đưa ra biến môi trường"

    if ev.get("component") == "app-code":
        if not ev.get("reachable_from_http"):
            return LOW, ev.get("note") or "không có đường đi từ dữ liệu người dùng tới đoạn mã này"
        if finding.severity in ("low", "info"):
            return LOW, ev.get("note") or "chất lượng mã, không tạo ra đường khai thác"
        entry = ", ".join(ev.get("entrypoints", [])) or "endpoint HTTP"
        source = ev.get("taint_source", "dữ liệu người dùng")
        return ACT, f"có đường đi từ {source} qua {entry}"

    if ev.get("component") in ("iac", "container"):
        if ev.get("applies_to_deployment"):
            return ACT, "áp dụng cho cấu hình triển khai thật"
        return LOW, ev.get("note") or "không ảnh hưởng tới cấu hình triển khai"

    # Nhánh dành cho SARIF thật, khi không có sẵn trường bằng chứng.
    if finding.severity in ("low", "info"):
        return LOW, "mức độ thấp, không có bằng chứng khai thác được"
    if SEVERITY_ORDER.get(finding.severity, 9) <= 1:
        return ACT, "mức độ nghiêm trọng, nằm trong mã được triển khai"
    return ACT, "nằm trong mã được triển khai, cần xác minh thêm"


def run(items: list[Finding]) -> TriageResult:
    seen: dict = {}
    actionable: list[Finding] = []
    nofix: list[Finding] = []
    low: list[Finding] = []

    for finding in items:
        finding.group = classify_group(finding)
        bucket, reason = _decide(finding, seen)
        finding.triage_reason = reason
        finding.reachable = bucket == ACT

        if bucket == ACT:
            seen.setdefault(_dedupe_key(finding), finding)
            actionable.append(finding)
        elif bucket == NOFIX:
            nofix.append(finding)
        else:
            low.append(finding)

    return TriageResult(actionable=actionable, nofix=nofix, low=low, total=len(items))
