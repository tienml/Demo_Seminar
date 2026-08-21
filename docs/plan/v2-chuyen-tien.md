# LB-214 · Chuyển tiền giữa hai tài khoản — bản v2

| | |
|---|---|
| Mã tính năng | LB-214 |
| Trạng thái | **v2 — đã rà soát theo `CLAUDE.md`** |
| Thay thế | `v1-chuyen-tien.md` |
| Ngày rà soát | 21/08/2026 |
| Nguồn phát hiện | `scripts/review_plan.py` — kết quả lưu ở `agent/ai_cache/plan_review.json` |

> Bản v2 giữ nguyên toàn bộ phần nghiệp vụ của v1. Phần thêm vào là các yêu cầu
> bảo mật phát sinh từ rà soát, cùng tiêu chí nghiệm thu có thể kiểm chứng bằng
> test tự động. Chưa có dòng mã nào được viết ở thời điểm rà soát này.

## A. Kết quả rà soát bản v1

Mười ba phát hiện ở tầng thiết kế. Không có phát hiện nào là lỗi mã nguồn — mã
chưa tồn tại. Đây là lý do chặng này là nơi rẻ nhất để tìm ra chúng.

| # | Phát hiện | Mục v1 | Quy tắc | CWE | Mức |
|---|---|---|---|---|---|
| F1 | Chỉ kiểm tra tài khoản **tồn tại**, không kiểm tra tài khoản nguồn **thuộc về người gọi**; `from_account` lại nhận từ thân yêu cầu — khách A chuyển được tiền từ tài khoản của khách B | §3.4, §4 | §3.1, §3.2 | CWE-639 | Nghiêm trọng |
| F2 | Không có khoá idempotency; kế hoạch còn ghi rõ yêu cầu gửi lại được xử lý như yêu cầu mới — khách bị trừ tiền hai lần | §6, §4, §5 | §4.2 | CWE-837 | Nghiêm trọng |
| F3 | Không kiểm tra số tiền dương và có chặn trên — số tiền âm đảo chiều dòng tiền và vẫn qua được bước kiểm tra số dư | §3.5, §4, §6 | §4.3 | CWE-20 | Nghiêm trọng |
| F4 | Dùng số thực cho tiền (`amount REAL`) — sai số cộng dồn, chọn được giá trị làm tròn có lợi | §4, §5 | §4.1 | CWE-681 | Cao |
| F5 | Ô gợi ý người nhận dựng truy vấn `LIKE '%tên%'` bằng nối chuỗi | §3.2 | §2.1, §2.2 | CWE-89 | Cao |
| F6 | Ghi log số thẻ và số tài khoản đầy đủ | §7 | §6.1 | CWE-532 | Cao |
| F7 | Không có dấu vết kiểm toán bền vững; giao dịch bị từ chối không để lại bản ghi nào vì đã rollback cùng transaction | §7, §5 | §6.2 | CWE-778 | Trung bình |
| F8 | Không có giới hạn tần suất trên endpoint chuyển tiền và endpoint gợi ý tên | §4, §6 | §7.1 | CWE-307 | Cao |
| F9 | Đọc số dư ở bước 5 rồi mới trừ ở bước 6, không khoá hàng — hai yêu cầu song song đều qua kiểm tra, chi vượt số dư | §3.5, §3.6 | §4.4 | CWE-367 | Cao |
| F10 | Không quy định bốn header bảo mật và cờ `HttpOnly`/`Secure`/`SameSite` cho cookie phiên | §3.1, §4 | §8.1, §8.2 | CWE-693 | Trung bình |
| F11 | Kế hoạch kiểm thử chỉ có luồng thuận, không có test âm nào — F1–F10 đi qua bộ test mà vẫn xanh | §8 | §12.1, §12.2 | — | Cao |
| F12 | Khoá nút giao diện được dùng làm cơ chế chống trùng lặp; gọi API bằng `curl` là biện pháp này không tồn tại | §6 | §3.3 | CWE-602 | Cao |
| F13 | Triển khai production chỉ cần "test chức năng đạt", không có rà soát bảo mật và không có phê duyệt của người | §9 | §13, §12.3 | — | Trung bình |

F1, F2, F3 tự khai thác được. F2 kết hợp F9 thì chỉ cần phát lại yêu cầu song
song là rút vượt số dư. F5 làm F1 dễ hơn vì nó rò ra danh sách số tài khoản.

