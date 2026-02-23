import os
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# Lấy biến môi trường từ Render
TOKEN = os.environ.get("BOT_TOKEN")
PORT = int(os.environ.get("PORT", 10000))
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    parts = text.split()

    # Format phải là: <ten> <nap> <rut>
    if len(parts) != 3:
        return

    try:
        name = parts[0]
        nap = float(parts[1])
        rut = float(parts[2])
        lai = rut - nap

        emoji = "🟢" if lai >= 0 else "🔴"

        await update.message.reply_text(
            f"{emoji} {name.upper()}\n"
            f"Nạp: {nap}\n"
            f"Rút: {rut}\n"
            f"Lãi: {lai}"
        )
    except:
        pass

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Nhận tất cả tin nhắn thường
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running...")

    # Chạy webhook (ổn định hơn polling trên Render free)
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=WEBHOOK_URL,
    )

if __name__ == "__main__":
    main()
