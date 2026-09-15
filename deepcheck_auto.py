# deepcheck_auto.py — دیپ‌چک خودکار با API-Football (مصدومیت/فرم/استراحت)

import os
import re
from datetime import datetime

import requests

BASE = "https://v3.football.api-sports.io"


def _headers():
    return {"x-apisports-key": os.getenv("APIFOOTBALL_KEY", "")}


def enabled():
    return bool(os.getenv("APIFOOTBALL_KEY", ""))


def _norm(s):
    s = (s or "").lower()
    s = s.replace("’", "'")
    s = re.sub(r"[^a-z0-9' ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _tok_match(x, y):
    return x == y or x.startswith(y) or y.startswith(x)


def _similar(a, b):
    ta, tb = _norm(a).split(), _norm(b).split()
    if not ta or not tb:
        return False
    matched = sum(1 for x in ta if any(_tok_match(x, y) for y in tb))
    return matched / min(len(ta), len(tb)) >= 0.6


def get_fixtures_for_date(date_str):
    try:
        r = requests.get(f"{BASE}/fixtures", params={"date": date_str}, headers=_headers(), timeout=25)
        if r.status_code != 200:
            return None, r.status_code
        return r.json().get("response", []), None
    except Exception as e:
        return None, repr(e)


def find_fixture(fixtures, home, away):
    for f in fixtures:
        t = f.get("teams") or {}
        h = (t.get("home") or {}).get("name")
        a = (t.get("away") or {}).get("name")
        if _similar(h, home) and _similar(a, away):
            return f
    return None


def injuries_by_team(fixture_id):
    try:
        r = requests.get(f"{BASE}/injuries", params={"fixture": fixture_id}, headers=_headers(), timeout=25)
        if r.status_code != 200:
            return None, r.status_code
        counts = {}
        for item in r.json().get("response", []):
            name = ((item.get("team") or {}).get("name")) or "?"
            counts[name] = counts.get(name, 0) + 1
        return counts, None
    except Exception as e:
        return None, repr(e)


def form_last5(team_id):
    try:
        r = requests.get(f"{BASE}/fixtures", params={"team": team_id, "last": 5}, headers=_headers(), timeout=25)
        if r.status_code != 200:
            return None, r.status_code
        out = []
        for f in r.json().get("response", []):
            teams = f.get("teams") or {}
            goals = f.get("goals") or {}
            th = teams.get("home") or {}
            ta = teams.get("away") or {}
            gh, ga = goals.get("home"), goals.get("away")
            if gh is None or ga is None:
                continue
            if th.get("id") == team_id:
                out.append({"res": "W" if gh > ga else "D" if gh == ga else "L",
                            "diff": gh - ga, "date": (f.get("fixture") or {}).get("date")})
            else:
                out.append({"res": "W" if ga > gh else "D" if ga == gh else "L",
                            "diff": ga - gh, "date": (f.get("fixture") or {}).get("date")})
        return out, None
    except Exception as e:
        return None, repr(e)


def _gap(form, match_iso):
    if not form or not match_iso or not form[-1].get("date"):
        return None
    try:
        md = datetime.fromisoformat(match_iso.replace("Z", "+00:00"))
        ld = datetime.fromisoformat(form[-1]["date"].replace("Z", "+00:00"))
        return (md - ld).days
    except Exception:
        return None


def analyze(match, fixtures, confirmed=False):
    """برمی‌گرداند: (dc_record, src_lines) یا (None, دلیل)"""
    if not enabled():
        return None, "کلید API-Football تنظیم نشده"
    f = find_fixture(fixtures, match["home"], match["away"])
    if not f:
        return None, "بازی در API-Football پیدا نشد"
    teams = f.get("teams") or {}
    hid = (teams.get("home") or {}).get("id")
    aid = (teams.get("away") or {}).get("id")
    hname = (teams.get("home") or {}).get("name") or match["home"]
    aname = (teams.get("away") or {}).get("name") or match["away"]
    fid = (f.get("fixture") or {}).get("id")
    match_iso = (f.get("fixture") or {}).get("date")

    counts, err = injuries_by_team(fid)
    if counts is None:
        return None, f"خطای مصدومیت‌ها: {err}"
    inj_h = sum(c for n, c in counts.items() if _similar(n, hname))
    inj_a = sum(c for n, c in counts.items() if _similar(n, aname))

    fh, _e1 = form_last5(hid)
    fa, _e2 = form_last5(aid)
    fh = fh or []
    fa = fa or []

    w1, x, w2 = match["w1"], match["x"], match["w2"]
    tot = 1.0 / w1 + 1.0 / x + 1.0 / w2
    cands = []
    if 1.8 <= w1 <= 4.5:
        cands.append(("home", w1))
    if 1.8 <= w2 <= 4.5:
        cands.append(("away", w2))
    hx2 = tot / (1.0 / w1 + 1.0 / x)
    ax2 = tot / (1.0 / w2 + 1.0 / x)
    if 1.8 <= hx2 <= 4.5:
        cands.append(("home_x2", round(hx2, 2)))
    if 1.8 <= ax2 <= 4.5:
        cands.append(("away_x2", round(ax2, 2)))
    if not cands:
        return None, "هیچ سمتی با ضریب در بازهٔ [1.8, 4.5] نیست"

    def side_info(side):
        ours_home = side in ("home", "home_x2")
        inj_opp = inj_a if ours_home else inj_h
        inj_us = inj_h if ours_home else inj_a
        form_us = fh if ours_home else fa
        form_opp = fa if ours_home else fh
        return inj_opp, inj_us, form_us, form_opp

    cands.sort(key=lambda s: -side_info(s[0])[0])
    side, our_odd = cands[0]
    inj_opp, inj_us, form_us, form_opp = side_info(side)

    form_us_up = bool(form_us) and form_us[-1]["res"] == "W" and form_us[-1]["diff"] >= 2
    form_opp_down = len(form_opp) >= 3 and len([r for r in form_opp if r["res"] == "W"]) <= 1

    rest_us = _gap(form_us, match_iso)
    rest_opp = _gap(form_opp, match_iso)
    rest_diff = (rest_us - rest_opp) if (rest_us is not None and rest_opp is not None) else 0
    fatigue_opp = rest_opp is not None and rest_opp <= 3
    fatigue_us = rest_us is not None and rest_us <= 3

    sources_inj = 0
    if inj_opp >= 4:
        sources_inj = 1
        if confirmed:
            sources_inj += 2

    src_lines = [
        f"🩺 API-Football /injuries: غایبان حریف = {inj_opp} | غایبان ما = {inj_us}",
        f"📈 فرم ما: {''.join(r['res'] for r in form_us[-5:]) or '—'} | فرم حریف: {''.join(r['res'] for r in form_opp[-5:]) or '—'}",
        f"😮‍💨 استراحت: ما {rest_us} روز | حریف {rest_opp} روز",
        f"🗣 تأیید تو (۲ منبع بیرونی): {'✅ ثبت شده' if confirmed else '❌ هنوز — دستور /confirm ردیف'}",
    ]

    dc = {
        "match": [match["home"], match["away"]],
        "side": side,
        "odds": our_odd,
        "inj_opp": inj_opp,
        "sources_inj": sources_inj,
        "rest_diff_days": rest_diff,
        "form_us": form_us_up,
        "form_opp_down": form_opp_down,
        "fatigue_opp": fatigue_opp,
        "fatigue_us": fatigue_us,
        "move_ok": True,
        "BLOCK": "",
    }
    return dc, src_lines