### Đã xem xét nhưng không tính là phát hiện

Theo §1, không cảnh báo nào bị loại trong im lặng.

- **§3.6 — ba thao tác đổi số dư trong cùng một transaction có rollback.** Đúng
  §4.4. Phần còn thiếu là khoá chống tranh chấp, đã tách thành F9, không tính trùng.
- **§6 — dòng "Lỗi cơ sở dữ liệu → 500, rollback transaction".** Có rollback tường
  minh ở nhánh lỗi. Thông báo lỗi cũng không tiết lộ chi tiết nội bộ.
- **§4 — trả `new_balance` cho khách.** §6.1 cấm ghi số dư vào log, không cấm trả
  cho chính chủ qua kênh đã xác thực. Chỉ hợp lệ **với điều kiện F1 được sửa**;
  nếu vẫn nhận `from_account` từ client thì đây thành kênh đọc số dư người khác.
- **§2 — loại trừ chuyển liên ngân hàng, chuyển theo lịch, huỷ giao dịch.** Thu hẹp
  bề mặt tấn công một cách tường minh.
- **§6 — trả `404` "Không tìm thấy tài khoản đích".** Là kênh dò tồn tại tài khoản
  thật, nhưng chính sách hiện không có quy tắc nào về chống liệt kê định danh.
  Chuyển sang mục H thay vì tự ý coi là lỗi.
- **§9–§11 của chính sách (thư viện, container, hạ tầng).** Kế hoạch không đổi gì
  ở ba tầng này nên không có gì để đối chiếu. Nếu khi làm F8 có thêm thư viện giới
  hạn tần suất thì phải ghim phiên bản chính xác theo §9.1.
- **§1 — mục tiêu 95% dưới 2 giây.** Chỉ tiêu hiệu năng, không xung đột quy tắc
  nào. Lưu ý duy nhất: không lấy nó làm lý do bỏ khoá hàng ở F9 hay bỏ F8.

## B. Luồng nghiệp vụ sửa lại

Thay đổi so với v1 in **đậm**.

1. Khách đăng nhập, mở trang **Chuyển tiền**. **Phản hồi đi qua middleware đặt đủ
   bốn header §8.1; cookie phiên bật `HttpOnly`, `Secure`, `SameSite`.**
2. Khách nhập số tài khoản đích, hoặc gõ tên người nhận để hệ thống gợi ý. **Mẫu
   `LIKE` truyền qua tham số buộc (`LIKE ?` với giá trị `%q%` bind vào), thoát `%`
   và `_`, tập trung tại một hàm truy vấn duy nhất.** Kết quả chỉ trả về tên đã
   che và bốn số cuối tài khoản.
3. Khách nhập số tiền và nội dung. **Giao diện sinh một `Idempotency-Key` dạng
   UUIDv4 cho mỗi lần mở form.**
4. **Tài khoản nguồn lấy từ phiên phía máy chủ, không nhận từ thân yêu cầu.** Nếu
   hợp đồng buộc phải nhận thì xác minh `account.owner_id == session.user_id` và
   trả `403` khi lệch, không tiết lộ tài khoản có tồn tại hay không.
5. Hệ thống xác minh tài khoản đích tồn tại và đang hoạt động.
6. **Hệ thống kiểm tra `Idempotency-Key`.** Đã xử lý rồi thì trả về nguyên kết quả
   lần đầu, không tạo giao dịch mới. **Đây là chốt duy nhất được tính; việc khoá
   nút ở giao diện chỉ là cải thiện trải nghiệm (F12).**
7. **Hệ thống kiểm tra số tiền: kiểu `Decimal`, lớn hơn 0, không vượt hạn mức mỗi
   lần và hạn mức ngày.** Mỗi loại vi phạm có mã lỗi `400` riêng.
8. **Hệ thống trừ tiền bằng một câu `UPDATE ... WHERE balance >= :amount` rồi kiểm
   tra số hàng bị ảnh hưởng, hoặc khoá hàng theo thứ tự cố định.** Không đọc số dư
   ra rồi mới quyết định (F9).
9. Hệ thống trừ, cộng, ghi bản ghi `transfers` trong cùng một transaction có
   rollback. **Bản ghi kiểm toán ghi ngoài transaction nghiệp vụ để tồn tại cả khi
   giao dịch bị từ chối (F7).**
