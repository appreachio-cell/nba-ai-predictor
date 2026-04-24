"""
backtest_ou.py — Backtest O/U picks across all saved history.

Run:  cd C:/NBA && python backtest_ou.py

Scans every file in picks_history/, cross-checks total_lean vs actual
game total from ESPN, and prints a full breakdown by direction, line
range, and month.
"""

import json, os, sys
from datetime import datetime
from collections import defaultdict

# Allow running from C:/NBA without installing the package
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import HISTORY_DIR
from espn import espn_schedule
from utils import fmt_odds, calc_ev


# ── COLLECT ALL O/U PICKS ─────────────────────────────────────────────────────
def load_all_ou_picks():
    picks = []
    for fn in sorted(os.listdir(HISTORY_DIR)):
        if not fn.endswith(".json"):
            continue
        date_str = fn.replace(".json", "")
        try:
            with open(os.path.join(HISTORY_DIR, fn)) as f:
                hdata = json.load(f)
        except:
            continue

        for pg in hdata.get("games", []):
            ai   = pg.get("ai", {})
            pred = pg.get("pred", {})
            lean = ai.get("total_lean") or pred.get("tot_dir")
            line = pred.get("total_line")
            if not lean or not line:
                continue

            picks.append({
                "date":       date_str,
                "home":       pg.get("homeAbbr", ""),
                "away":       pg.get("awayAbbr", ""),
                "lean":       lean,
                "line":       float(line),
                "over_odds":  pred.get("over_odds"),
                "under_odds": pred.get("under_odds"),
                "tot_conf":   ai.get("total_confidence"),
                "result":     pg.get("tot_result"),          # already graded
                "espn_id":    pg.get("espn_id", ""),
            })
    return picks


# ── FETCH MISSING RESULTS FROM ESPN ──────────────────────────────────────────
def fill_missing_results(picks):
    """For picks without a tot_result, fetch the final score from ESPN."""
    by_date = defaultdict(list)
    for p in picks:
        if p["result"] is None:
            by_date[p["date"]].append(p)

    for date_str, day_picks in by_date.items():
        print(f"  Fetching ESPN scores for {date_str}...")
        try:
            games = espn_schedule(date_str)
            score_map = {
                f"{g['awayAbbr']}@{g['homeAbbr']}": g
                for g in games if g["completed"]
            }
            for p in day_picks:
                key = f"{p['away']}@{p['home']}"
                rg  = score_map.get(key)
                if not rg:
                    continue
                actual = rg["totalPts"]
                if actual == 0:
                    continue
                line   = p["line"]
                p["actual"] = actual
                if actual == line:
                    p["result"] = "P"   # push
                elif (p["lean"] == "OVER"  and actual > line) or \
                     (p["lean"] == "UNDER" and actual < line):
                    p["result"] = "W"
                else:
                    p["result"] = "L"
        except Exception as e:
            print(f"    Error: {e}")

    return picks


# ── P&L CALCULATOR ────────────────────────────────────────────────────────────
def pnl(result, lean, over_odds, under_odds, stake=10):
    if result not in ("W", "L"):
        return 0.0
    odds = over_odds if lean == "OVER" else under_odds
    if odds is None:
        odds = -110   # assume standard juice if missing
    o = float(odds)
    if result == "W":
        return round(stake * (100 / abs(o)) if o < 0 else stake * (o / 100), 2)
    return -stake


# ── PRINT HELPERS ─────────────────────────────────────────────────────────────
def pct(w, t):
    return f"{round(w / t * 100, 1)}%" if t else "—"

def bar(w, t, width=30):
    if not t:
        return " " * width
    filled = round(w / t * width)
    return "█" * filled + "░" * (width - filled)

def pnl_str(v):
    return f"+${v:.2f}" if v >= 0 else f"-${abs(v):.2f}"


