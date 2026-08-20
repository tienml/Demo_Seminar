# LabBank — demo AI-Augmented DevSecOps

Một ứng dụng ngân hàng giả, cố ý dính sáu lỗ hổng, kèm một pipeline DevSecOps
đầy đủ và một AI agent tự phân loại cảnh báo, tự vá, tự kiểm thử, tự sửa lại khi
bản vá của chính nó làm hỏng thứ khác, rồi dừng trước cổng phê duyệt của con
người.

Thiết kế xoay quanh một ràng buộc duy nhất: **cả buổi chỉ có một mã QR, một địa
chỉ web.** Khán giả quét một lần lúc mở màn và chiếm được quyền admin. Cuối buổi
họ bấm lại đúng cái nút đó, trên đúng địa chỉ đó, và lần này bị chặn. Không có
mã QR thứ hai, không có "bản staging" nào lộ ra ngoài — nếu có, khán giả sẽ nghĩ
đó là hai website khác nhau và toàn bộ hiệu ứng đối chiếu trước/sau sẽ mất.

---

## Trạng thái ứng dụng không phải một cái cờ

Đây là chi tiết đáng bảo vệ nhất trong toàn bộ thiết kế, và cũng là câu trả lời
cho câu hỏi khó nhất mà khán giả có thể hỏi.

Endpoint `/version` không đọc biến cấu hình nào cả. Nó **chạy lại chính payload
tấn công** lên chính hàm xác thực của ứng dụng rồi báo cáo kết quả:

```135:138:app/main.py
    @app.get("/version")
    def version():
        """Tự kiểm chứng trạng thái bảo mật bằng cách chạy lại payload tấn công."""
        vulnerable = injection_succeeds()
```

Nghĩa là dải màu trên điện thoại khán giả là một phép đo trực tiếp trên mã đang
chạy, không phải một thông báo do người trình bày bật lên. Cũng vì vậy, không có
cách nào "diễn" trạng thái đã vá mà không thật sự vá.

Tương tự, `agent/verify.py` chạy pytest trong **tiến trình con** trên mã vừa ghi
xuống đĩa, và chạy lại payload trong một interpreter mới. Agent không thể tự
tuyên bố mình thành công.

---

## Ranh giới trung thực — hãy nói câu này với khán giả

Nói thẳng ngay từ đầu thì bạn được tin cả buổi; bị phát hiện giữa chừng thì mất
sạch. Câu ngắn gọn để nói:

> Các bản vá trong demo này là những thay đổi đã được soạn sẵn và áp dụng theo
> kịch bản — tôi không gọi API của một mô hình ngôn ngữ trên sân khấu. Nhưng
> toàn bộ phần **xác minh** là thật: pytest chạy thật trên mã vừa ghi, payload
> được chạy lại thật, và địa chỉ công khai kia cũng được tấn công thật.

Phần agent tự phát hiện bản vá của mình làm hỏng `app/external.py` rồi tự sửa
(Chặng 4) là một chuỗi nhân quả có thật, không dàn dựng: bản vá secret xoá hằng
số `ADMIN_API_KEY`, module khác đang `import` hằng số đó, nên pytest đỏ vì
`ImportError` thật.

---

## Sáu lỗ hổng cố ý

| Tầng | Lỗ hổng | Mã | Công cụ bắt được |
|---|---|---|---|
| Mã ứng dụng | SQL Injection ở khâu xác thực | CWE-89 | Semgrep |
| Mã ứng dụng | Ba khoá bí mật nhúng cứng | CWE-798 | Gitleaks |
| Mã ứng dụng | Đọc được hồ sơ người khác qua id trên URL | CWE-639 | Semgrep |
| Mã ứng dụng | Thiếu header bảo mật HTTP | CWE-693 | Semgrep |
| Thư viện | `requests` 2.25.1 | CVE-2023-32681, CVE-2024-35195 | Trivy |
| Container | Chạy quyền root, base image cũ | CWE-250 | Hadolint, Trivy |
| Hạ tầng | SSH và toàn dải cổng mở ra `0.0.0.0/0` | CWE-284, CWE-732 | Checkov |