10. Hệ thống trả mã giao dịch.

## C. Thiết kế API sửa lại

```
POST /api/transfer
Content-Type: application/json
Idempotency-Key: 3f9a1c7e-5b2d-4e81-9f3a-0c7d21e4b6a8

{
  "to_account": "9876543210",
  "amount":     "1500000.50",
  "note":       "tra tien an trua"
}
```

`from_account` **đã bỏ khỏi hợp đồng** — máy chủ lấy từ phiên (F1).

`amount` truyền dạng **chuỗi**, phía máy chủ chuyển sang `Decimal`. Không nhận
kiểu số thực của JSON (F4).

Thiếu header `Idempotency-Key` thì trả `400`.

Mã lỗi bổ sung: `403` sai chủ sở hữu, `429` vượt tần suất, `400` số tiền không
hợp lệ hoặc vượt hạn mức.

## D. Lược đồ dữ liệu sửa lại

```sql
CREATE TABLE transfers (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  idempotency_key TEXT    NOT NULL UNIQUE,   -- F2
  from_account    TEXT    NOT NULL,
  to_account      TEXT    NOT NULL,
  amount_minor    INTEGER NOT NULL,          -- F4: đơn vị đồng, số nguyên
  note            TEXT,
  initiated_by    INTEGER NOT NULL,          -- F1: ai thực hiện
  created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE transfer_audit (                -- F7: tồn tại cả khi bị từ chối
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  actor_user_id INTEGER NOT NULL,
  ip            TEXT    NOT NULL,
  user_agent    TEXT,
  ket_qua       TEXT    NOT NULL,            -- 'thanh_cong' | 'tu_choi'
  ly_do         TEXT,
  created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE accounts ADD CONSTRAINT balance_khong_am CHECK (balance >= 0);  -- F9
```

Ràng buộc `UNIQUE` trên `idempotency_key` là chốt cuối ở tầng dữ liệu, chạy đúng
cả khi có hai yêu cầu song song. `CHECK balance >= 0` là lưới cuối cho F9.

## E. Ghi log sửa lại

```
[TRANSFER] user_id=%s from=****%s to=****%s amount_minor=%d key=%s result=%s
```

Bỏ hoàn toàn số thẻ (F6). Số tài khoản chỉ giữ bốn số cuối. Không ghi số dư đầy
đủ. Dấu vết kiểm toán ghi vào `transfer_audit`, không lẫn với log gỡ lỗi (F7).

## F. Giới hạn tần suất

Tối đa 10 yêu cầu chuyển tiền mỗi phút cho mỗi tài khoản, và 30 mỗi phút cho mỗi
địa chỉ IP. Endpoint gợi ý tên áp cùng cơ chế. Vượt ngưỡng trả `429` (F8).

## G. Tiêu chí nghiệm thu

Mỗi tiêu chí phải có test âm tương ứng theo §12.1, và phải **đỏ trước khi vá**
theo §12.2. Đây là đầu vào trực tiếp của chặng kiểm thử.

