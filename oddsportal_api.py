"""
oddsportal_api.py — Scrape NBA 2025-26 odds directly from OddsPortal's internal AJAX API.

No Selenium needed — hits the API endpoint directly.

Run: python oddsportal_api.py
"""

import json, os, re, time, urllib.request
from datetime import datetime

CACHE_FILE  = "season_odds_cache.json"
RESULT_FILE = "season_backtest_results.txt"

# The internal AJAX endpoint discovered from network logs
# OIo52B5b = NBA 2025-26 tournament ID
# Format: /ajax-sport-country-tournament-archive_/3/{tournament_id}/{filter}/{page}/0/
AJAX_BASE = ("https://www.oddsportal.com/ajax-sport-country-tournament-archive_/"
             "3/OIo52B5b/X202178560X0X0X0X0X0X0X0X0X0X0X0X0X134217728X0X0X0X0X0X8X512"
             "X32X0X0X0X0X0X0X0X536870912X2560X2048X0X33554560X8519680X0X0X0X524288/{page}/0/")

HEADERS = {
    "User-Agent":  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120",
    "Accept":      "application/json, text/javascript, */*; q=0.01",
    "Referer":     "https://www.oddsportal.com/basketball/usa/nba/results/",
    "X-Requested-With": "XMLHttpRequest",
}


# ── ODDS MATH ─────────────────────────────────────────────────────────────────
def implied(odds):
    o = float(odds)
    return abs(o) / (abs(o) + 100) if o < 0 else 100 / (o + 100)

def true_probs(o1, o2):
    p1 = implied(o1); p2 = implied(o2); t = p1 + p2
    return p1 / t, p2 / t

def decimal_to_american(dec):
    if dec is None or float(dec) <= 1.01: return None
    d = float(dec)
    if d >= 2.0: return round((d - 1) * 100)
    return round(-100 / (d - 1))

def profit(odds, result, stake=10):
    if odds is None: return 0.0
    o = float(odds)
    if result == "W":
        return stake * (100 / abs(o)) if o < 0 else stake * (o / 100)
    return -stake

def fmt_odds(o):
    if o is None: return "  n/a"
    return f"+{int(o):4d}" if float(o) > 0 else f"{int(o):5d}"

def pct(w, t):
    return f"{round(w/t*100,1)}%" if t else "—"

def bar(w, t, width=20):
    filled = round(w / t * width) if t else 0
    return "█" * filled + "░" * (width - filled)

def conf_bucket(prob):
    c = round(prob * 100)
    if c >= 80:   return "80+%"
    if c >= 70:   return "70-79%"
    if c >= 60:   return "60-69%"
    return "50-59%"


# ── FETCH ONE PAGE ────────────────────────────────────────────────────────────
def fetch_page(page):
    url = AJAX_BASE.format(page=page) + f"?_={int(time.time()*1000)}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read().decode("utf-8")

        # OddsPortal wraps JSON in a callback or returns raw JSON
        # Strip any JSONP wrapper
        raw = raw.strip()
        if raw.startswith("globals.jsonpCallback"):
            raw = re.sub(r"^[^(]+\(", "", raw).rstrip(");")

        data = json.loads(raw)
        return data
    except Exception as e:
        print(f"    Error: {e}")
        return None


# ── PARSE GAMES FROM RESPONSE ─────────────────────────────────────────────────
def parse_games(data):
    games = []
    if not data:
        return games

    # OddsPortal response structure varies — explore it
    if isinstance(data, dict):
        # Look for 'd' key (common pattern) or 'data'
        payload = data.get("d") or data.get("data") or data

        if isinstance(payload, dict):
            # Try to find rows/events
            rows = (payload.get("rows") or payload.get("events") or
                    payload.get("oddsdata") or [])

            # Sometimes it's nested under another key
            if not rows:
                for k, v in payload.items():
                    if isinstance(v, list) and len(v) > 0:
                        rows = v
                        break
                    elif isinstance(v, dict):
                        for k2, v2 in v.items():
                            if isinstance(v2, list) and len(v2) > 0:
                                rows = v2
                                break

            for row in rows:
                game = parse_row(row)
                if game:
                    games.append(game)

        elif isinstance(payload, list):
            for row in payload:
                game = parse_row(row)
                if game:
                    games.append(game)

    elif isinstance(data, list):
        for row in data:
            game = parse_row(row)
            if game:
                games.append(game)

    return games


