"""
utils.py — Shared utilities: date helpers, HTTP fetch with cache, odds math.
"""

import json, os, re, time
import urllib.request
from datetime import date, timedelta

from config import CACHE_DIR


# ── DATE HELPERS ──────────────────────────────────────────────────────────────
def today_str():
    return date.today().strftime("%Y-%m-%d")

def yesterday_str():
    return (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")


# ── SAFE FLOAT ────────────────────────────────────────────────────────────────
def safe(v, d=0.0):
    try:
        return float(v) if v not in (None, "") else d
    except:
        return d


# ── HTTP FETCH WITH OPTIONAL CACHE ────────────────────────────────────────────
def fetch(url, cache_mins=None, no_cache=False):
    if cache_mins and not no_cache:
        key  = re.sub(r"[^a-zA-Z0-9_\-]", "_", url)[:200]
        path = os.path.join(CACHE_DIR, key + ".json")
        if os.path.exists(path):
            age_mins = (time.time() - os.path.getmtime(path)) / 60
            if age_mins < cache_mins:
                with open(path) as f:
                    return json.load(f)

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode())

    if cache_mins and not no_cache:
        key  = re.sub(r"[^a-zA-Z0-9_\-]", "_", url)[:200]
        path = os.path.join(CACHE_DIR, key + ".json")
        with open(path, "w") as f:
            json.dump(data, f)

    time.sleep(0.1)
    return data


def wipe_schedule_cache():
    """Delete today's scoreboard cache so we always get a fresh schedule."""
    td = today_str().replace("-", "")
    for fn in os.listdir(CACHE_DIR):
        if td in fn or "scoreboard" in fn.lower():
            try:
                os.remove(os.path.join(CACHE_DIR, fn))
            except:
                pass


# ── ODDS MATH ─────────────────────────────────────────────────────────────────
def implied(odds):
    """Convert American odds to implied probability."""
    o = float(odds)
    return abs(o) / (abs(o) + 100) if o < 0 else 100 / (o + 100)


def true_probs(o1, o2):
    """Remove vig and return true probabilities for both sides."""
    p1 = implied(o1)
    p2 = implied(o2)
    t  = p1 + p2
    return round(p1 / t, 4), round(p2 / t, 4)


def calc_ev(prob, odds):
    """Expected value per $100 bet given model probability and American odds."""
    if odds is None:
        return None
    o   = float(odds)
    pay = (100 / abs(o)) * 100 if o < 0 else o
    return round(prob * pay - (1 - prob) * 100, 1)


# ── FORMATTING ────────────────────────────────────────────────────────────────
def fmt_odds(o):
    if o is None:
        return "—"
    return f"+{int(float(o))}" if float(o) > 0 else str(int(float(o)))


def fmt_ev(ev):
    if ev is None:
        return "—"
    return f"+{ev}" if ev >= 0 else str(ev)


def ev_color(ev):
    if ev is None:
        return "#9ca3af"
    if ev >= 8:
        return "#16a34a"
    if ev >= 3:
        return "#65a30d"
    if ev >= 0:
        return "#d97706"
    return "#dc2626"
