# Runbook — 40 phút demo AI-Augmented DevSecOps

Kịch bản chạy theo một chuỗi hiện vật, không phải theo danh sách tính năng: bản kế
hoạch → AI rà → sửa → mã dựng từ kế hoạch đã sửa → AI rà → chốt chặn → kiểm thử →
quét → PR có người duyệt → production → tấn công thật trên trình duyệt.

Câu xuyên suốt cả buổi: **tìm lỗ hổng ở càng sớm càng rẻ.** Ở chặng 1 sửa một đoạn
văn. Ở chặng 7 sửa khi tiền đã ra khỏi tài khoản.

## Chuẩn bị trước khi lên

Mở sẵn, mỗi thứ một cửa sổ, đừng mở giữa buổi:

1. PowerShell tại `D:\Seminar-DevSecOps\devsecops-ai-demo` — chưa gõ `claude`
2. PowerShell thứ hai cùng thư mục — dành cho `pytest` và các script
3. Trình duyệt tab 1: bảng issue của repo
4. Trình duyệt tab 2: tab Actions của repo
5. Trình duyệt tab 3: URL ứng dụng đã triển khai
6. VS Code mở sẵn `CLAUDE.md` và `docs/plan/v1-chuyen-tien.md`

Kiểm tra ba thứ, mỗi thứ mất mười giây:

```
.\.venv\Scripts\python.exe scripts\review_plan.py --ai cache --speed 0
.\.venv\Scripts\python.exe -m pytest -q
D:\Seminar-DevSecOps\tools\bin\gh.exe auth status
```

`pytest` đúng phải là **37 xanh, 6 đỏ**. Sáu đỏ nằm ở `tests/test_security.py`, cố
tình đỏ cho tới khi vá xong. Nếu thấy con số khác thì có gì đó đã đổi.

**Đừng mở `~/.claude/settings.json` và đừng gõ `/config` khi đang chiếu màn hình.**
File đó có token ở dạng chữ thường. Sau seminar nên đổi token.

## Bảng nhịp

| Chặng | Phút | Trên màn hình | Chạy bằng |
|---|---|---|---|
| 1. Rà soát kế hoạch | 6 | Phiên `claude` tương tác | Claude Code |
| 1b. Thành issue thật | 2 | Bảng issue GitHub | `gh` |
| 2. Rà soát mã nguồn | 6 | Phiên `claude` tương tác | Claude Code |
| 2b. Chốt chặn chính sách | 3 | Terminal + git | pre-commit hook |
| 3. Kiểm thử — đỏ trước xanh sau | 5 | Terminal | pytest |
| 4. Quét và phân loại | 4 | Terminal, bảng SARIF | `agent/run_agent.py` |
| 5. PR và chốt người duyệt | 3 | GitHub web | Actions + Environments |
| 6. Xác thực production | 5 | Terminal + URL thật | `agent/run_agent.py` |
| 7. Tấn công trình duyệt | 4 | Chromium mở thật | Playwright |

38 phút, còn 2 phút biên. Nếu tụt nhịp thì cắt chặng 4 xuống 2 phút và bỏ lượt B
của chặng 2 — hai chỗ đó mất ít nhất.

---

## Chặng 1 · Rà soát bản kế hoạch — 6 phút

Chi tiết ở [prompts/01-ra-soat-ke-hoach.md](prompts/01-ra-soat-ke-hoach.md).

Mở đầu bằng câu hỏi cho khán giả: rẻ nhất thì nên tìm ra lỗ hổng ở đâu? Rồi mở
`docs/plan/v1-chuyen-tien.md` — chưa có dòng mã nào tồn tại.

Dán lượt A. Khoảng 10 giây ra bảng.

Điểm phải nói khi bảng hiện ra: prompt **không hề đưa chính sách vào**, nhưng nó
trích đúng `§4.1`, `§6.1`, `§7.1`. `CLAUDE.md` tự nạp làm bộ nhớ dự án. Đã kiểm
chứng: chạy cùng câu hỏi ngoài repo thì nó trả lời không biết.

Hỏi khán giả chọn một mã, chạy lượt B.

Nếu còn thời gian, chạy beat so sánh:

```
.\.venv\Scripts\python.exe scripts\so_sanh_chinh_sach.py
```