def parse_row(row):
    if not isinstance(row, dict):
        return None
    try:
        home = row.get("home-name") or row.get("home_name") or row.get("home") or ""
        away = row.get("away-name") or row.get("away_name") or row.get("away") or ""
        if not home or not away:
            return None

        h_score = row.get("home-score") or row.get("home_score") or row.get("score-home")
        a_score = row.get("away-score") or row.get("away_score") or row.get("score-away")
        if h_score is None or a_score is None:
            return None

        ts = row.get("date-start-timestamp") or row.get("date_start") or 0
        try:
            dt = datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d")
        except:
            dt = ""

        # Odds: decimal format, "1" = home, "2" = away
        odds = row.get("odds") or {}
        h_dec = odds.get("1") or odds.get("home")
        a_dec = odds.get("2") or odds.get("away")
        h_ml  = decimal_to_american(h_dec) if h_dec else None
        a_ml  = decimal_to_american(a_dec) if a_dec else None

        return {
            "date":       dt,
            "home":       str(home),
            "away":       str(away),
            "home_score": int(h_score),
            "away_score": int(a_score),
            "home_won":   int(h_score) > int(a_score),
            "total":      int(h_score) + int(a_score),
            "h_ml":       h_ml,
            "a_ml":       a_ml,
        }
    except:
        return None


