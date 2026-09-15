# scoring.py — موتور امتیاز الماس v10.0 (بخش ۴ سند)

MIN_ISSUE = 7          # حداقل امتیاز صدور
ODDS_MIN = 1.80        # بازهٔ ضریب مجاز ما
ODDS_MAX = 4.50
MARGIN_SILVER = 4.0    # آستانهٔ مارجین زیر ۴٪


def diamond_score(
    inj_opp: int = 0,          # تعداد غایبان کلیدی حریف
    sources_inj: int = 0,      # تعداد منابع تأیید مصدومیت
    fatigue_opp: bool = False, # خستگی حریف (بازی قاره‌ای + سفر)
    rest_diff_days: int = 0,   # اختلاف استراحت به نفع ما
    our_odd: float = 0.0,      # ضریب سمت ما
    margin_pct: float = 99.0,  # مارجین بازار
    form_us_up: bool = False,  # فرم صعودی ما (برد پرگل اخیر)
    form_opp_down: bool = False, # فرم نزولی حریف
    league_ok: bool = True,    # لیگ معتبر
    fatigue_us: bool = False,  # پرچم خستگی روی تیم ما
):
    """امتیاز الماس (۰ تا ۱۲) + لیست شاهد‌ها را برمی‌گرداند"""
    score = 0
    reasons = []

    # +۳ بحران مصدومیت حریف (≥۴ کلیدی + تأیید ≥۳ منبع)
    if inj_opp >= 4 and sources_inj >= 3:
        score += 3
        reasons.append(f"+۳ بحران مصدومیت حریف ({inj_opp} غایب کلیدی، {sources_inj} منبع)")

    # +۲ خستگی حریف / اختلاف استراحت ≥۴ روز
    if fatigue_opp or rest_diff_days >= 4:
        score += 2
        reasons.append("+۲ خستگی حریف / اختلاف استراحت به نفع ما")

    # +۲ ضریب ما در بازهٔ ۱.۸۰ تا ۴.۵۰
    if ODDS_MIN <= our_odd <= ODDS_MAX:
        score += 2
        reasons.append(f"+۲ ضریب ما در بازهٔ طلایی ({our_odd})")

    # +۲ مارجین زیر ۴٪
    if margin_pct < MARGIN_SILVER:
        score += 2
        reasons.append(f"+۲ مارجین بازار زیر ۴٪ ({margin_pct:.1f}٪)")

    # +۱ فرم ما صعودی
    if form_us_up:
        score += 1
        reasons.append("+۱ فرم صعودی ما (برد پرگل اخیر)")

    # +۱ فرم حریف نزولی
    if form_opp_down:
        score += 1
        reasons.append("+۱ فرم نزولی حریف")

    # +۱ لیگ معتبر + بدون خستگی روی ما
    if league_ok and not fatigue_us:
        score += 1
        reasons.append("+۱ لیگ معتبر و بدون پرچم خستگی روی ما")

    return score, reasons


def verdict(score: int) -> str:
    """حکم نهایی طبق سند"""
    if score >= MIN_ISSUE:
        return "DIAMOND"
    if score == 6:
        return "SILVER"
    return "NO BET"


def stake_percent(verdict_str: str) -> float:
    """درصد استیک طبق بخش ۹ سند"""
    if verdict_str == "DIAMOND":
        return 3.0
    if verdict_str == "SILVER":
        return 1.5
    return 0.0