Hàm dựng câu lệnh SQL được gọi từ **ba** nơi (đăng nhập, quên mật khẩu, ô tìm
kiếm quản trị). Công cụ so khớp mẫu báo ba cảnh báo rời rạc; agent đọc call graph
nhận ra cả ba cùng một gốc và vá trọn gói. Đây là ví dụ cụ thể nhất cho luận điểm
"AI hiểu ngữ cảnh mã nguồn" mà bạn nêu ở phần lý thuyết.

Ba khoá bí mật là **chuỗi bịa**, không phải credential thật.

---

## Chuẩn bị một lần

### 1. Môi trường trên máy

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -r requirements.txt -r requirements-dev.txt
```

Kiểm tra ngay:

```bash
pytest tests/test_functional.py -q      # phải XANH  (9 passed)
pytest tests/test_security.py -q        # phải ĐỎ    (6 failed)
```

Bộ test bảo mật đỏ là **đúng** ở trạng thái gốc. Nó chính là tiêu chí nghiệm thu
độc lập mà agent phải làm cho xanh.

### 2. Đẩy lên GitHub

```bash
git remote add origin https://github.com/<tài-khoản>/labbank-demo.git
git push -u origin main
```

Lần push này kích hoạt cả hai workflow. Cần biết trước để không bị bất ngờ:

* **DevSecOps Pipeline** chạy hết sáu job và đẩy kết quả lên tab Security. Đây
  là thứ bạn sẽ chiếu ở phút thứ 3.
* **Deploy** sẽ **thất bại có chủ đích** ở job `staging-verify`. Nó tự tấn công
  ứng dụng và đòi nhận về HTTP 401, nhưng mã còn lỗ hổng nên nhận về 200. Cổng
  chặn đã làm đúng việc của nó: **không cho mã dính lỗ hổng đi ra production.**
  Dấu X đỏ đó là một slide miễn phí, đừng giấu nó.

### 3. Render (gói Free, không cần thẻ)

1. New → Blueprint → trỏ vào repo. Render đọc `render.yaml` và tạo đúng **một**
   service `labbank-demo`.
2. Đặt hai biến môi trường (Environment → Add):
   * `FLASK_SECRET_KEY` — chuỗi ngẫu nhiên bất kỳ
   * `ADMIN_API_KEY` — chuỗi bất kỳ, chỉ để bản vá có cái mà đọc
3. Vì `autoDeploy: false`, deploy đầu tiên phải bấm tay: **Manual Deploy →
   Deploy latest commit**. Đúng như mong muốn — bản dính lỗ hổng lên được là do
   bạn bấm, còn bản vá thì phải đi qua cổng phê duyệt.
4. Settings → Deploy Hook → copy URL.

### 4. Nối GitHub với Render

Trong repo, Settings →

* **Secrets and variables → Actions → Secrets**: thêm `RENDER_DEPLOY_HOOK`
  (dán URL vừa copy).
* **Secrets and variables → Actions → Variables**: thêm `PUBLIC_APP_URL`
  (ví dụ `https://labbank-demo.onrender.com`, không có dấu `/` cuối).
* **Environments → New environment → `production`** → bật **Required
  reviewers** và chọn chính bạn.

Bước cuối là cổng phê duyệt. Không có nó, khoảnh khắc "con người bấm Approve"
giữa buổi demo sẽ không tồn tại.

---

## Trước mỗi buổi

```bash
# T-60  đưa kho mã về trạng thái dính lỗ hổng và tự kiểm chứng
python scripts/reset_demo.py

# T-45  lấy số liệu quét thật (tuỳ chọn nhưng nên có)
gh run download <run-id> --dir findings
#      không có gh: tải artifact sarif-* từ tab Actions rồi giải nén vào findings/

# T-30  sinh mã QR và mở trang chiếu
python scripts/make_qr.py https://labbank-demo.onrender.com
start artifacts\qr_slide.html

# T-30  mở một terminal RIÊNG, để chạy suốt buổi
python scripts/keepalive.py https://labbank-demo.onrender.com

# T-15  chạy thử trọn vẹn một lượt rồi reset lại
python agent/run_agent.py --speed 0 --no-pause
python scripts/reset_demo.py
```

`reset_demo.py` không chỉ khôi phục tệp — nó chạy lại payload và **thoát với mã
lỗi 1** nếu ứng dụng vẫn đang ở trạng thái đã vá. Nếu nó in ra chữ CẢNH BÁO, đừng
lên bục cho tới khi sửa xong.

