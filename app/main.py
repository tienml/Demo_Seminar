"""LabBank — ứng dụng web demo cho seminar AI-Augmented DevSecOps.

Ứng dụng được cố ý cài lỗ hổng để minh hoạ pipeline DevSecOps. Toàn bộ dữ liệu
là seed giả. Không triển khai ra internet ngoài khung giờ seminar.

Trạng thái "đã vá hay chưa" KHÔNG phải một cờ cấu hình: endpoint /version tự
chạy lại payload tấn công lên chính hàm xác thực của ứng dụng rồi báo cáo kết
quả. Nhờ vậy màn hình khán giả nhìn thấy luôn phản ánh sự thật của mã nguồn.
"""

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from . import __version__, config, db, transfer
from .auth import SQLI_PAYLOAD, admin_search, authenticate, injection_succeeds


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = config.SECRET_KEY
    app.config["APP_NAME"] = config.APP_NAME

    db.init_db()
    transfer.init_transfer_tables()
    app.register_blueprint(transfer.bp)

    # ------------------------------------------------------------------
    # LỖ HỔNG CỐ Ý #6 — thiếu security headers.
    # Cờ này mặc định tắt; bản vá của agent sẽ bật lên.
    # ------------------------------------------------------------------
    @app.after_request
    def apply_security_headers(response):
        if getattr(config, "ENABLE_SECURITY_HEADERS", False):
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; style-src 'self' 'unsafe-inline'; "
                "script-src 'self'"
            )
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response

    # ------------------------------------------------------------------
    # Trang chủ — sân khấu chính cho khán giả quét QR
    # ------------------------------------------------------------------
    @app.get("/")
    def index():
        return render_template(
            "index.html",
            payload=SQLI_PAYLOAD,
            app_name=config.APP_NAME,
        )

    @app.post("/login")
    def login():
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        looks_like_attack = "'" in username or "--" in username

        user = authenticate(username, password)

        if user and user.get("role") == "admin" and looks_like_attack:
            # Tấn công thành công: ứng dụng vẫn còn lỗ hổng.
            session["user_id"] = user["id"]
            session["role"] = user["role"]
            return render_template(
                "hacked.html",
                user=user,
                users=db.list_users(),
                payload=username,
                app_name=config.APP_NAME,
            )

        if user:
            session["user_id"] = user["id"]
            session["role"] = user.get("role", "user")
            return redirect(url_for("dashboard"))

        # Đăng nhập thất bại. Nếu đó là một payload tấn công thì đây chính là
        # khoảnh khắc Chặng 6: bản vá đã chặn được.
        return (
            render_template(
                "blocked.html",
                payload=username,
                was_attack=looks_like_attack,
                app_name=config.APP_NAME,
            ),
            401,
        )

    @app.get("/dashboard")
    def dashboard():
        uid = session.get("user_id")
        if not uid:
            return redirect(url_for("index"))
        return render_template(
            "dashboard.html", user=db.get_user_by_id(uid), app_name=config.APP_NAME
        )

    @app.get("/logout")
    def logout():
        session.clear()
        return redirect(url_for("index"))

    # ------------------------------------------------------------------
    # LỖ HỔNG CỐ Ý #6b — IDOR: không kiểm tra quyền sở hữu bản ghi.
    # ------------------------------------------------------------------
    @app.get("/api/user/<int:user_id>/profile")
    def user_profile(user_id: int):
        user = db.get_user_by_id(user_id)
        if not user:
            return jsonify({"error": "not found"}), 404
        return jsonify(user)

    @app.get("/api/admin/search")
    def api_admin_search():
        keyword = request.args.get("q", "")
        return jsonify({"results": admin_search(keyword)})

    # ------------------------------------------------------------------
    # Endpoint phục vụ pipeline và dashboard MTTR
    # ------------------------------------------------------------------
    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok", "version": __version__})

    @app.get("/version")
    def version():
        """Tự kiểm chứng trạng thái bảo mật bằng cách chạy lại payload tấn công."""
        vulnerable = injection_succeeds()
        return jsonify(
            {
                "app": config.APP_NAME,
                "version": __version__,
                "sqli_exploitable": vulnerable,
                "patched": not vulnerable,
                "security_headers": bool(
                    getattr(config, "ENABLE_SECURITY_HEADERS", False)
                ),
                "checked_payload": SQLI_PAYLOAD,
            }
        )

    return app


app = create_app()


if __name__ == "__main__":
    import os

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
