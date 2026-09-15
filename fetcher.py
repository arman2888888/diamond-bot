# fetcher.py — گرفتن خودکار بازی‌ها + ضرایب امروز (The Odds API)
# کلید لیگ‌ها به‌صورت پویا از /sports گرفته می‌شود (رایگان، بدون مصرف سهمیه)

import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

TZ = ZoneInfo("Asia/Tehran")
SPORTS_URL = "https://api.the-odds-api.com/v4/sports/"
ODDS_URL = "https://api.the-odds-api.com/v4/sports/{key}/odds/"

# (الگوی عنوان، عنوان ممنوع، هسته؟، نام نمایشی)
LEAGUE_PATTERNS = [
    ("EPL", None, True, "England Premier League"),
    ("La Liga", None, True, "Spain La Liga"),
    ("Serie A", None, True, "Italy Serie A"),
    ("Bundesliga", "Bundesliga 2", True, "Germany Bundesliga"),
    ("Ligue 1", None, True, "France Ligue 1"),
    ("Eredivisie", None, True, "Netherlands Eredivisie"),
    ("Primeira Liga", None, True, "Portugal Primeira Liga"),
    ("Super Lig", None, True, "Turkey Süper Lig"),
    ("Scotland", None, True, "Scotland Premiership"),
    ("Champions League", None, True, "UEFA Champions League"),
    ("Europa League", "Conference", True, "UEFA Europa League"),
    ("Conference League", None, True, "UEFA Conference League"),
    ("Belgium", None, False, "Belgium Pro League"),
    ("Allsvenskan", None, False, "Sweden Allsvenskan"),
    ("Eliteserien", None, False, "Norway Eliteserien"),
    ("Superliga", None, False, "Denmark Superliga"),
    ("Ekstraklasa", None, False, "Poland Ekstraklasa"),
]

PREFERRED_BOOKS = ["pinnacle", "bet365", "betfair", "unibet", "williamhill"]


def _pick_book(bookmakers):
    for pk in PREFERRED_BOOKS:
        for b in bookmakers:
            if b.get("key") == pk:
                return b
    return bookmakers[0] if bookmakers else None


def _odds_of(book, home, away):
    if not book:
        return None
    for m in book.get("markets", []):
        if m.get("key") != "h2h":
            continue
        w1 = x = w2 = None
        for o in m.get("outcomes", []):
            nm = o.get("name")
            pr = o.get("price")
            if nm == home:
                w1 = pr
            elif nm == away:
                w2 = pr
            elif nm == "Draw":
                x = pr
        if w1 and x and w2:
            return float(w1), float(x), float(w2)
    return None


def _in_window(commence_iso):
    try:
        dt = datetime.fromisoformat(commence_iso.replace("Z", "+00:00")).astimezone(TZ)
    except Exception:
        return False, None
    now = datetime.now(TZ)
    today = now.date()
    if dt.date() == today:
        return True, dt
    if dt.date() == today + timedelta(days=1) and dt.hour < 3:
        return True, dt
    return False, dt


def _resolve_leagues(api):
    """لیگ‌های فعال امروز را از /sports رایگان پیدا می‌کند"""
    try:
        r = requests.get(SPORTS_URL, params={"apiKey": api}, timeout=25)
        if r.status_code != 200:
            return [], [f"sports: {r.status_code}"]
        sports = r.json()
    except Exception as e:
        return [], [f"sports: {e!r}"]

    resolved = []
    errs = []
    for pat, exclude, core, name in LEAGUE_PATTERNS:
        found = None
        for s in sports:
            title = f"{s.get('title', '')} {s.get('group', '')}".lower()
            if pat.lower() in title and (exclude is None or exclude.lower() not in title):
                if s.get("active", True):
                    found = s.get("key")
                    break
        if found:
            resolved.append((found, core, name))
        else:
            errs.append(f"{name}: فعال/پیدا نشد")
    return resolved, errs


def fetch_day():
    """برمی‌گرداند: (matches, info)"""
    api = os.getenv("ODDS_API_KEY", "")
    if not api:
        return [], {"error": "ODDS_API_KEY تنظیم نشده"}

    resolved, errs = _resolve_leagues(api)
    if not resolved:
        return [], {"error": "هیچ لیگ فعالی پیدا نشد", "leagues_err": errs}

    leagues = [(k, n) for (k, c, n) in resolved if c]
    if datetime.now(TZ).day % 2 == 0:
        leagues += [(k, n) for (k, c, n) in resolved if not c]

    matches = []
    info = {
        "leagues_ok": 0,
        "leagues_err": errs,
        "used": None,
        "remaining": None,
        "extra_today": any(not c for (k, c, n) in resolved) and datetime.now(TZ).day % 2 == 0,
    }
    row = 0
    for key, league in leagues:
        try:
            r = requests.get(
                ODDS_URL.format(key=key),
                params={
                    "apiKey": api,
                    "regions": "eu",
                    "markets": "h2h",
                    "oddsFormat": "decimal",
                },
                timeout=25,
            )
            if r.status_code != 200:
                info["leagues_err"].append(f"{league}: {r.status_code}")
                continue
            info["leagues_ok"] += 1
            info["used"] = r.headers.get("x-requests-used")
            info["remaining"] = r.headers.get("x-requests-remaining")
            for ev in r.json():
                ok, dt = _in_window(ev.get("commence_time", ""))
                if not ok:
                    continue
                home = ev.get("home_team")
                away = ev.get("away_team")
                odds = _odds_of(_pick_book(ev.get("bookmakers", [])), home, away)
                if not odds:
                    continue
                row += 1
                matches.append({
                    "row": str(row),
                    "date": dt.strftime("%Y-%m-%d"),
                    "time": dt.strftime("%H:%M"),
                    "league": league,
                    "home": home,
                    "away": away,
                    "w1": odds[0],
                    "x": odds[1],
                    "w2": odds[2],
                    "live": False,
                })
        except Exception as e:
            info["leagues_err"].append(f"{league}: {e!r}")
    return matches, info