Số đo đi ngược trực giác — bản không có chính sách tìm **nhiều hơn**, 20 so với 13.
Nói đúng như vậy rồi mới nói khác biệt thật: 13/13 neo được vào một quy tắc viết
ra, so với 0/20. Chính sách không làm AI tìm nhiều hơn, nó làm kết quả dùng được.

**Dự phòng khi mạng chết:** `scripts\review_plan.py --ai cache`

## Chặng 1b · Từ phát hiện thành issue — 2 phút

Chuyển sang trình duyệt. 13 issue đã mở sẵn, `#1` đến `#13`.

```
D:\Seminar-DevSecOps\tools\bin\gh.exe issue list --label bao-mat --web
```

Mở `#1`. Chỉ vào ba thứ: nhãn mức độ, checklist tiêu chí nghiệm thu, và khối cuối
ghi rõ **chưa được người rà lại** kèm nhãn `can-nguoi-ra-lai`. Theo §1 của chính
sách, "đã báo cáo" không được trình bày như "đã kiểm chứng".

Mã issue (`F1…F13`) đến từ bản cache, **không khớp** mã trong bảng lượt A. Trỏ theo
tiêu đề, đừng trỏ theo mã.

Dọn sau mỗi lần tập:

```
.\.venv\Scripts\python.exe scripts\plan_to_issues.py --don-dep --tao-that
.\.venv\Scripts\python.exe scripts\plan_to_issues.py --tao-that
```

## Chặng 2 · Rà soát mã nguồn — 6 phút

Chi tiết ở [prompts/02-ra-soat-ma-nguon.md](prompts/02-ra-soat-ma-nguon.md).
Đáp án đầy đủ nằm **ngoài repo**: `D:\Seminar-DevSecOps\ghi-chu-chang-2-dap-an.md`.

Câu chuyển chặng: giờ đã có một bản kế hoạch được duyệt, nên câu hỏi không còn là
"mã này có an toàn không" mà là "mã này có làm đúng điều đã cam kết không". Theo
§12.3, lệch khỏi kế hoạch đã duyệt là một phát hiện — đó là thứ công cụ quét tĩnh
không làm được.

Ba chỗ đáng đào sâu, chọn theo nội dung chứ không theo mã: hai hàm gợi ý (một hàm
đã tham số hoá, một biến thể `?nhanh=1` bị bỏ quên); `from_account` vẫn nhận từ
client dù kế hoạch đã bỏ; phép đổi tiền đi qua `float` dù lược đồ đã đúng.

**Beat mạnh nhất — bắt AI sai tại chỗ.** Lần chạy thử nó xếp mức nghiêm trọng cho
một phát hiện nói rằng `from_account` trùng `to_account` làm tiền sinh ra từ không
khí. Chạy thử: chênh 0 xu. Đó là dương tính giả. Chỉ diễn beat này nếu hôm đó nó
thật sự báo lỗi đó — đừng bịa.

Kết chặng bằng:

```
.\.venv\Scripts\python.exe -m pytest tests\test_transfer.py -q
```

5 xanh, 0 đỏ, ngay cạnh danh sách vừa liệt kê một loạt lỗ hổng. Xanh không có
nghĩa là an toàn, nó chỉ có nghĩa là không ai hỏi đúng câu hỏi.

## Chặng 2b · Chính sách thành chốt chặn — 3 phút

Chi tiết ở [prompts/02b-chot-chan-chinh-sach.md](prompts/02b-chot-chan-chinh-sach.md).

```
.\.venv\Scripts\python.exe .claude\hooks\chan_vi_pham.py --quet app\
git add app\transfer.py
git commit -m "them tinh nang chuyen tien"
git reset
```

Commit bị chặn, in ra ba vi phạm kèm số hiệu mục chính sách. Điểm đáng nói: chốt
này không quan tâm mã đến từ đâu — AI sinh, IDE gợi ý hay gõ tay đều qua cùng một
cửa.

Tự nói ra giới hạn trước khi bị hỏi: đây là so khớp mẫu, bắt được `float(amount)`
nhưng không bắt được một hàm tính tiền sai đặt tên khác. Đó là lý do cần cả hai
lớp — regex không bao giờ mệt, AI đọc được ý định nhưng không tất định.

**Chưa kiểm chứng:** hook `PreToolUse` của Claude Code không kích hoạt ở chế độ
headless và tôi chưa xác nhận được nó chạy trong phiên tương tác. Nếu chưa kịp
kiểm tra thì chỉ diễn phần git, đừng nói gì về hook của Claude Code.

