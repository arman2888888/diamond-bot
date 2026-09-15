# filters.py — فیلترهای ابدی الماس v10.0

WHITELIST = [
    "premier league", "la liga", "laliga", "serie a", "bundesliga",
    "ligue 1", "eredivisie", "primeira liga", "super lig", "süper lig",
    "premiership", "pro league", "allsvenskan", "eliteserien",
    "superliga", "ekstraklasa", "champions league", "europa league",
    "conference league",
]

BLACKLIST = [
    "russia", "saudi", "argentina", "brazil", "colombia", "chile",
    "bolivia", "albania", "korea", "japan", "belarus", "china",
    "india", "venezuela", "uae", "jordan", "bahrain", "qatar",
    "algeria", "paraguay", "mls", "usa", "armenia", "cyprus",
    "bulgaria", "kazakhstan", "baltic", "egypt", "africa", "afc",
    "caf", "georgia", "azerbaijan", "israel", "romania", "serbia",
    "hungary", "ireland", "ukraine",
]

TIER2 = [
    "2. bundesliga", "segunda", "serie b", "ligue 2", "eerste",
    "superettan", "championship", "league 1", "league 2", "national",
    "reserve", "u19", "u21", "u23", " ii", "division 2", "divizia 2",
    "category 2", "category 3",
]

CUPS = [
    "cup", "copa", "coupe", "pokal", "super cup", "playoff",
    "play-off", "qualification", "friendly", "internationals",
    "world cup", "euro 2", "nations league b",
]

MIN_ODD = 1.50
MAX_MARGIN = 6.0


def margin(w1: float, x: float, w2: float) -> float:
    """مارجین بوکمیکن بر حسب درصد"""
    return (1.0 / w1 + 1.0 / x + 1.0 / w2 - 1.0) * 100.0


def margin_ok(w1: float, x: float, w2: float) -> bool:
    return margin(w1, x, w2) <= MAX_MARGIN


def odd_ok(odd: float) -> bool:
    return odd >= MIN_ODD


def league_block_reason(league: str):
    """اگر لیگ ممنوع است، دلیل را برمی‌گرداند؛ وگرنه None"""
    lg = f" {league.lower()} "
    for kw in BLACKLIST:
        if kw in lg:
            return f"لیگ سیاه: {kw}"
    for kw in TIER2:
        if kw in lg:
            return f"دسته پایین/ذخیره: {kw}"
    for kw in CUPS:
        if kw in lg:
            return f"جام حذفی/چرخشی: {kw}"
    return None


def is_whitelisted(league: str) -> bool:
    lg = league.lower()
    return any(w in lg for w in WHITELIST)