# ── SCRAPE ALL PAGES ──────────────────────────────────────────────────────────
def scrape_all():
    all_games = []
    page      = 1

    print("Scraping OddsPortal AJAX API...")
    while True:
        print(f"  Page {page}...", end=" ", flush=True)
        data = fetch_page(page)

        if data is None:
            print("failed — stopping")
            break

        # Save raw response for first page so we can inspect it
        if page == 1:
            with open("oddsportal_raw_p1.json", "w") as f:
                json.dump(data, f, indent=2)
            print(f"(raw saved to oddsportal_raw_p1.json)", end=" ")

        games = parse_games(data)
        print(f"→ {len(games)} games")

        if not games:
            # Print raw structure to help debug
            print(f"    Raw keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
            if isinstance(data, dict):
                for k, v in data.items():
                    print(f"    [{k}]: {str(v)[:150]}")
            break

        all_games.extend(games)
        page += 1
        if page > 60:
            break
        time.sleep(1.5)

    return all_games


# ── SIMULATE ──────────────────────────────────────────────────────────────────
def simulate(games):
    picks   = []
    no_odds = 0
    for g in games:
        h_ml = g.get("h_ml")
        a_ml = g.get("a_ml")
        if h_ml and a_ml:
            h_prob, a_prob = true_probs(h_ml, a_ml)
        else:
            h_prob, a_prob = 0.54, 0.46
            h_ml = a_ml = None
            no_odds += 1

        side  = "home" if h_prob >= a_prob else "away"
        prob  = h_prob if side == "home" else a_prob
        odds  = h_ml   if side == "home" else a_ml
        result = "W" if (side == "home" and g["home_won"]) or \
                        (side == "away" and not g["home_won"]) else "L"
        picks.append({
            "date":      g.get("date",""),
            "matchup":   f"{g['away']} @ {g['home']}",
            "pick_side": side,
            "pick_prob": prob,
            "pick_odds": odds,
            "result":    result,
        })

    if no_odds:
        print(f"  ⚠ {no_odds}/{len(games)} games missing odds — used 54% home default")
    return picks


# ── REPORT ────────────────────────────────────────────────────────────────────
def report(picks):
    lines = []
    def p(*args):
        s = " ".join(str(a) for a in args)
        print(s); lines.append(s)

    total     = len(picks)
    wins      = sum(1 for x in picks if x["result"] == "W")
    with_odds = [x for x in picks if x["pick_odds"] is not None]

    p("\n" + "━"*62)
    p("  NBA AI PREDICTOR — FULL SEASON BACKTEST  2025-26")
    p("━"*62)
    p(f"\n  Total graded picks : {total}")
    p(f"  Picks with real ML : {len(with_odds)}")
    p(f"  Overall record     : {wins}-{total-wins}  ({pct(wins,total)})")
    p(f"  {bar(wins,total)}")

    if with_odds:
        p(f"\n{'─'*62}")
        p("  FLAT BET P&L  (picks with real moneyline odds)")
        p(f"{'─'*62}")
        p(f"  {'Stake':>6}  {'P&L':>9}  {'ROI':>7}  {'Per pick':>9}")
        for stake in [10, 25, 50]:
            pnl     = sum(profit(x["pick_odds"], x["result"], stake) for x in with_odds)
            wagered = stake * len(with_odds)
            roi     = pnl / wagered * 100 if wagered else 0
            sign    = "+" if pnl >= 0 else ""
            n       = len(with_odds)
            p(f"  ${stake:>5}  {sign}${pnl:>8.2f}  {sign}{roi:>5.1f}%  {sign}${pnl/n:>7.2f}")

    p(f"\n{'─'*62}")
    p("  BY CONFIDENCE BUCKET")
    p(f"{'─'*62}")
    for cb in ["50-59%","60-69%","70-79%","80+%"]:
        bp = [x for x in picks if conf_bucket(x["pick_prob"]) == cb]
        if not bp: continue
        bw   = sum(1 for x in bp if x["result"] == "W")
        bt   = len(bp)
        bo   = [x for x in bp if x["pick_odds"] is not None]
        pnl  = sum(profit(x["pick_odds"], x["result"], 10) for x in bo)
        aodds= sum(float(x["pick_odds"]) for x in bo)/len(bo) if bo else 0
        sign = "+" if pnl >= 0 else ""
        p(f"\n  {cb}  —  {bt} games  ({len(bo)} with odds)")
        p(f"  {bar(bw,bt,15)} {bw}-{bt-bw} ({pct(bw,bt)})")
        if bo: p(f"  Avg odds: {fmt_odds(aodds)}   $10 P&L: {sign}${pnl:.2f}")

    p(f"\n{'─'*62}")
    p("  MONTH BY MONTH")
    p(f"{'─'*62}")
    by_month = {}
    for x in picks:
        key = x["date"][:7] if x["date"] else "unknown"
        by_month.setdefault(key, []).append(x)
    for mo in sorted(by_month):
        mp   = by_month[mo]
        mw   = sum(1 for x in mp if x["result"] == "W")
        mt   = len(mp)
        pnl  = sum(profit(x["pick_odds"], x["result"], 10) for x in mp)
        sign = "+" if pnl >= 0 else ""
        try: label = datetime.strptime(mo, "%Y-%m").strftime("%B %Y")
        except: label = mo
        p(f"  {label:<18} {bar(mw,mt,12)} {mw}-{mt-mw} ({pct(mw,mt)})  $10: {sign}${pnl:.2f}")

    p(f"\n{'─'*62}")
    p("  ODDS DISTRIBUTION")
    p(f"{'─'*62}")
    for label, fn in [
        ("-400 or worse",  lambda o: o is not None and float(o) <= -400),
        ("-300 to -399",   lambda o: o is not None and -400 < float(o) <= -300),
        ("-200 to -299",   lambda o: o is not None and -300 < float(o) <= -200),
        ("-130 to -199",   lambda o: o is not None and -200 < float(o) <= -130),
        ("pick / +odds",   lambda o: o is not None and float(o) > -130),
        ("no odds",        lambda o: o is None),
    ]:
        grp  = [x for x in picks if fn(x["pick_odds"])]
        if not grp: continue
        gw   = sum(1 for x in grp if x["result"] == "W")
        pnl  = sum(profit(x["pick_odds"], x["result"], 10) for x in grp)
        sign = "+" if pnl >= 0 else ""
        p(f"  {label:<20} {len(grp):>4} picks  {gw}-{len(grp)-gw}  ({pct(gw,len(grp))})  $10: {sign}${pnl:.2f}")

    p(f"\n{'━'*62}\n")
    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Saved → {RESULT_FILE}")


# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if os.path.exists(CACHE_FILE):
        print(f"Loading cache ({CACHE_FILE})...")
        with open(CACHE_FILE) as f:
            games = json.load(f)
        print(f"  {len(games)} games")
    else:
        games = scrape_all()
        if games:
            with open(CACHE_FILE, "w") as f:
                json.dump(games, f, indent=2)
            print(f"Cached {len(games)} games → {CACHE_FILE}")
        else:
            print("\n❌ No games scraped.")
            print("Upload oddsportal_raw_p1.json here so we can inspect the response structure.")
            exit(1)

    completed = [g for g in games if g.get("home_score") is not None]
    print(f"Simulating {len(completed)} games...")
    picks = simulate(completed)
    report(picks)
