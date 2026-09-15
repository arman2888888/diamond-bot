# ledger.py — دفتر نبردها + کارنامهٔ الگوها (بخش ۱۳ سند)
# کارنامهٔ اولیه دقیقاً از سند الماس v10.0 کاشته شده است.

import base64
import json
import os

import requests

GITHUB_REPO = os.getenv("GITHUB_REPO", "arman2888888/diamond-bot")
LEDGER_PATH = "data/ledger.json"
RETIRE_RATE = 55.0   # موفقیت زیر ۵۵٪ = بازنشستگی
MIN_GAMES = 5        # حداقل بازی برای قضاوت


def default_ledger():
    return {
        "bets": [],
        "patterns": {
            "injury_crisis": {"fa": "بحران مصدومیت حریف", "wins": 6, "losses": 2, "active": True},
            "fatigue_trap": {"fa": "تله خستگی / اختلاف استراحت", "wins": 2, "losses": 0, "active": True},
            "fame_trap": {"fa": "تله شهرت", "wins": 5, "losses": 0, "active": True},
            "low_goal": {"fa": "کم‌گل لیگ معتبر", "wins": 3, "losses": 0, "active": True},
            "strong_home_continental": {"fa": "تیم قوی در خانه مسابقات قاره‌ای", "wins": 1, "losses": 0, "active": True},
        },
    }


def add_bet(ledger, date, match, pattern, bet_type, odds, stake):
    bid = len(ledger["bets"]) + 1
    ledger["bets"].append({
        "id": bid,
        "date": date,
        "match": match,
        "pattern": pattern,
        "bet_type": bet_type,
        "odds": odds,
        "stake": stake,
        "result": "",
        "lesson": "",
    })
    return bid


def record_result(ledger, bet_id, result, lesson=""):
    """result: 'W' یا 'L' یا 'V' (برگشت وجه)"""
    for b in ledger["bets"]:
        if b["id"] == bet_id and not b["result"]:
            b["result"] = result
            b["lesson"] = lesson
            p = ledger["patterns"].get(b["pattern"])
            if p:
                if result == "W":
                    p["wins"] += 1
                elif result == "L":
                    p["losses"] += 1
                auto_retire(ledger)
            return True
    return False


def success_rate(p) -> float:
    total = p["wins"] + p["losses"]
    return (p["wins"] / total * 100.0) if total else 0.0


def auto_retire(ledger):
    """الگوی زیر ۵۵٪ موفقیت (با ≥۵ بازی) = بازنشستگی خودکار"""
    retired = []
    for p in ledger["patterns"].values():
        total = p["wins"] + p["losses"]
        if total >= MIN_GAMES and success_rate(p) < RETIRE_RATE and p["active"]:
            p["active"] = False
            retired.append(p["fa"])
    return retired


def pattern_active(ledger, key) -> bool:
    p = ledger["patterns"].get(key)
    return bool(p and p["active"])


def ledger_summary(ledger) -> str:
    lines = ["📒 دفتر نبردها — کارنامهٔ الگوها:"]
    for p in ledger["patterns"].values():
        rate = success_rate(p)
        status = "✅ فعال" if p["active"] else "🪦 بازنشسته"
        lines.append(f"• {p['fa']}: {p['wins']}برد/{p['losses']}باخت ({rate:.0f}٪) {status}")
    open_bets = [b for b in ledger["bets"] if not b["result"]]
    lines.append(f"\nشرط‌های باز: {len(open_bets)} | کل ثبت‌ها: {len(ledger['bets'])}")
    for b in ledger["bets"][-5:]:
        res = b["result"] or "—"
        lines.append(f"#{b['id']} {b['date']} {b['match']} | {b['bet_type']} @ {b['odds']} | {res}")
    return "\n".join(lines)


# ---------- همگام‌سازی با گیت‌هاب (ماندگاری دائمی) ----------

def _headers():
    return {
        "Authorization": f"Bearer {os.getenv('GITHUB_PAT', '')}",
        "Accept": "application/vnd.github+json",
    }


def _api_url():
    return f"https://api.github.com/repos/{GITHUB_REPO}/contents/{LEDGER_PATH}"


def load_ledger():
    pat = os.getenv("GITHUB_PAT", "")
    if pat:
        try:
            r = requests.get(_api_url(), headers=_headers(), timeout=20)
            if r.status_code == 200:
                content = base64.b64decode(r.json()["content"]).decode("utf-8")
                return json.loads(content)
        except Exception:
            pass
    return default_ledger()


def save_ledger(ledger) -> bool:
    pat = os.getenv("GITHUB_PAT", "")
    if not pat:
        return False
    try:
        r = requests.get(_api_url(), headers=_headers(), timeout=20)
        sha = r.json().get("sha") if r.status_code == 200 else None
        body = {
            "message": "ledger update",
            "content": base64.b64encode(
                json.dumps(ledger, ensure_ascii=False, indent=2).encode("utf-8")
            ).decode("utf-8"),
        }
        if sha:
            body["sha"] = sha
        requests.put(_api_url(), headers=_headers(), json=body, timeout=20)
        return True
    except Exception:
        return False
