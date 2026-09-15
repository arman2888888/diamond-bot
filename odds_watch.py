# odds_watch.py — دیدبان حرکت ضریب (بخش ۹ سند)
# قانون: حرکت >۱۰٪ خلاف ما = لغو بدون تعارف

CANCEL_THRESHOLD = 10.0


def record(watch: dict, key, side: str, odds: float, ts: float):
    """لحظهٔ اسکن، ضریب پایه را ثبت می‌کند"""
    watch[key] = {
        "side": side,
        "odds_at_scan": odds,
        "last_odds": odds,
        "last_ts": ts,
        "history": [(ts, odds)],
    }


def check(watch: dict, key, current_odds: float, ts: float):
    """مقایسهٔ ضریب الان با ضریب لحظهٔ اسکن
    برمی‌گرداند: (status, percent, message)"""
    rec = watch.get(key)
    if not rec:
        return "UNKNOWN", 0.0, "ثبت لحظهٔ اسکن وجود ندارد"
    base = rec["odds_at_scan"]
    if base <= 0:
        return "UNKNOWN", 0.0, "ضریب پایه نامعتبر است"

    pct = (current_odds - base) / base * 100.0
    rec["last_odds"] = current_odds
    rec["last_ts"] = ts
    rec["history"].append((ts, current_odds))

    if pct >= CANCEL_THRESHOLD:
        return "CANCEL", pct, f"ضریب {pct:.1f}٪ بالا رفته = خلاف ما = لغو"
    if pct <= -CANCEL_THRESHOLD:
        return "VALUE_GONE", pct, f"ضریب {abs(pct):.1f}٪ ریخته = ارزش رفته = بازبررسی"
    return "OK", pct, f"حرکت ضریب {pct:+.1f}٪ = در محدودهٔ مجاز"


def summary(watch: dict) -> str:
    if not watch:
        return "📡 دیدبان ضریب: هیچ ثبت فعالی نیست"
    lines = ["📡 دیدبان ضریب:"]
    for key, rec in watch.items():
        lines.append(
            f"• {key[0]} - {key[1]} | {rec['side']} | "
            f"اسکن: {rec['odds_at_scan']} | الان: {rec['last_odds']}"
        )
    return "\n".join(lines)
