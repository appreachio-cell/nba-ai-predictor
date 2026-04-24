"""
oddsportal_scraper.py — Scrape NBA 2025-26 historical moneylines from OddsPortal.

Uses Selenium + Chrome to render the JS and extract odds + results.
First run takes 10-20 mins (scraping ~50 pages). Results cached so re-runs instant.

Run:
    python oddsportal_scraper.py
"""

import json, os, time, re
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

CACHE_FILE  = "season_odds_cache.json"
RESULT_FILE = "season_backtest_results.txt"
BASE_URL    = "https://www.oddsportal.com/basketball/usa/nba/results/"


# ── ODDS MATH ─────────────────────────────────────────────────────────────────
def implied(odds):
    o = float(odds)
    return abs(o) / (abs(o) + 100) if o < 0 else 100 / (o + 100)

def true_probs(o1, o2):
    p1 = implied(o1); p2 = implied(o2); t = p1 + p2
    return p1 / t, p2 / t

def decimal_to_american(dec):
    if dec is None or dec <= 1.01: return None
    if dec >= 2.0: return round((dec - 1) * 100)
    return round(-100 / (dec - 1))

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


# ── SELENIUM SETUP ────────────────────────────────────────────────────────────
def make_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36")
    service = Service(ChromeDriverManager().install())
    driver  = webdriver.Chrome(service=service, options=opts)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver


# ── SCRAPE ONE PAGE ───────────────────────────────────────────────────────────
def scrape_page(driver, url):
    driver.get(url)
    time.sleep(4)  # let JS render

    # Wait for game rows
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.eventRow, a[href*='/basketball/usa/nba/']"))
        )
    except:
        pass

    time.sleep(2)

    games = []

    # Try to grab the __NEXT_DATA__ JSON blob (fastest method)
    try:
        script = driver.find_element(By.ID, "__NEXT_DATA__")
        data   = json.loads(script.get_attribute("innerHTML"))

        # Navigate the JSON tree to find events
        def find_events(obj, depth=0):
            if depth > 8: return []
            if isinstance(obj, list):
                # Check if this looks like a list of events
                if obj and isinstance(obj[0], dict) and "home-name" in obj[0]:
                    return obj
                for item in obj:
                    result = find_events(item, depth+1)
                    if result: return result
            elif isinstance(obj, dict):
                for k, v in obj.items():
                    if k in ("rows", "events", "data", "results", "initialEvents"):
                        found = find_events(v, depth+1)
                        if found: return found
                    else:
                        found = find_events(v, depth+1)
                        if found: return found
            return []

        events = find_events(data)
        print(f"    JSON: {len(events)} events", end=" ")

        for ev in events:
            try:
                home    = ev.get("home-name", "")
                away    = ev.get("away-name", "")
                h_score = ev.get("home-score")
                a_score = ev.get("away-score")
                ts      = ev.get("date-start-timestamp", 0)

                if not home or not away or h_score is None:
                    continue

                # Odds: OddsPortal uses "1" = home win, "2" = away win (decimal)
                odds  = ev.get("odds", {})
                h_dec = odds.get("1")
                a_dec = odds.get("2")
                h_ml  = decimal_to_american(float(h_dec)) if h_dec else None
                a_ml  = decimal_to_american(float(a_dec)) if a_dec else None

                dt = datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d") if ts else ""

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
            except:
                continue

        if games:
            return games

    except Exception as e:
        print(f"    JSON method failed: {e}", end=" ")

    # Fallback: parse HTML table rows
    print("    Trying HTML fallback...", end=" ")
    try:
        rows = driver.find_elements(By.CSS_SELECTOR, "div.eventRow")
        for row in rows:
            try:
                teams = row.find_elements(By.CSS_SELECTOR, "a[href*='/basketball/usa/nba/']")
                if len(teams) < 2: continue
                away = teams[0].text.strip()
                home = teams[1].text.strip()

                scores = row.find_elements(By.CSS_SELECTOR, "span[class*='score'], div[class*='score']")
                if len(scores) < 2: continue
                a_score = int(scores[0].text.strip())
                h_score = int(scores[1].text.strip())

                # Odds cells
                odds_els = row.find_elements(By.CSS_SELECTOR, "div[class*='odds'], span[class*='odds']")
                h_ml = a_ml = None
                if len(odds_els) >= 2:
                    try:
                        h_dec = float(odds_els[0].text.strip())
                        a_dec = float(odds_els[1].text.strip())
                        h_ml  = decimal_to_american(h_dec)
                        a_ml  = decimal_to_american(a_dec)
                    except: pass

                games.append({
                    "date":       "",
                    "home":       home,
                    "away":       away,
                    "home_score": h_score,
                    "away_score": a_score,
                    "home_won":   h_score > a_score,
                    "total":      h_score + a_score,
                    "h_ml":       h_ml,
                    "a_ml":       a_ml,
                })
            except: continue
    except Exception as e:
        print(f"HTML fallback failed: {e}", end=" ")

    return games


