"""
season_backtest.py — Simulate the NBA AI Predictor across the full 2025-26 season.

Uses Basketball Reference for game results + closing lines.
Simulates what the model would have picked (favourite after removing vig)
and grades every game.

Run:
    pip install requests beautifulsoup4
    python season_backtest.py

Output: season_backtest_results.txt  +  prints to console
"""

import time, json, os, re
from datetime import datetime

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Installing required packages...")
    os.system("pip install requests beautifulsoup4")
    import requests
    from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
BASE    = "https://www.basketball-reference.com"

# NBA 2025-26 regular season months
MONTHS  = ["october", "november", "december", "january", "february", "march", "april"]
SEASON  = "2026"


# ── HELPERS ───────────────────────────────────────────────────────────────────
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


# ── SCRAPE BASKETBALL REFERENCE ───────────────────────────────────────────────
def fetch_month(month):
    url = f"{BASE}/leagues/NBA_{SEASON}_games-{month}.html"
    print(f"  Fetching {month}...", end=" ", flush=True)
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            print(f"HTTP {r.status_code}")
            return []
        soup  = BeautifulSoup(r.text, "html.parser")
        table = soup.find("table", id="schedule")
        if not table:
            print("no table")
            return []

        games = []
        for row in table.find("tbody").find_all("tr"):
            if row.get("class") == ["thead"]: continue
            cells = row.find_all(["td", "th"])
            if len(cells) < 7: continue

            try:
                date_str = cells[0].get_text(strip=True)
                away     = cells[2].get_text(strip=True)
                away_pts = cells[3].get_text(strip=True)
                home     = cells[4].get_text(strip=True)
                home_pts = cells[5].get_text(strip=True)

                # Odds are in later columns if available (col index varies)
                # BRef shows spread and over/under but not moneyline
                # We'll use the spread to derive implied odds
                spread = None
                for c in cells[7:]:
                    txt = c.get_text(strip=True)
                    m   = re.match(r'^([+-]?\d+\.?\d*)$', txt)
                    if m:
                        try:
                            spread = float(m.group(1))
                            break
                        except: pass

                if not away_pts or not home_pts:
                    continue  # game not played yet

                away_score = int(away_pts)
                home_score = int(home_pts)
                home_won   = home_score > away_score

                games.append({
                    "date":       date_str,
                    "home":       home,
                    "away":       away,
                    "home_score": home_score,
                    "away_score": away_score,
                    "home_won":   home_won,
                    "total":      home_score + away_score,
                    "spread":     spread,  # negative = home favoured
                })
            except: continue

        print(f"{len(games)} games")
        time.sleep(3)  # be polite to BRef
        return games

    except Exception as e:
        print(f"error: {e}")
        return []


def fetch_full_season():
    all_games = []
    for month in MONTHS:
        games = fetch_month(month)
        all_games.extend(games)
    return all_games


# ── SIMULATE PICKS ────────────────────────────────────────────────────────────
def spread_to_ml(spread):
    """
    Convert point spread to approximate moneyline odds.
    NBA calibration: -7 spread ≈ -300 ML, -3 ≈ -160, 0 ≈ -110
    """
    if spread is None:
        return None, None
    # Formula: roughly 28 * spread in points → ML price
    if spread == 0:
        return -110, -110
    fav_ml  = round(-(100 + abs(spread) * 28))
    fav_ml  = max(fav_ml, -2500)
    dog_ml  = round(abs(fav_ml) * 0.75)  # rough vig removal
    if spread < 0:  # home is favourite
        return fav_ml, dog_ml
    else:            # away is favourite
        return dog_ml, fav_ml


def simulate_picks(games):
    """
    Simulate what the model would pick for each game.
    Logic: pick the side with higher true probability (de-vigged favourite).
    Use spread to derive ML odds where available, otherwise apply 54% home edge.
    """
    picks = []
    for g in games:
        spread = g.get("spread")

        if spread is not None:
            h_ml, a_ml = spread_to_ml(spread)
            if h_ml and a_ml:
                h_prob, a_prob = true_probs(h_ml, a_ml)
            else:
                h_prob, a_prob = 0.54, 0.46
                h_ml = a_ml = None
        else:
            # No spread — apply generic home court edge
            h_prob, a_prob = 0.54, 0.46
            h_ml = a_ml = None

        # Model picks the higher probability side
        if h_prob >= a_prob:
            pick_side = "home"
            pick_prob = h_prob
            pick_odds = h_ml
        else:
            pick_side = "away"
            pick_prob = a_prob
            pick_odds = a_ml

        result = "W" if (pick_side == "home" and g["home_won"]) or \
                        (pick_side == "away" and not g["home_won"]) else "L"

        picks.append({
            "date":       g["date"],
            "matchup":    f"{g['away']} @ {g['home']}",
            "pick_side":  pick_side,
            "pick_team":  g["home"] if pick_side == "home" else g["away"],
            "pick_prob":  pick_prob,
            "pick_odds":  pick_odds,
            "spread":     spread,
            "result":     result,
            "home_score": g["home_score"],
            "away_score": g["away_score"],
            "total":      g["total"],
        })

    return picks


