# Prompt chặng 1 — rà soát bản kế hoạch

Hai lượt, không phải một. Lượt A cho ra một bảng đọc được từ cuối phòng; lượt B
đào sâu đúng một phát hiện do khán giả chọn.

Lý do tách: bản một lượt cho ra 14 phát hiện kèm văn xuôi, hơn 90 dòng cuộn qua
màn hình trong 10 giây. Nội dung đúng nhưng không ai đọc kịp, và người xem bỏ
cuộc từ phát hiện thứ ba. Bảng trước rồi mới đào sâu vừa giải quyết việc đó, vừa
biến chặng này thành có tương tác thay vì đọc chép. Đã chạy thử: lượt A ra 12
dòng và dừng đúng chỗ, lượt B vừa một màn hình.

Không nhắc tới `CLAUDE.md` trong prompt là có chủ đích: Claude Code tự nạp file đó
làm bộ nhớ dự án khi thư mục làm việc là repo. Nó trích đúng số hiệu `§` mà prompt
không hề đưa chính sách vào — đó là luận điểm của chặng này. Đã kiểm chứng: cùng
câu hỏi chạy ngoài repo thì trả lời không biết.

Câu "không sửa file nào" là bắt buộc: cấu hình máy đang ở `bypassPermissions`, nên
phiên tương tác sẽ không dừng lại xin phép trước khi ghi file.

Mở cửa sổ PowerShell mới từ Windows (không phải terminal lồng trong một phiên
Claude Code đang chạy), rồi:

```
cd D:\Seminar-DevSecOps\devsecops-ai-demo
claude
```

---

## Lượt A — bảng phát hiện

```
Đọc docs/plan/v1-chuyen-tien.md — bản kế hoạch tính năng LB-214 chuyển tiền, chưa
có dòng mã nào được viết.

Rà soát bảo mật ở tầng thiết kế.

Trình bày kết quả CHỈ dưới dạng một bảng markdown, mỗi phát hiện đúng một dòng,
không có dòng nào khác chen vào giữa:

| Mã | Mức | Mục kế hoạch | Quy tắc | CWE | Phát hiện |

Cột "Phát hiện" tối đa 10 từ. Sắp xếp theo mức độ giảm dần.

Sau bảng, viết đúng bốn dòng, mỗi dòng một câu:

- Đã xem xét, không tính là lỗi: <liệt kê mục, cách nhau bằng dấu phẩy>
- Người phải quyết: <liệt kê, cách nhau bằng dấu phẩy>
- Nguy hiểm nhất: <một mã> — <lý do trong một câu>
- Trạng thái: chưa có phát hiện nào được sửa hay được kiểm chứng

Không viết đoạn văn giải thích. Không mở rộng phát hiện nào. Dừng lại sau bốn dòng
đó và chờ tôi chỉ định.

Chỉ đọc và báo cáo. Không sửa file nào.
```

## Lượt B — đào sâu một phát hiện

Hỏi khán giả chọn mã nào, rồi gõ. **Thay `<MÃ>` bằng mã thật đọc từ bảng.** Lần
chạy thử để nguyên placeholder; AI tự chọn giúp nên không hỏng, nhưng trên sân
khấu thì mất đúng cái đáng giá của lượt này là để khán giả chọn.

Mã không cố định giữa các lần chạy, và tệ hơn: **cùng một mã trỏ vào phát hiện
khác nhau**. Bản cache đánh `F1…F13` với `F3` là kiểm tra số tiền; một lần tương
tác đánh `P-01…P-14`; lần khác `F-01…F-12` với `F-03` là ghi log số thẻ. Đừng học
thuộc mã — đọc bảng vừa hiện rồi mới chọn.

Chọn theo nội dung:

- **An toàn nhất**: phát hiện về quyền sở hữu `from_account`, CWE-639. Lần nào
  cũng có, luôn được xếp nguy hiểm nhất, đường khai thác dễ kể nhất.
- **Đắt nhất nếu nó xuất hiện**: race condition đọc số dư rồi mới trừ (CWE-367),
  hoặc `from_account` trùng `to_account`. Hai cái đó tôi không gài vào bản kế
  hoạch, AI tự suy ra. Nhưng chúng **không xuất hiện ở mọi lần chạy** — chỉ nói
  câu "cái này tôi không gài" khi thật sự thấy nó trong bảng hôm đó.

```
Đào sâu <MÃ>. Đúng bốn phần, mỗi phần tối đa 3 dòng:

1. Đường khai thác — kẻ tấn công làm gì, từng bước
2. Sẽ thành đoạn mã sai như thế nào — viết đoạn mã đó ra
3. Sửa bản kế hoạch ra sao
4. Test nào chứng minh đã sửa xong

Không nhắc lại phần đã có trong bảng.
```

---

## Bảng issue — chuyển từ terminal sang web

13 issue đã mở sẵn tại `tienml/Demo_Seminar`, số #1 đến #13, sinh từ chính bản ghi
rà soát. Mở trên trình duyệt để chiếu:

```
gh issue list --label bao-mat --web
```

Mỗi issue có nhãn mức độ, trích quy tắc `CLAUDE.md`, checklist tiêu chí nghiệm thu,
và một khối ghi rõ "chưa được người rà lại" — theo §1, *đã báo cáo* không phải
*đã kiểm chứng*.

Tạo lại hoặc dọn sau mỗi lần tập:

```
.\.venv\Scripts\python.exe scripts\plan_to_issues.py --don-dep --tao-that
.\.venv\Scripts\python.exe scripts\plan_to_issues.py --tao-that
```

Mã issue (`F1…F13`) đến từ bản cache, **không khớp** với mã trong bảng lượt A. Nếu
định trỏ từ màn hình terminal sang bảng issue thì trỏ theo tiêu đề, đừng theo mã.

## Bản dự phòng khi mạng hoặc proxy chết

```
.\.venv\Scripts\python.exe scripts\review_plan.py --ai cache
```

Đọc từ `agent/ai_cache/plan_review.json`, hiện nhãn `[AI · đã ghi lại]`. Bản ghi đó
do một lần gọi thật tạo ra, không phải viết tay — nói được sự thật nếu bị hỏi.

## Beat so sánh

```
.\.venv\Scripts\python.exe scripts\so_sanh_chinh_sach.py
```

Số đo đi ngược trực giác: bản không có chính sách tìm 20, bản có chính sách tìm 13.
Khác biệt thật là 13/13 neo được vào quy tắc viết ra, so với 0/20.

## Đối chiếu các lần chạy — dùng khi bị hỏi về độ tin cậy

| | Headless (`--record`) | Tương tác lần 1 | Tương tác lần 2 |
|---|---|---|---|
| Số phát hiện | 13 | 14 | 12 |
| Quyền sở hữu `from_account` (CWE-639) | có | có | có |
| Race condition đọc–ghi số dư (CWE-367) | có | có | không |
| Trùng `from_account`/`to_account` | không | có | không |

Ba lần chạy độc lập, hai đường gọi khác nhau, ra 12–14 phát hiện. Phát hiện nguy
hiểm nhất có mặt cả ba lần; chênh lệch nằm ở nhóm dưới. Đây là câu trả lời trung
thực cho câu hỏi "AI có ổn định không": ổn định ở chỗ nguy hiểm, dao động ở rìa —
và đó chính là lý do bản ghi cache tồn tại, để buổi diễn không phụ thuộc may rủi.
