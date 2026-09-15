# fetcher.py — گرفتن خودکار بازی‌ها + ضرایب امروز (The Odds API)
# سهمیه: پلن رایگان ۵۰۰ درخواست/ماه → لیگ‌های هسته هر روز + لیگ‌های اضافی یک روز در میان

import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

TZ = ZoneInfo("Asia/Tehran")
BASE = "https://api.the-odds-api.com/v4/sports/{key}/odds/"

CORE = {
    "soccer_epl": "England Premier League",
    "soccer_spain_la_liga": "Spain La Liga",
    "soccer_italy_serie_a": "Italy Serie A",
    "soccer_germany_bundesliga": "Germany Bundesliga",
    "soccer_france_ligue_one": "France Ligue 1",
    "soccer_netherlands_eredivisie": "Netherlands Eredivisie",
    "soccer_portugal_primeira_liga": "Portugal Primeira Liga",
    "soccer_turkey_super_lig": "Turkey Süper Lig",
    "soccer_scotland_premiership": "Scotland Premiership",
    "soccer_uefa_champs_league": "UEFA Champions League",
    "soccer_uefa_europa_league": "UEFA Europa League",
    "soccer_uefa_europa_conference_league": "UEFA Conference League",
}

EXTRA = {
    "soccer_belgium_first_div": "Belgium Pro League",
    "soccer_sweden_allsvenskan": "Sweden Allsvenskan",
    "soccer_norway_eliteserien": "Norway Eliteserien",
    "soccer_denmark_superliga": "Denmark Superliga",
    "soccer_poland_ekstraklasa": "Poland Ekstraklasa",
}

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


def fetch_day():
    """برمی‌گرداند: (matches, info)"""
    api = os.getenv("ODDS_API_KEY", "")
    if not api:
        return [], {"error": "ODDS_API_KEY تنظیم نشده"}

    leagues = dict(CORE)
    if datetime.now(TZ).day % 2 == 0:
        leagues.update(EXTRA)

    matches = []
    info = {"leagues_ok": 0, "leagues_err": [], "used": None, "remaining": None,
            "extra_today": len(leagues) > len(CORE)}
    row = 0
    for key, league in leagues.items():
        try:
            r = requests.get(
                BASE.format(key=key),
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