# ── REPORT ────────────────────────────────────────────────────────────────────
def report(picks, save_path="season_backtest_results.txt"):
    lines = []

    def p(*args):
        s = " ".join(str(a) for a in args)
        print(s)
        lines.append(s)

    total = len(picks)
    wins  = sum(1 for p_ in picks if p_["result"] == "W")

    p("\n" + "━" * 60)
    p("  NBA AI PREDICTOR — FULL SEASON BACKTEST  2025-26")
    p("━" * 60)
    p(f"\n  Total games  : {total}")
    p(f"  Record       : {wins}-{total-wins}  ({pct(wins, total)})")
    p(f"  {bar(wins, total)}")

    # Flat bet P&L
    p(f"\n{'─'*60}")
    p("  FLAT BET P&L  ($10 / $25 / $50 per game)")
    p(f"{'─'*60}")
    p(f"  {'Stake':>6}  {'P&L':>9}  {'ROI':>7}  {'Per game':>9}")
    for stake in [10, 25, 50]:
        pnl     = sum(profit(p_["pick_odds"], p_["result"], stake) for p_ in picks)
        wagered = stake * total
        roi     = pnl / wagered * 100 if wagered else 0
        sign    = "+" if pnl >= 0 else ""
        p(f"  ${stake:>5}  {sign}${pnl:>8.2f}  {sign}{roi:>5.1f}%  {sign}${pnl/total:>7.2f}")

    # By confidence bucket
    p(f"\n{'─'*60}")
    p("  BY CONFIDENCE BUCKET")
    p(f"{'─'*60}")
    for cb in ["50-59%", "60-69%", "70-79%", "80+%"]:
        bp = [p_ for p_ in picks if conf_bucket(p_["pick_prob"]) == cb]
        if not bp: continue
        bw    = sum(1 for p_ in bp if p_["result"] == "W")
        bt    = len(bp)
        pnl10 = sum(profit(p_["pick_odds"], p_["result"], 10) for p_ in bp)
        odds_list = [float(p_["pick_odds"]) for p_ in bp if p_["pick_odds"]]
        avg_o = sum(odds_list) / len(odds_list) if odds_list else 0
        sign  = "+" if pnl10 >= 0 else ""
        p(f"\n  {cb}  —  {bt} games")
        p(f"  {bar(bw, bt, 15)} {bw}-{bt-bw} ({pct(bw, bt)})")
        p(f"  Avg odds: {fmt_odds(avg_o)}   $10 flat P&L: {sign}${pnl10:.2f}")

    # Odds distribution
    p(f"\n{'─'*60}")
    p("  ODDS DISTRIBUTION")
    p(f"{'─'*60}")
    ranges = [
        ("-400 or worse",  lambda o: o is not None and float(o) <= -400),
        ("-300 to -399",   lambda o: o is not None and -400 < float(o) <= -300),
        ("-200 to -299",   lambda o: o is not None and -300 < float(o) <= -200),
        ("-130 to -199",   lambda o: o is not None and -200 < float(o) <= -130),
        ("pick / +odds",   lambda o: o is not None and float(o) > -130),
        ("no odds data",   lambda o: o is None),
    ]
    for label, fn in ranges:
        grp = [p_ for p_ in picks if fn(p_["pick_odds"])]
        if not grp: continue
        gw = sum(1 for p_ in grp if p_["result"] == "W")
        p(f"  {label:<20} {len(grp):>4} games  {gw}-{len(grp)-gw}  ({pct(gw, len(grp))})")

    # Month by month
    p(f"\n{'─'*60}")
    p("  MONTH BY MONTH")
    p(f"{'─'*60}")
    by_month = {}
    for p_ in picks:
        try:
            dt = datetime.strptime(p_["date"], "%a, %b %d, %Y")
            key = dt.strftime("%B %Y")
        except:
            key = p_["date"][:7]
        by_month.setdefault(key, []).append(p_)

    for month, mp in by_month.items():
        mw   = sum(1 for p_ in mp if p_["result"] == "W")
        mt   = len(mp)
        pnl  = sum(profit(p_["pick_odds"], p_["result"], 10) for p_ in mp)
        sign = "+" if pnl >= 0 else ""
        p(f"  {month:<18} {bar(mw, mt, 12)} {mw}-{mt-mw} ({pct(mw, mt)})  $10: {sign}${pnl:.2f}")

    # Home vs away bias check
    home_picks = [p_ for p_ in picks if p_["pick_side"] == "home"]
    away_picks = [p_ for p_ in picks if p_["pick_side"] == "away"]
    hw = sum(1 for p_ in home_picks if p_["result"] == "W")
    aw = sum(1 for p_ in away_picks if p_["result"] == "W")
    p(f"\n{'─'*60}")
    p("  HOME vs AWAY PICKS")
    p(f"{'─'*60}")
    p(f"  Home picks: {len(home_picks)}  →  {hw}-{len(home_picks)-hw} ({pct(hw, len(home_picks))})")
    p(f"  Away picks: {len(away_picks)}  →  {aw}-{len(away_picks)-aw} ({pct(aw, len(away_picks))})")

    p(f"\n{'━'*60}")
    p(f"  Results saved to: season_backtest_results.txt")
    p(f"{'━'*60}\n")

    with open(save_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    cache = "season_games_cache.json"

    if os.path.exists(cache):
        print(f"Loading cached games from {cache}...")
        with open(cache) as f:
            games = json.load(f)
        print(f"  {len(games)} games loaded")
    else:
        print("Fetching full 2025-26 NBA season from Basketball Reference...")
        print("(This takes ~30 seconds — being polite to their servers)\n")
        games = fetch_full_season()
        with open(cache, "w") as f:
            json.dump(games, f, indent=2)
        print(f"\n  Total games fetched: {len(games)}")

    # Filter to completed games only
    completed = [g for g in games if g.get("home_score") and g.get("away_score")]
    print(f"  Completed games: {len(completed)}")

    picks = simulate_picks(completed)
    report(picks)