| Mã | Tiêu chí | Phát hiện |
|---|---|---|
| AC-1 | Gọi `POST /api/transfer` với tài khoản nguồn không thuộc người đang đăng nhập trả `403`; số dư cả hai tài khoản không đổi | F1 |
| AC-2 | Hai yêu cầu giống nhau cùng một `Idempotency-Key` chỉ tạo đúng một bản ghi `transfers`; lần hai trả lại đúng `transfer_id` lần đầu | F2 |
| AC-3 | `amount` bằng 0, âm, không phải số, hoặc vượt hạn mức đều trả `400` và không sinh bản ghi `transfers` nào | F3 |
| AC-4 | Chuyển 0,10 rồi 0,20 cho ra biến động đúng 0,30 tuyệt đối; cột `amount` không phải `REAL`/`FLOAT`; mã không dùng `float` cho tiền | F4 |
| AC-5 | Ô gợi ý với `' OR 1=1--` và với `UNION SELECT` trả kết quả rỗng hoặc `400`, không trả thêm bản ghi, không sinh lỗi cú pháp SQL | F5 |
| AC-6 | Sau một giao dịch thành công, log không chứa số thẻ, số tài khoản đầy đủ hay số dư; số tài khoản chỉ hiện dạng che bốn số cuối | F6 |
| AC-7 | Mỗi lần gọi chuyển tiền, **kể cả khi bị từ chối**, sinh đúng một bản ghi `transfer_audit` gồm actor, thời điểm, IP, kết quả kèm lý do | F7 |
| AC-8 | Vượt ngưỡng số lệnh trong cửa sổ thời gian, tính theo cả tài khoản và theo IP, trả `429` và không thực hiện giao dịch | F8 |
| AC-9 | Hai yêu cầu song song trên tài khoản chỉ đủ số dư cho một lệnh: đúng một thành công, một bị từ chối, số dư cuối không âm | F9 |
| AC-10 | Phản hồi trang Chuyển tiền và `/api/transfer` có đủ `X-Content-Type-Options`, `X-Frame-Options`, `Content-Security-Policy`, `Strict-Transport-Security`; cookie phiên có `HttpOnly`, `Secure`, `SameSite` | F10 |
| AC-11 | Bộ kiểm thử có ít nhất một test âm cho mỗi tiêu chí AC-1…AC-10, và mỗi test âm được chứng minh đỏ trên mã chưa vá | F11 |
| AC-12 | Gọi trực tiếp `/api/transfer` bằng công cụ dòng lệnh, bỏ qua giao diện, vẫn bị chặn trùng lặp bởi cơ chế phía máy chủ | F12 |
| AC-13 | Pipeline từ chối phát hành khi thiếu kết quả rà soát bảo mật đạt hoặc thiếu phê duyệt tường minh của người chịu trách nhiệm | F13 |

> **Ghi chú rà soát của người.** Trong lần chạy AI, AC-8 bị đánh nhãn `F9` thay vì
> `F8`. Nội dung tiêu chí đúng, chỉ sai tham chiếu. Đã sửa ở bảng trên. Ghi lại
> đây vì §1 yêu cầu phân biệt điều đã kiểm chứng với điều chỉ được báo cáo — và
> vì đây là ví dụ cụ thể cho việc kết quả AI vẫn cần người đọc lại.

## H. Việc con người phải quyết

Theo §13, bảy việc sau không được tự động hoá và phải chuyển cho người duyệt:

- **Phê duyệt triển khai production** và tỷ lệ mở 10% ở §9 của v1 — AI không quyết
  được mức rủi ro tiền thật mà tổ chức chấp nhận.
- **Hạn mức mỗi lần và hạn mức ngày** cho F3 — quyết định nghiệp vụ và ngưỡng báo
  cáo của LabBank. Bản kế hoạch để trống có chủ đích.
- **Ngưỡng giới hạn tần suất** cho F8 — 10 và 30 là giá trị khởi điểm đề xuất, cần
  số liệu lưu lượng thật và tỷ lệ khách dùng chung IP (NAT doanh nghiệp).
- **Đội vận hành có thật cần dữ liệu thẻ để tra soát khiếu nại hay không**, và mã
  tham chiếu thay thế nào là hợp lệ (F6) — thuộc quy trình nghiệp vụ và yêu cầu
  tuân thủ dữ liệu thẻ.
- **Hệ thống hiện tại đã có middleware header §8.1 và cờ cookie §8.2 chưa** — phải
  xem cấu hình ứng dụng đang chạy. F10 nêu ra như khoảng trống của tài liệu, không
  phải kết luận về mã hiện hữu.
- **Có yêu cầu chống liệt kê tài khoản** qua phản hồi `404` và ô gợi ý tên hay
  không — chính sách hiện chưa có quy tắc tương ứng; chủ sở hữu chính sách quyết
  định bổ sung hay chấp nhận rủi ro còn lại.
- **Chấp nhận rủi ro còn lại** cho mọi mục ở phần "không phải phát hiện".

## I. Điều kiện triển khai

Sửa §9 của v1. Ba điều kiện tiên quyết, thiếu một là pipeline chặn (F13):

1. Rà soát bảo mật đạt.
2. Toàn bộ test âm ở AC-11 xanh, và có bằng chứng chúng đã đỏ trước khi vá.
3. Phê duyệt tường minh của người chịu trách nhiệm — trước khi bật cho **bất kỳ**
   tỷ lệ khách hàng nào, kể cả 10%.
