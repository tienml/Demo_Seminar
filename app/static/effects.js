// Hiệu ứng phía khán giả cho demo seminar.
// Trạng thái "còn lỗ hổng / đã vá" lấy từ /version, nơi máy chủ tự chạy lại
// payload tấn công lên chính hàm xác thực — không phải một cờ đặt tay.

(function () {
  "use strict";

  function paintStatus() {
    var banner = document.getElementById("status-banner");
    var text = document.getElementById("status-text");
    if (!banner || !text) return;

    fetch("/version", { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        banner.classList.remove("status-unknown");
        if (data.sqli_exploitable) {
          banner.classList.add("status-vulnerable");
          banner.classList.remove("status-patched");
          text.textContent =
            "HỆ THỐNG ĐANG DÍNH LỖ HỔNG — phiên bản " + data.version;
        } else {
          banner.classList.add("status-patched");
          banner.classList.remove("status-vulnerable");
          text.textContent =
            "LỖ HỔNG ĐÃ ĐƯỢC VÁ — phiên bản " + data.version;
        }
      })
      .catch(function () {
        text.textContent = "Không đọc được trạng thái hệ thống.";
      });
  }

  function wireHackButton() {
    var btn = document.getElementById("hack-btn");
    var form = document.getElementById("login-form");
    if (!btn || !form) return;

    btn.addEventListener("click", function () {
      var payload = window.LABBANK_PAYLOAD || "admin' OR '1'='1--";
      var u = document.getElementById("username");
      var p = document.getElementById("password");

      btn.disabled = true;
      btn.textContent = "Đang gửi payload...";

      typeInto(u, payload, function () {
        p.value = "khong-can-mat-khau";
        setTimeout(function () { form.submit(); }, 320);
      });
    });
  }

  // Gõ từng ký tự để khán giả kịp nhìn thấy payload hình thành.
  function typeInto(input, value, done) {
    input.value = "";
    input.focus();
    var i = 0;
    var timer = setInterval(function () {
      input.value += value.charAt(i);
      i += 1;
      if (i >= value.length) {
        clearInterval(timer);
        done();
      }
    }, 55);
  }

  function confetti() {
    var canvas = document.createElement("canvas");
    canvas.id = "confetti-canvas";
    document.body.appendChild(canvas);

    var ctx = canvas.getContext("2d");
    var w = (canvas.width = window.innerWidth);
    var h = (canvas.height = window.innerHeight);
    var colors = ["#2ee6a8", "#5b8cff", "#ffd166", "#ffffff"];
    var pieces = [];

    for (var i = 0; i < 140; i++) {
      pieces.push({
        x: Math.random() * w,
        y: -20 - Math.random() * h * 0.5,
        r: 3 + Math.random() * 5,
        vy: 1.6 + Math.random() * 2.8,
        vx: -1 + Math.random() * 2,
        rot: Math.random() * Math.PI,
        vr: -0.08 + Math.random() * 0.16,
        color: colors[Math.floor(Math.random() * colors.length)]
      });
    }

    var frames = 0;
    (function draw() {
      ctx.clearRect(0, 0, w, h);
      pieces.forEach(function (p) {
        p.x += p.vx;
        p.y += p.vy;
        p.rot += p.vr;
        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.rotate(p.rot);
        ctx.fillStyle = p.color;
        ctx.fillRect(-p.r, -p.r * 0.5, p.r * 2, p.r);
        ctx.restore();
      });
      frames += 1;
      if (frames < 260) {
        requestAnimationFrame(draw);
      } else {
        canvas.remove();
      }
    })();
  }

  document.addEventListener("DOMContentLoaded", function () {
    paintStatus();
    wireHackButton();

    if (window.LABBANK_EFFECT === "breach" && navigator.vibrate) {
      navigator.vibrate([120, 60, 120]);
    }
    if (window.LABBANK_EFFECT === "patched") {
      confetti();
    }
  });
})();
