# Prompt chặng 2 — rà soát mã nguồn

Cùng cấu trúc hai lượt như chặng 1, vì đã chạy thử và nó giữ được nhịp: bảng
trước, đào sâu sau, khán giả chọn mã.

Khác biệt cốt lõi so với chặng 1: bây giờ đã có **một bản kế hoạch được duyệt**.
Câu hỏi không còn là "mã này có an toàn không" mà là "mã này có làm đúng điều đã
cam kết không". Theo §12.3 của `CLAUDE.md`, mã lệch khỏi kế hoạch đã duyệt là một
phát hiện, kể cả khi đoạn mã đó tự nó không có lỗ hổng nào.

Đó là điều một công cụ quét tĩnh không làm được. Semgrep đọc được `f"... {q} ..."`
trong câu SQL, nhưng không biết bản kế hoạch đã hứa gì. Nói câu đó ra khi chuyển
từ chặng này sang chặng quét.

Trong `app/transfer.py` **không có chú thích nào đánh dấu chỗ sai**. Nếu có thì
chặng này chỉ còn là đọc chú thích.

Mở cửa sổ PowerShell mới từ Windows, rồi:

```
cd D:\Seminar-DevSecOps\devsecops-ai-demo
claude
```

---

## Lượt A — bảng phát hiện

```
Đọc app/transfer.py và docs/plan/v2-chuyen-tien.md.

File mã nguồn được viết theo bản kế hoạch đó, sau khi bản kế hoạch đã qua rà soát
và được duyệt.

Rà soát mã nguồn. Tìm cả hai loại: lỗ hổng bảo mật trong mã, và những chỗ mã
không làm đúng điều bản kế hoạch đã quy định.

Trình bày kết quả CHỈ dưới dạng một bảng markdown, mỗi phát hiện đúng một dòng,
không có dòng nào khác chen vào giữa:

| Mã | Mức | Dòng | Mục kế hoạch | Quy tắc | CWE | Phát hiện |

Cột "Dòng" ghi số dòng trong app/transfer.py. Cột "Phát hiện" tối đa 10 từ.
Sắp xếp theo mức độ giảm dần.

Sau bảng, viết đúng năm dòng, mỗi dòng một câu:

- Kế hoạch đã làm đúng: <liệt kê mục, cách nhau bằng dấu phẩy>
- Lệch kế hoạch nhưng chưa chắc khai thác được: <liệt kê mã>
- Người phải quyết: <liệt kê, cách nhau bằng dấu phẩy>
- Nguy hiểm nhất: <một mã> — <lý do trong một câu>
- Trạng thái: chưa có phát hiện nào được sửa hay được kiểm chứng

Không viết đoạn văn giải thích. Không mở rộng phát hiện nào. Dừng lại sau năm dòng
đó và chờ tôi chỉ định.

Chỉ đọc và báo cáo. Không sửa file nào.
```

Lần chạy thử ra 18 phát hiện, bảng vừa một màn hình, dừng đúng chỗ. Số dòng nó
trích **khớp chính xác** với file — dòng 236 là `card_number`, 206 là
`new_balance`, 41 là `idempotency_key` thiếu `UNIQUE`. Nếu khán giả mở file kiểm
tra thì số khớp; đó là thứ đáng để mời họ kiểm.

## Lượt B — đào sâu một phát hiện

Đọc mã thật từ bảng vừa hiện, đừng học thuộc — mã không cố định giữa các lần chạy.

```
Đào sâu <MÃ>. Đúng bốn phần, mỗi phần tối đa 3 dòng:

1. Đường khai thác — kẻ tấn công gửi gì, từng bước
2. Dòng mã nào sai và sai ở chỗ nào
3. Sửa thế nào
4. Test nào chứng minh đã sửa xong, và test đó phải đỏ trước khi vá ra sao

Không nhắc lại phần đã có trong bảng.
```

## Chọn phát hiện nào để đào sâu

Chọn theo nội dung, không theo mã:

