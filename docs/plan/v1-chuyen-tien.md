# LB-214 · Chuyển tiền giữa hai tài khoản

| | |
|---|---|
| Mã tính năng | LB-214 |
| Người soạn | đội Core Banking |
| Trạng thái | **bản nháp v1 — chờ rà soát** |
| Ngày | 18/08/2026 |

## 1. Bối cảnh và mục tiêu

Khách hàng LabBank hiện chỉ xem được số dư và lịch sử giao dịch. Yêu cầu từ phía
nghiệp vụ: cho phép khách chuyển tiền sang một tài khoản khác trong cùng hệ thống,
hoàn tất trong một lần thao tác, không cần chờ duyệt.

Mục tiêu đo được: 95% giao dịch hoàn tất dưới 2 giây; tỷ lệ lỗi dưới 0,1%.

## 2. Phạm vi

**Trong phạm vi**

- Chuyển tiền nội bộ giữa hai tài khoản LabBank
- Giao diện web, một trang nhập liệu
- Lịch sử giao dịch có thêm mục chuyển tiền

**Ngoài phạm vi**

- Chuyển tiền liên ngân hàng
- Chuyển tiền theo lịch hẹn
- Huỷ giao dịch sau khi đã hoàn tất

## 3. Luồng nghiệp vụ

1. Khách đăng nhập, mở trang **Chuyển tiền**.
2. Khách nhập số tài khoản đích, hoặc gõ tên người nhận để hệ thống gợi ý. Ô gợi ý
   tra cứu theo tên chủ tài khoản bằng `LIKE '%tên%'` để khớp cả tên không đầy đủ.
3. Khách nhập số tiền và nội dung chuyển.
4. Hệ thống kiểm tra tài khoản nguồn và tài khoản đích **có tồn tại** trong bảng
   `accounts`.
5. Hệ thống kiểm tra số dư tài khoản nguồn có đủ hay không.
6. Hệ thống trừ tiền tài khoản nguồn, cộng tiền tài khoản đích, ghi một bản ghi
   vào bảng `transfers`. Ba việc này nằm trong cùng một transaction, lỗi ở bất kỳ
   bước nào thì rollback toàn bộ.
7. Hệ thống trả về mã giao dịch cho khách.

## 4. Thiết kế API

```
POST /api/transfer
Content-Type: application/json

{
  "from_account": "1234567890",
  "to_account":   "9876543210",
  "amount":       1500000.50,
  "note":         "tra tien an trua"
}
```

Trường `amount` nhận kiểu số thực để xử lý được phần lẻ.

**Phản hồi thành công**

```
200 OK
{ "transfer_id": "TRF-000123", "status": "completed", "new_balance": 3499999.50 }
```

## 5. Lược đồ dữ liệu

```sql
CREATE TABLE transfers (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  from_account  TEXT    NOT NULL,
  to_account    TEXT    NOT NULL,
  amount        REAL    NOT NULL,
  note          TEXT,
  created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 6. Xử lý lỗi

| Tình huống | Phản hồi |
|---|---|
| Tài khoản đích không tồn tại | `404` — "Không tìm thấy tài khoản đích" |
| Số dư không đủ | `400` — "Số dư không đủ để thực hiện giao dịch" |
| Lỗi cơ sở dữ liệu | `500` — rollback transaction, ghi log |

Nếu khách bấm **Gửi** lần nữa vì mạng chậm hoặc trang chưa phản hồi, hệ thống xử
lý như một yêu cầu mới. Phía giao diện sẽ khoá nút sau lần bấm đầu để hạn chế
tình huống này.

## 7. Ghi log

Mỗi giao dịch ghi một dòng log để đội vận hành tra soát khi khách khiếu nại:

```
[TRANSFER] user_id=%s from=%s to=%s card=%s amount=%s note=%s
```

Ghi đầy đủ số tài khoản và số thẻ liên kết để đối chiếu nhanh với hệ thống thẻ.

## 8. Kế hoạch kiểm thử

- Chuyển tiền thành công, số dư hai bên thay đổi đúng
- Chuyển tiền khi số dư không đủ, giao dịch bị từ chối
- Tài khoản đích không tồn tại, trả về 404
- Kiểm tra giao diện hiển thị đúng mã giao dịch

## 9. Kế hoạch triển khai

Triển khai thẳng lên production sau khi test chức năng đạt. Bật cho 10% khách
hàng trong tuần đầu, sau đó mở toàn bộ.
