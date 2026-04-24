"""
backtest.py — Analyse every saved pick in picks_history/.

Run:  python backtest.py

What it shows:
  • Overall W-L and hit rate
  • Breakdown by confidence bucket with avg odds
  • Are the 80+% picks just chalk? (shows avg odds per bucket)
  • P&L at $10, $25, $50 flat bet
  • P&L at Kelly-fraction sizing
  • Best and worst picks
  • Day-by-day summary
"""

import json, os
from datetime import datetime

# ── CONFIG ────────────────────────────────────────────────────────────────────
try:
    from config import HISTORY_DIR
except ImportError:
    HISTORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "picks_history")

FLAT_BETS = [10, 25, 50]   # bet sizes to simulate


# ── HELPERS ───────────────────────────────────────────────────────────────────
def fmt_odds(o):
    if o is None: return "  n/a "
    return f"+{int(o):4d}" if float(o) > 0 else f"{int(o):5d}"

def profit(odds, result, stake=10):
    """Return profit/loss for a single bet."""
    if odds is None: return 0.0
    o = float(odds)
    if result == "W":
        return stake * (100 / abs(o)) if o < 0 else stake * (o / 100)
    return -stake

def conf_bucket(conf):
    if conf is None: return "unknown"
    if conf >= 80:   return "80+%"
    if conf >= 70:   return "70-79%"
    if conf >= 60:   return "60-69%"
    return "50-59%"

def avg(lst):
    return sum(lst) / len(lst) if lst else 0.0

def pct(w, t):
    return f"{round(w/t*100,1)}%" if t else "—"

def bar(w, t, width=20):
    filled = round(w / t * width) if t else 0
    return "█" * filled + "░" * (width - filled)


# ── LOAD ALL PICKS ────────────────────────────────────────────────────────────
def load_all_picks():
    picks = []
    for fn in sorted(os.listdir(HISTORY_DIR)):
        if not fn.endswith(".json"): continue
        try:
            with open(os.path.join(HISTORY_DIR, fn)) as f:
                day = json.load(f)
        except: continue

        date_str = day.get("date", fn.replace(".json", ""))

        for g in day.get("games", []):
            # Support both old format (pick dict) and new format (ai + pred dicts)
            ai   = g.get("ai", {})
            pred = g.get("pred", {})
            old  = g.get("pick", {})

            # Result
            result = g.get("result") or old.get("result") or pred.get("result")
            if result not in ("W", "L"): continue   # skip ungraded

            # Confidence
            conf = (ai.get("confidence")
                    or old.get("conf")
                    or pred.get("conf"))
            if conf is None and pred.get("h_prob"):
                side = ai.get("pick") or old.get("win_side", "home")
                prob = pred.get("h_prob") if side == "home" else pred.get("a_prob")
                conf = round(prob * 100) if prob else None

            # Odds on the pick
            side = ai.get("pick") or old.get("win_side", "home")
            odds = (pred.get("h_odds") if side == "home" else pred.get("a_odds")) \
                   or old.get("win_odds")

            # Teams
            home = g.get("homeTeam") or old.get("homeTeam", "?")
            away = g.get("awayTeam") or old.get("awayTeam", "?")
            pick_team = (ai.get("pick_team") or old.get("pick_team")
                         or (home if side == "home" else away))

            picks.append({
                "date":      date_str,
                "matchup":   f"{away} @ {home}",
                "pick_team": pick_team,
                "conf":      conf,
                "odds":      odds,
                "result":    result,
                "reasoning": ai.get("reasoning") or "",
            })

    return picks