`keepalive.py` tồn tại vì gói Free của Render cho service ngủ sau ~15 phút không
có request, và lần đánh thức sau đó mất khoảng 50 giây. Năm mươi giây im lặng
đúng lúc ba mươi người vừa quét QR là quãng chết dài nhất bạn có thể gặp.

### Danh sách kiểm tra cuối, T-5

- [ ] Tự quét mã QR bằng điện thoại **của mình**, bấm nút, thấy hoạt ảnh chiếm quyền
- [ ] `curl https://.../version` báo `"patched": false`
- [ ] Terminal keepalive đang chạy, ping gần nhất dưới 1 giây
- [ ] Terminal agent đang ở thư mục kho mã, phông chữ đã phóng to
- [ ] Tab trình duyệt đã mở sẵn: tab Security của repo, tab Actions, trang Render
- [ ] Video dự phòng của một lượt chạy sạch nằm sẵn trên màn hình desktop

---

## Kịch bản 20 phút

Con số bên trái là mốc tính từ lúc bắt đầu. Ba mốc in đậm là phần không được cắt;
nếu tụt giờ thì rút ngắn ở những chỗ còn lại.

| Mốc | Nội dung | Việc bạn làm |
|---|---|---|
| 0:00 | Mã QR đã chiếu sẵn từ trước khi bạn nói câu đầu tiên | Để khán giả quét và bấm nút đỏ |
| **1:00** | **Cả phòng chiếm được quyền admin cùng lúc** | Chờ tiếng cười lắng xuống rồi mới nói tiếp |
| 2:00 | Đây là lỗ hổng gì, nằm ở dòng nào | Mở `app/auth.py`, chỉ vào chỗ nối chuỗi |
| 3:00 | Pipeline đã bắt được nó từ trước | Chiếu tab Security, 41 cảnh báo từ 6 công cụ |
| 4:00 | Nhưng 41 cảnh báo thì xử lý cái nào trước | Nêu vấn đề alert fatigue, rồi khởi động agent |
| 5:00 | Chặng 1–2 — nạp và phân loại còn 18 | Đọc to vài lý do loại bỏ, đây là phần AI thật sự có giá trị |
| 7:00 | Chặng 3 — vá trên năm tầng | Dừng ở bản vá SQLi: một hàm, ba nơi gọi |
| **10:00** | **Chặng 4 — test ĐỎ** | Đừng vội nói gì. Để khán giả kịp thấy màu đỏ |
| **11:00** | **Agent đọc traceback và tự sửa, test XANH** | Nói rõ: bản vá bảo mật vừa làm hỏng thứ khác, và nó tự nhận ra |
| 13:00 | Chặng 5 — Pull Request, agent dừng lại | Nhấn: agent không tự merge |
| 14:00 | Đẩy lên GitHub, pipeline chạy | `git push` |
| 16:00 | Cổng phê duyệt | Bấm **Approve** trước mặt khán giả |
| 18:00 | Render dựng lại, `/version` đổi trạng thái | Chiếu terminal keepalive — trạng thái đổi ngay trên màn hình |
| **19:00** | **"Bấm lại đúng cái nút lúc nãy"** | Cùng payload, cùng địa chỉ, lần này 401 và pháo giấy |
| 20:00 | Con số MTTR | Chốt bằng bảng dashboard |

Nếu được nới lên 25 phút, hãy dùng năm phút thừa ở mốc 5:00 và 10:00 — đó là hai
chỗ nội dung dày nhất và cũng là hai chỗ khán giả hỏi nhiều nhất.

### Nhịp độ

Mặc định agent **dừng lại giữa mỗi chặng và chờ bạn bấm Enter**. Nhịp nằm trong
tay bạn, không nằm trong tay cái máy.

```bash
python agent/run_agent.py                    # có checkpoint, tốc độ trình bày
python agent/run_agent.py --speed 0.5        # nhanh gấp đôi
python agent/run_agent.py --no-pause         # chạy liền, dùng khi quay video
python agent/run_agent.py --app-url https://labbank-demo.onrender.com
```

Có `--app-url` thì Chặng 6 sẽ theo dõi địa chỉ công khai và chỉ dừng đồng hồ MTTR
khi bản vá thật sự xuất hiện ở đó.

---

