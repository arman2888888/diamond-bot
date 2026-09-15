import asyncio
import json
import os
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
import tornado.httpserver
import tornado.ioloop
import tornado.web
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Update, ReplyKeyboardMarkup, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

import filters as FL
import parser as PR
import scoring as SC
import deepcheck as DC
import ledger as LG
import odds_watch as OW


def log(msg):
    print(msg, flush=True)


log("✅ وارد کردن ماژول‌ها تمام شد")

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_CHAT_ID", "")
TZ = ZoneInfo("Asia/Tehran")

LEDGER = LG.load_ledger()
log("✅ دفتر نبردها بارگذاری شد")

SCHED = AsyncIOScheduler(timezone=TZ)
log("✅ زمان‌بند ساخته شد")

STATE = {"csv_text": None, "deep": [], "issues": [], "removed": [], "watch": {}}
BOT = None

MENU = [
    ["💎 اسکن روزانه", "📌 برگه شرط"],
    ["📒 دفتر نبردها", "📊 وضعیت"],
    ["📜 قوانین", "🆔 آی‌دی من"],
]
KB = ReplyKeyboardMarkup(MENU, resize_keyboard=True, is_persistent=True)


# ---------- گزارش‌سازی ----------

def build_report(removed, watch_list, issues):
    lines = ["💎 گزارش اسکن الماس — v10.0", "", "🚫 حذف‌شده‌ها:"]
    if not removed:
        lines.append("• (هیچ)")
    for m, why in removed:
        lines.append(f"• {m['home']} - {m['away']} | {why}")
    lines.append("")
    lines.append("👁 تماشا / بدون شرط:")
    if not watch_list:
        lines.append("• (هیچ)")
    for m, why in watch_list:
        lines.append(f"• {m['home']} - {m['away']} | {why}")
    lines.append("")
    if not issues:
        lines.append("⛔ امروز NO BET — الماس واقعی نیست")
    for i in issues:
        emoji = "💎" if i["verdict"] == "DIAMOND" else "🥈"
        lines.append(
            f"{emoji} {i['verdict']} [{i['score']}/12] | {i['home']} - {i['away']} | "
            f"{i['time']} | {i['label']} | ضریب {i['odds']} | استیک {i['stake']}٪"
        )
        for r in i["reasons"]:
            lines.append(f"    {r}")
    lines.append("")
    lines.append(f"جمع استیک روز: {sum(i['stake'] for i in issues):.1f}٪ از بانک")
    lines.append("پروتکل فروش: دقیقه ۶۰ بررسی | دقیقه ۷۵ اگر جلو = فروش | گل خوردن + فشار = فروش فوری")
    return "\n".join(lines)


def match_dt(m):
    tm = re.search(r"(\d{1,2}):(\d{2})", m.get("time") or "")
    if not tm:
        return None
    now = datetime.now(TZ)
    return now.replace(hour=int(tm.group(1)), minute=int(tm.group(2)), second=0, microsecond=0)


# ---------- موتور اسکن ----------

def run_scan():
    if not STATE["csv_text"]:
        return None
    removed = []
    issues = []
    watch_list = []
    matches = PR.parse_csv_text(STATE["csv_text"])
    deep_by_key = {}
    for d in STATE["deep"]:
        k = DC.match_key(d)
        if k:
            deep_by_key[k] = d

    for m in matches:
        key = (m["home"].lower(), m["away"].lower())
        name = f"{m['home']} - {m['away']}"
        if m["live"]:
            removed.append((m, "لایو/پیش‌مسابقه = ورود ممنوع"))
            continue
        reason = FL.league_block_reason(m["league"])
        if reason:
            removed.append((m, reason))
            continue
        if not (m["w1"] and m["x"] and m["w2"]):
            removed.append((m, "ضرایب ناقص"))
            continue
        mg = FL.margin(m["w1"], m["x"], m["w2"])
        if not FL.margin_ok(m["w1"], m["x"], m["w2"]):
            removed.append((m, f"مارجین بالای ۶٪ ({mg:.1f}٪)"))
            continue
        d = deep_by_key.get(key)
        if not d:
            watch_list.append((m, "داده تأییدشده (DeepCheck) نیست = بدون شرط"))
            continue
        ok, why = DC.validate(d)
        if not ok:
            removed.append((m, why))
            continue
        if d["side"] in ("home", "away"):
            opp_odd = m["w2"] if d["side"] == "home" else m["w1"]
            if d["odds"] > opp_odd and d["inj_opp"] < 6:
                removed.append((m, "Win خالص روی underdog ممنوع؛ فقط X2/DNB"))
                continue
        score, reasons = SC.diamond_score(
            inj_opp=d["inj_opp"],
            sources_inj=d["sources_inj"],
            fatigue_opp=d["fatigue_opp"],
            rest_diff_days=d["rest_diff_days"],
            our_odd=d["odds"],
            margin_pct=mg,
            form_us_up=d["form_us"],
            form_opp_down=d["form_opp_down"],
            league_ok=FL.is_whitelisted(m["league"]),
            fatigue_us=d["fatigue_us"],
        )
        v = SC.verdict(score)
        if v == "NO BET":
            watch_list.append((m, f"امتیاز {score}/12 — زیر آستانهٔ صدور"))
            continue
        OW.record(STATE["watch"], key, d["side"], d["odds"], datetime.now(TZ).timestamp())
        issues.append({
            "home": m["home"], "away": m["away"], "time": m["time"],
            "label": DC.side_label(d["side"]), "odds": d["odds"],
            "stake": SC.stake_percent(v), "score": score,
            "verdict": v, "reasons": reasons,
        })
        dt = match_dt(m)
        if dt:
            SCHED.add_job(job_lineup, "date", run_date=dt - timedelta(hours=1),
                          args=[name], id=f"lineup-{key[0]}", replace_existing=True)
            SCHED.add_job(job_sell60, "date", run_date=dt + timedelta(minutes=60),
                          args=[name], id=f"sell60-{key[0]}", replace_existing=True)
            SCHED.add_job(job_sell75, "date", run_date=dt + timedelta(minutes=75),
                          args=[name], id=f"sell75-{key[0]}", replace_existing=True)

    issues.sort(key=lambda i: -i["score"])
    STATE["removed"] = removed
    STATE["issues"] = issues[:5]
    return build_report(removed, watch_list, STATE["issues"])


