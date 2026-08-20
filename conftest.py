"""Đưa thư mục gốc dự án vào sys.path để `import app` chạy được từ mọi nơi."""

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