## Khi có sự cố

| Hiện tượng | Nguyên nhân thường gặp | Xử lý tại chỗ |
|---|---|---|
| Trang web quay vòng ~50 giây | Service Render đã ngủ | Đã chạy keepalive chưa? Nói "đang đánh thức máy chủ" và chuyển sang slide kiến trúc |
| Agent in cảnh báo vàng "dùng bản kiểm kê dự phòng" | `findings/` rỗng | Cứ chạy tiếp, nhưng **nói rõ** đây là số kiểm kê sẵn |
| Chặng 4 xanh ngay lần đầu | Kho mã chưa reset | Ctrl+C, chạy `reset_demo.py`, chạy lại |
| Job Deploy đỏ ở `staging-verify` | Đang push mã còn lỗ hổng | Đúng như thiết kế — cổng chặn đang làm việc |
| Nút Approve không hiện | Chưa bật Required reviewers | Không sửa kịp trên bục; deploy tay trên Render và giải thích cổng phê duyệt bằng lời |
| Terminal hiện ô vuông thay vì tiếng Việt | Console dùng cp1252 | Đã xử lý sẵn trong `agent/console.py`; nếu vẫn lỗi, chạy `chcp 65001` |
| Khán giả bấm nút cuối buổi nhưng không có pháo giấy | Bản vá chưa lên tới production | Kiểm tra `/version`; đừng nói "chắc do mạng" |

Quy tắc chung: nếu một bước hỏng, **nói ra rằng nó hỏng**. Một buổi seminar về
DevSecOps mà người trình bày giấu lỗi thì tự mâu thuẫn với chính nội dung đang
trình bày.

---

## Sau buổi demo

1. **Xoá service trên Render.** Đây là một ứng dụng cố ý dính SQL Injection nằm
   trên internet công khai. Nó chỉ nên tồn tại đúng khung giờ seminar.
2. Kiểm tra lại điều khoản dịch vụ của nền tảng — một số nơi cấm host ứng dụng
   cố ý dính lỗ hổng.
3. `python scripts/reset_demo.py` để kho mã về trạng thái gốc cho lần sau.
4. Nếu định để repo ở chế độ public lâu dài, thêm ghi chú rõ ràng ở đầu README
   rằng đây là mã dạy học, không phải mã tham khảo để chép.

Mọi trang đều đã mang thẻ meta `noindex, nofollow` (đặt trong
`app/templates/base.html`); đừng gỡ nó đi.

---

## Bản đồ mã nguồn

```
app/                    Flask, sáu lỗ hổng cố ý, giao diện khán giả dùng
  main.py               route, /version tự kiểm chứng
  auth.py               chỗ SQL Injection — một hàm, ba nơi gọi
  templates/            index (nút tấn công) · hacked · blocked
  static/effects.js     gõ payload vào ô nhập, đổi màu banner, pháo giấy
tests/
  test_functional.py    phải xanh mọi lúc; hai bài cuối là bẫy của Chặng 4
  test_security.py      đỏ cho tới khi được vá — tiêu chí nghiệm thu độc lập
agent/
  run_agent.py          điều phối sáu chặng
  findings.py           chuẩn hoá SARIF của sáu công cụ về một schema
  triage.py             41 → 18, kèm lý do viết ra cho từng quyết định
  patches.py            năm bản vá + bản vá sửa lại ở Chặng 4
  verify.py             pytest tiến trình con, chạy lại payload, quét secret
  dashboard.py          bảng MTTR tự làm mới
scripts/
  reset_demo.py         khôi phục và TỰ KIỂM CHỨNG là đã dính lỗ hổng trở lại
  scan_local.py         quét trên máy, xuất SARIF thật vào findings/
  make_qr.py            sinh mã QR duy nhất + trang chiếu toàn màn hình
  keepalive.py          giữ service Render không ngủ
.github/workflows/
  ci.yml                sáu job quét, đẩy SARIF lên tab Security
  deploy.yml            staging tự tấn công trong runner → cổng phê duyệt → Render
```

`agent/patched/*.txt` là nội dung đích của từng tệp sau khi vá. `patches.py` đọc
chúng, tính diff so với tệp hiện tại rồi ghi đè — nhờ vậy diff chiếu lên màn
hình là diff thật, không phải chuỗi in sẵn.