# ---------- jobهای زمان‌بندی ----------

async def job_ping():
    host = os.getenv("RENDER_EXTERNAL_HOSTNAME", "")
    if host:
        try:
            requests.get(f"https://{host}/health", timeout=10)
        except Exception:
            pass


async def job_daily_scan():
    rep = run_scan()
    if rep and ADMIN_ID:
        await BOT.send_message(ADMIN_ID, "⏰ اسکن خودکار ساعت ۱۰:۰۰\n\n" + rep)


async def job_lineup(name):
    await BOT.send_message(ADMIN_ID, f"⏰ یک ساعت تا {name}: ترکیب رسمی را چک کن؛ هر پرچم قرمز = لغو بدون تعارف")


async def job_sell60(name):
    await BOT.send_message(ADMIN_ID, f"🔔 دقیقه ۶۰ {name}: بررسی فروش")


async def job_sell75(name):
    await BOT.send_message(ADMIN_ID, f"💰 دقیقه ۷۵ {name}: اگر جلو هستی = فروش قطعی")


# ---------- هندلرها ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "💎 ربات الماس فعال شد.\n"
        "نسخه: 10.0 — مغز کامل\n\n"
        "۱) فایل CSV روز را بفرست (یا متنش را پیست کن)\n"
        "۲) فایل JSON دیپ‌چک را بفرست (یا متنش را پیست کن)\n"
        "۳) دکمهٔ اسکن را بزن"
    )
    await update.message.reply_text(text, reply_markup=KB)


async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    rep = run_scan()
    if rep is None:
        await update.message.reply_text(
            "📂 اول فایل CSV بازی‌های روز را همین‌جا بفرست (یا متنش را پیست کن).",
            reply_markup=KB,
        )
    else:
        await update.message.reply_text(rep, reply_markup=KB)


async def slip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not STATE["issues"]:
        await update.message.reply_text("📌 امروز برگه‌ای صادر نشده. داده نیست = شرط نیست.", reply_markup=KB)
        return
    lines = ["📌 برگه امروز:"]
    for i in STATE["issues"]:
        lines.append(f"• {i['home']} - {i['away']} | {i['label']} | ضریب {i['odds']} | استیک {i['stake']}٪")
    lines.append("")
    lines.append("چک‌لیست ۱ ساعت قبل: ترکیب رسمی | مصدومیت‌ها | حرکت ضریب")
    lines.append("پروتکل فروش: ۶۰ بررسی | ۷۵ اگر جلو = فروش | گل خوردن + فشار = فروش فوری")
    await update.message.reply_text("\n".join(lines), reply_markup=KB)


async def ledger_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(LG.ledger_summary(LEDGER), reply_markup=KB)


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
        "🟢 وضعیت ربات: آنلاین (ابر)\n"
        f"📂 CSV روز: {'دارد' if STATE['csv_text'] else 'ندارد'}\n"
        f"🧠 DeepCheck: {len(STATE['deep'])} رکورد\n"
        f"📡 دیدبان ضریب: {len(STATE['watch'])} ثبت\n"
        f"📒 دفتر: {len(LEDGER['bets'])} ثبت\n"
        "📅 اسکن خودکار: هر روز ۱۰:۰۰ تهران\n"
        "⚠️ وضعیت فعلی: داده نیست = شرط نیست"
    )
    await update.message.reply_text(text, reply_markup=KB)


async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    await update.message.reply_text(f"🆔 Chat ID:\n{chat_id}", reply_markup=KB)


async def record_result_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, res: str):
    if not context.args:
        await update.message.reply_text("مثال: /win 3  یا  /loss 3  (درس اختیاری بعد از عدد)", reply_markup=KB)
        return
    try:
        bid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("شناسه باید عدد باشد. مثال: /win 3", reply_markup=KB)
        return
    lesson = " ".join(context.args[1:])
    if LG.record_result(LEDGER, bid, res, lesson):
        LG.save_ledger(LEDGER)
        await update.message.reply_text(f"📒 ثبت شد: شرط #{bid} = {res}", reply_markup=KB)
    else:
        await update.message.reply_text("شرط با این شناسه پیدا نشد یا قبلاً ثبت شده.", reply_markup=KB)


