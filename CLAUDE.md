# Chính sách bảo mật dự án LabBank

Đây là nguồn sự thật duy nhất về yêu cầu bảo mật của dự án. Mọi chặng trong quy
trình đều đọc file này: rà soát bản kế hoạch, viết mã, sinh bộ kiểm thử, chọn
cảnh báo nào đáng vá, và soạn nội dung bàn giao cho người duyệt.

Một yêu cầu bảo mật không nằm trong file này thì không tồn tại. Một quy tắc nằm
trong file này thì áp dụng cho cả sáu chặng, không cần ai nhắc lại.

## §1 · Cách báo cáo phát hiện

Mỗi phát hiện phải ghi đủ bốn thứ: **quy tắc bị vi phạm** (số hiệu §), **vị trí**
(tệp và dòng, hoặc mục trong tài liệu), **mã CWE**, và **lý do bằng chữ** giải
thích đường khai thác thực tế.

Không được loại bỏ cảnh báo trong im lặng. Mỗi cảnh báo bị gạt phải kèm lý do
gạt: trùng với công cụ nào, không nằm trên đường đi của dữ liệu người dùng, hay
nhà phát hành chưa có bản vá.

Không được báo cáo là đã xử lý xong một việc mà thực tế chỉ mới đề xuất cách xử
lý. Phân biệt rõ *đã sửa và đã kiểm chứng* với *đã sửa nhưng chưa kiểm chứng*.

## §2 · Truy vấn dữ liệu — CWE-89

**§2.1** Mọi truy vấn phải tham số hoá. Cấm nối chuỗi, cấm f-string, cấm
`%`-format để dựng câu lệnh SQL, kể cả khi giá trị đưa vào trông như số.

**§2.2** Khi một hàm dựng truy vấn được gọi từ nhiều nơi, bản vá phải sửa tại
hàm đó, không sửa lẻ từng nơi gọi. Rà soát phải liệt kê đủ mọi nơi gọi.

## §3 · Xác thực và phân quyền — CWE-862, CWE-639

**§3.1** Mọi truy cập vào một bản ghi phải xác minh **quyền sở hữu**, không phải
sự tồn tại. Kiểm tra "bản ghi này có tồn tại không" là chưa đạt yêu cầu; phải
kiểm tra "bản ghi này có thuộc về người đang gọi không".

**§3.2** Định danh bản ghi do phía client gửi lên luôn bị coi là không đáng tin,
kể cả khi nó vừa được chính hệ thống trả về ở bước trước.

**§3.3** Kiểm tra quyền phải nằm ở tầng máy chủ. Ẩn nút trên giao diện không phải
là kiểm soát truy cập.

## §4 · Tiền và giao dịch — CWE-681, CWE-837

**§4.1** Cấm dùng số thực dấu phẩy động cho tiền. Dùng `Decimal` hoặc số nguyên
theo đơn vị nhỏ nhất.

**§4.2** Mọi nghiệp vụ làm thay đổi số dư phải có **khoá idempotency** do client
sinh và server lưu lại. Gửi lại cùng một khoá phải trả về kết quả của lần xử lý
đầu tiên, không tạo giao dịch mới. Đây là yêu cầu bắt buộc, không phải tối ưu.

**§4.3** Số tiền phải được kiểm tra là dương, khác không, và có chặn trên.

**§4.4** Thay đổi số dư của hai tài khoản phải nằm trong cùng một giao dịch cơ sở
dữ liệu, có rollback khi lỗi.

## §5 · Khoá bí mật — CWE-798

**§5.1** Không có khoá, token, mật khẩu, chuỗi kết nối nào được nằm trong mã
nguồn. Đọc từ biến môi trường, không có giá trị mặc định dùng được cho production.

**§5.2** Một khoá đã từng nằm trong lịch sử Git là **khoá đã lộ**. Xoá khỏi mã
nguồn không làm nó hết hiệu lực. Việc thu hồi ở phía nhà cung cấp là hành động
bắt buộc và phải do con người thực hiện.

## §6 · Log và dữ liệu cá nhân — CWE-532

**§6.1** Cấm ghi log số thẻ, mã CVV, mật khẩu, token, số dư đầy đủ. Số tài khoản
phải che, chỉ giữ bốn số cuối.

**§6.2** Mọi nghiệp vụ tiền phải để lại dấu vết kiểm toán: ai thực hiện, lúc nào,
từ địa chỉ nào, kết quả ra sao. Dấu vết kiểm toán khác với log gỡ lỗi.

## §7 · Giới hạn tần suất — CWE-307

**§7.1** Endpoint đăng nhập, đặt lại mật khẩu và mọi endpoint chuyển tiền phải có
giới hạn tần suất theo cả tài khoản và địa chỉ IP.

## §8 · Tầng HTTP — CWE-693

**§8.1** Bắt buộc có `X-Content-Type-Options`, `X-Frame-Options`,
`Content-Security-Policy`, `Strict-Transport-Security`.

**§8.2** Cookie phiên phải bật `HttpOnly`, `Secure`, `SameSite`.

## §9 · Thư viện phụ thuộc

**§9.1** Ghim phiên bản chính xác. Không dùng dải phiên bản mở.

**§9.2** Lỗ hổng thư viện chỉ đáng vá khi gói đó **thực sự được nạp lúc chạy** và
nhà phát hành **đã có bản vá**. Thiếu một trong hai điều kiện thì ghi nhận và
giải thích, không tiêu tốn thời gian của đội.

## §10 · Container

**§10.1** Không chạy bằng `root`. Ảnh nền ghim theo digest, không dùng `:latest`.
Phải có `HEALTHCHECK`. Không sao chép khoá bí mật vào ảnh.

## §11 · Hạ tầng dưới dạng mã

**§11.1** Không có luật cho phép truy cập từ `0.0.0.0/0`, trừ cổng 443 của tầng
public. Dải quản trị phải khai báo qua biến, không viết cứng.

**§11.2** Bật mã hoá khi lưu trữ, chặn truy cập công khai, bật log truy cập.

## §12 · Kiểm thử

**§12.1** Mỗi yêu cầu bảo mật ở trên phải có **ít nhất một test âm** — test mô tả
hành vi tấn công và kỳ vọng bị chặn. Test chỉ đi qua luồng thuận là chưa đạt.

**§12.2** Test bảo mật phải **đỏ trước khi vá và xanh sau khi vá**. Một test bảo
mật xanh ngay từ đầu là test không kiểm chứng điều gì.

**§12.3** Mã nguồn phải thoả **tiêu chí nghiệm thu của bản kế hoạch đã duyệt**.
Lệch khỏi kế hoạch là một phát hiện, ngang hàng với một lỗ hổng.

## §13 · Giới hạn — những việc con người phải quyết

Các việc sau đây tuyệt đối không được tự động thực hiện hay tự nhận là đã xong.
Phải nêu ra và chuyển cho người duyệt:

- Thu hồi khoá đã lộ ở phía nhà cung cấp (§5.2).
- Chọn dải mạng thật cho biến quản trị (§11.1) — không ai ngoài chủ hệ thống biết
  giá trị đúng.
- Phê duyệt triển khai lên production.
- Chấp nhận rủi ro còn lại cho bất kỳ phát hiện nào bị gạt.

Khi không đủ dữ kiện để quyết, nói rõ là không đủ dữ kiện. Không đoán rồi trình
bày như một kết luận.
