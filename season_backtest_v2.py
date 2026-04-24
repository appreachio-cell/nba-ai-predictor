"""
season_backtest_v2.py — Full 2025-26 NBA season backtest using real moneylines.

Pulls historical odds from OddsPortal (free, no key needed).
Simulates the model's core logic: pick the de-vigged favourite,
grade against actual results.

Run:
    pip install requests beautifulsoup4
    python season_backtest_v2.py

First run takes a few minutes (scraping ~1200 games).
Results cached in season_odds_cache.json so re-runs are instant.
"""

import json, os, re, time, urllib.request
from datetime import datetime

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    os.system("pip install requests beautifulsoup4")
    import requests
    from bs4 import BeautifulSoup

CACHE_FILE  = "season_odds_cache.json"
RESULT_FILE = "season_backtest_results.txt"
HEADERS     = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120",
    "Accept-Language": "en-US,en;q=0.9",
}

# OddsPortal NBA 2025-26 results pages (pagination)
BASE_URL = "https://www.oddsportal.com/basketball/usa/nba/results/"


# ── ODDS MATH ─────────────────────────────────────────────────────────────────
def implied(odds):
    o = float(odds)
    return abs(o) / (abs(o) + 100) if o < 0 else 100 / (o + 100)

def true_probs(o1, o2):
    p1 = implied(o1); p2 = implied(o2); t = p1 + p2
    return p1 / t, p2 / t

def profit(odds, result, stake=10):
    if odds is None: return 0.0
    o = float(odds)
    if result == "W":
        return stake * (100 / abs(o)) if o < 0 else stake * (o / 100)
    return -stake

def decimal_to_american(dec):
    """Convert decimal odds (e.g. 1.65) to American (e.g. -154)."""
    if dec is None or dec <= 1.0: return None
    if dec >= 2.0:
        return round((dec - 1) * 100)
    else:
        return round(-100 / (dec - 1))

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