- **Đắt nhất**: hai hàm gợi ý người nhận (dòng 111 và 121). Một hàm dùng tham số
  buộc, hàm còn lại nối chuỗi và chỉ chạy khi có tham số `?nhanh=1` trong URL. Đây
  đúng hình dạng lỗi thật ngoài đời: hàm đầu đã được sửa, biến thể sinh sau bị bỏ
  quên. Lần chạy thử AI bắt được cả hai và nêu rõ điều kiện `nhanh=1`. Nếu lần
  diễn thật nó chỉ đọc hàm đầu rồi kết luận "đã tham số hoá" thì chỉ ra ngay tại
  chỗ — bài học đó đáng giá hơn một phát hiện đúng.
- **Dễ kể nhất**: `from_account` vẫn nhận từ thân yêu cầu (dòng 168). Kế hoạch v2
  mục C đã bỏ hẳn trường này khỏi hợp đồng API; mã vẫn đọc nó, kèm một chú thích
  viện lý do tương thích ngược. Lệch khỏi kế hoạch đã duyệt **và** là lỗ hổng.
- **Tinh vi nhất**: phép đổi số tiền (dòng 187). Lược đồ dùng số nguyên đơn vị xu
  đúng như kế hoạch, nhưng đường vào lại đi qua `float`, nên vẫn cắt cụt. Đúng cái
  bẫy "đã sửa lược đồ là xong".
- **Bất ngờ nhất, nếu nó xuất hiện**: khoá idempotency không giới hạn theo người
  gọi (dòng 198). Kẻ tấn công đoán được một khoá và gửi trước một lệnh vô hại bằng
  khoá đó; khi nạn nhân gửi lệnh thật, server thấy khoá đã tồn tại nên trả
  `duplicate` kèm mã giao dịch của kẻ tấn công — nạn nhân thấy báo thành công
  trong khi tiền chưa hề chuyển. Cơ chế đặt ra để chống trùng lặp lại thành công
  cụ nuốt giao dịch. Đã kiểm chứng bằng tay, không phải suy đoán.

## Beat mạnh nhất: bắt AI sai ngay trên sân khấu

Lần chạy thử, AI xếp **mức nghiêm trọng** cho một phát hiện nói rằng khi
`from_account` trùng `to_account` thì mã đọc cả hai số dư vào biến rồi ghi đè lên
nhau, làm tiền sinh ra từ không khí.

Tôi chạy thử: **chênh 0 xu.** Mã dùng hai câu `UPDATE` cộng và trừ trực tiếp trên
hàng, không đọc số dư ra biến, nên không có gì để ghi đè. Đây là dương tính giả.

Cách diễn: sau khi bảng hiện ra, chỉ vào phát hiện đó và hỏi "cái này khai thác
thật được không?", rồi chạy thử ngay tại chỗ để bác bỏ. Nếu lần diễn thật AI không
báo lỗi này thì bỏ beat — đừng bịa.

Câu chốt: AI đọc mã rồi suy ra sai; con người chạy thử rồi bác bỏ. Đó chính là lý
do §1 của chính sách bắt mọi phát hiện phải kèm đường khai thác — không phải để
làm khó AI, mà để cái sai lộ ra được.

## Beat sau khi rà soát: bộ test vẫn xanh

```
.\.venv\Scripts\python.exe -m pytest tests/test_transfer.py -q
```

5 xanh, 0 đỏ. Đúng lúc vừa liệt kê xong một loạt lỗ hổng trên màn hình bên cạnh.

Đây là F11 của chặng 1 hiện hình thành mã: bộ test viết theo mục §8 của kế hoạch
v1, toàn luồng thuận, không chạm tới bất kỳ tiêu chí AC-1…AC-13 nào. Xanh không
có nghĩa là an toàn — nó chỉ có nghĩa là không ai hỏi đúng câu hỏi.

Cả bộ test là 14 xanh 6 đỏ; sáu cái đỏ nằm ở `tests/test_security.py`, có từ
trước, cố tình đỏ cho tới khi vá xong. Nói rõ điều đó nếu chạy `pytest` không
giới hạn file, để không ai tưởng LB-214 làm hỏng thứ gì.
