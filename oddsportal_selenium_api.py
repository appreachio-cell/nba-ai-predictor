"""
oddsportal_selenium_api.py — Uses Selenium to execute the AJAX call in browser context,
bypassing bot detection. Fetches all pages and caches results.

Run: python oddsportal_selenium_api.py
"""

import json, os, re, time
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

TOURNAMENT_ID = "OIo52B5b"
FILTER_STR    = ("X202178560X0X0X0X0X0X0X0X0X0X0X0X0X134217728X0X0X0X0X0X8X512"
                 "X32X0X0X0X0X0X0X0X536870912X2560X2048X0X33554560X8519680X0X0X0X524288")


# ── ODDS MATH ─────────────────────────────────────────────────────────────────
def implied(odds):
    o = float(odds)
    return abs(o) / (abs(o) + 100) if o < 0 else 100 / (o + 100)

def true_probs(o1, o2):
    p1 = implied(o1); p2 = implied(o2); t = p1 + p2
    return p1 / t, p2 / t

def decimal_to_american(dec):
    if dec is None: return None
    d = float(dec)
    if d <= 1.01: return None
    if d >= 2.0:  return round((d - 1) * 100)
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
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    service = Service(ChromeDriverManager().install())
    driver  = webdriver.Chrome(service=service, options=opts)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver


def fetch_page_via_browser(driver, page):
    """Use the browser's fetch() to call the AJAX endpoint with proper cookies/headers."""
    url = (f"https://www.oddsportal.com/ajax-sport-country-tournament-archive_/"
           f"3/{TOURNAMENT_ID}/{FILTER_STR}/{page}/0/?_={int(time.time()*1000)}")

    js = f"""
    return new Promise((resolve, reject) => {{
        fetch("{url}", {{
            headers: {{
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": "https://www.oddsportal.com/basketball/usa/nba/results/"
            }},
            credentials: "include"
        }})
        .then(r => r.text())
        .then(t => resolve(t))
        .catch(e => reject(e.toString()));
    }});
    """
    try:
        result = driver.execute_async_script("""
            var callback = arguments[arguments.length - 1];
            """ + js.replace("return new Promise", "var p = new Promise").replace(
            "return new Promise((resolve, reject) => {",
            "var p = new Promise((resolve, reject) => {"
        ).replace("resolve(t)", "callback(t)").replace("reject(e.toString())", "callback('ERROR:'+e.toString())"))
        return result
    except Exception as e:
        # Fallback: navigate directly
        try:
            driver.get(url)
            time.sleep(2)
            body = driver.find_element(By.TAG_NAME, "body").text
            return body
        except:
            return None


def fetch_page_direct(driver, page):
    """Navigate directly to the AJAX URL and grab the body text."""
    url = (f"https://www.oddsportal.com/ajax-sport-country-tournament-archive_/"
           f"3/{TOURNAMENT_ID}/{FILTER_STR}/{page}/0/?_={int(time.time()*1000)}")
    try:
        driver.get(url)
        time.sleep(3)
        body = driver.find_element(By.TAG_NAME, "pre").text
        return body
    except:
        try:
            body = driver.find_element(By.TAG_NAME, "body").text
            return body
        except:
            return None


# ── PARSE RESPONSE ────────────────────────────────────────────────────────────
def parse_response(raw):
    if not raw or raw.startswith("ERROR"):
        return [], False

    # Strip JSONP wrapper if present
    raw = raw.strip()
    m = re.search(r'\{.*\}|\[.*\]', raw, re.DOTALL)
    if not m:
        return [], False

    try:
        data = json.loads(m.group(0))
    except:
        return [], False

    games    = []
    has_more = False

    def walk(obj, depth=0):
        if depth > 6: return
        if isinstance(obj, list):
            for item in obj:
                if isinstance(item, dict) and ("home-name" in item or "home_name" in item):
                    g = parse_game(item)
                    if g: games.append(g)
                else:
                    walk(item, depth+1)
        elif isinstance(obj, dict):
            # Check pagination
            nonlocal has_more
            if obj.get("pagination", {}).get("hasNextPage"):
                has_more = True
            if obj.get("isLastPage") is False:
                has_more = True

            for k, v in obj.items():
                if k in ("rows", "events", "data", "results", "d", "oddsdata"):
                    walk(v, depth+1)
                elif isinstance(v, (list, dict)):
                    walk(v, depth+1)

    walk(data)
    return games, has_more


def parse_game(row):
    try:
        home    = row.get("home-name") or row.get("home_name") or row.get("home","")
        away    = row.get("away-name") or row.get("away_name") or row.get("away","")
        h_score = row.get("home-score") or row.get("home_score") or row.get("score-home")
        a_score = row.get("away-score") or row.get("away_score") or row.get("score-away")

        if not home or not away or h_score is None or a_score is None:
            return None

        ts = row.get("date-start-timestamp") or row.get("date_start_timestamp") or 0
        try: dt = datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d")
        except: dt = ""

        odds  = row.get("odds") or {}
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


# ── SCRAPE ALL ────────────────────────────────────────────────────────────────
def scrape_all():
    print("Starting Chrome (headless)...")
    driver = make_driver()
    all_games = []

    try:
        # Load the main page first to get cookies
        print("Loading main page to get session cookies...")
        driver.get("https://www.oddsportal.com/basketball/usa/nba/results/")
        time.sleep(5)

        page = 1
        while page <= 60:
            print(f"  Page {page}...", end=" ", flush=True)
            raw = fetch_page_direct(driver, page)

            if not raw:
                print("empty — stopping")
                break

            # Save page 1 raw for debugging
            if page == 1:
                with open("oddsportal_raw_p1.txt", "w", encoding="utf-8") as f:
                    f.write(raw)
                print(f"(raw saved)", end=" ")

            games, has_more = parse_response(raw)
            print(f"→ {len(games)} games", end="")

            if not games:
                print(f"\n    Raw snippet: {raw[:300]}")
                break

            all_games.extend(games)
            print(f"  (total: {len(all_games)})")

            if not has_more:
                print("  Last page reached")
                break

            page += 1
            time.sleep(2)

    finally:
        driver.quit()

    return all_games


