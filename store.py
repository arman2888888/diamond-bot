# store.py — ماندگاری دائمی روی گیت‌هاب (data/state.json)

import base64
import json
import os

import requests

REPO = os.getenv("GITHUB_REPO", "arman2888888/diamond-bot")
PATH = "data/state.json"


def _headers():
    return {
        "Authorization": f"Bearer {os.getenv('GITHUB_PAT', '')}",
        "Accept": "application/vnd.github+json",
    }


def _url():
    return f"https://api.github.com/repos/{REPO}/contents/{PATH}"


def enabled():
    return bool(os.getenv("GITHUB_PAT", ""))


def load_state(default):
    if not enabled():
        return default
    try:
        r = requests.get(_url(), headers=_headers(), timeout=20)
        if r.status_code == 200:
            return json.loads(base64.b64decode(r.json()["content"]).decode("utf-8"))
    except Exception:
        pass
    return default


def save_state(obj):
    if not enabled():
        return False
    try:
        r = requests.get(_url(), headers=_headers(), timeout=20)
        sha = r.json().get("sha") if r.status_code == 200 else None
        body = {
            "message": "state update",
            "content": base64.b64encode(
                json.dumps(obj, ensure_ascii=False).encode("utf-8")
            ).decode("utf-8"),
        }
        if sha:
            body["sha"] = sha
        requests.put(_url(), headers=_headers(), json=body, timeout=20)
        return True
    except Exception:
        return False
