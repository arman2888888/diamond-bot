# parser.py — خواندن لیست روزانه از هر دری: CSV / تب / اکسل / متن فاصله‌ای / خط لوله‌ای

import csv
import io

FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
AR_DIGITS = "٠١٣٤٥٧٨٩"

# فرهنگ لیگ‌ها برای حالت فاصله‌ای (تماماً کوچک)
LEAGUE_GAZ = [
    "afc champions league elite", "uefa europa conference league", "uefa champions league",
    "uefa europa league", "england premier league", "england championship",
    "england isthmian league", "spain la liga", "italy serie a", "italy serie b",
    "germany bundesliga", "france ligue 1", "france ligue 2", "netherlands eredivisie",
    "netherlands eerste divisie", "portugal primeira liga", "turkey superliga",
    "turkey süper lig", "scotland premiership", "belgium pro league",
    "sweden allsvenskan", "norway eliteserien", "denmark superliga",
    "poland ekstraklasa", "switzerland super league", "greece super league",
    "georgia erovnuli liga", "ukraine premier league", "russia premier league",
    "russian championship league 1", "israel premier league", "romania liga 1",
    "azerbaijan premier league", "serbia superliga", "bulgaria first league",
    "cyprus first division", "egypt premier league", "saudi pro league",
    "ireland premier league", "uruguay primera division", "argentina primera division",
    "brazil serie a", "brazil serie b", "chile primera division", "ecuador serie a",
    "colombia primera a", "mexico liga mx", "usa mls", "china super league",
    "japan j league", "korea k league 1", "australia a-league",
    "south africa premiership", "morocco botola pro",
]

JUNK_HINTS = ["ii"]


def to_en_digits(s: str) -> str:
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
    for name in colnames:
        low = (name or "").strip().lower()
        for k in keys:
            if k in low:
                return name
    return None


def parse_csv_text(text: str):
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
        is_live = ("لایو" in raw_line) or ("پیش" in raw_line) or ("live" in raw_line.lower())
        matches.append({
            "row": g(c_row) or str(i),
            "date": g(c_date),
            "time": g(c_time),
            "league": g(c_league),
            "home": home,
            "away": away,
            "w1": w1, "x": x, "w2": w2,
            "live": is_live,
        })
    return matches


def _rows_to_csv(rows):
    out = io.StringIO()
    w = csv.writer(out)
    for r in rows:
        w.writerow(r)
    return out.getvalue()


def _match_league(mid):
    """بلندترین پیشوند mid را که لیگ شناخته‌شده است برمی‌گرداند: (نام، تعداد توکن)"""
    for n in range(min(5, len(mid)), 0, -1):
        cand = " ".join(mid[:n]).lower()
        if cand in LEAGUE_GAZ:
            return " ".join(mid[:n]), n
    return None, 0


def _parse_pipe_lines(lines):
    matches = []
    for i, ln in enumerate(lines, start=1):
        parts = [p.strip() for p in ln.split("|")]
        if len(parts) == 6:
            league, home, away, w1, x, w2 = parts
            row = str(i)
        elif len(parts) == 7:
            row, league, home, away, w1, x, w2 = parts
        else:
            continue
        try:
            w1, x, w2 = float(w1), float(x), float(w2)
        except ValueError:
            continue
        matches.append({
            "row": row, "date": "", "time": "", "league": league,
            "home": home, "away": away, "w1": w1, "x": x, "w2": w2, "live": False,
        })
    return matches


def _parse_space_lines(lines):
    matches = []
    row = 0
    for ln in lines:
        toks = ln.split()
        if len(toks) < 7:
            continue
        try:
            w1, x, w2 = float(toks[-3]), float(toks[-2]), float(toks[-1])
        except ValueError:
            continue
        head = toks[:3]
        mid = toks[3:-3]
        if len(mid) < 3:
            continue
        league, n = _match_league(mid)
        teams = mid[n:] if league else mid
        if len(teams) < 2:
            continue
        h_n = (len(teams) + 1) // 2
        home = " ".join(teams[:h_n])
        away = " ".join(teams[h_n:])
        row += 1
        matches.append({
            "row": str(row),
            "date": head[1],
            "time": head[2],
            "league": league or "Unknown League",
            "home": home,
            "away": away,
            "w1": w1, "x": x, "w2": w2,
            "live": False,
        })
    return matches


def parse_any_text(text: str):
    """هر متنی را می‌گیرد و لیست بازی‌ها را برمی‌گرداند (کاما/تب/فاصله/لوله)"""
    if text.startswith("\ufeff"):
        text = text[1:]
    text = to_en_digits(text)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []

    start = 0
    first = lines[0]
    if ("میزبان" in first) or ("home" in first.lower() and "away" in first.lower()):
        start = 1
    body = lines[start:]
    if not body:
        return []

    if "|" in body[0]:
        return _parse_pipe_lines(body)
    if "," in body[0]:
        return parse_csv_text("\n".join([lines[0]] + body) if start else "\n".join(body))
    if "\t" in body[0]:
        rows = [ln.split("\t") for ln in body]
        header = lines[0].split("\t") if start else ["ردیف", "تاریخ", "ساعت", "لیگ", "میزبان", "مهمان", "W1", "X", "W2"]
        return parse_csv_text(_rows_to_csv([header] + rows))
    return _parse_space_lines(body)


def matches_from_excel(data: bytes):
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    ws = wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []

    header = None
    hidx = 0
    for i, r in enumerate(rows[:10]):
        cells = [str(c if c is not None else "").strip() for c in r]
        joined = ",".join(cells).lower()
        if ("میزبان" in joined) or ("home" in joined) or ("w1" in joined):
            header = cells
            hidx = i
            break
    if header is None:
        return []

    out = []
    for r in rows[hidx + 1:]:
        cells = [str(c if c is not None else "").strip() for c in r]
        if not any(cells):
            continue
        out.append(cells)
    return parse_csv_text(_rows_to_csv([header] + out))