# ── MAIN REPORT ───────────────────────────────────────────────────────────────
def main():
    print("\n📊  NBA O/U Backtest — loading history...\n")
    picks = load_all_ou_picks()
    print(f"  Found {len(picks)} O/U picks in history\n")

    graded_already = sum(1 for p in picks if p["result"] is not None)
    print(f"  Already graded: {graded_already} | Need ESPN lookup: {len(picks) - graded_already}\n")

    if len(picks) - graded_already > 0:
        picks = fill_missing_results(picks)

    graded = [p for p in picks if p["result"] in ("W", "L")]
    pushes = [p for p in picks if p["result"] == "P"]

    if not graded:
        print("  No graded results found — check that past games are completed.")
        return

    # ── OVERALL ──────────────────────────────────────────────────────────────
    W   = sum(1 for p in graded if p["result"] == "W")
    L   = len(graded) - W
    tot = len(graded)
    total_pnl = sum(pnl(p["result"], p["lean"], p.get("over_odds"), p.get("under_odds")) for p in graded)

    print("=" * 60)
    print("  OVERALL O/U RECORD")
    print("=" * 60)
    print(f"  {W}-{L} ({pct(W, tot)})   Pushes: {len(pushes)}   P&L: {pnl_str(total_pnl)}")
    print(f"  {bar(W, tot)}")
    print()

    # ── BY DIRECTION ─────────────────────────────────────────────────────────
    print("-" * 60)
    print("  BY DIRECTION")
    print("-" * 60)
    for direction in ("OVER", "UNDER"):
        dp = [p for p in graded if p["lean"] == direction]
        dw = sum(1 for p in dp if p["result"] == "W")
        dl = pnl_str(sum(pnl(p["result"], p["lean"], p.get("over_odds"), p.get("under_odds")) for p in dp))
        print(f"  {direction:<8} {dw}-{len(dp)-dw} ({pct(dw, len(dp))})   P&L: {dl}")
    print()

    # ── BY CONFIDENCE ─────────────────────────────────────────────────────────
    conf_picks = [p for p in graded if p.get("tot_conf") is not None]
    if conf_picks:
        print("-" * 60)
        print("  BY CONFIDENCE")
        print("-" * 60)
        buckets = [("50-59", 50, 59), ("60-69", 60, 69), ("70-79", 70, 79), ("80+", 80, 100)]
        for label, lo, hi in buckets:
            bp = [p for p in conf_picks if lo <= (p.get("tot_conf") or 0) <= hi]
            if not bp:
                continue
            bw = sum(1 for p in bp if p["result"] == "W")
            bl = pnl_str(sum(pnl(p["result"], p["lean"], p.get("over_odds"), p.get("under_odds")) for p in bp))
            print(f"  {label}%   {bw}-{len(bp)-bw} ({pct(bw, len(bp))})   P&L: {bl}   {bar(bw, len(bp), 20)}")
        print()

    # ── BY LINE RANGE ─────────────────────────────────────────────────────────
    print("-" * 60)
    print("  BY TOTAL LINE RANGE")
    print("-" * 60)
    ranges = [
        ("<215",   0,   214.9),
        ("215-219", 215, 219.9),
        ("220-224", 220, 224.9),
        ("225-229", 225, 229.9),
        ("230-234", 230, 234.9),
        ("235+",   235, 999),
    ]
    for label, lo, hi in ranges:
        rp = [p for p in graded if lo <= p["line"] <= hi]
        if not rp:
            continue
        rw = sum(1 for p in rp if p["result"] == "W")
        rl = pnl_str(sum(pnl(p["result"], p["lean"], p.get("over_odds"), p.get("under_odds")) for p in rp))
        print(f"  {label:<8}  {rw}-{len(rp)-rw} ({pct(rw, len(rp))})   P&L: {rl}   {bar(rw, len(rp), 20)}")
    print()

    # ── BY MONTH ──────────────────────────────────────────────────────────────
    print("-" * 60)
    print("  BY MONTH")
    print("-" * 60)
    by_month = defaultdict(list)
    for p in graded:
        by_month[p["date"][:7]].append(p)
    for month in sorted(by_month):
        mp  = by_month[month]
        mw  = sum(1 for p in mp if p["result"] == "W")
        ml  = pnl_str(sum(pnl(p["result"], p["lean"], p.get("over_odds"), p.get("under_odds")) for p in mp))
        try:
            mlabel = datetime.strptime(month, "%Y-%m").strftime("%B %Y")
        except:
            mlabel = month
        print(f"  {mlabel:<14}  {mw}-{len(mp)-mw} ({pct(mw, len(mp))})   P&L: {ml}")
    print()

    # ── GAME LOG ─────────────────────────────────────────────────────────────
    print("-" * 60)
    print("  FULL GAME LOG")
    print("-" * 60)
    print(f"  {'Date':<12} {'Matchup':<14} {'Lean':<6} {'Line':<7} {'Conf':<6} {'Result':<6} {'Actual':<8} P&L")
    print(f"  {'-'*11} {'-'*13} {'-'*5} {'-'*6} {'-'*5} {'-'*6} {'-'*7} {'-'*7}")
    for p in sorted(graded, key=lambda x: x["date"]):
        matchup = f"{p['away']}@{p['home']}"
        conf    = str(p.get("tot_conf") or "—")
        actual  = str(p.get("actual", "—"))
        result  = p["result"]
        gp      = pnl(result, p["lean"], p.get("over_odds"), p.get("under_odds"))
        marker  = "✓" if result == "W" else "✗"
        print(
            f"  {p['date']:<12} {matchup:<14} {p['lean']:<6} "
            f"{p['line']:<7} {conf:<6} {marker} {result:<4} {actual:<8} {pnl_str(gp)}"
        )

    print()
    print(f"  Total: {W}-{L} ({pct(W, tot)})   P&L: {pnl_str(total_pnl)}")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
