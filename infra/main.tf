# LỖ HỔNG CỐ Ý #5 — hạ tầng dưới dạng mã bị cấu hình sai.
#   - Security Group mở cổng SSH và toàn dải cổng ra 0.0.0.0/0
#   - S3 bucket không bật mã hoá, không chặn public access
#   - log truy cập bị tắt
# Checkov sẽ bắt các điểm này ở stage `iac` của pipeline.
#
# Đây là mã minh hoạ, KHÔNG apply lên bất kỳ tài khoản cloud nào trong demo.

terraform {
  required_version = ">= 1.5.0"
}

provider "aws" {
  region = "ap-southeast-1"
}

resource "aws_security_group" "labbank_web" {
  name        = "labbank-web-sg"
  description = "Security group cho web tier cua LabBank"

  ingress {
    description = "SSH mo cho toan bo internet"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Mo toan bo dai cong"
    from_port   = 0
    to_port     = 65535
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_s3_bucket" "labbank_statements" {
  bucket = "labbank-customer-statements-demo"
}

resource "aws_s3_bucket_public_access_block" "labbank_statements" {
  bucket                  = aws_s3_bucket.labbank_statements.id
  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}
