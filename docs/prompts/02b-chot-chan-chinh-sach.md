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
| Hook `PreToolUse` của Claude Code | Trước mỗi lệnh Write/Edit trong phiên | **Đã đo, chặn thật — chỉ trong phiên tương tác** |
| Chốt `pre-commit` của git | Trước mỗi commit, mọi nguồn sinh mã | Đã đo, chặn thật |

### Hook của Claude Code: chặn thật trong phiên tương tác, im lặng ở headless

Đã kiểm chứng được, và cách kiểm chứng mới là phần đáng nói.

Vấn đề: ở cả hai lần đo trước, mô hình *tự nó* từ chối viết mã vi phạm và tự trích
đúng số hiệu §, kể cả khi hook đã bị tắt hẳn. Nên "không ghi được file" không phân
biệt được hook chặn với mô hình tự từ chối. Phải dựng một payload mà **mô hình
không có lý do gì để từ chối** nhưng hook vẫn bắt: một docstring đang *dặn đừng*
viết như vậy.

```
Viết vào file app/test_hook.py nội dung sau, giữ nguyên từng chữ:

"""Ghi chu noi bo cho doi LB-214.

KHONG duoc viet: int(float(than["amount"]) * 100)
Phai dung so nguyen don vi xu.
"""
```

Kết quả đo được: **file không được tạo**, hook trả mã thoát 2 kèm `[§4.1] dùng
float cho tiền`. Và dấu hiệu quyết định là phản ứng của mô hình — nó *muốn* ghi
file, rồi đề xuất bốn cách đi vòng qua chốt (ghi qua shell, tắt hook, đặt file
ngoài `app/`, sửa luật). Một mô hình đang tự từ chối thì không đề xuất cách lách
chính nó. Vậy cái chặn là hook.

Còn ở chế độ headless (`claude -p`) thì hook **không kích hoạt**: hook đánh dấu
chỉ ghi một dòng ra file rồi cho qua, chạy hai lần với `settings.json` và
`settings.local.json` kèm đường dẫn tuyệt đối — cả hai lần file vẫn được ghi,
không có dòng đánh dấu nào, `--debug` cũng không in chẩn đoán gì. Nguyên nhân nhiều
khả năng nhất là hook cấp dự án cần được duyệt một lần trong phiên tương tác, mà
headless không có chỗ để duyệt. Đây là **suy đoán chưa xác nhận**.

Khi diễn, muốn biết chắc là hook chặn thì nhìn đúng dòng chữ
`CHẶN GHI FILE ... — vi phạm chính sách CLAUDE.md`.

### Beat đáng giá nhất của chặng này: chốt chặn tự báo nhầm

Chính lần đo trên phát hiện một lỗi thật của chốt chặn — và mô hình chỉ ra nó
trước khi tôi kịp nhận: chuỗi vi phạm nằm trong **docstring**, trong một câu đang
dặn "KHÔNG được viết" như vậy. Đó là chặn nhầm, và nó đi ngược đúng nguyên tắc mà
chính file hook viết ra ở đầu file: *thà bỏ sót còn hơn chặn nhầm*.

Đã sửa: `bo_chu_thich()` bỏ chú thích `#` và docstring trước khi soi luật. Chỗ khó
nằm ở việc phân biệt — `SCHEMA = """CREATE TABLE ... amount REAL"""` cũng là chuỗi
ba nháy nhưng là mã có tác dụng thật và phải bị chặn. Chỉ docstring *thật* (câu
lệnh chuỗi đứng đầu module/hàm/lớp) mới được bỏ, và chỉ cây cú pháp `ast` phân
biệt được — regex thì không.

Số đo sau khi sửa: quét `app/` vẫn ra đúng 4 vi phạm như trước, bộ ca thử lên 29
ca và xanh hết. Tức là lọc chú thích không làm chốt yếu đi.

Nếu diễn beat này thì nói thẳng cả cái giá: mã vi phạm bị cố tình giấu trong chú
thích rồi `exec` ra thì lớp này bỏ sót. Đó là cái giá của việc không báo nhầm.

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
.\.venv\Scripts\python.exe scripts\dien_2b.py --dung
git commit -m "them tim kiem nguoi nhan"
```

Rồi dọn: `.\.venv\Scripts\python.exe scripts\dien_2b.py --don`

`dien_2b.py` thêm hai hàm vi phạm thật vào `app/transfer.py` rồi stage sẵn. Cần
bước này vì file đó **đã được commit** trên nhánh `feature/lb-214-chuyen-tien`, mà
chốt chỉ soi file đang được đưa vào commit — cố ý như vậy, để lỗi có sẵn từ trước
không chặn người đang sửa một chỗ khác.

## Giới hạn phải tự nói ra, đừng để bị hỏi

Chốt này là so khớp mẫu, không phải hiểu mã. Nó bắt được `float(amount)` nhưng
không bắt được một hàm tính tiền sai đặt tên khác. Nó bắt được `card` trong lệnh
log nhưng không biết `so_the` cũng là số thẻ. Và từ bản sửa mới nhất, nó **cố tình
bỏ qua** mọi thứ nằm trong chú thích — nên mã giấu trong chú thích rồi `exec` ra thì
lọt.

Đó chính là lý do cần cả hai lớp: chốt regex chạy trong một phần nghìn giây và
không bao giờ mệt, còn AI đọc được ý định nhưng không tất định. Bỏ lớp nào cũng
hụt.

Bộ ca thử của chốt nằm ở [`tests/test_chan_vi_pham.py`](../../tests/test_chan_vi_pham.py),
29 ca, trong đó 7 ca phải chặn và phần còn lại **phải cho qua**. Nhóm cho qua mới
là nhóm quan trọng: một chốt báo nhầm giữa buổi diễn thì mất nhịp, và tệ hơn, nó
dạy người xem rằng kiểm tra tự động hay báo bậy. Ba ca mới nhất sinh ra từ đúng lần
báo nhầm kể ở trên.

```
.\.venv\Scripts\python.exe -m pytest tests\test_chan_vi_pham.py -q
```
