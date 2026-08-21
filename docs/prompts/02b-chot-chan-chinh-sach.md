# Chặng 2b — chính sách thành chốt chặn, không còn là tài liệu

Chặng 1 và 2 đều là *phát hiện sau khi đã lỡ*: kế hoạch viết xong rồi mới rà, mã
viết xong rồi mới rà. Chặng này là bước còn lại — chính sách chạy như một cái
chốt, mã vi phạm không kịp nằm trên đĩa.

Một câu để nói khi chuyển chặng: chuyển từ *AI đọc chính sách* sang *chính sách
chặn cả AI*.

Bộ luật nằm ở [`.claude/hooks/chan_vi_pham.py`](../../.claude/hooks/chan_vi_pham.py),
bốn luật lấy thẳng từ `CLAUDE.md`: nối chuỗi vào SQL (§2.1, §2.2), `float` cho
tiền (§4.1), cột tiền kiểu `REAL` (§4.1), ghi số thẻ vào log (§6.1).

## Hai đường chạy, và đường nào đã được kiểm chứng

| | Chạy khi nào | Trạng thái |
|---|---|---|
| Hook `PreToolUse` của Claude Code | Trước mỗi lệnh Write/Edit trong phiên | **Chưa kiểm chứng được** — xem dưới |
| Chốt `pre-commit` của git | Trước mỗi commit, mọi nguồn sinh mã | Đã đo, chặn thật |

### Chỗ chưa kiểm chứng được, nói thẳng ra

Hook của Claude Code **không kích hoạt** khi gọi `claude -p` ở chế độ headless.
Tôi dựng một hook đánh dấu chỉ ghi một dòng ra file rồi cho qua, chạy hai lần —
một lần với `.claude/settings.json`, một lần với `.claude/settings.local.json` và
đường dẫn tuyệt đối. Cả hai lần: file vẫn được ghi, **không có dòng đánh dấu nào**.
`--debug` không in ra chẩn đoán gì về hook.

Nguyên nhân nhiều khả năng nhất là hook ở cấp dự án cần được duyệt một lần trong
phiên tương tác, mà chế độ headless thì không có chỗ để duyệt. Đây là **suy đoán
chưa xác nhận**, không phải kết luận.

Việc cần làm trước hôm diễn: mở một phiên `claude` tương tác trong repo, gõ
`/hooks` và xem hook có được liệt kê không, duyệt nếu nó hỏi. Rồi bảo nó viết một
đoạn mã vi phạm vào `app/` và xem có bị chặn không.

**Cẩn thận khi thử:** ở cả hai lần đo, mô hình *tự nó* từ chối viết mã vi phạm và
tự trích đúng số hiệu §, kể cả khi hook đã bị tắt hẳn. Nên nếu chỉ nhìn kết quả
"không ghi được file" thì không phân biệt được là hook chặn hay mô hình tự từ
chối. Muốn biết chắc phải nhìn thông báo: hook chặn thì ra đúng chữ
`CHẶN GHI FILE ... — vi phạm chính sách CLAUDE.md`.

Chuyện mô hình tự từ chối tự nó cũng là một beat tốt, và trung thực hơn: `CLAUDE.md`
tự nạp làm bộ nhớ dự án, nên nó không chịu viết mã vi phạm ngay từ đầu. Nhưng đừng
gọi đó là "hook đã chặn" nếu chưa thấy đúng dòng chữ trên.

### Đường chắc chắn chạy: chốt ở git

Đã đo trên máy: stage `app/transfer.py` rồi commit → bị chặn, in ra ba vi phạm
(§2.1/§2.2, §4.1, §6.1), không có commit nào được tạo. File sạch thì cho qua.

Bật cho mỗi bản sao repo:

```
git config core.hooksPath .githooks
```

Hoặc không đổi cấu hình:

```
cp .githooks/pre-commit .git/hooks/pre-commit
```

Trên máy demo đã cài sẵn theo cách thứ hai.

Chốt này mạnh hơn hook của Claude Code ở đúng một điểm đáng nói trên sân khấu: nó
không quan tâm mã đến từ đâu. AI sinh, IDE gợi ý, gõ tay, dán từ diễn đàn — đều đi
qua cùng một cửa. Chốt chỉ tin cậy được khi nó không phụ thuộc vào công cụ nào
sinh ra mã.

## Diễn chặng này thế nào

Chạy quét trước để có bảng vi phạm:

```
.\.venv\Scripts\python.exe .claude\hooks\chan_vi_pham.py --quet app\
```

Ra 4 vi phạm: một ở `app/auth.py` (lỗ hổng SQLi có từ đầu repo), ba ở
`app/transfer.py`. Ba cái sau đúng bằng ba phát hiện mà AI đã tìm ra ở chặng 2 —
điểm đáng nói là **cùng một chính sách sinh ra cả hai**, một bên là AI đọc và suy
luận, một bên là mấy chục dòng regex.

Rồi thử commit thật để thấy nó chặn:

```
git add app\transfer.py
git commit -m "them tinh nang chuyen tien"
```

Rồi bỏ stage: `git reset`

## Giới hạn phải tự nói ra, đừng để bị hỏi

Chốt này là so khớp mẫu, không phải hiểu mã. Nó bắt được `float(amount)` nhưng
không bắt được một hàm tính tiền sai đặt tên khác. Nó bắt được `card` trong lệnh
log nhưng không biết `so_the` cũng là số thẻ.

Đó chính là lý do cần cả hai lớp: chốt regex chạy trong một phần nghìn giây và
không bao giờ mệt, còn AI đọc được ý định nhưng không tất định. Bỏ lớp nào cũng
hụt.

Bộ ca thử của chốt nằm ở [`tests/test_chan_vi_pham.py`](../../tests/test_chan_vi_pham.py),
23 ca, trong đó 7 ca phải chặn và phần còn lại **phải cho qua**. Nhóm cho qua mới
là nhóm quan trọng: một chốt báo nhầm giữa buổi diễn thì mất nhịp, và tệ hơn, nó
dạy người xem rằng kiểm tra tự động hay báo bậy.

```
.\.venv\Scripts\python.exe -m pytest tests\test_chan_vi_pham.py -q
```
