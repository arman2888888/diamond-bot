# deepcheck.py — خواندن و اعتبارسنجی دادهٔ تأییدشدهٔ روزانه (JSON)
#
# نمونهٔ فرمت فایل روزانه:
# {
#   "match": ["Team A", "Team B"],
#   "side": "away_x2",
#   "odds": 2.10,
#   "inj_opp": 5,
#   "sources_inj": 3,
#   "rest_diff_days": 4,
#   "form_us": true,
#   "form_opp_down": true,
#   "fatigue_opp": true,
#   "fatigue_us": false,
#   "move_ok": true,
#   "BLOCK": ""
# }

VALID_SIDES = ["home", "away", "home_x2", "away_x2", "dnb", "u25"]

SIDE_LABELS = {
    "home": "برد میزبان",
    "away": "برد مهمان",
    "home_x2": "میزبان یا مساوی (1X)",
    "away_x2": "مهمان یا مساوی (X2)",
    "dnb": "بدون مساوی (DNB)",
    "u25": "زیر ۲.۵ گل",
}

MIN_ODD = 1.50


def load_deepcheck_text(text: str):
    """متن JSON را می‌گیرد و لیست رکوردها را برمی‌گرداند"""
    import json
    data = json.loads(text)
    if isinstance(data, dict):
        data = [data]
    return [normalize(item) for item in data]


def normalize(item: dict) -> dict:
    return {
        "match": item.get("match") or [],
        "side": str(item.get("side", "")).lower().strip(),
        "odds": float(item.get("odds", 0) or 0),
        "inj_opp": int(item.get("inj_opp", 0) or 0),
        "sources_inj": int(item.get("sources_inj", 0) or 0),
        "rest_diff_days": int(item.get("rest_diff_days", 0) or 0),
        "form_us": bool(item.get("form_us", False)),
        "form_opp_down": bool(item.get("form_opp_down", False)),
        "fatigue_opp": bool(item.get("fatigue_opp", False)),
        "fatigue_us": bool(item.get("fatigue_us", False)),
        "move_ok": bool(item.get("move_ok", True)),
        "BLOCK": item.get("BLOCK") or "",
    }


def validate(d: dict):
    """بررسی خط قرمزها؛ برمی‌گرداند (ok, reason)"""
    if d["BLOCK"]:
        return False, f"BLOCK: {d['BLOCK']}"
    if len(d["match"]) != 2:
        return False, "فرمت match ناقص است"
    if d["side"] not in VALID_SIDES:
        return False, f"side نامعتبر: {d['side']}"
    if d["odds"] < MIN_ODD:
        return False, "ضریب زیر ۱.۵۰ = بانکر فیک"
    if not d["move_ok"]:
        return False, "حرکت ضریب >۱۰٪ خلاف ما = لغو"
    return True, ""


def side_label(side: str) -> str:
    return SIDE_LABELS.get(side, side)


def match_key(d: dict):
    """کلید جفت‌شدن با بازی‌های CSV"""
    if len(d["match"]) != 2:
        return None
    return (d["match"][0].strip().lower(), d["match"][1].strip().lower())