## Chặng 3 · Kiểm thử — đỏ trước xanh sau — 5 phút

Theo §12.2, bản vá chỉ được tính là vá khi có test đỏ trước và xanh sau. Đây là
chỗ chứng minh, không phải chỗ tin lời.

```
.\.venv\Scripts\python.exe -m pytest tests\test_security.py -q
```

6 đỏ. Đó là các tiêu chí nghiệm thu chưa đạt, không phải lỗi hệ thống.

## Chặng 4 · Quét và phân loại — 4 phút

```
.\.venv\Scripts\python.exe agent\run_agent.py --speed 1
```

Sáu công cụ quét, một lược đồ SARIF chung. Điểm nhấn ở bước phân loại: mỗi cảnh
báo bị loại đều có lý do ghi ra, không cái nào bị bỏ trong im lặng. Đó là §1 chạy
ở quy mô hàng trăm cảnh báo — cũng chính là câu trả lời cho alert fatigue.

## Chặng 5 · PR và chốt người duyệt — 3 phút

Sang tab Actions. Pipeline dừng ở cổng phê duyệt của GitHub Environments, chờ chữ
ký người duyệt.

Nói rõ theo §13: bốn việc AI không được quyết — thu hồi khoá đã lộ, chọn dải IP
quản trị thật, phê duyệt triển khai production, chấp nhận rủi ro còn lại. Đây là
việc thứ ba, và nó đang chặn pipeline thật.

Bấm duyệt.

## Chặng 6 · Xác thực production — 5 phút

Không tin cờ cấu hình. Endpoint `/version` tự chạy lại payload tấn công lên chính
hàm xác thực rồi báo kết quả, nên màn hình luôn phản ánh sự thật của mã.

Mở URL thật, chỉ vào `patched: true`. Đọc số MTTR.

## Chặng 7 · Tấn công thật trên trình duyệt — 4 phút

```
.\.venv\Scripts\python.exe scripts\tan_cong_that.py
```

Script mở Chromium headed, chờ trang load, chụp ảnh trạng thái ban đầu, rồi bấm nút
"THỬ CHIẾM QUYỀN ADMIN" — nút đó tự điền payload `admin' OR '1'='1--` và submit.
Kết quả tùy trạng thái bản vá:

| Trạng thái | Trang đến | Ý nghĩa |
|---|---|---|
| Chưa vá | `hacked.html` — "ADMIN ACCESS GRANTED" | Toàn bộ dữ liệu khách hàng bị lộ |
| Đã vá | `blocked.html` — "TẤN CÔNG ĐÃ BỊ CHẶN" | Cùng payload, cùng URL, nhưng lỗ hổng không còn |

Ảnh chụp nằm ở `artifacts/attack-*.png`. Dùng `--slow 600` nếu muốn chậm hơn để
khán giả kịp nhìn payload hình thành từng ký tự.

Nếu chạy đầu buổi (chưa vá): dùng kết quả "ADMIN ACCESS GRANTED" làm điểm mở. Nếu
chạy cuối buổi (đã vá): đây là điểm chốt — cùng một nút, cùng một payload, nhưng
lần này bản vá do AI viết và người duyệt đã chặn được.

Chốt buổi: chuỗi vừa đi qua không có chỗ nào AI tự quyết. Nó đọc, nó đề xuất, nó
viết test. Người duyệt, người chịu trách nhiệm, và mọi khẳng định "đã sửa" đều
phải có một phép đo đứng sau.

---

## Khi có sự cố

| Hỏng gì | Làm gì |
|---|---|
| Proxy hoặc mạng chết ở chặng 1 | `review_plan.py --ai cache` — nhãn `[AI · đã ghi lại]`, bản ghi thật |
| Phiên `claude` trả lời lệch kịch bản | Đọc thẳng cái nó ra. Nội dung sai thì bác bỏ tại chỗ, đó là beat chứ không phải sự cố |
| `claude` treo quá 30 giây | Ctrl+C, chuyển sang bản cache, đi tiếp |
| GitHub Actions không chạy | Bỏ chặng 5, nói rõ là mất mạng, sang chặng 6 bằng URL đã triển khai |
| URL production chết | Chạy `/version` trên máy local, nói rõ là local |
| Mất internet hoàn toàn | Chặng 1, 2, 2b, 3, 4 vẫn chạy được. Mất 5, 6, 7 |