# ── SIMULATE ──────────────────────────────────────────────────────────────────
def simulate(games):
    picks = []; no_odds = 0
    for g in games:
        h_ml = g.get("h_ml"); a_ml = g.get("a_ml")
        if h_ml and a_ml:
            h_prob, a_prob = true_probs(h_ml, a_ml)
        else:
            h_prob, a_prob = 0.54, 0.46; h_ml = a_ml = None; no_odds += 1
        side   = "home" if h_prob >= a_prob else "away"
        prob   = h_prob if side == "home" else a_prob
        odds   = h_ml   if side == "home" else a_ml
        result = "W" if (side=="home" and g["home_won"]) or (side=="away" and not g["home_won"]) else "L"
        picks.append({"date":g.get("date",""),"matchup":f"{g['away']} @ {g['home']}",
                      "pick_side":side,"pick_prob":prob,"pick_odds":odds,"result":result})
    if no_odds: print(f"  ⚠ {no_odds}/{len(games)} games missing odds")
    return picks


# ── REPORT ────────────────────────────────────────────────────────────────────
def report(picks):
    lines = []
    def p(*args):
        s=" ".join(str(a) for a in args); print(s); lines.append(s)

    total=len(picks); wins=sum(1 for x in picks if x["result"]=="W")
    with_odds=[x for x in picks if x["pick_odds"] is not None]

    p("\n"+"━"*62)
    p("  NBA AI PREDICTOR — FULL SEASON BACKTEST  2025-26")
    p("━"*62)
    p(f"\n  Total picks        : {total}")
    p(f"  With real ML odds  : {len(with_odds)}")
    p(f"  Overall record     : {wins}-{total-wins}  ({pct(wins,total)})")
    p(f"  {bar(wins,total)}")

    if with_odds:
        p(f"\n{'─'*62}")
        p("  FLAT BET P&L")
        p(f"{'─'*62}")
        p(f"  {'Stake':>6}  {'P&L':>9}  {'ROI':>7}  {'Per pick':>9}")
        for stake in [10,25,50]:
            pnl=sum(profit(x["pick_odds"],x["result"],stake) for x in with_odds)
            wagered=stake*len(with_odds); roi=pnl/wagered*100 if wagered else 0
            sign="+" if pnl>=0 else ""; n=len(with_odds)
            p(f"  ${stake:>5}  {sign}${pnl:>8.2f}  {sign}{roi:>5.1f}%  {sign}${pnl/n:>7.2f}")

    p(f"\n{'─'*62}"); p("  BY CONFIDENCE BUCKET"); p(f"{'─'*62}")
    for cb in ["50-59%","60-69%","70-79%","80+%"]:
        bp=[x for x in picks if conf_bucket(x["pick_prob"])==cb]
        if not bp: continue
        bw=sum(1 for x in bp if x["result"]=="W"); bt=len(bp)
        bo=[x for x in bp if x["pick_odds"] is not None]
        pnl=sum(profit(x["pick_odds"],x["result"],10) for x in bo)
        aodds=sum(float(x["pick_odds"]) for x in bo)/len(bo) if bo else 0
        sign="+" if pnl>=0 else ""
        p(f"\n  {cb}  —  {bt} games  ({len(bo)} with odds)")
        p(f"  {bar(bw,bt,15)} {bw}-{bt-bw} ({pct(bw,bt)})")
        if bo: p(f"  Avg odds: {fmt_odds(aodds)}   $10 P&L: {sign}${pnl:.2f}")

    p(f"\n{'─'*62}"); p("  MONTH BY MONTH"); p(f"{'─'*62}")
    by_month={}
    for x in picks:
        key=x["date"][:7] if x["date"] else "unknown"
        by_month.setdefault(key,[]).append(x)
    for mo in sorted(by_month):
        mp=by_month[mo]; mw=sum(1 for x in mp if x["result"]=="W"); mt=len(mp)
        pnl=sum(profit(x["pick_odds"],x["result"],10) for x in mp)
        sign="+" if pnl>=0 else ""
        try: label=datetime.strptime(mo,"%Y-%m").strftime("%B %Y")
        except: label=mo
        p(f"  {label:<18} {bar(mw,mt,12)} {mw}-{mt-mw} ({pct(mw,mt)})  $10: {sign}${pnl:.2f}")

    p(f"\n{'━'*62}\n")
    with open(RESULT_FILE,"w",encoding="utf-8") as f: f.write("\n".join(lines))
    print(f"Saved → {RESULT_FILE}")


# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if os.path.exists(CACHE_FILE):
        print(f"Loading cache...")
        with open(CACHE_FILE) as f: games=json.load(f)
        print(f"  {len(games)} games")
    else:
        games = scrape_all()
        if games:
            with open(CACHE_FILE,"w") as f: json.dump(games,f,indent=2)
            print(f"Cached {len(games)} games → {CACHE_FILE}")
        else:
            print("\n❌ No games scraped. Upload oddsportal_raw_p1.txt here.")
            exit(1)

    completed=[g for g in games if g.get("home_score") is not None]
    print(f"Simulating {len(completed)} games...")
    picks=simulate(completed)
    report(picks)