# ── SCRAPE ODDSPORTAL ─────────────────────────────────────────────────────────
def scrape_page(url, page=1):
    """Scrape one results page from OddsPortal. Returns list of game dicts."""
    target = url if page == 1 else f"{url}#/page/{page}/"
    print(f"  Page {page}...", end=" ", flush=True)
    try:
        r = requests.get(target, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            print(f"HTTP {r.status_code}")
            return [], False

        soup = BeautifulSoup(r.text, "html.parser")

        # OddsPortal renders via JS so we need to find the JSON data in the page
        # Look for the script tag containing game data
        games = []

        # Try to find table rows
        rows = soup.select("div.eventRow, tr.deactivate, div[class*='flex'][class*='border']")

        # Alternative: look for the next-data JSON blob
        next_data = soup.find("script", id="__NEXT_DATA__")
        if next_data:
            try:
                data = json.loads(next_data.string)
                # Navigate to events
                events = (data.get("props", {})
                              .get("pageProps", {})
                              .get("initialEvents", []))
                if not events:
                    # Try alternate path
                    events = (data.get("props", {})
                                  .get("pageProps", {})
                                  .get("data", {})
                                  .get("results", []))

                for ev in events:
                    try:
                        home    = ev.get("home-name") or ev.get("home_name", "")
                        away    = ev.get("away-name") or ev.get("away_name", "")
                        h_score = ev.get("home-score") or ev.get("home_score")
                        a_score = ev.get("away-score") or ev.get("away_score")
                        date_ts = ev.get("date-start-timestamp") or ev.get("date_start_timestamp")

                        # Odds (decimal format on OddsPortal)
                        odds    = ev.get("odds", {})
                        h_dec   = odds.get("1")   # home win
                        a_dec   = odds.get("2")   # away win

                        if not home or not away or h_score is None: continue

                        h_ml = decimal_to_american(float(h_dec)) if h_dec else None
                        a_ml = decimal_to_american(float(a_dec)) if a_dec else None

                        dt = datetime.fromtimestamp(date_ts).strftime("%Y-%m-%d") if date_ts else ""

                        games.append({
                            "date":       dt,
                            "home":       home,
                            "away":       away,
                            "home_score": int(h_score),
                            "away_score": int(a_score),
                            "home_won":   int(h_score) > int(a_score),
                            "total":      int(h_score) + int(a_score),
                            "h_ml":       h_ml,
                            "a_ml":       a_ml,
                        })
                    except: continue

                has_next = bool(soup.select_one("a[href*='/page/']"))
                print(f"{len(games)} games")
                return games, has_next

            except Exception as e:
                print(f"JSON parse error: {e}")

        # Fallback: no JS data found
        print("no data (JS-rendered, try selenium)")
        return [], False

    except Exception as e:
        print(f"error: {e}")
        return [], False


def fetch_all_games():
    """
    OddsPortal is JS-rendered which makes pure scraping hard.
    Fall back to their API endpoint which returns JSON directly.
    """
    print("Fetching from OddsPortal API...")
    games = []

    # OddsPortal uses an internal API - try it
    api_url = ("https://www.oddsportal.com/api/v2/search-results-page/sport/basketball/"
               "?season=2025-2026&tournamentId=basketball%2Fusa%2Fnba&page=1&pageSize=50")

    try:
        r = requests.get(api_url, headers=HEADERS, timeout=15)
        print(f"  API status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"  Keys: {list(data.keys())[:5]}")
    except Exception as e:
        print(f"  API error: {e}")

    return games


def fetch_sportsbookreview():
    """
    Sportsbookreview has free historical odds in XLS format.
    URL pattern: https://www.sportsbookreviewsonline.com/scoresoddsarchives/nba/nba%20odds%202025-26.xlsx
    """
    print("\nTrying Sportsbookreview (free Excel download)...")
    url = "https://www.sportsbookreviewsonline.com/scoresoddsarchives/nba/nba%20odds%202025-26.xlsx"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()

        with open("nba_odds_2025_26.xlsx", "wb") as f:
            f.write(data)
        print(f"  ✅ Downloaded! ({len(data)//1024}KB) → nba_odds_2025_26.xlsx")
        return True
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return False


def parse_sbr_excel():
    """Parse the SBR Excel file if we got it."""
    try:
        import openpyxl
    except ImportError:
        os.system("pip install openpyxl")
        import openpyxl

    path = "nba_odds_2025_26.xlsx"
    if not os.path.exists(path):
        return []

    print("Parsing Excel file...")
    wb   = openpyxl.load_workbook(path)
    ws   = wb.active
    rows = list(ws.iter_rows(values_only=True))

    print(f"  Rows: {len(rows)}")
    if rows:
        print(f"  Headers: {rows[0]}")

    # SBR format: Date, Rot, VH, Team, 1st, 2nd, 3rd, 4th, Final, Open, Close, ML, 2H
    games  = []
    i      = 1  # skip header
    while i < len(rows) - 1:
        try:
            away_row = rows[i]
            home_row = rows[i + 1]

            date_val  = away_row[0]
            away_team = str(away_row[3]).strip() if away_row[3] else ""
            home_team = str(home_row[3]).strip() if home_row[3] else ""

            away_score = away_row[8]  # Final column
            home_score = home_row[8]

            away_ml = away_row[11]  # ML column
            home_ml = home_row[11]

            if not away_team or not home_team: i += 2; continue
            if away_score is None or home_score is None: i += 2; continue

            # Parse date
            if isinstance(date_val, int):
                dt = f"{str(date_val)[:4]}-{str(date_val)[4:6]}-{str(date_val)[6:8]}"
            elif isinstance(date_val, datetime):
                dt = date_val.strftime("%Y-%m-%d")
            else:
                dt = str(date_val)

            games.append({
                "date":       dt,
                "home":       home_team,
                "away":       away_team,
                "home_score": int(home_score),
                "away_score": int(away_score),
                "home_won":   int(home_score) > int(away_score),
                "total":      int(home_score) + int(away_score),
                "h_ml":       int(home_ml) if home_ml and str(home_ml).lstrip('-').isdigit() else None,
                "a_ml":       int(away_ml) if away_ml and str(away_ml).lstrip('-').isdigit() else None,
            })
        except: pass
        i += 2

    print(f"  Parsed {len(games)} games")
    return games


# ── SIMULATE ──────────────────────────────────────────────────────────────────
def simulate(games):
    picks = []
    no_odds = 0

    for g in games:
        h_ml = g.get("h_ml")
        a_ml = g.get("a_ml")

        if h_ml and a_ml:
            h_prob, a_prob = true_probs(h_ml, a_ml)
        else:
            # No odds — use generic home court (54%)
            h_prob, a_prob = 0.54, 0.46
            h_ml = a_ml = None
            no_odds += 1

        if h_prob >= a_prob:
            side, prob, odds = "home", h_prob, h_ml
        else:
            side, prob, odds = "away", a_prob, a_ml

        result = "W" if (side == "home" and g["home_won"]) or \
                        (side == "away" and not g["home_won"]) else "L"

        picks.append({
            "date":       g.get("date", ""),
            "matchup":    f"{g['away']} @ {g['home']}",
            "pick_side":  side,
            "pick_team":  g["home"] if side == "home" else g["away"],
            "pick_prob":  prob,
            "pick_odds":  odds,
            "result":     result,
        })

    if no_odds:
        print(f"  ⚠ {no_odds}/{len(games)} games had no odds — used 54% home default")
    return picks


# ── REPORT ────────────────────────────────────────────────────────────────────
def report(picks):
    lines = []
    def p(*args):
        s = " ".join(str(a) for a in args)
        print(s); lines.append(s)

    total = len(picks)
    wins  = sum(1 for x in picks if x["result"] == "W")
    with_odds = [x for x in picks if x["pick_odds"] is not None]

    p("\n" + "━"*62)
    p("  NBA AI PREDICTOR — FULL SEASON BACKTEST  2025-26")
    p("━"*62)
    p(f"\n  Total graded picks : {total}")
    p(f"  Picks with real ML : {len(with_odds)}")
    p(f"  Overall record     : {wins}-{total-wins}  ({pct(wins, total)})")
    p(f"  {bar(wins, total)}")

    p(f"\n{'─'*62}")
    p("  FLAT BET P&L  (picks with real moneyline odds only)")
    p(f"{'─'*62}")
    p(f"  {'Stake':>6}  {'P&L':>9}  {'ROI':>7}  {'Per pick':>9}")
    for stake in [10, 25, 50]:
        pnl     = sum(profit(x["pick_odds"], x["result"], stake) for x in with_odds)
        wagered = stake * len(with_odds)
        roi     = pnl / wagered * 100 if wagered else 0
        sign    = "+" if pnl >= 0 else ""
        p(f"  ${stake:>5}  {sign}${pnl:>8.2f}  {sign}{roi:>5.1f}%  {sign}${pnl/len(with_odds) if with_odds else 0:>7.2f}")

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
        aodds= sum(float(x["pick_odds"]) for x in bo) / len(bo) if bo else 0
        sign = "+" if pnl >= 0 else ""
        p(f"\n  {cb}  —  {bt} games  ({len(bo)} with odds)")
        p(f"  {bar(bw, bt, 15)} {bw}-{bt-bw} ({pct(bw, bt)})")
        if bo: p(f"  Avg odds: {fmt_odds(aodds)}   $10 P&L: {sign}${pnl:.2f}")

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
        grp = [x for x in picks if fn(x["pick_odds"])]
        if not grp: continue
        gw = sum(1 for x in grp if x["result"] == "W")
        pnl= sum(profit(x["pick_odds"], x["result"], 10) for x in grp)
        sign="+" if pnl>=0 else ""
        p(f"  {label:<20} {len(grp):>4} picks  {gw}-{len(grp)-gw}  ({pct(gw,len(grp))})  $10: {sign}${pnl:.2f}")

    p(f"\n{'─'*62}")
    p("  MONTH BY MONTH")
    p(f"{'─'*62}")
    by_month = {}
    for x in picks:
        try:
            key = x["date"][:7]
        except: key = "unknown"
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

    p(f"\n{'━'*62}\n")

    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Saved → {RESULT_FILE}")


# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Check cache first
    if os.path.exists(CACHE_FILE):
        print(f"Loading cache from {CACHE_FILE}...")
        with open(CACHE_FILE) as f:
            games = json.load(f)
        print(f"  {len(games)} games loaded")
    else:
        # Try SBR Excel download first (most reliable free source)
        ok = fetch_sportsbookreview()
        if ok:
            games = parse_sbr_excel()
        else:
            print("\n❌ Could not fetch odds data automatically.")
            print("\nManual option:")
            print("  1. Go to: https://www.sportsbookreviewsonline.com/scoresoddsarchives/nba/nbaoddsarchives.htm")
            print("  2. Download 'NBA 2025-26' Excel file")
            print("  3. Save it as 'nba_odds_2025_26.xlsx' in C:\\NBA")
            print("  4. Run this script again")
            games = []

        if games:
            with open(CACHE_FILE, "w") as f:
                json.dump(games, f, indent=2)
            print(f"Cached {len(games)} games → {CACHE_FILE}")

    if not games:
        exit(1)

    completed = [g for g in games if g.get("home_score") is not None]
    print(f"\nSimulating {len(completed)} completed games...")
    picks = simulate(completed)
    report(picks)
