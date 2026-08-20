# LỖ HỔNG CỐ Ý #4 — cấu hình container không an toàn.
#   - base image ghim phiên bản cũ, nhiều CVE
#   - tiến trình chạy bằng quyền root
#   - copy toàn bộ thư mục làm việc, kéo theo cả file .env nếu có
#   - không có HEALTHCHECK
# Hadolint và Trivy sẽ bắt các điểm này ở stage `container` của pipeline.

FROM python:3.9.7-slim

WORKDIR /srv

COPY . .

RUN pip install -r requirements.txt

ENV PORT=5000
EXPOSE 5000

CMD gunicorn --bind 0.0.0.0:$PORT --workers 2 app.main:app