# ── ANALYSIS ──────────────────────────────────────────────────────────────────
def analyse(picks):
    if not picks:
        print("No graded picks found in picks_history/")
        return

    total = len(picks)
    wins  = sum(1 for p in picks if p["result"] == "W")

    print("\n" + "━" * 58)
    print("  NBA AI PREDICTOR — BACKTEST REPORT")
    print("━" * 58)
    print(f"\n  Total picks : {total}")
    print(f"  Record      : {wins}-{total-wins}  ({pct(wins, total)})")
    print(f"  {bar(wins, total)} {pct(wins, total)}")

    # ── P&L at flat bet sizes ─────────────────────────────────────────────────
    print(f"\n{'─'*58}")
    print("  FLAT BET P&L")
    print(f"{'─'*58}")
    header = f"  {'Stake':>6}  {'P&L':>8}  {'ROI':>7}  {'Per pick':>9}"
    print(header)
    for stake in FLAT_BETS:
        pnl     = sum(profit(p["odds"], p["result"], stake) for p in picks)
        wagered = stake * total
        roi     = pnl / wagered * 100 if wagered else 0
        sign    = "+" if pnl >= 0 else ""
        print(f"  ${stake:>5}  {sign}${pnl:>7.2f}  {sign}{roi:>5.1f}%  {sign}${pnl/total:>7.2f}")

    # ── By confidence bucket ──────────────────────────────────────────────────
    print(f"\n{'─'*58}")
    print("  BY CONFIDENCE BUCKET  (were 80+% picks just chalk?)")
    print(f"{'─'*58}")

    buckets = ["50-59%", "60-69%", "70-79%", "80+%"]
    for cb in buckets:
        bp    = [p for p in picks if conf_bucket(p["conf"]) == cb]
        if not bp: continue
        bw    = sum(1 for p in bp if p["result"] == "W")
        bt    = len(bp)
        odds_list = [float(p["odds"]) for p in bp if p["odds"] is not None]
        avg_o = avg(odds_list)
        pnl10 = sum(profit(p["odds"], p["result"], 10) for p in bp)
        sign  = "+" if pnl10 >= 0 else ""

        # Flag if avg odds suggest chalk
        chalk = ""
        if avg_o < -200: chalk = "  ⚠ heavy chalk (avg odds suggest low value)"
        elif avg_o < -130: chalk = "  moderate favourite"
        else: chalk = "  ✓ reasonable odds range"

        print(f"\n  {cb}")
        print(f"  {bar(bw, bt, 15)} {bw}-{bt-bw} ({pct(bw, bt)})")
        print(f"  Avg odds : {fmt_odds(avg_o)}   Min: {fmt_odds(min(odds_list) if odds_list else None)}   Max: {fmt_odds(max(odds_list) if odds_list else None)}")
        print(f"  $10 flat : {sign}${pnl10:.2f}{chalk}")

    # ── Odds distribution ─────────────────────────────────────────────────────
    print(f"\n{'─'*58}")
    print("  ODDS DISTRIBUTION  (how often are we picking big favourites?)")
    print(f"{'─'*58}")
    ranges = [
        ("-400 or worse",  lambda o: o <= -400),
        ("-300 to -399",   lambda o: -400 < o <= -300),
        ("-200 to -299",   lambda o: -300 < o <= -200),
        ("-130 to -199",   lambda o: -200 < o <= -130),
        ("pick / +odds",   lambda o: o > -130),
    ]
    for label, fn in ranges:
        grp = [p for p in picks if p["odds"] is not None and fn(float(p["odds"]))]
        if not grp: continue
        gw = sum(1 for p in grp if p["result"] == "W")
        print(f"  {label:<20} {len(grp):>3} picks  {gw}-{len(grp)-gw}  ({pct(gw, len(grp))})")

    # ── Day by day ────────────────────────────────────────────────────────────
    print(f"\n{'─'*58}")
    print("  DAY BY DAY")
    print(f"{'─'*58}")
    by_day = {}
    for p in picks:
        by_day.setdefault(p["date"], []).append(p)
    for ds in sorted(by_day):
        dp  = by_day[ds]
        dw  = sum(1 for p in dp if p["result"] == "W")
        dt  = len(dp)
        try:    label = datetime.strptime(ds, "%Y-%m-%d").strftime("%b %d")
        except: label = ds
        pnl = sum(profit(p["odds"], p["result"], 10) for p in dp)
        sign = "+" if pnl >= 0 else ""
        print(f"  {label}  {bar(dw, dt, 10)} {dw}-{dt-dw}  $10 flat: {sign}${pnl:.2f}")

    # ── Best and worst picks ──────────────────────────────────────────────────
    graded_with_odds = [p for p in picks if p["odds"] is not None]
    if graded_with_odds:
        print(f"\n{'─'*58}")
        print("  NOTABLE PICKS")
        print(f"{'─'*58}")

        # Biggest upsets won (best underdog wins)
        wins_plus = [p for p in graded_with_odds if p["result"] == "W" and float(p["odds"]) > 0]
        if wins_plus:
            best = max(wins_plus, key=lambda p: float(p["odds"]))
            print(f"\n  Best underdog win:")
            print(f"  {best['pick_team']} {fmt_odds(best['odds'])} ✓  ({best['date']})")

        # Losses on big favourites (most painful)
        losses_fav = [p for p in graded_with_odds if p["result"] == "L" and float(p["odds"]) < -150]
        if losses_fav:
            worst = min(losses_fav, key=lambda p: float(p["odds"]))
            print(f"\n  Worst loss (big favourite that lost):")
            print(f"  {worst['pick_team']} {fmt_odds(worst['odds'])} ✗  ({worst['date']})")

    print(f"\n{'━'*58}\n")


# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    picks = load_all_picks()
    analyse(picks)
