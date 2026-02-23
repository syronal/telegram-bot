import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import os
import re
from dataclasses import dataclass
from datetime import datetime

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("BOT_TOKEN")

USER_ROWS = {}  # user_id -> list[Row]

@dataclass
class Row:
    time: str
    date: str
    name: str
    nap: float
    rut: float
    lai: float

def today_str():
    return datetime.now().strftime("%Y-%m-%d")

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def get_rows(user_id: int):
    return USER_ROWS.setdefault(user_id, [])

def fmt_k(x: float) -> str:
    if abs(x - round(x)) < 1e-9:
        return f"{int(round(x))}k"
    return f"{x:.2f}k"

def parse_input(text: str):
    t = (text or "").strip()
    if not t:
        return None

    def to_num(s: str) -> float:
        return float(s.replace(",", ""))

    m_nap = re.search(r"\bnạp\b\s*([0-9]+(?:[.,][0-9]+)?)", t, flags=re.IGNORECASE)
    m_rut = re.search(r"\brút\b\s*([0-9]+(?:[.,][0-9]+)?)", t, flags=re.IGNORECASE)

    nap = to_num(m_nap.group(1)) if m_nap else None
    rut = to_num(m_rut.group(1)) if m_rut else None

    # có đủ nạp+rút
    if nap is not None and rut is not None:
        idx = re.search(r"\bnạp\b", t, flags=re.IGNORECASE).start()
        name = t[:idx].strip() or "không tên"
        return name, nap, rut

    # "100 rút 80" hoặc "78win 100 rút 120"
    if rut is not None and nap is None:
        m_firstnum = re.search(r"([0-9]+(?:[.,][0-9]+)?)", t)
        if not m_firstnum:
            return None
        nap = to_num(m_firstnum.group(1))
        name = t[:m_firstnum.start()].strip() or "không tên"
        return name, nap, rut

    return None

def sum_today(rows, date_str):
    total = 0.0
    count = 0
    for r in rows:
        if r.date == date_str:
            total += r.lai
            count += 1
    return count, total

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ Bot tính lãi theo ngày (bạn nhập số = k)\n\n"
        "Nhập:\n"
        "- 78win nạp 100 rút 120\n"
        "- nạp 100 rút 80\n"
        "- 100 rút 80\n\n"
        "Lệnh:\n"
        "/tongket  - tổng lãi hôm nay\n"
        "/list     - 10 dòng gần nhất hôm nay\n"
        "/undo     - xóa dòng vừa nhập\n"
        "/reset_today - xóa dữ liệu hôm nay\n"
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = update.message.text or ""

    parsed = parse_input(msg)
    if not parsed:
        await update.message.reply_text("Mình chưa hiểu. Ví dụ: 78win nạp 100 rút 120 hoặc 100 rút 80")
        return

    name, nap, rut = parsed
    lai = rut - nap
    date_str = today_str()

    row = Row(time=now_str(), date=date_str, name=name, nap=nap, rut=rut, lai=lai)
    rows = get_rows(user_id)
    rows.append(row)

    if lai > 0:
        line = f"Sếp đã lãi {fmt_k(lai)} ✅"
    elif lai < 0:
        line = f"Sếp âm {fmt_k(abs(lai))} ❌"
    else:
        line = "Sếp hòa 0k 🙂"

    count, total = sum_today(rows, date_str)
    await update.message.reply_text(
        f"{line}\n"
        f"({name}: nạp {fmt_k(nap)} → rút {fmt_k(rut)})\n"
        f"📌 Hôm nay: {count} dòng | Tổng: {fmt_k(total)}"
    )

async def tongket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    rows = get_rows(user_id)
    date_str = today_str()
    count, total = sum_today(rows, date_str)

    if total > 0:
        kq = f"✅ Tổng kết hôm nay: Lãi {fmt_k(total)}"
    elif total < 0:
        kq = f"❌ Tổng kết hôm nay: Âm {fmt_k(abs(total))}"
    else:
        kq = "🙂 Tổng kết hôm nay: Hòa 0k"

    await update.message.reply_text(f"{kq}\nSố dòng hôm nay: {count}")

async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    rows = get_rows(user_id)
    date_str = today_str()

    today_rows = [r for r in rows if r.date == date_str]
    if not today_rows:
        await update.message.reply_text("Hôm nay chưa có dữ liệu.")
        return

    last = today_rows[-10:]
    start_idx = len(today_rows) - len(last) + 1
    lines = []
    for i, r in enumerate(last, start=start_idx):
        sign = "+" if r.lai > 0 else "-" if r.lai < 0 else ""
        val = fmt_k(abs(r.lai)) if r.lai != 0 else "0k"
        lines.append(f"#{i} {r.name}: nạp {fmt_k(r.nap)} rút {fmt_k(r.rut)} => {sign}{val}")

    _, total = sum_today(rows, date_str)
    await update.message.reply_text("📋 10 dòng gần nhất hôm nay:\n" + "\n".join(lines) + f"\n\nTổng hôm nay: {fmt_k(total)}")

async def undo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    rows = get_rows(user_id)
    if not rows:
        await update.message.reply_text("Không có gì để xóa.")
        return
    last = rows.pop()
    date_str = today_str()
    count, total = sum_today(rows, date_str)
    await update.message.reply_text(
        f"↩️ Đã xóa dòng cuối: {last.name} (lãi {fmt_k(last.lai)})\n"
        f"Hôm nay còn: {count} dòng | Tổng: {fmt_k(total)}"
    )

async def reset_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    rows = get_rows(user_id)
    date_str = today_str()
    USER_ROWS[user_id] = [r for r in rows if r.date != date_str]
    await update.message.reply_text("🧹 Đã xóa toàn bộ dữ liệu của hôm nay.")

def main():
    if not BOT_TOKEN:
        raise SystemExit("❌ Thiếu BOT_TOKEN trong Environment Variables của Render.")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tongket", tongket))
    app.add_handler(CommandHandler("list", list_cmd))
    app.add_handler(CommandHandler("undo", undo_cmd))
    app.add_handler(CommandHandler("reset_today", reset_today))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
   def start_port_listener():
    """
    Render Web Service cần có process listen trên $PORT.
    Ta mở 1 HTTP server rất nhẹ để Render detect port.
    """
    port = int(os.environ.get("PORT", "10000"))

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"OK")

        def log_message(self, format, *args):
            return  # tắt log http cho gọn

    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever() main()

