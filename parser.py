# parser.py — خواندن و تمیز کردن CSV لیست روزانه

import csv
import io

FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
AR_DIGITS = "٠١٢٣٤٥٦٧٨٩"


def to_en_digits(s: str) -> str:
    """ارقام فارسی و عربی را به انگلیسی تبدیل می‌کند"""
    out = []
    for ch in s:
        if ch in FA_DIGITS:
            out.append(str(FA_DIGITS.index(ch)))
        elif ch in AR_DIGITS:
            out.append(str(AR_DIGITS.index(ch)))
        else:
            out.append(ch)
    return "".join(out)


def _find(colnames, *keys):
    """اولین ستونی که یکی از کلیدها را دارد برمی‌گرداند"""
    for name in colnames:
        low = (name or "").strip().lower()
        for k in keys:
            if k in low:
                return name
    return None


def parse_csv_text(text: str):
    """متن CSV را می‌گیرد و لیست بازی‌ها را برمی‌گرداند"""
    if text.startswith("\ufeff"):
        text = text[1:]
    text = to_en_digits(text)

    reader = csv.DictReader(io.StringIO(text))
    cols = reader.fieldnames or []

    c_row = _find(cols, "ردیف", "row")
    c_date = _find(cols, "تاریخ", "date")
    c_time = _find(cols, "ساعت", "time")
    c_league = _find(cols, "لیگ", "league")
    c_home = _find(cols, "میزبان", "home")
    c_away = _find(cols, "مهمان", "away")
    c_w1 = _find(cols, "w1")
    c_x = _find(cols, "x", "draw")
    c_w2 = _find(cols, "w2")

    matches = []
    for i, row in enumerate(reader, start=1):
        def g(c):
            return (row.get(c) or "").strip() if c else ""

        home = g(c_home)
        away = g(c_away)
        if not home or not away:
            continue

        try:
            w1 = float(g(c_w1) or "0")
            x = float(g(c_x) or "0")
            w2 = float(g(c_w2) or "0")
        except ValueError:
            continue

        raw_line = ",".join(v or "" for v in row.values())
        is_live = (
            ("لایو" in raw_line)
            or ("پیش" in raw_line)
            or ("live" in raw_line.lower())
        )

        matches.append({
            "row": g(c_row) or str(i),
            "date": g(c_date),
            "time": g(c_time),
            "league": g(c_league),
            "home": home,
            "away": away,
            "w1": w1,
            "x": x,
            "w2": w2,
            "live": is_live,
        })
    return matches
