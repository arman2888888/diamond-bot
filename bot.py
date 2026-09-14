import os
from telegram import Update, ReplyKeyboardMarkup, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise SystemExit("BOT_TOKEN تنظیم نیست.")

MENU = [
    ["💎 اسکن روزانه", "📌 برگه شرط"],
    ["📒 دفتر نبردها", "📊 وضعیت"],
    ["📜 قوانین", "🆔 آی‌دی من"],
]
KB = ReplyKeyboardMarkup(MENU, resize_keyboard=True, is_persistent=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "💎 ربات الماس فعال شد.\n"
        "نسخه: 10.0\n\n"
        "از دکمه‌های پایین استفاده کن یا دستور بنویس."
    )
    await update.message.reply_text(text, reply_markup=KB)


async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "⏳ اسکن واقعی هنوز فعال نشده است.\n"
        "تا ورود داده تأییدشده:\n"
        "داده نیست = شرط نیست",
        reply_markup=KB,
    )


async def slip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📌 ماژول برگه شرط در مرحله بعد فعال می‌شود.", reply_markup=KB
    )


async def ledger(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📒 ماژول دفتر نبردها در مرحله بعد فعال می‌شود.", reply_markup=KB
    )


async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "📜 قوانین الماس v10.0\n"
        "• بدون داده تأییدشده = بدون شرط\n"
        "• حداقل امتیاز الماس: 7/12\n"
        "• امتیاز 6 = نقره با نصف استیک\n"
        "• کمتر از 6 = NO BET\n"
        "• ضریب زیر 1.50 ممنوع\n"
        "• مارجین بالای 6٪ ممنوع\n"
        "• لیگ سیاه ممنوع\n"
        "• لایو و پیش‌مسابقه ممنوع\n"
        "• شرط انتقامی ممنوع\n"
        "• ثبت نهایی فقط با کاربر است"
    )
    await update.message.reply_text(text, reply_markup=KB)


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "🟢 وضعیت ربات: آنلاین\n"
        "📅 اسکن خودکار: فعال نشده\n"
        "📊 پایگاه داده: متصل نشده\n"
        "🧠 DeepCheck: فعال نشده\n"
        "⚠️ وضعیت فعلی: داده نیست = شرط نیست"
    )
    await update.message.reply_text(text, reply_markup=KB)


async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    await update.message.reply_text(f"🆔 Chat ID:\n{chat_id}", reply_markup=KB)


HANDLERS = {
    "💎 اسکن روزانه": scan,
    "📌 برگه شرط": slip,
    "📒 دفتر نبردها": ledger,
    "📊 وضعیت": status,
    "📜 قوانین": rules,
    "🆔 آی‌دی من": id_cmd,
}


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    fn = HANDLERS.get(update.message.text)
    if fn:
        await fn(update, context)


async def post_init(application: Application) -> None:
    await application.bot.set_my_commands([
        BotCommand("scan", "اسکن روزانه"),
        BotCommand("slip", "برگه شرط"),
        BotCommand("ledger", "دفتر نبردها"),
        BotCommand("rules", "قوانین الماس"),
        BotCommand("status", "وضعیت"),
        BotCommand("id", "آی‌دی من"),
    ])


def main() -> None:
    print("در حال شروع ربات...")
    app = Application.builder().token(TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("scan", scan))
    app.add_handler(CommandHandler("slip", slip))
    app.add_handler(CommandHandler("ledger", ledger))
    app.add_handler(CommandHandler("rules", rules))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("id", id_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    port = os.getenv("PORT")
    if port:
        host = os.getenv("RENDER_EXTERNAL_HOSTNAME", "")
        print("✅ حالت ابری (webhook) فعال شد.")
        app.run_webhook(
            listen="0.0.0.0",
            port=int(port),
            url_path=TOKEN,
            webhook_url=f"https://{host}/{TOKEN}",
        )
    else:
        print("✅ ربات در حال اجرا است (حالت محلی).")
        app.run_polling()


if __name__ == "__main__":
    main()