# ── SCRAPE ALL PAGES ──────────────────────────────────────────────────────────
def scrape_all(driver):
    all_games = []
    page      = 1

    while True:
        url = BASE_URL if page == 1 else f"{BASE_URL}#/page/{page}/"
        print(f"  Page {page} ({url})...", end=" ", flush=True)

        games = scrape_page(driver, url)
        print(f"→ {len(games)} games")

        if not games:
            print(f"  No games on page {page} — stopping")
            break

        all_games.extend(games)
        page += 1

        # OddsPortal NBA season ~50 pages max
        if page > 60:
            break

        time.sleep(2)

    return all_games


# ── SIMULATE ──────────────────────────────────────────────────────────────────
def simulate(games):
    picks    = []
    no_odds  = 0

    for g in games:
        h_ml = g.get("h_ml")
        a_ml = g.get("a_ml")

        if h_ml and a_ml:
            h_prob, a_prob = true_probs(h_ml, a_ml)
        else:
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
            "date":      g.get("date", ""),
            "matchup":   f"{g['away']} @ {g['home']}",
            "pick_side": side,
            "pick_prob": prob,
            "pick_odds": odds,
            "result":    result,
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

    total     = len(picks)
    wins      = sum(1 for x in picks if x["result"] == "W")
    with_odds = [x for x in picks if x["pick_odds"] is not None]

    p("\n" + "━"*62)
    p("  NBA AI PREDICTOR — FULL SEASON BACKTEST  2025-26")
    p("━"*62)
    p(f"\n  Total graded picks : {total}")
    p(f"  Picks with real ML : {len(with_odds)}")
    p(f"  Overall record     : {wins}-{total-wins}  ({pct(wins, total)})")
    p(f"  {bar(wins, total)}")

    p(f"\n{'─'*62}")
    p("  FLAT BET P&L  (picks with real moneyline odds)")
    p(f"{'─'*62}")
    p(f"  {'Stake':>6}  {'P&L':>9}  {'ROI':>7}  {'Per pick':>9}")
    for stake in [10, 25, 50]:
        pnl     = sum(profit(x["pick_odds"], x["result"], stake) for x in with_odds)
        wagered = stake * len(with_odds)
        roi     = pnl / wagered * 100 if wagered else 0
        sign    = "+" if pnl >= 0 else ""
        n       = len(with_odds) or 1
        p(f"  ${stake:>5}  {sign}${pnl:>8.2f}  {sign}{roi:>5.1f}%  {sign}${pnl/n:>7.2f}")

    p(f"\n{'─'*62}")
    p("  BY CONFIDENCE BUCKET")
    p(f"{'─'*62}")
    for cb in ["50-59%", "60-69%", "70-79%", "80+%"]:
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
        grp  = [x for x in picks if fn(x["pick_odds"])]
        if not grp: continue
        gw   = sum(1 for x in grp if x["result"] == "W")
        pnl  = sum(profit(x["pick_odds"], x["result"], 10) for x in grp)
        sign = "+" if pnl >= 0 else ""
        p(f"  {label:<20} {len(grp):>4} picks  {gw}-{len(grp)-gw}  ({pct(gw,len(grp))})  $10: {sign}${pnl:.2f}")

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

    p(f"\n{'━'*62}\n")

    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Saved → {RESULT_FILE}")


# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if os.path.exists(CACHE_FILE):
        print(f"Loading cache from {CACHE_FILE}...")
        with open(CACHE_FILE) as f:
            games = json.load(f)
        print(f"  {len(games)} games loaded")
    else:
        print("Starting Chrome (headless)...")
        driver = make_driver()
        try:
            games = scrape_all(driver)
        finally:
            driver.quit()

        if games:
            with open(CACHE_FILE, "w") as f:
                json.dump(games, f, indent=2)
            print(f"\nCached {len(games)} games → {CACHE_FILE}")
        else:
            print("No games scraped — check OddsPortal structure")
            exit(1)

    completed = [g for g in games if g.get("home_score") is not None]
    print(f"Simulating {len(completed)} completed games...")
    picks = simulate(completed)
    report(picks)