async def win(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await record_result_cmd(update, context, "W")


async def loss(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await record_result_cmd(update, context, "L")


HANDLERS = {
    "💎 اسکن روزانه": scan,
    "📌 برگه شرط": slip,
    "📒 دفتر نبردها": ledger_cmd,
    "📊 وضعیت": status,
    "📜 قوانین": rules,
    "🆔 آی‌دی من": id_cmd,
}


# ---------- دریافت فایل ----------

async def on_doc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    doc = update.message.document
    f = await doc.get_file()
    data = await f.download_as_bytearray()
    text = bytes(data).decode("utf-8-sig", errors="ignore")
    stripped = text.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            STATE["deep"] = DC.load_deepcheck_text(text)
            await update.message.reply_text(f"🧠 DeepCheck ذخیره شد: {len(STATE['deep'])} رکورد", reply_markup=KB)
        except Exception as e:
            await update.message.reply_text(f"❌ JSON نامعتبر: {e}", reply_markup=KB)
    else:
        STATE["csv_text"] = text
        n = len(PR.parse_csv_text(text))
        await update.message.reply_text(f"📂 CSV روز ذخیره شد: {n} بازی خوانده شد. حالا /scan بزن.", reply_markup=KB)


# ---------- دریافت متن ----------

async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    t = update.message.text or ""
    fn = HANDLERS.get(t)
    if fn:
        await fn(update, context)
        return
    if "میزبان" in t and "," in t:
        STATE["csv_text"] = t
        n = len(PR.parse_csv_text(t))
        await update.message.reply_text(
            f"📂 CSV روز ذخیره شد: {n} بازی خوانده شد. حالا /scan بزن.",
            reply_markup=KB,
        )
        return
    if t.strip().startswith("{") or t.strip().startswith("["):
        try:
            STATE["deep"] = DC.load_deepcheck_text(t)
            await update.message.reply_text(f"🧠 DeepCheck ذخیره شد: {len(STATE['deep'])} رکورد", reply_markup=KB)
        except Exception as e:
            await update.message.reply_text(f"❌ JSON نامعتبر: {e}", reply_markup=KB)


# ---------- راه‌اندازی ----------

async def post_init(application: Application) -> None:
    global BOT
    BOT = application.bot
    if not SCHED.running:
        SCHED.start()
    await application.bot.set_my_commands([
        BotCommand("scan", "اسکن روزانه"),
        BotCommand("slip", "برگه شرط"),
        BotCommand("ledger", "دفتر نبردها"),
        BotCommand("rules", "قوانین الماس"),
        BotCommand("status", "وضعیت"),
        BotCommand("win", "ثبت برد: /win شناسه"),
        BotCommand("loss", "ثبت باخت: /loss شناسه"),
        BotCommand("id", "آی‌دی من"),
    ])


def build_app():
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("scan", scan))
    app.add_handler(CommandHandler("slip", slip))
    app.add_handler(CommandHandler("ledger", ledger_cmd))
    app.add_handler(CommandHandler("rules", rules))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("id", id_cmd))
    app.add_handler(CommandHandler("win", win))
    app.add_handler(CommandHandler("loss", loss))
    app.add_handler(MessageHandler(filters.Document.ALL, on_doc))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    return app


async def boot(app):
    port = int(os.getenv("PORT", "10000"))
    holder = {"app": None}

    class Health(tornado.web.RequestHandler):
        def get(self):
            self.write("OK")

    class Hook(tornado.web.RequestHandler):
        async def post(self):
            if not holder["app"]:
                self.set_status(503)
                self.write("booting")
                return
            try:
                data = json.loads(self.request.body)
                upd = Update.de_json(data, holder["app"].bot)
                await holder["app"].process_update(upd)
            except Exception:
                pass
            self.write("ok")

    web = tornado.web.Application([
        (r"/health", Health),
        (r"/" + TOKEN, Hook),
    ])
    server = tornado.httpserver.HTTPServer(web)
    server.listen(port)
    log(f"✅ پورت باز شد: {port}")

    await post_init(app)
    log("✅ منوها و زمان‌بند آماده شد")

    holder["app"] = app
    host = os.getenv("RENDER_EXTERNAL_HOSTNAME", "")
    await app.bot.set_webhook(url=f"https://{host}/{TOKEN}")
    log("✅ وب‌هوک ست شد — حالت ابری فعال")

    await asyncio.Event().wait()


def main() -> None:
    log("در حال شروع ربات...")
    app = build_app()
    SCHED.add_job(job_ping, "interval", minutes=10)
    SCHED.add_job(job_daily_scan, "cron", hour=10, minute=0)
    if os.getenv("PORT"):
        asyncio.run(boot(app))
    else:
        log("✅ حالت محلی (polling).")
        app.run_polling()


if __name__ == "__main__":
    main()
