# findings/

Thư mục này là nơi agent tìm kết quả quét **thật** ở định dạng SARIF.

`agent/run_agent.py` đọc theo thứ tự ưu tiên:

1. Mọi tệp `*.sarif` trong thư mục này.
2. Nếu không có tệp nào → lùi về `agent/baseline.json` và **in cảnh báo vàng**
   lên terminal.

Cảnh báo đó là cố ý. Nếu nó xuất hiện giữa buổi demo, hãy nói thẳng với khán giả
rằng con số đang chiếu là số kiểm kê sẵn chứ không phải số vừa quét — mất vài
giây thừa nhận còn hơn để ai đó phát hiện ra sau.

## Lấy SARIF thật, cách 1 — từ pipeline (khuyến nghị)

Pipeline `.github/workflows/ci.yml` upload SARIF của cả sáu công cụ dưới dạng
artifact. Sau khi một lần chạy kết thúc:

```bash
gh run list --limit 5
gh run download <run-id> --dir findings
```

Không có `gh` trên máy cũng không sao: vào tab **Actions** trên GitHub, mở lần
chạy đó, kéo xuống mục **Artifacts** và tải các gói `sarif-*` về, giải nén vào
đúng thư mục này. Đây là cách duy nhất lấy được đủ cả sáu công cụ mà không phải
cài gì lên máy.

## Lấy SARIF thật, cách 2 — quét ngay trên máy

```bash
python scripts/scan_local.py
```

Script tự dò từng công cụ trên PATH, thiếu thì thử chạy qua Docker, thiếu cả hai
thì bỏ qua và nói rõ. Tệp sinh ra có đuôi `.local.sarif` nên nằm ngoài Git.

Lưu ý về Windows: `semgrep` không chạy trực tiếp trên Windows (cần WSL hoặc
Docker), còn `checkov` thì cài được thẳng bằng `pip install checkov`.

## Trước khi lên bục

Chạy thử `python agent/run_agent.py --speed 0 --no-pause` và nhìn dòng đầu của
Chặng 1. Nếu nó nói `đọc N tệp SARIF trong findings/` thì số liệu là thật. Nếu
nó nói `đang dùng bản kiểm kê dự phòng` thì thư mục này đang rỗng.
